"""v2 雷切排版：把零件排進 255×355 的板（合板、壓克力分開排）。

用法
----
    from laser_v2.layout import layout
    sheets = layout(parts)              # parts: list[V2Part]（compose.compose() 的結果）
    for s in sheets:
        s.material, s.no, s.w, s.h      # 材質、同材質內第幾張（1 起算）、板寬高 mm
        for pl in s.items:              # Placement
            pl.part, pl.copy, pl.M      # 零件、第幾份（0 起算）、3×3 矩陣（零件座標 → 板座標）
            pl.spare                    # 這一份是不是備品（copy ≥ qty）
            pl.rot                      # 轉了幾度（0/90/180/270）
            pl.geom                     # 排好後的 shapely 外形（板座標）
        s.util                          # 利用率＝零件淨面積（外框減孔）／板面積
        s.unplaced                      # 這個材質放不進現有板的備品（只記在該材質最後一張）
    unplaced_spares(sheets)             # 全部放不下的備品說明（空＝備品全部排進去了）

規則（params）
--------------
* 每張板 params.SHEET（255×355），零件離板邊 ≥ SHEET_MARGIN、零件之間 ≥ PART_GAP。
  間距是「真實外形」距離（shapely 外形，含曲線取樣），不是外接框。
* 合板、壓克力分開排（壓克力也用 255×355）；同一個 group 的零件排在同一張板；
  qty>1 的零件每一份各一個 Placement；零件只轉 0／90／180／270 度，不鏡像（雕刻面不能翻）。
* 備品（V2Part.spare，每套多切幾份；使用者 2026-10-08：極小零件每套多一整份）：正式的 qty 份
  照下面的演算法排完、張數定了以後，備品（copy＝qty … qty+spare−1）才逐件塞進「已經開的板」，
  先試同零件正式份所在的板，再依板序；不會為備品開新板（不增加張數）。放不下的不排，
  記在該材質最後一張的 Sheet.unplaced，用 unplaced_spares(sheets) 取出回報。
  備品不受 group 限制（只是替換用）。
* 彎曲條（#27 這種有很多開放鋸縫的零件）只轉 0／180 度，保持和原始檔相同的方向：
  原檔的彎曲條在直式 300×400 板上直放，鋸縫橫向；合板表層木紋通常沿板的長邊，
  這樣鋸縫和木紋垂直，轉 90 度會變成順紋，鋸縫之間的橋容易裂（假設板材木紋沿長邊）。

演算法
------
點陣＋FFT 相關運算的「上左靠齊」排法（bottom-left fill 的變形，SVG 座標 y 向下所以是往上靠）：
1. 每個零件（每種轉角）做一張「佔用點陣」：格寬 RES mm，格子中心落在
   外形.buffer(PART_GAP/2 + RES·√2/2 + 0.02) 裡就算佔用。
   兩個零件的點陣沒有共同格子 ⇒ 兩者外形距離 ≥ PART_GAP（保守，證明見 _footprint）。
   代價是實際間距多 0～0.7 mm（原始 60 件排出來最近 2.48 mm）。
2. 板子的佔用點陣和零件點陣做 FFT 相關運算（float32），一次得到所有平移位置的重疊格數；
   重疊 0、又在板邊界內（≥ SHEET_MARGIN，用真實外形的外接框算）的位置就是可放的位置。
   選中的位置再用逐格相乘核對一次，確定真的不重疊（不靠 FFT 的浮點誤差）。
3. 大件先排（first-fit decreasing）：每個零件依序試已開的板，找到可放的板就放在
   「最靠上、再靠左」（或「最靠左、再靠上」）的位置；四種轉角都試，取分數最好的。
   group 當成一個整體，一起放進同一張板，放不下就整組換下一張。
   某形狀在某張板放不下就記起來（板只會越排越滿），同形零件不再重試。
4. 三種排序（面積／最長邊／外接框面積）× 兩種靠齊方向各排一次，取張數最少、
   最後一張用得最少（排到的寬×高最小）的結果。整個流程沒有亂數，同輸入同輸出。
5. 「零件放在別的零件的孔裡」預設不用（NEST_IN_HOLES='auto'）：張數比面積下限多時，
   用最好的排序／靠齊再排一次「可放進孔裡」，能少張數才採用，並在 Sheet.notes 註明
   （雷切軟體要開「先切內部」）。
6. 排完用 shapely 逐對核對真實距離與板邊，不合就直接報錯（不會靜默輸出）。
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import shapely
from scipy.signal import fftconvolve
from shapely import affinity
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

from . import params

RES = 0.5                 # mm：佔用點陣格寬
GROW_EPS = 0.02           # mm：buffer 多邊形近似圓弧（弦在圓內）的補償
KERF_LINES_LOCK = 20      # 開放切割線 ≥ 這麼多條 → 視為彎曲條，只轉 0／180
ROT_LOCK: dict[str, tuple[int, ...]] = {}   # 指定零件可用的轉角，例如 {'#27': (0, 180)}；空＝自動判斷
NEST_IN_HOLES = 'auto'    # False：不放進別的零件的孔；True：可以；'auto'：能少張數才用
ORDERS = ('area', 'maxside', 'bbox')
GRAVITIES = ('top', 'left')
ROTS = (0, 90, 180, 270)


# ---------------------------------------------------------------------------
# 資料結構
# ---------------------------------------------------------------------------
def _affine_params(M: np.ndarray) -> list[float]:
    return [M[0, 0], M[0, 1], M[1, 0], M[1, 1], M[0, 2], M[1, 2]]


def qty_of(part) -> int:
    """每套數量（V2Part.qty；沒有或 0 時當 1）。"""
    return int(getattr(part, 'qty', 1) or 1)


def spare_of(part) -> int:
    """每套備品數（V2Part.spare；沒有這個欄位時 0）。"""
    s = int(getattr(part, 'spare', 0) or 0)
    if s < 0:
        raise ValueError(f'{part.id} 的 spare={s}，備品數不可以是負的')
    return s


@dataclass
class Placement:
    part: Any                 # V2Part
    copy: int                 # 第幾份（0 起算；copy ≥ qty 的是備品）
    M: np.ndarray             # 3×3：零件座標 → 板座標
    rot: int = 0              # 轉角（度）
    spare: bool = False       # 這一份是不是備品

    @property
    def geom(self):
        """排好後的外形（板座標）。"""
        return affinity.affine_transform(self.part.geom, _affine_params(self.M))

    @property
    def label(self) -> str:
        """代號標籤：正式份 'PIN-S50（1/2）'，備品 'PIN-S50（備品 1/2）'、只有 1 份備品時 'S1-P（備品）'。"""
        q = qty_of(self.part)
        if self.spare:
            n = spare_of(self.part)
            return f'{self.part.id}（備品）' if n <= 1 else f'{self.part.id}（備品 {self.copy - q + 1}/{n}）'
        return self.part.id if q <= 1 else f'{self.part.id}（{self.copy + 1}/{q}）'


@dataclass
class Sheet:
    material: str
    no: int
    w: float
    h: float
    items: list[Placement] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    unplaced: list[str] = field(default_factory=list)   # 放不進現有板的備品（只記在該材質最後一張）

    @property
    def n_spare(self) -> int:
        return sum(1 for pl in self.items if pl.spare)

    @property
    def area(self) -> float:
        return self.w * self.h

    @property
    def used_area(self) -> float:
        """零件淨面積（外框減孔）合計。"""
        return float(sum(pl.part.geom.area for pl in self.items))

    @property
    def outer_area(self) -> float:
        """零件外框面積（不扣孔）合計。"""
        return float(sum(_solid(pl.part.geom).area for pl in self.items))

    @property
    def util(self) -> float:
        return self.used_area / self.area

    @property
    def extent(self) -> tuple[float, float]:
        """排到的最右 x、最下 y（板座標）。"""
        if not self.items:
            return (0.0, 0.0)
        b = np.array([pl.geom.bounds for pl in self.items])
        return (float(b[:, 2].max()), float(b[:, 3].max()))

    @property
    def title(self) -> str:
        return f'{self.material} 第 {self.no} 張'


# ---------------------------------------------------------------------------
# 幾何工具
# ---------------------------------------------------------------------------
def _solid(g):
    """外形去掉孔（MultiPolygon 取各塊外框的聯集）。"""
    if isinstance(g, Polygon):
        return Polygon(g.exterior)
    if isinstance(g, MultiPolygon):
        return unary_union([Polygon(p.exterior) for p in g.geoms])
    return g


def rot_matrix(deg: int) -> np.ndarray:
    """繞原點轉 deg 度（SVG 座標 y 向下，畫面上看是順時針），3×3。"""
    c = {0: 1, 90: 0, 180: -1, 270: 0}[deg % 360]
    s = {0: 0, 90: 1, 180: 0, 270: -1}[deg % 360]
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def translate(dx: float, dy: float) -> np.ndarray:
    return np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1.0]])


def allowed_rots(part) -> tuple[int, ...]:
    if part.id in ROT_LOCK:
        return tuple(ROT_LOCK[part.id])
    closed = list(getattr(part, 'cut_closed', []) or [])
    if closed.count(False) >= KERF_LINES_LOCK:
        return (0, 180)
    return ROTS


@dataclass
class _Shape:
    """某零件某轉角的佔用點陣。"""
    R: np.ndarray        # 佔用格（float32 0/1），shape (rows, cols)
    ox: float            # 點陣左上角（區域座標，已正規化到外接框左上＝0）
    oy: float
    gw: float            # 真實外形寬高
    gh: float
    Mr: np.ndarray       # 3×3：零件座標 → 正規化區域座標（轉角＋平移到外接框左上＝0）
    cells: int = 0       # 佔用格數
    sig: tuple = ()      # 形狀簽章（同形零件共用，記「放不下」用）


def _footprint(geom, deg: int, res: float, grow: float, holes: bool) -> _Shape:
    """零件外形轉 deg 度、平移到外接框左上角＝(0,0)，做佔用點陣。

    保守性：若 A、B 兩外形距離 < g，取兩最近點的中點 m，m 同時在 A.buffer(g/2)、B.buffer(g/2) 內；
    m 所在格子的中心 c 與 m 相距 ≤ res·√2/2，所以 c 同時在兩者的 buffer(g/2 + res·√2/2) 內，
    兩張點陣都會標到 c 那格 ⇒ 有共同格子。反過來說，點陣不重疊 ⇒ 距離 ≥ g。
    （平移只用整數格，所以點陣平移後和重新點陣化完全相同。）"""
    Rm = rot_matrix(deg)
    g = affinity.affine_transform(geom, _affine_params(Rm))
    x0, y0, x1, y1 = g.bounds
    Mr = translate(-x0, -y0) @ Rm
    g = affinity.translate(g, -x0, -y0)
    if not holes:
        g = _solid(g)
    F = g.buffer(grow, quad_segs=16)
    fx0, fy0, fx1, fy1 = F.bounds
    ox = math.floor(fx0 / res) * res
    oy = math.floor(fy0 / res) * res
    nx = int(math.ceil((fx1 - ox) / res)) + 1
    ny = int(math.ceil((fy1 - oy) / res)) + 1
    xs = ox + (np.arange(nx) + 0.5) * res
    ys = oy + (np.arange(ny) + 0.5) * res
    X, Y = np.meshgrid(xs, ys)
    shapely.prepare(F)
    R = shapely.contains_xy(F, X, Y).astype(np.float32)
    sig = (R.shape, round(ox, 6), round(oy, 6), round(x1 - x0, 4), round(y1 - y0, 4),
           hashlib.blake2b(R.tobytes(), digest_size=16).hexdigest())
    return _Shape(R, ox, oy, x1 - x0, y1 - y0, Mr, int(R.sum()), sig)


class _SheetState:
    """一張板的佔用點陣與已排零件。"""

    def __init__(self, material: str, w: float, h: float, res: float, pad: int):
        self.material, self.w, self.h, self.res, self.pad = material, w, h, res, pad
        self.ny = int(math.ceil(h / res)) + 2 * pad
        self.nx = int(math.ceil(w / res)) + 2 * pad
        self.O = np.zeros((self.ny, self.nx), dtype=np.float32)
        self.free = self.ny * self.nx           # 空格數（只用來快速排除放不下的零件）
        self.items: list[tuple[Any, int, np.ndarray, int]] = []   # (part, copy, M, rot)
        self.fail: set = set()                  # 已確定放不下的零件形狀（佔用只增不減，所以永遠放不下）

    def copy(self) -> '_SheetState':
        s = _SheetState.__new__(_SheetState)
        s.__dict__.update(self.__dict__)
        s.O = self.O.copy()
        s.items = list(self.items)
        s.fail = set(self.fail)
        return s

    def best_position(self, shape: _Shape, gravity: str):
        """回傳 (score, i, j, tx, ty)，放不下回傳 None。

        FFT 用 float32 算（快），選中的位置再用整數逐格核對一次，確定重疊格數真的是 0。"""
        res, pad, m = self.res, self.pad, params.SHEET_MARGIN
        R = shape.R
        rh, rw = R.shape
        if rh > self.ny or rw > self.nx or shape.cells > self.free:
            return None
        base = -pad * res
        # 平移 t = (base + j·res − ox, base + i·res − oy)；真實外形外接框 = [t, t + (gw, gh)]
        jmin = math.ceil((m - base + shape.ox) / res - 1e-9)
        jmax = math.floor((self.w - m - shape.gw - base + shape.ox) / res + 1e-9)
        imin = math.ceil((m - base + shape.oy) / res - 1e-9)
        imax = math.floor((self.h - m - shape.gh - base + shape.oy) / res + 1e-9)
        jmax = min(jmax, self.nx - rw)
        imax = min(imax, self.ny - rh)
        jmin, imin = max(jmin, 0), max(imin, 0)
        if jmin > jmax or imin > imax:
            return None
        sub_O = self.O[imin:imax + rh, jmin:jmax + rw]
        if sub_O.any():
            C = fftconvolve(sub_O, R[::-1, ::-1], mode='valid')
            feas = C < 0.5
        else:
            feas = np.ones((imax - imin + 1, jmax - jmin + 1), dtype=bool)
        if not feas.any():
            return None
        ii, jj = np.nonzero(feas)
        ty = base + (ii + imin) * res - shape.oy
        tx = base + (jj + jmin) * res - shape.ox
        if gravity == 'top':
            score = np.round(ty + shape.gh, 6) * 1e5 + tx
        else:
            score = np.round(tx + shape.gw, 6) * 1e5 + ty
        for k in np.argsort(score, kind='stable'):
            i, j = int(ii[k] + imin), int(jj[k] + jmin)
            if not np.any(self.O[i:i + rh, j:j + rw] * R):      # 逐格核對
                return (float(score[k]), i, j, float(tx[k]), float(ty[k]))
        return None

    def place(self, part, copy_no: int, shape: _Shape, deg: int, i: int, j: int, tx: float, ty: float):
        rh, rw = shape.R.shape
        np.maximum(self.O[i:i + rh, j:j + rw], shape.R, out=self.O[i:i + rh, j:j + rw])
        self.free -= shape.cells
        M = translate(tx, ty) @ shape.Mr
        self.items.append((part, copy_no, M, deg))


# ---------------------------------------------------------------------------
# 排版主程式
# ---------------------------------------------------------------------------
class _Packer:
    def __init__(self, res: float = RES):
        self.res = res
        self.grow = params.PART_GAP / 2 + res * math.sqrt(2) / 2 + GROW_EPS
        self.pad = int(math.ceil((self.grow + 2 * res) / res)) + 1
        self._cache: dict[tuple[int, int, bool], _Shape] = {}

    def shape(self, part, deg: int, holes: bool) -> _Shape:
        key = (id(part), deg, holes)
        if key not in self._cache:
            self._cache[key] = _footprint(part.geom, deg, self.res, self.grow, holes)
        return self._cache[key]

    def _unit_sig(self, members, holes: bool) -> tuple:
        return tuple((tuple(self.shape(p, d, holes).sig for d in allowed_rots(p))) for p, _ in members)

    def _place_unit(self, st: _SheetState, members, gravity: str, holes: bool) -> bool:
        """把一個 unit（同 group 的所有份）依序放進 st；全部放得下才回傳 True（st 會被改動）。"""
        for part, cp in members:
            best = None
            for deg in allowed_rots(part):
                sh = self.shape(part, deg, holes)
                r = st.best_position(sh, gravity)
                if r is None:
                    continue
                if best is None or r[0] < best[0] - 1e-9:
                    best = (r[0], deg, sh, r[1], r[2], r[3], r[4])
            if best is None:
                return False
            _, deg, sh, i, j, tx, ty = best
            st.place(part, cp, sh, deg, i, j, tx, ty)
        return True

    def pack(self, units, material: str, gravity: str, holes: bool) -> list[_SheetState]:
        W, H = params.SHEET
        sheets: list[_SheetState] = []
        for members in units:
            sig = self._unit_sig(members, holes)
            done = False
            for k, st in enumerate(sheets):
                if sig in st.fail:
                    continue
                trial = st.copy()
                if self._place_unit(trial, members, gravity, holes):
                    sheets[k] = trial
                    done = True
                    break
                st.fail.add(sig)
            if not done:
                st = _SheetState(material, W, H, self.res, self.pad)
                if not self._place_unit(st, members, gravity, holes):
                    names = '、'.join(p.id for p, _ in members)
                    raise RuntimeError(f'{material}：{names} 放不進一張空白的 {W}×{H} 板（扣邊距 {params.SHEET_MARGIN}）')
                sheets.append(st)
        return sheets

    def place_spares(self, sheets: list[_SheetState], units, gravity: str, holes: bool) -> list[str]:
        """備品逐件塞進已經開的板（sheets 會被改動）；不開新板。先試同零件已排在的板，再依板序。
        回傳放不下的備品說明。"""
        unplaced = []
        for members in units:
            part, cp = members[0]
            home = [k for k, st in enumerate(sheets) if any(it[0] is part for it in st.items)]
            order = home + [k for k in range(len(sheets)) if k not in home]
            sig = self._unit_sig(members, holes)
            done = False
            for k in order:
                st = sheets[k]
                if sig in st.fail:
                    continue
                trial = st.copy()
                if self._place_unit(trial, members, gravity, holes):
                    sheets[k] = trial
                    done = True
                    break
                st.fail.add(sig)
            if not done:
                q = qty_of(part)
                unplaced.append(f'{part.id}（備品第 {cp - q + 1}/{spare_of(part)} 份）')
        return unplaced


def _natkey(pid: str):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', pid)]


def _spare_units(parts) -> list[list[tuple[Any, int]]]:
    """備品：每份各自一個單位（不受 group 限制），大件先、同大小依代號與份數。"""
    units = [[(p, c)] for p in parts for c in range(qty_of(p), qty_of(p) + spare_of(p))]
    units.sort(key=lambda u: (-_solid(u[0][0].geom).area, _natkey(u[0][0].id), u[0][1]))
    return units


def _units(parts) -> list[list[tuple[Any, int]]]:
    """依 group 分成「一起放」的單位；每份（qty）各一個成員，成員依面積由大到小。備品不在這裡（_spare_units）。"""
    by_group: dict[str, list] = {}
    singles = []
    for p in parts:
        q = qty_of(p)
        items = [(p, c) for c in range(q)]
        g = getattr(p, 'group', None)
        if g:
            by_group.setdefault(g, []).extend(items)
        else:
            singles.extend([[it] for it in items])
    units = list(by_group.values()) + singles
    for u in units:
        u.sort(key=lambda it: (-_solid(it[0].geom).area, _natkey(it[0].id), it[1]))
    return units


def _unit_key(order: str):
    def k(u):
        p = u[0][0]
        x0, y0, x1, y1 = p.geom.bounds
        if order == 'area':
            v = sum(_solid(q.geom).area for q, _ in u)
        elif order == 'maxside':
            v = max(x1 - x0, y1 - y0) * 1e4 + (x1 - x0) * (y1 - y0) / 1e3
        else:
            v = sum((q.geom.bounds[2] - q.geom.bounds[0]) * (q.geom.bounds[3] - q.geom.bounds[1]) for q, _ in u)
        return (-round(v, 6), _natkey(p.id), u[0][1])
    return k


def _quality(sheets: list[_SheetState]):
    """越小越好：(張數, 最後一張排到的最下緣 × 最右緣)。"""
    if not sheets:
        return (0, 0.0)
    last = sheets[-1]
    b = np.array([affinity.affine_transform(p.geom, _affine_params(M)).bounds for p, _, M, _ in last.items])
    return (len(sheets), round(float(b[:, 3].max() * b[:, 2].max()), 3))


def _verify(sheet: Sheet):
    """用 shapely 核對真實外形：板邊 ≥ SHEET_MARGIN、零件之間 ≥ PART_GAP。"""
    m, gap = params.SHEET_MARGIN, params.PART_GAP
    geoms = [pl.geom for pl in sheet.items]
    for pl, g in zip(sheet.items, geoms):
        x0, y0, x1, y1 = g.bounds
        if x0 < m - 1e-6 or y0 < m - 1e-6 or x1 > sheet.w - m + 1e-6 or y1 > sheet.h - m + 1e-6:
            raise RuntimeError(f'{sheet.title}：{pl.label} 超出板邊距（{x0:.3f},{y0:.3f})～({x1:.3f},{y1:.3f}）')
    tree = shapely.STRtree(geoms)
    for a, ga in enumerate(geoms):
        for b in tree.query(ga.buffer(gap)):
            b = int(b)
            if b <= a:
                continue
            d = ga.distance(geoms[b])
            if d < gap - 1e-6:
                raise RuntimeError(f'{sheet.title}：{sheet.items[a].label} 與 {sheet.items[b].label} '
                                   f'距離 {d:.3f} < {gap}')


def layout(parts, verbose: bool = True) -> list[Sheet]:
    """排版：回傳 list[Sheet]（先合板、再壓克力、再其他材質；同材質 no 從 1 起算）。"""
    by_mat: dict[str, list] = {}
    for p in parts:
        by_mat.setdefault(p.material, []).append(p)
    order_mat = [m for m in ('合板', '壓克力') if m in by_mat] + sorted(m for m in by_mat if m not in ('合板', '壓克力'))
    packer = _Packer()
    out: list[Sheet] = []
    for mat in order_mat:
        units = _units(by_mat[mat])
        best = None
        for order in ORDERS:
            us = sorted(units, key=_unit_key(order))
            for grav in GRAVITIES:
                sts = packer.pack(us, mat, grav, False)
                q = _quality(sts)
                if best is None or q < best[0]:
                    best = (q, sts, order, grav, False)
        if NEST_IN_HOLES is True or (NEST_IN_HOLES == 'auto' and best[0][0] > _lower_bound(by_mat[mat])):
            # 用最好的排序／靠齊再排一次「可以放進孔裡」；'auto' 時要少張數才採用
            _, _, order, grav, _ = best
            sts = packer.pack(sorted(units, key=_unit_key(order)), mat, grav, True)
            q = _quality(sts)
            if NEST_IN_HOLES is True or q[0] < best[0][0]:
                best = (q, sts, order, grav, True)
        _, sts, order, grav, holes = best
        sp_units = _spare_units(by_mat[mat])
        unplaced = []
        if sp_units:                         # 備品：只塞進已經開的板，不增加張數
            sts = [st.copy() for st in sts]
            unplaced = packer.place_spares(sts, sp_units, grav, holes)
        for no, st in enumerate(sts, start=1):
            sh = Sheet(mat, no, st.w, st.h, [Placement(p, c, M, d, spare=c >= qty_of(p)) for p, c, M, d in st.items])
            sh.notes.append(f'排序 {order}、靠齊 {grav}、{"允許" if holes else "不"}放進其他零件的孔')
            if sh.n_spare:
                sh.notes.append(f'含備品 {sh.n_spare} 件')
            if holes:
                inside = _parts_in_holes(sh)
                if inside:
                    sh.notes.append('放在其他零件孔內：' + '、'.join(inside) + '（雷切軟體請開「先切內部」）')
            _verify(sh)
            out.append(sh)
        if unplaced:
            last = out[-1] if out and out[-1].material == mat else None
            msg = f'{mat}：{len(unplaced)} 件備品放不進現有的 {len(sts)} 張板（不加張數，沒有排）：' + '、'.join(unplaced)
            if last is None:
                raise RuntimeError(msg)
            last.unplaced = list(unplaced)
            last.notes.append(msg)
    if verbose:
        print(summary(out))
    return out


def unplaced_spares(sheets) -> list[str]:
    """放不進現有板的備品（各材質合起來）；空＝備品全部排進切割檔。"""
    return [f'{s.material}：{u}' for s in sheets for u in getattr(s, 'unplaced', [])]


def _lower_bound(parts) -> int:
    W, H = params.SHEET
    tot = sum(p.geom.area * qty_of(p) for p in parts)          # 備品不開新板，不算
    return max(1, int(math.ceil(tot / (W * H))))


def _parts_in_holes(sheet: Sheet) -> list[str]:
    out = []
    geoms = [pl.geom for pl in sheet.items]
    for a, ga in enumerate(geoms):
        for b, gb in enumerate(geoms):
            if a != b and _solid(gb).contains(ga):
                out.append(f'{sheet.items[a].label} 在 {sheet.items[b].label} 孔內')
    return out


def summary(sheets: list[Sheet]) -> str:
    lines = ['排版結果：']
    for s in sheets:
        ex, ey = s.extent
        lines.append(f'  {s.title}：{len(s.items)} 件' + (f'（含備品 {s.n_spare}）' if s.n_spare else '')
                     + f'，利用率 {s.util * 100:.1f}%'
                     f'（外框 {s.outer_area / s.area * 100:.1f}%），排到 x≤{ex:.1f}、y≤{ey:.1f}')
    by = {}
    for s in sheets:
        by[s.material] = by.get(s.material, 0) + 1
    lines.append('  張數：' + '、'.join(f'{m} {n} 張' for m, n in by.items()))
    un = unplaced_spares(sheets)
    if un:
        lines.append(f'  備品放不下（沒有排，不加張數）：{len(un)} 件：' + '、'.join(un))
    return '\n'.join(lines)


if __name__ == '__main__':
    import time
    from .build_v2 import wrap_originals
    from .catalog import load_catalog
    t = time.time()
    sh = layout(wrap_originals(load_catalog()))
    print(f'{time.time() - t:.1f} s')

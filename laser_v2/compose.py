"""v2 零件合成：把各子系統（crosstrack／s1／ebox）的 edits 與 new_parts 套到原始零件上。

用法
----
    from laser_v2.catalog import load_catalog
    from laser_v2 import compose as C
    parts = C.compose(load_catalog(), {'crosstrack': r1, 's1': r2, 'ebox': r3})   # list[V2Part]
    print(C.compose_report(parts))

    results 的值是各子系統 build() 的回傳（edits／new_parts／notes／warnings，選用 renames／groups／checks），
    格式見 INTERFACE.md。compose 不修改傳進來的 cat。

套用順序（同一零件的所有子系統 edits 合併後；同一種 op 依 results 的順序、再依 edits 的順序）
------------------------------------------------------------------------------------------------
    delete_cut → translate_cut → union → subtract → 雕刻（move_engrave → delete_engrave → add_engrave → add_engrave_text）
* 材料＝((外框 − 各孔) ∪ 所有 union) − 所有 subtract。所以 union 蓋到原始孔會把孔填掉（會警告），
  subtract 碰到外框就變成缺口，整個孔被 subtract 包住就併進新的開口（原始孔消失）。
* 結果必須是單一連通零件（可以有孔）；否則 raise ComposeError，訊息裡寫出是哪個 edit 造成的
  （哪一塊沒接上本體、是哪個 union 沒接上或哪個 subtract 切斷，以及逐步重放時第一個造成分離的 edit）。
  面積 < SLIVER_AREA 的碎塊與微小孔會丟掉並警告。

「碰到」的定義（TOUCH＝0.05 mm）
-------------------------------
edit 幾何（union／subtract 的 geom，以及 translate_cut 平移後的孔）與某條原始切割子路徑的距離 < TOUCH：
* 外框：看外框「線」（edit 在零件內部挖孔、沒碰到外框線，外框不算碰到）。
* 孔：看孔的「區域」（edit 和孔重疊、在孔裡面、或離孔邊 < TOUCH 都算）。
* 開放切割線（#27 的彎曲切線、#12 的螺旋線等）：看「線」。
* 平移後的孔和其他孔或外框距離 < TOUCH 時，兩者互相算碰到（會警告）。
delete_cut 只把那個孔補成實心，不算碰到別的子路徑。

輸出規則
--------
* 沒被碰到的子路徑：原始 d 逐字保留（曲線、文字完全不變）；translate_cut 的孔輸出平移後的 d
  （catalog.transform_d，曲線種類不變）。
* 被碰到的封閉子路徑：由 shapely 結果重新產生。重生時，原始子路徑中「離所有碰到它的 edit 都 ≥ TOUCH」
  的線段原樣保留（直線、圓弧、貝茲曲線不變，只可能反向），其餘部分是折線：原始曲線以弦高誤差
  ≤ FLAT_TOL（0.005 mm）取樣（圓弧依半徑算點數），edit 自己的多邊形頂點原樣使用。
  重生後若和原始環完全相同（例如 edit 在大孔裡面、沒有實際改到邊），仍輸出原始 d。
* 被碰到的開放切割線：落在 subtract（或平移後的孔）裡的部分裁掉，其餘同上（遠離的線段保留原曲線）；
  被裁成好幾段就輸出好幾條。落在 union 加料區裡要警告（切線會切在加料上），線本身不改。
* cut_d 的順序：外框、孔（依原始順序；合併的環放在其中最前面那個孔的位置；全新的孔放最後）、開放線。
* cut_src：
  - 保留的子路徑用原始 src。translate_cut 只平移、沒被碰到的孔也維持原 src（d 是平移後的原始曲線，
    列在 V2Part.stats['moved']；和 frames.fix_26_tooth_hole() 的做法一致）。
  - 重生的環：參與的原始 src 用 + 連接再加 *，例如 'rect2[0]*'、'path131[1]+path131[2]*'。
  - 全新的孔：'new1*'、'new2*'…；裁過的開放線：'path14[5]*'（裁成多段時 'path14[5]~1*'、'~2*'）。
  - 所有重生或新增的 src 都以 * 結尾；不帶 * 的就是原始曲線。

額外檢查（只發警告，不擋）
--------------------------
* edit 附近寬度 < THIN_W（0.02 mm）的細條／細縫：多半是 edit 邊界和原始邊幾乎重合。
* edit 造成、寬度 < WEB_WARN（1.0 mm）的細料，以及 subtract／平移的孔離別的切割線 < WEB_WARN
  （但沒碰到、沒合併）：雷切後容易斷（設計規格的 min_web 是 2.0）。
* union／subtract 沒有作用（可能座標系用錯）、union 蓋到原始孔、開放切割線落在加料區。

雕刻
----
* move_engrave 用 catalog.transform_engrave 平移整個元素；delete_engrave 刪除；
  add_engrave 的 d 包成 <path style="fill:none;stroke:#ff0000;stroke-width:0.2">（和原始雕刻相同；
  edit 可帶 style 覆寫）；add_engrave_text 用 textpath.text_to_d 轉成 <path style="fill:#ff0000;stroke:none">，
  輸出不會有 <text>。新增雕刻的 data-src 是 'new-engrave-k'／'text:文字'。
* 雕刻（套完雕刻操作之後）的 bbox 和 subtract 挖掉的區域相交 → 警告（子系統應該先 move_engrave）。
  新增的文字或平移後的雕刻跑到零件外或壓到孔 → 警告。

新零件（new_parts）
------------------
geom（Polygon，可含孔）→ 外框＋孔的折線 d；engrave（d 字串）→ 線雕刻；texts → 文字填色雕刻。
num=0、page=0、layer='new'，qty、group、material（'合板'／'壓克力'）照子系統給的值。

V2Part 額外欄位
---------------
INTERFACE.md 規定的 layer／name／qty／tags／group 之外，另有 orig_id（改代號前的代號）、applied（套用紀錄）、
n_regen／n_kept（重生／原樣保留的切割子路徑數）、warnings、stats（保留曲線段數、折線段數、消失的孔…）。
原始零件的 name 用 frames 裡的說明（例如 #24「前面板」），沒有的用代號。

renames／groups
---------------
renames={'#13': '#13R'}：V2Part.id 改成新代號（orig_id 留原代號）；edits 用舊或新代號指零件都可以。
groups={'#13R': 'S1-wall'}：可指原始零件（新或舊代號）或新零件；也可以在 new_parts 的 dict 帶 group。
兩個子系統給同一個零件不同的新代號或 group → raise。

原始檔修正（#26 齒孔）
---------------------
params.FIX_26_TOOTH_HOLE 為 True（預設）時，compose 對 #26 加一個 translate_cut（path131[19] 對齊
path131[18]／path131[26]，算法同 frames.fix_26_tooth_hole()）。會先檢查：若傳進來的 #26 已經修過
（例如 build_v2 先呼叫了 frames.fix_26_tooth_hole()），就不再平移，只把 #26 標成 modified 並加 tag；
所以兩邊都做也不會重複平移。compose(..., fix_defects=False) 可關掉。

自我測試：python -m laser_v2.compose
"""
from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass, field

from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, nearest_points, unary_union
from shapely.validation import make_valid
from svgpathtools import Arc, CubicBezier, Line, QuadraticBezier, parse_path
from svgpathtools import Path as SvgPath

from . import catalog as _cat
from . import params
from . import textpath

TOUCH = 0.05          # mm：edit 與子路徑距離小於此值算「碰到」
FLAT_TOL = 0.005      # mm：重生折線的弦高誤差上限（規格要求 ≤0.02）
SLIVER_AREA = 0.01    # mm²：小於此值的碎塊、微小孔丟掉並警告
THIN_W = 0.02         # mm：edit 附近寬度小於此值的細縫、尖刺要警告
WEB_WARN = 1.0        # mm：edit 造成、比這個窄的料要警告（設計規格的 min_web 是 2.0）
MIN_PIECE = 0.01      # mm：開放線裁切後短於此值的碎段丟掉
RING_MATCH_AREA = 1e-4  # mm²：座標被 GEOS 微調時，用面積差判斷「同一個環」

CUT_OPS = ('delete_cut', 'translate_cut', 'union', 'subtract')
ENGRAVE_OPS = ('move_engrave', 'delete_engrave', 'add_engrave', 'add_engrave_text')
OPS = CUT_OPS + ENGRAVE_OPS
REQUIRED = {
    'subtract': ('part', 'geom'), 'union': ('part', 'geom'),
    'delete_cut': ('part', 'src'), 'translate_cut': ('part', 'src', 'dx', 'dy'),
    'move_engrave': ('part', 'src', 'dx', 'dy'), 'delete_engrave': ('part', 'src'),
    'add_engrave': ('part', 'd'), 'add_engrave_text': ('part', 'text', 'x', 'y', 'size'),
}
STYLE_ENGRAVE_LINE = f'fill:none;stroke:{params.STROKE_ENGRAVE_COLOR};stroke-width:0.2'
STYLE_ENGRAVE_FILL = f'fill:{params.STROKE_ENGRAVE_COLOR};stroke:none'
LAYERS = ('original', 'modified', 'new')

DEFECT_SYS = '原始檔修正'
TAG_FIX26 = '修正 #26 右側第 1 個齒孔（原始檔偏 ΔV+1.000、ΔU+0.134；frames.fix_26_tooth_hole）'


class ComposeError(ValueError):
    """edits 不合法或套用後零件不合格（不連通、被挖光、src 不存在…）。"""


# ---------------------------------------------------------------------------
# 資料結構
# ---------------------------------------------------------------------------
@dataclass
class V2Part(_cat.Part):
    """v2 零件：catalog.Part 加上圖層、名稱、數量、tag、同板群組。

    座標：原始與修改零件維持原始頁座標；新零件用自己的區域座標。"""
    layer: str = 'original'            # 'original'／'modified'／'new'
    name: str = ''                     # 中文名稱（原始零件沒有名稱時用代號）
    qty: int = 1                       # 每套數量
    tags: list[str] = field(default_factory=list)       # 套用到這個零件的 edit 說明
    group: str | None = None           # 同板群組代號
    orig_id: str | None = None         # 改代號前的原始代號（新零件為 None）
    applied: list[str] = field(default_factory=list)    # 套用紀錄（報告用）
    n_regen: int = 0                   # 重新產生的切割子路徑數（含全新的孔與裁過的開放線）
    n_kept: int = 0                    # 原樣保留的切割子路徑數（含只平移的孔）
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)          # 細節：保留曲線段數、折線段數、消失的孔…

    def svg_fragment(self, cut_style: str = params.STROKE_CUT, group_id: str | None = None) -> str:
        gid = group_id or 'part-' + re.sub(r'[^0-9A-Za-z_-]+', '_', self.id).strip('_')
        return super().svg_fragment(cut_style, gid)


@dataclass
class _Toucher:
    label: str
    geom: BaseGeometry            # 判斷距離用的幾何
    kind: str                     # 'union'／'subtract'／'moved'（平移後的孔）／'neighbor'
    edit: dict | None = None
    sub: '_Sub | None' = None


def _fmt_edit(e: dict) -> str:
    return f"{e['op']}「{e.get('tag') or '未命名'}」〈{e.get('_sys', '?')}〉"


# ---------------------------------------------------------------------------
# 曲線取樣
# ---------------------------------------------------------------------------
def _xy(z: complex) -> tuple[float, float]:
    return (float(z.real), float(z.imag))


def _flatten(seg, tol: float = FLAT_TOL) -> list[tuple[float, float]]:
    """單一線段 → 折線點（含精確的起點與終點），弦高誤差 ≤ tol。

    圓弧：參數角均分，誤差 ≤ R·Δ²/8（R＝較大半徑）；貝茲：均分參數，誤差 ≤ max|B''|/(8n²)。"""
    a, b = _xy(seg.start), _xy(seg.end)
    if isinstance(seg, Line):
        return [a, b]
    if isinstance(seg, Arc):
        R = max(abs(seg.radius.real), abs(seg.radius.imag), 1e-9)
        n = math.ceil(abs(math.radians(seg.delta)) / math.sqrt(8 * tol / R))
    elif isinstance(seg, QuadraticBezier):
        p0, p1, p2 = seg.bpoints()
        M = 2 * abs(p0 - 2 * p1 + p2)
        n = math.ceil(math.sqrt(M / (8 * tol)))
    elif isinstance(seg, CubicBezier):
        p0, p1, p2, p3 = seg.bpoints()
        M = 6 * max(abs(p0 - 2 * p1 + p2), abs(p1 - 2 * p2 + p3))
        n = math.ceil(math.sqrt(M / (8 * tol)))
    else:
        raise TypeError(type(seg))
    n = min(max(n, 1), 4000)
    return [a] + [_xy(seg.point(k / n)) for k in range(1, n)] + [b]


def _segments(d: str) -> list:
    """d（單一連續子路徑）→ svgpathtools 線段（拿掉長度 0 的直線）。"""
    return [s for s in parse_path(d) if not (isinstance(s, Line) and abs(s.end - s.start) < 1e-12)]


def _d_region(d: str):
    """d（可含多個封閉子路徑）→ shapely 區域（evenodd 合成），給雕刻檢查用。"""
    out = None
    for sp in parse_path(d).continuous_subpaths():
        pts = []
        for s in sp:
            q = _flatten(s, 0.01)
            pts.extend(q if not pts else q[1:])
        if len(pts) < 3:
            continue
        g = Polygon(pts)
        if not g.is_valid:
            g = make_valid(g)
        out = g if out is None else out.symmetric_difference(g)
    return out if out is not None else Polygon()


def _d_bbox(d: str):
    x0, x1, y0, y1 = parse_path(d).bbox()
    return (x0, y0, x1, y1)


def _elem_d(elem: str) -> str | None:
    m = re.search(r'\bd="([^"]*)"', elem)
    return m.group(1) if m and re.match(r'\s*<path\b', elem) else None


def _ring_d(coords) -> str:
    """shapely 環座標 → 'M … L … Z'（catalog 的數字格式）。"""
    pts = list(coords)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    f = _cat._f
    return 'M ' + ' L '.join(f'{f(x)},{f(y)}' for x, y in pts) + ' Z'


# ---------------------------------------------------------------------------
# 幾何小工具
# ---------------------------------------------------------------------------
def _polygons(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g] if g.area > 0 else []
    out = []
    for h in getattr(g, 'geoms', []):
        out.extend(_polygons(h))
    return out


def _lines(g) -> list[LineString]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    out = []
    for h in getattr(g, 'geoms', []):
        out.extend(_lines(h))
    return out


def _near(b1, b2, tol: float) -> bool:
    return not (b1[2] < b2[0] - tol or b2[2] < b1[0] - tol or b1[3] < b2[1] - tol or b2[3] < b1[1] - tol)


def _as_geom(e: dict, pid: str, warns: list[str]):
    g = e.get('geom')
    if not isinstance(g, BaseGeometry):
        raise ComposeError(f'{pid}：{_fmt_edit(e)} 的 geom 不是 shapely 幾何（{type(g).__name__}）')
    if g.is_empty:
        warns.append(f'{_fmt_edit(e)} 的 geom 是空的，略過')
        return None
    if not g.is_valid:
        warns.append(f'{_fmt_edit(e)} 的 geom 不合法（自交等），已用 make_valid 修正')
        g = make_valid(g)
    polys = _polygons(g)
    if not polys:
        raise ComposeError(f'{pid}：{_fmt_edit(e)} 的 geom 沒有面積（{g.geom_type}），union／subtract 需要 Polygon')
    return polys[0] if len(polys) == 1 else unary_union(polys)


def _ncomp(g) -> int:
    return sum(1 for p in _polygons(g) if p.area >= SLIVER_AREA)


# ---------------------------------------------------------------------------
# 子路徑
# ---------------------------------------------------------------------------
class _Sub:
    """套用過程中的一條切割子路徑（目前的 d、線段、取樣點、shapely 幾何）。"""

    def __init__(self, src: str, d: str, closed: bool, kind: str, order: int):
        self.src, self.closed, self.kind, self.order = src, closed, kind, order
        self.deleted = False
        self.moved: tuple[float, float] | None = None
        self.move_edits: list[dict] = []
        self.touch: list[_Toucher] = []
        self._set_d(d)

    def _set_d(self, d: str):
        self.d = d
        self.segs = _segments(d)
        self.samples = [_flatten(s) for s in self.segs]
        pts: list[tuple[float, float]] = []
        for smp in self.samples:
            pts.extend(smp if not pts else (smp[1:] if pts[-1] == smp[0] else smp))
        if self.closed and len(pts) > 1 and pts[-1] == pts[0]:
            pts = pts[:-1]
        self.pts = pts
        self.ptset = set(pts)
        if self.closed:
            g = Polygon(pts)
            if not g.is_valid:
                ps = _polygons(make_valid(g))
                g = max(ps, key=lambda q: q.area) if ps else g
            self.geom = g
        else:
            self.geom = LineString(pts)

    def target(self):
        """判斷「碰到」用的幾何：外框看線、孔看區域、開放線看線。"""
        return self.geom.exterior if self.kind == 'outer' else self.geom

    def translate(self, dx: float, dy: float):
        self._set_d(_cat.transform_d(self.d, _cat.translate_matrix(dx, dy)))


# ---------------------------------------------------------------------------
# 重生：環的拼接（保留遠離 edit 的原始線段）
# ---------------------------------------------------------------------------
def _seg_kept(sub: _Sub, j: int) -> bool:
    smp = sub.samples[j]
    ls = LineString(smp)
    b = ls.bounds
    for t in sub.touch:
        if _near(b, t.geom.bounds, TOUCH) and t.geom.distance(ls) < TOUCH:
            return False
    return True


def _splice_ring(coords, kept_idx) -> tuple[list, int, int]:
    """shapely 環座標 → svgpathtools 線段 list。整條出現在環上的保留線段換回原始曲線，其他用直線。
    回傳 (線段, 保留的原始線段數, 直線段數)。"""
    pts = list(coords)
    if pts and pts[0] == pts[-1]:
        pts = pts[:-1]
    n = len(pts)

    def interior(p):
        return any(0 < k < m for (_, _, k, m) in kept_idx.get(p, ()))

    st = next((i for i in range(n) if not interior(pts[i])), 0)
    P = pts[st:] + pts[:st] + [pts[st]]
    segs, nk, nl = [], 0, 0
    i = 0
    while i < len(P) - 1:
        done = False
        for (s, j, k, m) in kept_idx.get(P[i], ()):
            if i + m >= len(P):
                continue
            smp = s.samples[j]
            if k == 0 and P[i:i + m + 1] == smp:
                segs.append(s.segs[j])
                done = True
            elif k == m and P[i:i + m + 1] == smp[::-1]:
                segs.append(s.segs[j].reversed())
                done = True
            if done:
                i += m
                nk += 1
                break
        if not done:
            segs.append(Line(complex(*P[i]), complex(*P[i + 1])))
            nl += 1
            i += 1
    return segs, nk, nl


def _clip_open(sub: _Sub, clip) -> tuple[list[str], int, int]:
    """開放線扣掉 clip 區域。遠離所有碰到它的 edit 的線段保留原曲線，其他取樣成折線再裁切。
    回傳 (d list, 保留的原始線段數, 直線段數)。"""
    atoms: list[tuple[str, object]] = []   # ('seg', 線段) 或 ('pts', 點 list)
    run: list[tuple[float, float]] = []

    def flush():
        if len(run) >= 2:
            ls = LineString(run)
            rest = _lines(ls.difference(clip))
            if len(rest) > 1:
                rest = _lines(linemerge(rest))
            items = []
            for p in rest:
                c = list(p.coords)
                a, b = ls.project(Point(c[0])), ls.project(Point(c[-1]))
                if a > b:
                    c.reverse()
                    a = b
                items.append((a, c))
            for _, c in sorted(items, key=lambda t: t[0]):
                if LineString(c).length >= MIN_PIECE:
                    atoms.append(('pts', c))
        run.clear()

    for j, (seg, smp) in enumerate(zip(sub.segs, sub.samples)):
        if _seg_kept(sub, j):
            flush()
            atoms.append(('seg', seg))
        else:
            run.extend(smp if not run else smp[1:])
    flush()
    chains: list[list] = []
    end = None
    nk = nl = 0
    for kind, a in atoms:
        if kind == 'seg':
            s0, s1, segs = _xy(a.start), _xy(a.end), [a]
            nk += 1
        else:
            s0, s1 = a[0], a[-1]
            segs = [Line(complex(*p), complex(*q)) for p, q in zip(a[:-1], a[1:])]
            nl += len(segs)
        if chains and end == s0:
            chains[-1].extend(segs)
        else:
            chains.append(list(segs))
        end = s1
    return [_cat.path_to_d(SvgPath(*c), closed=False) for c in chains if c], nk, nl


# ---------------------------------------------------------------------------
# 不連通時找原因
# ---------------------------------------------------------------------------
def _blame(pid: str, M0, unions, subtracts, big: list[Polygon]) -> str:
    big = sorted(big, key=lambda g: -g.area)
    lines = [f'{pid}：套用 edits 後變成 {len(big)} 塊（必須是單一連通零件；主體 {big[0].area:.1f} mm²）']
    for c in big[1:]:
        b = c.bounds
        where = f'{c.area:.2f} mm²，x{b[0]:.2f}～{b[2]:.2f} y{b[1]:.2f}～{b[3]:.2f}'
        if c.intersection(M0).area < 0.5 * c.area:
            who = [_fmt_edit(e) for e, g in unions if g.intersects(c)]
            lines.append(f'  另一塊（{where}）是加料，沒接上本體：' + ('、'.join(who) or '（找不到對應的 union）'))
        else:
            who = [_fmt_edit(e) for e, g in subtracts if g.distance(c) < TOUCH]
            lines.append(f'  另一塊（{where}）被切斷，切斷它的是：' + ('、'.join(who) or '（可能是平移的孔）'))
    cur = M0
    first = None
    if _ncomp(cur) > 1:
        first = '刪孔／平移孔之後就已經不連通'
    else:
        for e, g in list(unions) + list(subtracts):
            cur = cur.union(g) if e['op'] == 'union' else cur.difference(g)
            if _ncomp(cur) > 1:
                first = f'逐步重放時第一個造成分離的是 {_fmt_edit(e)}'
                break
    if first:
        lines.append('  ' + first)
    return '\n'.join(lines)


def _opening(G, r: float):
    """形態學 opening（先內縮再外擴，尖角用 mitre 還原）：寬度 < 2r 的部分會被去掉。"""
    return G.buffer(-r, join_style=2, mitre_limit=10).buffer(r, join_style=2, mitre_limit=10)


def _narrow_checks(M0, M, edit_geom, warns: list[str]):
    """只看 edit 附近：(1) 寬度 < THIN_W 的細條／細縫（多半是 edit 邊界和原始邊幾乎重合）；
    (2) edit 造成、原本沒有的寬度 < WEB_WARN 的細料（雷切後容易斷）。"""
    def where(g):
        b = g.bounds
        return f'x{b[0]:.2f}～{b[2]:.2f} y{b[1]:.2f}～{b[3]:.2f}'
    h = THIN_W / 2
    near = edit_geom.buffer(0.2)
    spikes = M.difference(_opening(M, h)).intersection(near)
    closed_ = M.buffer(h, join_style=2, mitre_limit=10).buffer(-h, join_style=2, mitre_limit=10)
    slits = closed_.difference(M).intersection(near)
    for what, g in (('寬度 < 0.02 mm 的細條／尖刺', spikes), ('寬度 < 0.02 mm 的細縫', slits)):
        if g.area > 1e-3:
            warns.append(f'edit 附近有{what}（{g.area:.4f} mm²，{where(g)}）'
                         f'：edit 邊界可能和原始邊幾乎重合，請讓 union／subtract 多重疊一點')
    r = WEB_WARN / 2
    near = edit_geom.buffer(WEB_WARN)
    neck = M.difference(_opening(M, r)).intersection(near)
    neck0 = M0.difference(_opening(M0, r)).buffer(0.01)
    for g in _polygons(neck.difference(neck0)):
        if g.area > 0.02:
            w = 2 * g.area / max(g.length, 1e-9)
            warns.append(f'edit 造成寬度 < {WEB_WARN} mm 的細料（約 {w:.2f} mm 寬，{g.area:.2f} mm²，{where(g)}），'
                         f'雷切後容易斷；考慮併進開口或讓開')


# ---------------------------------------------------------------------------
# 切割 edits
# ---------------------------------------------------------------------------
def _apply_cut(part: _cat.Part, ops: dict, log: list[str], warns: list[str]) -> dict:
    subs = [_Sub(src, d, cl, 'outer' if i == 0 else ('hole' if cl else 'open'), i)
            for i, (src, d, cl) in enumerate(zip(part.cut_src, part.cut_d, part.cut_closed))]
    by_src = {s.src: s for s in subs}
    pid = part.id

    def get(e):
        s = by_src.get(e['src'])
        if s is None:
            near = [k for k in by_src if k.split('[')[0] == str(e['src']).split('[')[0]][:8]
            raise ComposeError(f'{pid}：{_fmt_edit(e)} 的 src {e["src"]!r} 不存在'
                               + (f'（同元素的有 {near}）' if near else f'（第一個是 {part.cut_src[0]}）'))
        if s.kind == 'outer':
            raise ComposeError(f'{pid}：{_fmt_edit(e)} 指到外框 {s.src}，外框不能刪除或平移（要改外形請用 union／subtract）')
        return s

    # 1) delete_cut
    for e in ops['delete_cut']:
        s = get(e)
        if s.deleted:
            raise ComposeError(f'{pid}：{s.src} 被刪除兩次（{_fmt_edit(e)}）')
        s.deleted = True
        log.append(f'{_fmt_edit(e)}：刪除 {s.src}（補成實心）')
    # 2) translate_cut
    for e in ops['translate_cut']:
        s = get(e)
        if s.deleted:
            raise ComposeError(f'{pid}：{s.src} 已被 delete_cut 刪除，不能再平移（{_fmt_edit(e)}）')
        dx, dy = float(e['dx']), float(e['dy'])
        if s.moved is not None:
            warns.append(f'{s.src} 被平移不只一次，平移量累加（{_fmt_edit(e)}）')
        s.translate(dx, dy)
        px, py = s.moved or (0.0, 0.0)
        s.moved = (px + dx, py + dy)
        s.move_edits.append(e)
        log.append(f'{_fmt_edit(e)}：{s.src} 平移 ({dx:+.3f}, {dy:+.3f})')
    live = [s for s in subs if not s.deleted]
    outer = subs[0]
    for s in live:
        if s.moved and s.closed and not outer.geom.contains(s.geom):
            raise ComposeError(f'{pid}：{s.src} 平移後超出零件外框（{_fmt_edit(s.move_edits[-1])}）')

    # 3) union／subtract 幾何
    unions = [(e, g) for e in ops['union'] if (g := _as_geom(e, pid, warns)) is not None]
    subtracts = [(e, g) for e in ops['subtract'] if (g := _as_geom(e, pid, warns)) is not None]
    touchers = ([_Toucher(_fmt_edit(e), g, 'union', e) for e, g in unions]
                + [_Toucher(_fmt_edit(e), g, 'subtract', e) for e, g in subtracts])
    moved_closed = [s for s in live if s.moved and s.closed]
    for s in moved_closed:
        touchers.append(_Toucher(f'平移後的 {s.src}', s.geom, 'moved', s.move_edits[-1], s))

    # 4) 碰到
    for s in live:
        tgt = s.target()
        tb = tgt.bounds
        for t in touchers:
            if t.sub is s:
                continue
            if _near(tb, t.geom.bounds, TOUCH) and t.geom.distance(tgt) < TOUCH:
                s.touch.append(t)
    for s in moved_closed:
        for o in live:
            if o is s or o.kind == 'open':
                continue
            tgt = o.target()
            if _near(s.geom.bounds, tgt.bounds, TOUCH) and s.geom.distance(tgt) < TOUCH:
                s.touch.append(_Toucher(o.src, tgt, 'neighbor', None, o))
                warns.append(f'平移後的 {s.src} 離 {o.src} 不到 {TOUCH} mm，兩者合併重生'
                             f'（{_fmt_edit(s.move_edits[-1])}）')

    # 5) 材料
    holes = [s.geom for s in live if s.kind == 'hole']
    M0 = outer.geom.difference(unary_union(holes)) if holes else outer.geom
    M1 = M0
    for e, g in unions:
        before = M1
        M1 = M1.union(g)
        if abs(M1.area - before.area) < 1e-6:
            warns.append(f'{_fmt_edit(e)} 沒有作用（加料區整個在零件材料內）')
        else:
            log.append(f'{_fmt_edit(e)}：加料 {M1.area - before.area:.2f} mm²')
        for s in live:
            if s.kind == 'hole' and _near(g.bounds, s.geom.bounds, 0) and g.intersection(s.geom).area > 1e-6:
                warns.append(f'{_fmt_edit(e)} 蓋到原始孔 {s.src}（{g.intersection(s.geom).area:.2f} mm² 被填實）')
    M = M1
    for e, g in subtracts:
        before = M
        M = M.difference(g)
        if abs(before.area - M.area) < 1e-6:
            warns.append(f'{_fmt_edit(e)} 沒有作用（挖掉區域不在零件材料上；座標系用對了嗎？）')
        else:
            log.append(f'{_fmt_edit(e)}：挖掉 {before.area - M.area:.2f} mm²')

    # 6) 單一連通
    comps = _polygons(M)
    big = [g for g in comps if g.area >= SLIVER_AREA]
    if not big:
        raise ComposeError(f'{pid}：套用 edits 後零件不見了（被挖光）：' + '、'.join(_fmt_edit(e) for e, _ in subtracts))
    if len(big) > 1:
        raise ComposeError(_blame(pid, M0, unions, subtracts, big))
    if len(comps) > 1:
        tiny = [g for g in comps if g.area < SLIVER_AREA]
        warns.append(f'丟掉 {len(tiny)} 塊 < {SLIVER_AREA} mm² 的碎片（總面積 {sum(g.area for g in tiny):.4f} mm²，'
                     f'位置 {[tuple(round(v, 2) for v in g.bounds) for g in tiny][:3]}）')
    M = big[0]
    keep_int, drop_int = [], []
    for r in M.interiors:
        (keep_int if Polygon(r).area >= SLIVER_AREA else drop_int).append(r)
    if drop_int:
        warns.append(f'補掉 {len(drop_int)} 個 < {SLIVER_AREA} mm² 的微小孔（edit 邊界幾乎重合造成）')
        M = Polygon(M.exterior, keep_int)

    # 7) edit 附近的細縫、尖刺、細料；新切割離原有切割太近（沒碰到，但料寬 < WEB_WARN）
    if touchers:
        _narrow_checks(M0, M, unary_union([t.geom for t in touchers]), warns)
    cutters = [(_fmt_edit(e), g) for e, g in subtracts] + [(f'平移後的 {s.src}', s.geom) for s in moved_closed]
    for k, (lab, g) in enumerate(cutters):
        others = [(s.src, s.target()) for s in live if s.geom is not g and not any(t.geom is g for t in s.touch)]
        others += [(lab2, g2) for lab2, g2 in cutters[k + 1:]]
        for name, tgt in others:
            if not _near(g.bounds, tgt.bounds, WEB_WARN):
                continue
            dd = g.distance(tgt)
            if TOUCH <= dd < WEB_WARN:
                p1, p2 = nearest_points(g, tgt)
                mid = Point((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)
                if M.contains(mid):
                    warns.append(f'{lab} 離 {name} 只剩 {dd:.3f} mm 的料（< {WEB_WARN} mm，'
                                 f'約在 x{mid.x:.2f} y{mid.y:.2f}），雷切後容易斷；考慮併進開口或讓開')

    # 8) 環 → 子路徑
    closed_live = [s for s in live if s.closed]
    owner: dict[tuple, list[_Sub]] = {}
    for s in closed_live:
        for p in s.pts:
            owner.setdefault(p, []).append(s)
    rings = [('ext', M.exterior)] + [('int', r) for r in M.interiors]
    verbatim: dict[_Sub, int] = {}
    regen: list[tuple[int, str, list]] = []
    for ri, (rk, r) in enumerate(rings):
        coords = list(r.coords)[:-1]
        cset = set(coords)
        hit = None
        for s in owner.get(coords[0], ()):
            if s not in verbatim and len(cset) == len(s.ptset) and cset == s.ptset \
                    and (rk == 'ext') == (s.kind == 'outer'):
                hit = s
                break
        if hit is not None:
            verbatim[hit] = ri
        else:
            regen.append((ri, rk, coords))
    # 沒被碰到的必須原樣出現（GEOS 若微調座標，改用面積差比對）
    for s in closed_live:
        if s.touch or s in verbatim:
            continue
        found = None
        for k, (ri, rk, coords) in enumerate(regen):
            if (rk == 'ext') == (s.kind == 'outer'):
                q = Polygon(coords)
                if q.symmetric_difference(s.geom).area < RING_MATCH_AREA:
                    found = k
                    break
        if found is None:
            raise ComposeError(f'{pid}：內部錯誤，沒被任何 edit 碰到的 {s.src} 在結果裡找不到')
        verbatim[s] = regen.pop(found)[0]

    # 重生環：保留線段索引
    kept_idx: dict[tuple, list] = {}
    for s in closed_live:
        if not s.touch or s in verbatim:
            continue
        for j, smp in enumerate(s.samples):
            if _seg_kept(s, j):
                m = len(smp) - 1
                for k, p in enumerate(smp):
                    kept_idx.setdefault(p, []).append((s, j, k, m))
    out: list[tuple[tuple, str, str, bool]] = []    # (排序鍵, d, src, closed)
    stats = dict(kept_segments=0, poly_lines=0, vanished=[], filled=[], regen_src=[], new_src=[], touched=[])
    in_regen: set[_Sub] = set()
    regen_info = []
    for ri, rk, coords in regen:
        segs, nk, nl = _splice_ring(coords, kept_idx)
        stats['kept_segments'] += nk
        stats['poly_lines'] += nl
        contrib = {s for p in coords for s in owner.get(p, ()) if s not in verbatim}
        regen_info.append([ri, rk, coords, segs, contrib])
        in_regen |= contrib
    # 沒有任何點留在結果裡的被碰到子路徑：被挖掉（併進新開口）或被填實
    for s in closed_live:
        if s in verbatim or s in in_regen:
            continue
        rp = s.geom.representative_point()
        if s.kind == 'outer':
            stats['vanished'].append(s.src)
            log.append(f'外框 {s.src} 整條被取代')
            continue
        host = None
        for info in regen_info:
            if info[1] == 'int' and Polygon(info[2]).contains(rp):
                host = info
                break
        if host is not None:
            host[4].add(s)
            stats['vanished'].append(s.src)
            log.append(f'孔 {s.src} 整個被挖掉，併進新開口')
        elif M.contains(rp):
            stats['filled'].append(s.src)
            log.append(f'孔 {s.src} 被加料填實')
        else:
            stats['vanished'].append(s.src)
            log.append(f'孔 {s.src} 消失（併進外框缺口）')
    n_new = 0
    for ri, rk, coords, segs, contrib in regen_info:
        d = _cat.path_to_d(SvgPath(*segs), closed=True)
        if rk == 'ext':
            key = (0, 0)
            src = '+'.join(s.src for s in sorted(contrib | {outer}, key=lambda q: q.order)) + '*'
        elif contrib:
            cs = sorted(contrib, key=lambda q: q.order)
            key = (1, cs[0].order)
            src = '+'.join(s.src for s in cs) + '*'
        else:
            n_new += 1
            key = (1, 10 ** 6 + n_new)
            src = f'new{n_new}*'
        (stats['new_src'] if not contrib and rk == 'int' else stats['regen_src']).append(src)
        out.append((key, d, src, True))
    for s, ri in verbatim.items():
        out.append(((0, 0) if s.kind == 'outer' else (1, s.order), s.d, s.src, True))
        if s.touch:
            log.append(f'{s.src} 被碰到但邊界沒有改變，保留原始 d')

    # 開放線
    n_open_kept = n_open_regen = 0
    for s in live:
        if s.closed:
            continue
        for t in s.touch:
            if t.kind == 'union':
                L = s.geom.intersection(t.geom).length
                if L > 1e-6:
                    warns.append(f'開放切割線 {s.src} 有 {L:.2f} mm 落在加料區（{t.label}），照切會切在加料上')
        cl = [t for t in s.touch if t.kind in ('subtract', 'moved')]
        clip = unary_union([t.geom for t in cl]) if cl else None
        if clip is None or s.geom.intersection(clip).length < 1e-9:
            out.append(((2, s.order, 0), s.d, s.src, False))
            n_open_kept += 1
            continue
        ds, nk, nl = _clip_open(s, clip)
        stats['kept_segments'] += nk
        stats['poly_lines'] += nl
        if not ds:
            stats['vanished'].append(s.src)
            log.append(f'開放切割線 {s.src} 整條被挖掉')
        for k, d in enumerate(ds):
            src = s.src + (f'~{k + 1}' if len(ds) > 1 else '') + '*'
            out.append(((2, s.order, k), d, src, False))
            stats['regen_src'].append(src)
            n_open_regen += 1
    stats['touched'] = [s.src for s in live if s.touch]
    stats['moved'] = [s.src for s in live if s.moved and s.src in {t[2] for t in out}]
    out.sort(key=lambda t: t[0])
    if out[0][0] != (0, 0):
        raise ComposeError(f'{pid}：內部錯誤，輸出的第一條不是外框')
    n_closed_kept = sum(1 for s in verbatim)
    return dict(cut_d=[t[1] for t in out], cut_src=[t[2] for t in out], cut_closed=[t[3] for t in out],
                geom=M, n_kept=n_closed_kept + n_open_kept,
                n_regen=len(regen_info) + n_open_regen, stats=stats,
                removed=unary_union([g for _, g in subtracts]) if subtracts else None)


# ---------------------------------------------------------------------------
# 雕刻 edits
# ---------------------------------------------------------------------------
def _engrave_elem(d: str, src: str, style: str, text: str | None = None) -> str:
    extra = f' data-text="{html.escape(text, quote=True)}"' if text is not None else ''
    return f'<path d="{d}" style="{style}" data-src="{html.escape(src, quote=True)}"{extra}/>'


def _text_elem(t: dict, src: str) -> str:
    d = textpath.text_to_d(str(t['text']), float(t['x']), float(t['y']), float(t['size']),
                           float(t.get('angle', 0.0) or 0.0), t.get('anchor', 'start') or 'start')
    return _engrave_elem(d, src, STYLE_ENGRAVE_FILL, str(t['text']))


def _uniq(src: str, used: set[str]) -> str:
    if src not in used:
        return src
    k = 2
    while f'{src}#{k}' in used:
        k += 1
    return f'{src}#{k}'


def _apply_engrave(pid, engrave, esrc, ops, removed, geom, log, warns):
    engrave, esrc = list(engrave), list(esrc)
    touched: set[str] = set()      # 平移或新增的雕刻（要檢查有沒有跑到零件外或壓到孔）
    added: set[str] = set()
    for e in ops['move_engrave']:
        if e['src'] not in esrc:
            raise ComposeError(f'{pid}：{_fmt_edit(e)} 的雕刻 src {e["src"]!r} 不存在（有 {esrc}）')
        i = esrc.index(e['src'])
        dx, dy = float(e['dx']), float(e['dy'])
        engrave[i] = _cat.transform_engrave(engrave[i], _cat.translate_matrix(dx, dy))
        touched.add(e['src'])
        log.append(f'{_fmt_edit(e)}：雕刻 {e["src"]} 平移 ({dx:+.3f}, {dy:+.3f})')
    for e in ops['delete_engrave']:
        if e['src'] not in esrc:
            raise ComposeError(f'{pid}：{_fmt_edit(e)} 的雕刻 src {e["src"]!r} 不存在（有 {esrc}）')
        i = esrc.index(e['src'])
        if e['src'] in touched:
            warns.append(f'雕刻 {e["src"]} 先被平移又被刪除（{_fmt_edit(e)}）')
        del engrave[i], esrc[i]
        log.append(f'{_fmt_edit(e)}：刪除雕刻 {e["src"]}')
    used = set(esrc)
    for k, e in enumerate(ops['add_engrave']):
        src = _uniq(e.get('src') or f'new-engrave-{k + 1}', used)
        used.add(src)
        engrave.append(_engrave_elem(str(e['d']), src, e.get('style') or STYLE_ENGRAVE_LINE))
        esrc.append(src)
        added.add(src)
        log.append(f'{_fmt_edit(e)}：新增雕刻 {src}')
    for e in ops['add_engrave_text']:
        src = _uniq(f'text:{e["text"]}', used)
        used.add(src)
        engrave.append(_text_elem(e, src))
        esrc.append(src)
        added.add(src)
        log.append(f'{_fmt_edit(e)}：新增雕刻文字「{e["text"]}」（{float(e["size"]):g} mm，'
                   f'{float(e.get("angle", 0) or 0):g}°，{e.get("anchor", "start")}）')
    # 檢查
    outer_poly = Polygon(geom.exterior) if isinstance(geom, Polygon) else geom
    for el, s in zip(engrave, esrc):
        d = _elem_d(el)
        if d is None:
            continue
        bb = _d_bbox(d)
        bx = box(*bb)
        if removed is not None and _near(bb, removed.bounds, 0):
            a = bx.intersection(removed).area
            if a > 1e-6:
                warns.append(f'雕刻 {s} 的範圍（x{bb[0]:.2f}～{bb[2]:.2f} y{bb[1]:.2f}～{bb[3]:.2f}）'
                             f'被 subtract 挖到 {a:.2f} mm²（子系統應先 move_engrave）')
        if s in added:
            reg = _d_region(d)
            off = reg.difference(geom).area
            if off > 1e-3:
                warns.append(f'新增雕刻 {s} 有 {off:.2f} mm² 跑到零件外或壓到孔')
        elif s in touched:
            if not bx.within(outer_poly):
                warns.append(f'平移後的雕刻 {s} 超出零件外框')
    return engrave, esrc


# ---------------------------------------------------------------------------
# 原始檔修正
# ---------------------------------------------------------------------------
def defect_edits(cat: dict) -> tuple[list[dict], str]:
    """依 params 與 #26 目前狀態，回傳要加的 translate_cut（list）與說明。

    #26 path131[19] 若已經和 path131[18]（x）、path131[26]（y）對齊，代表呼叫端已修過，回傳空 list。"""
    p = cat.get('#26')
    if p is None or 'path131[19]' not in p.cut_src:
        return [], '#26 不在 cat 裡或沒有 path131[19]，不修'

    def bb(k):
        return parse_path(p.cut_d[p.cut_src.index(k)]).bbox()
    cur, refx, refy = bb('path131[19]'), bb('path131[18]'), bb('path131[26]')
    dx, dy = refx[0] - cur[0], refy[2] - cur[2]
    if abs(dx) < 0.005 and abs(dy) < 0.005:
        return [], 'already'
    if not (abs(dx + 1.0) < 0.02 and abs(dy + 0.134) < 0.02):
        raise ComposeError(f'#26 齒孔偏移量和預期不同：dx={dx:.4f} dy={dy:.4f}（預期約 -1.000、-0.134）')
    e = dict(op='translate_cut', part='#26', src='path131[19]', dx=dx, dy=dy, tag=TAG_FIX26, _sys=DEFECT_SYS)
    return [e], f'平移 ({dx:+.4f}, {dy:+.4f})'


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
_NAMES: dict[str, str] | None = None


def _names() -> dict[str, str]:
    """原始零件的中文名稱（frames 裡有 desc 的零件）。"""
    global _NAMES
    if _NAMES is None:
        try:
            from . import frames as _fr
            _NAMES = {k: f.desc for k, f in _fr.frames().items()}
        except Exception:   # noqa: BLE001 —— 名稱只是報告用，frames 有問題不影響合成
            _NAMES = {}
    return _NAMES


def _norm_material(m, pid: str) -> str:
    s = str(m or '合板')
    if '壓克力' in s or 'acrylic' in s.lower():
        return _cat.ACRYLIC
    if '合板' in s or 'plywood' in s.lower():
        return _cat.PLY
    raise ComposeError(f'{pid}：不認得的材質 {m!r}（只能是「合板」或「壓克力」）')


def _validate_edit(e, sys_name: str, k: int) -> dict:
    if not isinstance(e, dict):
        raise ComposeError(f'〈{sys_name}〉edits[{k}] 不是 dict')
    op = e.get('op')
    if op not in OPS:
        raise ComposeError(f'〈{sys_name}〉edits[{k}] 的 op {op!r} 不認得（可用 {OPS}）')
    miss = [f for f in REQUIRED[op] if f not in e]
    if miss:
        raise ComposeError(f'〈{sys_name}〉edits[{k}]（{op}「{e.get("tag") or ""}」）缺欄位 {miss}')
    if op == 'add_engrave_text' and e.get('anchor', 'start') not in textpath.ANCHORS:
        raise ComposeError(f'〈{sys_name}〉edits[{k}] anchor {e.get("anchor")!r} 不合法')
    e2 = dict(e)
    e2['_sys'] = sys_name
    e2['_k'] = k
    return e2


def _new_part(spec: dict, sys_name: str) -> V2Part:
    if not isinstance(spec, dict) or 'id' not in spec or 'geom' not in spec:
        raise ComposeError(f'〈{sys_name}〉new_parts 的項目要有 id 與 geom：{spec!r:.120}')
    pid = str(spec['id'])
    g = spec['geom']
    if not isinstance(g, BaseGeometry):
        raise ComposeError(f'〈{sys_name}〉新零件 {pid} 的 geom 不是 shapely 幾何')
    warns: list[str] = []
    if not g.is_valid:
        warns.append('geom 不合法，已用 make_valid 修正')
        g = make_valid(g)
    polys = _polygons(g)
    big = [q for q in polys if q.area >= SLIVER_AREA]
    if len(big) != 1:
        raise ComposeError(f'〈{sys_name}〉新零件 {pid} 的 geom 有 {len(big)} 塊（必須是單一連通零件）')
    g = big[0]
    g = Polygon(g.exterior, [r for r in g.interiors if Polygon(r).area >= SLIVER_AREA])
    material = _norm_material(spec.get('material'), pid)
    try:
        qty = int(spec.get('qty', 1))
    except (TypeError, ValueError):
        raise ComposeError(f'〈{sys_name}〉新零件 {pid} 的 qty {spec.get("qty")!r} 不是整數') from None
    if qty < 1:
        raise ComposeError(f'〈{sys_name}〉新零件 {pid} 的 qty {qty} < 1')
    cut_d = [_ring_d(g.exterior.coords)] + [_ring_d(r.coords) for r in g.interiors]
    cut_src = [f'{pid}:outer'] + [f'{pid}:hole{k + 1}' for k in range(len(g.interiors))]
    engrave, esrc = [], []
    used: set[str] = set()
    for k, d in enumerate(spec.get('engrave') or []):
        src = _uniq(f'{pid}:engrave{k + 1}', used)
        used.add(src)
        if str(d).lstrip().startswith('<'):
            if '<text' in str(d):
                raise ComposeError(f'〈{sys_name}〉新零件 {pid} 的 engrave 不可以是 <text>，請用 texts')
            engrave.append(str(d).strip())
        else:
            engrave.append(_engrave_elem(str(d), src, STYLE_ENGRAVE_LINE))
        esrc.append(src)
    for t in spec.get('texts') or []:
        for f_ in ('text', 'x', 'y', 'size'):
            if f_ not in t:
                raise ComposeError(f'〈{sys_name}〉新零件 {pid} 的 texts 缺 {f_}：{t!r}')
        src = _uniq(f'text:{t["text"]}', used)
        used.add(src)
        el = _text_elem(t, src)
        engrave.append(el)
        esrc.append(src)
        off = _d_region(_elem_d(el)).difference(g).area
        if off > 1e-3:
            warns.append(f'文字「{t["text"]}」有 {off:.2f} mm² 跑到零件外或壓到孔')
    tag = spec.get('tag')
    return V2Part(id=pid, num=0, page=0, material=material, cut_d=cut_d, engrave=engrave, geom=g,
                  bbox=tuple(float(v) for v in g.bounds), cut_src=cut_src, cut_closed=[True] * len(cut_d),
                  engrave_src=esrc, layer='new', name=str(spec.get('name') or pid), qty=qty,
                  tags=[tag] if tag else [], group=spec.get('group'), orig_id=None,
                  applied=[f'新增零件〈{sys_name}〉'], n_regen=len(cut_d), n_kept=0, warnings=warns,
                  stats=dict(sys=sys_name, n_texts=len(spec.get('texts') or [])))


def _as_original(p: _cat.Part, name: str) -> V2Part:
    return V2Part(id=p.id, num=p.num, page=p.page, material=p.material, cut_d=list(p.cut_d),
                  engrave=list(p.engrave), geom=p.geom, bbox=p.bbox, cut_src=list(p.cut_src),
                  cut_closed=list(p.cut_closed), engrave_src=list(p.engrave_src), layer='original',
                  name=name, qty=1, tags=[], group=None, orig_id=p.id, applied=[], n_regen=0,
                  n_kept=len(p.cut_d), warnings=[], stats={})


def _apply_part(p: _cat.Part, edits: list[dict], name: str) -> V2Part:
    ops = {op: [e for e in edits if e['op'] == op] for op in OPS}
    log: list[str] = []
    warns: list[str] = []
    if any(ops[op] for op in CUT_OPS):
        r = _apply_cut(p, ops, log, warns)
        cut_d, cut_src, cut_closed, geom = r['cut_d'], r['cut_src'], r['cut_closed'], r['geom']
        bb = _d_bbox(cut_d[0])
        n_kept, n_regen, stats, removed = r['n_kept'], r['n_regen'], r['stats'], r['removed']
    else:
        cut_d, cut_src, cut_closed, geom = list(p.cut_d), list(p.cut_src), list(p.cut_closed), p.geom
        bb, n_kept, n_regen, stats, removed = p.bbox, len(p.cut_d), 0, {}, None
    if any(ops[op] for op in ENGRAVE_OPS):
        engrave, esrc = _apply_engrave(p.id, p.engrave, p.engrave_src, ops, removed, geom, log, warns)
    else:
        engrave, esrc = list(p.engrave), list(p.engrave_src)
        if removed is not None:
            _apply_engrave(p.id, engrave, esrc, ops, removed, geom, log, warns)   # 只做檢查
    tags = []
    for e in edits:
        t = e.get('tag') or f"{e['op']}〈{e['_sys']}〉"
        if t not in tags:
            tags.append(t)
    return V2Part(id=p.id, num=p.num, page=p.page, material=p.material, cut_d=cut_d, engrave=engrave,
                  geom=geom, bbox=tuple(float(v) for v in bb), cut_src=cut_src, cut_closed=cut_closed,
                  engrave_src=esrc, layer='modified', name=name, qty=1, tags=tags, group=None,
                  orig_id=p.id, applied=log, n_regen=n_regen, n_kept=n_kept, warnings=warns, stats=stats)


def compose(cat: dict[str, _cat.Part], results: dict[str, dict] | None,
            *, fix_defects: bool | None = None) -> list[V2Part]:
    """合併所有子系統的 edits／new_parts，回傳 list[V2Part]（原始零件依編號，接著新零件）。

    fix_defects：None＝照 params.FIX_26_TOOTH_HOLE；True／False 強制開關 #26 齒孔修正。"""
    results = dict(results or {})
    fix = params.FIX_26_TOOTH_HOLE if fix_defects is None else bool(fix_defects)
    edits_by_part: dict[str, list[dict]] = {}
    renames: dict[str, str] = {}
    groups: dict[str, str] = {}
    group_by: dict[str, str] = {}
    new_specs: list[tuple[str, dict]] = []
    for sys_name, res in results.items():
        if res is None:
            continue
        if not isinstance(res, dict):
            raise ComposeError(f'results[{sys_name!r}] 不是 dict')
        for k, e in enumerate(res.get('edits') or []):
            e2 = _validate_edit(e, sys_name, k)
            edits_by_part.setdefault(str(e2['part']), []).append(e2)
        for old, new in (res.get('renames') or {}).items():
            if old in renames and renames[old] != new:
                raise ComposeError(f'{old} 被兩個子系統改成不同代號：{renames[old]}、{new}（〈{sys_name}〉）')
            renames[old] = new
        for key, gname in (res.get('groups') or {}).items():
            if key in groups and groups[key] != gname:
                raise ComposeError(f'{key} 被指定到兩個 group：{groups[key]}（〈{group_by[key]}〉）、{gname}（〈{sys_name}〉）')
            groups[key] = gname
            group_by[key] = sys_name
        for spec in res.get('new_parts') or []:
            new_specs.append((sys_name, spec))
    for old, new in renames.items():
        if old not in cat:
            raise ComposeError(f'renames 的 {old} 不是原始零件')
        if new in cat and new != old:
            raise ComposeError(f'renames：新代號 {new} 和原始零件重複')
    rev = {new: old for old, new in renames.items()}
    merged: dict[str, list[dict]] = {}
    for key, lst in edits_by_part.items():
        pid = rev.get(key, key)
        if pid not in cat:
            raise ComposeError(f'edits 指到不存在的零件 {key}（{_fmt_edit(lst[0])}）')
        merged.setdefault(pid, []).extend(lst)

    defect_note = None
    if fix:
        des = merged.get('#26', [])
        hit = [e for e in des if e['op'] in ('delete_cut', 'translate_cut') and e['src'] == 'path131[19]']
        if hit:
            defect_note = f'#26 齒孔修正略過：path131[19] 已被 {_fmt_edit(hit[0])} 處理'
        else:
            fe, why = defect_edits(cat)
            if fe:
                merged.setdefault('#26', []).insert(0, fe[0])
            elif why == 'already':
                defect_note = 'already'

    names = _names()
    out: list[V2Part] = []
    for pid, p in cat.items():
        nm = names.get(pid, '')
        lst = merged.get(pid, [])
        v = _apply_part(p, lst, nm) if lst else _as_original(p, nm)
        if pid == '#26' and defect_note == 'already':
            v.layer = 'modified'
            v.tags.insert(0, TAG_FIX26)
            v.applied.insert(0, f'{TAG_FIX26}：傳進來的 #26 已修過（齒孔已對齊），不再平移')
        elif pid == '#26' and defect_note:
            v.warnings.append(defect_note)
        if pid in renames:
            v.id = renames[pid]
            v.layer = 'modified'
            v.applied.append(f'改代號 {pid} → {v.id}')
        if not v.name:
            v.name = v.id
        out.append(v)
    ids = {v.id for v in out}
    for sys_name, spec in new_specs:
        v = _new_part(spec, sys_name)
        if v.id in ids:
            raise ComposeError(f'〈{sys_name}〉新零件代號 {v.id} 重複')
        ids.add(v.id)
        out.append(v)
    by_id = {v.id: v for v in out}
    by_orig = {v.orig_id: v for v in out if v.orig_id}
    for key, gname in groups.items():
        v = by_id.get(key) or by_orig.get(key)
        if v is None:
            raise ComposeError(f'groups 指到不存在的零件 {key}（〈{group_by[key]}〉）')
        if v.group is not None and v.group != gname:
            raise ComposeError(f'{v.id} 的 group 衝突：{v.group}、{gname}')
        v.group = gname
    return out


# ---------------------------------------------------------------------------
# 報告
# ---------------------------------------------------------------------------
def compose_warnings(parts: list[V2Part]) -> list[str]:
    return [f'{v.id}：{w}' for v in parts for w in v.warnings]


def compose_report(parts: list[V2Part]) -> str:
    """每個零件：layer、套了哪些 edit、重生幾條子路徑、保留幾條（Markdown）。"""
    n = {k: sum(1 for v in parts if v.layer == k) for k in LAYERS}
    L = ['# compose 報告', '',
         f'零件 {len(parts)} 個：原樣 {n["original"]}、修改 {n["modified"]}、新增 {n["new"]}。'
         f'警告 {sum(len(v.warnings) for v in parts)} 則。', '',
         '| 零件 | 名稱 | layer | 數量 | group | 切割子路徑（保留／重生） | 雕刻 | 套用的 edit |',
         '|---|---|---|---|---|---|---|---|']
    for v in parts:
        idn = v.id if (v.orig_id in (None, v.id)) else f'{v.id}（原 {v.orig_id}）'
        tags = '；'.join(v.tags) if v.tags else '—'
        L.append(f'| {idn} | {v.name} | {v.layer} | {v.qty} | {v.group or ""} | '
                 f'{len(v.cut_d)}（{v.n_kept}／{v.n_regen}） | {len(v.engrave)} | {tags} |')
    for v in parts:
        if v.layer == 'original':
            continue
        L += ['', f'## {v.id} {v.name}（{v.layer}）']
        st = v.stats or {}
        if v.layer == 'modified':
            L.append(f'- 切割子路徑 {len(v.cut_d)} 條：原樣保留 {v.n_kept}、重生 {v.n_regen}'
                     + (f'（重生的保留原曲線段 {st.get("kept_segments", 0)} 段、折線 {st.get("poly_lines", 0)} 段）'
                        if v.n_regen else ''))
            if st.get('regen_src'):
                L.append(f'- 重生：{", ".join(st["regen_src"])}')
            if st.get('new_src'):
                L.append(f'- 新開的孔：{", ".join(st["new_src"])}')
            if st.get('moved'):
                L.append(f'- 只平移（原曲線、原 src）：{", ".join(st["moved"])}')
            if st.get('vanished'):
                L.append(f'- 消失（被挖掉）：{", ".join(st["vanished"])}')
            if st.get('filled'):
                L.append(f'- 被填實：{", ".join(st["filled"])}')
        else:
            L.append(f'- 材質 {v.material}、每套 {v.qty} 個、外形 {v.size[0]:.2f}×{v.size[1]:.2f} mm、'
                     f'孔 {len(v.cut_d) - 1}、雕刻 {len(v.engrave)}')
        for a in v.applied:
            L.append(f'- {a}')
        for w in v.warnings:
            L.append(f'- ⚠ {w}')
    return '\n'.join(L)


# ---------------------------------------------------------------------------
# 自我測試
# ---------------------------------------------------------------------------
def _cut_region(v, tol: float = 0.001) -> BaseGeometry:
    """由 cut_d（封閉者）重建零件區域（外框 − 孔），檢查輸出的 d 與 geom 一致。"""
    rings = []
    for d, cl in zip(v.cut_d, v.cut_closed):
        if not cl:
            continue
        pts = []
        for s in _segments(d):
            q = _flatten(s, tol)
            pts.extend(q if not pts else q[1:])
        rings.append(Polygon(pts))
    out = rings[0].difference(unary_union(rings[1:])) if len(rings) > 1 else rings[0]
    ps = _polygons(out)
    return ps[0] if len(ps) == 1 else unary_union(ps)


def _fine_ring(d: str, tol: float = 0.0002) -> LineString:
    """原始 d 以極小弦高取樣的線（當作真實曲線，檢查重生折線的弦高誤差用）。"""
    pts = []
    for s in _segments(d):
        q = _flatten(s, tol)
        pts.extend(q if not pts else q[1:])
    return LineString(pts)


def _outer_ring_err(v, ref_lines) -> float:
    """輸出外框每條直線段的端點與中點，到參考線（原始外框＋edit 邊界）的最大距離。"""
    worst = 0.0
    ref = unary_union(ref_lines)
    for s in _segments(v.cut_d[0]):
        for t in (0.0, 0.5, 1.0):
            worst = max(worst, ref.distance(Point(_xy(s.point(t)))))
    return worst


def _selftest() -> list[str]:
    import time
    from . import frames as _fr
    errs: list[str] = []

    def chk(cond, msg):
        print(('OK  ' if cond else '!!  ') + msg)
        if not cond:
            errs.append(msg)

    t0 = time.time()
    orig = _cat.load_catalog()

    # ① results 全空
    print('\n① results 全空')
    cat = _cat.load_catalog()
    for res in ({}, {'crosstrack': dict(edits=[], new_parts=[], notes=[], warnings=[]),
                     's1': dict(edits=[], new_parts=[], notes=[], warnings=[], renames={}, groups={}),
                     'ebox': dict(edits=[], new_parts=[], notes=[], warnings=[])}):
        parts = compose(cat, res, fix_defects=False)
        same = all(v.cut_d == orig[v.id].cut_d and v.engrave == orig[v.id].engrave
                   and v.cut_src == orig[v.id].cut_src and v.engrave_src == orig[v.id].engrave_src for v in parts)
        chk(len(parts) == 60 and same and all(v.layer == 'original' for v in parts),
            f'{len(parts)} 個零件 cut_d／engrave／src 與 load_catalog() 逐字相同、layer 全 original（results={list(res)}）')
    chk(all(cat[k].cut_d == orig[k].cut_d for k in cat), 'compose 沒有改到傳進來的 cat')
    parts = compose(cat, {})                  # 預設：params.FIX_26_TOOTH_HOLE
    mod = [v.id for v in parts if v.layer != 'original']
    fixed = _fr.fix_26_tooth_hole(orig['#26'])
    v26 = next(v for v in parts if v.id == '#26')
    i19 = orig['#26'].cut_src.index('path131[19]')
    diff = [k for k in range(len(v26.cut_d)) if v26.cut_d[k] != orig['#26'].cut_d[k]]
    chk(mod == ['#26'] and diff == [i19] and v26.cut_d == fixed.cut_d and v26.n_regen == 0,
        f'預設修 #26 齒孔：只有 #26 改、只改 path131[19]，和 frames.fix_26_tooth_hole() 逐字相同（改了 {mod}）')
    a26 = _Sub('o', orig['#26'].cut_d[0], True, 'outer', 0).geom.difference(unary_union(
        [_Sub(s, d, True, 'hole', i).geom for i, (s, d) in enumerate(zip(orig['#26'].cut_src, orig['#26'].cut_d)) if i])).area
    chk(abs(v26.geom.area - a26) < 1e-6 and TAG_FIX26 in v26.tags, f'#26 面積不變 {v26.geom.area:.4f}（平移孔）、tag 正確')
    cat2 = _cat.load_catalog()
    cat2['#26'] = _fr.fix_26_tooth_hole(cat2['#26'])
    v = next(v for v in compose(cat2, {}) if v.id == '#26')
    chk(v.cut_d == fixed.cut_d and v.layer == 'modified' and TAG_FIX26 in v.tags,
        '呼叫端先修過 #26 時不重複平移（冪等），仍標 modified＋tag')

    # ② #24：碰外框的缺口、union、吞掉整個孔、和孔合併、新孔、大孔內無效 subtract、雕刻
    print('\n② #24 subtract／union／雕刻')
    p24 = orig['#24']
    notch = box(5.0, 280.0, 12.0, 290.0)          # 左緣直邊上的缺口（深 5 mm）
    tab = box(3.0, 300.0, 8.0, 310.0)             # 左緣加料（往外 4 mm）
    swallow = box(49.5, 150.5, 56.0, 155.5)       # 整個包住 rect2[8]
    merge = box(18.0, 158.0, 22.0, 161.0)         # 和 rect2[2] 部分重疊
    newhole = box(60.0, 170.0, 64.0, 174.0)       # 空白處新孔
    inslot = box(40.0, 300.0, 42.0, 302.0)        # 在斜槽 rect2[1] 裡面（沒有作用）
    hit_eng = box(36.0, 336.0, 40.0, 340.0)       # 挖到雕刻「10」（text2-1-3）
    E = [dict(op='subtract', part='#24', geom=notch, tag='測試缺口'),
         dict(op='union', part='#24', geom=tab, tag='測試加料'),
         dict(op='subtract', part='#24', geom=swallow, tag='測試吞孔'),
         dict(op='subtract', part='#24', geom=merge, tag='測試併孔'),
         dict(op='subtract', part='#24', geom=newhole, tag='測試新孔'),
         dict(op='subtract', part='#24', geom=inslot, tag='測試槽內'),
         dict(op='subtract', part='#24', geom=hit_eng, tag='測試挖雕刻'),
         dict(op='move_engrave', part='#24', src='text16-7-2', dx=0.0, dy=-5.0, tag='測試移雕刻'),
         dict(op='add_engrave_text', part='#24', text='S50', x=91.0, y=300.0, size=4, angle=-90,
              anchor='middle', tag='測試文字')]
    t = time.time()
    v = next(v for v in compose(cat, {'test': dict(edits=E)}, fix_defects=False) if v.id == '#24')
    print(f'    （#24 合成 {time.time() - t:.2f} s）')
    exp_touch = {'rect2[0]', 'rect2[2]', 'rect2[8]', 'rect2[1]'}
    chk(set(v.stats['touched']) == exp_touch, f'碰到的子路徑 {sorted(v.stats["touched"])}（預期 {sorted(exp_touch)}）')
    kept = [s for s in v.cut_src if not s.endswith('*')]
    untouched = [s for s in p24.cut_src if s not in ('rect2[0]', 'rect2[2]', 'rect2[8]')]
    chk(sorted(kept) == sorted(untouched) and all(v.cut_d[v.cut_src.index(s)] == p24.cut_d[p24.cut_src.index(s)] for s in kept),
        f'沒碰到（或碰到但沒變）的 {len(kept)} 條子路徑逐字保留（含斜槽 rect2[1]）')
    chk(sorted(v.stats['regen_src']) == sorted(['rect2[0]*', 'rect2[2]*', 'rect2[8]*']) and v.stats['new_src'] == ['new1*', 'new2*'],
        f'重生 {v.stats["regen_src"]}、新孔 {v.stats["new_src"]}；rect2[8] 消失 {v.stats["vanished"]}')
    chk(v.n_kept == 32 and v.n_regen == 5 and len(v.cut_d) == 37 and v.cut_src[0] == 'rect2[0]*',
        f'保留 {v.n_kept}、重生 {v.n_regen}、共 {len(v.cut_d)} 條，外框在第 0 條')
    chk(isinstance(v.geom, Polygon) and v.geom.is_valid, '單一連通（Polygon）')
    G0 = p24.geom
    expect = (G0.union(tab).area - G0.area) - sum(G0.intersection(g).area for g in (notch, swallow, merge, newhole, hit_eng))
    base = _Sub(p24.cut_src[0], p24.cut_d[0], True, 'outer', 0).geom.difference(
        unary_union([_Sub(s, d, True, 'hole', i).geom for i, (s, d) in enumerate(zip(p24.cut_src, p24.cut_d)) if i]))
    got = v.geom.area - base.area
    chk(abs(got - expect) < 0.05, f'面積變化 {got:+.3f} mm²（用 catalog geom 算的預期 {expect:+.3f}）')
    xe = LineString([(0, 285), (20, 285)]).intersection(G0).bounds[0]      # 左緣 x
    a8 = _Sub('h', p24.cut_d[p24.cut_src.index('rect2[8]')], True, 'hole', 1).geom.area
    hand = (xe - 3.0) * 10 - (12.0 - xe) * 10 - (6.5 * 5.0 - a8) - (4 * 3 - (19.3879 - 18.0) * 3.0) - 16 - 16
    chk(abs(got - hand) < 0.05, f'面積變化和手算一致 {hand:+.3f}（左緣 x={xe:.4f}：+加料 −缺口 −吞孔(6.5×5−孔) −併孔 −16 新孔 −16 挖雕刻）')
    R = _cut_region(v, FLAT_TOL)
    chk(R.symmetric_difference(v.geom).area < 1e-3, f'輸出 d（同樣取樣）重建的區域與 geom 差 {R.symmetric_difference(v.geom).area:.2e} mm²')
    ref = [_fine_ring(p24.cut_d[0]), notch.exterior, tab.exterior]
    err = _outer_ring_err(v, ref)
    chk(err < 0.02, f'重生外框每段端點與中點離原外框／edit 邊界最多 {err:.4f} mm（≤0.02）')
    n_curve0 = sum(not isinstance(s, Line) for s in _segments(p24.cut_d[0]))
    n_curve1 = sum(not isinstance(s, Line) for s in _segments(v.cut_d[0]))
    chk(n_curve1 == n_curve0, f'外框遠離 edit 的曲線段原樣保留：曲線段 {n_curve1}／原本 {n_curve0}')
    e_old = p24.engrave[p24.engrave_src.index('text16-7-2')]
    e_new = v.engrave[v.engrave_src.index('text16-7-2')]
    b0, b1 = _d_bbox(_elem_d(e_old)), _d_bbox(_elem_d(e_new))
    chk(all(abs(b1[i] - b0[i] - (0, -5, 0, -5)[i]) < 1e-3 for i in range(4)), 'move_engrave：text16-7-2 平移 (0,-5)')
    et = v.engrave[v.engrave_src.index('text:S50')]
    chk(STYLE_ENGRAVE_FILL in et and '<text' not in ''.join(v.engrave), '新增文字轉成填色 <path>，沒有 <text>')
    chk(any('text2-1-3' in w and '挖到' in w for w in v.warnings), '雕刻被 subtract 挖到有警告（text2-1-3）')
    chk(any('測試槽內' in w and '沒有作用' in w for w in v.warnings), '在孔裡的 subtract 警告「沒有作用」')
    chk(not any('S50' in w for w in v.warnings), '新增文字沒有壓到孔')
    chk(set(v.tags) >= {'測試缺口', '測試加料', '測試吞孔', '測試移雕刻', '測試文字'} and v.layer == 'modified',
        f'layer=modified、tags 收齊（{len(v.tags)} 個）')
    # 弧線被切到：轉盤圓弧（左緣 x≈2.6）
    arc_notch = box(1.0, 198.0, 4.5, 202.0)
    v2 = next(q for q in compose(cat, {'t': dict(edits=[dict(op='subtract', part='#24', geom=arc_notch, tag='弧上缺口')])},
                                 fix_defects=False) if q.id == '#24')
    err = _outer_ring_err(v2, [_fine_ring(p24.cut_d[0]), arc_notch.exterior])
    n_curve2 = sum(not isinstance(s, Line) for s in _segments(v2.cut_d[0]))
    chk(err < 0.02 and v2.stats['poly_lines'] > 10 and n_curve2 >= n_curve0 - 2,
        f'切到圓弧：折線 {v2.stats["poly_lines"]} 段、弦高最大 {err:.4f} mm（≤0.02），其他曲線段保留 {n_curve2}／{n_curve0}')

    # 細料警告：新孔離 rect2[5]（x38.65～41.55）右邊只剩 0.3 mm
    v3 = next(q for q in compose(cat, {'t': dict(edits=[dict(op='subtract', part='#24', geom=box(41.85, 195, 44, 200), tag='貼太近')])},
                                 fix_defects=False) if q.id == '#24')
    chk(any('貼太近' in w and 'rect2[5]' in w and '0.300' in w for w in v3.warnings) and 'rect2[5]' in v3.cut_src,
        '新孔離原有孔只剩 0.3 mm：不合併、但有細料警告')

    # ③ #26：delete_cut 與 translate_cut
    print('\n③ #26 delete_cut／translate_cut')
    p26 = orig['#26']
    E = [dict(op='delete_cut', part='#26', src='path131[27]', tag='測試刪孔'),
         dict(op='translate_cut', part='#26', src='path131[1]', dx=0.0, dy=-3.0, tag='測試移孔')]
    v = next(q for q in compose(cat, {'test': dict(edits=E)}, fix_defects=False) if q.id == '#26')
    moved_d = _cat.transform_d(p26.cut_d[p26.cut_src.index('path131[1]')], _cat.translate_matrix(0, -3))
    chk('path131[27]' not in v.cut_src and len(v.cut_d) == len(p26.cut_d) - 1, 'path131[27] 刪掉')
    chk(v.cut_d[v.cut_src.index('path131[1]')] == moved_d, 'path131[1] 平移後的 d 等於 transform_d 結果（曲線種類不變）')
    others = [s for s in p26.cut_src if s not in ('path131[27]', 'path131[1]')]
    chk(all(v.cut_d[v.cut_src.index(s)] == p26.cut_d[p26.cut_src.index(s)] for s in others) and v.n_regen == 0,
        f'其他 {len(others)} 條逐字保留、重生 0 條')
    h27 = _Sub('h', p26.cut_d[p26.cut_src.index('path131[27]')], True, 'hole', 1).geom.area
    base26 = _Sub('o', p26.cut_d[0], True, 'outer', 0).geom.difference(unary_union(
        [_Sub(s, d, True, 'hole', i).geom for i, (s, d) in enumerate(zip(p26.cut_src, p26.cut_d)) if i]))
    chk(abs(v.geom.area - base26.area - h27) < 1e-6, f'面積增加 {v.geom.area - base26.area:.4f}＝刪掉的孔 {h27:.4f}')
    # 平移撞到別的孔：合併重生並警告
    E = [dict(op='translate_cut', part='#26', src='path131[1]', dx=0.0, dy=-30.0, tag='測試撞孔')]
    v = next(q for q in compose(cat, {'test': dict(edits=E)}, fix_defects=False) if q.id == '#26')
    chk('path131[1]+path131[2]*' in v.cut_src and any('合併重生' in w for w in v.warnings),
        f'平移撞到 path131[2]：合併成 {[s for s in v.cut_src if "*" in s]}，有警告')
    # 三子系統＋修正一起：修正的 translate 在前
    E = [dict(op='delete_cut', part='#26', src='path131[27]', tag='A')]
    v = next(q for q in compose(cat, {'x': dict(edits=E)}) if q.id == '#26')
    chk(v.cut_d[v.cut_src.index('path131[19]')] == fixed.cut_d[i19] and v.tags[0] == TAG_FIX26,
        '#26 子系統 edits 與齒孔修正一起套用')

    # ④ 新零件＋texts、renames、groups
    print('\n④ new_parts（含 texts）、renames、groups')
    geom = box(0, 0, 40, 20).difference(Point(33, 10).buffer(3, 64))
    vx, vy = orig['#13'].geom.exterior.coords[0]          # 外框上一點：加料方塊一半在外
    res = {'s1': dict(edits=[dict(op='union', part='#13R', geom=box(vx - 2, vy - 2, vx + 2, vy + 2), tag='測試加高（用新代號）')],
                      new_parts=[dict(id='S1-T', name='測試蓋板', material='3 mm 合板', qty=2, geom=geom,
                                      engrave=['M 2,2 L 8,2'],
                                      texts=[dict(text='S1-T', x=15, y=12, size=4, anchor='middle'),
                                             dict(text='電子盒', x=15, y=18, size=3)],
                                      group='S1-wall'),
                                 dict(id='S1-W', name='文字超出', material='壓克力', geom=box(0, 0, 10, 5),
                                      texts=[dict(text='超出很多', x=0, y=4, size=4)])],
                      renames={'#13': '#13R'}, groups={'#13R': 'S1-wall'})}
    parts = compose(cat, res, fix_defects=False)
    nv = next(q for q in parts if q.id == 'S1-T')
    chk(nv.layer == 'new' and nv.num == 0 and nv.page == 0 and nv.qty == 2 and nv.group == 'S1-wall'
        and nv.material == '合板', f'新零件 layer={nv.layer} num={nv.num} page={nv.page} qty={nv.qty} group={nv.group} 材質={nv.material}')
    chk(len(nv.cut_d) == 2 and all(nv.cut_closed) and len(nv.engrave) == 3
        and sum(STYLE_ENGRAVE_FILL in e for e in nv.engrave) == 2 and '<text' not in ''.join(nv.engrave),
        f'新零件切割 {len(nv.cut_d)} 條（外框＋孔）、雕刻 {len(nv.engrave)}（文字 2 個轉成填色 path）')
    chk(abs(_cut_region(nv).area - geom.area) < 0.05 and not nv.warnings, f'新零件面積 {_cut_region(nv).area:.3f}（geom {geom.area:.3f}），沒有警告')
    w = next(q for q in parts if q.id == 'S1-W')
    chk(w.material == '壓克力' and any('超出很多' in x for x in w.warnings), '文字超出零件有警告；材質壓克力')
    r13 = next(q for q in parts if q.orig_id == '#13')
    chk(r13.id == '#13R' and r13.group == 'S1-wall' and r13.layer == 'modified' and r13.name.startswith('抽屜櫃側板'),
        f'renames：{r13.orig_id}→{r13.id}，group={r13.group}，edits 用新代號也能指到')
    chk('#13' not in {q.id for q in parts} and len(parts) == 62, f'零件數 {len(parts)}（60＋2 新）')

    # ⑤ #27 開放切割線
    print('\n⑤ #27 開放切割線（彎曲條鋸縫）')
    p27 = orig['#27']
    cut27 = box(250.0, 240.0, 257.0, 245.0)
    v = next(q for q in compose(cat, {'t': dict(edits=[dict(op='subtract', part='#27', geom=cut27, tag='測試裁線'),
                                                        dict(op='union', part='#27', geom=box(260, 300, 262, 302), tag='測試蓋線')])},
                                fix_defects=False) if q.id == '#27')
    hit = [s for s, d, cl in zip(p27.cut_src, p27.cut_d, p27.cut_closed)
           if not cl and LineString(_flatten(_segments(d)[0])).intersects(cut27)]
    clipped = [s for s in v.cut_src if s.endswith('*') and s != v.cut_src[0]]
    ok = True
    for s in clipped:
        d = v.cut_d[v.cut_src.index(s)]
        b = _d_bbox(d)
        o = _d_bbox(p27.cut_d[p27.cut_src.index(s[:-1])])
        ok &= abs(b[0] - 257.0) < 1e-6 and abs(b[2] - o[2]) < 1e-6 and abs(b[1] - o[1]) < 1e-6
    chk(sorted(s[:-1] for s in clipped) == sorted(hit) and ok,
        f'{len(hit)} 條鋸縫被缺口裁短（起點 x=257，終點不變）')
    rest = [s for s, cl in zip(p27.cut_src, p27.cut_closed) if not cl and s not in hit]
    chk(all(v.cut_d[v.cut_src.index(s)] == p27.cut_d[p27.cut_src.index(s)] for s in rest),
        f'其他 {len(rest)} 條鋸縫逐字保留')
    chk(any('落在加料區' in x for x in v.warnings), '鋸縫落在 union 區有警告')
    chk(isinstance(v.geom, Polygon) and v.cut_src[0] == 'path14[270]*', '外框重生、單一連通')

    # ⑥ 錯誤要 raise 並說明原因
    print('\n⑥ 錯誤處理')
    for label, E, key in [
        ('subtract 把 #24 切成兩塊', [dict(op='subtract', part='#24', geom=box(-1, 260, 130, 262), tag='切斷測試')], '切斷測試'),
        ('union 沒接上本體', [dict(op='union', part='#24', geom=box(200, 200, 210, 210), tag='孤島測試')], '孤島測試'),
        ('src 不存在', [dict(op='delete_cut', part='#24', src='rect2[99]', tag='錯 src')], 'rect2[99]'),
        ('刪外框', [dict(op='delete_cut', part='#24', src='rect2[0]', tag='刪外框')], '外框'),
        ('孔平移出零件', [dict(op='translate_cut', part='#24', src='rect2[8]', dx=0, dy=-10, tag='移出去')], '超出零件外框'),
        ('零件不存在', [dict(op='subtract', part='#99', geom=box(0, 0, 1, 1))], '#99'),
        ('缺欄位', [dict(op='translate_cut', part='#24', src='rect2[8]')], '缺欄位'),
        ('缺字', [dict(op='add_engrave_text', part='#24', text='\U0001F600', x=50, y=200, size=3)], '沒有這些字'),
    ]:
        try:
            compose(cat, {'t': dict(edits=E)}, fix_defects=False)
            chk(False, f'{label}：應該 raise')
        except (ComposeError, ValueError) as ex:
            chk(key in str(ex), f'{label}：raise「{str(ex).splitlines()[0][:70]}…」' + (
                f'／{str(ex).splitlines()[-1].strip()[:60]}' if len(str(ex).splitlines()) > 1 else ''))

    rep = compose_report(compose(cat, res, fix_defects=False))
    chk('#13R（原 #13）' in rep and 'S1-T' in rep, f'compose_report 產生 {len(rep.splitlines())} 行')
    print(f'\n（全部測試 {time.time() - t0:.1f} s）')
    return errs


if __name__ == '__main__':
    import sys
    e = _selftest()
    print(f'\ncompose 自我測試：{"全部通過" if not e else f"{len(e)} 項失敗"}')
    sys.exit(1 if e else 0)

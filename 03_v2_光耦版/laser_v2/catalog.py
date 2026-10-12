"""分幣機雷切原始檔解析：把原始 SVG 依零件拆開（v2 產生器的基礎模組）。

用法
----
    from laser_v2.catalog import load_catalog, removed_items
    parts = load_catalog()          # dict[str, Part]，key = '#24' 這種零件編號
    p = parts['#24']
    p.cut_d        # list[str]：切割子路徑（絕對座標 d 字串，單位 mm，該頁左上角為原點）
    p.engrave      # list[str]：雕刻元素（完整 SVG 元素字串，座標系同上）
    p.geom         # shapely Polygon：外框減孔（供布林運算、排版）
    p.bbox         # (minx, miny, maxx, maxy)，頁座標 mm
    removed_items()  # 清理時刪掉／修正的東西（list[dict]）

座標
----
* 原始檔是 Inkscape 1.4.2、單位 mm、4 頁 300×400 橫向排列（頁原點 x = 0 / 336.45 /
  670.53 / 1003.45）。本模組把每個元素的累積 transform（圖層 translate＋群組
  rotate＋路徑自身 transform）全部套進座標，再減掉所在頁的原點，所以輸出都是
  「該頁左上角＝(0,0)、x 向右、y 向下、單位 mm」的絕對座標，沒有任何 transform。
* 曲線保留原樣（Line / CubicBezier / QuadraticBezier / Arc），不做取樣；只有
  shapely 外形（geom）是用 0.2 mm 弦長取樣的多邊形。

拆零件的規則
------------
1. 黑色 #000000 線＝切割、紅色 #ff0000＝雕刻；stroke:none 或 display:none 的
   path 看不見，視為雜線刪除；含綠色 #008000 的 text（300X400、壓克力）是註記，刪除。
2. 每個 path 用 svgpathtools 拆成連續子路徑，一個子路徑只屬於一個零件，所以
   一個 path 內混了多個零件時會自動拆開。
3. 封閉子路徑依幾何包含關係算深度：深度 0、2…＝零件外框，深度 1、3…＝孔。
   開放子路徑（螺旋切線、彎曲條的鋸縫）與雕刻子路徑，歸給「包含它大部分長度」
   的最小零件外框。
4. 零件編號（#1～#63，跳號 #28～#30）用外框所在的原始元素 id＋子路徑序號
   對照（NUMBERING 表），這張表是拿零件編號圖的藍框位置比對出來的；
   載入時會檢查 60 個零件都有編號、沒有重複。

清理（removed_items() 會逐筆列出）
---------------------------------
* stroke:none 的雜線：path9（第 1 頁，一個看不見的 #1 形狀）、path174（第 2 頁）。
* 註記文字：text173/176/178/180（300X400 ×4）、text4-3（壓克力）。
* 退化子路徑（面積 0 的來回線）：
  - rect2[18]：#24 斜槽內那條多餘切割線。它其實是一條 P0=P3、P1=P2 的三次貝茲，
    依 SVG 規格畫出來是 (V102.95,U56.02)↔(V25.59,U200.09) 來回各一次、長 163.5 mm，
    其中只有 40.2 mm 在斜槽內（V59.7,U136.6→V40.6,U172.1），另外 118 mm
    穿過 #24 本體。cairo 系的繪圖（cairosvg、零件編號圖）會把這種退化曲線略過不畫，
    所以圖上看不到；但雷切軟體若照幾何切，#24 會被切出一道長裂縫。
  - rect2[6]：#24 一個 2.9×6.4 槽（rect2[5]）邊外 0.025～0.036 mm（略斜）的 6.45 mm
    來回重複線（等於重切同一邊）。
  - path2[1]：#63 一個卡榫孔兩邊（3.95＋2.9）的來回重複線（重切）。
* 子路徑內的來回「毛刺」線段（例如 rect2[4] 起點 2.888 mm 的來回）與長度 0 的
  線段：從 d 中拿掉，形狀不變。

輸出樣式
--------
* 切割一律 fill:none;stroke:#000000;stroke-width:0.2，雕刻一律 fill:none;stroke:#ff0000;
  stroke-width:0.2。原檔的 opacity 等顯示用樣式不保留（只有 #26 的 text2 原本是
  opacity:0.6，顏色仍是 #ff0000，雷切軟體照顏色分層，結果相同）。

獨立核對（審查，2026-10-02）
---------------------------
* 用 svgelements（另一套解析器）重算原檔每條子路徑，與本模組重組回原頁位置的線做雙向
  最近距離比對：切割與雕刻逐元素最大偏差 7 µm；只有上面列的刪除項不見，沒有多出任何線；
  總長差 359.43 mm ＝ rect2[18] 327.05＋rect2[6] 12.90＋path2[1] 13.70＋rect2[4] 毛刺 5.78。
* cairosvg 整張四頁點陣相減：只差註記文字（300X400 ×4、壓克力）。
* transform：rotate(-90)（#24、抽屜零件群組）、rotate(90)、巢狀 rotate、0.2646 等比
  matrix（含旋轉）、非等比 matrix（只有 path96＝#12 的螺旋切割線；Logo path1-5-9 只有
  rotate(-90)）都核過。Arc 330、Quadratic 106、Cubic 859（少的 1 條是 rect2[18]）全部保留。
"""
from __future__ import annotations

import copy
import functools
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path as FsPath

import numpy as np
from shapely.geometry import LineString, MultiPoint, MultiPolygon, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from svgpathtools import Arc, CubicBezier, Line, QuadraticBezier, parse_path
from svgpathtools import Path as SvgPath

REPO = FsPath(__file__).resolve().parents[1]   # v2 資料夾（03_v2_光耦版），草稿與試切小樣輸出在這裡
SRC_SVG = REPO.parent / '01_原始機構' / '分幣機雷切原始檔.svg'   # 2026-10-12 整理資料夾後的位置

CUT = '#000000'
ENGRAVE = '#ff0000'
NOTE = '#008000'
SVG_NS = 'http://www.w3.org/2000/svg'
INK_NS = 'http://www.inkscape.org/namespaces/inkscape'
SODI_NS = 'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd'

MATERIAL_BY_PAGE = {1: '合板', 2: '合板', 3: '壓克力', 4: '合板'}
PLY = '合板'
ACRYLIC = '壓克力'

ZERO_LEN = 1e-4        # mm：比這短的線段視為長度 0，從 d 拿掉
CLOSE_TOL = 1e-3       # mm：起終點距離小於此值視為封閉
DEGENERATE_AREA = 0.01  # mm²：封閉子路徑面積小於此值視為退化（來回線）
SAMPLE_STEP = 0.2      # mm：shapely 取樣弦長
FMT = '{:.4f}'

# ---------------------------------------------------------------------------
# 零件編號表：外框子路徑「元素id[子路徑序號]」→ 編號。
# 由零件編號圖（分幣機雷切原始檔_零件編號圖.png）的藍框位置比對而得，
# 比對腳本與核對圖見 v2work/catalog/。
# ---------------------------------------------------------------------------
NUMBERING: dict[str, int] = {}  # 於檔尾填入


# ---------------------------------------------------------------------------
# 基本工具
# ---------------------------------------------------------------------------
def parse_transform(s: str | None) -> np.ndarray:
    """SVG transform 屬性 → 3×3 齊次矩陣（支援 matrix/translate/scale/rotate/skewX/skewY）。"""
    M = np.eye(3)
    if not s:
        return M
    for name, args in re.findall(r'(\w+)\s*\(([^)]*)\)', s):
        a = [float(x) for x in re.split(r'[\s,]+', args.strip()) if x]
        if name == 'translate':
            T = np.array([[1, 0, a[0]], [0, 1, a[1] if len(a) > 1 else 0.0], [0, 0, 1]])
        elif name == 'scale':
            sy = a[1] if len(a) > 1 else a[0]
            T = np.diag([a[0], sy, 1.0])
        elif name == 'matrix':
            T = np.array([[a[0], a[2], a[4]], [a[1], a[3], a[5]], [0, 0, 1]])
        elif name == 'rotate':
            th = math.radians(a[0])
            c, s_ = math.cos(th), math.sin(th)
            R = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1]])
            if len(a) == 3:
                cx, cy = a[1], a[2]
                T = (np.array([[1, 0, cx], [0, 1, cy], [0, 0, 1]]) @ R
                     @ np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]]))
            else:
                T = R
        elif name == 'skewX':
            T = np.array([[1, math.tan(math.radians(a[0])), 0], [0, 1, 0], [0, 0, 1]])
        elif name == 'skewY':
            T = np.array([[1, 0, 0], [math.tan(math.radians(a[0])), 1, 0], [0, 0, 1]])
        else:
            raise ValueError(f'不支援的 transform：{name}')
        M = M @ T
    return M


def _tp(M: np.ndarray, z: complex) -> complex:
    x = M[0, 0] * z.real + M[0, 1] * z.imag + M[0, 2]
    y = M[1, 0] * z.real + M[1, 1] * z.imag + M[1, 2]
    return complex(x, y)


def transform_segment(seg, M: np.ndarray):
    """把單一線段套上 3×3 仿射矩陣，曲線種類不變（Arc 會重新算半徑、旋轉角、sweep）。"""
    if isinstance(seg, Line):
        return Line(_tp(M, seg.start), _tp(M, seg.end))
    if isinstance(seg, QuadraticBezier):
        return QuadraticBezier(*[_tp(M, p) for p in seg.bpoints()])
    if isinstance(seg, CubicBezier):
        return CubicBezier(*[_tp(M, p) for p in seg.bpoints()])
    if isinstance(seg, Arc):
        A = M[:2, :2]
        det = float(np.linalg.det(A))
        rx, ry = seg.radius.real, seg.radius.imag
        # 橢圓 (R D R^T) 經 A 轉換後的新主軸
        phi = math.radians(seg.rotation)
        R = np.array([[math.cos(phi), -math.sin(phi)], [math.sin(phi), math.cos(phi)]])
        Q = R @ np.diag([1 / rx ** 2, 1 / ry ** 2]) @ R.T
        Ai = np.linalg.inv(A)
        D = Ai.T @ Q @ Ai
        w, v = np.linalg.eigh(0.5 * (D + D.T))
        nrx, nry = 1 / math.sqrt(w[0]), 1 / math.sqrt(w[1])
        rot = math.degrees(math.atan2(v[1, 0], v[0, 0]))
        sweep = seg.sweep if det > 0 else (not seg.sweep)
        new = Arc(_tp(M, seg.start), complex(nrx, nry), rot, seg.large_arc, sweep,
                  _tp(M, seg.end), autoscale_radius=True)
        # 驗證：中點與 1/4 點應與「先取點再轉換」一致，不一致就改用三次貝茲近似
        ok = all(abs(new.point(t) - _tp(M, seg.point(t))) < 1e-4 for t in (0.25, 0.5, 0.75))
        if ok:
            return new
        return [transform_segment(c, M) for c in seg.as_cubic_curves()]
    raise TypeError(type(seg))


def transform_path(path: SvgPath, M: np.ndarray) -> SvgPath:
    out = []
    for seg in path:
        r = transform_segment(seg, M)
        out.extend(r if isinstance(r, list) else [r])
    return SvgPath(*out)


def translate_matrix(dx: float, dy: float) -> np.ndarray:
    return np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1.0]])


def _f(v: float) -> str:
    s = FMT.format(v)
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def _pt(z: complex) -> str:
    return f'{_f(z.real)},{_f(z.imag)}'


def path_to_d(path: SvgPath, closed: bool | None = None) -> str:
    """svgpathtools Path（單一連續子路徑）→ 絕對座標 d 字串。"""
    if len(path) == 0:
        return ''
    if closed is None:
        closed = abs(path[-1].end - path[0].start) < CLOSE_TOL
    parts = [f'M {_pt(path[0].start)}']
    segs = list(path)
    if closed and isinstance(segs[-1], Line) and len(segs) > 1:
        segs = segs[:-1]  # 最後一段直線由 Z 補上
    for s in segs:
        if isinstance(s, Line):
            parts.append(f'L {_pt(s.end)}')
        elif isinstance(s, CubicBezier):
            parts.append(f'C {_pt(s.control1)} {_pt(s.control2)} {_pt(s.end)}')
        elif isinstance(s, QuadraticBezier):
            parts.append(f'Q {_pt(s.control)} {_pt(s.end)}')
        elif isinstance(s, Arc):
            parts.append(f'A {_f(s.radius.real)},{_f(s.radius.imag)} {_f(s.rotation)} '
                         f'{int(bool(s.large_arc))},{int(bool(s.sweep))} {_pt(s.end)}')
        else:
            raise TypeError(type(s))
    if closed:
        parts.append('Z')
    return ' '.join(parts)


def transform_d(d: str, M: np.ndarray) -> str:
    """把 d 字串（可含多個子路徑）套上 3×3 矩陣，回傳新的絕對座標 d 字串。"""
    p = parse_path(d)
    out = []
    for sp in p.continuous_subpaths():
        q = transform_path(sp, M)
        out.append(path_to_d(q))
    return ' '.join(out)


def sample_path(path: SvgPath, step: float = SAMPLE_STEP) -> np.ndarray:
    pts = []
    for seg in path:
        L = seg.length()
        n = max(2, int(math.ceil(L / step)) + 1)
        if not isinstance(seg, Line):
            n = max(n, 9)
        for t in np.linspace(0, 1, n, endpoint=False):
            z = seg.point(float(t))
            pts.append((z.real, z.imag))
    z = path[-1].end
    pts.append((z.real, z.imag))
    return np.array(pts)


def _is_reverse(a, b) -> bool:
    if type(a) is not type(b):
        return False
    if abs(a.start - b.end) > 1e-6 or abs(a.end - b.start) > 1e-6:
        return False
    return abs(a.point(0.5) - b.point(0.5)) < 1e-6 and abs(a.point(0.25) - b.point(0.75)) < 1e-6


def clean_subpath(path: SvgPath, closed: bool):
    """拿掉長度 0 的線段與來回毛刺（a 後面緊接著 a 的反向）。回傳 (新 Path, 拿掉的毛刺長度 list)。"""
    segs = [s for s in path if s.length() >= ZERO_LEN]
    stack, spurs = [], []
    for s in segs:
        if stack and _is_reverse(stack[-1], s):
            spurs.append(s.length())
            stack.pop()
        else:
            stack.append(s)
    if closed:
        while len(stack) >= 2 and _is_reverse(stack[-1], stack[0]):
            spurs.append(stack[0].length())
            stack.pop()
            stack.pop(0)
    return SvgPath(*stack), spurs


def _poly_from_pts(P: np.ndarray) -> Polygon:
    pg = Polygon(P)
    if not pg.is_valid:
        fixed = pg.buffer(0)
        if isinstance(fixed, MultiPolygon):
            fixed = max(fixed.geoms, key=lambda g: g.area)
        pg = Polygon(fixed.exterior) if not fixed.is_empty else pg
    return pg


# ---------------------------------------------------------------------------
# 資料結構
# ---------------------------------------------------------------------------
@dataclass
class Part:
    id: str                       # '#24'
    num: int                      # 24
    page: int                     # 1～3（原始檔的頁）
    material: str                 # '合板' / '壓克力'
    cut_d: list[str]              # 切割子路徑 d（第 0 個是外框）
    engrave: list[str]            # 雕刻 SVG 元素字串
    geom: Polygon                 # 外框減孔
    bbox: tuple[float, float, float, float]
    cut_src: list[str] = field(default_factory=list)      # 與 cut_d 平行：'元素id[子路徑序號]'
    cut_closed: list[bool] = field(default_factory=list)  # 與 cut_d 平行
    engrave_src: list[str] = field(default_factory=list)  # 與 engrave 平行：原始元素 id

    @property
    def size(self) -> tuple[float, float]:
        return (self.bbox[2] - self.bbox[0], self.bbox[3] - self.bbox[1])

    @property
    def outer_src(self) -> str:
        return self.cut_src[0]

    @property
    def src_ids(self) -> list[str]:
        ids = {s.split('[')[0] for s in self.cut_src} | set(self.engrave_src)
        return sorted(ids)

    def transformed(self, M: np.ndarray) -> 'Part':
        """回傳套上 3×3 矩陣後的新 Part（cut_d、engrave、geom、bbox 一起轉）。page 不變。"""
        from shapely import affinity
        q = copy.copy(self)
        q.cut_d = [transform_d(d, M) for d in self.cut_d]
        q.engrave = [transform_engrave(e, M) for e in self.engrave]
        q.geom = affinity.affine_transform(self.geom, [M[0, 0], M[0, 1], M[1, 0], M[1, 1], M[0, 2], M[1, 2]])
        q.bbox = _bbox_of_ds(q.cut_d)
        q.cut_src = list(self.cut_src)
        q.cut_closed = list(self.cut_closed)
        q.engrave_src = list(self.engrave_src)
        return q

    def svg_fragment(self, cut_style: str = 'fill:none;stroke:#000000;stroke-width:0.2',
                     group_id: str | None = None) -> str:
        """這個零件的 <g>（切割 path 一個子路徑一個元素，雕刻元素原樣）。"""
        gid = group_id or f'part{self.num}'
        lines = [f'<g id="{gid}" inkscape:label="{self.id}">']
        for i, (d, src) in enumerate(zip(self.cut_d, self.cut_src)):
            lines.append(f'  <path id="{gid}-c{i}" d="{d}" style="{cut_style}" data-src="{src}"/>')
        for e in self.engrave:
            lines.append('  ' + e)
        lines.append('</g>')
        return '\n'.join(lines)


def _bbox_of_ds(ds: list[str]) -> tuple[float, float, float, float]:
    xs0, ys0, xs1, ys1 = [], [], [], []
    for d in ds:
        p = parse_path(d)
        if len(p) == 0:
            continue
        x0, x1, y0, y1 = p.bbox()
        xs0.append(x0); xs1.append(x1); ys0.append(y0); ys1.append(y1)
    return (min(xs0), min(ys0), max(xs1), max(ys1))


def transform_engrave(elem: str, M: np.ndarray) -> str:
    """雕刻元素字串套上矩陣：<path> 直接改 d；<text> 把 transform 前乘。"""
    m = re.match(r'\s*<path\b', elem)
    if m:
        return re.sub(r'\bd="([^"]*)"', lambda mm: f'd="{transform_d(mm.group(1), M)}"', elem, count=1)
    if re.match(r'\s*<text\b', elem):
        tm = re.search(r'\btransform="matrix\(([^)]*)\)"', elem)
        old = parse_transform(f'matrix({tm.group(1)})') if tm else np.eye(3)
        new = M @ old
        s = _matrix_str(new)
        if tm:
            return elem[:tm.start()] + f'transform="{s}"' + elem[tm.end():]
        return re.sub(r'<text\b', f'<text transform="{s}"', elem, count=1)
    raise ValueError('未知的雕刻元素')


def _matrix_str(M: np.ndarray) -> str:
    return 'matrix({})'.format(','.join(_f(v) for v in (M[0, 0], M[1, 0], M[0, 1], M[1, 1], M[0, 2], M[1, 2])))


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------
def _style(e) -> dict:
    d = {}
    for kv in e.get('style', '').split(';'):
        if ':' in kv:
            k, v = kv.split(':', 1)
            d[k.strip()] = v.strip()
    for k in ('stroke', 'fill', 'display', 'visibility'):
        if e.get(k) is not None and k not in d:
            d[k] = e.get(k)
    return d


@dataclass
class _Sub:
    eid: str
    k: int
    color: str
    path: SvgPath        # 已轉成絕對座標（整份文件座標，尚未減頁原點）
    closed: bool
    pts: np.ndarray      # 清理後的取樣點
    orig_pts: np.ndarray  # 清理前的取樣點（定位刪除項目用）
    spurs: list = field(default_factory=list)

    @property
    def key(self):
        return f'{self.eid}[{self.k}]'


def _read_pages(root) -> list[tuple[float, float, float, float]]:
    pages = []
    for e in root.iter(f'{{{INK_NS}}}page'):
        pages.append((float(e.get('x')), float(e.get('y')), float(e.get('width')), float(e.get('height'))))
    pages.sort(key=lambda p: (p[0], p[1]))
    return pages


def _page_of(x: float, pages) -> int:
    best, bd = 1, 1e18
    for i, (px, py, pw, ph) in enumerate(pages, start=1):
        if px <= x <= px + pw:
            return i
        dd = min(abs(x - px), abs(x - px - pw))
        if dd < bd:
            best, bd = i, dd
    return best


def _xml_text(e) -> str:
    return ''.join(e.itertext())


def _strip_ns(s: str) -> str:
    s = re.sub(r'\sxmlns(:\w+)?="[^"]*"', '', s)
    s = re.sub(r'<(/?)ns\d+:', r'<\1', s)
    s = re.sub(r'\sns\d+:', ' inkscape:', s)
    return s


@functools.lru_cache(maxsize=4)
def _build(svg_path: str):
    root = ET.parse(svg_path).getroot()
    pages = _read_pages(root)
    subs: list[_Sub] = []
    texts = []        # (elem, M, style)
    removed = []

    def walk(e, M, inh):
        tag = e.tag.split('}')[-1]
        if tag in ('defs', 'namedview', 'desc', 'title', 'metadata'):
            return
        M = M @ parse_transform(e.get('transform'))
        st = dict(inh)
        own = _style(e)
        for k in ('stroke', 'fill', 'display', 'visibility'):
            if k in own:
                st[k] = own[k]
        invisible = st.get('display') == 'none' or st.get('visibility') == 'hidden'
        if tag == 'path' and e.get('d'):
            eid = e.get('id')
            color = (st.get('stroke') or 'none').lower()
            if invisible or color in ('none', ''):
                p = transform_path(parse_path(e.get('d')), M)
                x0, x1, y0, y1 = p.bbox()
                pg = _page_of((x0 + x1) / 2, pages)
                px, py = pages[pg - 1][:2]
                removed.append(dict(kind='不可見雜線', id=eid, page=pg,
                                    where=f'頁{pg} x{x0 - px:.1f}~{x1 - px:.1f} y{y0 - py:.1f}~{y1 - py:.1f}',
                                    reason='stroke:none（看不見、不切割），刪除',
                                    detail=f'{len(p.continuous_subpaths())} 個子路徑'))
                return
            p = parse_path(e.get('d'))
            for k, sp in enumerate(p.continuous_subpaths()):
                q = transform_path(sp, M)
                closed = abs(q.start - q.end) < CLOSE_TOL
                q2, spurs = clean_subpath(q, closed)
                subs.append(_Sub(eid, k, color, q2, closed,
                                 sample_path(q2) if len(q2) else np.zeros((0, 2)),
                                 sample_path(q) if len(q) else np.zeros((0, 2)), spurs))
            return
        if tag == 'text':
            texts.append((e, M, st))
            return
        for c in e:
            walk(c, M, st)

    walk(root, np.eye(3), {})

    # --- 註記文字 ---------------------------------------------------------
    keep_texts = []
    for e, M, st in texts:
        fills = {(_style(t).get('fill') or '').lower() for t in e.iter()} | {(st.get('fill') or '').lower()}
        x = float(e.get('x', 0)); y = float(e.get('y', 0))
        z = _tp(M, complex(x, y))
        pg = _page_of(z.real, pages)
        px, py = pages[pg - 1][:2]
        if NOTE in fills:
            removed.append(dict(kind='註記文字', id=e.get('id'), page=pg,
                                where=f'頁{pg} 約 x{z.real - px:.1f} y{z.imag - py:.1f}',
                                reason=f'註記「{_xml_text(e).strip()}」（tspan 綠色 fill:{NOTE}、外層 stroke:{st.get("stroke")}），刪除',
                                detail=''))
        else:
            keep_texts.append((e, M, st, pg))

    # --- 退化子路徑 --------------------------------------------------------
    good: list[_Sub] = []
    degenerate: list[tuple[dict, _Sub]] = []
    for s in subs:
        if len(s.path) == 0:
            r = dict(kind='退化子路徑', id=s.key, page=_page_of_sub(s, pages), where=_where(s, pages),
                     reason='整條都是來回重複線（拿掉來回毛刺後什麼都不剩），刪除',
                     detail=f'來回線段長 {" + ".join(f"{v:.2f}" for v in s.spurs)} mm')
            removed.append(r); degenerate.append((r, s))
            continue
        if s.closed:
            area = abs(Polygon(s.pts).area) if len(s.pts) >= 4 else 0.0
            if area < DEGENERATE_AREA:
                r = dict(kind='退化子路徑', id=s.key, page=_page_of_sub(s, pages), where=_where(s, pages),
                         reason='封閉但面積≈0（同一條線來回走一次），刪除',
                         detail=f'實際線段長 {s.path.length() / 2:.2f} mm')
                removed.append(r); degenerate.append((r, s))
                continue
        big_spurs = [v for v in s.spurs if v >= 0.01]
        if big_spurs:
            removed.append(dict(kind='來回毛刺', id=s.key, page=_page_of_sub(s, pages), where=_where(s, pages),
                                reason='子路徑內有線段緊接著自己的反向（同一段重切），只拿掉毛刺，形狀不變',
                                detail=f'毛刺長 {", ".join(f"{v:.3f}" for v in big_spurs)} mm'))
        good.append(s)

    cut = [s for s in good if s.color == CUT]
    eng = [s for s in good if s.color == ENGRAVE]
    other = [s for s in good if s.color not in (CUT, ENGRAVE)]
    for s in other:
        removed.append(dict(kind='未知顏色', id=s.key, page=None, where=_where(s, pages),
                            reason=f'stroke {s.color} 不是切割也不是雕刻，刪除', detail=''))

    # --- 封閉切割子路徑 → 包含深度 ---------------------------------------
    closed = [s for s in cut if s.closed]
    polys = [_poly_from_pts(s.pts) for s in closed]
    areas = np.array([p.area for p in polys])
    tree = STRtree(polys)
    parent = [-1] * len(closed)
    for i, pg in enumerate(polys):
        rp = pg.representative_point()
        best = -1
        for j in tree.query(rp):
            j = int(j)
            if j == i or areas[j] <= areas[i]:
                continue
            if polys[j].contains(rp) and polys[j].buffer(0.05).contains(pg):
                if best < 0 or areas[j] < areas[best]:
                    best = j
        parent[i] = best
    depth = [0] * len(closed)
    for i in range(len(closed)):
        d, j = 0, parent[i]
        while j >= 0:
            d += 1
            j = parent[j]
        depth[i] = d

    groups: dict[int, list[int]] = {}
    for i in range(len(closed)):
        if depth[i] % 2 == 0:
            groups.setdefault(i, [i])
    for i in range(len(closed)):
        if depth[i] % 2 == 1:
            groups[parent[i]].append(i)
    outer_ids = list(groups)
    outer_polys = [polys[i] for i in outer_ids]
    otree = STRtree(outer_polys)

    def owner(s: _Sub) -> int | None:
        """包含此線段大部分長度（>50%）的零件外框中，面積最小的那個。"""
        line = unary_union(LineString(s.pts))  # 去掉來回重疊，長度只算一趟
        best = None
        for j in otree.query(line):
            j = int(j)
            op = outer_polys[j]
            frac = line.intersection(op.buffer(0.05)).length / max(line.length, 1e-9)
            if frac > 0.5 and (best is None or op.area < outer_polys[best].area):
                best = j
        return best

    open_by_part: dict[int, list[_Sub]] = {}
    for s in cut:
        if s.closed:
            continue
        j = owner(s)
        if j is None:
            removed.append(dict(kind='孤立開放線', id=s.key, page=None, where=_where(s, pages),
                                reason='不在任何零件內，刪除', detail=''))
            continue
        open_by_part.setdefault(j, []).append(s)
    eng_by_part: dict[int, list[_Sub]] = {}
    for s in eng:
        j = owner(s)
        if j is None:
            removed.append(dict(kind='孤立雕刻', id=s.key, page=None, where=_where(s, pages),
                                reason='不在任何零件內，刪除', detail=''))
            continue
        eng_by_part.setdefault(j, []).append(s)

    # 雕刻 text（目前原檔沒有；保留通用處理）
    text_by_part: dict[int, list] = {}
    for e, M, st, pg in keep_texts:
        z = _tp(M, complex(float(e.get('x', 0)), float(e.get('y', 0))))
        hit = [j for j in otree.query(Point(z.real, z.imag)) if outer_polys[int(j)].contains(Point(z.real, z.imag))]
        if not hit:
            removed.append(dict(kind='孤立文字', id=e.get('id'), page=pg, where='', reason='不在零件內，刪除', detail=''))
            continue
        j = min((int(h) for h in hit), key=lambda h: outer_polys[h].area)
        text_by_part.setdefault(j, []).append((e, M))

    # --- 組成 Part --------------------------------------------------------
    parts: dict[str, Part] = {}
    unnumbered = []
    for j, oi in enumerate(outer_ids):
        members = groups[oi]
        outer = closed[oi]
        cx = (outer.pts[:, 0].min() + outer.pts[:, 0].max()) / 2
        pg = _page_of(cx, pages)
        px, py = pages[pg - 1][:2]
        T = translate_matrix(-px, -py)
        hole_idx = sorted(members[1:], key=lambda i: (closed[i].eid, closed[i].k))
        subs_in = [outer] + [closed[i] for i in hole_idx] + sorted(open_by_part.get(j, []), key=lambda s: (s.eid, s.k))
        cut_paths = [transform_path(s.path, T) for s in subs_in]
        cut_d = [path_to_d(p, s.closed) for p, s in zip(cut_paths, subs_in)]
        shell = outer.pts - [px, py]
        holes = [closed[i].pts - [px, py] for i in hole_idx]
        geom = Polygon(_poly_from_pts(shell).exterior, [_poly_from_pts(h).exterior for h in holes])
        if not geom.is_valid:
            geom = geom.buffer(0)
        # 雕刻：同一元素同一零件的子路徑合成一個 <path>
        engrave, engrave_src = [], []
        by_elem: dict[str, list[_Sub]] = {}
        for s in eng_by_part.get(j, []):
            by_elem.setdefault(s.eid, []).append(s)
        for eid in sorted(by_elem):
            ss = sorted(by_elem[eid], key=lambda s: s.k)
            d = ' '.join(path_to_d(transform_path(s.path, T), s.closed) for s in ss)
            engrave.append(f'<path d="{d}" style="fill:none;stroke:{ENGRAVE};stroke-width:0.2" data-src="{eid}"/>')
            engrave_src.append(eid)
        for e, M in text_by_part.get(j, []):
            e2 = copy.deepcopy(e)
            e2.set('transform', _matrix_str(T @ M))
            engrave.append(_strip_ns(ET.tostring(e2, encoding='unicode')).strip())
            engrave_src.append(e.get('id'))
        key = outer.key
        num = NUMBERING.get(key)
        if num is None:
            unnumbered.append(key)
            pid = f'?{key}'
        else:
            pid = f'#{num}'
        parts[pid] = Part(id=pid, num=num if num is not None else -1, page=pg,
                          material=MATERIAL_BY_PAGE.get(pg, PLY), cut_d=cut_d, engrave=engrave,
                          geom=geom, bbox=_bbox_of_paths(cut_paths[:1]),
                          cut_src=[s.key for s in subs_in], cut_closed=[s.closed for s in subs_in],
                          engrave_src=engrave_src)
    # 補註：退化線落在哪個零件、穿過孔與本體各多長
    by_outer = {j: p for j, p in zip(range(len(outer_ids)), parts.values())}
    for r, s in degenerate:
        line = _trace(s.orig_pts)
        j = owner(_Sub(s.eid, s.k, s.color, s.path, False, s.orig_pts, s.orig_pts))
        if j is None:
            continue
        p = by_outer[j]
        pg = pages[p.page - 1]
        from shapely import affinity
        g = affinity.translate(p.geom, pg[0], pg[1])
        in_mat = line.intersection(g).length
        in_hole = line.intersection(Polygon(g.exterior)).length - in_mat
        r['part'] = p.id
        others = [LineString(sample_path(parse_path(d))) for d in p.cut_d]
        gap = min(affinity.translate(o, pg[0], pg[1]).distance(line) for o in others)
        r['detail'] += (f'；在 {p.id} 上，穿過孔／槽 {in_hole:.1f} mm、穿過本體 {in_mat:.1f} mm；'
                        f'離同零件其他切割線最近 {gap:.3f} mm')
        if p.num == 24 and in_hole > 30:
            r['kind'] = '#24 斜槽多餘切割線'
            r['reason'] = ('P0=P3、P1=P2 的退化三次貝茲（畫出來是一條直線來回各一次），'
                           '刪除；注意它不只在斜槽內，也穿過 #24 本體，照切會把 #24 切出裂縫')
    return parts, removed, unnumbered, pages


def _trace(pts: np.ndarray):
    """退化線的實際走過的軌跡（來回只算一趟）。共線時取兩端點連線。"""
    hull = MultiPoint([tuple(p) for p in pts]).convex_hull
    if hull.geom_type == 'LineString':
        return hull
    if hull.geom_type == 'Polygon' and hull.area < 1e-3 * max(hull.length, 1.0):
        H = np.array(hull.exterior.coords)
        D = np.linalg.norm(H[:, None, :] - H[None, :, :], axis=2)
        i, j = np.unravel_index(np.argmax(D), D.shape)
        return LineString([H[i], H[j]])
    return unary_union(LineString(pts))


def _page_of_sub(s: '_Sub', pages) -> int:
    P = s.orig_pts if len(s.orig_pts) else s.pts
    return _page_of((P[:, 0].min() + P[:, 0].max()) / 2, pages)


def _bbox_of_paths(paths) -> tuple[float, float, float, float]:
    xs0, ys0, xs1, ys1 = [], [], [], []
    for p in paths:
        x0, x1, y0, y1 = p.bbox()
        xs0.append(x0); xs1.append(x1); ys0.append(y0); ys1.append(y1)
    return (min(xs0), min(ys0), max(xs1), max(ys1))


def _where(s: _Sub, pages) -> str:
    P = s.orig_pts if len(s.orig_pts) else s.pts
    if len(P) == 0:
        return ''
    cx = (P[:, 0].min() + P[:, 0].max()) / 2
    pg = _page_of(cx, pages)
    px, py = pages[pg - 1][:2]
    return (f'頁{pg} x{P[:, 0].min() - px:.2f}~{P[:, 0].max() - px:.2f} '
            f'y{P[:, 1].min() - py:.2f}~{P[:, 1].max() - py:.2f}')


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------
def load_catalog(svg_path: str | FsPath = SRC_SVG, strict: bool = True) -> dict[str, Part]:
    """解析原始 SVG，回傳 {'#1': Part, …}（60 個零件）。每次回傳新的 Part 物件，可自由修改。"""
    parts, removed, unnumbered, _ = _build(str(svg_path))
    if strict:
        if unnumbered:
            raise RuntimeError(f'有零件沒有編號：{unnumbered}')
        nums = sorted(p.num for p in parts.values())
        expect = [n for n in range(1, 64) if n not in (28, 29, 30)]
        if nums != expect:
            raise RuntimeError(f'零件編號不完整：缺 {sorted(set(expect) - set(nums))}，多 {sorted(set(nums) - set(expect))}')
    out = {}
    for k in sorted(parts, key=lambda k: (parts[k].num, k)):
        p = parts[k]
        q = copy.copy(p)
        q.cut_d = list(p.cut_d); q.engrave = list(p.engrave)
        q.cut_src = list(p.cut_src); q.cut_closed = list(p.cut_closed); q.engrave_src = list(p.engrave_src)
        out[k] = q
    return out


def removed_items(svg_path: str | FsPath = SRC_SVG) -> list[dict]:
    """清理時刪除或修正的項目：kind / id / where / reason / detail。"""
    _, removed, _, _ = _build(str(svg_path))
    return [dict(r) for r in removed]


def pages(svg_path: str | FsPath = SRC_SVG) -> list[tuple[float, float, float, float]]:
    """原始檔各頁 (x, y, w, h)，依 x 排序（第 1 頁在前）。"""
    return list(_build(str(svg_path))[3])


def part_path(part: Part, i: int = 0) -> SvgPath:
    """第 i 個切割子路徑的 svgpathtools Path（頁座標）。"""
    return parse_path(part.cut_d[i])


def svg_document(parts: list[Part], width: float = 300, height: float = 400, extra: str = '') -> str:
    """把零件（頁座標）輸出成一份單頁 SVG 字串（給檢查用；正式排版由其他模組負責）。"""
    body = '\n'.join(p.svg_fragment() for p in parts)
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="{SVG_NS}" xmlns:inkscape="{INK_NS}" width="{width}mm" height="{height}mm" '
            f'viewBox="0 0 {width} {height}">\n{body}\n{extra}\n</svg>\n')


# ---------------------------------------------------------------------------
# 編號表（外框子路徑 → 零件編號）
# ---------------------------------------------------------------------------
NUMBERING.update({
    'path3[0]': 1, 'path6[0]': 2, 'path7[0]': 3, 'path180[8]': 4,
    'rect370[0]': 5, 'path529[0]': 6, 'path414[0]': 7, 'rect227-2[0]': 8,
    'path18[0]': 9, 'path1[0]': 10, 'path50[0]': 11, 'path52[0]': 12,
    'path256[0]': 13, 'circle37-6[0]': 14, 'path152[0]': 15, 'rect113[0]': 16,
    'path116[0]': 17, 'path159[0]': 18, 'path51[0]': 19, 'path20[0]': 20,
    'path13[0]': 21, 'path33[0]': 22, 'path19[0]': 23, 'rect2[0]': 24,
    'path149[0]': 25, 'path131[0]': 26, 'path14[270]': 27, 'path106[0]': 31,
    'path197[0]': 32, 'rect238[0]': 33, 'path204[0]': 34, 'path202[0]': 35,
    'path44[0]': 36, 'path509-6[0]': 37, 'path185[0]': 38, 'path178[0]': 39,
    'path109[0]': 40, 'path181[0]': 41, 'path183[0]': 42, 'path191[0]': 43,
    'path233[0]': 44, 'path107[0]': 45, 'path111[0]': 46, 'path189[0]': 47,
    'path105[0]': 48, 'path112[0]': 49, 'path193[0]': 50, 'path195[0]': 51,
    'path63[0]': 52, 'path61[0]': 53, 'path24[0]': 54, 'path25[0]': 55,
    'path59[0]': 56, 'path65[0]': 57, 'path34[0]': 58, 'path113[0]': 59,
    'path103[0]': 60, 'path110[0]': 61, 'path257[0]': 62, 'path2[0]': 63,

})


def table(parts: dict[str, Part] | None = None) -> str:
    """編號表：#n、頁、材質、尺寸、切割子路徑數（開放）、雕刻、原始元素 id。"""
    parts = parts if parts is not None else load_catalog()
    lines = ['編號\t頁\t材質\t尺寸(mm)\t切割(開放)\t雕刻\t外框\t其他原始元素']
    for p in sorted(parts.values(), key=lambda p: p.num):
        w, h = p.size
        others = [i for i in p.src_ids if i != p.outer_src.split('[')[0]]
        lines.append(f'{p.id}\t{p.page}\t{p.material}\t{w:.1f}×{h:.1f}\t{len(p.cut_d)}({p.cut_closed.count(False)})\t'
                     f'{len(p.engrave)}\t{p.outer_src}\t{",".join(others)}')
    return '\n'.join(lines)


if __name__ == '__main__':
    print(table())
    print('\n刪除／修正：')
    for r in removed_items():
        print(f"- [{r['kind']}] {r['id']} {r['where']}：{r['reason']}" + (f"（{r['detail']}）" if r['detail'] else ''))

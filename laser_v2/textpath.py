"""雕刻文字轉路徑：把一行文字用字型的輪廓轉成 SVG path d（v2 產生器用，輸出裡不留 <text>）。

用法
----
    from laser_v2.textpath import text_to_d
    d = text_to_d('S1-C', x=10, y=20, size=4)                    # 基線左端在 (10, 20)
    d = text_to_d('電子盒', 50, 30, 5, angle=90, anchor='middle')  # 以 (50, 30) 為中心、轉 90°

    compose.py 會把 d 包成 <path d="…" style="fill:none;stroke:#ff0000;stroke-width:0.2"/>
    （compose.STYLE_ENGRAVE：和原始檔的雕刻一樣是紅色 0.2 mm「外框線字」，不填色）。
    使用者 2026-10-08 決定：雕刻樣式統一成原始檔的紅色 0.2 mm 線，紅色圖層在雷切軟體設「線／向量雕刻」；
    字會刻出每個輪廓的外框線——外框和字腔（口、回、8、0、B 的內框）都是獨立的封閉輪廓，所以中空字的
    內外框都會刻到（自我測試逐字檢查：每個輪廓都封閉、不自交、輪廓之間不交叉，線雕時字裡不會多出線）。

排字小工具（給各子系統放代號字）
------------------------------
    ink_bounds(text, size, angle, anchor, x, y)  → 字墨的精確外包 (x0, y0, x1, y1)（輪廓曲線的 bbox）
    ink_box(text, x, y, size, angle, anchor)     → 字墨外框（未旋轉時的外包矩形，再繞錨點旋轉）：Polygon
    fit_text(region, text, sizes, clear=TEXT_CLEAR, avoid=…, avoid_clear=ENGRAVE_GAP, angles=…, prefer=…)
        在 region（零件實料，含孔）裡找字墨外框離 region 邊界（＝切割線）≥ clear、離 avoid（其他雕刻線、
        記號、黏貼框）≥ avoid_clear 的位置；sizes 依序試（先大後小），回傳 add_engrave_text／texts 用的 dict
        （另含 ink＝字墨外框、slack＝比要求多出的距離），放不下回傳 None。
    TEXT_CLEAR＝1.0（字墨離任何切割線）、ENGRAVE_GAP＝0.4（字墨離其他雕刻線，兩條 0.2 線之間還留 0.2 空隙）。

座標與參數
----------
* 單位 mm，SVG 座標（x 向右、y 向下），和 catalog.Part 的頁座標相同。
* (x, y)：基線上的錨點。anchor='start'＝錨點在第一個字的起筆位置（字寬方框左緣），
  'middle'＝錨點在整行字寬（各字 advance 總和）的中點，'end'＝錨點在整行字寬的右端。
  只對齊水平方向；垂直方向一律以基線為準（大寫字母頂在 y − 0.756·size 左右，
  中文字約 y − 0.84·size～y + 0.07·size）。
* size：em 高（mm）。微軟正黑體 unitsPerEm＝2048，所以 1 個字型單位＝size/2048 mm。
* angle：度，照 SVG rotate() 的方向（y 向下，所以正值在畫面上是順時針），繞錨點 (x, y) 轉。
  angle=90 時字由上往下排、字頭朝右。
* 字距只用各字的 advance（hmtx），不做 kerning；一行文字，不處理換行。

字型
----
* 讀 params.FONT_PATH（C:\\Windows\\Fonts\\msjh.ttc，微軟正黑體，使用者 2026-10-07 指定）的
  第 0 個字型（TTC 內的 Microsoft JhengHei Regular）。這是 TrueType glyf 字型，輪廓是二次
  貝茲，原樣輸出成 Q 指令（不取樣），組合字（composite glyph）由 fontTools 展開。
* 字型裡沒有的字一律 raise ValueError（不默默換字或略過）。空白有 advance、沒有輪廓。
* 輸出全部是封閉輪廓（每個輪廓以 Z 結尾），外框與字腔方向相反；已檢查 v2 用到的字沒有互相
  重疊或交叉的輪廓，所以線雕只刻出字的外形，填色預覽時 nonzero 與 evenodd 結果也相同（見自我測試）。
  outline_problems(text) 可檢查任一段文字（compose 對每個新增的字都會查，有問題發警告）。

自我測試：python -m laser_v2.textpath
"""
from __future__ import annotations

import functools
import math

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

from . import params

FONT_INDEX = 0          # TTC 內第幾個字型
ANCHORS = ('start', 'middle', 'end')
FMT = '{:.4f}'          # 和 catalog.py 相同的輸出精度（0.1 µm）
TEXT_CLEAR = 1.0        # mm：v2 新增的字，字墨離任何切割線（外框、孔、缺口）的下限（使用者 2026-10-08）
ENGRAVE_GAP = 0.4       # mm：字墨離其他雕刻線（黏貼框、▲ 記號、方塊）的下限：不壓到線，兩條 0.2 線之間留 0.2


def _f(v: float) -> str:
    s = FMT.format(v)
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


@functools.lru_cache(maxsize=4)
def _font(path: str, index: int):
    """載入字型（快取）。回傳 (TTFont, glyphSet, cmap, unitsPerEm)。"""
    font = TTFont(path, fontNumber=index, lazy=True)
    if 'glyf' not in font:
        raise ValueError(f'{path} 第 {index} 個字型不是 TrueType glyf 字型')
    return font, font.getGlyphSet(), font.getBestCmap(), font['head'].unitsPerEm


def font_info(path: str | None = None, index: int = FONT_INDEX) -> dict:
    """字型名稱、unitsPerEm、大寫高、上下緣（給報告與測試用）。"""
    font, _, _, upem = _font(path or params.FONT_PATH, index)
    os2 = font['OS/2']
    return dict(family=font['name'].getDebugName(1), full=font['name'].getDebugName(4), upem=upem,
                cap_height=getattr(os2, 'sCapHeight', None), ascent=font['hhea'].ascent,
                descent=font['hhea'].descent)


class _AbsPen(BasePen):
    """把字型單位的輪廓轉成 SVG 絕對座標 d 指令（M/L/Q/C/Z）。xf：(gx, gy) → (X, Y)。"""

    def __init__(self, glyphset, xf):
        super().__init__(glyphset)
        self.xf = xf
        self.out: list[str] = []

    def _p(self, pt) -> str:
        X, Y = self.xf(pt[0], pt[1])
        return f'{_f(X)},{_f(Y)}'

    def _moveTo(self, pt):
        self.out.append(f'M {self._p(pt)}')

    def _lineTo(self, pt):
        self.out.append(f'L {self._p(pt)}')

    def _qCurveToOne(self, pt1, pt2):
        self.out.append(f'Q {self._p(pt1)} {self._p(pt2)}')

    def _curveToOne(self, pt1, pt2, pt3):
        self.out.append(f'C {self._p(pt1)} {self._p(pt2)} {self._p(pt3)}')

    def _closePath(self):
        self.out.append('Z')

    def _endPath(self):
        # 字型輪廓理論上都封閉；開放輪廓雷切填色沒有意義，視為錯誤
        raise ValueError('字型輪廓沒有封閉（endPath），無法當填色雕刻')


def _glyph_names(text: str, cmap) -> list[str]:
    names = []
    missing = []
    for ch in text:
        n = cmap.get(ord(ch))
        if n is None:
            missing.append(ch)
        names.append(n)
    if missing:
        shown = '、'.join(f'「{c}」(U+{ord(c):04X})' for c in missing)
        raise ValueError(f'字型 {params.FONT_PATH} 沒有這些字：{shown}（文字「{text}」）')
    return names


def text_advance(text: str, size: float, path: str | None = None, index: int = FONT_INDEX) -> float:
    """整行字寬（各字 advance 總和，mm）。"""
    font, gs, cmap, upem = _font(path or params.FONT_PATH, index)
    return sum(gs[n].width for n in _glyph_names(text, cmap)) * size / upem


def text_to_d(text: str, x: float, y: float, size: float, angle: float = 0.0, anchor: str = 'start',
              *, font_path: str | None = None, font_index: int = FONT_INDEX) -> str:
    """文字 → SVG path d（mm、SVG 座標）。參數意義見模組說明；缺字 raise ValueError。"""
    if anchor not in ANCHORS:
        raise ValueError(f'anchor 只能是 {ANCHORS}，收到 {anchor!r}')
    if not (size > 0):
        raise ValueError(f'size 必須 > 0，收到 {size!r}')
    if not text:
        raise ValueError('文字是空的')
    font, gs, cmap, upem = _font(font_path or params.FONT_PATH, font_index)
    names = _glyph_names(text, cmap)
    s = size / upem
    total = sum(gs[n].width for n in names) * s
    shift = {'start': 0.0, 'middle': -total / 2, 'end': -total}[anchor]
    th = math.radians(angle)
    c, sn = math.cos(th), math.sin(th)
    out: list[str] = []
    pen_x = 0.0
    for n in names:
        g = gs[n]
        ox = shift + pen_x

        def xf(gx, gy, ox=ox):
            u = ox + gx * s          # 沿基線
            v = -gy * s              # 字型 y 向上 → SVG y 向下
            return x + u * c - v * sn, y + u * sn + v * c

        pen = _AbsPen(gs, xf)
        g.draw(pen)
        out.extend(pen.out)
        pen_x += g.width * s
    return ' '.join(out)


# ---------------------------------------------------------------------------
# 字墨外框與排字（給子系統放代號字；compose 檢查用）
# ---------------------------------------------------------------------------
def _bbox(d: str):
    from svgpathtools import parse_path
    x0, x1, y0, y1 = parse_path(d).bbox()
    return float(x0), float(y0), float(x1), float(y1)


def ink_bounds(text: str, size: float, angle: float = 0.0, anchor: str = 'start', x: float = 0.0, y: float = 0.0,
               *, font_path: str | None = None, font_index: int = FONT_INDEX) -> tuple[float, float, float, float]:
    """字墨（所有輪廓曲線）的精確外包 (x0, y0, x1, y1)，mm、SVG 座標。只有空白時 raise ValueError。"""
    d = text_to_d(text, x, y, size, angle, anchor, font_path=font_path, font_index=font_index)
    if not d:
        raise ValueError(f'文字「{text}」沒有字墨（只有空白）')
    return _bbox(d)


@functools.lru_cache(maxsize=1024)
def _ink_rel(text: str, size: float, anchor: str, font_path: str | None, font_index: int):
    """angle=0、錨點在 (0, 0) 時的字墨外包。"""
    return ink_bounds(text, size, 0.0, anchor, 0.0, 0.0, font_path=font_path, font_index=font_index)


def _box_coords(text, x, y, size, angle, anchor, font_path=None, font_index=FONT_INDEX):
    x0, y0, x1, y1 = _ink_rel(str(text), float(size), anchor, font_path, font_index)
    th = math.radians(angle)
    c, s = math.cos(th), math.sin(th)
    return [(x + u * c - v * s, y + u * s + v * c) for u, v in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]


def ink_box(text: str, x: float, y: float, size: float, angle: float = 0.0, anchor: str = 'start',
            *, font_path: str | None = None, font_index: int = FONT_INDEX):
    """字墨外框：angle=0 時的字墨外包矩形，繞錨點 (x, y) 轉 angle（和 text_to_d 同一套參數）。

    是字墨的「外包」：外框離某條線 ≥ c，字墨一定也 ≥ c（保守）。回傳 shapely Polygon。"""
    from shapely.geometry import Polygon
    return Polygon(_box_coords(text, x, y, size, angle, anchor, font_path, font_index))


def text_spec(fit: dict) -> dict:
    """fit_text() 的結果 → add_engrave_text／new_parts.texts 用的 dict（只留 text/x/y/size/angle/anchor）。"""
    return {k: fit[k] for k in ('text', 'x', 'y', 'size', 'angle', 'anchor')}


def _anchor_set(allowed, rel):
    """字墨外框（錨點在原點時的四角 rel）整個落在 allowed 裡的錨點集合（精確，Minkowski）。

    外框是凸的：外框和 allowed 的邊界不相交、且中心在 allowed 裡 ⇔ 外框整個在 allowed 裡。
    所以「可用錨點」＝(allowed 平移 −中心) − ∪(每條邊界邊 ⊕ (−外框))，每一項是 8 個點的凸包。"""
    import numpy as np
    import shapely
    from shapely import affinity

    polys = [g for g in getattr(allowed, 'geoms', [allowed]) if g.geom_type == 'Polygon' and not g.is_empty]
    if not polys:
        return None
    p0, p1 = [], []
    for pg in polys:
        for ring in [pg.exterior, *pg.interiors]:
            c = np.asarray(ring.coords)
            p0.append(c[:-1])
            p1.append(c[1:])
    P0, P1 = np.concatenate(p0), np.concatenate(p1)
    neg = -np.asarray(rel, float)
    pts = np.concatenate([P0[:, None, :] + neg[None], P1[:, None, :] + neg[None]], axis=1)
    forbid = shapely.union_all(shapely.convex_hull(shapely.multipoints(pts)))
    c = np.asarray(rel, float).mean(axis=0)
    base = affinity.translate(shapely.union_all(polys), -c[0], -c[1])
    return base.difference(forbid)


def fit_text(region, text: str, sizes, *, clear: float = TEXT_CLEAR, avoid=None, avoid_clear: float = ENGRAVE_GAP,
             angles=(0.0,), anchor: str = 'middle', prefer=None, angle_penalty: float = 0.3, step=None) -> dict | None:
    """在 region 裡放一行字，字墨外框（ink_box）離 region 邊界 ≥ clear、離 avoid ≥ avoid_clear。

    region：零件實料（shapely Polygon，含孔；邊界＝切割線）；avoid：不可壓到的東西（其他雕刻線、記號、
    黏貼框、要留空的區域；線或面都可以），None＝沒有。sizes：em 高，依序試，第一個放得下的就用。
    angles：可用的角度（度，和 text_to_d 相同），排前面的優先（每往後一個扣 angle_penalty mm 的分數；
    給很大的值＝同一個字高下，前面的角度放得下就不用後面的）。
    prefer：(x, y) 偏好的字墨外框中心；放得下就用那裡，否則取放得下的位置裡離它最近的；
    沒有 prefer 時取「比要求多出的距離」(slack) 最大的位置。
    可用位置用 Minkowski 精確算（不是格點搜尋），所以剛好擠得進窄條的字也找得到。
    回傳 dict(text, x, y, size, angle, anchor, ink=Polygon, slack=float)（text_spec() 取前 6 個鍵），
    放不下回傳 None。step 參數保留相容、不使用。"""
    import numpy as np
    import shapely
    from shapely.geometry import Point
    from shapely.ops import nearest_points, polylabel

    if region is None or region.is_empty:
        return None
    if anchor not in ANCHORS:
        raise ValueError(f'anchor 只能是 {ANCHORS}，收到 {anchor!r}')
    bnd = region.boundary
    eps = 0.005                                    # 內縮圓弧用折線近似的誤差（quad_segs 16、r≤2 時 < 0.002）再保守一點
    allowed = region.buffer(-(clear + eps), quad_segs=16)
    if avoid is not None and not avoid.is_empty:
        allowed = allowed.difference(avoid.buffer(avoid_clear + eps, quad_segs=16))
    else:
        avoid = None
    if allowed.is_empty:
        return None

    def slack_of(q):
        s = float(bnd.distance(q)) - clear
        if avoid is not None:
            s = min(s, float(avoid.distance(q)) - avoid_clear)
        return s

    for size in sizes:
        best = None                                # (score, x, y, angle)
        for ia, ang in enumerate(angles):
            rel = np.array(_box_coords(text, 0.0, 0.0, size, ang, anchor))
            V = _anchor_set(allowed, rel)
            parts = [g for g in getattr(V, 'geoms', [V]) if g is not None and g.geom_type == 'Polygon' and g.area > 1e-9] \
                if V is not None and not V.is_empty else []
            if not parts:
                continue
            cx, cy = rel.mean(axis=0)
            if prefer is not None:
                p0 = Point(float(prefer[0]) - cx, float(prefer[1]) - cy)
                Vu = shapely.union_all(parts)
                if Vu.contains(p0):
                    p, dd = p0, 0.0
                else:                              # 放得下的位置裡最近的一點，再往裡面挪一點點（避開邊界上的數值誤差）
                    q = nearest_points(Vu, p0)[0]
                    host = min(parts, key=lambda g: g.distance(q))
                    r = host.representative_point()
                    v = np.array([r.x - q.x, r.y - q.y])
                    nv = float(np.hypot(*v))
                    p = Point(q.x + v[0] / nv * min(0.002, nv), q.y + v[1] / nv * min(0.002, nv)) if nv > 0 else q
                    dd = float(p.distance(p0))
                score = -dd - angle_penalty * ia
            else:                                  # 離可用範圍邊界最遠的點≈slack 最大
                cand = [polylabel(g, tolerance=0.01) for g in parts]
                sl = [slack_of(shapely.polygons(rel + [c.x, c.y])) for c in cand]
                k = int(np.argmax(sl))
                p = cand[k]
                score = sl[k] - angle_penalty * ia
            if best is None or score > best[0] + 1e-9:
                best = (score, p.x, p.y, ang)
        if best is not None:
            _, x, y, ang = best
            x, y = round(x, 4), round(y, 4)
            ink = ink_box(text, x, y, size, ang, anchor)
            sl = slack_of(ink)
            if not (region.contains(ink) and sl >= -1e-6):      # 四捨五入後再確認一次
                raise RuntimeError(f'fit_text 內部錯誤：「{text}」放好後離邊界只多 {sl:.4f}')
            return dict(text=text, x=x, y=y, size=float(size), angle=float(ang), anchor=anchor, ink=ink, slack=sl)
    return None


def _polys(d: str, step: float = 0.05):
    """d → 各輪廓的 shapely Polygon（取樣），檢查重疊與面積用。"""
    import numpy as np
    from shapely.geometry import Polygon
    from svgpathtools import parse_path
    out = []
    for sp in parse_path(d).continuous_subpaths():
        pts = []
        for seg in sp:
            n = max(2, int(math.ceil(seg.length() / step)))
            for t in np.linspace(0, 1, n, endpoint=False):
                z = seg.point(float(t))
                pts.append((z.real, z.imag))
        out.append(Polygon(pts))
    return out


@functools.lru_cache(maxsize=256)
def outline_problems(text: str) -> tuple[str, ...]:
    """線雕檢查：每個字的輪廓都封閉（終點回到起點）、不自交、輪廓之間不交叉。回傳問題說明（空＝沒問題）。

    輪廓互相交叉時，線雕會在字裡多刻出線（填色時看不出來）。"""
    from svgpathtools import parse_path
    out = []
    for ch in sorted(set(text) - {' ', '　'}):
        d = text_to_d(ch, 0.0, 0.0, 10.0)
        if not d:
            continue
        subs = parse_path(d).continuous_subpaths()
        if any(abs(sp.start - sp.end) > 1e-6 for sp in subs) or d.count('M') != d.count('Z'):
            out.append(f'「{ch}」有沒封閉的輪廓')
        ps = _polys(d, 0.02)
        if not all(p.exterior.is_simple for p in ps):
            out.append(f'「{ch}」有自交的輪廓')
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                if ps[i].exterior.intersects(ps[j].exterior):
                    out.append(f'「{ch}」第 {i + 1}、{j + 1} 個輪廓交叉（線雕會在字裡多出線）')
    return tuple(out)


# ---------------------------------------------------------------------------
# 自我測試
# ---------------------------------------------------------------------------


def _selftest() -> list[str]:
    from svgpathtools import parse_path
    errs: list[str] = []
    info = font_info()
    print(f"字型：{info['full']}（{params.FONT_PATH} #{FONT_INDEX}），unitsPerEm={info['upem']}，"
          f"大寫高={info['cap_height']}（{info['cap_height'] / info['upem']:.3f} em）")

    def chk(cond, msg):
        print(('OK  ' if cond else '!!  ') + msg)
        if not cond:
            errs.append(msg)

    size = 10.0
    cap = info['cap_height'] / info['upem'] * size
    # 1) 'S1-C'：高度≈大寫高（S、C 有 1～2% 的圓弧溢出），底在基線附近，字寬＝advance 總和
    d = text_to_d('S1-C', 0, 0, size)
    x0, y0, x1, y1 = _bbox(d)
    adv = text_advance('S1-C', size)
    chk(abs((y1 - y0) - cap) < 0.04 * cap, f"'S1-C' 高 {y1 - y0:.3f}（大寫高 {cap:.3f}）")
    chk(-0.3 < y1 < 0.3 and abs(y0 + cap) < 0.3, f"'S1-C' 底 y={y1:.3f}、頂 y={y0:.3f}（基線 0）")
    chk(0 <= x0 < 0.15 * size and adv - 0.15 * size < x1 <= adv, f"'S1-C' x {x0:.3f}～{x1:.3f}，advance {adv:.3f}")
    chk(d.count('M') == 4 and d.count('Z') == 4, f"'S1-C' 4 個封閉輪廓（M={d.count('M')}、Z={d.count('Z')}）")
    # 2) '電子盒'：三個全形字，advance＝3 em；字身在 em 方框內
    d = text_to_d('電子盒', 0, 0, size)
    x0, y0, x1, y1 = _bbox(d)
    adv = text_advance('電子盒', size)
    chk(abs(adv - 3 * size) < 1e-9, f"'電子盒' advance {adv:.3f}（3 em＝{3 * size}）")
    chk(0 <= x0 < 0.1 * size and 2.9 * size < x1 <= 3 * size, f"'電子盒' x {x0:.3f}～{x1:.3f}")
    chk(-0.95 * size < y0 < -0.75 * size and 0 < y1 < 0.15 * size, f"'電子盒' y {y0:.3f}～{y1:.3f}")
    # 3) '50'：數字高≈大寫高；'0' 有字腔（2 個輪廓，方向相反）
    d = text_to_d('50', 0, 0, size)
    x0, y0, x1, y1 = _bbox(d)
    chk(abs((y1 - y0) - cap) < 0.05 * cap, f"'50' 高 {y1 - y0:.3f}（大寫高 {cap:.3f}）")
    sub = parse_path(d).continuous_subpaths()
    chk(len(sub) == 3, f"'50' 輪廓數 {len(sub)}（5 一個、0 外框＋字腔）")
    ps = _polys(text_to_d('0', 0, 0, size))
    chk(len(ps) == 2 and ps[0].exterior.is_ccw != ps[1].exterior.is_ccw, "'0' 外框與字腔方向相反（nonzero 正確挖空）")
    # 4) 各字沒有互相重疊的輪廓：evenodd 面積＝nonzero 面積
    for t in ('S1-C', '電子盒', '50', '鎖塊蓋板導流帽', '×'):
        ps = _polys(text_to_d(t, 0, 0, size))
        xor = ps[0]
        for q in ps[1:]:
            xor = xor.symmetric_difference(q)
        signed = abs(sum(q.area * (1 if q.exterior.is_ccw else -1) for q in ps))
        chk(abs(xor.area - signed) < 1e-6 * max(signed, 1), f"'{t}' evenodd 面積 {xor.area:.3f}＝nonzero {signed:.3f}")
    # 5) anchor：middle、end 正好平移 -W/2、-W
    for t in ('S1-C', '電子盒'):
        W = text_advance(t, 6)
        b0 = _bbox(text_to_d(t, 30, 40, 6, anchor='start'))
        bm = _bbox(text_to_d(t, 30, 40, 6, anchor='middle'))
        be = _bbox(text_to_d(t, 30, 40, 6, anchor='end'))
        chk(all(abs((bm[i] - b0[i]) - (-W / 2 if i % 2 == 0 else 0)) < 2e-4 for i in range(4)),
            f"'{t}' anchor=middle：bbox 平移 {bm[0] - b0[0]:.4f}（-W/2＝{-W / 2:.4f}）")
        chk(all(abs((be[i] - b0[i]) - (-W if i % 2 == 0 else 0)) < 2e-4 for i in range(4)),
            f"'{t}' anchor=end：bbox 平移 {be[0] - b0[0]:.4f}（-W＝{-W:.4f}）")
        chk(be[2] <= 30 + 1e-9 and bm[0] < 30 < bm[2], f"'{t}' end 右緣 {be[2]:.3f} ≤ 錨點 30；middle 跨過錨點")
    # 6) angle=90：每個點都是 angle=0 的點繞錨點順時針轉 90°（(u,v) → (-v,u)）
    x, y = 100.0, 50.0
    p0 = parse_path(text_to_d('S1-C', x, y, 5))
    p9 = parse_path(text_to_d('S1-C', x, y, 5, angle=90))
    dev = 0.0
    for s0, s9 in zip(p0, p9):
        for t in (0, 0.5, 1):
            a, b = s0.point(t), s9.point(t)
            u, v = a.real - x, a.imag - y
            dev = max(dev, abs(complex(x - v, y + u) - b))
    chk(len(p0) == len(p9) and dev < 2e-4, f"angle=90 與 angle=0 旋轉後的最大差 {dev:.2e} mm")
    b9 = _bbox(text_to_d('S1-C', x, y, 5, angle=90))
    chk(b9[1] >= y - 0.2 and b9[2] > x and b9[0] > x - 0.3, f"angle=90：字往下排（y {b9[1]:.2f}～{b9[3]:.2f}）、字頭朝右（x {b9[0]:.2f}～{b9[2]:.2f}）")
    b27 = _bbox(text_to_d('S1-C', x, y, 5, angle=-90))
    chk(b27[3] <= y + 0.2 and b27[0] < x, f"angle=-90：字往上排（y {b27[1]:.2f}～{b27[3]:.2f}）、字頭朝左")
    # 7) 缺字要 raise
    for bad in ('\U0001F600', 'A\u0378B'):
        try:
            text_to_d(bad, 0, 0, 3)
            chk(False, f'缺字 {bad!r} 應該 raise')
        except ValueError as e:
            chk('沒有這些字' in str(e), f'缺字 raise：{e}')
    # 8) 其他常用符號都有
    d = text_to_d('S5 S10 S50 P1 C1 #13R ×2 EB-1 （）', 0, 0, 3)
    chk(len(d) > 0, '常用符號（空白、#、×、全形括號）都有字形')
    # 9) 輸出沒有 NaN、全部封閉
    chk('nan' not in d.lower() and d.count('M') == d.count('Z'), '輸出沒有 NaN，每個輪廓都封閉')
    # 10) 線雕（外框線字）：中空字的外框與內框都在，每個輪廓都封閉（終點回到起點）
    for ch, n_exp in (('口', 2), ('回', 4), ('8', 3), ('0', 2), ('B', 3), ('P', 2)):
        dd = text_to_d(ch, 0, 0, size)
        sub = parse_path(dd).continuous_subpaths()
        ps = _polys(dd)
        areas = sorted((q.area for q in ps), reverse=True)
        nested = all(ps[0].buffer(1e-6).contains(q) for q in ps[1:]) if ch in '口0P' else True
        chk(len(sub) == n_exp and all(abs(sp.start - sp.end) < 1e-6 for sp in sub) and dd.count('Z') == n_exp and nested,
            f"線雕「{ch}」：{len(sub)} 個封閉輪廓（預期 {n_exp}：外框＋字腔），面積 {[round(a, 1) for a in areas]}")
    # 11) v2 用到的字：輪廓不自交、彼此不交叉（線雕時字裡不會多出線）
    used = ('S5 v2 S10 v2 S50 v2 S1-B S1-C 前→ S1 ↑ S1-F S1-P 13R 右 S1 卡匣 21 左 感測器線 '
            'EB-WL 左牆 EB-WR USB 側 EB-B EB-T EB-S EB-F EB-E EB-K 口回80 #×（）')
    probs = outline_problems(used)
    chk(not probs, f'v2 用到的 {len(set(used) - {" "})} 個字線雕都沒問題' + (f'：{probs}' if probs else ''))
    # 12) ink_bounds／ink_box：等於 text_to_d 的 bbox；轉 90° 的外框＝轉過的矩形
    b = ink_bounds('S1-P', 3, 0, 'middle', 10, 20)
    q = ink_box('S1-P', 10, 20, 3, 0, 'middle').bounds
    chk(all(abs(b[i] - q[i]) < 1e-9 for i in range(4)) and abs(b[3] - 20) < 0.1, f"ink_box＝ink_bounds（'S1-P' {[round(v, 3) for v in b]}）")
    q9 = ink_box('S1-P', 10, 20, 3, 90, 'middle').bounds
    b9 = ink_bounds('S1-P', 3, 90, 'middle', 10, 20)
    chk(all(abs(b9[i] - q9[i]) < 1e-6 for i in range(4)), "angle=90 的 ink_box 外包＝實際字墨外包")
    # 13) fit_text：離邊界 ≥ clear、離 avoid ≥ avoid_clear；放不下回 None；prefer 放得下就用
    from shapely.geometry import LineString, Point, box as _box
    reg = _box(0, 0, 9.9, 4.4)
    f = fit_text(reg, 'S1-P', [3.0, 2.5])
    chk(f is not None and reg.exterior.distance(f['ink']) >= TEXT_CLEAR - 1e-9 and f['slack'] >= -1e-9,
        f"fit_text 9.9×4.4 放「S1-P」：em {f and f['size']}，離邊 {f and reg.exterior.distance(f['ink']):.3f}")
    chk(fit_text(reg, 'S1-P', [4.0]) is None, 'fit_text 放不下（em 4 的字墨比 2.4 高）回 None')
    reg2 = _box(0, 0, 30, 12).difference(Point(8, 6).buffer(2))
    av = LineString([(15, 0), (15, 12)])
    f2 = fit_text(reg2, 'S50', [3.0], avoid=av, angles=(0.0, 90.0))
    ok2 = f2 is not None and reg2.boundary.distance(f2['ink']) >= TEXT_CLEAR - 1e-9 and av.distance(f2['ink']) >= ENGRAVE_GAP - 1e-9
    chk(ok2, f"fit_text 避開孔與雕刻線：離切割 {f2 and reg2.boundary.distance(f2['ink']):.3f}、離線 {f2 and av.distance(f2['ink']):.3f}")
    f3 = fit_text(reg2, 'S50', [3.0], prefer=(22.0, 6.0))
    c3 = f3['ink'].centroid
    chk(abs(c3.x - 22) < 1e-3 and abs(c3.y - 6) < 1e-3, f'fit_text prefer 放得下就用（中心 {c3.x:.3f}, {c3.y:.3f}）')
    chk(set(text_spec(f3)) == {'text', 'x', 'y', 'size', 'angle', 'anchor'}, 'text_spec 只留 6 個鍵')
    strip = _box(0, 0, 3.7, 20)          # 窄條：扣掉兩邊各 1.0 只剩 1.7，em 2.1 直排的「S5」字墨寬 1.64
    f4 = fit_text(strip, 'S5', [2.1], angles=(0.0, -90.0))
    chk(f4 is not None and f4['angle'] == -90.0 and strip.exterior.distance(f4['ink']) >= TEXT_CLEAR - 1e-9,
        f"fit_text 剛好擠得進窄條（精確找位置，不是格點）：{f4 and (f4['angle'], round(strip.exterior.distance(f4['ink']), 3))}")
    return errs


if __name__ == '__main__':
    import sys
    e = _selftest()
    print(f'\ntextpath 自我測試：{"全部通過" if not e else f"{len(e)} 項失敗"}')
    sys.exit(1 if e else 0)

"""雕刻文字轉路徑：把一行文字用字型的輪廓轉成 SVG path d（v2 產生器用，輸出裡不留 <text>）。

用法
----
    from laser_v2.textpath import text_to_d
    d = text_to_d('S1-C', x=10, y=20, size=4)                    # 基線左端在 (10, 20)
    d = text_to_d('電子盒', 50, 30, 5, angle=90, anchor='middle')  # 以 (50, 30) 為中心、轉 90°

    compose.py 會把 d 包成 <path d="…" style="fill:#ff0000;stroke:none"/>（雕刻、填色）。

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
* 輸出全部是封閉輪廓（每個輪廓以 Z 結尾），外框與字腔方向相反；已檢查常用字沒有互相
  重疊的輪廓，所以 nonzero 與 evenodd 填色結果相同（見自我測試）。

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
# 自我測試
# ---------------------------------------------------------------------------
def _bbox(d: str):
    from svgpathtools import parse_path
    x0, x1, y0, y1 = parse_path(d).bbox()
    return x0, y0, x1, y1


def _polys(d: str, step: float = 0.05):
    """d → 各輪廓的 shapely Polygon（取樣），給測試檢查重疊與面積。"""
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
    return errs


if __name__ == '__main__':
    import sys
    e = _selftest()
    print(f'\ntextpath 自我測試：{"全部通過" if not e else f"{len(e)} 項失敗"}')
    sys.exit(1 if e else 0)

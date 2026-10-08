# -*- coding: utf-8 -*-
"""光耦簡易測試原型：雷切檔、預覽、示意圖、零件表產生器（自給自足，不 import laser_v2）。

用途
----
一段直滑坡（傾斜和正式機一樣）＋一個槽型光耦模組的安裝位置，雷切後自己裝模組，
驗證「槽型光耦跨裝在滑坡上（兩臂跨住擋幣板＋背牆，共 6 mm）是否可行」。

執行（在 repo 根目錄）
--------------------
    .venv/Scripts/python.exe -B 光耦測試原型/make_proto.py

輸出（都在本檔同一個資料夾）
    光耦測試原型_雷切.svg   單頁、單位 mm；圖層「切割」（黑 0.2）、「雕刻」（紅 0.2，線／向量雕刻）
    預覽.png                整張板：切割黑、雕刻紅、零件代號藍（藍字只在預覽圖，不在 SVG）
    示意圖.png              ①滑坡正視 ②感測處沿光束剖面 ③側視（30° 後仰與支撐）
    零件表.csv              代號、名稱、數量、尺寸、用途（UTF-8 BOM，Excel 可直接開）
最後印出自我檢查，每項 PASS／FAIL。

收到模組實量後：只改下面「模組（暫定）」MODULE 的數字（必要時改窗、墊片參數）再執行一次，
窗、光孔、墊片高度、示意圖會一起更新。

座標約定（全部 mm）
------------------
背牆平面內 (X, Y)：從正面看，X 往右、Y 沿背牆往上（Y＝0 是背牆下緣）。硬幣從左上往右下滾。
站座標 (s, n, w)：原點＝光束正下方的軌道點（擋幣板上緣、背牆正面）。
    s 沿軌道往下游；n 在背牆平面內垂直軌道往上；w 垂直背牆往背後（w＝0 背牆正面、w＝3 背牆背面，
    擋幣板在 w −3～0，硬幣立著靠在背牆正面，佔 w −t～0）。
    (X, Y) ＝ O ＋ s·(cos20°, −sin20°) ＋ n·(sin20°, cos20°)
世界側視 (y, z)：y 往背後、z 往上，z＝0 是桌面；底板頂面 z＝3；背牆背面下緣在 (y, z)＝(0, 3)。
重力在站座標＝(+0.296, −0.814, +0.500) g（沿軌往下、往下、往背後）。
"""
import csv
import math
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))

# =============================================================================
# 參數（收到模組實量後改這裡）
# =============================================================================
# ---- 模組（暫定，全部待實量；數值同正式機 v2 的 MODULE，但這裡是獨立一份，v2 以後改了不影響原型）----
# 「沿光束」＝兩臂之間的方向（w）；「寬」＝沿軌道（s）。
MODULE = dict(
    slot_w=10.0,    # 槽寬：兩臂內面距（w）
    slot_d=9.0,     # 槽深：臂頂到槽底
    beam_sb=5.0,    # 光束中心離槽底
    arm_t=7.0,      # 單臂沿光束厚（w）
    arm_w=6.4,      # 臂寬＝光耦本體寬（s）
    arm_top=12.0,   # 臂頂離 PCB 元件面
    pcb_L=27.6,     # PCB 沿光束長（w）
    pcb_W=20.0,     # PCB 寬（s）
    pcb_t=1.6,      # PCB 厚
    body_e=0.5,     # 光耦本體側邊到 PCB 長邊的距離（本體靠 PCB 一邊）
    wing='up',      # 本體靠 PCB 哪一邊：'up'＝PCB 往上游伸（本體靠下游邊）／'down'／'center'
    comp_h=2.0,     # PCB 元件面最高零件
    back_h=2.0,     # PCB 背面焊點凸出
    hdr_up=14.0,    # 直立排針＋杜邦頭高（從 PCB 元件面量）
    hdr_len=8.0,    # 排針＋杜邦頭沿光束方向佔的長度（在 PCB 背面那一端）
    aperture=1.0,   # 光耦收發窗高（估計）
)

# ---- 板材、雷切 ----
T_PLY = 3.0             # 合板厚
C_TAB = 0.1             # 榫槽單邊餘隙
TAB_RECESS = 0.2        # 榫頭比對方板厚短的量（不凸出正面／桌面）
PART_GAP = 2.0          # 零件間距
SHEET_MARGIN = 2.0      # 零件離板邊
SHEET_MAX = (255.0, 355.0)
STROKE_CUT = 'fill:none;stroke:#000000;stroke-width:0.2'
STROKE_ENGRAVE = 'fill:none;stroke:#ff0000;stroke-width:0.2'
FONT_PATH = r'C:\Windows\Fonts\msjh.ttc'
TEXT_EM_CJK = 5.0       # 中文字 em 高（外框線字）
TEXT_EM_NUM = 4.5       # 數字、英文 em 高
TEXT_CLEAR = 1.0        # 字墨離切割線
LINE_CLEAR = 1.0        # 雕刻線離切割線

# ---- 滑坡 ----
TILT_DEG = 30.0         # 背牆後仰（離鉛直）
TRACK_DEG = 20.0        # 軌道在背牆平面內的斜度
S_START = -112.0        # 軌道（擋幣板）起點，相對光束（約 110 mm）
S_END = 45.0            # 軌道終點：感測處之後 45 mm（≥40），硬幣從這裡滾出落下
RELEASE = (('S5', 36.0), ('S10', 70.0), ('S50', 106.0))   # 放幣線離光束（硬幣中心對線）
TRACK_END_Z = 60.0      # 軌道出口（擋幣板上緣末端）離桌面高（決定整片背牆的高度）
WALL_TOP_N = 34.0       # 背牆上緣在軌道上方（垂直軌道量；50 元高 28）
WALL_EXT = 3.0          # 背牆左端比擋幣板／50 元硬幣再多出的量
STRIP_BAR = 2.3         # 軌道條：窗頂到軌道（兩片疊起來共 6 mm 厚）
STRIP_H = 30.0          # 擋幣板高（垂直軌道）

# ---- 感測窗（兩片同形） ----
PCB_W_MAX = 24.0        # 窗要放得下的 PCB 最大寬（沿軌道）
C_WIN = 0.4             # 窗兩側單邊餘隙 → 窗寬 24.8
C_SLIDE = 1.0           # 低位時臂頂離軌道條下緣（至少）
WIN_EXTRA_H = 2.0       # 模組總高未知，窗再加高
C_WIN_V = 0.4           # 低位時窗底多留
SHIM_STEP = 0.5         # 墊片每片差
SHIM_DOWN = 3.0         # 比「模組頂到軌道條」那片再低 3 mm
SHIM_UP = 1.0           # 再高 1 mm（模組比暫定小時用）

# ---- 墊片（L 形，板面垂直軌道） ----
SHIM_EAR_W = 5.0        # 擋耳寬（w，在擋幣板前方）
SHIM_EAR_DROP = 5.0     # 擋耳往窗底下方伸（靠在擋幣板正面）
SHIM_BACK_W = 12.0      # 墊片後端（w，伸到背牆後方撐 PCB）

# ---- 光孔（背牆） ----
LH_W = 1.8              # 沿軌道寬
LH_N_BOT = 0.2          # 下緣離軌道（光束再低就被擋幣板上緣擋住）
BEAM_SB_TOL = 1.5       # 光孔往上多涵蓋：光束離槽底的實品誤差
LH_WINGS = ('up', 'center', 'down')   # 為三種本體位置各開一個光孔（實量後可只留一個）

# ---- 支撐（2 片，在兩端） ----
SUP_INSET = 12.0        # 支撐中心離背牆左右端
SUP_HB = 60.0           # 支撐斜邊頂端在背牆上的高（背牆平面內 Y）
SUP_Y0 = 3.0            # 支撐前緣離背牆背面下緣（截掉尖角）
SUP_WALL_TAB_LO = (10.0, 20.0)   # 插背牆的下榫：沿斜邊 Y 範圍（上榫自動放在擋幣板下緣下方，見 SUP_WALL_TABS）
SUP_BASE_TABS = ((8.0, 14.0), (20.0, 26.0))    # 插底板的榫：y 範圍
FOOT_TABS = (0.30, 0.70)   # 背牆下緣插底板的榫中心（佔背牆長的比例）
FOOT_TAB_W = 12.0
FOOT_TAB_L = 3.2        # 沿背牆往下伸（30° 斜插，最低點仍在桌面上方）
BASE_FRONT = 6.0        # 底板在斜槽前方多留
BASE_BACK = 35.0        # 底板在支撐後方多留：背牆後仰，軌道上段的硬幣、模組都在支撐後方，底板要夠深才不會往後翻
# 防後翻檢查用（自我檢查「整台不會往後翻」）
PLY_RHO = 0.45          # 合板密度 g/cm³（取偏輕的值，比較保守）
COIN_G = {'1 元': 3.8, '5 元': 4.4, '10 元': 7.5, '50 元': 10.0}   # 硬幣重 g
MODULE_G = 6.0          # 模組＋杜邦頭估計重 g
TIP_MIN = 10.0          # 合成重心離底板前後緣至少（mm）

# ---- 硬幣（直徑、厚） ----
COINS = (('1 元', 20.0, 1.57), ('5 元', 22.0, 1.49), ('10 元', 26.0, 1.63), ('50 元', 28.0, 2.40))

OUT_SVG = os.path.join(HERE, '光耦測試原型_雷切.svg')
OUT_PREVIEW = os.path.join(HERE, '預覽.png')
OUT_FIG = os.path.join(HERE, '示意圖.png')
OUT_CSV = os.path.join(HERE, '零件表.csv')

# =============================================================================
# 推導量
# =============================================================================
M = MODULE
TR = math.radians(TRACK_DEG)
TL = math.radians(TILT_DEG)
TVEC = (math.cos(TR), -math.sin(TR))     # 沿軌往下游（X, Y）
NVEC = (math.sin(TR), math.cos(TR))      # 垂直軌道往上（X, Y）
SB_TO_LOW = (M['arm_top'] - M['slot_d']) + M['pcb_t'] + M['back_h']   # 槽底到模組最低點（焊點）
STACK = M['back_h'] + M['pcb_t'] + M['arm_top']                        # 焊點到臂頂
PCB_OVH = (M['pcb_L'] - 2 * M['arm_t'] - M['slot_w']) / 2.0            # PCB 超出臂外面
N_STRIP = -STRIP_BAR                                                     # 軌道條下緣＝窗頂
_n_wb_raw = N_STRIP - C_SLIDE - (STACK + WIN_EXTRA_H) - C_WIN_V
_H0_raw = N_STRIP - SB_TO_LOW - _n_wb_raw
H0 = math.ceil(round(_H0_raw / SHIM_STEP, 6)) * SHIM_STEP   # 「模組頂到軌道條」的墊片高（取 0.5 的倍數）
N_WB = N_STRIP - SB_TO_LOW - H0                               # 窗底
WIN_H = N_STRIP - N_WB
WIN_W = PCB_W_MAX + 2 * C_WIN
BEAM_TOP = N_STRIP + M['beam_sb']                             # 模組頂到軌道條時的光束高


def body_offset(wing):
    """PCB 下游邊（推到窗的下游邊）到本體中心（＝光束）的距離。"""
    if wing == 'up':
        return M['body_e'] + M['arm_w'] / 2
    if wing == 'down':
        return M['pcb_W'] - M['body_e'] - M['arm_w'] / 2
    return M['pcb_W'] / 2


S_DN = body_offset(M['wing'])          # 窗下游邊（光束 s＝0 對應設定的 wing）
WIN_S0, WIN_S1 = S_DN - WIN_W, S_DN
LH_S = [(wg, S_DN - body_offset(wg)) for wg in LH_WINGS]
LH_N_TOP = BEAM_TOP + BEAM_SB_TOL + M['aperture'] / 2
SHIMS = [round(H0 + k * SHIM_STEP, 3)
         for k in range(-int(round(SHIM_DOWN / SHIM_STEP)), int(round(SHIM_UP / SHIM_STEP)) + 1)]

# 背牆平面：原點 O 的 (X, Y)；X_O＝0
_z_front0 = 3.0 + T_PLY * math.sin(TL)          # 背牆正面下緣的 z（＝4.5）
Y_END = (TRACK_END_Z - _z_front0) / math.cos(TL)
X_O = 0.0
Y_O = Y_END - S_END * TVEC[1]                   # TVEC[1] < 0
R_MAX = max(c[1] for c in COINS) / 2


def st2xy(s, n):
    return (X_O + s * TVEC[0] + n * NVEC[0], Y_O + s * TVEC[1] + n * NVEC[1])


def xy2st(X, Y):
    dx, dy = X - X_O, Y - Y_O
    return (dx * TVEC[0] + dy * TVEC[1], dx * NVEC[0] + dy * NVEC[1])


def st_poly(coords):
    return Polygon([st2xy(s, n) for s, n in coords])


def st_rect(s0, s1, n0, n1):
    return st_poly([(s0, n0), (s1, n0), (s1, n1), (s0, n1)])


X_R = st2xy(S_END, 0.0)[0]                       # 背牆右端＝軌道出口
_x_strip_left = st2xy(S_START, -STRIP_H)[0]
_s50 = dict(RELEASE)['S50']
_x_coin_left = st2xy(-_s50, R_MAX)[0] - R_MAX
X_L = min(_x_strip_left, _x_coin_left) - WALL_EXT


def y_track(X):
    return Y_O - (X - X_O) * math.tan(TR)


def y_walltop(X):
    return y_track(X) + WALL_TOP_N / math.cos(TR)


def world_of(Y, w):
    """背牆平面內高度 Y、深度 w 的點 → 世界 (y, z)。"""
    yf = Y * math.sin(TL) - T_PLY * math.cos(TL)
    zf = _z_front0 + Y * math.cos(TL)
    return (yf + w * math.cos(TL), zf - w * math.sin(TL))


SUP_X = (X_L + SUP_INSET, X_R - SUP_INSET)
# 上榫：頂端在「支撐處擋幣板下緣」下方 2.5（背牆上雕的擋幣板對位線不碰到槽），最多到斜邊頂下 4
_strip_bot_at_sup = min(y_track(x) for xs in SUP_X for x in (xs - 2, xs + 2)) - STRIP_H / math.cos(TR)
_hi_top = min(SUP_HB - 4.0, _strip_bot_at_sup - 2.5)
SUP_WALL_TABS = (SUP_WALL_TAB_LO, (_hi_top - 8.0, _hi_top))

# =============================================================================
# 雕刻文字：用 fontTools 把字型輪廓轉成線（外框線字），輸出裡不留 <text>
# =============================================================================
_FONT = None


def _font():
    global _FONT
    if _FONT is None:
        from fontTools.ttLib import TTCollection
        f = TTCollection(FONT_PATH).fonts[0]       # 微軟正黑體 Regular
        _FONT = (f.getGlyphSet(), f.getBestCmap(), f['hmtx'], f['head'].unitsPerEm)
    return _FONT


def _contours_of_glyph(gname):
    from fontTools.pens.basePen import BasePen

    class _Pen(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.contours, self.cur = [], None

        def _moveTo(self, p):
            self.cur = [('M', p)]

        def _lineTo(self, p):
            self.cur.append(('L', p))

        def _qCurveToOne(self, c, p):
            self.cur.append(('Q', c, p))

        def _curveToOne(self, a, b, p):
            self.cur.append(('C', a, b, p))

        def _closePath(self):
            if self.cur and len(self.cur) > 1:
                self.contours.append(self.cur)
            self.cur = None

        _endPath = _closePath

    gs = _font()[0]
    pen = _Pen(gs)
    gs[gname].draw(pen)
    return pen.contours


def flatten_contour(c, nq=8):
    """一個輪廓 → 封閉折線點列（不重複起點）。"""
    pts, last = [], None
    for seg in c:
        if seg[0] in ('M', 'L'):
            pts.append(seg[1])
        elif seg[0] == 'Q':
            p0, cc, p1 = last, seg[1], seg[2]
            for i in range(1, nq + 1):
                t = i / nq
                pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * cc[0] + t * t * p1[0],
                            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * cc[1] + t * t * p1[1]))
        elif seg[0] == 'C':
            p0, a, b, p1 = last, seg[1], seg[2], seg[3]
            for i in range(1, nq + 1):
                t = i / nq
                pts.append(tuple((1 - t) ** 3 * p0[k] + 3 * (1 - t) ** 2 * t * a[k] + 3 * (1 - t) * t * t * b[k]
                                 + t ** 3 * p1[k] for k in range(2)))
        last = seg[-1]
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-9:
        pts.pop()
    return pts


def make_text(s, em, cx, cy, angle=0.0):
    """一行字，字墨外包框中心放在 (cx, cy)（零件自然座標，y 往上），逆時針轉 angle 度。"""
    gs, cmap, hmtx, upm = _font()
    k = em / upm
    x, raw = 0.0, []
    for ch in s:
        if ord(ch) not in cmap:
            raise ValueError(f'字型沒有「{ch}」')
        g = cmap[ord(ch)]
        for c in _contours_of_glyph(g):
            raw.append([(seg[0],) + tuple((x + p[0] * k, p[1] * k) for p in seg[1:]) for seg in c])
        x += hmtx[g][0] * k
    allp = [p for c in raw for p in flatten_contour(c)]
    x0, x1 = min(p[0] for p in allp), max(p[0] for p in allp)
    y0, y1 = min(p[1] for p in allp), max(p[1] for p in allp)
    ox, oy = (x0 + x1) / 2, (y0 + y1) / 2
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def tf(p):
        px, py = p[0] - ox, p[1] - oy
        return (cx + px * ca - py * sa, cy + px * sa + py * ca)

    contours = [[(seg[0],) + tuple(tf(p) for p in seg[1:]) for seg in c] for c in raw]
    ink = Polygon([tf(p) for p in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]])
    return dict(text=s, em=em, contours=contours, ink=ink, size=(x1 - x0, y1 - y0))


# =============================================================================
# 零件（每個零件用自己的「自然座標」：y 往上；排版時才翻成 SVG 的 y 往下）
# =============================================================================
class Part:
    def __init__(self, code, name, qty_note=''):
        self.code, self.name, self.qty_note = code, name, qty_note
        self.outline = None      # Polygon（只有外框）
        self.holes = []          # [(名稱, Polygon)]
        self.lines = []          # 雕刻直線 [LineString]
        self.texts = []          # make_text() 的結果
        self.size_note = ''
        self.use = ''

    def solid(self):
        sol = Polygon(self.outline.exterior)
        for _, h in self.holes:
            sol = sol.difference(h)
        return sol

    def hole(self, name):
        return [h for nm, h in self.holes if nm == name]


def _outline_of(geom):
    if isinstance(geom, MultiPolygon):
        raise ValueError('外框不是一塊')
    return Polygon(geom.exterior)


def _rect(x0, y0, x1, y1):
    return box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


# ---- 背牆下緣榫（30° 斜插底板）：側視 (y, z) ----
def foot_tab_side():
    return Polygon([world_of(0.0, T_PLY), world_of(0.0, 0.0), world_of(-FOOT_TAB_L, 0.0), world_of(-FOOT_TAB_L, T_PLY)])


_ft = foot_tab_side()
FOOT_SLOT_Y = (_ft.bounds[0] - C_TAB, _ft.bounds[2] + C_TAB)    # 底板斜插槽 y 範圍（含餘隙）
FOOT_X = [X_L + f * (X_R - X_L) for f in FOOT_TABS]


def sup_hyp_point(a):
    """支撐斜邊（＝背牆背面）上，背牆平面高 a 的點 → 側視 (y, z)。"""
    return world_of(a, T_PLY)


def sup_tab_side(a0, a1):
    dep = T_PLY - TAB_RECESS
    nb = (math.cos(TL), -math.sin(TL))
    p0, p1 = sup_hyp_point(a0), sup_hyp_point(a1)
    ov = 0.05    # 往支撐本體內多畫一點，聯集時不留浮點縫（外露的榫形不變）
    q0, q1 = (p0[0] + ov * nb[0], p0[1] + ov * nb[1]), (p1[0] + ov * nb[0], p1[1] + ov * nb[1])
    return Polygon([q0, q1, (p1[0] - dep * nb[0], p1[1] - dep * nb[1]), (p0[0] - dep * nb[0], p0[1] - dep * nb[1])])


def build_parts():
    parts = {}
    # ---------------- B 背牆 ----------------
    B = Part('B', '背牆')
    body = Polygon([(X_L, 0), (X_R, 0), (X_R, y_walltop(X_R)), (X_L, y_walltop(X_L))])
    for xt in FOOT_X:
        body = body.union(_rect(xt - FOOT_TAB_W / 2, -FOOT_TAB_L, xt + FOOT_TAB_W / 2, 0.0))
    B.outline = _outline_of(body)
    B.holes.append(('窗', st_rect(WIN_S0, WIN_S1, N_WB, N_STRIP)))
    for wg, sb in LH_S:
        B.holes.append(('光孔', st_rect(sb - LH_W / 2, sb + LH_W / 2, LH_N_BOT, LH_N_TOP)))
    for xs in SUP_X:
        for a0, a1 in SUP_WALL_TABS:
            B.holes.append(('支撐槽', _rect(xs - T_PLY / 2 - C_TAB, a0 - C_TAB, xs + T_PLY / 2 + C_TAB, a1 + C_TAB)))
    # 雕刻：放幣線＋標籤、光孔標籤、擋幣板對位線、代號
    for name, d in RELEASE:
        B.lines.append(LineString([st2xy(-d, 1.5), st2xy(-d, 26.0)]))
        B.texts.append(make_text(name, TEXT_EM_NUM, *st2xy(-d, 29.6), angle=-TRACK_DEG))
    s_mid = sum(sb for _, sb in LH_S) / len(LH_S)
    B.texts.append(make_text('光孔', TEXT_EM_CJK, *st2xy(s_mid, LH_N_TOP + 5.0), angle=-TRACK_DEG))
    B.lines.append(LineString([st2xy(S_START, -STRIP_H), st2xy(S_END, -STRIP_H)]))
    B.lines.append(LineString([st2xy(S_START, -STRIP_H), st2xy(S_START, -4.0)]))
    B.lines.append(LineString([st2xy(S_END, -STRIP_H), st2xy(S_END, -4.0)]))
    B.texts.append(make_text('B 背牆（正面）', TEXT_EM_CJK, (X_L + X_R) / 2, 9.0))
    B.texts.append(make_text('↑ 擋幣板 D 下緣對齊這條線', TEXT_EM_CJK, *st2xy(-62.0, -STRIP_H - 4.5), angle=-TRACK_DEG))
    parts['B'] = B

    # ---------------- D 擋幣板（自然座標＝站座標 (s, n)，從正面看） ----------------
    D = Part('D', '擋幣板')
    D.outline = _rect(S_START, -STRIP_H, S_END, 0.0)
    D.holes.append(('窗', _rect(WIN_S0, N_WB, WIN_S1, N_STRIP)))
    D.texts.append(make_text('D 擋幣板（正面）', TEXT_EM_CJK, -62.0, -15.0))
    D.texts.append(make_text('上緣＝軌道', TEXT_EM_CJK, (WIN_S1 + S_END) / 2 + 2.0, -15.0))
    parts['D'] = D

    # ---------------- C 支撐（側視 (y, z)） ----------------
    C = Part('C', '支撐', '2 片同形')
    yB, zB = sup_hyp_point(SUP_HB)
    z4 = sup_hyp_point(SUP_Y0 / math.sin(TL))[1]
    body = Polygon([(SUP_Y0, 3.0), (yB, 3.0), (yB, zB), (SUP_Y0, z4)])
    for a0, a1 in SUP_WALL_TABS:
        body = body.union(sup_tab_side(a0, a1))
    for y0, y1 in SUP_BASE_TABS:
        body = body.union(_rect(y0, 3.0 - (T_PLY - TAB_RECESS), y1, 3.0))
    C.outline = _outline_of(body)
    C.texts.append(make_text('C 支撐', TEXT_EM_CJK, (SUP_Y0 + yB) / 2 + 4.0, 9.5))
    parts['C'] = C

    # ---------------- A 底板（俯視 (x, y)，y 往背後） ----------------
    A = Part('A', '底板')
    y_front = FOOT_SLOT_Y[0] - BASE_FRONT
    y_back = yB + BASE_BACK
    A.outline = _rect(X_L, y_front, X_R, y_back)
    for xt in FOOT_X:
        A.holes.append(('斜插槽', _rect(xt - FOOT_TAB_W / 2 - C_TAB, FOOT_SLOT_Y[0], xt + FOOT_TAB_W / 2 + C_TAB, FOOT_SLOT_Y[1])))
    for xs in SUP_X:
        for y0, y1 in SUP_BASE_TABS:
            A.holes.append(('支撐槽', _rect(xs - T_PLY / 2 - C_TAB, y0 - C_TAB, xs + T_PLY / 2 + C_TAB, y1 + C_TAB)))
    A.texts.append(make_text('A 底板（這面朝上）', TEXT_EM_CJK, (X_L + X_R) / 2, (y_front + y_back) / 2 + 6.0))
    A.texts.append(make_text('↓ 前側（滑坡正面）', TEXT_EM_CJK, (X_L + X_R) / 2, y_front + 6.5))
    parts['A'] = A

    # ---------------- E 墊片（剖面 (w, n)） ----------------
    for i, H in enumerate(SHIMS):
        E = Part(f'E{i + 1}', f'墊片 {H:.1f}')
        E.outline = shim_poly(H)
        # 代號＋高度，例如「E7  12.5」（E7＝零件代號、12.5＝撐高）
        tx = make_text(f'E{i + 1}  {H:.1f}', TEXT_EM_NUM, (-T_PLY - SHIM_EAR_W + SHIM_BACK_W) / 2, N_WB + H / 2 + 0.6)
        E.texts.append(tx)
        x0, y0, x1, _ = tx['ink'].bounds
        E.lines.append(LineString([(x0, y0 - 0.9), (x1, y0 - 0.9)]))   # 底線：分辨 6／9，也表示這邊朝下
        E.height = H
        parts[E.code] = E

    # ---------------- F 對位塞 ----------------
    F = Part('F', '對位塞')
    F.outline = _rect(0, 0, WIN_W - 2 * C_TAB, WIN_H - 2 * C_TAB)
    F.texts.append(make_text('F 對位塞', TEXT_EM_CJK, (WIN_W - 2 * C_TAB) / 2, (WIN_H - 2 * C_TAB) / 2))
    parts['F'] = F
    return parts


def shim_poly(H):
    wf = -T_PLY - SHIM_EAR_W
    return Polygon([(wf, N_WB - SHIM_EAR_DROP), (-T_PLY, N_WB - SHIM_EAR_DROP), (-T_PLY, N_WB),
                    (SHIM_BACK_W, N_WB), (SHIM_BACK_W, N_WB + H), (wf, N_WB + H)])


# =============================================================================
# 模組暫定外形（剖面 (w, n) 與正視 (s, n)）
# =============================================================================
def module_section(n_sb, w_fa=-T_PLY):
    """沿光束剖面。n_sb＝槽底高、w_fa＝前臂內面（重力往背後 → 靜止時貼擋幣板正面 w＝−3）。"""
    pcb_top = n_sb - (M['arm_top'] - M['slot_d'])
    pcb_bot = pcb_top - M['pcb_t']
    arm_top = n_sb + M['slot_d']
    wf0, wb0 = w_fa - M['arm_t'], w_fa + M['slot_w']
    wb1 = wb0 + M['arm_t']
    p0, p1 = wf0 - PCB_OVH, wb1 + PCB_OVH
    return {
        '前臂': _rect(wf0, pcb_top, w_fa, arm_top),
        '後臂': _rect(wb0, pcb_top, wb1, arm_top),
        '本體': _rect(w_fa, pcb_top, wb0, n_sb),
        'PCB': _rect(p0, pcb_bot, p1, pcb_top),
        '焊點': _rect(p0, pcb_bot - M['back_h'], p1, pcb_bot),
        '元件': _rect(p0, pcb_top, p1, pcb_top + M['comp_h']),
        '排針': _rect(p1 - M['hdr_len'], pcb_top, p1, pcb_top + M['hdr_up']),
    }


def module_front(n_sb, s_pd=S_DN, wing=None):
    """正視 (s, n) 的穿窗截面：PCB（含焊點、元件）＋本體／臂。s_pd＝PCB 下游邊。"""
    wing = wing or M['wing']
    pcb_top = n_sb - (M['arm_top'] - M['slot_d'])
    low = pcb_top - M['pcb_t'] - M['back_h']
    sc = s_pd - body_offset(wing)
    return {'PCB': _rect(s_pd - M['pcb_W'], low, s_pd, pcb_top + M['comp_h']),
            '本體臂': _rect(sc - M['arm_w'] / 2, pcb_top, sc + M['arm_w'] / 2, n_sb + M['slot_d'])}


def n_sb_low():
    return N_WB + SB_TO_LOW            # 低位：焊點坐在窗底


def n_sb_on(H):
    return N_WB + H + SB_TO_LOW        # 坐在高 H 的墊片上


def boards_section(s=0.0):
    """感測處（站座標 s）沿光束剖面裡的板子：擋幣板 w −3～0、背牆 w 0～3。"""
    out = {'擋幣板軌道條': _rect(-T_PLY, N_STRIP, 0.0, 0.0),
           '擋幣板下段': _rect(-T_PLY, -STRIP_H, 0.0, N_WB),
           '背牆下段': _rect(0.0, N_WB - 40.0, T_PLY, N_WB)}
    hit = [sb for _, sb in LH_S if abs(s - sb) <= LH_W / 2]
    if hit:
        out['背牆軌道條'] = _rect(0.0, N_STRIP, T_PLY, LH_N_BOT)
        out['背牆光孔上'] = _rect(0.0, LH_N_TOP, T_PLY, WALL_TOP_N)
    else:
        out['背牆軌道條'] = _rect(0.0, N_STRIP, T_PLY, WALL_TOP_N)
    return out

# =============================================================================
# 排版（網格點陣＋相關運算找最低可放位置，再用 shapely 精確驗證間距）
# =============================================================================
class Placed:
    """零件在板上的位置：自然座標先逆時針轉 rot 度，再翻 y（SVG 往下），再平移。"""

    def __init__(self, part, rot, tx, ty):
        self.part, self.rot, self.tx, self.ty = part, rot, tx, ty

    def pt(self, p):
        a = math.radians(self.rot)
        x = p[0] * math.cos(a) - p[1] * math.sin(a)
        y = p[0] * math.sin(a) + p[1] * math.cos(a)
        return (x + self.tx, -y + self.ty)

    def geom(self, g):
        a = math.radians(self.rot)
        c, s = math.cos(a), math.sin(a)
        # 旋轉＋翻 y＋平移 的仿射矩陣 [a, b, d, e, xoff, yoff]
        return affinity.affine_transform(g, [c, -s, -s, -c, self.tx, self.ty])


def _oriented(part, rot):
    pl = Placed(part, rot, 0.0, 0.0)
    g = pl.geom(Polygon(part.outline.exterior))
    x0, y0 = g.bounds[0], g.bounds[1]
    return Placed(part, rot, -x0, -y0)


def _raster(poly, x0, y0, nx, ny, res):
    import shapely
    xs = x0 + (np.arange(nx) + 0.5) * res
    ys = y0 + (np.arange(ny) + 0.5) * res
    X, Y = np.meshgrid(xs, ys)
    return shapely.contains_xy(poly, X, Y)


def layout(instances, width, res=0.5):
    from scipy.signal import correlate
    Hmax = SHEET_MAX[1]
    nx, ny = int(round(width / res)), int(round(Hmax / res))
    occ = np.zeros((ny, nx), dtype=float)
    placed, placed_g = [], []
    pad = PART_GAP + 0.6
    for part, rots in instances:
        cands = []
        for rot in rots:
            base = _oriented(part, rot)
            g = base.geom(Polygon(part.outline.exterior))
            gw, gh = g.bounds[2], g.bounds[3]
            if gw > width - 2 * SHEET_MARGIN or gh > Hmax - 2 * SHEET_MARGIN:
                continue
            mx, my = int(math.ceil((gw + 2 * pad) / res)), int(math.ceil((gh + 2 * pad) / res))
            mask = _raster(g.buffer(pad), -pad, -pad, mx, my, res).astype(float)
            if mx > nx or my > ny:
                continue
            ov = correlate(occ, mask, mode='valid', method='fft')
            iy, ix = np.nonzero(ov < 0.5)
            tx = ix * res + pad          # 遮罩原點在零件外包左上角往外 pad
            ty = iy * res + pad
            ok = (tx >= SHEET_MARGIN) & (ty >= SHEET_MARGIN) & (tx + gw <= width - SHEET_MARGIN) & (ty + gh <= Hmax - SHEET_MARGIN)
            tx, ty = tx[ok], ty[ok]
            order = np.lexsort((tx, np.round(ty + gh, 3)))[:300]     # 先找底邊最高（SVG y 最小）、再靠左
            for i in order:
                cands.append((round(float(ty[i] + gh), 3), float(tx[i]), rot, base, float(tx[i]), float(ty[i])))
        cands.sort(key=lambda c: (c[0], c[1]))
        done = False
        for _, _, rot, base, X0, Y0 in cands:
            pl = Placed(part, rot, base.tx + X0, base.ty + Y0)
            g = pl.geom(Polygon(part.outline.exterior))
            if any(g.distance(qg) < PART_GAP - 1e-6 for qg in placed_g):
                continue
            placed.append(pl)
            placed_g.append(g)
            occ = np.maximum(occ, _raster(g.buffer(0.6), 0.0, 0.0, nx, ny, res).astype(float))
            done = True
            break
        if not done:
            return None
    return placed


def best_layout(parts):
    order = [parts['B'], parts['A'], parts['D'], parts['F'], parts['C'], parts['C']] + \
            [parts[k] for k in sorted(k for k in parts if k.startswith('E'))]
    insts = [(p, (0,) if p.code in ('B', 'A') else (0, 90, 180, 270)) for p in order]
    wB = parts['B'].outline.bounds[2] - parts['B'].outline.bounds[0]
    best = None
    for W in sorted({math.ceil(wB + 2 * SHEET_MARGIN)} | {math.ceil(wB) + d for d in (12, 22, 30, 40, 50, 60)} | {int(SHEET_MAX[0])}):
        if W > SHEET_MAX[0]:
            continue
        pl = layout(insts, W)
        if pl is None:
            continue
        gs = [p.geom(Polygon(p.part.outline.exterior)) for p in pl]
        ux = max(g.bounds[2] for g in gs) + SHEET_MARGIN
        uy = max(g.bounds[3] for g in gs) + SHEET_MARGIN
        area = ux * uy
        if best is None or area < best[0] - 1e-6:
            best = (area, math.ceil(ux * 10) / 10, math.ceil(uy * 10) / 10, pl)
    if best is None:
        raise RuntimeError('排不下')
    return best[1], best[2], best[3]


# =============================================================================
# SVG 輸出
# =============================================================================
def _f(v):
    s = f'{v:.3f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def _ring_d(pts):
    pts = list(pts)
    if math.dist(pts[0], pts[-1]) < 1e-9:
        pts = pts[:-1]
    return 'M ' + ' L '.join(f'{_f(x)},{_f(y)}' for x, y in pts) + ' Z'


def _poly_d(pl, poly):
    g = pl.geom(Polygon(poly.exterior))
    return _ring_d(g.exterior.coords)


def _text_d(pl, t):
    out = []
    for c in t['contours']:
        segs = []
        for seg in c:
            pts = [pl.pt(p) for p in seg[1:]]
            segs.append(seg[0] + ' ' + ' '.join(f'{_f(x)},{_f(y)}' for x, y in pts))
        out.append(' '.join(segs) + ' Z')
    return ' '.join(out)


def write_svg(path, W, H, placed):
    cnt = {}
    eng, cut = [], []
    for pl in placed:
        p = pl.part
        k = cnt.get(p.code, 0)
        cnt[p.code] = k + 1
        gid = f'{p.code}-{k + 1}'
        lab = f'{p.code} {p.name}' + (f'（第 {k + 1} 片）' if p.code == 'C' else '')
        e = [f'    <g id="eng-{gid}" inkscape:label="{lab}" data-part="{p.code}">']
        for i, ln in enumerate(p.lines):
            a, b = pl.pt(ln.coords[0]), pl.pt(ln.coords[-1])
            e.append(f'      <path id="eng-{gid}-l{i}" d="M {_f(a[0])},{_f(a[1])} L {_f(b[0])},{_f(b[1])}" style="{STROKE_ENGRAVE}"/>')
        for i, t in enumerate(p.texts):
            e.append(f'      <path id="eng-{gid}-t{i}" d="{_text_d(pl, t)}" style="{STROKE_ENGRAVE}"/>')
        e.append('    </g>')
        if p.lines or p.texts:
            eng += e
        c = [f'    <g id="cut-{gid}" inkscape:label="{lab}" data-part="{p.code}">']
        for i, (nm, h) in enumerate(p.holes):     # 孔與內部線先切
            c.append(f'      <path id="cut-{gid}-h{i}" data-kind="hole" d="{_poly_d(pl, h)}" style="{STROKE_CUT}"/>')
        c.append(f'      <path id="cut-{gid}-outline" data-kind="outline" d="{_poly_d(pl, p.outline)}" style="{STROKE_CUT}"/>')
        c.append('    </g>')
        cut += c
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
             '<!-- 光耦簡易測試原型（光耦測試原型/make_proto.py 產生，請勿手改；改參數後重跑）。'
             '黑 0.2＝切割；紅 0.2＝雕刻（紅色圖層設「線／向量雕刻」）。單位 mm。 -->',
             f'<svg width="{_f(W)}mm" height="{_f(H)}mm" viewBox="0 0 {_f(W)} {_f(H)}" version="1.1" id="svg1"',
             '   xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"',
             '   xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"',
             '   xmlns="http://www.w3.org/2000/svg"',
             '   xmlns:svg="http://www.w3.org/2000/svg">',
             '  <sodipodi:namedview id="namedview1" pagecolor="#ffffff" bordercolor="#000000" borderopacity="0.25"',
             '     inkscape:document-units="mm" showgrid="false" inkscape:current-layer="layer-cut" />',
             '  <g inkscape:groupmode="layer" id="layer-engrave" inkscape:label="雕刻">'] + eng + ['  </g>',
             '  <g inkscape:groupmode="layer" id="layer-cut" inkscape:label="切割">'] + cut + ['  </g>', '</svg>', '']
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines))


def read_svg(path):
    """讀回 SVG：每個 path 的圖層、零件、種類、樣式、取樣點、是否封閉。"""
    from svgpathtools import parse_path
    ns = {'svg': 'http://www.w3.org/2000/svg', 'ink': 'http://www.inkscape.org/namespaces/inkscape'}
    tree = ET.parse(path)
    root = tree.getroot()
    out = dict(W=float(root.get('viewBox').split()[2]), H=float(root.get('viewBox').split()[3]),
               paths=[], has_text=False, tags=set())
    for el in root.iter():
        tag = el.tag.split('}')[-1]
        out['tags'].add(tag)
        if tag in ('text', 'tspan', 'flowRoot'):
            out['has_text'] = True
    for layer in root.findall('svg:g', ns):
        lname = layer.get(f'{{{ns["ink"]}}}label')
        for grp in layer.findall('svg:g', ns):
            for el in grp.findall('svg:path', ns):
                pth = parse_path(el.get('d'))
                subs = []
                for sp in pth.continuous_subpaths():
                    pts = []
                    for seg in sp:
                        n = 1 if type(seg).__name__ == 'Line' else 10
                        for i in range(n):
                            z = seg.point(i / n)
                            pts.append((z.real, z.imag))
                    z = sp[-1].point(1.0)
                    pts.append((z.real, z.imag))
                    if math.dist(pts[0], pts[-1]) < 1e-6:
                        pts[-1] = pts[0]
                    subs.append(dict(pts=pts, closed=sp.isclosed()))
                out['paths'].append(dict(layer=lname, part=grp.get('data-part'), group=grp.get('id'),
                                         kind=el.get('data-kind'), style=el.get('style'), subs=subs,
                                         fill=el.get('fill'), stroke=el.get('stroke')))
    return out

# =============================================================================
# 自我檢查
# =============================================================================
EPS = 1e-6


def _area(g):
    return 0.0 if g.is_empty else g.area


def _components(g):
    if g.is_empty:
        return []
    return list(g.geoms) if hasattr(g, 'geoms') else [g]


def _slot_fit(slot, tab, c=C_TAB):
    """tab（矩形，同一平面）在 slot 內、四邊間隙都等於 c → (ok, 最小間隙, 最大間隙)。"""
    sx0, sy0, sx1, sy1 = slot.bounds
    tx0, ty0, tx1, ty1 = tab.bounds
    gaps = [tx0 - sx0, sx1 - tx1, ty0 - sy0, sy1 - ty1]
    ok = all(abs(g - c) < 1e-4 for g in gaps) and slot.contains(tab)
    return ok, min(gaps), max(gaps)


def run_checks(parts, placed, svg, W, H):
    R = []

    def add(name, ok, detail):
        R.append((name, bool(ok), detail))

    A, B, C, D, F = (parts[k] for k in 'ABCDF')
    shims = [parts[k] for k in sorted((k for k in parts if k.startswith('E')), key=lambda k: int(k[1:]))]

    # 1 切割外框閉合
    cuts = [p for p in svg['paths'] if p['layer'] == '切割']
    bad = []
    for p in cuts:
        for sp in p['subs']:
            if not sp['closed'] or not Polygon(sp['pts']).is_valid or Polygon(sp['pts']).area < 0.5:
                bad.append(p['group'])
    add('切割外框閉合', not bad and cuts, f'{len(cuts)} 條切割路徑全部封閉、多邊形有效' if not bad else f'未閉合／無效：{bad}')

    # 2 顏色、線寬、fill
    badst = []
    for p in svg['paths']:
        st = dict(kv.split(':') for kv in (p['style'] or '').split(';') if kv)
        want = '#000000' if p['layer'] == '切割' else '#ff0000'
        if p['layer'] not in ('切割', '雕刻') or st.get('fill') != 'none' or st.get('stroke') != want \
                or abs(float(st.get('stroke-width', '0')) - 0.2) > 1e-9 or p['fill'] or p['stroke'] or len(st) != 3:
            badst.append(p['group'])
    add('只有黑紅兩色、0.2 線、fill none', not badst,
        f'切割 {len(cuts)} 條全黑 #000000、雕刻 {len(svg["paths"]) - len(cuts)} 條全紅 #ff0000，線寬 0.2，fill none'
        if not badst else f'樣式不符：{badst[:5]}')

    # 3 沒有 <text>
    add('沒有 <text>', not svg['has_text'], f'SVG 標籤只有 {sorted(svg["tags"])}')

    # 4 每個零件孔在前、外框在後
    groups = {}
    for p in cuts:
        groups.setdefault(p['group'], []).append(p)
    badord = []
    for gid, ps in groups.items():
        polys = [Polygon(p['subs'][0]['pts']) for p in ps]
        last = polys[-1]
        if ps[-1]['kind'] != 'outline' or any(p['kind'] != 'hole' for p in ps[:-1]) or \
                any(not last.buffer(1e-3).contains(q) for q in polys[:-1]) or \
                any(q.area >= last.area for q in polys[:-1]):
            badord.append(gid)
    add('每個零件孔在前、外框在後', not badord, f'{len(groups)} 個零件群組都是先孔後外框' if not badord else f'順序錯：{badord}')

    # 5 間距、板邊、板子大小
    outl = {gid: Polygon(ps[-1]['subs'][0]['pts']) for gid, ps in groups.items()}
    ids = list(outl)
    dmin, pair = 1e9, None
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            d = outl[ids[i]].distance(outl[ids[j]])
            if d < dmin:
                dmin, pair = d, (ids[i], ids[j])
    bx = unary_union(list(outl.values())).bounds
    edge = min(bx[0], bx[1], W - bx[2], H - bx[3])
    ok = dmin >= PART_GAP - 1e-3 and edge >= SHEET_MARGIN - 1e-3 and W <= SHEET_MAX[0] and H <= SHEET_MAX[1]
    add('零件間距 ≥2、離板邊 ≥2、板子 ≤255×355', ok,
        f'板子 {W:g}×{H:g} mm；最小零件間距 {dmin:.2f}（{pair[0]}／{pair[1]}）；離板邊最小 {edge:.2f}')
    # 雕刻在零件內（讀回的 SVG）
    eng_out = []
    for p in svg['paths']:
        if p['layer'] != '雕刻':
            continue
        own = [outl[g] for g in outl if g.split('-', 1)[1] == p['group'].split('-', 1)[1]]
        for sp in p['subs']:
            if not own or not own[0].buffer(1e-3).contains(LineString(sp['pts']) if len(sp['pts']) > 1 else Point(sp['pts'][0])):
                eng_out.append(p['group'])
    add('雕刻都在自己零件的外框內（讀回 SVG）', not eng_out, '全部在內' if not eng_out else f'超出：{set(eng_out)}')

    # 6 雕刻離切割線、字高
    badtx = []
    for P in parts.values():
        sol = P.solid()
        cutl = unary_union([LineString(P.outline.exterior.coords)] + [LineString(h.exterior.coords) for _, h in P.holes])
        for t in P.texts:
            if t['em'] < 4.0 - EPS or not sol.contains(t['ink']) or t['ink'].distance(cutl) < TEXT_CLEAR - EPS:
                badtx.append(f'{P.code}:{t["text"]}（離切割 {t["ink"].distance(cutl):.2f}）')
        for ln in P.lines:
            if not sol.contains(ln) or ln.distance(cutl) < LINE_CLEAR - EPS:
                badtx.append(f'{P.code}:線（離切割 {ln.distance(cutl):.2f}）')
        allink = [t['ink'] for t in P.texts]
        for i in range(len(allink)):
            for j in range(i + 1, len(allink)):
                if allink[i].distance(allink[j]) < 0.4:
                    badtx.append(f'{P.code}:字重疊')
    ems = sorted({t['em'] for P in parts.values() for t in P.texts})
    add('雕刻字清楚（em ≥4、字墨離切割 ≥1、線離切割 ≥1）', not badtx,
        f'字高 em {ems} mm（外框線字，msjh.ttc 轉輪廓）' if not badtx else '；'.join(badtx[:6]))

    # 7 榫與槽
    jt = []
    # (a) 背牆下緣榫 → 底板斜插槽（30° 斜插）
    ft = foot_tab_side()
    a_slots = A.hole('斜插槽')
    tabsB = _components(B.outline.intersection(_rect(X_L - 1, -50, X_R + 1, 0.0)))
    tabsB = [t for t in tabsB if t.area > 1]
    ok_a = len(tabsB) == len(FOOT_X) == len(a_slots)
    gaps_a = []
    for tb in tabsB:
        proj = _rect(tb.bounds[0], ft.bounds[0], tb.bounds[2], ft.bounds[2])   # 俯視投影（垂直往下插時掃過的範圍）
        m = [s for s in a_slots if s.intersects(proj)]
        if len(m) != 1:
            ok_a = False
            continue
        okf, g0, g1 = _slot_fit(m[0], proj)
        ok_a &= okf
        gaps_a += [g0, g1]
        ok_a &= abs((tb.bounds[3] - tb.bounds[1]) - FOOT_TAB_L) < 1e-6
    zlow = ft.bounds[1]
    ok_a &= zlow > 0.0 and ft.bounds[3] > 3.0
    slot_wy = FOOT_SLOT_Y[1] - FOOT_SLOT_Y[0]
    jt.append(ok_a)
    add('榫槽(a) 背牆下緣榫 → 底板斜插槽（30° 斜插）', ok_a,
        f'{len(tabsB)} 榫↔{len(a_slots)} 槽；榫 {FOOT_TAB_W:g}×板厚 3、沿背牆伸 {FOOT_TAB_L:g}；'
        f'斜插的俯視投影深 {ft.bounds[2] - ft.bounds[0]:.3f} → 槽 {FOOT_TAB_W + 2 * C_TAB:.1f}×{slot_wy:.3f}'
        f'（直插只要 3.2）；四邊間隙 {min(gaps_a):.3f}～{max(gaps_a):.3f}；榫最低點離桌面 {zlow:.2f}（不凸出底板下面）')
    # (b) 支撐斜邊榫 → 背牆槽
    nb = (math.cos(TL), -math.sin(TL))
    u = (math.sin(TL), math.cos(TL))
    hyp = LineString([sup_hyp_point(-10), sup_hyp_point(SUP_HB + 10)])
    front_side = Polygon([sup_hyp_point(-10), sup_hyp_point(SUP_HB + 10),
                          (sup_hyp_point(SUP_HB + 10)[0] - 10 * nb[0], sup_hyp_point(SUP_HB + 10)[1] - 10 * nb[1]),
                          (sup_hyp_point(-10)[0] - 10 * nb[0], sup_hyp_point(-10)[1] - 10 * nb[1])])
    tabsC = [t for t in _components(C.outline.intersection(front_side)) if t.area > 1]
    b_slots = B.hole('支撐槽')
    ok_b = len(tabsC) == len(SUP_WALL_TABS) and len(b_slots) == len(SUP_WALL_TABS) * len(SUP_X)
    used, gaps_b, deps = set(), [], []
    p0 = sup_hyp_point(0.0)
    for xs in SUP_X:
        for tb in tabsC:
            cs = list(tb.exterior.coords)
            along = [(p[0] - p0[0]) * u[0] + (p[1] - p0[1]) * u[1] for p in cs]
            dep = max(-((p[0] - p0[0]) * nb[0] + (p[1] - p0[1]) * nb[1]) for p in cs)
            deps.append(dep)
            tabB = _rect(xs - T_PLY / 2, min(along), xs + T_PLY / 2, max(along))
            m = [i for i, s in enumerate(b_slots) if s.intersects(tabB)]
            if len(m) != 1 or m[0] in used:
                ok_b = False
                continue
            used.add(m[0])
            okf, g0, g1 = _slot_fit(b_slots[m[0]], tabB)
            ok_b &= okf
            gaps_b += [g0, g1]
    ok_b &= len(used) == len(b_slots) and all(abs(d - (T_PLY - TAB_RECESS)) < 1e-6 for d in deps)
    jt.append(ok_b)
    add('榫槽(b) 支撐斜邊榫 → 背牆槽（垂直背牆插）', ok_b,
        f'{len(tabsC)}×{len(SUP_X)} 榫↔{len(b_slots)} 槽，一一對應；槽 {T_PLY + 2 * C_TAB:.1f}×{SUP_WALL_TABS[0][1] - SUP_WALL_TABS[0][0] + 2 * C_TAB:.1f}，'
        f'間隙 {min(gaps_b):.3f}～{max(gaps_b):.3f}；榫深 {max(deps):.2f}（背牆 3，正面凹 {T_PLY - max(deps):.2f}，不凸出）')
    # (c) 支撐下緣榫 → 底板槽
    tabsCb = [t for t in _components(C.outline.intersection(_rect(-50, -50, 100, 3.0))) if t.area > 1]
    c_slots = A.hole('支撐槽')
    ok_c = len(tabsCb) == len(SUP_BASE_TABS) and len(c_slots) == len(SUP_BASE_TABS) * len(SUP_X)
    used, gaps_c = set(), []
    for xs in SUP_X:
        for tb in tabsCb:
            tabA = _rect(xs - T_PLY / 2, tb.bounds[0], xs + T_PLY / 2, tb.bounds[2])
            m = [i for i, s in enumerate(c_slots) if s.intersects(tabA)]
            if len(m) != 1 or m[0] in used:
                ok_c = False
                continue
            used.add(m[0])
            okf, g0, g1 = _slot_fit(c_slots[m[0]], tabA)
            ok_c &= okf
            gaps_c += [g0, g1]
            ok_c &= tb.bounds[1] > 0.0
    ok_c &= len(used) == len(c_slots)
    jt.append(ok_c)
    add('榫槽(c) 支撐下緣榫 → 底板槽（垂直插）', ok_c,
        f'{len(tabsCb)}×{len(SUP_X)} 榫↔{len(c_slots)} 槽，一一對應；間隙 {min(gaps_c):.3f}～{max(gaps_c):.3f}；'
        f'榫底離桌面 {min(t.bounds[1] for t in tabsCb):.2f}')
    # 組裝方向：背牆＋支撐先黏成一體，再整個垂直往下插進底板（斜插槽是垂直柱，包含斜榫整個俯視投影）
    add('組裝可行：背牆＋支撐一體後垂直往下插進底板', ok_a and ok_c and abs(ft.bounds[2] - ft.bounds[0] + 2 * C_TAB - slot_wy) < 1e-6,
        '斜插槽＝斜榫的整個俯視投影＋0.1，所以背牆（後仰 30°）可以和支撐一起垂直往下插')

    # 8 窗、軌道條對齊；軌道條厚；軌道 20°；背牆 30°
    winB = B.hole('窗')[0]
    winD = D.hole('窗')[0]
    winD_on_B = Polygon([st2xy(*p) for p in winD.exterior.coords])
    sym = winB.symmetric_difference(winD_on_B).area
    strip_on_B = Polygon([st2xy(*p) for p in D.outline.exterior.coords])
    guide = unary_union(B.lines[len(RELEASE):len(RELEASE) + 3])
    bot_edge = LineString([st2xy(S_START, -STRIP_H), st2xy(S_END, -STRIP_H)])
    guide_ok = guide.buffer(1e-6).contains(bot_edge)
    nB = [xy2st(*p)[1] for p in winB.exterior.coords]
    barB = 0.0 - max(nB)
    barD = 0.0 - winD.bounds[3]
    fw, fh = F.outline.bounds[2] - F.outline.bounds[0], F.outline.bounds[3] - F.outline.bounds[1]
    ok = sym < 1e-6 and abs(barB - STRIP_BAR) < 1e-9 and abs(barD - STRIP_BAR) < 1e-9 and guide_ok and \
        abs(fw - (WIN_W - 2 * C_TAB)) < 1e-9 and abs(fh - (WIN_H - 2 * C_TAB)) < 1e-9 and \
        B.outline.contains(strip_on_B)
    add('擋幣板與背牆的窗、軌道條黏合後對齊', ok,
        f'擋幣板窗移到背牆座標後和背牆窗相差面積 {sym:.1e} mm²；兩片軌道條各 {barD:.2f}／{barB:.2f}（疊起 {2 * T_PLY:g} mm 厚）；'
        f'窗 {WIN_W:.1f}×{WIN_H:.1f}，對位塞 F {fw:.1f}×{fh:.1f}（單邊 {C_TAB}）；背牆雕的擋幣板下緣線與擋幣板下緣重合')
    top = LineString([st2xy(S_START, 0), st2xy(S_END, 0)])
    ang = math.degrees(math.atan2(-(top.coords[1][1] - top.coords[0][1]), top.coords[1][0] - top.coords[0][0]))
    vx = (C.outline.exterior.coords)
    yB, zB = sup_hyp_point(SUP_HB)
    vert = (0.0, zB - 3.0)
    hp = (yB - sup_hyp_point(6.0)[0], zB - sup_hyp_point(6.0)[1])
    tilt = math.degrees(math.acos((vert[0] * hp[0] + vert[1] * hp[1]) / (math.hypot(*vert) * math.hypot(*hp))))
    has_vert = any(abs(a[0] - yB) < 1e-9 and abs(b[0] - yB) < 1e-9 and abs(abs(a[1] - b[1]) - (zB - 3.0)) < 1e-9
                   for a, b in zip(vx[:-1], vx[1:]))
    gT = math.sin(TR) * math.cos(TL)
    gN = -math.cos(TR) * math.cos(TL)
    gW = math.sin(TL)
    horiz = math.degrees(math.asin(math.sin(TR) * math.cos(TL)))
    add('軌道條厚 2.3、軌道斜 20°、背牆後仰 30°', abs(barD - 2.3) < 1e-9 and abs(ang - TRACK_DEG) < 1e-9 and
        abs(tilt - TILT_DEG) < 1e-6 and has_vert,
        f'軌道條 {barD:.2f}；軌道在背牆面內 {ang:.3f}°（對水平 {horiz:.2f}°）；支撐斜邊對鉛直後緣 {tilt:.3f}°＝背牆後仰；'
        f'重力（沿軌, 垂直軌道, 往背後）＝({gT:+.3f}, {gN:+.3f}, {gW:+.3f}) g')

    # 9 光孔涵蓋光束高度
    ap = M['aperture']
    rows, okl = [], True
    for H_ in SHIMS:
        nsb = n_sb_on(H_)
        if nsb > N_STRIP + 1e-9:
            rows.append(f'{H_:.1f}→塞不進（暫定尺寸）')
            continue
        beam = nsb + M['beam_sb']
        if beam - ap / 2 < LH_N_BOT - 1e-9:
            rows.append(f'{H_:.1f}→{beam:.1f}（低於軌道可用高，模組比暫定大時才用）')
            continue
        cov = beam - ap / 2 >= LH_N_BOT - 1e-9 and beam + ap / 2 <= LH_N_TOP + 1e-9
        okl &= cov
        rows.append(f'{H_:.1f}→{beam:.1f}{"" if cov else "✗"}')
    hs = B.hole('光孔')
    sc_ok = all(abs(sum(xy2st(*p)[0] for p in h.exterior.coords[:-1]) / 4 - sb) < 1e-6 for h, (_, sb) in zip(hs, LH_S))
    okl &= sc_ok and len(hs) == len(LH_S) and LH_N_TOP >= BEAM_TOP + BEAM_SB_TOL + ap / 2 - 1e-9
    add('光孔涵蓋所有墊片對應的光束高度', okl,
        f'光孔 {len(hs)} 個（本體位置 {", ".join(f"{w} s={sb:+.1f}" for w, sb in LH_S)}），寬 {LH_W}、n {LH_N_BOT:.1f}～{LH_N_TOP:.1f}；'
        f'墊片→光束高：' + '、'.join(rows))

    # 10 模組暫定外形
    low = n_sb_low()
    cont = n_sb_on(H0)
    win_st = _rect(WIN_S0, N_WB, WIN_S1, N_STRIP)
    mf_c = module_front(low, s_pd=WIN_S1 - (WIN_W - M['pcb_W']) / 2)
    mf_d = module_front(low, s_pd=WIN_S1)
    in_win = all(win_st.buffer(1e-9).contains(g) for g in list(mf_c.values()) + list(mf_d.values()))
    arm_top_low = low + M['slot_d']
    top_gap = N_STRIP - arm_top_low
    side_gap = (WIN_W - M['pcb_W']) / 2
    # 水平推入：從背後沿 −w 推到前臂內面 w＝−3，掃過的範圍不可碰板
    hit_push = []
    for s_cut in [0.0] + [sb for _, sb in LH_S] + [WIN_S0 + 1, WIN_S1 - 1]:
        bds = boards_section(s_cut)
        for nm, g in module_section(low).items():
            sweep = _rect(g.bounds[0], g.bounds[1], 200.0, g.bounds[3])
            for bn, bg in bds.items():
                if _area(sweep.intersection(bg)) > 1e-9:
                    hit_push.append(f'{nm}×{bn}')
    # 抬起：低位 → 頂到軌道條，沿 +n 掃過
    hit_lift = []
    ms_lo, ms_hi = module_section(low), module_section(cont)
    for s_cut in [0.0] + [sb for _, sb in LH_S]:
        bds = boards_section(s_cut)
        for nm in ms_lo:
            sweep = _rect(ms_lo[nm].bounds[0], ms_lo[nm].bounds[1], ms_lo[nm].bounds[2], ms_hi[nm].bounds[3])
            for bn, bg in bds.items():
                if _area(sweep.intersection(bg)) > 1e-9:
                    hit_lift.append(f'{nm}×{bn}')
    fa_gap = (-T_PLY) - ms_hi['前臂'].bounds[2]
    ba_gap = ms_hi['後臂'].bounds[0] - T_PLY
    comp_gap = N_STRIP - ms_hi['元件'].bounds[3]
    hdr_gap = ms_hi['排針'].bounds[0] - T_PLY
    ok = in_win and top_gap >= C_SLIDE - 1e-9 and side_gap >= C_WIN - 1e-9 and not hit_push and not hit_lift \
        and fa_gap >= -1e-9 and ba_gap > 0 and comp_gap >= 0.3 and hdr_gap > 0 and abs(cont - N_STRIP) < 1e-9
    add('模組低位能水平推入、抬起後兩臂跨板有餘隙', ok,
        f'窗 n {N_WB:.1f}～{N_STRIP:.1f}；低位（焊點坐窗底）臂頂 {arm_top_low:.1f}，離軌道條下緣 {top_gap:.1f}；'
        f'PCB 置中時兩側各 {side_gap:.1f}；從背後推入、往上抬到頂（行程 {cont - low:.1f}）都不碰板；'
        f'槽寬 {M["slot_w"]:g} 跨兩片共 {2 * T_PLY:g}，總餘隙 {M["slot_w"] - 2 * T_PLY:.1f}：'
        f'靜止時重力往背後，前臂內面貼擋幣板正面（間隙 {fa_gap:.1f}），後臂內面離背牆背面 {ba_gap:.1f}；'
        f'元件頂離軌道條 {comp_gap:.1f}；排針在背牆後 {hdr_gap:.1f}')
    # 墊片撐得到
    sh_hit, ov_min = [], 1e9
    for H_ in SHIMS:
        sp = shim_poly(H_)
        for bn, bg in boards_section(0.0).items():
            if _area(sp.intersection(bg)) > 1e-9:
                sh_hit.append(f'{H_}×{bn}')
        nsb = n_sb_on(H_)
        if nsb <= N_STRIP + 1e-9:
            ms = module_section(nsb)
            for nm, g in ms.items():
                if _area(sp.intersection(g)) > 1e-9:
                    sh_hit.append(f'{H_}×{nm}')
            bar_top = LineString([(-T_PLY - SHIM_EAR_W, N_WB + H_), (SHIM_BACK_W, N_WB + H_)])
            ov = bar_top.intersection(LineString([(ms['焊點'].bounds[0], N_WB + H_), (ms['焊點'].bounds[2], N_WB + H_)])).length
            ov_min = min(ov_min, ov)
    nxt = n_sb_on(H0 + SHIM_STEP) > N_STRIP + 1e-9
    ear_ok = N_WB - SHIM_EAR_DROP >= -STRIP_H + 1.0
    ok = H0 in SHIMS and nxt and not sh_hit and ov_min >= 10 and ear_ok and max(SHIMS) < WIN_H
    add('墊片撐得到模組', ok,
        f'{len(SHIMS)} 片 {min(SHIMS):.1f}～{max(SHIMS):.1f}（每片差 {SHIM_STEP}）；暫定尺寸「模組頂到軌道條」＝{H0:.1f}（再高一片就塞不進）；'
        f'墊片坐在兩片窗底、擋耳靠擋幣板正面（窗底下 {SHIM_EAR_DROP:g}，擋幣板窗下還有 {N_WB + STRIP_H:.1f}）；'
        f'墊片頂和 PCB 底重疊長 ≥{ov_min:.1f}；不和板、模組重疊' + (f'；問題：{sh_hit}' if sh_hit else ''))
    # 世界座標：低位最低點離底板、模組離支撐
    zmin, xs_mod = 1e9, []
    for s_ in (WIN_S0, WIN_S1):
        for n_ in (N_WB, ms_hi['排針'].bounds[3]):
            X_, Y_ = st2xy(s_, n_)
            xs_mod.append(X_)
            for w_ in (module_section(low)['PCB'].bounds[0], module_section(low)['PCB'].bounds[2]):
                zmin = min(zmin, world_of(xy2st_to_Y(s_, N_WB), w_)[1])
    gap_sup = min(min(abs(x - xs) for x in (min(xs_mod), max(xs_mod))) - T_PLY / 2 for xs in SUP_X)
    in_span = [xs for xs in SUP_X if min(xs_mod) - T_PLY / 2 <= xs <= max(xs_mod) + T_PLY / 2]
    add('模組離底板、支撐都夠遠', zmin >= 6.0 and not in_span and gap_sup >= 10,
        f'低位時模組最低點離桌面 {zmin:.1f}（底板頂 3）；窗與模組在 X {min(xs_mod):.1f}～{max(xs_mod):.1f}，'
        f'支撐在 X {SUP_X[0]:.1f}、{SUP_X[1]:.1f}，最近 {gap_sup:.1f}')

    # 11 硬幣滾動路徑沒有東西突出
    bad, dmins = [], []
    positions = [('低位', low)] + [(f'墊片{H_:.1f}', n_sb_on(H_)) for H_ in SHIMS if n_sb_on(H_) <= N_STRIP + 1e-9]
    for nm_c, dia, t in COINS:
        coin = _rect(-t, 0.0, 0.0, dia)
        dm = 1e9
        for pn, nsb in positions:
            for nm, g in module_section(nsb).items():
                if _area(coin.intersection(g)) > 1e-9:
                    bad.append(f'{nm_c}×{pn}{nm}')
                dm = min(dm, coin.distance(g))
        for H_ in SHIMS:
            if _area(coin.intersection(shim_poly(H_))) > 1e-9:
                bad.append(f'{nm_c}×墊片')
        dmins.append(f'{nm_c} {dm:.2f}')
    shim_top = N_WB + max(SHIMS)
    ear_top = N_WB
    sup_tip = T_PLY - (T_PLY - TAB_RECESS)
    top_band = _rect(S_START, -0.05, S_END, 0.0)
    track_len = D.solid().intersection(top_band).area / 0.05
    ok = not bad and shim_top < 0 and sup_tip > 0 and abs(track_len - (S_END - S_START)) < 1e-6
    add('四種硬幣滾動路徑上沒有東西突出', ok,
        f'硬幣立在擋幣板上緣、靠背牆正面（w −t～0）；模組在低位與每一片墊片的位置都不進入硬幣範圍，'
        f'離前臂最近：{"、".join(dmins)}；墊片最高點在軌道下 {-shim_top:.1f}、擋耳在軌道下 {-ear_top:.1f}；'
        f'支撐榫頭在背牆正面內 {sup_tip:.1f}；軌道（擋幣板上緣）連續 {track_len:.1f} mm 沒有缺口'
        + (f'；問題：{bad}' if bad else ''))

    # 12 其他數字
    rel = ', '.join(f'{n} {d:g}' for n, d in RELEASE)
    zend = world_of(Y_END, 0.0)[1]
    add('滑坡尺寸', S_END >= 40 and abs(-S_START - 110) <= 5,
        f'軌道 {S_END - S_START:.0f} mm（感測處前 {-S_START:.0f}、後 {S_END:.0f}）；放幣線離光束 {rel} mm；'
        f'出口離桌面 {zend:.1f} mm；背牆 {X_R - X_L:.1f}×{y_walltop(X_L):.1f}（右端高 {y_walltop(X_R):.1f}）')

    # 13 不會往後翻（背牆後仰 30°，軌道上段的硬幣和背後的模組都在支撐後方）
    tp = tip_analysis(parts)
    ok = tp['worst_in'] >= TIP_MIN - 1e-9 and tp['front_in'] >= TIP_MIN - 1e-9
    add('整台不會往後翻', ok,
        f'合板密度取 {PLY_RHO} g/cm³：整台 {tp["m"]:.0f} g，重心 y {tp["yc"]:.1f}（底板 y {tp["y0"]:.1f}～{tp["y1"]:.1f}，'
        f'離後緣 {tp["y1"] - tp["yc"]:.1f}）；加上模組 {MODULE_G:g} g 和兩枚 50 元相貼放在軌道最上游'
        f'（上游那枚離軌道起點 1 mm，T4 的 S50 相貼）時，'
        f'合成重心離後緣 {tp["worst_in"]:.1f}（要 ≥{TIP_MIN:g}）；空台在感測處軌道高（z {tp["z_push"]:.0f}）'
        f'從正面往後推 {tp["push_gf"]:.0f} gf 才會翻')
    return R


def tip_analysis(parts, rho=PLY_RHO):
    """整台（底板、背牆、擋幣板、2 片支撐；墊片和 F 太輕不算）＋模組＋硬幣的重心，和底板前後緣比。

    y 往背後、z 往上（側視）。回傳合成重心離底板後緣、前緣的距離（mm，正＝在底板範圍內）。"""
    k = T_PLY * rho / 1000.0                     # g/mm²
    items = []                                   # (質量 g, y, z)
    Bs = parts['B'].solid()
    items.append((Bs.area * k,) + world_of(Bs.centroid.y, T_PLY / 2))
    Ds = parts['D'].solid()
    items.append((Ds.area * k,) + world_of(st2xy(Ds.centroid.x, Ds.centroid.y)[1], -T_PLY / 2))
    Cs = parts['C'].solid()
    items += [(Cs.area * k, Cs.centroid.x, Cs.centroid.y)] * len(SUP_X)
    As = parts['A'].solid()
    items.append((As.area * k, As.centroid.y, T_PLY / 2))
    y0, y1 = parts['A'].outline.bounds[1], parts['A'].outline.bounds[3]

    def cg(its):
        m = sum(i[0] for i in its)
        return m, sum(i[0] * i[1] for i in its) / m, sum(i[0] * i[2] for i in its) / m

    m, yc, zc = cg(items)
    # 模組（工作位置，PCB 中段）
    mu = unary_union(list(module_section(n_sb_on(H0)).values()))
    s_mod = S_DN - M['pcb_W'] / 2
    mod = (MODULE_G,) + world_of(st2xy(s_mod, mu.centroid.y)[1], mu.centroid.x)
    # 兩枚 50 元相貼、放在軌道最上游（上游那枚的中心＝和軌道的接觸點，離軌道起點 1 mm；T4 的 S50 相貼就是這樣放）
    name, dia, t = COINS[-1]
    r = dia / 2
    coins = [(COIN_G[name],) + world_of(st2xy(S_START + 1.0 + j * dia, r)[1], -t / 2) for j in range(2)]
    _, ycw, _ = cg(items + [mod] + coins)
    z_push = world_of(st2xy(0.0, 0.0)[1], 0.0)[1]
    return dict(m=m, yc=yc, zc=zc, y0=y0, y1=y1, worst_in=y1 - ycw, front_in=ycw - y0,
                z_push=z_push, push_gf=m * (y1 - yc) / z_push)


def xy2st_to_Y(s, n):
    return st2xy(s, n)[1]

# =============================================================================
# 圖：預覽、示意圖
# =============================================================================
def _mpl():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    fp = font_manager.FontProperties(fname=FONT_PATH)
    font_manager.fontManager.addfont(FONT_PATH)
    matplotlib.rcParams['font.family'] = fp.get_name()
    matplotlib.rcParams['axes.unicode_minus'] = False
    return plt


def draw_preview(svg, placed, W, H, path):
    plt = _mpl()
    sc = 1 / 25.4 * 2.2
    fig, ax = plt.subplots(figsize=(W * sc + 0.6, H * sc + 0.9))
    ax.add_patch(__import__('matplotlib.patches', fromlist=['Rectangle']).Rectangle((0, 0), W, H, fill=False, ec='#999999', ls='--', lw=0.8))
    for p in svg['paths']:
        col = '#000000' if p['layer'] == '切割' else '#ff0000'
        for sp in p['subs']:
            xs, ys = zip(*sp['pts'])
            ax.plot(xs, ys, color=col, lw=0.5 if col == '#000000' else 0.35)
    cnt = {}
    for pl in placed:
        P = pl.part
        k = cnt.get(P.code, 0) + 1
        cnt[P.code] = k
        lab = P.code + (f'-{k}' if P.code == 'C' else '')
        if P.code.startswith('E'):
            anc = (-T_PLY - SHIM_EAR_W / 2, N_WB - SHIM_EAR_DROP / 2 + 1.0)
        elif P.code == 'C':
            anc = (P.outline.bounds[2] - 6.0, 3.0 + 22.0)
        elif P.code == 'F':
            anc = (3.0, 3.0)
        elif P.code == 'B':
            anc = (X_L + 30.0, 30.0)
        else:
            anc = P.outline.centroid.coords[0]
        c = pl.pt(anc)
        ax.text(c[0], c[1], lab, color='#1f4fd1', fontsize=12 if P.code in 'ABD' else 9, fontweight='bold',
                ha='center', va='center')
    ax.set_xlim(-2, W + 2)
    ax.set_ylim(H + 2, -2)
    ax.set_aspect('equal')
    ax.set_title(f'光耦測試原型 雷切預覽　板子 {W:g}×{H:g} mm（黑＝切割、紅＝雕刻、藍＝零件代號，只在預覽）', fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp_ in ax.spines.values():
        sp_.set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _patch(ax, poly, **kw):
    from matplotlib.patches import Polygon as MP
    if poly.is_empty:
        return
    for g in _components(poly):
        ax.add_patch(MP(list(g.exterior.coords), closed=True, **kw))
        for r in g.interiors:
            ax.add_patch(MP(list(r.coords), closed=True, fc='white', ec=kw.get('ec', 'k'), lw=kw.get('lw', 0.8)))


def draw_schematic(parts, path):
    plt = _mpl()
    from matplotlib import gridspec
    from matplotlib.patches import Circle, Rectangle
    fig = plt.figure(figsize=(25, 11.5))
    gsp = gridspec.GridSpec(1, 3, width_ratios=[1.0, 0.62, 0.66], wspace=0.10)
    wood, wood2, mod, shim_c = '#f1dfbd', '#d7aa78', '#3c9d5d', '#f2a03d'
    B, D = parts['B'], parts['D']
    fs = 10

    # ① 正視 ---------------------------------------------------------------
    ax = fig.add_subplot(gsp[0, 0])
    _patch(ax, B.solid(), fc=wood, ec='k', lw=0.9)
    strip = Polygon([st2xy(*p) for p in D.outline.exterior.coords])
    win = Polygon([st2xy(*p) for p in D.hole('窗')[0].exterior.coords])
    _patch(ax, strip.difference(win), fc=wood2, ec='#7a4b1c', lw=0.9, alpha=0.95)
    for h in B.hole('光孔'):
        _patch(ax, h, fc='#3b6fd8', ec='#3b6fd8', lw=0.6)
    for i, xs in enumerate(SUP_X):
        y0 = SUP_Y0 / math.sin(TL)
        ax.add_patch(Rectangle((xs - 1.5, y0), 3.0, SUP_HB - y0, fill=False, ec='#555', ls='--', lw=1.0))
        ax.text(xs + (3 if i == 0 else -3), SUP_HB - 4, '支撐 C\n（在背牆後面）', fontsize=fs - 1, color='#444',
                ha='left' if i == 0 else 'right', va='top')
    t0, t1 = st2xy(S_START, 0), st2xy(S_END, 0)
    ax.plot([t0[0], t1[0]], [t0[1], t1[1]], color='#8b3a0e', lw=2.6)
    ax.text(*st2xy(-70, -9.0), '軌道＝擋幣板 D 上緣（在背牆面內斜 20°）', rotation=-TRACK_DEG, rotation_mode='anchor',
            fontsize=fs, color='#5a2a08', ha='center', va='center')
    for name, d in RELEASE:
        a, b = st2xy(-d, 5), st2xy(-d, 30)
        ax.plot([a[0], b[0]], [a[1], b[1]], color='red', lw=1.2)
        ax.text(*st2xy(-d, 32), f'{name}\n離光束 {d:g}', color='red', fontsize=fs - 1, ha='center', va='bottom')
    c50 = st2xy(-dict(RELEASE)['S50'], R_MAX)
    ax.add_patch(Circle(c50, R_MAX, fill=False, ec='#777', ls=':', lw=1))
    ax.text(c50[0] + 2, c50[1] + 3, '50 元：中心對線', ha='center', va='center', fontsize=fs - 2, color='#555')
    mf = module_front(n_sb_on(H0))
    for g in mf.values():
        _patch(ax, Polygon([st2xy(*p) for p in g.exterior.coords]), fc='none', ec=mod, lw=1.3, ls='--')
    a0, a1 = st2xy(-60, 8), st2xy(-40, 8)
    ax.annotate('', a1, a0, arrowprops=dict(arrowstyle='-|>', color='#555', lw=1.5))
    ax.text(*st2xy(-50, 10), '滾動方向', rotation=-TRACK_DEG, ha='center', fontsize=fs - 1, color='#555')
    wc = st2xy((WIN_S0 + WIN_S1) / 2, N_WB)
    ax.annotate(f'感測窗（背牆、擋幣板同形）\n沿軌 {WIN_W:.1f} × 高 {WIN_H:.1f}，窗頂留軌道條 {STRIP_BAR}\n'
                f'綠虛線＝模組暫定外形（工作位置）', wc, (-70, 18), fontsize=fs,
                arrowprops=dict(arrowstyle='->'))
    lh = st2xy(LH_S[0][1], LH_N_TOP)
    ax.annotate(f'光孔 {len(LH_S)} 個：寬 {LH_W}、軌道上 {LH_N_BOT}～{LH_N_TOP:.1f}\n'
                f'由下游往上游＝本體靠 PCB 下游邊／中間／上游邊', lh, (8, 128), fontsize=fs, color='#2a55b8',
                arrowprops=dict(arrowstyle='->', color='#2a55b8'))
    e = st2xy(S_END, 0)
    ax.annotate(f'出口：硬幣滾出\n落進杯子\n（離桌面 {world_of(Y_END, 0)[1]:.0f} mm）', e, (X_R + 6, e[1] + 22),
                fontsize=fs, arrowprops=dict(arrowstyle='->'))
    ax.set_aspect('equal')
    ax.set_xlim(X_L - 8, X_R + 40)
    ax.set_ylim(-8, y_walltop(X_L) + 8)
    ax.set_title('① 滑坡正視（從前面看；淺色＝背牆 B、深色＝擋幣板 D；mm）', fontsize=13, loc='left')
    ax.set_xlabel('X（沿背牆長邊）')
    ax.set_ylabel('Y（沿背牆往上）')

    # ② 剖面（沿光束，s＝0） -------------------------------------------------
    ax = fig.add_subplot(gsp[0, 1])
    for nm, g in boards_section(0.0).items():
        _patch(ax, g, fc=wood2 if '擋幣板' in nm else wood, ec='k', lw=0.8)
    ax.add_patch(Rectangle((-2.4, 0), 2.4, 28, fc='#cfcfcf', ec='#888', alpha=0.7))
    ax.text(-1.2, 20, '50 元（厚 2.4）', ha='center', va='center', fontsize=fs - 2, rotation=90)
    for nm, g in module_section(n_sb_low()).items():
        if nm != '元件':
            _patch(ax, g, fc='none', ec='#888', lw=0.9, ls='--')
    ms = module_section(n_sb_on(H0))
    for nm, g in ms.items():
        if nm != '元件':
            _patch(ax, g, fc=mod, ec='#1d5c33', lw=1.0, alpha=0.30 if nm not in ('PCB',) else 0.65)
    _patch(ax, shim_poly(H0), fc=shim_c, ec='#9a5a00', lw=1.0, alpha=0.9)
    ax.plot([ms['前臂'].bounds[0], ms['後臂'].bounds[2]], [BEAM_TOP] * 2, color='red', lw=1.5, ls='-.')
    ax.plot([T_PLY + 0.5] * 2, [LH_N_BOT, LH_N_TOP], color='#2a55b8', lw=3)
    L = [  # (文字, 指向點, 文字位置, ha)
        (f'光束 {BEAM_TOP:.1f}（墊片 {H0:.1f} 時；\n每換低一片，光束低 {SHIM_STEP}）', (ms['後臂'].bounds[2], BEAM_TOP), (17, 3.5), 'left'),
        (f'光孔 n {LH_N_BOT}～{LH_N_TOP:.1f}', (T_PLY + 0.5, LH_N_TOP), (5, 22), 'left'),
        ('前臂（靜止時靠擋幣板正面）', ms['前臂'].centroid.coords[0], (-29, 14), 'left'),
        ('後臂', ms['後臂'].centroid.coords[0], (17, 12), 'left'),
        ('排針（留在背面）', (ms['排針'].bounds[2], ms['排針'].bounds[3]), (17, 17), 'left'),
        ('PCB（焊點朝下）', (ms['PCB'].bounds[2], ms['PCB'].centroid.y), (17, -4.5), 'left'),
        (f'軌道條 {STRIP_BAR}（兩片疊 6 厚）', (-1.5, -1.2), (-29, 7), 'left'),
        (f'墊片 E（L 形，撐高 {H0:.1f}）', (SHIM_BACK_W, N_WB + H0 / 2), (17, -14), 'left'),
        ('擋耳靠擋幣板正面', (-T_PLY - SHIM_EAR_W / 2, N_WB - SHIM_EAR_DROP / 2), (-29, -31), 'left'),
        ('擋幣板 D', (-1.5, -28), (-29, -37), 'left'),
        ('背牆 B', (1.5, -30), (8, -37), 'left'),
        ('灰虛線＝低位：\n從背面垂直背牆推入，\n再往上抬到槽底頂住軌道條', (-6, n_sb_low() - 1), (-29, -9), 'left'),
    ]
    for txt, p, q, ha in L:
        ax.annotate(txt, p, q, fontsize=fs - 1, ha=ha, va='center', arrowprops=dict(arrowstyle='->', lw=0.7))
    ax.annotate('', (-27, 33.5), (-10, 33.5), arrowprops=dict(arrowstyle='->'))
    ax.text(-18.5, 34.3, '正面', ha='center', fontsize=fs - 1)
    ax.annotate('', (28, 33.5), (11, 33.5), arrowprops=dict(arrowstyle='->'))
    ax.text(19.5, 34.3, '背後（w）', ha='center', fontsize=fs - 1)
    ax.axhline(0, color='#8b3a0e', lw=0.6, ls=':')
    ax.set_aspect('equal')
    ax.set_xlim(-30, 34)
    ax.set_ylim(-40, 37)
    ax.set_title('② 感測處剖面（沿光束；縱軸 n＝垂直軌道，0＝軌道）', fontsize=13, loc='left')
    ax.set_xlabel('w（0＝背牆正面，往背後為正）')

    # ③ 側視 -----------------------------------------------------------------
    ax = fig.add_subplot(gsp[0, 2])
    A_, C_ = parts['A'], parts['C']
    yb0, yb1 = A_.outline.bounds[1], A_.outline.bounds[3]
    ax.add_patch(Rectangle((yb0, 0), yb1 - yb0, 3, fc=wood, ec='k'))
    ax.axhline(0, color='#555', lw=1)
    ytop = y_walltop(X_L)
    _patch(ax, Polygon([world_of(0, 0), world_of(0, T_PLY), world_of(ytop, T_PLY), world_of(ytop, 0)]), fc=wood, ec='k', lw=0.9)
    yr = y_walltop(X_R)
    ax.plot(*zip(world_of(yr, -2), world_of(yr, T_PLY + 2)), color='#777', ls='--', lw=0.8)
    ax.text(*world_of(yr, T_PLY + 3), '背牆右端頂', fontsize=fs - 2, color='#777', va='center')
    _patch(ax, C_.outline, fc='#e9c99a', ec='k', lw=0.9)
    sb_top, sb_bot = Y_O, Y_O - STRIP_H / math.cos(TR)
    _patch(ax, Polygon([world_of(sb_bot, -T_PLY), world_of(sb_bot, 0), world_of(sb_top, 0), world_of(sb_top, -T_PLY)]),
           fc=wood2, ec='#7a4b1c', lw=0.9)
    _patch(ax, Polygon([world_of(Y_O, -2.4), world_of(Y_O, 0), world_of(Y_O + 28 * math.cos(TR), 0),
                        world_of(Y_O + 28 * math.cos(TR), -2.4)]), fc='#cfcfcf', ec='#888', alpha=0.8)
    for nm, g in module_section(n_sb_on(H0)).items():
        if nm != '元件':
            _patch(ax, Polygon([world_of(Y_O + n * math.cos(TR), w) for w, n in g.exterior.coords]),
                   fc=mod, ec='#1d5c33', alpha=0.35, lw=0.6)
    _patch(ax, Polygon([world_of(Y_O + n * math.cos(TR), w) for w, n in shim_poly(H0).exterior.coords]),
           fc=shim_c, ec='#9a5a00', lw=0.8)
    p0 = world_of(0, T_PLY)
    ax.plot([p0[0], p0[0]], [p0[1], p0[1] + 70], color='#555', ls=':', lw=1)
    ax.text(p0[0] - 2, p0[1] + 50, f'後仰 {TILT_DEG:g}°', fontsize=fs + 1, ha='right')
    ax.text(*world_of(ytop * 0.85, T_PLY + 3), '背牆 B', fontsize=fs)
    ax.text(C_.outline.bounds[2] + 2, 22, '支撐 C\n（兩端各一片，\n斜邊榫插背牆、\n下緣榫插底板）', fontsize=fs - 1)
    ax.text(yb0, -7, f'底板 A（背牆斜插、支撐直插；後方多留 {BASE_BACK:g} 防後翻）', fontsize=fs - 1)
    q = world_of(sb_top, -T_PLY)
    ax.annotate('擋幣板 D（上緣＝軌道）＋硬幣', q, (q[0] - 45, q[1] + 12), fontsize=fs - 1, arrowprops=dict(arrowstyle='->'))
    q = world_of(Y_O - 8, 12)
    ax.annotate('感測處的模組＋墊片\n（從右邊看）', q, (yb1 - 8, 50), fontsize=fs - 1, color='#1d5c33',
                arrowprops=dict(arrowstyle='->', color='#1d5c33'))
    ex = world_of(Y_END, -1.2)
    ax.plot(*ex, marker='o', color='#c0392b', ms=6)
    ax.annotate(f'出口（右端，軌道末端）\n離桌面約 {world_of(Y_END, 0)[1]:.0f} mm', ex, (ex[0] - 48, ex[1] - 22), fontsize=fs - 1,
                color='#c0392b', arrowprops=dict(arrowstyle='->', color='#c0392b'))
    ax.set_aspect('equal')
    ax.set_xlim(yb0 - 45, yb1 + 32)
    ax.set_ylim(-11, world_of(ytop, 0)[1] + 8)
    ax.set_title('③ 側視（從右邊看；y 往背後、z 往上）', fontsize=13, loc='left')
    ax.set_xlabel('y（往背後）')
    ax.set_ylabel('z（離桌面）')
    fig.canvas.draw()
    ytop_ax = max(a.get_position().y1 for a in fig.axes)
    fig.suptitle('光耦簡易測試原型 示意圖（模組尺寸全部是暫定值；改 make_proto.py 的 MODULE 後重跑會更新）',
                 fontsize=15, y=ytop_ax + 0.06)
    fig.savefig(path, dpi=100, bbox_inches='tight')
    plt.close(fig)


# =============================================================================
# 零件表
# =============================================================================
def write_csv(parts, path):
    A, B, C, D, F = (parts[k] for k in 'ABCDF')

    def sz(P):
        x0, y0, x1, y1 = P.outline.bounds
        return f'{x1 - x0:.1f}×{y1 - y0:.1f}'

    rows = [('代號', '名稱', '數量', '尺寸(mm)', '用途')]
    rows.append(('A', '底板', 1, sz(A) + '（3 合板）',
                 f'放桌上；{len(FOOT_X)} 個斜插槽（{FOOT_TAB_W + 2 * C_TAB:.1f}×{FOOT_SLOT_Y[1] - FOOT_SLOT_Y[0]:.2f}，背牆 30° 斜插）＋4 個支撐槽'))
    rows.append(('B', '背牆', 1, sz(B) + '（含下緣榫）',
                 f'後仰 30°（相當於正式機 #26）；感測窗 {WIN_W:.1f}×{WIN_H:.1f}、光孔 {len(LH_S)} 個 {LH_W}×{LH_N_TOP - LH_N_BOT:.1f}；'
                 f'正面雕放幣線 S5/S10/S50 與擋幣板下緣對位線'))
    rows.append(('C', '支撐', 2, sz(C) + '（含榫）', '30° 支撐，放兩端；斜邊 2 榫插背牆、下緣 2 榫插底板'))
    rows.append(('D', '擋幣板', 1, f'{S_END - S_START:.1f}×{STRIP_H:.1f}',
                 f'白膠黏在背牆正面框內；上緣＝軌道（斜 20°）；同形感測窗，窗頂留軌道條 {STRIP_BAR}'))
    for k in sorted((k for k in parts if k.startswith('E')), key=lambda k: int(k[1:])):
        E = parts[k]
        note = '（暫定尺寸時：模組頂到軌道條）' if abs(E.height - H0) < 1e-9 else ''
        nsb = n_sb_on(E.height)
        bm = nsb + M['beam_sb']
        if nsb > N_STRIP + 1e-9:
            bm = '暫定尺寸時塞不進（模組比暫定小時用）'
        elif bm - M['aperture'] / 2 < LH_N_BOT:
            bm = f'暫定尺寸時光束約 {bm:.1f}，低於軌道可用高（光窗會被擋幣板上緣擋到；模組比暫定大時用）'
        else:
            bm = f'暫定尺寸時光束離軌道約 {bm:.1f}'
        rows.append((k, f'墊片 {E.height:.1f}', 1, sz(E) + f'（撐高 {E.height:.1f}）',
                     f'雕「{k}  {E.height:.1f}」；從前方塞到 PCB 下面、擋耳靠擋幣板正面'
                     f'（本體正下方一片，PCB 另一端再撐一片）；{bm}{note}'))
    rows.append(('F', '對位塞', 1, sz(F), '黏擋幣板時對齊兩片的窗：背牆正面朝上平放，窗裡的桌面上先墊約 1.5 mm 厚、比窗小的東西'
                 '（例如 5 張名片剪成約 22×16），F 包一層保鮮膜後放進背牆的窗、坐在上面，凸出約 1.5，擋幣板的窗套上去；'
                 '不要用硬幣墊（四種硬幣都比窗的短邊大，會把背牆墊高）；窗挖下來的那塊也可以代替 F'))
    rows.append(('—', '槽型 LM393 光耦模組', 1, '自備（暫定槽寬 10）', '跨裝在感測窗；收到後實量，改 MODULE 重跑；槽寬小於 6.5 的不能用'))
    rows.append(('—', 'ESP32 開發板＋擴展板', 1, '自備', '擴展板 G27 那一排要有 S／V／G；黃色跳帽設 3.3V'))
    rows.append(('—', '母母杜邦線', 3, '自備', '光耦 OUT／VCC／GND 接到擴展板 G27 那一排的 S／V／G；先插在模組上再裝模組'))
    rows.append(('—', 'USB 傳輸線', 1, '自備', '要能傳資料（不是只能充電的線）；上傳程式、看序列埠'))
    rows.append(('—', 'TM1637 四位數顯示器（可不接）', 1, '自備', '再加 4 條母母杜邦線：CLK→G14、DIO→G13、VCC→V、GND→G'))
    rows.append(('—', '白膠', '適量', '—', '全部用白膠，不用螺絲'))
    rows.append(('—', '杯子或碗', 1, f'杯口低於約 {world_of(Y_END, 0)[1] - 8:.0f} mm', '放在右端外側接滾出的硬幣（不用做）'))
    with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
        csv.writer(fh).writerows(rows)
    return rows


# =============================================================================
# 主程式
# =============================================================================
def main():
    parts = build_parts()
    W, H, placed = best_layout(parts)
    write_svg(OUT_SVG, W, H, placed)
    svg = read_svg(OUT_SVG)
    results = run_checks(parts, placed, svg, W, H)
    draw_preview(svg, placed, W, H, OUT_PREVIEW)
    draw_schematic(parts, OUT_FIG)
    write_csv(parts, OUT_CSV)
    print(f'板子 {W:g}×{H:g} mm；零件 {len(placed)} 片')
    print(f'窗 s {WIN_S0:.2f}～{WIN_S1:.2f}（寬 {WIN_W:.1f}）、n {N_WB:.2f}～{N_STRIP:.2f}（高 {WIN_H:.1f}）；'
          f'墊片 {", ".join(f"{h:.1f}" for h in SHIMS)}；H0＝{H0:.1f}')
    print('自我檢查：')
    nfail = 0
    for name, ok, detail in results:
        nfail += not ok
        print(f'  [{"PASS" if ok else "FAIL"}] {name}：{detail}')
    print('全部 PASS' if nfail == 0 else f'{nfail} 項 FAIL')
    for p in (OUT_SVG, OUT_PREVIEW, OUT_FIG, OUT_CSV):
        print('輸出', os.path.relpath(p, os.path.dirname(HERE)))
    return nfail


if __name__ == '__main__':
    sys.exit(1 if main() else 0)

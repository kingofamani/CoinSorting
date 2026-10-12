"""電子盒（#37 背面兩層掛勾盒）＋TM1637 正面窗：v2 子系統 ebox。

把 design/ebox_final/spec.md（裁判合併版）寫成產生器，回傳 INTERFACE.md 約定的 dict：

* #24 前面板：TM1637 LED 窗、4 個 M2 孔、Logo（雕刻 path1-5-9＋9 個菱形切穿孔）依
  params.LOGO_PLAN 平移（'L2' 顯示窗正下方〔預設〕／'L1' 「10」右邊）。Logo 用
  translate_cut（9 個孔）＋move_engrave（雕刻）搬，原位置自動補回實料。
* #26 內牆：頂邊 L 形缺口（A 段放 PCB 與 M2 螺帽；B 段放彎針、杜邦頭與往上折的線）。
* #5（10|50 隔板）：前上角讓位給 TM1637 背面零件。只回傳本子系統的 subtract；crosstrack
  另有 #5 的修改（刪長榫等），compose 合併後 #5 只剩第二小榫＋後榫（spec b-3）。
* #37 後面板：4 個掛勾槽、頂邊顯示器線 U 形缺口、感測器線孔（crosstrack 的 S5/S10/S50
  線從右側空腔穿到背面；crosstrack spec b-7 規定位置由電子盒決定，所以由本模組開）、
  選用雕刻（槽旁箭頭、「感測器線」）。
* 新零件 EB-WL／EB-WR／EB-B／EB-T／EB-S／EB-F／EB-E（各 1）、EB-K 防拔鍵（選用，2）。

用法
----
    from laser_v2.catalog import load_catalog
    from laser_v2 import ebox
    res = ebox.build(load_catalog())        # edits / new_parts / notes / warnings / checks / groups
    ebox.recheck(cat, {'crosstrack': r_ct, 's1': r_s1, 'ebox': res})   # 整合時用實際結果重查
    python -m laser_v2.ebox                 # 印摘要（含全部檢查）
    python -m laser_v2.ebox --selftest      # 名目參數下和 design/ebox_final/geometry_final.json 比對，並跑 L1

座標
----
* 組裝座標 (U,V,W') 同 frames.py：U 0＝右端轉盤側→246 左端（從背面看往右增加）；V 0＝面板頂
  往下；W' 0＝#26 背面，往後為正（#24 −6～−3、#26 −3～0、#37 29～32）。
* edits 的幾何一律換成該零件的原始頁座標（frames 的 4×4 矩陣），符合 INTERFACE.md。
* 新零件的區域座標 (a,b)＝板面兩個組裝軸各減外包最小值（每片的對應寫在 notes 與
  NEW_PART_MAP），與 geometry_final.json 的 outline_local 相同。

參數
----
* 模組尺寸讀 params.TM1637／ESP32_BOARD／BATTERY_9V（spec d-1 標「要量」的鍵都已列在 params.py，
  2026-10-07 補；同名鍵覆蓋本檔 *_DEFAULT）；字典裡沒有的欄位才用本檔 *_DEFAULT 的值（後備）。
  注意 TM1637 的 hole_dx／hole_dy 是半距（孔中心離 PCB 中心），實量孔距要除以 2。
* 板厚 params.T_PLY、榫槽餘隙 params.C_TAB、掛勾槽餘隙 params.C_HOOK、Logo 方案 params.LOGO_PLAN。
* 本子系統自己的設計參數（顯示器位置、盒子位置、掛勾、開關…）在下面「設計參數」一節。

自動規則（spec d-2）
--------------------
1. PCB 上緣 Vp＝max(V5, 上排 M2 孔到 #24 頂邊料寬 ≥2 所需)，0.5 進位；不用螺絲時 V5。
2. 左牆 U_WL＝min(146, 擴展板左端 −6 −板厚)；下限＝S1 禁區右界 +1，超過就警告。
3. 電池口袋用 max(實測, 9V 標準 48.5×26.5×17.5)，實品較小不縮。
4. Logo：先用 LOGO_PLAN 指定的方案；不合條件（外框內縮 3、離窗／螺絲頭／雕刻／斜槽／感測窗／
   轉盤區 ≥3、菱形孔離其他孔 ≥2、孔背後不露出 #26 缺口或顯示器線）就改另一個方案，兩個都不行
   才重新搜尋，三種情況都寫進 warnings。
5. 盒底上限 V77.5（離 #12／#21 ≥2）。

跨子系統資料（名目值，整合時要用各模組實際結果重查）
------------------------------------------------------
* crosstrack：design/crosstrack_final/geometry_final.json 的 #24 感測窗、「5」「1」雕刻搬移量、
  #5/#6/#7 v2 外形、#26 新 #6 槽（只用於檢查與 Logo 避讓，不輸出）。
* S1：design/s1wall_final/geometry_s1_final.json 的背蓋 S1-F、模組後端（PCB、排針）、#37 卡匣窗／
  B1 槽／M3 孔。「S1 禁區」由這些實際範圍算出（見 s1_zone()），不用 ebox spec 的估計值。
* build(cat, others={'s1': …, 'crosstrack': …}) 或 recheck(cat, results) 會改用那兩個模組 build() 的
  實際結果（mods_s1 的 keepout 與 #37/#26 切割、mods_crosstrack 的 #24/#26 切割、雕刻搬移、隔板外形）。

檢查（checks）
--------------
由幾何算得出的都移植自 design/ebox_final/checks.py：A 顯示器／#24、B #26 缺口、C #5、
D 顯示器零件 ↔ 結構、E 硬幣路徑、F #37、G 電子盒 ↔ 機身（含安裝掃掠）、H 盒內、K 用板。
3D 距離：兩個擠出體同軸、或其中一個是長方體時用精確公式；其餘用參考程式的取樣法（偏大 ≤0.2）。
I 翻倒穩定（要質量模型）與 J 可視性（要眼睛位置模型）需要外部模型，本模組不做，
數字見 spec e-6、e-7。
"""
from __future__ import annotations

import copy
import functools
import json
import math
import re
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiPoint, Point, Polygon, box
from shapely.ops import unary_union
from svgpathtools import parse_path

from . import catalog as C
from . import frames as F
from . import params as PRM
from . import textpath as TP

HERE = Path(__file__).resolve().parent
DESIGN = HERE / 'design'
REF_JSON = DESIGN / 'ebox_final' / 'geometry_final.json'
REF_CHECKS = DESIGN / 'ebox_final' / 'checks.json'
CT_JSON = DESIGN / 'crosstrack_final' / 'geometry_final.json'
S1_JSON = DESIGN / 's1wall_final' / 'geometry_s1_final.json'

AXI = {'U': 0, 'V': 1, 'W': 2}
PLANE = {'W': ('U', 'V'), 'U': ('W', 'V'), 'V': ('U', 'W')}   # 擠出軸 → 板面兩軸

# ---------------------------------------------------------------------------
# 機身固定尺寸（組裝座標；由 frames 與原始檔量得，_ref() 會用幾何再核一次）
# ---------------------------------------------------------------------------
V_TOP = 4.0            # U≥100 處 #24、#37 頂邊的 V
V_TOP_26 = 14.0        # U≥133 處 #26 頂邊（也是隔板頂）
W24_FRONT, W24_BACK = F.W24            # #24 W' −6～−3
W37_IN = F.W37_IN                      # #37 內面 29.0
W37_OUT = F.W37_IN + F.T_BOARD         # #37 外面 32.0
TURNTABLE_U = 113.0    # 轉盤區 U<113（Logo 不可進入）

# ---------------------------------------------------------------------------
# 模組尺寸的暫定值（params 的同名字典沒有的鍵才用這裡的值）
# ---------------------------------------------------------------------------
DISP_DEFAULT = dict(
    pcb_w=42.0, pcb_h=24.0, pcb_t=1.6,          # PCB（params.TM1637 會覆蓋）
    body_w=30.0, body_h=14.0, body_H=7.2,       # 0.36 吋四位 LED 塊
    body_dx=0.0, body_dy=0.0,                   # LED 塊中心相對 PCB 中心（+dx 往觀看者右手 −U；+dy 往下 +V）
    back_h=2.6, back_inset=1.0,                 # 背面零件最高、零件區離 PCB 邊
    # 固定孔（沒有孔就 use_screws=False，#24 不切 M2 孔）。hole_dx／hole_dy 是「半距」：孔中心離 PCB 中心
    # 的距離（孔在 Uc±hole_dx、Vc±hole_dy）。實量的孔距（全距，例如 38×20）要除以 2 再填（19、10）。
    hole_d=2.2, hole_dx=19.0, hole_dy=10.0,
    use_screws=True,
    hdr_mode='RA',                              # 'RA' 彎針朝觀看者右手（−U）；'STRAIGHT' 直針朝後
    hdr_pins=4, hdr_pitch=2.54, hdr_dy=0.0, hdr_body=2.5, pin_h=1.27,
    dup_len=14.0, dup_sq=2.54, dup_gap=1.0, wire_bend=5.5,
)
BOARD_DEFAULT = dict(
    L=78.0, W=53.5, t=1.6,                      # 擴展板（params.ESP32_BOARD 的 L、W 會覆蓋）
    # M3 尼龍；hole_inset＝四個孔中心離板邊的距離（四孔都一樣）。實品四孔離邊不相等時要改程式（M.BOARD_HOLES）
    standoff=4.8, hole_inset=3.0, hole_d=3.4,
    c_end=0.5, c_top=1.0, c_bot=1.0,            # 板端到右牆內面、板上緣到電池架、板下緣到底板下緣
    hdr_h=8.5, dev_t=1.6, dev_comp=3.0, dev_len=55.0, dev_w=28.0, usb_inset=2.0,
    gvs_V_off=6.0, male_h=2.5, dup_len=14.0, bend=5.5,
    usb_V_off=26.75, btn_dv=8.5, usb_w=8.0, usb_h=2.6, usb_plug=(11.0, 8.0),   # 插頭外殼 (V, W')
    dc_V_off=6.5, dc_d=9.0, dc_h=11.0, dc_len=14.0, dc_plug_d=10.0,
    en_V_off=(11.7, 25.7), pin1_from_antenna=5.0, pitch=2.54,
)
BATT_DEFAULT = dict(L=48.5, W=26.5, Tk=17.5,    # 9V：L 沿 U、Tk 沿 V、W 沿 W'（params.BATTERY_9V 的 L/W/T 會覆蓋）
                    c=0.25, clip=12.5, proud=4.0)   # 口袋餘隙、電池扣＋線彎預留、頂面凸出盒頂
BATT_STD = (48.5, 26.5, 17.5)                   # 9V 標準最大值（口袋不小於此）

# ---------------------------------------------------------------------------
# 設計參數（spec d-1；改這裡會連動所有切割與新零件）
# ---------------------------------------------------------------------------
MIN_WEB = 2.0          # 新切割留下的料寬下限
DISP_UR = 193.5        # TM1637 PCB 右緣（觀看者右手，U 小側）
DISP_VP = None         # PCB 上緣 V；None＝自動（規則 1）
C_WIN = 0.3            # #24 LED 窗單邊餘隙
C_SCREW = 0.1          # M2 孔 Ø(hole_d + 2·C_SCREW)
C_NOTCH = 0.5          # #26 缺口對 PCB／杜邦頭／螺帽
C_DIV = 0.8            # #5 前上角對 PCB 背面零件
NUT_M2 = dict(d_circ=4.62, t=1.6)
SCREW_M2 = dict(L=8.0, head_d=3.8, head_h=1.3)
WIRE_D = 1.4
NOTCH26_TOP_V = 13.0   # #26 缺口多邊形上緣畫到 V13（頂邊 V14 外 1 mm，確保切穿）

# 感測器線盒端 1×3 杜邦頭插哪一欄（spec a-2 第 5 步、a-3 第 3 步）；盒端標籤照這個寫「S5→G26」
SENSOR_PINS = {'S1': 'G27', 'S5': 'G26', 'S10': 'G25', 'S50': 'G33'}

CABLE_U = 168.0                            # 顯示器線越過機頂的 U（#37 頂邊 U 形缺口中心）
CABLE_NOTCH_37 = dict(w=6.5, depth=4.5)    # 寬（U）× 深（V，從頂邊 V4 往下）
CABLE_NOTCH_37_OUT = 2.0                   # 缺口多邊形畫到頂邊外 2 mm（V2）
CABLE_RUN_V = (5.5, 9.5)                   # 線在 #24 背面水平段的 V 範圍

LOGO_SRC = 'path1-5-9'                     # #24 Logo 雕刻
LOGO_PLANS = {'L2': (-13.5, 17.0),         # 顯示窗正下方、「10」「50」之間（名目最小距 3.38）
              'L1': (-50.5, 7.0)}          # 「5」(crosstrack 新位置) 與「10」之間（名目 3.50）
LOGO_CLEAR = 3.0                           # Logo 離其他東西
LOGO_HOLE_CLEAR = 2.0                      # Logo 菱形孔離其他孔

BOX = dict(
    U_WL=146.0,        # 左牆 −U 面上限（自動規則 2 只會往 −U 移）
    U_WR=237.0,        # 右牆內面（外面 240，#37 掛勾槽到 #37 左緣 U243 料寬 2.8）
    V_top=V_TOP,       # 頂板上面（＝#37 頂邊）
    W_front=W37_OUT + 0.25,   # 牆前緣（#37 外面 + 0.25）
    W_back=70.0,       # 牆後緣
    gap=3.0,           # #37 外面到底板 EB-B 前面
    top_W0=50.0,       # 頂板開關區前緣 W'
    wl_notch=(32.25, 42.0, 41.0, 53.0),   # 左牆前緣排線口 W'0,W'1,V0,V1
    wl_bay=6.0,        # 擴展板左端到左牆內面的走線灣下限
    V_bot_max=77.5,    # 盒底上限（規則 5）
)
HOOK = dict(lip_W0=25.0, lip_back=28.85, neck_h=6.0, lip_len=6.0, levels=(13.5, 29.0), chamfer=1.0)
SWITCH = dict(cut_a=9.0, cut_b=13.5, body_depth=14.0, U0=152.0, W0=53.0)   # 13.5×9 面板式，轉 90°
SERVICE_WIN_C = 1.0                          # USB/DC 服務窗：插頭外殼外加 1.0
SENSOR_HOLE_37 = (88.0, 100.0, 40.0, 46.0)   # 感測器線孔 U0,U1,V0,V1（crosstrack 要求 U72.1～104.9 內 ≥10×5）
MOTOR_SW = (40.25, 53.75, 1.0, 19.23)        # 原馬達開關（U0,U1,V0,V1；參考值，只用於檢查距離）
S1_ZONE_MARGIN = 0.5                         # S1 禁區：S1 實際外包每邊再加
S1_PLUG_SPACE = 15.0                         # S1 排針後方杜邦頭＋拔插手指空間（W'）
EB_GROUP = 'ebox'                            # 新零件同板群組
LABEL_SIZE = 3.0                             # 新零件代號雕刻字高
ENGRAVE_37 = True                            # #37 選用雕刻（槽旁箭頭、「感測器線」）

# 硬幣（spec e-2 的模型）
COIN_D = {'1': 20.0, '5': 22.0, '10': 26.0, '50': 28.0}
V_EXIT_26, V_EXIT_37 = 98.0, 82.0            # 出口平面 V＝98−16·W'/29（貼 #26 V98、貼 #37 V82）


# ===========================================================================
# 參數
# ===========================================================================
def design_params(overrides: dict | None = None) -> NS:
    """組出本子系統用的參數（params.py 的模組尺寸＋本檔設計參數）。

    overrides：{'DISP.pcb_w': 46, 'CABLE_U': 166, 'LOGO_PLAN': 'L1', …}（敏感度或測試用）。"""
    pr = NS()
    pr.T = float(PRM.T_PLY)
    pr.C_TAB = float(PRM.C_TAB)
    pr.C_HOOK = float(PRM.C_HOOK)
    pr.MIN_WEB = MIN_WEB
    pr.DISP = {**DISP_DEFAULT, **dict(PRM.TM1637)}
    pr.BOARD = {**BOARD_DEFAULT, **dict(PRM.ESP32_BOARD)}
    b9 = dict(PRM.BATTERY_9V)
    pr.BATT = {**BATT_DEFAULT, **{k: v for k, v in b9.items() if k not in ('T',)}}
    if 'T' in b9:
        pr.BATT['Tk'] = b9['T']
    for k in ('DISP_UR', 'DISP_VP', 'C_WIN', 'C_SCREW', 'C_NOTCH', 'C_DIV', 'WIRE_D', 'CABLE_U',
              'CABLE_RUN_V', 'SERVICE_WIN_C', 'SENSOR_HOLE_37', 'MOTOR_SW'):
        setattr(pr, k, copy.deepcopy(globals()[k]))
    for k in ('NUT_M2', 'SCREW_M2', 'CABLE_NOTCH_37', 'BOX', 'HOOK', 'SWITCH'):
        setattr(pr, k, copy.deepcopy(globals()[k]))
    pr.LOGO_PLAN = PRM.LOGO_PLAN
    for key, v in (overrides or {}).items():
        if '.' in key:
            a, b = key.split('.', 1)
            getattr(pr, a)[b] = v
        else:
            setattr(pr, key, v)
    pr.LOGO_SHIFT, pr.LOGO_LABEL = _logo_plan(pr.LOGO_PLAN)
    alt = 'L1' if pr.LOGO_LABEL == 'L2' else 'L2'
    pr.LOGO_SHIFT_ALT, pr.LOGO_ALT_LABEL = LOGO_PLANS[alt], alt
    return pr


def _logo_plan(plan):
    if isinstance(plan, str):
        if plan not in LOGO_PLANS:
            raise ValueError(f'params.LOGO_PLAN 只能是 {list(LOGO_PLANS)} 或 (ΔU, ΔV)，收到 {plan!r}')
        return tuple(LOGO_PLANS[plan]), plan
    dU, dV = plan
    return (float(dU), float(dV)), f'自訂 ({dU}, {dV})'


# ===========================================================================
# 幾何工具
# ===========================================================================
def rect(a0, a1, b0, b1):
    return box(min(a0, a1), min(b0, b1), max(a0, a1), max(b0, b1))


def pieces(g) -> int:
    if g.is_empty:
        return 0
    return 1 if g.geom_type == 'Polygon' else len(g.geoms)


def min_web(g, start: float = 0.1, stop: float = 6.0) -> float:
    """最小料寬（近似）：負緩衝 w/2 後件數改變的最小 w（0.1 步，上限 6）。"""
    n0 = pieces(g)
    w = start
    while w < stop:
        h = g.buffer(-w / 2)
        if h.is_empty or pieces(h) != n0:
            return round(w, 1)
        w += 0.1
    return stop


class Solid:
    """擠出體：截面 poly（PLANE[axis] 兩軸）× 擠出軸範圍 rng（移植自 design/ebox_final/base.py）。"""

    def __init__(self, name, axis, poly, rng, kind='', is_box=None):
        self.name, self.axis, self.poly, self.rng, self.kind = name, axis, poly, (float(min(rng)), float(max(rng))), kind
        if is_box is None:
            is_box = poly.geom_type == 'Polygon' and abs(poly.area - poly.envelope.area) < 1e-9 and len(poly.interiors) == 0
        self.is_box = bool(is_box)

    def bounds3(self):
        a, b = PLANE[self.axis]
        x0, y0, x1, y1 = self.poly.bounds
        lo = [0.0] * 3
        hi = [0.0] * 3
        lo[AXI[a]], hi[AXI[a]] = x0, x1
        lo[AXI[b]], hi[AXI[b]] = y0, y1
        lo[AXI[self.axis]], hi[AXI[self.axis]] = self.rng
        return np.array(lo), np.array(hi)

    def as_axis(self, axis):
        """長方體換成沿另一軸擠出的表示法（只限 is_box）。"""
        lo, hi = self.bounds3()
        a, b = PLANE[axis]
        return Solid(self.name, axis, rect(lo[AXI[a]], hi[AXI[a]], lo[AXI[b]], hi[AXI[b]]),
                     (lo[AXI[axis]], hi[AXI[axis]]), self.kind, True)

    def dist_points(self, P3):
        a, b = PLANE[self.axis]
        P3 = np.asarray(P3, float)
        pts = shapely.points(P3[:, AXI[a]], P3[:, AXI[b]])
        d2 = shapely.distance(self.poly, pts)
        c = P3[:, AXI[self.axis]]
        lo, hi = self.rng
        dc = np.maximum(0, np.maximum(lo - c, c - hi))
        return np.sqrt(d2 ** 2 + dc ** 2)

    def sample(self, step=0.4, surface=False):
        """取樣點。surface=True 只取表面（側面＋兩端蓋）：兩實體最近距離一定在表面上，結果相同但快很多。"""
        a, b = PLANE[self.axis]
        x0, y0, x1, y1 = self.poly.bounds
        xs = np.arange(x0, x1 + 1e-9, step)
        ys = np.arange(y0, y1 + 1e-9, step)
        X, Y = np.meshgrid(xs, ys)
        X = X.ravel()
        Y = Y.ravel()
        ins = shapely.contains_xy(self.poly.buffer(1e-6), X, Y)
        X, Y = X[ins], Y[ins]
        bds = [self.poly] if self.poly.geom_type == 'Polygon' else list(self.poly.geoms)
        bx, by = [], []
        for g in bds:
            for ring in [g.exterior] + list(g.interiors):
                L = ring.length
                ts = np.linspace(0, L, max(8, int(L / step)))
                pp = np.array([[ring.interpolate(t).x, ring.interpolate(t).y] for t in ts])
                bx.append(pp[:, 0])
                by.append(pp[:, 1])
        BX, BY = np.concatenate(bx), np.concatenate(by)
        X = np.r_[X, BX]
        Y = np.r_[Y, BY]
        lo, hi = self.rng
        cs = np.unique(np.r_[np.arange(lo, hi, step), hi])
        blocks = []
        for k, cv in enumerate(cs):
            if surface and 0 < k < len(cs) - 1:
                xs, ys = BX, BY                       # 中間層只取側面
            else:
                xs, ys = X, Y
            blk = np.zeros((len(xs), 3))
            blk[:, AXI[a]] = xs
            blk[:, AXI[b]] = ys
            blk[:, AXI[self.axis]] = cv
            blocks.append(blk)
        return np.vstack(blocks)


def boxsolid(name, u0, u1, v0, v1, w0, w1, kind=''):
    return Solid(name, 'W', rect(u0, u1, v0, v1), (min(w0, w1), max(w0, w1)), kind, True)


def dist(A: Solid, B: Solid, step: float = 0.35) -> float:
    """兩擠出體最小距離（0＝接觸或重疊）。同軸或其一是長方體：精確；否則取樣（參考程式的方法）。"""
    la, ha = A.bounds3()
    lb, hb = B.bounds3()
    gap = np.maximum(0, np.maximum(la - hb, lb - ha))
    if np.linalg.norm(gap) > 40:
        return float(np.linalg.norm(gap))
    if A.axis != B.axis:
        if A.is_box:
            A = A.as_axis(B.axis)
        elif B.is_box:
            B = B.as_axis(A.axis)
    if A.axis == B.axis:
        d2 = A.poly.distance(B.poly)
        di = max(0.0, A.rng[0] - B.rng[1], B.rng[0] - A.rng[1])
        return float(math.hypot(d2, di))
    va = np.prod(ha - la + 0.1)
    vb = np.prod(hb - lb + 0.1)
    S, O = (A, B) if va <= vb else (B, A)
    st = max(step, (min(va, vb) / 60000.0) ** (1 / 3))
    pts = S.sample(st, surface=True)
    # 加速：把大的那個截面裁到取樣體外包 ±m 的範圍、只留離它外包 <m 的取樣點
    # （最近點一定在裡面，只要結果 < m 就和不裁時同一個值）
    m = 10.0
    ls, hs = S.bounds3()
    a, b = PLANE[O.axis]
    win = rect(ls[AXI[a]] - m, hs[AXI[a]] + m, ls[AXI[b]] - m, hs[AXI[b]] + m)
    oc = O.poly.intersection(win)
    if not oc.is_empty:
        Oc = Solid(O.name, O.axis, oc, O.rng, is_box=False)
        lo, hi = Oc.bounds3()
        gb = np.linalg.norm(np.maximum(0, np.maximum(lo - pts, pts - hi)), axis=1)
        near = pts[gb < m]
        if len(near):
            d = float(Oc.dist_points(near).min())
            if d < m - 1e-9:
                return d
    return float(O.dist_points(pts).min())


def coords(poly, nd=3):
    return [(round(float(x), nd), round(float(y), nd)) for x, y in poly.exterior.coords][:-1]


# ---------------------------------------------------------------------------
# 組裝座標 ↔ 頁座標
# ---------------------------------------------------------------------------
def to_page(pid: str, geom, third: float | None = None):
    """零件板面上的組裝座標幾何（兩軸＝PLANE[板面法線軸]）→ 該零件原始頁座標。"""
    fr = F.frame(pid)
    ax, lo, hi = fr.plane()
    a, b = PLANE[ax]
    third = (lo + hi) / 2 if third is None else third
    Ti = fr.Tinv
    ia, ib, ik = AXI[a], AXI[b], AXI[ax]
    co = [Ti[0, ia], Ti[0, ib], Ti[1, ia], Ti[1, ib],
          Ti[0, ik] * third + Ti[0, 3], Ti[1, ik] * third + Ti[1, 3]]
    return affinity.affine_transform(geom, co)


def page_delta(pid: str, dA: float, dB: float):
    """板面組裝座標的平移量 → 頁座標平移量 (dx, dy)。"""
    fr = F.frame(pid)
    ax = fr.plane()[0]
    a, b = PLANE[ax]
    Ti = fr.Tinv
    dx = Ti[0, AXI[a]] * dA + Ti[0, AXI[b]] * dB
    dy = Ti[1, AXI[a]] * dA + Ti[1, AXI[b]] * dB
    return float(dx), float(dy)


def asm_geom(cat, pid, axes=('U', 'V')):
    fr = F.frame(pid)
    return fr.geom_asm(cat[pid].geom, fr.thickness / 2, axes)


# ===========================================================================
# 跨子系統資料（名目值）
# ===========================================================================
@functools.lru_cache(maxsize=1)
def _ct_json() -> dict:
    return json.loads(CT_JSON.read_text(encoding='utf-8'))


@functools.lru_cache(maxsize=1)
def _s1_json() -> dict:
    return json.loads(S1_JSON.read_text(encoding='utf-8'))


def s1_zone() -> dict:
    """S1 卡匣在 #37 背面（W'≥32）的實際範圍＋每邊 S1_ZONE_MARGIN＋排針後方 S1_PLUG_SPACE。

    來源：geometry_s1_final.json 的背蓋 S1-F（asm 外形、W 範圍）與 module_boxes_UVW 中 W'>32 的部分
    （PCB、焊點、元件、本體、後臂、排針）。名目：U91.08～130.48 × V50.2～78.5 × W'32～54.9，
    與 s1wall spec 寫給電子盒的「U91.1～130.5 × V50.2～78.5 × W'32～55」一致。"""
    J = _s1_json()
    bx = []
    cov = Polygon(J['new_parts']['S1-F']['asm']['exterior'])
    cw = J['new_parts']['S1-F']['W']
    b = cov.bounds
    bx.append(('S1-F 背蓋', b[0], b[2], b[1], b[3], float(cw[0]), float(cw[1])))
    for k, v in J['module_boxes_UVW'].items():
        if v[5] > W37_OUT:
            bx.append((f'S1 模組 {k}', v[0], v[1], v[2], v[3], max(v[4], W37_OUT), v[5]))
    m = S1_ZONE_MARGIN
    U = (min(x[1] for x in bx) - m, max(x[2] for x in bx) + m)
    V = (min(x[3] for x in bx) - m, max(x[4] for x in bx) + m)
    W = (W37_OUT, max(x[6] for x in bx) + S1_PLUG_SPACE)
    return dict(U=U, V=V, W=W, parts=bx)


def s1_cuts37() -> dict:
    """S1 在 #37 的開孔（組裝 U,V）：卡匣窗、B1 槽、2 個 M3 孔。"""
    J = _s1_json()['#37']
    out = {'S1 卡匣窗': Polygon(J['window']['asm_UV'])}
    for k, v in J['slots'].items():
        out[f'S1 {k} 槽'] = Polygon(v['asm_UV'])
    for i, h in enumerate(J['holes']):
        out[f'S1 M3 孔 {i + 1}'] = Point(*h['center_UV']).buffer(h['d'] / 2, 32)
    return out


def s1_engrave37() -> list:
    """S1 在 #37 的雕刻文字（近似外包，供本模組雕刻避讓）。"""
    out = []
    for e in _s1_json()['#37'].get('engrave', []):
        u, v = e['at_UV']
        h = e['h']
        w = _text_width(e['text'], h)
        out.append(rect(u - w / 2, u + w / 2, v - 0.85 * h, v + 0.25 * h))
    return out


# ===========================================================================
# 原始零件的參考幾何（不隨本模組參數變）
# ===========================================================================
def _engrave_pts(part) -> dict:
    out = {}
    for e, src in zip(part.engrave, part.engrave_src):
        pts = []
        for d in re.findall(r'\sd="([^"]+)"', e):
            p = parse_path(d)
            for sp in p.continuous_subpaths():
                for t in np.linspace(0, 1, 300):
                    z = sp.point(t)
                    pts.append((z.real, z.imag))
        out[src] = np.array(pts)
    return out


def _hole_srcs(part) -> list:
    """part.geom 每個 interior 對應的 cut_src（用 bbox 對）。"""
    bbs = []
    for d, src, cl in zip(part.cut_d, part.cut_src, part.cut_closed):
        if cl and src != part.cut_src[0]:
            x0, x1, y0, y1 = parse_path(d).bbox()
            bbs.append((src, (x0, y0, x1, y1)))
    out = []
    for ring in part.geom.interiors:
        b = Polygon(ring).bounds
        hit = [s for s, bb in bbs if max(abs(b[i] - bb[i]) for i in range(4)) < 0.05]
        out.append(hit[0] if len(hit) == 1 else None)
    return out


def _ref(cat) -> NS:
    """原始零件、crosstrack、S1 的參考幾何（組裝座標）。"""
    R = NS()
    fr24 = F.frame('#24')
    R.G24 = asm_geom(cat, '#24')
    R.G26 = asm_geom(cat, '#26')
    R.G37 = asm_geom(cat, '#37')
    R.H24 = [fr24.geom_asm(Polygon(h), fr24.thickness / 2, ('U', 'V')) for h in cat['#24'].geom.interiors]
    R.H24_SRC = _hole_srcs(cat['#24'])
    fr26 = F.frame('#26')
    R.H26 = [fr26.geom_asm(Polygon(h), fr26.thickness / 2, ('U', 'V')) for h in cat['#26'].geom.interiors]
    R.SLOT24 = max(R.H24, key=lambda h: h.area)                     # 斜槽
    R.ENG = {k: fr24.to_asm(v[:, 0], v[:, 1], 0)[:, :2] for k, v in _engrave_pts(cat['#24']).items()}
    if LOGO_SRC not in R.ENG:
        raise RuntimeError(f'#24 找不到 Logo 雕刻 {LOGO_SRC}')

    def hull(s, d=(0, 0)):
        return affinity.translate(MultiPoint([tuple(p) for p in R.ENG[s]]).convex_hull, *d)
    R.hull = hull
    lh = hull(LOGO_SRC)
    idx = [i for i, h in enumerate(R.H24) if h.area < 6 and lh.buffer(0.5).contains(h)]
    R.LOGO_HOLES = [R.H24[i] for i in idx]
    R.LOGO_HOLE_SRC = [R.H24_SRC[i] for i in idx]
    if len(R.LOGO_HOLES) != 9 or None in R.LOGO_HOLE_SRC:
        raise RuntimeError(f'#24 Logo 菱形孔應有 9 個且都對得到 cut_src，實得 {R.LOGO_HOLE_SRC}')
    R.LOGO = unary_union([lh] + R.LOGO_HOLES)
    R.OTHER_H24 = [h for i, h in enumerate(R.H24) if h is not R.SLOT24 and i not in idx]
    CTJ = _ct_json()
    R.CTJ = CTJ
    MV = CTJ['parts']['engrave_moves_24']
    R.ENG_NEW = {'「50」': hull('text1-6-4'), '「10」': hull('text2-1-3'),
                 '「5」(crosstrack 新位)': hull('text11-4-1', (MV['text11-4-1']['dU'], MV['text11-4-1']['dV'])),
                 '「1」(crosstrack 新位)': hull('text16-7-2', (MV['text16-7-2']['dU'], MV['text16-7-2']['dV']))}
    R.CT_WIN24 = unary_union([Polygon(CTJ['stations'][s]['win24']['UV']) for s in ('S5', 'S10', 'S50')])
    R.DIV_V2 = {pid: Polygon(CTJ['stations'][st]['divider']['new_outline']['WV'])
                for st, pid in (('S5', '#7'), ('S10', '#6'), ('S50', '#5'))}
    R.DIV_V2_LOCAL = {pid: Polygon(CTJ['stations'][st]['divider']['new_outline']['local'])
                      for st, pid in (('S5', '#7'), ('S10', '#6'), ('S50', '#5'))}
    R.CT_SLOT26_6 = Polygon(CTJ['parts']['#26_slot_tab6']['UV'])
    R.DIV_U = {pid: F.frame(pid).plane()[1:] for pid in ('#7', '#6', '#5')}
    e12 = np.array(cat['#12'].geom.exterior.coords)
    A = np.vstack([F.frame('#12').to_asm(e12[:, 0], e12[:, 1], z) for z in (0.0, F.T_BOARD)])
    R.G12_WV = MultiPoint([tuple(p) for p in A[:, [2, 1]]]).convex_hull
    R.G21_WV = F.frame('#21').geom_asm(cat['#21'].geom, 1.5, ('W', 'V'))
    R.G36_WV = F.frame('#36').geom_asm(cat['#36'].geom, 1.5, ('W', 'V'))
    R.G13_WV = F.frame('#13').geom_asm(cat['#13'].geom, 1.5, ('W', 'V'))
    # 硬幣開口（#26，U>110 由右到左＝1、5、10、50）
    R.OPEN = {}
    for h in sorted([h for h in R.H26 if h.area > 400 and h.bounds[0] > 110], key=lambda h: h.bounds[0]):
        R.OPEN[['1', '5', '10', '50'][len(R.OPEN)]] = h
    pl = {pid: F.frame(pid).plane() for pid in ('#13', '#7', '#6', '#5', '#36')}
    R.CHUTE_U = {'1': (pl['#13'][2], pl['#7'][1]), '5': (pl['#7'][2], pl['#6'][1]),
                 '10': (pl['#6'][2], pl['#5'][1]), '50': (pl['#5'][2], pl['#36'][1])}
    R.COIN = _coin_zones(R)
    R.COIN_ARC = _coin_arcs(R)
    R.S1 = s1_zone()
    R.S1_CUTS37 = s1_cuts37()
    R.S1_ENG37 = s1_engrave37()
    J26 = _s1_json()['#26']['slots']
    R.OTHER_CUTS26 = [('crosstrack 新增 #6 上方小榫槽', R.CT_SLOT26_6)] + \
                     [(f'S1 #26 槽 {k}', Polygon(v['asm_UV'])) for k, v in J26.items()]
    R.SOURCE = dict(s1='design/s1wall_final/geometry_s1_final.json（名目）',
                    crosstrack='design/crosstrack_final/geometry_final.json（名目）')
    # 機身尺寸核對（V_TOP 等常數）
    top24 = R.G24.intersection(rect(180, 246, -10, 30)).bounds[1]
    top26 = R.G26.intersection(rect(140, 243, -10, 30)).bounds[1]
    top37 = R.G37.intersection(rect(140, 246, -10, 30)).bounds[1]
    R.const_check = dict(V_TOP_24=top24, V_TOP_26=top26, V_TOP_37=top37)
    return R


def from_page(pid: str, geom):
    """零件頁座標幾何 → 板面組裝座標（兩軸＝PLANE[板面法線軸]，取板厚中間）。"""
    fr = F.frame(pid)
    return fr.geom_asm(geom, fr.thickness / 2, PLANE[fr.plane()[0]])


def _delta_from_page(pid, dx, dy):
    fr = F.frame(pid)
    a, b = PLANE[fr.plane()[0]]
    T = fr.T
    return (T[AXI[a], 0] * dx + T[AXI[a], 1] * dy, T[AXI[b], 0] * dx + T[AXI[b], 1] * dy)


def _text_box_page(e):
    """add_engrave_text（頁座標）的近似外框，angle 只支援 0／±90／180。"""
    x, y, size = e['x'], e['y'], e['size']
    w = _text_width(e['text'], size)
    anc = e.get('anchor', 'start')
    s0 = {'start': 0.0, 'middle': -w / 2, 'end': -w}[anc]
    th = math.radians(e.get('angle', 0.0))
    c, s = round(math.cos(th)), round(math.sin(th))
    pts = []
    for u in (s0, s0 + w):
        for v in (-0.85 * size, 0.25 * size):
            pts.append((x + c * u - s * v, y + s * u + c * v))
    return MultiPoint(pts).envelope


def _apply_others(R, cat, others: dict):
    """用其他子系統 build() 的實際結果取代名目 json（整合時重查用）。others：{'s1': …, 'crosstrack': …}。"""
    s1 = (others or {}).get('s1')
    ct = (others or {}).get('crosstrack')
    if s1:
        k = s1.get('keepout')
        if k:
            R.S1 = dict(U=tuple(k['U']), V=tuple(k['V']), W=tuple(k['W']), parts=[])
        cuts = {}
        for i, e in enumerate(x for x in s1['edits'] if x['part'] == '#37' and x['op'] == 'subtract'):
            tag = str(e.get('tag', i + 1))
            cuts[tag if tag.startswith('S1') else f'S1 {tag}'] = from_page('#37', e['geom'])
        if cuts:
            R.S1_CUTS37 = cuts
        eng = [from_page('#37', _text_box_page(e)) for e in s1['edits'] if e['part'] == '#37' and e['op'] == 'add_engrave_text']
        if eng:
            R.S1_ENG37 = eng
        R.SOURCE['s1'] = 'mods_s1.build() 實際結果'
    if ct:
        sub24 = [from_page('#24', e['geom']) for e in ct['edits'] if e['part'] == '#24' and e['op'] == 'subtract']
        if sub24:
            R.CT_WIN24 = unary_union(sub24)
        mv = {e['src']: e for e in ct['edits'] if e['part'] == '#24' and e['op'] == 'move_engrave'}
        for key, src in (('「5」(crosstrack 新位)', 'text11-4-1'), ('「1」(crosstrack 新位)', 'text16-7-2')):
            d = _delta_from_page('#24', mv[src]['dx'], mv[src]['dy']) if src in mv else (0.0, 0.0)
            R.ENG_NEW[key] = R.hull(src, d)
        for pid in ('#5', '#6', '#7'):
            eds = [e for e in ct['edits'] if e['part'] == pid]
            if not eds:
                continue
            g = cat[pid].geom
            un = [e['geom'] for e in eds if e['op'] == 'union']
            sb = [e['geom'] for e in eds if e['op'] == 'subtract']
            if un:
                g = g.union(unary_union(un))
            if sb:
                g = g.difference(unary_union(sb))
            if g.geom_type != 'Polygon':
                g = max(g.geoms, key=lambda q: q.area)
            R.DIV_V2[pid] = from_page(pid, g)
            o = cat[pid].bbox
            R.DIV_V2_LOCAL[pid] = affinity.translate(g, -o[0], -o[1])
        R.SOURCE['crosstrack'] = 'mods_crosstrack.build() 實際結果'
    oth = []
    for nm, res in (('crosstrack', ct), ('S1', s1)):
        if res:
            for e in res['edits']:
                if e['part'] == '#26' and e['op'] == 'subtract':
                    oth.append((f'{nm} #26 新切割「{e.get("tag", "")}」', from_page('#26', e['geom'])))
        else:
            oth += [x for x in R.OTHER_CUTS26 if x[0].startswith(nm)]
    R.OTHER_CUTS26 = oth
    return R


def _exit_V(W):
    return V_EXIT_26 - (V_EXIT_26 - V_EXIT_37) * W / W37_IN


def _coin_zones(R):
    Z = [Solid('斜槽滾動區（#24 板厚內）', 'W', R.SLOT24, (W24_FRONT, W24_BACK), 'coin')]
    for c, op in R.OPEN.items():
        Z.append(Solid(f'{c} 元開口（#26 板厚內）', 'W', op, F.W26, 'coin'))
        Z.append(Solid(f'{c} 元翻倒掃掠（開口×W\'0~D）', 'W', op, (0.0, COIN_D[c]), 'coin'))
        u0, u1 = R.CHUTE_U[c]
        vt = op.bounds[1]
        Z.append(Solid(f'{c} 元滑道落下區（保守：V≥開口頂 {vt:.1f} 整個深度）', 'U',
                       Polygon([(0.0, vt), (W37_IN, vt), (W37_IN, _exit_V(W37_IN)), (0.0, _exit_V(0.0))]),
                       (u0, u1), 'coin'))
    return Z


def _coin_arcs(R, step=2.0, shift=10.0):
    """翻倒弧＋落下（沿 U 分片；每片用 max(開口右端, U−shift) 的唇高）。"""
    out = []
    for c, op in R.OPEN.items():
        Dc = COIN_D[c]
        U0 = op.bounds[0]
        u0, u1 = R.CHUTE_U[c]
        for ua in np.arange(u0, u1, step):
            ub = min(ua + step, u1)
            Vlip = float(F.rail_V(max(U0, ua - shift))) - 1.31 / 0.94
            ws = np.linspace(0, W37_IN, 59)
            top = [(w, Vlip - math.sqrt(max(0.0, Dc ** 2 - w ** 2)) / 0.94) for w in ws]
            poly = Polygon(top + [(W37_IN, max(_exit_V(W37_IN), Vlip)), (0.0, _exit_V(0.0))]).buffer(0)
            out.append(Solid(f'{c} 元翻倒弧＋落下（U{ua:.0f}~{ub:.0f}）', 'U', poly, (ua, ub), 'coin'))
    return out


# ===========================================================================
# 模型（移植自 design/ebox_final/model.py 的 build）
# ===========================================================================
def model(R: NS, pr: NS, logo_search: bool = False) -> NS:
    M = NS()
    T = pr.T
    D = dict(pr.DISP)
    M.D = D
    # ---------------- 顯示器
    w, h = D['pcb_w'], D['pcb_h']
    Ur = pr.DISP_UR
    if pr.DISP_VP is not None:
        Vp = pr.DISP_VP
    elif D['use_screws']:      # 規則 1：上排 M2 孔到 #24 頂邊料寬 ≥ MIN_WEB；PCB 上緣至少 V5
        need = V_TOP + pr.MIN_WEB + D['hole_d'] / 2 + pr.C_SCREW + D['hole_dy'] - D['pcb_h'] / 2
        Vp = max(V_TOP + 1.0, math.ceil(need * 2 - 1e-9) / 2)
    else:
        Vp = V_TOP + 1.0
    Uc, Vc = Ur + w / 2, Vp + h / 2
    Wf = W24_BACK
    Wb = Wf + D['pcb_t']
    g = {}
    g['PCB'] = (Ur, Ur + w, Vp, Vp + h, Wf, Wb)
    bu, bv = Uc - D['body_dx'], Vc + D['body_dy']
    g['LED 塊'] = (bu - D['body_w'] / 2, bu + D['body_w'] / 2, bv - D['body_h'] / 2, bv + D['body_h'] / 2, Wf - D['body_H'], Wf)
    i = D['back_inset']
    g['背面零件'] = (Ur + i, Ur + w - i, Vp + i, Vp + h - i, Wb, Wb + D['back_h'])
    Vh = Vc + D['hdr_dy']
    half = D['hdr_pins'] * D['hdr_pitch'] / 2
    nW = D['hdr_pins'] * pr.WIRE_D
    pc = Wb + D['pin_h']
    if D['hdr_mode'] == 'RA':
        g['排針座'] = (Ur, Ur + D['hdr_body'], Vh - half, Vh + half, Wb, Wb + D['hdr_body'])
        u1 = Ur - D['dup_gap']
        u0 = u1 - D['dup_len']
        g['杜邦頭'] = (u0, u1, Vh - half, Vh + half, pc - D['dup_sq'] / 2, pc + D['dup_sq'] / 2)
        g['外露針'] = (u1, Ur, Vh - 0.32, Vh + 0.32, pc - 0.32, pc + 0.32)
        ub = u0 - D['wire_bend']
        riser = (ub, ub + nW)
        L_B = D['dup_gap'] + D['dup_len'] + D['wire_bend']
    else:
        g['排針座'] = (Ur + 0.5, Ur + 0.5 + D['hdr_pitch'], Vh - half, Vh + half, Wb, Wb + 2.5)
        g['杜邦頭'] = (Ur + 0.5, Ur + 0.5 + D['hdr_pitch'], Vh - half, Vh + half, Wb + 2.5, Wb + 2.5 + D['dup_len'])
        riser = (Ur + 0.3, Ur + 0.3 + nW)
        L_B = 0.0
    V_run0, V_run1 = pr.CABLE_RUN_V
    g['線：上升段'] = (riser[0], riser[1], V_run0, Vh + half, W24_BACK, 1.4)
    cu = pr.CABLE_U
    g['線：#24 背面水平段'] = (cu - nW / 2, riser[1], V_run0, V_run1, W24_BACK, -1.4)
    holes = ([(Uc + sx * D['hole_dx'], Vc + sy * D['hole_dy']) for sx in (-1, 1) for sy in (-1, 1)]
             if D['use_screws'] else [])
    rn = pr.NUT_M2['d_circ'] / 2
    for k, (u, v) in enumerate(holes):
        g[f'M2 螺帽{k + 1}'] = (u - rn, u + rn, v - rn, v + rn, Wb, Wb + pr.NUT_M2['t'])
        tip = W24_FRONT + pr.SCREW_M2['L']
        g[f'M2 螺絲尖{k + 1}'] = (u - 1.0, u + 1.0, v - 1.0, v + 1.0, Wb + pr.NUT_M2['t'], tip)
    M.Vp = Vp
    M.disp = g
    M.Uc, M.Vc, M.Vh, M.half, M.holes, M.riser, M.L_B = Uc, Vc, Vh, half, holes, riser, L_B
    M.disp_solids = [boxsolid(n, *bx, kind='disp') for n, bx in g.items()]
    hd = pr.SCREW_M2['head_d'] / 2
    M.screw_heads = [Point(u, v).buffer(hd, 32) for u, v in holes]
    M.head_solids = [Solid(f'M2 螺絲頭{k + 1}（#24 正面）', 'W', hh, (W24_FRONT - pr.SCREW_M2['head_h'], W24_FRONT), 'disp')
                     for k, hh in enumerate(M.screw_heads)]
    # ---------------- #24
    l0, l1, v0, v1 = g['LED 塊'][:4]
    M.WIN = rect(l0 - pr.C_WIN, l1 + pr.C_WIN, v0 - pr.C_WIN, v1 + pr.C_WIN)
    M.SCREW_HOLES = [Point(u, v).buffer(D['hole_d'] / 2 + pr.C_SCREW, 32) for u, v in holes]
    keep = unary_union([M.WIN, R.SLOT24, R.CT_WIN24, rect(0, TURNTABLE_U, 0, 114)] + M.screw_heads
                       + list(R.ENG_NEW.values()))
    outer24 = Polygon(R.G24.exterior)
    # ---------------- #26 缺口
    hu = [u for u, v in holes] or [Ur + w / 2]
    hv = [v for u, v in holes] or [Vp + h / 2]
    rr = rn if holes else 0.0
    A_u0 = min(Ur, min(hu) - rr) - pr.C_NOTCH
    A_u1 = max(Ur + w, max(hu) + rr) + pr.C_NOTCH
    A_v1 = max(Vp + h, max(hv) + rr) + pr.C_NOTCH
    M.A_v1 = A_v1
    M.NOTCH_A = rect(A_u0, A_u1, 9.0, A_v1)
    if D['hdr_mode'] == 'RA':
        M.NOTCH_B = rect(Ur - L_B - pr.C_NOTCH, A_u0 + 0.01, 9.0, Vh + half + pr.C_NOTCH)
        M.NOTCH26 = unary_union([M.NOTCH_A, M.NOTCH_B])
    else:
        M.NOTCH_B = None
        M.NOTCH26 = M.NOTCH_A
    M.NOTCH26_OUT = M.NOTCH26.intersection(rect(0, 300, NOTCH26_TOP_V, 200)).simplify(0.001)   # 輸出用
    M.G26_V2 = R.G26.difference(M.NOTCH26)
    see = unary_union([M.NOTCH26, rect(*g['線：上升段'][:4]), rect(*g['線：#24 背面水平段'][:4])])

    # ---------------- Logo
    inner24 = outer24.buffer(-LOGO_CLEAR)
    other24 = unary_union(R.OTHER_H24)
    holes0 = unary_union(R.LOGO_HOLES)
    shapely.prepare(inner24)

    def logo_eval(dU, dV):
        L = affinity.translate(R.LOGO, dU, dV)
        lh = affinity.translate(holes0, dU, dV)
        inside = inner24.contains(L)
        return dict(clear=L.distance(keep), hole_clear=lh.distance(other24),
                    see=lh.intersection(see).area, inside=inside, L=L, lh=lh, shift=(dU, dV))

    def logo_ok(e):
        return (e['inside'] and e['clear'] >= LOGO_CLEAR and e['hole_clear'] >= LOGO_HOLE_CLEAR
                and e['see'] < 1e-9)
    M.logo_eval, M.logo_ok = logo_eval, logo_ok
    M.logo_main = logo_eval(*pr.LOGO_SHIFT)
    M.logo_alt = logo_eval(*pr.LOGO_SHIFT_ALT)
    M.logo_note = ''
    if logo_ok(M.logo_main):
        M.logo, M.LOGO_SHIFT, M.LOGO_USED = M.logo_main, pr.LOGO_SHIFT, pr.LOGO_LABEL
    elif logo_ok(M.logo_alt):
        M.logo, M.LOGO_SHIFT, M.LOGO_USED = M.logo_alt, pr.LOGO_SHIFT_ALT, pr.LOGO_ALT_LABEL
        M.logo_note = f'Logo 方案 {pr.LOGO_LABEL} 不合條件，自動改用 {pr.LOGO_ALT_LABEL}'
    else:
        best = logo_search_grid(logo_eval, logo_ok)
        if best:
            M.LOGO_SHIFT = best[0][2:]
            M.logo = logo_eval(*M.LOGO_SHIFT)
            M.LOGO_USED = f'搜尋 ({M.LOGO_SHIFT[0]:.2f}, {M.LOGO_SHIFT[1]:.2f})'
            M.logo_note = f'Logo 的 {pr.LOGO_LABEL}、{pr.LOGO_ALT_LABEL} 都不合條件，改用搜尋結果 ΔU{M.LOGO_SHIFT[0]:.2f}、ΔV{M.LOGO_SHIFT[1]:.2f}'
        else:
            M.logo, M.LOGO_SHIFT, M.LOGO_USED = M.logo_main, pr.LOGO_SHIFT, pr.LOGO_LABEL
            M.logo_note = f'Logo 找不到合條件的位置，仍用 {pr.LOGO_LABEL}（請人工決定）'
    if logo_search:
        M.logo_search = logo_search_grid(logo_eval, logo_ok)
    G24v = R.G24
    for x in R.LOGO_HOLES:
        G24v = G24v.union(x.buffer(0.01))
    M.G24_V2 = G24v.difference(unary_union([M.logo['lh'], M.WIN] + M.SCREW_HOLES))
    # ---------------- #5（前上角讓位；crosstrack v2 外形再減）
    M.DIV5_CUT_W = g['背面零件'][5] + pr.C_DIV          # W'
    M.DIV5_CUT_V = A_v1
    M.DIV5_CUT_WV = rect(-7.0, M.DIV5_CUT_W, V_TOP_26 - 1.0, M.DIV5_CUT_V)
    M.DIV5_WV = R.DIV_V2['#5'].difference(M.DIV5_CUT_WV)
    # ---------------- 電子盒
    BX, HK, BD, Bt, SW = pr.BOX, pr.HOOK, pr.BOARD, pr.BATT, pr.SWITCH
    U_R0 = BX['U_WR']
    U_R1 = U_R0 + T
    U_bd1 = U_R0 - BD['c_end']
    U_bd0 = U_bd1 - BD['L']
    U_L0 = min(BX['U_WL'], U_bd0 - BX['wl_bay'] - T)           # 規則 2
    U_L1 = U_L0 + T
    M.U_WL_LIMIT = R.S1['U'][1] + 1.0
    Vt = BX['V_top']
    Wfr = BX['W_front']
    Wbk = BX['W_back']
    W_B0 = W37_OUT + BX['gap']
    W_B1 = W_B0 + T
    Lp, Wp, Tp = max(Bt['L'], BATT_STD[0]), max(Bt['W'], BATT_STD[1]), max(Bt['Tk'], BATT_STD[2])   # 規則 3
    V_bat0 = Vt - Bt['proud']
    V_bat1 = V_bat0 + Tp
    V_F0 = V_bat1 + Bt['c']
    V_F1 = V_F0 + T                                             # 電池架 EB-F
    W_bat0 = W37_OUT + 0.3
    W_bat1 = W_bat0 + Wp
    W_S0 = W_bat1 + 0.3
    W_S1 = W_S0 + T                                             # 電池後擋 EB-S
    U_bat1 = U_R0 - Bt['c']
    U_bat0 = U_bat1 - Lp
    U_E1 = U_bat0 - Bt['clip']
    U_E0 = U_E1 - T                                             # 電池端擋 EB-E
    W_F1 = W_S1 + 2.9                                           # EB-F 後緣（EB-S 榫槽後留 2.8）
    V_T0, V_T1 = Vt, Vt + T                                     # 頂板
    V_bd0 = V_F1 + BD['c_top']
    V_bd1 = V_bd0 + BD['W']
    V_B0 = V_F1
    V_B1 = V_bd1 + BD['c_bot']                                  # 底板 EB-B
    Vb = V_B1                                                   # 盒底
    W_bd0 = W_B1 + BD['standoff']
    W_bd1 = W_bd0 + BD['t']
    M.U_L0, M.U_L1, M.U_R0, M.U_R1, M.Vb, M.Vt = U_L0, U_L1, U_R0, U_R1, Vb, Vt
    M.W_B0, M.W_B1 = W_B0, W_B1
    M.bat = (U_bat0, U_bat1, V_bat0, V_bat1, W_bat0, W_bat1)
    M.U_E0, M.U_E1, M.V_F0, M.V_F1, M.W_S0, M.W_S1, M.W_F1 = U_E0, U_E1, V_F0, V_F1, W_S0, W_S1, W_F1
    M.board = (U_bd0, U_bd1, V_bd0, V_bd1, W_bd0, W_bd1)
    # 掛勾槽（#37）
    SLIDE = HK['lip_len'] + 0.4
    M.SLIDE = SLIDE
    M.SLOTS37 = [rect(ua - pr.C_HOOK, ua + T + pr.C_HOOK, n0 - SLIDE - pr.C_HOOK, n0 + HK['neck_h'] + pr.C_HOOK)
                 for ua in (U_L0, U_R0) for n0 in HK['levels']]
    cw, cd = pr.CABLE_NOTCH_37['w'], pr.CABLE_NOTCH_37['depth']
    M.CABLE_NOTCH = rect(cu - cw / 2, cu + cw / 2, V_TOP - CABLE_NOTCH_37_OUT, V_TOP + cd)
    M.SENSOR_HOLE = rect(*pr.SENSOR_HOLE_37)
    M.G37_V2 = R.G37.difference(unary_union(M.SLOTS37 + [M.CABLE_NOTCH, M.SENSOR_HOLE]))

    def hooked_wall(w_back):
        out = rect(Wfr, w_back, Vt, Vb)
        for n0 in HK['levels']:
            neck = rect(HK['lip_back'], Wfr + 0.01, n0, n0 + HK['neck_h'])
            ch = HK['chamfer']
            vlo = n0 + HK['neck_h'] + HK['lip_len']
            lip = Polygon([(HK['lip_W0'], n0), (HK['lip_back'], n0), (HK['lip_back'], vlo),
                           (HK['lip_W0'] + ch, vlo), (HK['lip_W0'], vlo - ch)])
            out = unary_union([out, neck, lip])
        return out

    def slot_wv(w0, w1, v0, v1, c=pr.C_TAB):
        return rect(w0 - c, w1 + c, v0 - c, v1 + c)
    TAB_B_V = [(22.0, 32.0), (Vb - 12.0, Vb - 2.0)]            # EB-B 側榫（V）
    TAB_T_WL = (55.0, 65.0)
    TAB_T_WR = (61.0, 68.0)                                     # EB-T 端榫（W'）
    TAB_S_V = (10.0, 16.0)                                      # EB-S 端榫（V）
    TAB_F_W = (40.0, 50.0)                                      # EB-F 端榫（W'，只進 EB-E）
    TAB_E_W = (62.0, 68.0)                                      # EB-E 頂榫（W'，進 EB-T）
    TAB_SF_U = [(U_bat0 + 4.0, U_bat0 + 14.0), (U_bat1 - 14.0, U_bat1 - 4.0)]   # EB-S 下榫（U，進 EB-F）
    M.tabs = dict(TAB_B_V=TAB_B_V, TAB_T_WL=TAB_T_WL, TAB_T_WR=TAB_T_WR, TAB_S_V=TAB_S_V, TAB_F_W=TAB_F_W,
                  TAB_E_W=TAB_E_W, TAB_SF_U=TAB_SF_U)
    sl_B = [slot_wv(W_B0, W_B1, a, b) for a, b in TAB_B_V]

    def nT(wr):          # 頂緣開口缺口
        return rect(wr[0] - pr.C_TAB, wr[1] + pr.C_TAB, Vt - 1.0, V_T1 + pr.C_TAB)
    WLn = BX['wl_notch']
    WL_WV = hooked_wall(Wbk).difference(unary_union(sl_B + [nT(TAB_T_WL), rect(WLn[0] - 1.0, WLn[1], WLn[2], WLn[3])]))
    # 服務窗（USB＋DC 插頭外殼外包）
    dev_u1 = U_bd1 - BD['usb_inset']
    dev_u0 = dev_u1 - BD['dev_len']
    dev_vc = V_bd0 + BD['usb_V_off']
    W_dev0 = W_bd1 + BD['hdr_h']
    W_dev1 = W_dev0 + BD['dev_t']
    usb_wc = W_dev1 + BD['usb_h'] / 2
    dc_vc = V_bd0 + BD['dc_V_off']
    dc_wc = W_bd1 + BD['dc_h'] / 2
    c_sw = pr.SERVICE_WIN_C
    pv, pw = BD['usb_plug']
    rdc = BD['dc_plug_d'] / 2
    M.SERVICE_WIN = unary_union([rect(dc_wc - rdc - c_sw, dc_wc + rdc + c_sw, dc_vc - rdc - c_sw, dc_vc + rdc + c_sw),
                                 rect(usb_wc - pw / 2 - c_sw, usb_wc + pw / 2 + c_sw, dev_vc - pv / 2 - c_sw,
                                      dev_vc + pv / 2 + c_sw)]).envelope
    M.WR_CABLE_NOTCH = rect(W_S1 + 2.9, Wbk + 1.0, 9.5, 16.5)     # 右牆後緣 DC 線出口
    WR_WV = hooked_wall(Wbk).difference(unary_union(sl_B + [nT(TAB_T_WR), slot_wv(W_S0, W_S1, *TAB_S_V), M.SERVICE_WIN,
                                                            M.WR_CABLE_NOTCH]))
    # EB-B（U,V）
    EBB = unary_union([rect(U_L1, U_R0, V_B0, V_B1)] + [rect(U_L0, U_L1, a, b) for a, b in TAB_B_V]
                      + [rect(U_R0, U_R1, a, b) for a, b in TAB_B_V])
    ins = BD['hole_inset']
    M.BOARD_HOLES = [(U_bd0 + ins, V_bd0 + ins), (U_bd1 - ins, V_bd0 + ins), (U_bd0 + ins, V_bd1 - ins), (U_bd1 - ins, V_bd1 - ins)]
    EBB = EBB.difference(unary_union([Point(u, v).buffer(BD['hole_d'] / 2, 32) for u, v in M.BOARD_HOLES]))
    # EB-T（U,W'）：開關區（W' top_W0~後緣）＋電池後方條（W'S0~後緣）
    W_T_front = BX['top_W0']
    EBT = unary_union([rect(U_L1, U_E1, W_T_front, Wbk), rect(U_E1 - 0.01, U_R0, W_S0, Wbk),
                       rect(U_L0, U_L1, *TAB_T_WL), rect(U_R0, U_R1, *TAB_T_WR)])
    M.SW_CUT = rect(SW['U0'], SW['U0'] + SW['cut_a'], SW['W0'], SW['W0'] + SW['cut_b'])
    EBT = EBT.difference(unary_union([M.SW_CUT, rect(U_E0 - pr.C_TAB, U_E1 + pr.C_TAB, TAB_E_W[0] - pr.C_TAB,
                                                     TAB_E_W[1] + pr.C_TAB)]))
    # EB-S（U,V）：電池後擋
    EBS = unary_union([rect(U_E1, U_R0, V_T1, V_F0), rect(U_E0, U_E1, *TAB_S_V), rect(U_R0, U_R1, *TAB_S_V)]
                      + [rect(a, b, V_F0 - 0.01, V_F1) for a, b in TAB_SF_U])
    # EB-F（U,W'）：電池架
    EBF = unary_union([rect(U_E1, U_R0, Wfr, W_F1), rect(U_E0, U_E1, *TAB_F_W)])
    EBF = EBF.difference(unary_union([rect(a - pr.C_TAB, b + pr.C_TAB, W_S0 - pr.C_TAB, W_S1 + pr.C_TAB) for a, b in TAB_SF_U]))
    # EB-E（W',V）：電池端擋
    EBE = unary_union([rect(Wfr, W_F1, V_T1, V_F1), rect(*TAB_E_W, Vt, V_T1)])
    EBE = EBE.difference(unary_union([slot_wv(W_S0, W_S1, *TAB_S_V),
                                      rect(TAB_F_W[0] - pr.C_TAB, TAB_F_W[1] + pr.C_TAB, V_F0 - pr.C_TAB, V_F1 + 1.0)]))
    # 防拔鍵（選用）：塞進上層槽上段（勾頸／勾唇上緣 n_top 以上、槽頂以下那段 V6.9～13.5）
    # 頭和舌的下緣都在 n_top−0.1：頭在 #37 內側和勾唇（W'25～28.85、V≥n_top）同一個 U 平面，
    # 頭若往下超過 n_top 就會和勾唇重疊、塞不進去（spec c-3 原本畫到 n_top+1.5，2026-10-07 修正）。
    # 頭頂 n_top−SLIDE−2.0 比槽頂高 1.8，壓在 #37 內面，鍵不會整支穿過槽。
    n_top = HK['levels'][0]
    key_bot = n_top - 0.1
    M.KEY_TONGUE_WV = rect(W37_IN, W37_OUT, n_top - SLIDE + 0.1, key_bot)
    M.KEY_HEAD_WV = rect(HK['lip_W0'] + 0.5, W37_IN, n_top - SLIDE - 2.0, key_bot)
    M.KEY_WV = unary_union([M.KEY_TONGUE_WV, M.KEY_HEAD_WV])
    M.WL_WV, M.WR_WV = WL_WV, WR_WV
    M.BOX = [Solid('EB-WL 左牆', 'U', WL_WV, (U_L0, U_L1), 'box'),
             Solid('EB-WR 右牆', 'U', WR_WV, (U_R0, U_R1), 'box'),
             Solid('EB-B 主板底板', 'W', EBB, (W_B0, W_B1), 'box'),
             Solid('EB-T 頂板', 'V', EBT, (V_T0, V_T1), 'box'),
             Solid('EB-S 電池後擋', 'W', EBS, (W_S0, W_S1), 'box'),
             Solid('EB-F 電池架', 'V', EBF, (V_F0, V_F1), 'box'),
             Solid('EB-E 電池端擋', 'U', EBE, (U_E0, U_E1), 'box')]
    M.KEY = Solid('EB-K 防拔鍵（選用）', 'U', M.KEY_WV, (U_L0, U_L1), 'box')
    # ---------------- 盒內元件（DevKit 38P 左排；USB 在 +U 端 → 用到的列在下）
    order = ['3V3', 'EN', 'VP', 'VN', '34', '35', '32', '33', '25', '26', '27', '14', '12', 'GND', '13', 'D2', 'D3', 'CMD', '5V']
    p1 = dev_u0 + BD['pin1_from_antenna']
    M.GPIO_U = {n: p1 + k * BD['pitch'] for k, n in enumerate(order)}
    gvs_vc = V_bd1 - BD['gvs_V_off']
    row_u0 = min(M.GPIO_U.values()) - 2.0
    row_u1 = max(M.GPIO_U.values()) + 2.0
    Wgvs1 = W_bd1 + BD['male_h'] + BD['dup_len'] + BD['bend']
    M.Wgvs1 = Wgvs1
    Cn = {}
    Cn['9V 電池'] = M.bat
    Cn['電池扣（含線彎）'] = (U_E1 + 0.25, U_bat0, V_bat0 + 1.0, V_bat1 - 1.0, W_bat0 + 1.0, W_bat1 - 1.0)
    Cn['擴展板 PCB'] = M.board
    Cn['墊高螺帽＋螺絲區'] = (U_bd0, U_bd1, V_bd0, V_bd1, W_B1, W_bd0)
    Cn['ESP32 開發板＋母座'] = (dev_u0, dev_u1, dev_vc - BD['dev_w'] / 2, dev_vc + BD['dev_w'] / 2, W_bd1, W_dev1 + BD['dev_comp'])
    Cn['USB 座'] = (dev_u1 - 5.5, dev_u1 + 0.5, dev_vc - 4.0, dev_vc + 4.0, W_dev1, W_dev1 + BD['usb_h'])
    Cn['DC 座'] = (U_bd1 - BD['dc_len'], U_bd1, dc_vc - BD['dc_d'] / 2, dc_vc + BD['dc_d'] / 2, W_bd1, W_bd1 + BD['dc_h'])
    Cn['未用排針列（上）'] = (row_u0, row_u1, V_bd0 + BD['gvs_V_off'] - 3.81, V_bd0 + BD['gvs_V_off'] + 3.81, W_bd1, W_bd1 + 8.5)
    Cn['用到的 GVS 列＋杜邦頭＋彎線（下）'] = (row_u0, row_u1, gvs_vc - 3.81, gvs_vc + 3.81, W_bd1, Wgvs1)
    Cn['開關本體'] = (SW['U0'] - 1.0, SW['U0'] + SW['cut_a'] + 1.0, V_T1, V_T1 + SW['body_depth'], SW['W0'] - 0.5,
                   SW['W0'] + SW['cut_b'] + 0.5)
    for k, (u, v) in enumerate(M.BOARD_HOLES):
        Cn[f'M3 螺帽{k + 1}（底板前）'] = (u - 3.2, u + 3.2, v - 3.2, v + 3.2, W_B0 - 2.4, W_B0)
        Cn[f'M3 螺絲尖{k + 1}'] = (u - 1.5, u + 1.5, v - 1.5, v + 1.5, W_B0 - 2.6, W_B0 - 2.4)
    M.CONTENTS = Cn
    M.dev = (dev_u0, dev_u1, dev_vc, W_dev1)
    M.usb_c = (dev_u1, dev_vc, usb_wc)
    M.dc_c = (U_bd1, dc_vc, dc_wc)
    M.EN_BTN = [(dev_u1 - 4.0, dev_vc - BD['btn_dv']), (dev_u1 - 4.0, dev_vc + BD['btn_dv'])]
    M.USB_PLUG = (dev_u1, dev_u1 + 38.0, dev_vc - pv / 2, dev_vc + pv / 2, usb_wc - pw / 2, usb_wc + pw / 2)
    M.DC_PLUG = (U_bd1, U_bd1 + 40.0, dc_vc - rdc, dc_vc + rdc, dc_wc - rdc, dc_wc + rdc)
    # ---------------- 線路中心線（組裝座標；長度與干涉用）
    Wq = Wgvs1 - 2.0
    M.WIRES = {}
    M.WIRES['顯示器 4P（G14/G13/V/G）'] = np.array([
        (g['杜邦頭'][0], Vh, pc), (riser[0] + nW / 2, Vh, pc), (riser[0] + nW / 2, (V_run0 + V_run1) / 2, -2.2),
        (cu, (V_run0 + V_run1) / 2, -2.2), (cu, 7.6, -2.2), (cu, 7.6, 33.2), (cu, V_F1 - 1.0, 33.2),
        (cu, V_F1 - 1.0, Wq), (cu, gvs_vc, Wq), (M.GPIO_U['14'], gvs_vc, Wq)])
    hx = pr.SENSOR_HOLE_37
    hc = ((hx[0] + hx[1]) / 2, (hx[2] + hx[3]) / 2)
    nv = (WLn[2] + WLn[3]) / 2
    bay_u = (U_L1 + U_bd0) / 2
    back = [(hc[0], hc[1], 33.2), (U_L0 - 3.0, nv, 33.2), (U_L1 + 1.0, nv, 37.0), (bay_u, nv, Wq), (bay_u, gvs_vc, Wq)]
    ct_front = {'S5': 137.580, 'S10': 167.177, 'S50': 199.846}   # crosstrack 光束 U（名目）
    for s, ubeam in ct_front.items():
        hu_ = ubeam - 16.0                                       # 排針在翼遠端（wing=up）
        hv_ = float(F.rail_V(hu_)) + 2.0
        pts = [(hu_, hv_, -14.0), (hu_, 95.0, -7.5), (96.5, 95.0, -7.5), (96.5, 105.75, -4.5), (96.5, 105.75, 1.0),
               (hc[0], hc[1] + 2.0, 27.0), (hc[0], hc[1], 30.5)] + back
        gp = {'S5': '26', 'S10': '25', 'S50': '33'}[s]
        M.WIRES[f'{s} 3P（→G{gp}）'] = np.array(pts + [(M.GPIO_U[gp], gvs_vc, Wq)])
    M.WIRES['S1 3P（→G27）'] = np.array([(112.0, 68.0, 37.5), (U_L0 - 3.0, nv, 34.0), (U_L1 + 1.0, nv, 37.0), (bay_u, nv, Wq),
                                       (bay_u, gvs_vc, Wq), (M.GPIO_U['27'], gvs_vc, Wq)])
    M.WIRES['電池扣→開關→DC 插頭'] = np.array([(U_E1 + 3.0, V_bat0 + 3.0, 40.0), (U_E1 + 3.0, Vt - 1.0, 40.0), (U_E0 - 2.0, Vt - 1.0, 40.0),
                                          (SW['U0'] + 6.0, V_T1 + 8.0, W_T_front - 2.0), (SW['U0'] + 6.0, V_T1 + 8.0, W_S1 + 4.0),
                                          (U_R1 - 1.0, 13.0, Wbk - 2.0), (U_R1 + 6.0, 13.0, Wbk - 2.0), (U_R1 + 12.0, dc_vc, dc_wc)])
    M.WIRE_LEN = {k: float(np.sum(np.linalg.norm(np.diff(v, axis=0), axis=1))) for k, v in M.WIRES.items()}
    M.WIRE_SOLIDS = []
    for k, v in M.WIRES.items():
        for j in range(len(v) - 1):
            a, b = v[j], v[j + 1]
            lo = np.minimum(a, b) - 1.0
            hi = np.maximum(a, b) + 1.0
            M.WIRE_SOLIDS.append((k, j, boxsolid(f'{k} 第{j + 1}段', lo[0], hi[0], lo[1], hi[1], lo[2], hi[2], 'wire')))
    M.pr = pr
    return M


def logo_search_grid(logo_eval, logo_ok, step=0.5):
    """Logo 平移量搜尋（ΔU −60～5、ΔV −5～25），回傳 [(clear, −|Δ|, dU, dV), …]，clear 大的在前。"""
    best = []
    for dU in np.arange(-60, 5 + 1e-9, step):
        for dV in np.arange(-5, 25 + 1e-9, step):
            e = logo_eval(float(dU), float(dV))
            if logo_ok(e):
                best.append((round(e['clear'], 2), -math.hypot(dU, dV), float(dU), float(dV)))
    best.sort(reverse=True)
    return best[:12]


# ===========================================================================
# 新零件
# ===========================================================================
NEW_PART_INFO = {   # 代號 → (名稱, 數量, 說明)
    'EB-WL': ('電子盒左牆（兩層掛勾、排線口）', 1, '兩層掛勾穿 #37 掛勾槽 1、2；前緣排線口讓感測器線進盒'),
    'EB-WR': ('電子盒右牆（兩層掛勾、服務窗、DC 線口）', 1, 'USB／DC 從服務窗插；掛勾穿 #37 掛勾槽 3、4'),
    'EB-B': ('電子盒主板底板', 1, '擴展板用 4 支 M3×12 尼龍螺絲＋墊高螺帽鎖在這片'),
    'EB-T': ('電子盒頂板（電源開關）', 1, '開關卡進 9×13.5 孔'),
    'EB-S': ('電子盒電池後擋', 1, ''),
    'EB-F': ('電子盒電池架', 1, '9V 電池橫躺在上面'),
    'EB-E': ('電子盒電池端擋', 1, ''),
    'EB-K': ('電子盒防拔鍵（選用）', 2, '兩片同形，WL、WR 各一；盒子掛好後從機身內側把舌頭往後塞進上層掛勾槽上段，'
             '盒子就抬不起來。L 形：頭比舌長出來的那端朝上，頭與舌齊平的那邊朝下（靠在勾頂上），放反會撞勾唇'),
}
LABEL_TEXT = {'EB-WL': 'EB-WL 左牆', 'EB-WR': 'EB-WR USB 側'}
SPARE_PARTS = ('EB-K',)     # 極小零件：每套多切一整份備品（數量＝每套數量；使用者 2026-10-08 決定 3）


def _clean(poly):
    """清掉 0.01 mm 接縫（同參考程式 export.py）。"""
    return poly.buffer(0.02, join_style='mitre').buffer(-0.02, join_style='mitre').simplify(0.02)


def _face(axis) -> str:
    """區域座標 (a,b) 不鏡像組裝時，雷切上面（雕刻面）朝向。"""
    a, b = PLANE[axis]
    ea = np.eye(3)[AXI[a]]
    eb = np.eye(3)[AXI[b]]
    ez = np.eye(3)[AXI[axis]]
    det = float(np.linalg.det(np.c_[ea, eb, ez]))
    # 合法擺法 det(T)=−1：z（往板內）＝+axis 時上面在 axis 小側、朝 −axis
    sgn = '−' if det < 0 else '+'
    nm = {'U': 'U', 'V': 'V', 'W': "W'"}[axis]
    return f'{sgn}{nm}'


def _text_width(text, size):
    return sum((0.62 if ord(c) < 128 else 1.0) for c in text) * size


def _text_box(x, y, w, size, angle):
    """雕刻文字（anchor=middle、y＝基線）的近似外框。angle 只支援 0／90。"""
    if angle == 0:
        return rect(x - w / 2, x + w / 2, y - 0.85 * size, y + 0.25 * size)
    return rect(x - 0.25 * size, x + 0.85 * size, y - w / 2, y + w / 2)


def _label_pos(geom, text, size):
    """在零件區域座標裡找放得下代號文字、離邊與孔最遠的位置（textpath.fit_text：精確字墨外框，
    字墨離切割線 ≥ TEXT_CLEAR＝1.0；橫排優先，直排要多 0.3 mm 才換）。回傳 (x, y, angle) 或 None。"""
    f = TP.fit_text(geom, text, [size], angles=(0.0, 90.0), angle_penalty=0.3)
    return None if f is None else (f['x'], f['y'], f['angle'])


def _new_parts(M) -> tuple[list, dict]:
    out = []
    maps = {}
    solids = list(M.BOX) + [M.KEY]
    for s in solids:
        code = s.name.split()[0]
        nm, qty, note = NEW_PART_INFO[code]
        g = _clean(s.poly)
        b = g.bounds
        loc = affinity.translate(g, -b[0], -b[1])
        if loc.geom_type != 'Polygon':
            raise RuntimeError(f'{code} 不是單一多邊形（{loc.geom_type}）')
        a1, a2 = PLANE[s.axis]
        face = _face(s.axis)
        maps[code] = dict(a=a1, a0=b[0], b=a2, b0=b[1], axis=s.axis, rng=s.rng, face=face)
        texts = []
        if code != 'EB-K':
            txt = LABEL_TEXT.get(code, code)
            pos = _label_pos(loc, txt, LABEL_SIZE)
            if pos is None:
                txt = code
                pos = _label_pos(loc, txt, LABEL_SIZE)
            if pos is not None:
                texts.append(dict(text=txt, x=pos[0], y=pos[1], size=LABEL_SIZE, angle=pos[2], anchor='middle'))
        face_txt = {'−U': '朝 −U（U 小側）', '+U': '朝 +U', '−V': '朝上（−V）', '+V': '朝下（+V）',
                    "−W'": "朝前（−W'）", "+W'": "朝後（+W'，從機身背面看得到）"}.get(face, face)
        maps[code]['desc'] = ((f'{note}；' if note else '') + f'區域 a＝{a1}−{b[0]:.3f}、b＝{a2}−{b[1]:.3f}；'
                              f'板厚 {s.axis} {s.rng[0]:.3f}～{s.rng[1]:.3f}；雕刻面（上面）{face_txt}')
        npd = dict(id=code, name=nm, material=C.PLY, qty=qty, geom=loc, engrave=[], texts=texts, group=EB_GROUP)
        if code in SPARE_PARTS:     # 外包兩邊都 <10 mm 的極小零件：每套多切一整份備品（使用者 2026-10-08 決定 3）
            npd['spare'] = qty
        out.append(npd)
    return out, maps


# ===========================================================================
# edits
# ===========================================================================
def _arrow_d(pid, u, v0, v1, head=1.2):
    """#37 上沿 +V 的箭頭（組裝 u 處，從 v0 指到 v1），回傳頁座標 d。"""
    pts = [(u, v0), (u, v1), (u - head, v1 - head * 1.4), (u + head, v1 - head * 1.4)]
    q = [to_page(pid, Point(a, b)) for a, b in pts]
    f = lambda p: f'{p.x:.4f},{p.y:.4f}'
    return f'M {f(q[0])} L {f(q[1])} M {f(q[2])} L {f(q[1])} L {f(q[3])}'


def _engrave37(M, R, pr):
    """#37 選用雕刻：掛勾槽 1、3 旁往下箭頭（盒子掛上後往下滑）、感測器線孔旁「感測器線」。
    回傳 (edits, 外框 list[(名稱, 組裝 UV 幾何)])。"""
    eds, boxes = [], []
    if not ENGRAVE_37:
        return eds, boxes
    HK = pr.HOOK
    n0 = HK['levels'][0]
    v0, v1 = n0 - M.SLIDE + 1.0, n0 + HK['neck_h'] - 1.0
    for ua, lab in ((M.U_L0, '左牆'), (M.U_R0, '右牆')):
        u = ua - pr.C_HOOK - 2.6
        eds.append(dict(op='add_engrave', part='#37', d=_arrow_d('#37', u, v0, v1),
                        tag=f'電子盒掛勾槽旁箭頭（{lab}；盒子推到底後往下滑，選用雕刻）'))
        boxes.append((f'箭頭（{lab}）', rect(u - 1.2, u + 1.2, v0, v1)))
    h = pr.SENSOR_HOLE_37
    size = 3.0
    txt = '感測器線'
    uc = (h[0] + h[1]) / 2
    vb = h[2] - 2.0                                   # 基線（字往 −V 長；字底離孔約 1.2）
    w = _text_width(txt, size)
    p = to_page('#37', Point(uc, vb))
    # #37 上面朝後；從背面看 +U 往右、−V 往上 → 頁座標 angle=90 時字是正的
    eds.append(dict(op='add_engrave_text', part='#37', text=txt, x=round(p.x, 4), y=round(p.y, 4), size=size,
                    angle=90, anchor='middle', tag='感測器線孔標示（選用雕刻；從機身背面看是正的）'))
    boxes.append(('「感測器線」', rect(uc - w / 2, uc + w / 2, vb - 0.85 * size, vb + 0.25 * size)))
    return eds, boxes


def _edits(cat, M, R, pr) -> list:
    E = []
    # ---- #24
    E.append(dict(op='subtract', part='#24', geom=to_page('#24', M.WIN), tag='TM1637 顯示窗（LED 塊每邊 +0.3）'))
    for k, hh in enumerate(M.SCREW_HOLES):
        E.append(dict(op='subtract', part='#24', geom=to_page('#24', hh), tag=f'TM1637 M2 固定孔 {k + 1}'))
    dx, dy = page_delta('#24', *M.LOGO_SHIFT)
    for src in R.LOGO_HOLE_SRC:
        E.append(dict(op='translate_cut', part='#24', src=src, dx=round(dx, 6), dy=round(dy, 6),
                      tag=f'Logo 移位（{M.LOGO_USED}）：菱形孔'))
    E.append(dict(op='move_engrave', part='#24', src=LOGO_SRC, dx=round(dx, 6), dy=round(dy, 6),
                  tag=f'Logo 移位（{M.LOGO_USED}）：雕刻'))
    # ---- #26
    E.append(dict(op='subtract', part='#26', geom=to_page('#26', M.NOTCH26_OUT),
                  tag='TM1637 頂邊 L 形缺口（PCB、M2 螺帽、彎針、杜邦頭、上升線）'))
    # ---- #5（只回傳本子系統的前上角讓位）
    E.append(dict(op='subtract', part='#5', geom=to_page('#5', M.DIV5_CUT_WV),
                  tag='TM1637 背面零件讓位（前上角，連帶刪上小榫）'))
    # ---- #37
    labs = ['左牆上層', '左牆下層', '右牆上層', '右牆下層']
    for k, s in enumerate(M.SLOTS37):
        E.append(dict(op='subtract', part='#37', geom=to_page('#37', s), tag=f'電子盒掛勾槽 {k + 1}（{labs[k]}）'))
    E.append(dict(op='subtract', part='#37', geom=to_page('#37', M.CABLE_NOTCH), tag='顯示器線頂邊 U 形缺口'))
    E.append(dict(op='subtract', part='#37', geom=to_page('#37', M.SENSOR_HOLE),
                  tag='感測器線孔（S5/S10/S50 線由右側空腔穿到背面）'))
    eds, _ = _engrave37(M, R, pr)
    E.extend(eds)
    return E


# ===========================================================================
# 警告（Go/No-Go，移植自 sens.py 的 fails()）
# ===========================================================================
def _warnings(M, R, pr) -> list:
    f = []
    D = M.D
    pcb = rect(*M.disp['PCB'][:4])
    if not pcb.buffer(-1.5).contains(M.WIN):
        f.append('LED 窗超出 PCB 內縮 1.5（PCB 壓不住 #24 背面）')
    if D['body_H'] - F.T_BOARD < 0.5:
        f.append('LED 面凸出 #24 <0.5（會被窗緣遮）')
    front = unary_union([M.WIN] + M.screw_heads)
    for nm, e in R.ENG_NEW.items():
        if front.distance(e) < 2.0:
            f.append(f'窗／螺絲頭碰雕刻{nm}（{front.distance(e):.2f} <2）')
    if M.logo_note:
        f.append(M.logo_note)
    if not M.logo_ok(M.logo):
        f.append(f'Logo 位置不合條件（最小距 {M.logo["clear"]:.2f}、孔距 {M.logo["hole_clear"]:.2f}、'
                 f'露出 {M.logo["see"]:.2f}、內縮 3：{M.logo["inside"]}）')
    if M.holes and min(v for u, v in M.holes) - (D['hole_d'] / 2 + pr.C_SCREW) - V_TOP < pr.MIN_WEB:
        f.append('M2 孔到 #24 頂邊料寬 <2')
    hin = _hole_in_pcb(M)
    if hin is not None and hin < HOLE_PCB_WEB:
        f.append(f'TM1637 的 M2 孔不在 PCB 上（孔緣到 PCB 邊 {hin:.2f} <{HOLE_PCB_WEB}）：改了 params.TM1637 的 pcb_w／pcb_h，'
                 '要一起量孔距改 hole_dx／hole_dy（半距＝孔中心離 PCB 中心；實量全距要除以 2）')
    if M.WIN.bounds[1] - V_TOP < 3.0:
        f.append('窗上緣料寬 <3')
    if M.NOTCH26.distance(LineString([(243, 0), (243, 120)])) < 3.0 or M.NOTCH26.bounds[2] > 240.0:
        f.append('#26 缺口離 #26 左緣 <3（PCB 太寬／太靠左）')
    for c, op in R.OPEN.items():
        if M.NOTCH26.distance(op) < 10:
            f.append(f'#26 缺口離 {c} 元開口 <10')
            break
    if M.NOTCH26.distance(R.SLOT24) < 8:
        f.append('#26 缺口離斜槽靠背區 <8')
    u5 = R.DIV_U['#5']
    s5top = rect(u5[0] - 0.1, u5[1] + 0.1, 16.9, 27.1)      # #5 上小榫槽（本缺口會吃掉，不算）
    for hh in [x for x in R.H26 if x.area < 120 and not x.intersects(s5top)]:
        if hh.distance(M.NOTCH26) < 2.5:
            f.append(f'#26 缺口離隔板榫槽 U{hh.bounds[0]:.0f} V{hh.bounds[1]:.0f} <2.5')
            break
    for nm, og in R.OTHER_CUTS26:
        if og.distance(M.NOTCH26) < 2.5:
            f.append(f'#26 缺口離 {nm} <2.5')
    if M.DIV5_CUT_W > 6.0:
        f.append(f'#5 前上角要削到 W\'{M.DIV5_CUT_W:.1f}（>6，隔板頂太弱）')
    if pieces(M.DIV5_WV) != 1:
        f.append('#5 v2（crosstrack＋本修改）斷成多塊')
    if M.NOTCH_B is not None and M.riser[0] < R.DIV_U['#6'][1] + 0.5:
        f.append('上升線壓到 #6 隔板')
    # ---- 電子盒
    if M.U_L0 < M.U_WL_LIMIT - 1e-9:
        f.append(f'左牆要移到 U{M.U_L0:.1f}（< S1 禁區右界 +1 ＝ U{M.U_WL_LIMIT:.1f}）')
    if M.U_E0 < pr.CABLE_U + pr.CABLE_NOTCH_37['w'] / 2 + 1.5 - 1e-9:
        f.append(f'電池帶太長：端擋 EB-E 要到 U{M.U_E0:.1f}，擋到顯示器線越頂處')
    if pr.SWITCH['U0'] + pr.SWITCH['cut_a'] + 1.0 > pr.CABLE_U - 2.8 - 1.0:
        f.append('開關本體擋到顯示器線')
    if M.Vb > pr.BOX['V_bot_max'] + 1e-9:
        f.append(f'盒底 V{M.Vb:.2f} > {pr.BOX["V_bot_max"]}')
    bot = rect(pr.BOX['W_front'], pr.BOX['W_back'], M.Vb - 5, M.Vb)
    if bot.distance(R.G12_WV) < 2.0 or bot.distance(R.G21_WV) < 2.0:
        f.append(f'盒底離 #12／#21 <2（{min(bot.distance(R.G12_WV), bot.distance(R.G21_WV)):.2f}）')
    if M.Wgvs1 > pr.BOX['W_back'] - 1.0:
        f.append(f'杜邦頭＋彎線到 W\'{M.Wgvs1:.1f}，超出盒後緣')

    def ov(a, b, m):
        return a[0] < b[1] + m and b[0] < a[1] + m
    sw = M.CONTENTS['開關本體']
    for other in ('未用排針列（上）', 'ESP32 開發板＋母座', '擴展板 PCB'):
        o = M.CONTENTS[other]
        if ov(sw[0:2], o[0:2], 1.0) and ov(sw[2:4], o[2:4], 1.0) and ov(sw[4:6], o[4:6], 1.0):
            f.append(f'開關本體碰到{other}')
            break
    wr = M.BOX[1]
    sb = M.SERVICE_WIN.bounds
    if pieces(wr.poly) != 1 or sb[0] < pr.BOX['W_front'] + 2.0 or sb[2] > pr.BOX['W_back'] - 2.0 \
            or sb[3] > M.Vb - 2.0 or sb[1] < 17.1 + 2.0:
        f.append(f'服務窗超出右牆可用範圍（W\'{sb[0]:.1f}~{sb[2]:.1f}，V{sb[1]:.1f}~{sb[3]:.1f}）')
    for b in M.BOX:
        if pieces(b.poly) != 1:
            f.append(f'{b.name} 斷成多塊')
            break
    if pr.BOX['W_back'] - M.W_S0 < 9.0:
        f.append('電池太厚（W\'）：頂板後條太窄')
    if M.board[3] > M.Vb:
        f.append('擴展板超出盒底')
    # ---- 跨子系統：S1 禁區、S1 在 #37 的開孔
    z = R.S1
    zb = boxsolid('S1 禁區', *z['U'], *z['V'], *z['W'])
    dS1 = min(dist(b, zb) for b in M.BOX)
    if dS1 < 1.0:
        f.append(f'電子盒離 S1 禁區 {dS1:.2f} <1')
    for nm, c in _cuts37(M):
        for k, o in R.S1_CUTS37.items():
            if c.distance(o) < 2.0:
                f.append(f'#37 {nm} 離 {k} {c.distance(o):.2f} <2')
    return f


HOLE_PCB_WEB = 0.5     # TM1637 的 M2 孔緣到 PCB 邊至少這麼多（孔要真的在 PCB 上；名目 0.9）


def _hole_in_pcb(M):
    """TM1637 每個 M2 孔：min(孔心到 PCB 四邊，孔心在 PCB 外為負) − hole_d/2 的最小值；不用螺絲時 None。"""
    if not M.holes:
        return None
    u0, u1, v0, v1 = M.disp['PCB'][:4]
    r = M.D['hole_d'] / 2
    return min(min(u - u0, u1 - u, v - v0, v1 - v) - r for u, v in M.holes)


def _cuts37(M):
    return ([(f'掛勾槽 {k + 1}', s) for k, s in enumerate(M.SLOTS37)]
            + [('頂邊顯示器線缺口', M.CABLE_NOTCH.intersection(rect(0, 300, V_TOP, 120))),
               ('感測器線孔', M.SENSOR_HOLE)])


# ===========================================================================
# 檢查（移植自 design/ebox_final/checks.py）
# ===========================================================================
class _Rec:
    def __init__(self):
        self.rows = []

    def __call__(self, group, item, val, need, ok, note=''):
        v = val if isinstance(val, str) else round(float(val), 2)
        self.rows.append(dict(name=f'{group}：{item}', group=group, item=item, ok=bool(ok), value=v,
                              expected=need, note=note))


def _checks(cat, M, R, pr, eng37_boxes) -> list:
    rec = _Rec()
    D = M.D
    # ================================================================ 0 機身常數核對
    G = '0 機身常數'
    cc = R.const_check
    rec(G, '#24／#37 頂邊 V（U≥140）＝V_TOP 4.0', f'{cc["V_TOP_24"]:.3f}／{cc["V_TOP_37"]:.3f}', '4.000',
        abs(cc['V_TOP_24'] - V_TOP) < 0.01 and abs(cc['V_TOP_37'] - V_TOP) < 0.01)
    rec(G, '#26 頂邊 V（U≥140）＝14.0', cc['V_TOP_26'], '14.00', abs(cc['V_TOP_26'] - V_TOP_26) < 0.01)
    # ================================================================ A 顯示器與 #24
    G = 'A 顯示器／#24'
    W = M.WIN.bounds
    rec(G, 'LED 窗（切穿）U×V', f'U{W[0]:.2f}~{W[2]:.2f} × V{W[1]:.2f}~{W[3]:.2f}（{W[2] - W[0]:.2f}×{W[3] - W[1]:.2f}）', '—', True)
    rec(G, '窗上緣到 #24 頂邊 V4 料寬', W[1] - V_TOP, '≥3', W[1] - V_TOP >= 3)
    if M.holes:
        web = min(v for u, v in M.holes) - (D['hole_d'] / 2 + pr.C_SCREW) - V_TOP
        rec(G, 'M2 孔到 #24 頂邊 V4 料寬', web, f'≥{pr.MIN_WEB}', web >= pr.MIN_WEB)
        hh = unary_union(M.SCREW_HOLES)
        rec(G, 'M2 孔 ↔ LED 窗 料寬', hh.distance(M.WIN), '≥2', hh.distance(M.WIN) >= 2)
        hin = _hole_in_pcb(M)
        rec(G, 'M2 孔在 TM1637 PCB 上（孔緣到 PCB 邊，孔用 hole_d）', hin, f'≥{HOLE_PCB_WEB}', hin >= HOLE_PCB_WEB,
            f'孔中心＝PCB 中心 ±(hole_dx, hole_dy)＝±({D["hole_dx"]:g}, {D["hole_dy"]:g})（半距；孔距全距 '
            f'{2 * D["hole_dx"]:g}×{2 * D["hole_dy"]:g}）')
    rec(G, f'PCB 上緣 V{M.Vp:.2f}（自動）低於 #24 頂邊 V4（從正面看不到 PCB）', M.Vp - V_TOP, '≥0.5', M.Vp - V_TOP >= 0.5)
    rec(G, 'LED 塊凸出 #24 正面', D['body_H'] - F.T_BOARD, '>0.5（不被窗緣遮）', D['body_H'] - F.T_BOARD > 0.5)
    pcb = rect(*M.disp['PCB'][:4])
    rec(G, 'LED 窗在 PCB 範圍內（PCB 能壓住 #24 背面）', float(pcb.buffer(-1.5).contains(M.WIN)), '窗 ⊂ PCB 內縮 1.5',
        pcb.buffer(-1.5).contains(M.WIN))
    front_items = unary_union([M.WIN] + M.screw_heads)
    for nm, e in R.ENG_NEW.items():
        d = front_items.distance(e)
        rec(G, f'窗／螺絲頭 ↔ 雕刻 {nm}', d, '≥2.0', d >= 2.0)
    d = front_items.distance(R.SLOT24)
    rec(G, '窗／螺絲頭 ↔ #24 斜槽', d, '≥8', d >= 8)
    d = front_items.distance(R.CT_WIN24)
    rec(G, '窗／螺絲頭 ↔ crosstrack #24 感測窗', d, '≥3', d >= 3, f'來源：{R.SOURCE["crosstrack"]}')
    d = front_items.distance(unary_union(R.OTHER_H24))
    rec(G, '窗／螺絲頭 ↔ #24 其他既有孔', d, '≥3', d >= 3)
    rec(G, '原 Logo 與新窗重疊（>0 表示 Logo 必須搬）', R.LOGO.intersection(M.WIN).area, '—', True)
    L = M.logo
    lb = L['L'].bounds
    rec(G, f'Logo 新位置（{M.LOGO_USED}）ΔU{M.LOGO_SHIFT[0]}、ΔV{M.LOGO_SHIFT[1]} 外包',
        f'U{lb[0]:.2f}~{lb[2]:.2f} × V{lb[1]:.2f}~{lb[3]:.2f}', '—', True)
    rec(G, f'Logo {M.LOGO_USED} ↔ 窗／螺絲頭／雕刻(含 crosstrack 新「5」「1」)／斜槽／感測窗／轉盤區', L['clear'], '≥3',
        L['clear'] >= LOGO_CLEAR)
    rec(G, f'Logo {M.LOGO_USED} 菱形孔背後是否露出 #26 缺口／顯示器線', L['see'], '=0', L['see'] < 1e-9)
    rec(G, f'Logo {M.LOGO_USED} 菱形孔 ↔ #24 其他既有孔', L['hole_clear'], '≥2', L['hole_clear'] >= LOGO_HOLE_CLEAR)
    rec(G, f'Logo {M.LOGO_USED} 在 #24 外框內縮 3', float(L['inside']), 'True', L['inside'])
    La = M.logo_alt if M.LOGO_USED == pr.LOGO_LABEL else M.logo_main
    lab_a = pr.LOGO_ALT_LABEL if M.LOGO_USED == pr.LOGO_LABEL else pr.LOGO_LABEL
    alt_ok = M.logo_ok(La)
    rec(G, f'（另一方案 {lab_a} ΔU{La["shift"][0]}、ΔV{La["shift"][1]}）最小距／露出', f'{La["clear"]:.2f}／{La["see"]:.2f}',
        '參考（備案）', True, '備案也可用' if alt_ok else '備案目前不合條件（不影響本次輸出）')
    rec(G, '#24 v2 仍是 1 塊', pieces(M.G24_V2), '=1', pieces(M.G24_V2) == 1)
    ext24 = Polygon(R.G24.exterior).exterior
    newcuts24 = [('LED 窗', M.WIN)] + [(f'M2 孔{k + 1}', hh) for k, hh in enumerate(M.SCREW_HOLES)] + [('Logo 新孔（9 個）', M.logo['lh'])]
    for nm, cpoly in newcuts24:
        others = [o for n2, o in newcuts24 if n2 != nm] + R.OTHER_H24 + [R.SLOT24]
        de = cpoly.distance(ext24)
        do = min(cpoly.distance(o) for o in others)
        rec(G, f'#24 新切割 {nm}：到外框／到其他孔（含其他新切割、斜槽）', f'{de:.2f}／{do:.2f}', '≥2.0／≥2.0', min(de, do) >= 2.0)
    # ================================================================ B #26 缺口
    G = 'B #26 缺口'
    rec(G, '缺口 A（PCB）', f'U{M.NOTCH_A.bounds[0]:.2f}~{M.NOTCH_A.bounds[2]:.2f} × V14~{M.NOTCH_A.bounds[3]:.2f}', '—', True)
    if M.NOTCH_B is not None:
        rec(G, '缺口 B（彎針＋杜邦頭＋上升線）', f'U{M.NOTCH_B.bounds[0]:.2f}~{M.NOTCH_B.bounds[2]:.2f} × V14~{M.NOTCH_B.bounds[3]:.2f}', '—', True)
    for c, op in R.OPEN.items():
        d = M.NOTCH26.distance(op)
        rec(G, f'缺口 ↔ {c} 元開口', d, '≥10', d >= 10)
    d = M.NOTCH26.distance(R.SLOT24)
    rec(G, '缺口 ↔ #24 斜槽投影（硬幣靠背區）', d, '≥8', d >= 8)
    slots26 = [hh for hh in R.H26 if hh.area < 120]
    eaten = [hh for hh in slots26 if hh.intersects(M.NOTCH26)]
    u5 = R.DIV_U['#5'][0]
    rec(G, '缺口吃掉的 #26 原有槽', ', '.join(f'U{hh.bounds[0]:.1f}~{hh.bounds[2]:.1f} V{hh.bounds[1]:.1f}~{hh.bounds[3]:.1f}' for hh in eaten),
        '只能是 #5 上小榫槽', len(eaten) == 1 and abs(eaten[0].bounds[0] - u5) < 0.3)
    for hh in slots26:
        if hh.intersects(M.NOTCH26):
            continue
        d = hh.distance(M.NOTCH26)
        if d < 15:
            rec(G, f'缺口 ↔ #26 槽 U{hh.bounds[0]:.1f}~{hh.bounds[2]:.1f} V{hh.bounds[1]:.1f}~{hh.bounds[3]:.1f}', d, '≥2.5', d >= 2.5)
    for nm, og in R.OTHER_CUTS26:
        d = og.distance(M.NOTCH26)
        if d < 30:
            rec(G, f'缺口 ↔ {nm}', d, '≥2.5', d >= 2.5, f'來源：{R.SOURCE["crosstrack" if nm.startswith("crosstrack") else "s1"]}')
    d = M.NOTCH26.distance(LineString([(243, 0), (243, 120)]))
    rec(G, '缺口 ↔ #26 左緣 U243', d, '≥3', d >= 3)
    rec(G, '#26 v2 仍是 1 塊', pieces(M.G26_V2), '=1', pieces(M.G26_V2) == 1)
    for c in ('10', '50'):
        part = M.NOTCH26.intersection(rect(*R.CHUTE_U[c], 0, 120))
        val = R.OPEN[c].bounds[1] - part.bounds[3] if not part.is_empty else 99
        rec(G, f'缺口底到 {c} 元開口頂（#26 保留料高）', val, '≥10', val >= 10)
    # ================================================================ C #5 合併
    G = 'C #5（crosstrack v2 ＋ 前上角讓位）'
    rec(G, '前上角減除 (W\',V)', f'W\'0~{M.DIV5_CUT_W:.2f} × V14~{M.DIV5_CUT_V:.2f}（局部 x≤{M.DIV5_CUT_W + 6:.2f}、y≤{M.DIV5_CUT_V - 14:.2f}）', '—', True)
    rec(G, '#5 v2 合併後件數', pieces(M.DIV5_WV), '=1', pieces(M.DIV5_WV) == 1,
        f'crosstrack #5 v2 外形來源：{R.SOURCE["crosstrack"]}')
    w5 = min_web(M.DIV5_WV)
    rec(G, '#5 v2 最小料寬（近似）', w5, '≥2', w5 >= 2)
    tl = []
    for nm, rr in (('上小榫 V17~27', rect(-3.1, 0, 17, 27)), ('第二小榫 V35~45', rect(-3.1, 0, 35, 45)),
                   ('後榫 V40~56', rect(W37_IN, W37_OUT + 0.1, 40, 56))):
        tl.append(f'{nm}：{"保留" if M.DIV5_WV.intersection(rr).area > 5 else "刪除"}')
    rec(G, '剩下的定位榫', '；'.join(tl), '至少前 1＋後 1', True,
        'crosstrack 刪長榫；本修改再刪上小榫 → 只剩第二小榫＋後榫（夾在 #26/#37 之間不會掉）')
    d5 = Solid('#5 v2', 'U', M.DIV5_WV, R.DIV_U['#5'])
    d6 = Solid('#6 v2', 'U', R.DIV_V2['#6'], R.DIV_U['#6'])
    s26 = Solid('#26 v2', 'W', M.G26_V2, F.W26)
    s24 = Solid('#24 v2', 'W', M.G24_V2, F.W24)
    s37 = Solid('#37 v2', 'W', M.G37_V2, (W37_IN, W37_OUT))
    # ================================================================ D 顯示器 ↔ 結構
    G = 'D 顯示器零件 ↔ 結構'
    for s in M.disp_solids:
        if s.name.startswith('LED'):
            continue
        for o, need in ((s26, 0.49), (d5, 0.5), (d6, 0.5)):
            d = dist(s, o)
            if d < 12:
                rec(G, f'{s.name} ↔ {o.name}', d, f'≥{need}', d >= need)
    d = dist(M.disp_solids[1], s24)
    rec(G, 'LED 塊 ↔ #24 v2 窗邊', d, '≈C_WIN 0.3', d >= pr.C_WIN - 0.01)
    rec(G, 'PCB ↔ #24 v2（貼合）', dist(M.disp_solids[0], s24), '=0（PCB 正面貼 #24 背面）', True)
    s26o = Solid('#26 原形', 'W', R.G26, F.W26)
    hit = [s.name for s in M.disp_solids if dist(s, s26o) < 1e-6]
    rec(G, '若 #26 不開缺口會撞到的部位', '、'.join(hit) or '無', '證明缺口必要', True)
    # ================================================================ E 顯示器與線 ↔ 硬幣路徑
    G = 'E 硬幣路徑'

    def need_of(nm):
        return 8.0 if ('斜槽' in nm or '開口（' in nm) else 10.0
    disp_and_wire = M.disp_solids + M.head_solids + [ws for k, j, ws in M.WIRE_SOLIDS if k.startswith('顯示器')]
    for z in R.COIN:
        best = min(((dist(s, z), s.name) for s in disp_and_wire), key=lambda x: x[0])
        rec(G, f'顯示器／螺絲／顯示器線 ↔ {z.name}', best[0], f'≥{need_of(z.name)}', best[0] >= need_of(z.name), f'最近：{best[1]}')
    HK = pr.HOOK
    lips = []
    for ua, lab in ((M.U_L0, 'WL'), (M.U_R0, 'WR')):
        for n0 in HK['levels']:
            vlo = n0 + HK['neck_h'] + HK['lip_len']
            ch = HK['chamfer']
            lp = Polygon([(HK['lip_W0'], n0), (HK['lip_back'], n0), (HK['lip_back'], vlo), (HK['lip_W0'] + ch, vlo), (HK['lip_W0'], vlo - ch)])
            lips.append(Solid(f'{lab} 勾唇 V{n0:.1f}~{vlo:.1f}', 'U', lp, (ua, ua + pr.T)))
    key_s = [Solid(f'防拔鍵頭（{lab}）', 'U', M.KEY_HEAD_WV, (ua, ua + pr.T)) for ua, lab in ((M.U_L0, 'WL'), (M.U_R0, 'WR'))]
    for s in lips + key_s:
        ds = [(dist(s, z), z.name) for z in R.COIN_ARC if z.rng[1] > s.rng[0] - 12 and z.rng[0] < s.rng[1] + 12]
        best = min(ds) if ds else (99, '—')
        rec(G, f'{s.name}（U{s.rng[0]:.0f}~{s.rng[1]:.0f}）↔ 翻倒弧＋落下（分片）', best[0], '≥8', best[0] >= 8, best[1])
        dcon = min(dist(s, z) for z in R.COIN if '落下區' in z.name)
        rec(G, f'{s.name} ↔ 保守落下區（開口頂以下整個深度）', dcon, '參考', True)
    behind26 = [z for z in R.COIN if z.axis == 'U' or z.rng[0] >= 0.0]
    for k, v in M.WIRES.items():
        segs = [ws for kk, j, ws in M.WIRE_SOLIDS if kk == k]
        if k[:2] == 'S5' or k[:3] in ('S10', 'S50'):
            dmin = min(dist(s, z) for s in segs[4:6] for z in behind26)
            rec(G, f'{k}：右側空腔內上升段 ↔ #26 背後的硬幣區（翻倒／落下）', dmin, '≥8', dmin >= 8,
                '空腔 U72.1~104.9 在 1 元滑道右牆外側；路徑前段照 crosstrack 名目')
            wmin = float(np.min(v[7:, 2]))
            rec(G, f'{k}：#37 背面段的最小 W\'（>32＝在 #37 外面，被 #37 隔開）', wmin, '>32', wmin > W37_OUT)
        elif not k.startswith('顯示器'):
            wmin = float(np.min(v[:, 2]))
            rec(G, f'{k}：全程最小 W\'（>32＝在 #37 外面，與所有硬幣區之間隔著 #37）', wmin, '>32', wmin > W37_OUT)
    # ================================================================ F #37 修改
    G = 'F #37 修改'
    cuts = _cuts37(M)
    ext37 = Polygon(R.G37.exterior)
    oth37 = [Polygon(r) for r in R.G37.interiors]
    for nm, c in cuts:
        if nm == '頂邊顯示器線缺口':
            de = c.distance(LineString(list(ext37.exterior.coords)).difference(rect(0, 300, V_TOP - 0.1, V_TOP + 0.1)))
        else:
            de = c.distance(ext37.exterior)
        dh = min(c.distance(o) for o in oth37)
        dn = min([c.distance(o) for n2, o in cuts if n2 != nm] or [99])
        b = c.bounds
        rec(G, f'{nm} U{b[0]:.2f}~{b[2]:.2f} V{b[1]:.2f}~{b[3]:.2f}：到外框／既有孔／其他新切割',
            f'{de:.2f}／{dh:.2f}／{dn:.2f}', '≥2.5／≥2.5／≥2.5', min(de, dh, dn) >= 2.5 - 1e-6)
    for nm, c in cuts:
        dd = min((c.distance(o), k) for k, o in R.S1_CUTS37.items())
        rec(G, f'{nm} ↔ S1 在 #37 的開孔（最近）', dd[0], '≥2.0', dd[0] >= 2.0,
            f'{dd[1]}；來源：{R.SOURCE["s1"]}')
    zs = R.S1
    sz = rect(zs['U'][0], zs['U'][1], zs['V'][0], zs['V'][1])
    for nm, c in cuts:
        if nm.startswith('感測器'):
            d = c.distance(sz)
            rec(G, f'{nm} ↔ S1 禁區（背蓋 S1-F／模組後端，U,V 投影）', d, '≥2.0', d >= 2.0)
    ms = rect(*pr.MOTOR_SW)
    rec(G, '新切割 ↔ 原馬達開關（參考位置）', min(c.distance(ms) for nm, c in cuts), '—', True)
    rec(G, '#37 v2 仍是 1 塊', pieces(M.G37_V2), '=1', pieces(M.G37_V2) == 1)
    dten = min(s.distance(o) for s in M.SLOTS37 for o in oth37 if o.area > 40)
    rec(G, '掛勾槽 ↔ 3 片隔板後榫槽（V40.3~56.2）最近', dten, '≥2.5', dten >= 2.5)
    if eng37_boxes:
        allcut37 = unary_union([Polygon(r) for r in R.G37.interiors] + [c for n, c in cuts] + list(R.S1_CUTS37.values()))
        for nm, bx in eng37_boxes:
            d1 = bx.distance(allcut37)
            d2 = min([bx.distance(e) for e in R.S1_ENG37] or [99])
            d3 = bx.distance(ext37.exterior)
            rec(G, f'選用雕刻 {nm} ↔ 切割／S1 雕刻／外框', f'{d1:.2f}／{d2:.2f}／{d3:.2f}', '≥1／≥1／≥1', min(d1, d2, d3) >= 1.0)
    # ================================================================ G 電子盒 ↔ 機身
    G = 'G 電子盒 ↔ 機身'
    s12 = Solid('#12 抽屜櫃後板', 'U', R.G12_WV, (105.0, 239.0))
    s21 = Solid('#21 左櫃側板', 'U', R.G21_WV, F.frame('#21').plane()[1:])
    s36 = Solid('#36 左端板', 'U', R.G36_WV, F.frame('#36').plane()[1:])
    s13 = Solid('#13（右櫃側板原形）', 'U', R.G13_WV, F.frame('#13').plane()[1:])
    sS1 = boxsolid('S1 禁區（s1wall_final 實際範圍）', *zs['U'], *zs['V'], *zs['W'])
    sMS = boxsolid('原馬達開關（含背面本體 20 mm）', pr.MOTOR_SW[0] - 2, pr.MOTOR_SW[1] + 2, pr.MOTOR_SW[2], pr.MOTOR_SW[3] + 2,
                   W37_IN, W37_IN + 23.0)
    box_all = M.BOX
    for o in (s12, s21, s36, s13, sS1, sMS, s37):
        d = min(dist(b, o) for b in box_all)
        need = 0.15 if o is s37 else 1.0
        rec(G, f'盒體（7 片）↔ {o.name}', d, f'≥{need}', d >= need - 1e-6,
            ('S1 禁區 U{:.2f}~{:.2f} × V{:.2f}~{:.2f} × W\'{:.2f}~{:.2f}；來源：{}'.format(
                *zs['U'], *zs['V'], *zs['W'], R.SOURCE['s1']) if o is sS1 else ''))
    rec(G, f'左牆 U{M.U_L0:.2f} ↔ 下限（S1 禁區右界 +1＝U{M.U_WL_LIMIT:.2f}）', M.U_L0 - M.U_WL_LIMIT, '≥0', M.U_L0 >= M.U_WL_LIMIT - 1e-9)
    lipd = min(dist(lp, s37) for lp in lips)
    rec(G, '勾唇後面 ↔ #37 內面（W\'29）', lipd, '0.1~0.3（扣住）', 0.1 <= lipd <= 0.3)
    rec(G, '牆前緣 ↔ #37 外面', pr.BOX['W_front'] - W37_OUT, '0.25', True)
    for k, bx in M.CONTENTS.items():
        if k.startswith('M3'):
            d = dist(boxsolid(k, *bx), s37)
            rec(G, f'{k} ↔ #37', d, '≥0.2', d >= 0.2)
    d = M.W_B0 - W37_OUT
    rec(G, '底板 EB-B 前面 ↔ 3 支隔板後榫尖（W\'32）', d, '≥2.5', d >= 2.5)
    sw = []
    for b in [b for b in box_all if b.name.startswith('EB-W')]:
        s37c = Solid('#37 v2（牆附近）', 'W', M.G37_V2.intersection(rect(b.rng[0] - 8, b.rng[1] + 8, -10, 90)), (W37_IN, W37_OUT))
        for dw in np.arange(0, 15.01, 1.0):
            sw.append(dist(Solid(b.name, b.axis, affinity.translate(b.poly, dw, -M.SLIDE), b.rng), s37c))
        for dv in np.arange(0, M.SLIDE + 0.01, 0.8):
            sw.append(dist(Solid(b.name, b.axis, affinity.translate(b.poly, 0, -M.SLIDE + dv), b.rng), s37c))
    rec(G, '安裝掃掠（抬 %.1f → 往前推 15 → 放下）↔ #37 v2 最小距' % M.SLIDE, min(sw), '≥0.15', min(sw) >= 0.15 - 1e-6)
    lv = HK['levels']
    rec(G, '兩層掛勾層距（盒子不能繞 U 軸轉出、不能直接拔）', lv[1] - lv[0], '≥15', lv[1] - lv[0] >= 15)
    rec(G, '兩面掛勾牆間距（U）', M.U_R0 - M.U_L0, '—', True)
    # 選用防拔鍵 EB-K：和 WL／WR 在同一個 U 平面（板厚同在 #37 上層掛勾槽內），要避開同側牆的勾頸／勾唇與 #37。
    # 盒子取名目、下滑 C_HOOK（勾頸底碰槽底）兩個位置；鍵沿 V 取可動範圍兩端（舌頂碰槽頂／舌底碰勾頂）；
    # 再從機身內側沿 +W' 塞 8 mm 的掃掠。
    n_top = HK['levels'][0]
    slot_top = n_top - M.SLIDE - pr.C_HOOK
    slot_bot = n_top + HK['neck_h'] + pr.C_HOOK
    kb = M.KEY_TONGUE_WV.bounds
    s37_key = unary_union([rect(W37_IN, W37_OUT, -50.0, slot_top), rect(W37_IN, W37_OUT, slot_bot, 150.0)])
    key_ov, room = 0.0, []
    for dv_box in (0.0, pr.C_HOOK):
        lo, hi = slot_top - kb[1], (n_top + dv_box) - kb[3]     # 鍵沿 V 的可動範圍
        room.append(hi - lo)
        walls = [affinity.translate(w_, 0, dv_box) for w_ in (M.WL_WV, M.WR_WV)] + [s37_key]
        for dv_key in (lo, hi):
            for dw in np.arange(0.0, 8.01, 0.5):
                kk = affinity.translate(M.KEY_WV, -dw, dv_key)
                key_ov = max([key_ov] + [kk.intersection(w_).area for w_ in walls])
    rec(G, 'EB-K ↔ 同側牆勾頸／勾唇、#37（盒子名目／下滑 C_HOOK；鍵在槽上段上下兩端；沿 +W\' 塞入 8 mm 掃掠）板面交集',
        key_ov, '=0（塞得進）', key_ov < 1e-6, 'spec c-3 原本頭到 V15.0，和勾唇重疊 1.5 mm；已改成頭、舌下緣齊在勾頂上 0.1')
    rec(G, f'EB-K 舌頭 V{kb[1]:.2f}~{kb[3]:.2f}（高 {kb[3] - kb[1]:.2f}）放進上層槽上段 V{slot_top:.2f}~{n_top:.2f} 的上下餘量'
           '（盒子名目／下滑）', '／'.join(f'{x:.2f}' for x in room), '≥0', min(room) >= -1e-9)
    hd = slot_top - M.KEY_HEAD_WV.bounds[1]
    rec(G, 'EB-K 頭頂高出槽頂（頭壓在 #37 內面，鍵不會穿過槽）', hd, '≥1.0', hd >= 1.0)
    # ================================================================ H 盒內
    G = 'H 盒內'
    cs = {k: boxsolid(k, *bx) for k, bx in M.CONTENTS.items()}
    bx_by = {b.name: b for b in box_all}
    pairs = [('9V 電池', 'EB-F 電池架', 0.2), ('9V 電池', 'EB-S 電池後擋', 0.25), ('9V 電池', 'EB-WR 右牆', 0.2), ('9V 電池', 'EB-T 頂板', 0.25),
             ('9V 電池', 'EB-E 電池端擋', 5.0), ('電池扣（含線彎）', 'EB-E 電池端擋', 0.2),
             ('擴展板 PCB', 'EB-WR 右牆', 0.4), ('擴展板 PCB', 'EB-WL 左牆', 5.0), ('擴展板 PCB', 'EB-F 電池架', 0.4),
             ('開關本體', 'EB-WL 左牆', 1.0), ('開關本體', 'EB-E 電池端擋', 2.0),
             ('用到的 GVS 列＋杜邦頭＋彎線（下）', 'EB-WL 左牆', 2.0), ('用到的 GVS 列＋杜邦頭＋彎線（下）', 'EB-WR 右牆', 1.0),
             ('ESP32 開發板＋母座', 'EB-F 電池架', 2.0), ('未用排針列（上）', 'EB-F 電池架', 1.0), ('DC 座', 'EB-WR 右牆', 0.4)]
    for a, b, need in pairs:
        d = dist(cs[a], bx_by[b])
        rec(G, f'{a} ↔ {b}', d, f'≥{need}', d >= need - 1e-6)
    for a, b, need in (('開關本體', '擴展板 PCB', 2.0), ('開關本體', '未用排針列（上）', 1.0), ('開關本體', 'ESP32 開發板＋母座', 2.0),
                       ('9V 電池', '擴展板 PCB', 2.0), ('9V 電池', '開關本體', 2.0), ('電池扣（含線彎）', '開關本體', 2.0)):
        d = dist(cs[a], cs[b])
        rec(G, f'{a} ↔ {b}', d, f'≥{need}', d >= need - 1e-6)
    rec(G, '電池帶：電池頂凸出盒頂（捏得到）', pr.BOX['V_top'] - M.bat[2], '≥3', pr.BOX['V_top'] - M.bat[2] >= 3)
    gv = pr.BOX['W_back'] - M.CONTENTS['用到的 GVS 列＋杜邦頭＋彎線（下）'][5]
    rec(G, 'GVS 杜邦頭＋彎線最後端 W\' ↔ 盒後緣', gv, '≥2', gv >= 2)
    batt = cs['9V 電池']
    sweep = min(dist(Solid('電池', 'W', affinity.translate(batt.poly, 0, -dv), batt.rng, is_box=True), b)
                for dv in np.arange(0, 30.1, 1.0) for b in box_all if not b.name.startswith('EB-F'))
    rec(G, '電池往上拔出 30 mm 的掃掠 ↔ 盒體（不含下面的電池架）', sweep, '≥0.2', sweep >= 0.2 - 1e-6)
    sweep37 = min(dist(Solid('電池', 'W', affinity.translate(batt.poly, 0, -dv), batt.rng, is_box=True), s37)
                  for dv in np.arange(0, 30.1, 1.0))
    rec(G, '電池拔出掃掠 ↔ #37', sweep37, '≥0.2', sweep37 >= 0.2)
    up = boxsolid('USB 插頭', *M.USB_PLUG)
    dp = boxsolid('DC 插頭（直頭 40）', *M.DC_PLUG)
    for p in (up, dp):
        d = dist(p, bx_by['EB-WR 右牆'])
        rec(G, f'{p.name} ↔ 右牆（穿過服務窗）', d, '≥0.5', d >= 0.5)
        d = dist(p, s36)
        rec(G, f'{p.name}（伸出機身外）↔ #36 端板', d, '≥3', d >= 3)
    for k, (u, v) in enumerate(M.EN_BTN):
        finger = Solid(f'EN/BOOT{k + 1} 手指通道 Ø10', 'W', Point(u, v).buffer(5.0, 24), (M.dev[3] + 1.0, 90.0))
        d = min(dist(finger, b) for b in box_all)
        dw = min(dist(finger, ws) for kk, j, ws in M.WIRE_SOLIDS)
        rec(G, f'EN/BOOT 鍵 {k + 1}（U{u:.1f},V{v:.1f}）手指通道 ↔ 盒體／線', f'{d:.2f}／{dw:.2f}', '>0（盒子背面不加蓋）', d > 0 and dw > 0)
    for b in list(box_all) + [M.KEY]:
        mw = min_web(b.poly)
        rec(G, f'{b.name} 件數／最小料寬（近似）', f'{pieces(b.poly)}／{mw:.1f}', '=1／≥2', pieces(b.poly) == 1 and mw >= 2.0)
    for k in M.WIRES:
        rec(G, f'{k} 路徑長', M.WIRE_LEN[k], '—', True)
    # ================================================================ K 用板
    G = 'K 用板'
    A = sum(b.poly.area for b in box_all)
    bbA = sum((b.poly.bounds[2] - b.poly.bounds[0] + 2.5) * (b.poly.bounds[3] - b.poly.bounds[1] + 2.5) for b in box_all)
    sheet = PRM.SHEET[0] * PRM.SHEET[1]
    rec(G, '電子盒合板 7 片 淨面積／外包＋2.5 間距', f'{A:.0f}／{bbA:.0f} mm²（一張 {PRM.SHEET[0]:.0f}×{PRM.SHEET[1]:.0f} 的 '
        f'{A / sheet * 100:.1f}%／{bbA / sheet * 100:.1f}%）', '—', True)
    rec(G, '選用防拔鍵 ×2', f'{M.KEY_WV.area * 2:.0f} mm²', '—', True)
    rec(G, '顯示器側新增料', '0（#24/#26/#5/#37 只開孔）', '—', True)
    return rec.rows


# ===========================================================================
# 公開 API
# ===========================================================================
def build(cat: dict, pr: NS | None = None, checks: bool = True, others: dict | None = None) -> dict:
    """ebox 子系統：回傳 edits / new_parts / notes / warnings / checks / groups（INTERFACE.md）。

    pr：design_params() 的結果（None＝用目前 params.py）；checks=False 時略過檢查（敏感度掃描用）。
    others：{'s1': mods_s1.build() 的回傳, 'crosstrack': mods_crosstrack.build() 的回傳}（選用）。
      給了就用它們的實際結果（S1 keepout、#37／#26／#24 新切割、「5」「1」搬移、隔板 v2 外形）取代
      design/ 的名目 json 來做 Logo 避讓與檢查；切割幾何本身不受影響（除非 Logo 因此換方案）。"""
    return _run(cat, pr, checks, others)[0]


def recheck(cat: dict, results: dict, pr: NS | None = None) -> dict:
    """整合時重查：results＝{'crosstrack': …, 's1': …, 'ebox': …}（各子系統 build() 的回傳）。

    回傳 dict(checks, warnings, same_edits)：same_edits＝用實際結果重算的 ebox edits 是否和 results['ebox'] 相同
    （不同表示 Logo 方案因其他子系統而改變，要用新的 ebox 結果）。"""
    res, M, R = _run(cat, pr, True, {k: v for k, v in results.items() if k in ('s1', 'crosstrack')})
    same = True
    old = results.get('ebox')
    if old is not None:
        a = [(e['op'], e['part'], e.get('src'), round(e.get('dx', 0), 6), round(e.get('dy', 0), 6),
              e['geom'].wkt if 'geom' in e else e.get('d', e.get('text'))) for e in res['edits']]
        b = [(e['op'], e['part'], e.get('src'), round(e.get('dx', 0), 6), round(e.get('dy', 0), 6),
              e['geom'].wkt if 'geom' in e else e.get('d', e.get('text'))) for e in old['edits']]
        same = a == b
    return dict(checks=res['checks'], warnings=res['warnings'], same_edits=same)


def _run(cat, pr=None, checks=True, others=None):
    """build() 的本體；另外回傳內部模型 M 與參考幾何 R（自我測試、除錯用）。"""
    pr = pr if pr is not None else design_params()
    R = _ref(cat)
    if others:
        _apply_others(R, cat, others)
    M = model(R, pr)
    edits = _edits(cat, M, R, pr)
    new_parts, maps = _new_parts(M)
    _, eng37_boxes = _engrave37(M, R, pr)
    warnings = _warnings(M, R, pr)
    chk = _checks(cat, M, R, pr, eng37_boxes) if checks else []
    for r in chk:
        if not r['ok']:
            warnings.append(f'檢查未過：{r["name"]}＝{r["value"]}（要求 {r["expected"]}）')
    notes = _notes(M, R, pr, maps)
    res = dict(edits=edits, new_parts=new_parts, notes=notes, warnings=warnings, checks=chk, groups={},
               pending=_pending(M, pr), bom=_bom(M, pr))
    return res, M, R


def _bom(M, pr) -> list[dict]:
    """採購清單（spec c-4 ＋ 電子零件；INTERFACE.md 的 bom，export 合併成 report.md「材料與採購」）。數量是每套。"""
    D = M.D
    L = M.WIRE_LEN
    sens = {k.split()[0]: v for k, v in L.items() if '3P' in k}

    def pin_lbl(k):
        return f'{k}→{SENSOR_PINS[k]}'
    out = [
        dict(cat='電子', item='TM1637 四位數七段顯示器（0.36 吋）', qty=1, unit='個', who='講師預組',
             note=f'暫定 PCB {D["pcb_w"]:g}×{D["pcb_h"]:g}、固定孔距（全距）{2 * D["hole_dx"]:g}×{2 * D["hole_dy"]:g}，待實量',
             src='ebox a-1'),
        dict(cat='電子', item='ESP32 擴展板（GVS 排針）', qty=1, unit='塊', who='講師預組',
             note=f'暫定 {pr.BOARD["L"]:g}×{pr.BOARD["W"]:g}；鎖在 EB-B', src='ebox a-2'),
        dict(cat='電子', item='ESP32 DevKit 38P 開發板', qty=1, unit='塊', who='講師預組', note='插在擴展板上；燒錄程式',
             src='ebox a-2'),
        dict(cat='電子', item='9V 電池', qty=1, unit='顆', who='講師預組', note='放進電池帶；換電池見 spec a-4', src='ebox a-2'),
        dict(cat='電子', item='9V 電池扣＋線上開關＋DC 5.5×2.1 插頭（免焊線組）', qty=1, unit='組', who='講師預組',
             note=f'開關照預設是 {pr.SWITCH["cut_b"]:g}×{pr.SWITCH["cut_a"]:g} 面板式，卡進 EB-T（型式待決）；線長 ≥160 mm',
             src='ebox c-4'),
        dict(cat='電子', item='4P 母對母杜邦連排線 30 cm', qty=1, unit='條', who='講師預組',
             note=f'顯示器↔擴展板（路徑約 {L["顯示器 4P（G14/G13/V/G）"]:.0f} mm）', src='ebox c-4'),
        dict(cat='電子', item='3P 母對母杜邦線 20 cm（盒端 1×3 G-V-S）', qty=1, unit='條', who='講師預組',
             note='S1' + (f'（路徑約 {sens["S1"]:.0f} mm）' if 'S1' in sens else '') + f'；盒端貼標籤「{pin_lbl("S1")}」',
             src='ebox c-4、a-2 第 5 步'),
        dict(cat='電子', item='3P 母對母杜邦線 40 cm（盒端 1×3 G-V-S）', qty=3, unit='條', who='講師預組',
             note='S5／S10／S50（路徑約 ' + '／'.join(f'{sens[k]:.0f}' for k in ('S5', 'S10', 'S50') if k in sens)
                  + ' mm；S50 太緊改 50 cm）；盒端貼標籤' + ''.join(f'「{pin_lbl(k)}」' for k in ('S5', 'S10', 'S50')),
             src='ebox c-4、a-2 第 5 步'),
        dict(cat='耗材', item='感測器線盒端標籤（' + '、'.join(pin_lbl(k) for k in SENSOR_PINS) + '）',
             qty=len(SENSOR_PINS), unit='張', who='講師預組',
             note='每條感測器線的盒端 1×3 杜邦頭旁貼一張（寫要插的欄位）；模組端另貼站名標籤（S5／S10／S50、S1，見上）。'
                  '老師在盒內插線時照盒端標籤對欄位',
             src='ebox a-2 第 5 步'),
    ]
    if D['use_screws']:
        out += [dict(cat='五金', item='M2×8 尼龍螺絲＋M2 尼龍螺帽', qty=4, unit='組', who='講師預組',
                     note='TM1637 鎖 #24（螺絲頭在正面）', src='ebox c-4')]
    out += [
        dict(cat='五金', item='M3×12 尼龍螺絲', qty=4, unit='支', who='講師預組', note='擴展板鎖 EB-B', src='ebox c-4'),
        dict(cat='五金', item='M3 尼龍螺帽', qty=12, unit='顆', who='講師預組',
             note='每孔 3 顆：2 顆墊高 4.8＋EB-B 前面 1 顆', src='ebox c-4'),
        dict(cat='耗材', item='緞帶 5×80 mm', qty=1, unit='條', who='講師預組', note='墊在電池下當拉環', src='ebox c-4'),
        dict(cat='耗材', item='白膠、熱熔膠' + ('' if D['use_screws'] else '（TM1637 改用熱熔膠固定）'), qty=None, unit='少量',
             who='講師預組', note='盒體、鎖塊、卡匣用白膠；杜邦頭、線、開關、螺帽用熱熔膠', src='ebox c-4'),
    ]
    return out


def _pending(M, pr) -> list:
    """spec 最後「仍待使用者決定」的項目（這份草稿照預設值做）；export 寫進 report.md 待決事項。"""
    D = M.D
    return [
        f'待決：Logo 位置（照預設 {pr.LOGO_PLAN}；本次實際用 {M.LOGO_USED}）',
        f'待決：TM1637 實量（照暫定 PCB {D["pcb_w"]}×{D["pcb_h"]}、LED 塊 {D["body_w"]}×{D["body_h"]}、'
        f'孔距（全距）{2 * D["hole_dx"]}×{2 * D["hole_dy"]}＝params.TM1637 的 hole_dx={D["hole_dx"]}、hole_dy={D["hole_dy"]}（半距））',
        '待決：TM1637 用 M2 螺絲或熱熔膠（照預設 M2 尼龍螺絲，#24 切 4 個 M2 孔）',
        f'待決：擴展板與開發板實量、USB/DC 在哪一端（照暫定 {pr.BOARD["L"]}×{pr.BOARD["W"]}、開發板置中、USB/DC 在 +U）',
        '待決：電源免焊線組型式（照預設面板式開關，孔 9×13.5）',
        '待決：電池凸出盒頂（照預設 4 mm）',
        '待決：#5 只剩 2 支榫（照預設接受，試切 T5 確認）',
        '待決：感測器線盒端 1×3 G-V-S、線長 40 cm（照預設）',
        '待決：防拔鍵 EB-K（照預設輸出 2 片）',
    ]


def _notes(M, R, pr, maps) -> list:
    D = M.D
    z = R.S1
    n = []
    n.append(f'ebox（spec：design/ebox_final/spec.md）：TM1637 裝在 #24 正面左上（PCB 右緣 U{pr.DISP_UR}、上緣 V{M.Vp:.2f}，'
             f'LED 窗 U{M.WIN.bounds[0]:.2f}～{M.WIN.bounds[2]:.2f} × V{M.WIN.bounds[1]:.2f}～{M.WIN.bounds[3]:.2f}）；'
             f'電子盒掛在 #37 背面 U{M.U_L0:.1f}～{M.U_R1:.1f}、V{M.Vt:.1f}～{M.Vb:.2f}、W\'{pr.BOX["W_front"]:.2f}～{pr.BOX["W_back"]:.1f}。')
    n.append(f'Logo：方案 {M.LOGO_USED}（ΔU{M.LOGO_SHIFT[0]}、ΔV{M.LOGO_SHIFT[1]}；params.LOGO_PLAN={pr.LOGO_PLAN!r}），'
             f'9 個菱形孔用 translate_cut、雕刻 {LOGO_SRC} 用 move_engrave，原位置自動補回實料。'
             + (f'（{M.logo_note}）' if M.logo_note else ''))
    n.append('#5：本模組只減前上角（W\'0～{:.2f} × V{:.0f}～{:.2f}）；crosstrack 也改 #5，合併後只剩第二小榫＋後榫，'
             '試切 T5 要確認不晃（晃 >0.5 mm 就在 #5 與 #37 內面點白膠）。'.format(M.DIV5_CUT_W, V_TOP_26, M.DIV5_CUT_V))
    n.append('#37 感測器線孔 U{:.0f}～{:.0f} × V{:.0f}～{:.0f} 由本模組開（crosstrack spec b-7：位置由電子盒決定）；'
             'mods_crosstrack 不應再開同一孔（重複開時 compose 取聯集，結果相同）。'.format(*pr.SENSOR_HOLE_37))
    s1_real = '實際結果' in R.SOURCE['s1']
    ct_real = '實際結果' in R.SOURCE['crosstrack']
    if s1_real:     # 整合時（build_v2 用 others= 重跑）：禁區就是 mods_s1 的 keepout
        n.append('S1 禁區（mods_s1 keepout）：U{:.2f}～{:.2f} × V{:.2f}～{:.2f} × W\'{:.1f}～{:.1f}'
                 '（背蓋 S1-F＋模組後端／排針，每邊 +0.5，排針後方 +15 給杜邦頭與手指）。'
                 '左牆下限、#37 開孔距離都已用它重查。本次資料來源：{}。'.format(*z['U'], *z['V'], *z['W'], R.SOURCE['s1']))
    else:
        n.append('S1 禁區用 s1wall_final 實際範圍：U{:.2f}～{:.2f} × V{:.2f}～{:.2f} × W\'{:.1f}～{:.1f}'
                 '（背蓋 S1-F＋模組後端／排針，每邊 +{}，排針後方 +{} 給杜邦頭與手指）。'
                 '整合時要用 mods_s1 的結果重查（左牆下限、#37 開孔距離）：ebox.recheck(cat, results) 或 '
                 'build(cat, others={{"s1": …, "crosstrack": …}})。本次資料來源：{}。'.format(
                     *z['U'], *z['V'], *z['W'], S1_ZONE_MARGIN, S1_PLUG_SPACE, R.SOURCE['s1']))
    n.append('crosstrack 相關（#24 感測窗、「5」「1」新位置、#5/#6 v2 外形、#26 新槽）的檢查與 Logo 避讓，本次資料來源：'
             f'{R.SOURCE["crosstrack"]}' + ('。' if ct_real else '；整合時要用 mods_crosstrack 的結果重查（同上）。'))
    for k, v in maps.items():
        n.append(f'{k}：{v["desc"]}。')
    n.append('新零件雕刻面＝雷切上面（照區域座標不鏡像組裝時的朝向，見上）。WL、WR 外形除開孔外相同，靠雕刻代號分辨。'
             f'新零件都放同板群組 {EB_GROUP!r}（講師預組時一起拿）。')
    n.append('#37 雕刻在上面（朝機身背面）：掛勾槽旁往下箭頭、感測器線孔上方「感測器線」（angle=90，從背面看是正的）。')
    n.append('講師預組：盒體白膠（EB-E＋EB-F＋EB-S 子件 → WL＋EB-B → 放子件 → WR → EB-T）；TM1637 用 4 支 M2×8 尼龍螺絲鎖 #24'
             '（改熱熔膠時把 params.TM1637 的 use_screws 改成 False，#24 不切 M2 孔）；擴展板 4 支 M3×12＋墊高螺帽鎖 EB-B。'
             '老師：裝 #24 →線放進 #37 頂邊缺口→插 4 條感測器線（照盒端標籤：'
             + '、'.join(f'{k}→{v}' for k, v in SENSOR_PINS.items())
             + f'）→ 掛盒（抬 {M.SLIDE:.1f}、推、放）→（選用）從機身內側把 EB-K '
             '舌頭往後塞進上層掛勾槽上段（頭長出來的那端朝上）。')
    n.append('極小零件 EB-K（外包兩邊都 <10 mm）每套多切一整份備品（×2），排在同一份切割檔（parts.csv「備品」欄；'
             '使用者 2026-10-08 決定 3）。所有雕刻（箭頭、字）都是紅色 0.2 mm 線；代號字墨離切割線 ≥1.0。')
    n.append(f'模組尺寸：TM1637 pcb {D["pcb_w"]}×{D["pcb_h"]}、LED 塊 {D["body_w"]}×{D["body_h"]}、'
             f'固定孔距（全距）{2 * D["hole_dx"]:g}×{2 * D["hole_dy"]:g}（params.TM1637 的 hole_dx／hole_dy 是半距 '
             f'{D["hole_dx"]:g}／{D["hole_dy"]:g}）；擴展板 {pr.BOARD["L"]}×{pr.BOARD["W"]}；'
             f'9V {pr.BATT["L"]}×{pr.BATT["W"]}×{pr.BATT["Tk"]}（標「暫定」者待實量，'
             '最需要先量：TM1637 固定孔距（全距）V 向 ≤20.0（hole_dy＝半距 ≤10.0）、PCB 高 ≤25.5、杜邦頭長 ≤15、電池＋電池扣 ≤61）。')
    n.append('翻倒穩定（spec e-6）、正面可視性（spec e-7）需要質量模型與眼睛位置模型，本模組不重算。')
    return n


# ===========================================================================
# 自我測試：名目參數下和 geometry_final.json 比對
# ===========================================================================
def _hd(a, b):
    return float(a.hausdorff_distance(b))


# 和 design/ebox_final/geometry_final.json 已知不同的新零件：代號 → (理由, 參考外框 → 期望外框)
KNOWN_DEVIATION = {
    'EB-K': ('頭部下緣由 b9.9 改成 b8.3（V15.0→V13.4，和舌齊平）；參考的頭和上層勾唇重疊 1.5 mm、塞不進槽，'
             '2026-10-07 修正', lambda ref: ref.intersection(box(-50.0, -50.0, 50.0, 8.3))),
}


def self_test(cat=None, tol=0.01, verbose=True) -> dict:
    """名目 params（LOGO_PLAN 照 params）下比對 design/ebox_final/geometry_final.json；另跑 L1。"""
    cat = cat if cat is not None else C.load_catalog()
    J = json.loads(REF_JSON.read_text(encoding='utf-8'))
    pr = design_params({'LOGO_PLAN': 'L2'})
    res, M, R = _run(cat, pr)
    rows = []
    geo = []          # 幾何比對的差異（mm）

    def chk(name, val, ok_tol=tol, is_geo=True):
        rows.append((name, float(val), val <= ok_tol))
        if is_geo:
            geo.append(float(val))

    def poly_rec(pid, rec, mine_asm):
        chk(f'{pid} {rec["label"]}：asm', _hd(Polygon(rec['asm']), mine_asm))
        chk(f'{pid} {rec["label"]}：page', _hd(Polygon(rec['page']), to_page(pid, mine_asm)))
    m24 = J['mods']['#24']
    poly_rec('#24', m24[0], M.WIN)
    for k in range(4):
        r = m24[1 + k]
        u, v = M.holes[k]
        pg = to_page('#24', Point(u, v))
        chk(f'#24 {r["label"]} 中心 asm／page／直徑', max(abs(u - r['asm_center'][0]), abs(v - r['asm_center'][1]),
                                                     abs(pg.x - r['page_center'][0]), abs(pg.y - r['page_center'][1]),
                                                     abs(M.D['hole_d'] + 2 * pr.C_SCREW - r['d'])))
    lg = m24[5]
    dx, dy = page_delta('#24', *M.LOGO_SHIFT)
    chk('#24 Logo page_delta', max(abs(dx - lg['page_delta'][0]), abs(dy - lg['page_delta'][1])))
    nh = [affinity.translate(h, *M.LOGO_SHIFT) for h in R.LOGO_HOLES]
    worst = 0.0
    for rr in lg['new_holes']:
        ref = Polygon(rr['asm'])
        worst = max(worst, min(_hd(ref, x) for x in nh))
    chk('#24 Logo 9 個新孔 asm（逐孔最近）', worst)
    chk('#24 Logo 新外包（參考值只到 0.01）', max(abs(a - b) for a, b in zip(M.logo['L'].bounds, lg['new_bbox_asm'])), 0.006,
        is_geo=False)
    poly_rec('#26', J['mods']['#26'][0], M.NOTCH26_OUT)
    r5 = J['mods']['#5'][0]
    o5 = np.array(cat['#5'].bbox[:2])
    loc_rect = affinity.translate(to_page('#5', M.DIV5_CUT_WV), -o5[0], -o5[1])
    chk('#5 減除矩形（局部）', max(abs(a - b) for a, b in zip(loc_rect.bounds, r5['remove_local'])))
    ct5 = R.DIV_V2_LOCAL['#5'].difference(loc_rect)
    chk('#5 合併後外形（crosstrack 名目 v2 − 本修改，局部）', _hd(ct5, Polygon(r5['new_outline_local'])))
    chk('#5 合併後外形（W\'V）', _hd(M.DIV5_WV, Polygon(r5['new_outline_WV'])))
    m37 = J['mods']['#37']
    for k, s in enumerate(M.SLOTS37):
        poly_rec('#37', m37[k], s)
    poly_rec('#37', m37[4], M.CABLE_NOTCH)
    poly_rec('#37', m37[5], M.SENSOR_HOLE)
    # 新零件
    mine = {p['id']: p for p in res['new_parts']}
    for name, ref in J['new_parts'].items():
        code = name.split()[0]
        p = mine[code]
        g = p['geom']
        if code in KNOWN_DEVIATION:     # 已知偏離 geometry_final.json：改和「參考外形照修正規則裁過」的形狀比
            why, fix = KNOWN_DEVIATION[code]
            exp = fix(Polygon(ref['outline_local']))
            chk(f'新零件 {code} 外框（已知偏離參考：{why}）', _hd(Polygon(g.exterior), exp))
            rows.append((f'新零件 {code} 數量 {p["qty"]}／參考 {ref["qty"]}', 0.0, p['qty'] == ref['qty']))
            continue
        chk(f'新零件 {code} 外框', _hd(Polygon(g.exterior), Polygon(ref['outline_local'])))
        hs = [Polygon(r) for r in g.interiors]
        rh = [Polygon(r) for r in ref['holes_local']]
        ok_n = len(hs) == len(rh)
        rows.append((f'新零件 {code} 孔數 {len(hs)}／參考 {len(rh)}', 0.0 if ok_n else 1.0, ok_n))
        if ok_n and hs:
            chk(f'新零件 {code} 孔（逐孔最近）', max(min(_hd(a, b) for b in hs) for a in rh))
        rows.append((f'新零件 {code} 數量 {p["qty"]}／參考 {ref["qty"]}', 0.0, p['qty'] == ref['qty']))
        chk(f'新零件 {code} 淨面積差（mm²）', abs(g.area - ref['net_area']), 0.05, is_geo=False)
    # 文字：精確字墨外框在零件內、離切割線 ≥ TEXT_CLEAR（使用者 2026-10-08）
    for p in res['new_parts']:
        for t in p['texts']:
            tb = TP.ink_box(t['text'], t['x'], t['y'], t['size'], t['angle'], t['anchor'])
            dd = p['geom'].boundary.distance(tb) if p['geom'].contains(tb) else -1.0
            ok = dd >= TP.TEXT_CLEAR - 1e-6
            rows.append((f'新零件 {p["id"]} 雕刻「{t["text"]}」em {t["size"]:g} 字墨離切割線 {dd:.2f}（≥{TP.TEXT_CLEAR:g}）',
                         0.0 if ok else 1.0, ok))
    k = [p for p in res['new_parts'] if p['id'] == 'EB-K']
    ok = bool(k) and k[0].get('spare') == k[0]['qty']
    rows.append((f'EB-K 每套另切備品 {k[0].get("spare") if k else None}（＝每套數量）', 0.0 if ok else 1.0, ok))
    # 檢查與警告
    bad = [r for r in res['checks'] if not r['ok']]
    rows.append((f'名目 checks 全過（{len(res["checks"])} 項，未過 {len(bad)}）', float(len(bad)), not bad))
    rows.append((f'名目 warnings 為空（{len(res["warnings"])}）', float(len(res['warnings'])), not res['warnings']))
    # 與參考 checks.json 同名項目比對（數值）
    diff = _compare_ref_checks(res['checks'])
    # L1
    pr1 = design_params({'LOGO_PLAN': 'L1'})
    r1, M1, _ = _run(cat, pr1)
    ok1 = M1.LOGO_USED == 'L1' and abs(M1.logo['clear'] - 3.50) < 0.01
    rows.append((f'LOGO_PLAN=L1 可跑（用 {M1.LOGO_USED}，最小距 {M1.logo["clear"]:.2f}，checks 未過 '
                 f'{sum(not r["ok"] for r in r1["checks"])}，warnings {len(r1["warnings"])}）', 0.0, ok1 and not r1['warnings']))
    t1 = [e for e in r1['edits'] if e['op'] == 'translate_cut']
    d1 = page_delta('#24', -50.5, 7.0)
    okd = all(abs(e['dx'] - d1[0]) < 1e-6 and abs(e['dy'] - d1[1]) < 1e-6 for e in t1) and len(t1) == 9
    rows.append((f'L1 translate_cut ×{len(t1)} 平移量 (dx,dy)=({d1[0]:.2f},{d1[1]:.2f})', 0.0, okd))
    allok = all(r[2] for r in rows)
    maxdev = max(geo) if geo else 0.0
    if verbose:
        for nm, v, ok in rows:
            print(f'{"OK" if ok else "!!"} {nm}：{v:.4f}')
        print(f'\n幾何最大差異 {maxdev:.4f} mm；全部 {"通過" if allok else "未通過"}')
        print(f'與參考 checks.json 同名數值項目：{diff["n"]} 項，最大差 {diff["max"]:.3f}（{diff["worst"]}）；'
              f'不同名或文字項目 {diff["skipped"]} 項')
    return dict(ok=allok, rows=rows, maxdev=maxdev, ref_checks=diff, L1=dict(used=M1.LOGO_USED, clear=M1.logo['clear']))


def _compare_ref_checks(rows) -> dict:
    """本模組 checks 與 design/ebox_final/checks.json 同名、可轉數字的項目比對。"""
    try:
        ref = json.loads(REF_CHECKS.read_text(encoding='utf-8'))['checks']
    except Exception:
        return dict(n=0, max=0.0, worst='', skipped=0, items=[])
    refd = {(r['group'][:1], r['item']): r['value'] for r in ref}
    out = []
    skipped = 0
    for r in rows:
        key = (r['group'][:1], r['item'])
        if key not in refd:
            skipped += 1
            continue
        a, b = r['value'], refd[key]
        try:
            av = [float(x) for x in re.findall(r'-?\d+\.?\d*', str(a))]
            bv = [float(x) for x in re.findall(r'-?\d+\.?\d*', str(b))]
        except ValueError:
            skipped += 1
            continue
        if not av or len(av) != len(bv):
            skipped += 1
            continue
        out.append((max(abs(x - y) for x, y in zip(av, bv)), r['name'], a, b))
    out.sort(reverse=True)
    return dict(n=len(out), max=out[0][0] if out else 0.0, worst=out[0][1] if out else '', skipped=skipped, items=out)


# ===========================================================================
if __name__ == '__main__':
    import time
    t0 = time.time()
    cat = C.load_catalog()
    if '--selftest' in sys.argv:
        st = self_test(cat)
        print('\n參考 checks.json 差異最大的 10 項：')
        for d, nm, a, b in st['ref_checks']['items'][:10]:
            print(f'  {d:.3f}  {nm}：本模組 {a}／參考 {b}')
        sys.exit(0 if st['ok'] else 1)
    res = build(cat)
    print(f'ebox：edits {len(res["edits"])}、new_parts {len(res["new_parts"])}、checks {len(res["checks"])}'
          f'（未過 {sum(not r["ok"] for r in res["checks"])}）、warnings {len(res["warnings"])}；{time.time() - t0:.1f} s')
    print('\n[edits]')
    for e in res['edits']:
        g = e.get('geom')
        extra = f'頁座標外包 ({g.bounds[0]:.2f},{g.bounds[1]:.2f})～({g.bounds[2]:.2f},{g.bounds[3]:.2f})' if g is not None else \
            (f'src={e.get("src")} dx={e.get("dx"):.3f} dy={e.get("dy"):.3f}' if 'dx' in e else
             (f'「{e["text"]}」@({e["x"]:.2f},{e["y"]:.2f}) angle {e["angle"]}' if 'text' in e else 'd=…'))
        print(f'  {e["op"]:15s} {e["part"]:4s} {e.get("tag", "")}：{extra}')
    print('\n[new_parts]')
    for p in res['new_parts']:
        b = p['geom'].bounds
        print(f'  {p["id"]:6s} ×{p["qty"]} {p["name"]}：{b[2] - b[0]:.2f}×{b[3] - b[1]:.2f}、淨 {p["geom"].area:.0f} mm²、'
              f'孔 {len(p["geom"].interiors)}、雕刻 {[t["text"] for t in p["texts"]]}')
    print('\n[notes]')
    for s in res['notes']:
        print('  - ' + s)
    print('\n[warnings]' + ('（無）' if not res['warnings'] else ''))
    for s in res['warnings']:
        print('  ! ' + s)
    print('\n[checks]')
    for r in res['checks']:
        print(f'  {"OK" if r["ok"] else "!!"} {r["name"]}：{r["value"]}（要求 {r["expected"]}）' + (f'  ※{r["note"]}' if r['note'] else ''))

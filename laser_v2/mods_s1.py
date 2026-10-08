"""S1 卡匣（方案 A）：右櫃側板 #13 加高成 1 元滑道右牆 #13R，卡匣從 #37 背面插入。

來源
----
權威規格是 laser_v2/design/s1wall_final/spec.md（裁判版）。幾何移植自同資料夾的 design.py、
export.py；檢查移植自 checks.py 裡能由幾何算的項目（pybullet 模擬 sim*.py 不移植）。
名目參數（s1wall_final 的 MOD／DES）下，所有多邊形與 geometry_s1_final.json 相同（selftest() 比對）。

build(cat) 做什麼（回傳格式見 INTERFACE.md）
------------------------------------------
* #13 → #13R（renames）：在 (W',V) 平面算「加高區＋前榫 F1/F2＋後榫 B1」聯集、「牆槽＋角落讓位」差集，
  再用 frames 轉回 #13 原始頁座標。原 3 個 #12 槽、3 個齒不動。雕「13R 右」「S1 卡匣」。
  #13R 必須和 S1-B 排同一張板（牆面齊平）：groups={'#13R': 'S1-wall'}、S1-B 的 group='S1-wall'。
* #21：外形不改，只雕「21 左」（防裝反）。
* #26：加 F1、F2、C 三個槽。原檔齒孔偏移由 build_v2 用 frames.fix_26_tooth_hole() 修，本模組不碰。
* #37：卡匣窗、B1 槽、2 個 Ø3.4 孔（M3 尼龍螺絲），雕「S1 卡匣」。
* 新零件（3 mm 合板）：S1-B 座塊、S1-C 座板、S1-H 導流帽 ×N、S1-F 背蓋、S1-P 帽通道填塊
  （comp_band_free=True 時另加 S1-K 元件帶填塊）。
* checks：checks.py 能由幾何算的項目，加上跨子系統（#37 感測器線孔、S5 間隙、電子盒 S1 禁區）
  與 Go/No-Go（spec §d-3、§d-4）。不合格的 Go/No-Go 也寫進 warnings。
* 另回傳 keepout（電子盒用的 #37 背面 S1 禁區，組裝座標）——INTERFACE 之外的選用欄位。

座標（spec §b-0）
-----------------
* 組裝座標 (U,V,W')，見 frames.py。重力 (U,V,W') 分量＝(0, 0.866, 0.5)。
* (W',V) 平面零件：#13R（板在 U104.875～107.875，上面＝雕刻面在 U104.875 朝空腔）、S1-B、S1-H、S1-K。
  S1-B／S1-H：局部 x＝W'−W'min、y＝V−Vmin，U＝U0＋z，上面朝 −U。
  S1-C：雕刻面要朝 +U（貼牆、貼 S1-B），局部 x＝W'max−W'（鏡像）、y＝V−Vmin，U＝104.875−z。
* (U,V) 平面零件：#26、#37、S1-F、S1-P。S1-F／S1-P：局部 x＝U−Umin、y＝V−Vmin（從機身背面看），
  W'＝W1−z，上面朝 +W'（朝外）。
* 原始零件的修改一律換成「該零件原始頁座標」（frames.asm_to_page），新零件用上面的局部座標。

雕刻文字
--------
規格給的文字位置是「字的中心」。INTERFACE 的 add_engrave_text／texts 用基線錨點（SVG 慣例：
(x, y) 在基線上，anchor 決定左右），所以本模組把中心沿字的「下」方向移 TEXT_MID_EM×字高。
angle＝基線方向（頁座標，y 向下，度）。文字方向由 frames 算：#13R、#21 基線沿 +W'（由 #26 往 #37），
#37 沿 +U（從機身背面看由左往右），字的上方都是 −V；selftest() 會驗證不鏡像。
新零件的代號字（S1-B、S1-C、S1-F、S1-P）用 textpath.fit_text 排（使用者 2026-10-08）：字墨離切割線 ≥1.0、
離黏貼框／別的字 ≥0.4；代號先試 em 3.0～2.5，放不下才只刻單字母（B、P…）。所有雕刻都是紅色 0.2 mm 線
（compose.STYLE_ENGRAVE）。極小零件 S1-H、S1-P 帶 spare（每套多切一整份備品）。

參數
----
模組尺寸讀 params.MODULE（pcb_ovf、aperture 不在 MODULE 時用 MODULE_EXTRA）；牆頂讀
params.S1_WALL_TOP_V（30 或 38）；餘隙 c_opt／c_pcb 用 params.C_SENSOR；板厚 params.T_PLY。
S1 自己的設計參數在 DES。build(cat, module=..., des=...) 可臨時覆寫（測試、敏感度用）。

用法
----
    python -m laser_v2.mods_s1              # 印摘要與檢查
    python -m laser_v2.mods_s1 --selftest   # 與 geometry_s1_final.json 比對，並跑牆頂 V38
"""
from __future__ import annotations

import copy
import functools
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import linemerge, unary_union
from svgpathtools import parse_path

from . import frames as F
from . import params as P
from . import textpath as TP

HERE = Path(__file__).resolve().parent
REF_DIR = HERE / 'design' / 's1wall_final'
REF_JSON = REF_DIR / 'geometry_s1_final.json'

T = P.T_PLY

# ---------------------------------------------------------------------------
# 模組尺寸：params.MODULE 沒有的兩項（S1 專用預設，見 spec §d-1）
# ---------------------------------------------------------------------------
MODULE_EXTRA = dict(
    pcb_ovf=0.0,    # PCB 前端（W' 小）超出前臂外面的量；本體置中時＝(pcb_L−24)/2＝1.8
    aperture=1.0,   # 光窗寬（估計；光束餘量要扣半寬）
)

# ---------------------------------------------------------------------------
# S1 設計參數（spec §d-2；牆頂 wall_top 由 params.S1_WALL_TOP_V 給）
# ---------------------------------------------------------------------------
DES = dict(
    s_pcb=1.0,            # PCB 背面離牆滑道面 U107.875 的墊高＝1.0 mm 雙面泡棉膠（0～1.6，用來調光束 U）
    Vb=74.0,              # 光束中心 V（可用 72.5～74.9）
    wb_recess=0.3,        # 後臂內面在 #37 內面之後的量（wb＝W37_IN＋0.3＝29.3）
    c_tab=0.15,           # 木榫對槽單邊餘隙（長、寬都加）；S1 規格值，比 params.C_TAB 鬆
    c_opt=P.C_SENSOR,     # 光耦／臂／導流帽通過 #37 窗的單邊餘隙（0.4）
    c_pcb=P.C_SENSOR,     # PCB 通過 #37 窗的單邊餘隙（0.4）
    fit=0.1,              # 小填塊（S1-P、S1-K）比窗縮小的單邊量
    raise_V1=76.2,        # 加高區下緣 V（蓋過原頂邊 V75 與後上圓角）
    tabs_front=((50.5, 56.0), (68.0, 74.5)),   # #13R 前榫 F1、F2（插 #26）V 範圍：都在軌道以下
    tabs_back=((36.0, 48.0),),                 # #13R 後榫 B1（插 #37）V 範圍；上端不高於牆頂（見 geometry()）
    tab_len_26=2.6,       # 插 #26 的榫長（< 最薄板 2.7，榫尖不露出 #26 前面）
    tab_len_37=3.0,       # 插 #37 的榫長（＝#37 厚）
    corner_fix=True,      # 修 KNOWN_DEFECTS['37-cutout-corners'] 右側：#13R 在 #37 板厚內讓到 V84
    corner_fix_V=84.0,
    cap=True,             # 前臂導流帽 S1-H
    cap_h=4.5,            # 帽頂前緣比臂頂高（沿 V）；坡角約 63°
    cover_v1=78.0,        # 背蓋 S1-F 下緣 V（#13R 在 #37 後方的櫃頂邊約 V79.9）
    cover_left=10.0,      # 背蓋左緣（U 小）超出卡匣窗的量（螺絲孔在這段）
    cover_right=4.0,      # 背蓋右緣超出卡匣窗的量
    cover_top=3.5,        # 背蓋上緣超出卡匣窗的量
    cover_open=0.7,       # 背蓋外形做 0.7 mm 開運算，去掉細條
    screw_dU=5.0,         # 螺絲孔中心在窗左緣外 5.0
    screw_dV=(2.0, 4.5),  # 上孔在窗上緣下 2.0、下孔在背蓋下緣上 4.5
    screw_hole_cover=3.4,  # M3 尼龍螺絲過孔（背蓋）
    screw_hole_37=3.4,     # #37 孔（M3 螺帽預黏在空腔側）；改 M2.6 自攻螺絲時改 2.2、不黏螺帽
    tabC_front_v=(59.0, 65.0),   # S1-C 前榫（插 #26 槽 C）V 範圍
    s1c_w0=0.6,           # S1-C 前緣 W'（離 #26 背面 0.6）
    s1c_v1=78.5,          # S1-C 下緣 V
    comp_band_free=False,  # 實品 PCB 在 W'29～35、本體以上那條帶沒有元件時改 True：背蓋不切元件帶、另切 S1-K
    hdr_len=7.62,         # 3P 排針沿 V 長
    hdr_extra=5.5,        # 排針塑膠座 2.5＋線彎 3（加在 MODULE['hdr_up'] 上）
    # 雕刻（字的中心；見模組說明）
    text13_W=15.0, text13_dV=(10.0, 16.0),   # #13R：W'15、V＝牆頂＋10（「13R 右」）／＋16（「S1 卡匣」）
    text21_WV=(12.0, 80.0),                  # #21「21 左」
    text37_V=46.5, text37_gap=2.0,           # #37「S1 卡匣」：V46.5，起點在 B1 槽右緣＋2.0
    s1c_text_V=70.0,                         # S1-C「S1-C 前→」的 V
    cover_text_dV=7.3,                       # S1-F「S1 ↑」離背蓋上緣
)

# ---------------------------------------------------------------------------
# 其他子系統與機身的協調數字（組裝座標；來源寫在旁邊）
# ---------------------------------------------------------------------------
S5_W_MAX = 10.0        # crosstrack_final：S5 不論翼朝哪邊，最終位置＋安裝掃掠都在 W'≤10.0
SENSOR_HOLE_37 = (88.0, 100.0, 40.0, 46.0)   # ebox_final：#37 感測器線孔 U88～100 × V40～46
CABLE_HOLE = (91.5, 101.5, 103.5, 108.0)     # crosstrack_final：右下排線孔 U91.5～101.5 × V103.5～108
MOTOR_U = 72.07        # TT 馬達盒右壁 U（s1wall_final checks.py）
V37_BOTTOM = 82.0      # #37 下方開口頂（#37 底邊）V（frames.py 說明）
COIN_D, COIN_T = 20.0, 1.85   # 1 元：直徑、厚度（保守）
SHEET_AREA = P.SHEET[0] * P.SHEET[1]
S1_SOLIDS = ('pcb', 'comp', 'body', 'front_arm', 'solder')   # 會進到滑道附近的模組實體
TEXT_MID_EM = 0.39     # 微軟正黑體：字的墨色垂直中心在基線上 0.39 em（-0.05～0.83 em 的中點）
CODE_SIZES = (3.0, 2.9, 2.8, 2.7, 2.6, 2.5)   # 新零件代號字 em（使用者 2026-10-08：太小的字放大到 2.5～3）


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def _rect(a0, a1, b0, b1):
    return box(min(a0, a1), min(b0, b1), max(a0, a1), max(b0, b1))


def _circ(u, v, d):
    """Ø d 圓孔（36 邊；Ø3.4 時弦高誤差 0.006 mm，與 s1wall_final 相同）。"""
    return Point(u, v).buffer(d / 2, quad_segs=9)


def _r(v, n=2):
    return None if v is None else round(float(v), n)


def _f(v: float) -> str:
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def _line_d(line) -> str:
    """LineString／MultiLineString → SVG path d（絕對座標）。"""
    lines = [line] if isinstance(line, LineString) else list(line.geoms)
    out = []
    for ln in lines:
        c = list(ln.coords)
        out.append('M ' + ' L '.join(f'{_f(x)},{_f(y)}' for x, y in c))
    return ' '.join(out)


def _top_U(pid: str) -> float:
    """側板（#13、#21）上面（z=0，雕刻面）的 U。"""
    return float(F.frame(pid).to_asm(0.0, 0.0, 0.0)[0])


def _affine(pid: str, axes: tuple[str, str], fixed: float):
    """組裝座標某平面 (a, b) → pid 的原始頁座標 (x, y) 的仿射參數（shapely 格式）與板內深度 z。

    axes＝('W','V') 或 ('U','V')；fixed＝第三軸的值（側板用上面 U、#26/#37 用板中心 W'）。"""
    fr = F.frame(pid)
    third = ({'U', 'V', 'W'} - set(axes)).pop()

    def page(a, b):
        q = {axes[0]: a, axes[1]: b, third: fixed}
        return fr.to_page(q['U'], q['V'], q['W'])
    o, pa, pb = page(0.0, 0.0), page(1.0, 0.0), page(0.0, 1.0)
    if max(abs(pa[2] - o[2]), abs(pb[2] - o[2])) > 1e-9:
        raise ValueError(f'{pid} 的 {axes} 平面不平行板面')
    return [float(pa[0] - o[0]), float(pb[0] - o[0]), float(pa[1] - o[1]), float(pb[1] - o[1]),
            float(o[0]), float(o[1])], float(o[2])


def _angle_of(A, da: float, db: float) -> float:
    """組裝平面方向 (da, db) 在頁座標的角度（度，y 向下）。"""
    x = A[0] * da + A[1] * db
    y = A[2] * da + A[3] * db
    return math.degrees(math.atan2(y, x))


def _text(text: str, cx: float, cy: float, size: float, angle: float = 0.0, anchor: str = 'middle') -> dict:
    """字的中心 (cx, cy)（anchor='start' 時 cx 是起點）→ INTERFACE 的基線錨點文字 dict。"""
    a = math.radians(angle)
    k = TEXT_MID_EM * size
    return dict(text=text, x=round(cx - math.sin(a) * k, 4), y=round(cy + math.cos(a) * k, 4),
                size=size, angle=round(angle, 6), anchor=anchor)


def _center_of(t: dict) -> tuple[float, float]:
    """_text() 的反算：基線錨點 → 字的中心（anchor 方向不動）。"""
    a = math.radians(t['angle'])
    k = TEXT_MID_EM * t['size']
    return t['x'] + math.sin(a) * k, t['y'] - math.cos(a) * k


# ---------------------------------------------------------------------------
# 參數
# ---------------------------------------------------------------------------
def module_params(override: dict | None = None) -> dict:
    """S1 用到的模組尺寸：params.MODULE ＋ MODULE_EXTRA（MODULE 有就用 MODULE 的）＋ override。"""
    M = dict(MODULE_EXTRA)
    M.update({k: v for k, v in P.MODULE.items()})
    if override:
        M.update(override)
    return M


def design_params(override: dict | None = None) -> dict:
    Dd = copy.deepcopy(DES)
    Dd['wall_top'] = float(P.S1_WALL_TOP_V)
    if override:
        Dd.update(override)
    return Dd


@functools.lru_cache(maxsize=1)
def _geo() -> dict:
    """機身固定量（由 frames 算）：#13R 板面 U、#7 右面 U、#37 內外面 W'。"""
    U13 = F.frame('#13').plane()[1:]
    U7 = F.frame('#7').plane()[1:]
    return dict(U_out=U13[0], U_in=U13[1], U7_in=U7[0], W37=F.W37_IN, W37o=F.W37_IN + T)


def derived(M: dict, Dd: dict, G: dict | None = None) -> dict:
    """spec §b-1 推導量（名目：光束 U118.475、V74、W'19.3→29.3）。"""
    G = G or _geo()
    h_sb = M['arm_top'] - M['slot_d']                     # 槽底（本體頂）離 PCB 元件面
    h_beam = h_sb + M['beam_sb']                          # 光束離 PCB 元件面
    U_pcb_back = G['U_in'] + Dd['s_pcb']
    U_pcb = U_pcb_back + M['pcb_t']
    wb = G['W37'] + Dd['wb_recess']
    wa = wb - M['slot_w']
    fa = (wa - M['arm_t'], wa)
    ba = (wb, wb + M['arm_t'])
    pw0 = fa[0] - M['pcb_ovf']
    pw1 = pw0 + M['pcb_L']
    Vb = Dd['Vb']
    av = (Vb - M['arm_w'] / 2, Vb + M['arm_w'] / 2)
    pv1 = av[1] + M['body_e']
    pv0 = pv1 - M['pcb_W']
    D = dict(h_sb=h_sb, h_beam=h_beam, h_beam_back=h_beam + M['pcb_t'],
             U_pcb_back=U_pcb_back, U_pcb=U_pcb, U_sb=U_pcb + h_sb, Ub=U_pcb + h_beam,
             U_tip=U_pcb + M['arm_top'], U_comp=U_pcb + M['comp_h'], U_solder=U_pcb_back - M['back_h'],
             wa=wa, wb=wb, front_arm=fa, back_arm=ba, pcb_w=(pw0, pw1), pcb_v=(pv0, pv1),
             Vb=Vb, arm_v=av, body_len=2 * M['arm_t'] + M['slot_w'])
    D['cap_Vr'] = av[0] - Dd['cap_h']
    D['cap_U'] = (D['U_sb'], D['U_tip'])
    return D


# ---------------------------------------------------------------------------
# 原始零件在組裝座標（檢查用）
# ---------------------------------------------------------------------------
def _env(cat) -> dict:
    """#24/#26/#37 在 (U,V) 的外形與孔、軌道擬合（#24 斜槽下緣）、1 元開口。"""
    def asm(pid):
        fr = F.frame(pid)
        return fr.geom_asm(cat[pid].geom, fr.thickness / 2, ('U', 'V'))
    G24, G26, G37 = asm('#24'), asm('#26'), asm('#37')
    E = dict(G24=G24, G26=G26, G37=G37,
             O24=Polygon(G24.exterior), O26=Polygon(G26.exterior), O37=Polygon(G37.exterior),
             H24=[Polygon(h) for h in G24.interiors], H26=[Polygon(h) for h in G26.interiors],
             H37=[Polygon(h) for h in G37.interiors])
    slot24 = max(E['H24'], key=lambda p: p.area)
    pts = []
    for U in np.arange(80, 232, 1.0):
        L = LineString([(U, -5), (U, 130)]).intersection(slot24)
        if not L.is_empty:
            pts.append((U, L.bounds[3]))
    pts = np.array(pts)
    m, b = np.linalg.lstsq(np.vstack([pts[:, 0], np.ones(len(pts))]).T, pts[:, 1], rcond=None)[0]
    E['RAIL_M'], E['RAIL_B'] = float(m), float(b)
    E['ANG'] = math.atan(m)
    op = [p for p in E['H26'] if p.area > 300 and abs(p.bounds[0] - 114.1) < 1.0]
    if len(op) != 1:
        raise RuntimeError(f'#26 找不到 1 元開口（{len(op)} 個候選）')
    E['OP1'] = op[0]
    E['OPEN1'] = (op[0].bounds[0], op[0].bounds[2])
    seg = LineString([(114.5, -5), (114.5, 130)]).intersection(op[0])
    E['LIP_V0'] = seg.bounds[3]        # 開口下緣（唇）在 U114.5 的 V（＝50.205）
    E['OPEN_TOP_V'] = seg.bounds[1]    # 開口右端頂緣（＝31.43）
    E['eng26'] = []
    fr26 = F.frame('#26')
    for e in cat['#26'].engrave:
        mm = re.search(r'\bd="([^"]*)"', e)
        if mm:
            x0, x1, y0, y1 = parse_path(mm.group(1)).bbox()
            E['eng26'].append(fr26.geom_asm(box(x0, y0, x1, y1), 1.5, ('U', 'V')))
    return E


def railV(E, U):
    return E['RAIL_M'] * np.asarray(U, float) + E['RAIL_B']


def exitV(W):
    """滑道出口平面（間隔條 #7 斜底邊）：貼 #26 V98、貼 #37 V82。"""
    return 98.0 - 16.0 * np.asarray(W, float) / 29.0


def slope_deg(dW, dV):
    """(W',V) 平面內方向 (dW, dV) 對世界水平的夾角（往下為正）。"""
    return math.degrees(math.asin((0.5 * dW + 0.866025 * dV) / math.hypot(dW, dV)))


# ---------------------------------------------------------------------------
# 幾何（組裝座標；移植 design.py）
# ---------------------------------------------------------------------------
def geometry(cat, M: dict | None = None, Dd: dict | None = None) -> dict:
    """所有新增／修改幾何（shapely）。(W',V) 平面用座標 (W', V)；(U,V) 平面用 (U, V)。"""
    M = module_params() if M is None else M
    Dd = design_params() if Dd is None else Dd
    G = _geo()
    D = derived(M, Dd, G)
    ct, co, cp, fit = Dd['c_tab'], Dd['c_opt'], Dd['c_pcb'], Dd['fit']
    U_out, U_in, W37, W37o = G['U_out'], G['U_in'], G['W37'], G['W37o']
    fa, ba, av = D['front_arm'], D['back_arm'], D['arm_v']
    pw0, pw1 = D['pcb_w']
    pv0, pv1 = D['pcb_v']
    Ub0, Up = D['U_pcb_back'], D['U_pcb']
    out = dict(D=D, M=M, Dd=Dd, G=G)

    # ---- 模組（組裝座標盒：U0, U1, V0, V1, W0, W1） ----
    hdr_v = (pv0 + (M['pcb_W'] - Dd['hdr_len']) / 2, pv0 + (M['pcb_W'] + Dd['hdr_len']) / 2)
    out['mod'] = dict(
        pcb=(Ub0, Up, pv0, pv1, pw0, pw1),
        comp=(Up, D['U_comp'], pv0, av[0], pw0, pw1),                 # 元件區（保守：本體以外整片）
        solder=(D['U_solder'], Ub0, pv0, pv1, pw0, pw1),
        body=(Up, D['U_sb'], av[0], av[1], fa[0], ba[1]),
        front_arm=(Up, D['U_tip'], av[0], av[1], fa[0], fa[1]),
        back_arm=(Up, D['U_tip'], av[0], av[1], ba[0], ba[1]),
        header=(Up, Up + M['hdr_up'] + Dd['hdr_extra'], hdr_v[0], hdr_v[1], ba[1], pw1),  # 短端直立排針＋杜邦頭＋線彎
    )
    out['beam'] = dict(U=D['Ub'], V=D['Vb'], w0=D['wa'], w1=D['wb'])

    # ---- S1-H 前臂導流帽（(W',V) 剖面三角形，沿 U 疊 N 片；片數＝round(槽深/板厚)） ----
    Vr = D['cap_Vr']
    out['S1H_WV'] = Polygon([(fa[0], av[0]), (fa[0], Vr), (fa[1], av[0])])
    nl = max(1, int(round(M['slot_d'] / T))) if Dd['cap'] else 0
    out['cap_layers'] = nl
    out['S1H_U'] = [(D['U_sb'] + k * T, D['U_sb'] + (k + 1) * T) for k in range(nl)]
    out['cap_U'] = (out['S1H_U'][0][0], out['S1H_U'][-1][1]) if nl else (D['U_sb'], D['U_sb'])
    out['cap_slope_deg'] = slope_deg(fa[1] - fa[0], av[0] - Vr)

    # ---- S1-B 座塊（牆槽內 U104.875～107.875） ----
    bv0, bv1 = pv0, pv1 - 1.0                  # 上緣齊 PCB，下緣縮 1.0 讓焊腳
    bw0 = pw0                                  # 前緣齊 PCB
    tabB_v = (bv0, bv0 + 6.0)                  # 後榫 6 mm（沿 V）
    sB = unary_union([_rect(bw0, W37, bv0, bv1), _rect(W37, W37o + T, tabB_v[0], tabB_v[1])])
    reliefB = _rect(bw0 + 2.0, W37 - 3.0, bv0 + 3.0, bv1 - 2.0)   # 焊點讓位孔；四周料 2.0/3.0/3.0/2.0
    out['S1B_WV'] = sB.difference(reliefB)
    out['S1B_relief'] = reliefB
    out['tabB_v'] = tabB_v

    # ---- #13R 牆槽（開向 #37） ----
    out['wall_slot_WV'] = _rect(bw0 - 0.5, W37 + 1.0, bv0 - 0.2, bv1 + 0.2)

    # ---- S1-C 座板（空腔側 U101.875～104.875） ----
    cv0, cv1 = bv0 - 3.2, Dd['s1c_v1']
    cw0 = Dd['s1c_w0']
    a, b = Dd['tabC_front_v']
    tabC = Polygon([(cw0, a), (cw0 - 2.0, a + 0.6), (cw0 - 2.6, a + 1.0), (cw0 - 2.6, b - 1.0),
                    (cw0 - 2.0, b - 0.6), (cw0, b)])        # 前榫尖端收窄到 4 mm，自己找 #26 槽 C
    tabC_back_v = tabB_v                       # 與 S1-B 後榫並排：背蓋上合成一個槽
    out['S1C_WV'] = unary_union([_rect(cw0, W37, cv0, cv1), tabC, _rect(W37, W37o + T, *tabC_back_v)])
    out['tabC_back_v'] = tabC_back_v
    out['S1C_v'] = (cv0, cv1)
    U_car = (U_out - T, U_out)
    out['U_car'] = U_car

    # ---- #37 窗：卡匣通過 #37 時的 (U,V) 輪廓聯集 ----
    v_top_mod = Vr if Dd['cap'] else av[0]
    parts = [
        _rect(U_car[0] - 0.3, U_car[1], cv0 - 0.3, cv1 + 0.3),                  # S1-C
        _rect(U_out, U_in, bv0 - 0.3, bv1 + 0.3),                                # S1-B
        _rect(min(U_in, Ub0) - 0.1, Up + co, pv0 - cp, pv1 + cp),                # PCB＋泡棉膠
        _rect(D['U_solder'] - 0.2, Ub0, pv0 - cp, pv1 + cp),                     # PCB 背面焊點
        _rect(Up, Up + max(M['comp_h'] + co, T + 0.4), pv0 - cp, pv1 + cp),      # 元件帶
        _rect(Up, D['U_tip'] + co, v_top_mod - co, av[1] + co),                  # 本體＋臂＋導流帽
    ]
    win = unary_union(parts).simplify(0.001)
    out['win37_UV'] = win
    out['win37_parts'] = parts

    # ---- S1-P 帽通道填塊、S1-K 元件帶填塊（貼背蓋前面 W'29～32） ----
    out['S1P_UV'] = (_rect(D['U_comp'] + co, D['U_tip'] + co - fit, Vr - co + fit, av[0] - co)
                     if Dd['cap'] else None)
    kb_u = (Up + 0.2, Up + 0.2 + T)
    k_v1 = (Vr - co + fit) if Dd['cap'] else (av[0] - co)
    out['S1K_UV'] = _rect(kb_u[0], kb_u[1], pv0 - cp + 0.15, k_v1 - 0.15) if Dd['comp_band_free'] else None

    # ---- S1-F 背蓋（貼 #37 外面 W'32～35） ----
    fb = win.bounds
    cover = _rect(fb[0] - Dd['cover_left'], fb[2] + Dd['cover_right'], fb[1] - Dd['cover_top'], Dd['cover_v1'])
    cut_mod = unary_union([
        _rect(U_in - 0.1, Up + co, pv0 - cp, pv1 + cp),                                       # PCB＋泡棉膠
        (_rect(Up, D['U_comp'] + co, pv0 - cp, av[0]) if not Dd['comp_band_free'] else Polygon()),   # 元件帶
        _rect(Up, D['U_tip'] + co, av[0] - co, av[1] + co),                                   # 本體＋後臂
        box(min(U_in, D['U_solder']) - 0.2, av[0] - co, 400, 400),                            # 後臂以下整塊（不留細條）
    ])
    slotsF = unary_union([_rect(U_car[0] - ct, U_car[1] + ct, tabC_back_v[0] - ct, tabC_back_v[1] + ct),
                          _rect(U_out - ct, U_in + ct, tabB_v[0] - ct, tabB_v[1] + ct)])
    sF = cover.difference(cut_mod).difference(slotsF)
    k = Dd['cover_open']
    sF = sF.buffer(-k, join_style='mitre').buffer(k, join_style='mitre').intersection(cover)
    screws = [(fb[0] - Dd['screw_dU'], fb[1] + Dd['screw_dV'][0]),
              (fb[0] - Dd['screw_dU'], Dd['cover_v1'] - Dd['screw_dV'][1])]
    for (u, v) in screws:
        sF = sF.difference(_circ(u, v, Dd['screw_hole_cover']))
    out['S1F_UV'] = sF
    out['S1F_rect'] = cover
    out['screws_UV'] = screws

    # ---- #13R（(W',V) 平面） ----
    o13 = F.frame('#13').geom_asm(cat['#13'].geom, 0.0, ('W', 'V'))
    out['orig13_WV'] = o13
    wt = Dd['wall_top']
    out['raise_WV'] = _rect(0.0, W37, wt, Dd['raise_V1'])
    tl26, tl37 = Dd['tab_len_26'], Dd['tab_len_37']
    # 後榫上端不高於牆頂（牆頂 V30 時就是規格的 V36～48；V38 時變 V38～48，否則榫會凸出牆頂）
    tabs_back = [(max(a_, wt), b_) for a_, b_ in Dd['tabs_back']]
    out['tabs_back_eff'] = tabs_back
    tabs = ([(f'前榫 F{i + 1}', _rect(-tl26, 0.0, a_, b_)) for i, (a_, b_) in enumerate(Dd['tabs_front'])]
            + [(f'後榫 B{i + 1}', _rect(W37, W37 + tl37, a_, b_)) for i, (a_, b_) in enumerate(tabs_back)])
    out['tabs13_WV'] = tabs
    wall = unary_union([Polygon(o13.exterior), out['raise_WV']] + [t for _, t in tabs]).difference(out['wall_slot_WV'])
    out['corner_notch_WV'] = None
    if Dd['corner_fix']:
        out['corner_notch_WV'] = _rect(W37, W37o + 0.2, 77.0, Dd['corner_fix_V'])
        wall = wall.difference(out['corner_notch_WV'])
    for h in o13.interiors:
        wall = wall.difference(Polygon(h))
    out['wall13R_WV'] = wall

    # ---- #26 新槽 ----
    s26 = {f'F{i + 1}': _rect(U_out - ct, U_in + ct, a_ - ct, b_ + ct) for i, (a_, b_) in enumerate(Dd['tabs_front'])}
    s26['C'] = _rect(U_car[0] - ct, U_car[1] + ct, Dd['tabC_front_v'][0] - ct, Dd['tabC_front_v'][1] + ct)
    out['slots26_UV'] = s26

    # ---- #37 新槽與螺絲孔 ----
    out['slots37_UV'] = {f'B{i + 1}': _rect(U_out - ct, U_in + ct, a_ - ct, b_ + ct) for i, (a_, b_) in enumerate(tabs_back)}
    out['holes37_UV'] = [_circ(u, v, Dd['screw_hole_37']) for (u, v) in screws]
    return out


# ---------------------------------------------------------------------------
# 新零件局部座標
# ---------------------------------------------------------------------------
def _local(g, a0=None, b0=None):
    b = g.bounds
    a0 = b[0] if a0 is None else a0
    b0 = b[1] if b0 is None else b0
    return affinity.translate(g, -a0, -b0), (a0, b0)


def _mirror_WV(g, W1, V0):
    """S1-C：x＝W1−W'、y＝V−V0（雕刻面朝 +U 的合法擺法）。"""
    return affinity.affine_transform(g, [-1, 0, 0, 1, W1, -V0])


def _code_text(geom, code: str, short: str, prefer, avoid=None) -> list[dict]:
    """新零件代號字（使用者 2026-10-08）：字墨離切割線 ≥1.0（textpath.TEXT_CLEAR）、離其他雕刻 ≥0.4。
    先試完整代號 em 3.0～2.5；放不下就只刻單字母 short（em 3.0～2.5）；再放不下才縮小單字母。
    prefer＝偏好的字中心（放得下就用，否則取最近的可用位置）。回傳 texts list（放不下回傳空 list）。"""
    for txt, sizes in ((code, CODE_SIZES), (short, CODE_SIZES), (short, (2.4, 2.2, 2.0, 1.8))):
        f = TP.fit_text(geom, txt, sizes, avoid=avoid, prefer=prefer)
        if f:
            return [TP.text_spec(f)]
    return []


def new_parts_geometry(g: dict) -> dict:
    """各新零件的局部外形、雕刻與文字（與 geometry_s1_final.json 的 new_parts[*].local 同一座標）。"""
    D, Dd, G = g['D'], g['Dd'], g['G']
    out = {}
    # S1-B
    locB, (wB, vB) = _local(g['S1B_WV'])
    tx0, tx1 = G['W37'] - wB, G['W37o'] + T - wB          # 後榫範圍（局部 x）
    out['S1-B'] = dict(geom=locB, origin=(wB, vB), engrave=[],
                       texts=_code_text(locB, 'S1-B', 'B', ((tx0 + tx1) / 2, (g['tabB_v'][0] + g['tabB_v'][1]) / 2 - vB)))
    # S1-C（鏡像）
    sC = g['S1C_WV']
    W1c, V0c = sC.bounds[2], sC.bounds[1]
    locC = _mirror_WV(sC, W1c, V0c)
    frameB = Polygon(_mirror_WV(g['S1B_WV'], W1c, V0c).exterior).simplify(0.01)
    # 黏貼框：只雕在 S1-C 實料內的那幾段（和 S1-C 外框重合的段落本來就是切割線，不重複雕）
    fc = list(frameB.exterior.coords)
    cv = [Point(c) for c in locC.exterior.coords]
    keep = []
    for i in range(len(fc) - 1):
        seg = LineString([fc[i], fc[i + 1]])
        ts = sorted({0.0, 1.0} | {seg.project(p, normalized=True) for p in cv if seg.distance(p) < 1e-6})
        for t0, t1 in zip(ts[:-1], ts[1:]):                # 在 S1-C 頂點處切開，逐段判斷是否壓在外框上
            a, b = seg.interpolate(t0, normalized=True), seg.interpolate(t1, normalized=True)
            if t1 - t0 > 1e-9 and locC.exterior.distance(seg.interpolate((t0 + t1) / 2, normalized=True)) > 1e-6:
                keep.append(LineString([a, b]))
    eng = linemerge(keep)
    xa, xb = W1c - D['pcb_w'][0], W1c - Dd['s1c_w0']                # S1-B 框前緣、S1-C 前緣（局部 x）
    # 「S1-C 前→」：規格字高 2.5、在 S1-B 框和 S1-C 前緣之間；字墨離前緣（切割）≥1.0、離框線 ≥0.4，
    # 空間不夠就縮小（→ 要指向前，所以只橫排）
    fC = TP.fit_text(locC, 'S1-C 前→', (2.5, 2.4, 2.3, 2.2, 2.1, 2.0, 1.8), avoid=eng,
                     prefer=((xa + xb) / 2, Dd['s1c_text_V'] - V0c))
    out['S1-C'] = dict(geom=locC, origin=(W1c, V0c), engrave=[_line_d(eng)], engrave_geom=eng, frame_full=frameB,
                       texts=[TP.text_spec(fC)] if fC else [])
    # S1-H
    if g['cap_layers']:
        locH, (wH, vH) = _local(g['S1H_WV'])
        out['S1-H'] = dict(geom=locH, origin=(wH, vH), engrave=[], texts=[])
    # S1-F
    sF = g['S1F_UV']
    locF, (uF, vF) = _local(sF)
    right0 = D['U_comp'] + Dd['c_opt']               # 背蓋右塊左緣（元件帶缺口邊）
    rb = g['S1F_rect'].bounds
    hy = [v - vF for _, v in g['screws_UV']]
    tF = [_text('S1 ↑', (right0 + rb[2]) / 2 - uF, Dd['cover_text_dV'], 4.0)]
    tF += _code_text(locF, 'S1-F', 'F', (g['screws_UV'][0][0] - uF, (hy[0] + hy[1]) / 2),
                     avoid=TP.ink_box(**tF[0]))         # 代號 em 3（使用者 2026-10-08），在兩個螺絲孔之間
    out['S1-F'] = dict(geom=locF, origin=(uF, vF), engrave=[], texts=tF)
    # S1-P
    if g['S1P_UV'] is not None:
        locP, (uP, vP) = _local(g['S1P_UV'])
        bb = locP.bounds
        out['S1-P'] = dict(geom=locP, origin=(uP, vP), engrave=[],
                           texts=_code_text(locP, 'S1-P', 'P', (bb[2] / 2, bb[3] / 2)))
    # S1-K（條件式）
    if g['S1K_UV'] is not None:
        locK, (uK, vK) = _local(g['S1K_UV'])
        out['S1-K'] = dict(geom=locK, origin=(uK, vK), engrave=[], texts=[])
    return out


SPARE_PARTS = ('S1-H', 'S1-P')    # 外包兩邊都 <10 mm 的極小零件：每套多切一整份備品（數量＝每套數量）

NEW_PART_INFO = {
    'S1-B': ('S1 座塊（嵌 #13R 牆槽；雕刻面朝 S1-C，和 #13R 同板）', 1),
    'S1-C': ('S1 座板（空腔側貼牆；雕刻面朝牆／S1-B，紅框是 S1-B 黏貼位置）', 1),
    'S1-H': ('S1 導流帽（三角片，疊黏在前臂頂面；不雕刻）', None),
    'S1-F': ('S1 背蓋（貼 #37 外面，2 支 M3 尼龍螺絲；雕刻面朝外）', 1),
    'S1-P': ('S1 帽通道填塊（黏在背蓋前面；雕刻面朝背蓋）', 1),
    'S1-K': ('S1 元件帶填塊（實品元件帶無零件時才用；黏在背蓋前面）', 1),
}


# ---------------------------------------------------------------------------
# build（INTERFACE）
# ---------------------------------------------------------------------------
def build(cat, module: dict | None = None, des: dict | None = None) -> dict:
    """S1 卡匣子系統：回傳 edits／new_parts／notes／warnings／renames／groups／checks／keepout。"""
    M = module_params(module)
    Dd = design_params(des)
    g = geometry(cat, M, Dd)
    D, G = g['D'], g['G']
    edits = []

    # ---- #13 → #13R（頁座標＝原 #13） ----
    U13 = _top_U('#13')
    A13, z13 = _affine('#13', ('W', 'V'), U13)
    if abs(z13) > 1e-6:
        raise RuntimeError(f'#13 上面 U{U13} 不在 z=0（z={z13}）')
    p13 = lambda q: affinity.affine_transform(q, A13)
    wt = Dd['wall_top']
    # 加高區和 3 支榫在 (W',V) 先合成一塊再轉頁座標：榫和加高區共用邊，分開轉換會有 1e-14 的縫，聯集後榫會斷開
    add13 = unary_union([g['raise_WV']] + [q for _, q in g['tabs13_WV']])
    if add13.geom_type != 'Polygon':
        raise RuntimeError('#13R 加高區與榫沒有連成一塊')
    tabs_txt = '、'.join(f"{n}（插 {'#26' if n.startswith('前') else '#37'}；W'{q.bounds[0]:g}～{q.bounds[2]:g} × "
                        f"V{q.bounds[1]:g}～{q.bounds[3]:g}）" for n, q in g['tabs13_WV'])
    edits.append(dict(op='union', part='#13', geom=p13(add13),
                      tag=f"S1 #13R 加高成 1 元滑道右牆（W'0～{G['W37']:g} × V{wt:g}～{Dd['raise_V1']:g}）＋{tabs_txt}"))
    b_ = g['wall_slot_WV'].bounds
    edits.append(dict(op='subtract', part='#13', geom=p13(g['wall_slot_WV']),
                      tag=f"S1 #13R 牆槽（開向 #37，S1-B 由背面插入；W'{b_[0]:g}～{b_[2]:g} × V{b_[1]:g}～{b_[3]:g}）"))
    if g['corner_notch_WV'] is not None:
        b_ = g['corner_notch_WV'].bounds
        edits.append(dict(op='subtract', part='#13', geom=p13(g['corner_notch_WV']),
                          tag=f"S1 #13R 角落讓位（修 #37 開口 R2 內角干涉；W'{b_[0]:g}～{b_[2]:g} × V{b_[1]:g}～{b_[3]:g}）"))
    ang13 = _angle_of(A13, 1.0, 0.0)            # 基線沿 +W'
    W_t = Dd['text13_W']
    for txt, dv, h in (('13R 右', Dd['text13_dV'][0], 4.0), ('S1 卡匣', Dd['text13_dV'][1], 3.0)):
        cx, cy = p13(Point(W_t, wt + dv)).coords[0]
        edits.append(dict(op='add_engrave_text', part='#13', tag=f'S1 #13R 雕刻「{txt}」（上面，朝空腔）',
                          **_text(txt, cx, cy, h, ang13)))

    # ---- #21：只雕「21 左」 ----
    U21 = _top_U('#21')
    A21, z21 = _affine('#21', ('W', 'V'), U21)
    if abs(z21) > 1e-6:
        raise RuntimeError(f'#21 上面 U{U21} 不在 z=0')
    cx, cy = affinity.affine_transform(Point(*Dd['text21_WV']), A21).coords[0]
    edits.append(dict(op='add_engrave_text', part='#21', tag='S1 #21 雕刻「21 左」（防裝反；上面，朝 50 元滑道）',
                      **_text('21 左', cx, cy, 4.0, _angle_of(A21, 1.0, 0.0))))

    # ---- #26：F1、F2、C 三個槽 ----
    A26, _ = _affine('#26', ('U', 'V'), -1.5)
    for k_, s in g['slots26_UV'].items():
        b_ = s.bounds
        what = f'#13R 前榫 {k_}' if k_.startswith('F') else 'S1-C 前榫'
        edits.append(dict(op='subtract', part='#26', geom=affinity.affine_transform(s, A26),
                          tag=f'S1 #26 槽 {k_}（{what}；U{b_[0]:.3f}～{b_[2]:.3f} × V{b_[1]:.2f}～{b_[3]:.2f}）'))

    # ---- #37：卡匣窗、B1 槽、2 個 M3 孔、雕刻 ----
    A37, _ = _affine('#37', ('U', 'V'), G['W37'] + T / 2)
    p37 = lambda q: affinity.affine_transform(q, A37)
    b_ = g['win37_UV'].bounds
    edits.append(dict(op='subtract', part='#37', geom=p37(g['win37_UV']),
                      tag=f'S1 #37 卡匣窗（U{b_[0]:.3f}～{b_[2]:.3f} × V{b_[1]:.1f}～{b_[3]:.1f}，{g["win37_UV"].area:.1f} mm²）'))
    for k_, s in g['slots37_UV'].items():
        b_ = s.bounds
        edits.append(dict(op='subtract', part='#37', geom=p37(s),
                          tag=f'S1 #37 槽 {k_}（#13R 後榫；U{b_[0]:.3f}～{b_[2]:.3f} × V{b_[1]:.2f}～{b_[3]:.2f}）'))
    for i, (u, v) in enumerate(g['screws_UV']):
        edits.append(dict(op='subtract', part='#37', geom=p37(g['holes37_UV'][i]),
                          tag=f"S1 #37 M3 孔 Ø{Dd['screw_hole_37']:g}（中心 U{u:.3f} V{v:.1f}；空腔側預黏螺帽）"))
    B1u1 = max(s.bounds[2] for s in g['slots37_UV'].values())
    cx, cy = p37(Point(B1u1 + Dd['text37_gap'], Dd['text37_V'])).coords[0]
    edits.append(dict(op='add_engrave_text', part='#37', tag='S1 #37 雕刻「S1 卡匣」（外面，背蓋上緣之上）',
                      **_text('S1 卡匣', cx, cy, 4.0, _angle_of(A37, 1.0, 0.0), anchor='start')))

    # ---- 新零件 ----
    NP = new_parts_geometry(g)
    new_parts = []
    for pid, d in NP.items():
        name, qty = NEW_PART_INFO[pid]
        if pid == 'S1-H':
            qty = g['cap_layers']
            name = f'S1 導流帽（三角片 ×{qty}，疊黏在前臂頂面；不雕刻）'
        npd = dict(id=pid, name=name, material='合板', qty=qty, geom=d['geom'],
                   engrave=list(d['engrave']), texts=list(d['texts']))
        if pid in SPARE_PARTS:          # 極小零件（外包兩邊都 <10 mm）：每套多切一整份備品（使用者 2026-10-08 決定 3）
            npd['spare'] = qty
        if pid == 'S1-B':
            npd['group'] = 'S1-wall'
        new_parts.append(npd)

    # ---- 檢查、警告、說明 ----
    E = _env(cat)
    checks, warns = run_checks(cat, g, E, edits, NP)
    keep = keepout(g)
    notes = _notes(g, E, keep, NP)
    return dict(edits=edits, new_parts=new_parts, notes=notes, warnings=warns,
                renames={'#13': '#13R'}, groups={'#13R': 'S1-wall'}, checks=checks, keepout=keep,
                pending=_pending(g), bom=_bom(g))


def _bom(g) -> list[dict]:
    """採購／備品清單（INTERFACE.md 的 bom；export 合併成 report.md「材料與採購」）。數量是每套。"""
    Dd = g['Dd']
    nl = g['cap_layers']
    m3 = abs(Dd['screw_hole_37'] - 3.4) < 1e-9
    out = [
        dict(cat='電子', item='槽型光耦模組（同 S5～S50 型號）', qty=1, unit='個', who='講師預組',
             note='S1 卡匣用；貼在 S1-B 上', src='s1 a-2'),
    ]
    if Dd.get('s_pcb', 0) > 0:
        out.append(dict(cat='耗材', item=f"雙面泡棉膠 {Dd['s_pcb']:g} mm 厚", qty=3, unit='cm²', who='講師預組',
                        note='模組 PCB 貼 S1-B（s_pcb 墊高，調光束 U）', src='s1 (c)'))
    if m3:
        out += [dict(cat='五金', item='M3×10 尼龍螺絲', qty=2, unit='支', who='老師現場',
                     note='卡匣背蓋鎖 #37（手擰）', src='s1 (c)、a-3'),
                dict(cat='五金', item='M3 螺帽', qty=2, unit='顆', who='講師預組',
                     note='熱熔膠預黏在 #37 空腔側兩個 Ø3.4 孔上', src='s1 a-2 第 8 步')]
    else:
        out.append(dict(cat='五金', item='M2.6 自攻螺絲', qty=2, unit='支', who='老師現場',
                        note=f"#37 孔 Ø{Dd['screw_hole_37']:g}（不黏螺帽）", src='s1 待決'))
    out += [
        dict(cat='耗材', item='瞬間膠', qty=None, unit='少量', who='講師預組',
             note=f'{nl} 片 S1-H 導流帽疊齊後黏到前臂頂面（spec R1：用瞬間膠，掉了會卡幣）', src='s1 a-2、R1'),
        dict(cat='耗材', item='S1 排線標籤（模組端）', qty=1, unit='張', who='講師預組',
             note='貼在 S1 模組排線靠模組端（寫 S1）；老師依排線標籤裝卡匣、接線不會和 S5～S50 弄混。'
                  '盒端標籤（S1→G27）另列在電子盒',
             src='使用者 2026-10-08 決定 4'),
        dict(cat='備品（不在切割檔）', item=f'S1 卡匣（S1-B、S1-C、S1-F、S1-P、S1-H×{nl}）＋模組', qty=None,
             per10='2 個（建議）', unit='個', who='講師',
             note='待決（s1 spec (i) 8）：每場幾個備品卡匣，建議 10 套配 2 個；整個卡匣目前切割檔沒有排'
                  f'（極小零件 S1-H×{nl}、S1-P×1 的備品已排進切割檔，見「備品已排進切割檔」）', src='s1 a-2、(i) 8'),
    ]
    return out


def _pending(g) -> list[str]:
    """spec 最後「仍待使用者決定」的項目（這份草稿照預設值做）；export 寫進 report.md 待決事項。"""
    M, Dd = g['M'], g['Dd']
    return [
        f"待決：S1 導流帽 S1-H 和 1.0 mm 雙面泡棉膠（照預設：做 {g['cap_layers']} 片帽，泡棉膠墊高 s_pcb={Dd['s_pcb']:g}）",
        '待決：卡匣固定方式（照預設：M3 尼龍螺絲＋講師預黏螺帽，#37／背蓋孔 Ø3.4；若改 M2.6 自攻，#37 孔改 2.2）',
        f"待決：#13R 牆頂 V30 或 V38（照預設 V{Dd['wall_top']:g}＝params.S1_WALL_TOP_V；V38 可跑，wall_top 檢查會不合格並出警告）",
        '待決：左側 #21 的 37-cutout-corners 要不要一起修（照預設：不修，#21 只加雕刻）',
        '待決：備品卡匣數（照預設：每套 1 個，不含備品；建議每 10 套另做 2 個）',
        f"待決：comp_band_free（照預設 {Dd.get('comp_band_free', False)}：背蓋切元件帶，不切 S1-K）",
        '待實量：槽型光耦模組全部尺寸、本體與排針位置、元件高、背面焊點高 back_h、擋住時輸出準位',
    ]


def keepout(g: dict) -> dict:
    """電子盒要避開的 #37 背面 S1 禁區（背蓋＋後臂＋PCB 後端＋排針＋杜邦頭＋拔插手指空間 15）。"""
    D, G = g['D'], g['G']
    sF, hdr = g['S1F_UV'], g['mod']['header']
    return dict(name='S1 禁區（#37 背面，組裝座標）',
                U=(_r(sF.bounds[0] - 0.5, 1), _r(max(sF.bounds[2], hdr[1]) + 0.5, 1)),
                V=(_r(sF.bounds[1] - 0.5, 1), _r(max(sF.bounds[3], hdr[3]) + 0.5, 1)),
                W=(_r(G['W37o'], 1), _r(max(hdr[5], D['back_arm'][1], D['pcb_w'][1]) + 15, 1)))


def _notes(g, E, keep, NP=None) -> list[str]:
    D, M, Dd = g['D'], g['M'], g['Dd']
    nl = g['cap_layers']
    return [
        'S1 卡匣（方案 A）：#13 換成 #13R（加高成 1 元滑道右牆、開牆槽），卡匣從 #37 背面插入；'
        f"光束 U{D['Ub']:.3f}、V{D['Vb']:g}、W'{D['wa']:g}→{D['wb']:g}。",
        f"#13R 牆頂 V{Dd['wall_top']:g}（params.S1_WALL_TOP_V）；後榫 B1 V{g['tabs_back_eff'][0][0]:g}～{g['tabs_back_eff'][0][1]:g}。",
        '套件裡只有 #13R（雕「13R 右」、上半截高出一大塊）和 #21（雕「21 左」），沒有 #13。'
        '#13R 若誤裝到左邊，#26／#37 沒有新槽插不進去；#21 若誤裝到右邊，沒有牆槽、卡匣插不進去。',
        '講師預組（每套 1 個卡匣，建議每 10 套另做 2 個備品）：S1-B 白膠黏到 S1-C 的紅框內（後榫並排）→ '
        '後榫插進 S1-F 的槽、上膠 → S1-P 黏在 S1-F 前面（塞進背蓋缺口內角）→ '
        f'{nl} 片 S1-H 疊齊後黏到前臂頂面（4.5 直角邊齊前臂外面，坡往槽方向下降，不可伸進槽）→ '
        'S1-B 滑道側貼 1.0 mm 雙面泡棉膠、把模組由下往上套進去（PCB 上緣齊 S1-B 上緣、前緣齊 S1-B 前緣），'
        '驗位：後臂內面到背蓋前面 2.7±0.2 → #37 空腔側兩個 Ø3.4 孔預黏 M3 螺帽。',
        '老師組裝：#13R 照原 #13 位置裝（另 2 支前榫插 #26 新槽、後榫 B1 插 #37 新槽）→ 蓋 #37 → '
        'S5～S50 照 crosstrack 從前面裝（依排線標籤把模組裝到對應的站：沿滑道從轉盤那端往下游，第 1 個感測窗 S5、'
        '第 2 個 S10、最下游開底缺口 S50；見 crosstrack「老師組裝」）→ 最後從背面把卡匣（排線貼「S1」標籤）'
        '水平推進牆槽、背蓋貼平 #37，鎖 2 支 M3×10 尼龍螺絲（手擰）。',
        '沒插卡匣時不可送幣：牆槽和 #37 窗是開的，硬幣會掉進空腔或從背面掉出去。換模組：卸 2 支螺絲、卡匣往後拉出，約 1 分鐘。',
        '每套另購：1.0 mm 雙面泡棉膠約 3 cm²、M3×10 尼龍螺絲 2 支、M3 螺帽 2 顆。',
        '雕刻面：S1-B 朝 S1-C（−U）、S1-C 朝牆（+U，紅框＝S1-B 黏貼位置）、S1-F 朝外（「S1 ↑」朝上）、S1-P 朝背蓋；S1-H 不雕刻。'
        '所有雕刻（框線、字）都是紅色 0.2 mm 線；代號字 em 2.5～3、字墨離切割線 ≥1.0（使用者 2026-10-08）：'
        + '、'.join(f"{pid}「{t['text']}」em {t['size']:g}" for pid in ('S1-B', 'S1-C', 'S1-F', 'S1-P')
                   for t in ((NP or {}).get(pid, {}).get('texts') or [])[-1:]) + '。',
        f"極小零件 S1-H（{nl} 片）、S1-P 每套多切一整份備品（S1-H×{nl}、S1-P×1），排在同一份切割檔"
        '（parts.csv「備品」欄；使用者 2026-10-08 決定 3），掉進蜂巢台或弄丟時用。',
        f"電子盒 S1 禁區：U{keep['U'][0]}～{keep['U'][1]} × V{keep['V'][0]}～{keep['V'][1]} × W'{keep['W'][0]}～{keep['W'][1]}。",
        f"#37 感測器線孔（U{SENSOR_HOLE_37[0]:g}～{SENSOR_HOLE_37[1]:g} × V{SENSOR_HOLE_37[2]:g}～{SENSOR_HOLE_37[3]:g}）"
        '不和 S1 背蓋、B1 槽、M3 孔重疊（見 checks）。',
        f"模組尺寸（params.MODULE）：PCB {M['pcb_L']:g}×{M['pcb_W']:g}×{M['pcb_t']:g}、臂 {M['arm_t']:g}×{M['arm_w']:g}、"
        f"臂高 {M['arm_top']:g}、槽 {M['slot_w']:g}×{M['slot_d']:g}、光束離槽底 {M['beam_sb']:g}、背面焊點 {M['back_h']:g}（暫定，待實量）。",
    ] + ([f"背面焊點 back_h 讀 params.MODULE＝{M['back_h']:g}（s1wall_final 名目 2.0）：#37 窗焊點段與 S1-F 缺口左緣在 "
          f"U{D['U_solder'] - 0.2:.3f}（名目 106.675），其餘幾何與規格相同。"] if abs(M['back_h'] - 2.0) > 1e-9 else [])


# ---------------------------------------------------------------------------
# 檢查（移植 checks.py 能由幾何算的部分＋跨子系統＋Go/No-Go）
# ---------------------------------------------------------------------------
def apply_edits(geom, edits, part):
    """照 compose 順序（union → subtract）把本模組對 part 的形狀修改套到 geom（頁座標）。"""
    ed = [e for e in edits if e['part'] == part]
    for e in ed:
        if e['op'] == 'union':
            geom = geom.union(e['geom'])
    for e in ed:
        if e['op'] == 'subtract':
            geom = geom.difference(e['geom'])
    return geom


@functools.lru_cache(maxsize=1)
def _font():
    """字型（只讀 params.FONT_PATH 的第 0 個字型；讀不到時回 None，改用估計字寬）。"""
    try:
        from fontTools.ttLib import TTCollection, TTFont
        path = P.FONT_PATH
        f = TTCollection(path).fonts[0] if str(path).lower().endswith('.ttc') else TTFont(path)
        return f.getBestCmap(), f['hmtx'], f['head'].unitsPerEm, f.getGlyphSet()
    except Exception:
        return None


def text_width_em(text: str) -> float:
    """前進寬度（em）：anchor 'middle'／'end' 依這個寬度對齊。"""
    f = _font()
    if f is None:
        return sum(1.0 if ord(c) > 0x2000 else 0.6 for c in text)
    cmap, hmtx, upm, _ = f
    return sum(hmtx[cmap[ord(c)]][0] if ord(c) in cmap else upm for c in text) / upm


def text_box(t: dict) -> Polygon:
    """文字（基線錨點 dict）的字墨外框（textpath.ink_box：精確字墨外包，再繞錨點旋轉；頁座標或零件局部座標）。"""
    return TP.ink_box(t['text'], t['x'], t['y'], t['size'], t.get('angle', 0.0), t.get('anchor', 'start'))


def gonogo(M: dict, Dd: dict, E: dict, G: dict | None = None) -> list[tuple[str, bool, str]]:
    """spec §d-3 六條失效準則＋§d-4 Go/No-Go（依目前模組尺寸）。回傳 (名稱, 通過, 數值說明)。"""
    G = G or _geo()
    d = derived(M, Dd, G)
    zone0 = G['U7_in'] - COIN_D
    o0 = E['OPEN1'][0]
    b1_end = max(b for _, b in Dd['tabs_back'])
    bm = d['Ub'] - zone0 - M['aperture'] / 2
    return [
        ('光束餘量 ≥1.0（扣光窗半寬）', bm >= 1.0, f'{bm:.2f}'),
        (f"前臂／帽前面離 S5 掃掠 ≥1.0（W'≥{S5_W_MAX + 1:g}）", d['front_arm'][0] >= S5_W_MAX + 1.0, f"W'{d['front_arm'][0]:.2f}"),
        (f'#37 窗下料條 ≥3.0（PCB 下緣＋{Dd["c_pcb"]:g} ≤ V{V37_BOTTOM - 3:g}）',
         d['pcb_v'][1] + Dd['c_pcb'] <= V37_BOTTOM - 3.0, f"PCB 下緣 V{d['pcb_v'][1]:.2f}"),
        ('背蓋上緣不壓 B1 榫尾', d['pcb_v'][0] - 7.0 >= b1_end + Dd['c_tab'] + 1.0,
         f"背蓋上緣 V{d['pcb_v'][0] - 7.0:.2f}，B1 榫尾 V{b1_end + Dd['c_tab']:.2f}"),
        ('臂尖到 #7 ≥12', G['U7_in'] - d['U_tip'] >= 12.0, f"{G['U7_in'] - d['U_tip']:.2f}"),
        (f'槽底（本體頂）在死區（U < 開口右緣 {o0:.3f}）', d['U_sb'] < o0, f"U{d['U_sb']:.3f}"),
        ('Go/No-Go：槽寬 ≥8', M['slot_w'] >= 8.0, f"{M['slot_w']:g}"),
        ('Go/No-Go：光耦本體靠 PCB 長邊（body_e ≤1.3）', M['body_e'] <= 1.3, f"{M['body_e']:g}"),
        ('Go/No-Go：元件高 ≤3.0（導流帽從槽底起）', M['comp_h'] <= 3.0, f"{M['comp_h']:g}"),
    ]


def run_checks(cat, g: dict, E: dict, edits: list, NP: dict):
    """回傳 (checks, warnings)。checks：dict(name, ok, value, expected, note, key)。"""
    D, M, Dd, G = g['D'], g['M'], g['Dd'], g['G']
    U_out, U_in, U7, W37, W37o = G['U_out'], G['U_in'], G['U7_in'], G['W37'], G['W37o']
    o0, o1 = E['OPEN1']
    C = []
    warns = []

    def chk(key, name, value, expected, ok, note=''):
        if isinstance(value, (np.floating, float)):
            value = round(float(value), 3)
        C.append(dict(key=key, name=name, ok=bool(ok), value=value, expected=expected, note=note))

    # ===== 1. 光束 =====
    zone = (U7 - COIN_D, U_in + COIN_D)
    mb = D['Ub'] - zone[0]
    chk('beam_margin', f'光束 U 離保證覆蓋區左界 U{zone[0]:.3f}（扣光窗半寬）', mb - M['aperture'] / 2, '≥1.0',
        mb - M['aperture'] / 2 >= 1.0, f"光束 U{D['Ub']:.3f}，未扣光窗 +{mb:.2f}")
    Uw = COIN_D * math.sqrt(1 - math.sin(E['ANG']) ** 2)
    chk('beam_margin_roll', f'硬幣繞軌道方向任意翻轉時（U 寬 ≥{Uw:.2f}）光束重疊', D['Ub'] - (U7 - Uw), '>0',
        D['Ub'] - (U7 - Uw) > 0)
    chk('beam_V', "後臂內面在 #37 內面之後", D['wb'] - W37, '≥0', D['wb'] >= W37,
        f"光束 V{D['Vb']:g}，W'{D['wa']:g}→{D['wb']:g}")

    # ===== 2. S5 =====
    sol = {k: g['mod'][k] for k in S1_SOLIDS}
    front_W = min([v[4] for v in sol.values()] + ([g['S1H_WV'].bounds[0]] if g['cap_layers'] else []))
    chk('s5_gap', "S1 最前實體 W' 到 S5 最終位置＋安裝掃掠（W'≤10.0，翼 up/down/center 同）", front_W - S5_W_MAX, '≥1.5',
        front_W - S5_W_MAX >= 1.5, 'S5 掃掠深度取自 crosstrack_final spec')

    # ===== 3. 滑道內凸出物 =====
    capU = g['cap_U']
    beyond = max(D['U_tip'], capU[1]) - o0
    vol = ((D['U_tip'] - o0) * (D['arm_v'][1] - D['arm_v'][0]) * (D['front_arm'][1] - D['front_arm'][0])
           + (capU[1] - max(capU[0], o0)) * g['S1H_WV'].area)
    chk('beyond_direct', f'越過硬幣直落線 U{o0:.3f} 的凸出（只有前臂＋導流帽）', beyond, '記錄', True, f'體積 {vol:.0f} mm³')
    chk('tip_to_7', '臂尖／帽左面到 #7', U7 - max(D['U_tip'], capU[1]), '記錄（<20 靠帽頂坡導走）', True,
        f"帽頂坡 {g['cap_slope_deg']:.1f}°")
    chk('wall_to_open', 'PCB 元件頂、本體頂都在死區（< 1 元開口右緣）', f"{D['U_comp']:.3f}／{D['U_sb']:.3f}",
        f'<{o0:.3f}', D['U_comp'] < o0 and D['U_sb'] < o0, f'牆滑道面到開口右緣 {o0 - U_in:.3f}')

    # ===== 4. 翻倒掃掠 =====
    th = _flip_first_contact(g, E)
    chk('flip_first_S1', '1 元以唇為軸往後翻 0～180°，第一次碰到 S1 的角度', '翻到 180° 都不碰' if th is None else f'{th}°',
        '>90°', th is None or th > 90)

    # ===== 5. #13R =====
    wall, o13 = g['wall13R_WV'], g['orig13_WV']
    chk('w13_single', '#13R 單一外形（W\',V）', f'{wall.geom_type}，面積 {wall.area:.1f}（原 #13 {o13.area:.1f}）', 'Polygon',
        wall.geom_type == 'Polygon')
    g13 = apply_edits(cat['#13'].geom, edits, '#13')
    chk('w13_page', '#13R 頁座標套用 edits 後：單一外形、#12 槽 3 個保留',
        f'{g13.geom_type}，孔 {len(getattr(g13, "interiors", []))} 個', 'Polygon、3 孔',
        g13.geom_type == 'Polygon' and len(g13.interiors) == len(cat['#13'].geom.interiors))
    slot = g['wall_slot_WV']
    chk('w13_strip', '牆槽前料條（連接上段與下段）', slot.bounds[0], '≥8', slot.bounds[0] >= 8,
        f'長 {slot.bounds[3] - slot.bounds[1]:.2f}')
    upper = wall.intersection(box(-10, Dd['wall_top'] - 1, 40, slot.bounds[1]))
    chk('w13_upper', f"加高上段（V{Dd['wall_top']:g}～{slot.bounds[1]:g}）面積", upper.area, '有前、後各 1 榫', True)
    for i, (a, b) in enumerate(Dd['tabs_front']):
        rv = float(railV(E, U_in + 0.15))
        chk(f'tabF{i + 1}_hidden', f'前榫 F{i + 1} 槽口上緣 V{a - Dd["c_tab"]:.2f} 在軌道 V{rv:.2f} 以下',
            a - Dd['c_tab'] - rv, '>0（#26 槽被 #24 擋住）', a - Dd['c_tab'] - rv > 0)
    chk('tab26_len', '前榫長 vs #26 最薄 2.7', Dd['tab_len_26'], '<2.7', Dd['tab_len_26'] < 2.7)
    O37 = E['O37']
    v_bot = []
    for U in np.linspace(U_out, U_in, 13):
        x = LineString([(U, 60), (U, 120)]).intersection(O37)
        v_bot.append(x.bounds[3] if not x.is_empty else 0)
    reg37 = box(W37, -10, W37o, max(v_bot))
    inter_orig = o13.intersection(reg37).area
    inter_new = wall.intersection(reg37).area - sum(wall.intersection(box(W37, a, W37o, b)).area
                                                    for a, b in g['tabs_back_eff'])
    chk('corner_fix', f'#13R 與 #37 板厚區（V≤{max(v_bot):.2f}）重疊（後榫除外）', max(inter_new, 0.0), '0',
        inter_new < 1e-3, f'原 #13 {inter_orig:.3f} mm²')

    # ===== 6. #26 =====
    h26, o26 = E['H26'], E['O26']
    for k, s in g['slots26_UV'].items():
        inside = o26.buffer(-2.0).contains(s)
        d_h = min(s.distance(h) for h in h26)
        d_24 = min(s.distance(h) for h in E['H24'])
        d_out = s.distance(o26.exterior)
        d_eng = min([s.distance(e) for e in E['eng26']] or [99])
        chk(f's26_{k}', f'#26 槽 {k} 離外框／既有孔／#24 孔', f'{d_out:.2f}／{d_h:.2f}／{d_24:.2f}',
            '外框 ≥2、既有孔 ≥2.5、#24 孔 >0', inside and d_h >= 2.5 and d_24 > 0, f'離 #26 雕刻 {d_eng:.2f}')
    sl = list(g['slots26_UV'].values())
    webs = min(a.distance(b) for i, a in enumerate(sl) for b in sl[i + 1:])
    chk('s26_web', '#26 新槽彼此之間的料', webs, '≥2.5', webs >= 2.5)

    # ===== 7. #37 =====
    win = g['win37_UV']
    chk('w37_inside', '#37 窗在 #37 內（不切斷外框）', f'{win.area:.1f} mm²', '窗 ⊂ #37', O37.buffer(-1e-6).contains(win))
    strip = win.distance(O37.exterior)
    chk('w37_strip', '窗到 #37 外框最小料（下方開口 R2 圓角處）', strip, '≥3.0', strip >= 3.0)
    d_oth = min(win.distance(h) for h in E['H37'])
    chk('w37_holes', '窗到 #37 既有孔', d_oth, '≥3', d_oth >= 3)
    for k, s in g['slots37_UV'].items():
        dw, do = s.distance(win), s.distance(O37.exterior)
        chk(f's37_{k}', f'#37 後榫槽 {k} 離窗／外框', f'{dw:.2f}／{do:.2f}', '≥3', dw >= 3 and do >= 3)
    for i, h in enumerate(g['holes37_UV']):
        dw = h.distance(win)
        chk(f'h37_{i}', f'#37 螺絲孔 {i + 1}（U{h.centroid.x:.3f} V{h.centroid.y:.1f}）離窗', dw, '≥2.5', dw >= 2.5,
            f'離外框 {h.distance(O37.exterior):.2f}')
    fill = unary_union([box(D['U_pcb_back'], D['pcb_v'][0], D['U_pcb'], D['pcb_v'][1]),
                        box(D['U_pcb'], D['arm_v'][0], D['U_tip'], D['arm_v'][1]),
                        g['S1P_UV'] if g['S1P_UV'] is not None else Polygon()])
    gap = win.intersection(box(U_in, 0, 200, 200)).difference(fill)
    band = gap.intersection(box(D['U_pcb'], 0, D['U_comp'] + Dd['c_opt'], 200))
    chk('w37_gap', '卡匣插好後窗在滑道側剩的縫', f'{gap.area:.1f} mm²', '帽通道由 S1-P 填住', (not Dd['cap']) or g['S1P_UV'] is not None,
        f'其中元件帶通道 {band.area:.1f} mm²（在死區）')

    # ===== 8. 卡匣零件 =====
    sB, sC, sF = g['S1B_WV'], g['S1C_WV'], g['S1F_UV']
    mwB = 99.0
    for t in np.arange(0.5, 5.0, 0.05):
        e_ = sB.buffer(-t / 2)
        if e_.is_empty or e_.geom_type == 'MultiPolygon' or len(list(e_.interiors)) < len(list(sB.interiors)):
            mwB = t
            break
    chk('S1B', 'S1-B 座塊：單一外形、最細料', round(mwB, 2), '1 塊、≥2', sB.geom_type == 'Polygon' and mwB >= 1.95,
        f'{sB.bounds[2] - sB.bounds[0]:.2f}×{sB.bounds[3] - sB.bounds[1]:.2f}')
    inslot = slot.buffer(1e-6).contains(sB.intersection(box(-10, 0, W37, 200)))
    chk('S1B_inslot', 'S1-B 本體落在牆槽內', inslot, 'True', inslot)
    up_, dn_ = slot.bounds[1] - g['S1C_v'][0], g['S1C_v'][1] - slot.bounds[3]
    chk('S1C', 'S1-C 比牆槽上／下多（壓在牆空腔側）', f'{up_:.2f}／{dn_:.2f}', '都 ≥1.5', up_ >= 1.5 and dn_ >= 1.5)
    minw = 99.0
    for t in np.arange(0.5, 5.0, 0.05):
        e_ = sF.buffer(-t / 2)
        if e_.is_empty or e_.geom_type == 'MultiPolygon':
            minw = t
            break
    chk('S1F', 'S1-F 背蓋：單一外形、最細料', round(minw, 2), '1 塊、≥3', sF.geom_type == 'Polygon' and minw >= 3.0,
        f'{sF.bounds[2] - sF.bounds[0]:.2f}×{sF.bounds[3] - sF.bounds[1]:.2f}')
    tops = []
    for W in (W37o, W37o + 1.5, W37o + 3.0):
        x = LineString([(W, 0), (W, 200)]).intersection(o13)
        if not x.is_empty:
            tops.append(x.bounds[1])
    gap13 = min(tops) - Dd['cover_v1']
    chk('cover_13', f"背蓋下緣 V{Dd['cover_v1']:g} 到 #13R 在 #37 後方的櫃頂邊", gap13, '≥1.0', gap13 >= 1.0)
    b1_end = max(b for _, b in g['tabs_back_eff'])
    cb = sF.bounds[1] - (b1_end + Dd['c_tab'])
    chk('cover_B1', '背蓋上緣到 B1 榫尾（榫可能凸出 #37 外面 0～0.3）', cb, '≥1.0', cb >= 1.0)
    nl = g['cap_layers']
    if nl:
        chk('S1H', f'S1-H 導流帽片數 {nl}（疊 U{capU[0]:.3f}～{capU[1]:.3f}）vs 槽深 {M["slot_d"]:g}', nl, '≈ 槽深/3',
            abs(nl * T - M['slot_d']) <= 1.5, f'每片 {g["S1H_WV"].area:.1f} mm²，頂坡 {g["cap_slope_deg"]:.1f}°')
    P_ = g['S1P_UV']
    if P_ is not None:
        a_, b_ = D['arm_v'][0] - P_.bounds[3], P_.bounds[0] - D['U_comp']
        chk('S1P', 'S1-P 下緣到後臂頂／左緣到元件頂', f'{a_:.2f}／{b_:.2f}', '都 ≥0.3', a_ >= 0.3 and b_ >= 0.3)

    # ===== 9. 出口平面、#12、馬達盒、空腔、排線、電子盒 =====
    low = max(v[3] for v in sol.values() if v[4] < W37)
    lowW = [v for v in sol.values() if v[3] == low][0]
    ex = float(exitV(min(W37, lowW[5])))
    chk('exit', '模組在滑道內最低點到出口平面', ex - low, '≥2', ex - low >= 2, f'PCB 下緣 V{low:.2f}，出口平面 V{ex:.2f}')
    fp12 = F.frame('#12').footprint(('W', 'V'), geom=cat['#12'].geom)
    pw, pv, hdr = D['pcb_w'], D['pcb_v'], g['mod']['header']
    rear = box(pw[0], pv[0], pw[1], pv[1])
    hdr_WV = box(hdr[4], hdr[2], hdr[5], hdr[3])
    cov_WV = box(W37o, sF.bounds[1], W37o + T, sF.bounds[3])
    d12 = (rear.distance(fp12), hdr_WV.distance(fp12), cov_WV.distance(fp12))
    chk('to12', '#12（櫃後板）到 PCB 後端／排針／背蓋', '／'.join(f'{v:.2f}' for v in d12), '≥1.5', min(d12) >= 1.5)
    hole_u = g['screws_UV'][0][0] - Dd['screw_hole_37'] / 2
    chk('motor', f'TT 馬達盒右壁 U{MOTOR_U} 到 S1-C／螺絲孔', f'{U_out - T - MOTOR_U:.2f}／{hole_u - MOTOR_U:.2f}', '≥10',
        U_out - T - MOTOR_U >= 10)
    chk('cavity', '右側空腔剩餘寬（馬達盒～S1-C）', U_out - T - MOTOR_U, '≥25（S5～S50 排線經空腔）', U_out - T - MOTOR_U >= 25)
    s1c_UV = box(U_out - T, g['S1C_v'][0], U_out, g['S1C_v'][1])
    dc = box(*CABLE_HOLE[0:1], *CABLE_HOLE[2:3], *CABLE_HOLE[1:2], *CABLE_HOLE[3:4]).distance(s1c_UV)
    chk('cable', 'crosstrack 右下排線孔到 S1-C', dc, '>0', dc > 0)
    chk('front', 'S1 最前點（前榫尖，在 #26 板內）', -Dd['tab_len_26'], "W'>-3", -Dd['tab_len_26'] > -3)
    keep = keepout(g)
    chk('ebox', '#37 背面 S1 禁區右界（電子盒在 U≥134）', keep['U'][1], '≤133.5', keep['U'][1] <= 133.5,
        f"U{keep['U']}×V{keep['V']}×W'{keep['W']}")
    sh = _rect(*SENSOR_HOLE_37)
    d_cov = sh.distance(g['S1F_rect'])
    d_b1 = min(sh.distance(s) for s in g['slots37_UV'].values())
    d_m3 = min(sh.distance(h) for h in g['holes37_UV'])
    d_win = sh.distance(win)
    chk('sensor_hole_37', '#37 感測器線孔（ebox，U88～100×V40～46）到 S1 背蓋／B1 槽／M3 孔／卡匣窗',
        f'{d_cov:.2f}／{d_b1:.2f}／{d_m3:.2f}／{d_win:.2f}', '背蓋 ≥1（不擋線）、孔與孔 ≥2.5',
        d_cov >= 1.0 and min(d_b1, d_m3, d_win) >= 2.5)
    chk('wall_top', f"加高牆頂 V（1 元開口右端頂緣 V{E['OPEN_TOP_V']:.1f}）", Dd['wall_top'],
        f"≤{E['OPEN_TOP_V'] + 0.1:.1f}", Dd['wall_top'] <= E['OPEN_TOP_V'] + 0.1,
        '' if Dd['wall_top'] <= E['OPEN_TOP_V'] + 0.1 else '牆頂低於開口頂緣：省板材，但反彈防護略少（spec §i-5 待決）')
    if Dd['wall_top'] > E['OPEN_TOP_V'] + 0.1:
        warns.append(f"S1：#13R 牆頂 V{Dd['wall_top']:g} 低於 1 元開口右端頂緣 V{E['OPEN_TOP_V']:.1f}，反彈防護比 V30 少。")

    # ===== 10. 板材 =====
    add = {'#13R 增加': wall.area - o13.area, 'S1-B': sB.area, 'S1-C': sC.area, 'S1-F': sF.area,
           f'S1-H ×{nl}': nl * g['S1H_WV'].area, 'S1-P': P_.area if P_ is not None else 0.0}
    tot = sum(add.values())
    chk('material', '每套新增合板淨面積', round(tot, 0), '<5% 張', tot / SHEET_AREA < 0.05,
        '、'.join(f'{k} {v:.0f}' for k, v in add.items()) + f'（{tot / SHEET_AREA * 100:.1f}% 張）')

    # ===== 11. 雕刻文字落在實料內 =====
    _text_checks(cat, g, E, edits, NP, chk)

    # ===== 12. Go/No-Go =====
    for c in C:
        if not c['ok'] and c['key'] != 'wall_top':
            warns.append(f"S1 檢查不合格：{c['name']}（{c['value']}，要求 {c['expected']}）。")
    for i, (name, ok, val) in enumerate(gonogo(M, Dd, E, G)):
        chk(f'gonogo_{i}', name, val, '成立', ok)
        if not ok:
            warns.append(f'S1 Go/No-Go 不成立：{name}（目前 {val}）；見 spec §d-3／§d-4。')
    return C, warns


def _text_checks(cat, g, E, edits, NP, chk):
    """雕刻文字墨色外框離切割線 ≥ TEXT_CLEAR（1.0）、離黏貼框 ≥ ENGRAVE_GAP（0.4）、不壓其他子系統已知的孔。"""
    pages = {pid: apply_edits(cat[pid].geom, edits, pid) for pid in ('#13', '#21', '#37')}
    A37, _ = _affine('#37', ('U', 'V'), g['G']['W37'] + T / 2)
    sensor_pg = affinity.affine_transform(_rect(*SENSOR_HOLE_37), A37)
    for e in edits:
        if e['op'] != 'add_engrave_text':
            continue
        r = text_box(e)
        gp = pages[e['part']]
        d_edge = gp.boundary.distance(r) if gp.contains(r) else -1.0   # boundary 含孔
        extra = ''
        ok = d_edge >= TP.TEXT_CLEAR - 1e-6
        if e['part'] == '#37':
            ds = sensor_pg.distance(r)
            extra = f'；離感測器線孔 {ds:.2f}'
            ok = ok and ds >= TP.TEXT_CLEAR - 1e-6
        chk(f'text_{e["part"]}_{e["text"]}', f'{e["part"]} 雕刻「{e["text"]}」離切割線', round(d_edge, 3),
            f'≥{TP.TEXT_CLEAR:g}', ok, f'em {e["size"]:g}、字寬 {text_width_em(e["text"]) * e["size"]:.1f} mm' + extra)
    for pid, d in NP.items():
        for t in d['texts']:
            r = text_box(t)
            gp = d['geom']
            dd = gp.boundary.distance(r) if gp.contains(r) else -1.0
            note = f'em {t["size"]:g}、字寬 {text_width_em(t["text"]) * t["size"]:.1f} mm'
            ok = dd >= TP.TEXT_CLEAR - 1e-6
            others = [text_box(t2) for t2 in d['texts'] if t2 is not t]
            if others:
                dt = min(o.distance(r) for o in others)
                note += f'；離別的字 {dt:.2f}'
                ok = ok and dt >= TP.ENGRAVE_GAP - 1e-6
            if pid == 'S1-C':
                df = d['engrave_geom'].distance(r)
                note += f'；離 S1-B 黏貼框 {df:.2f}'
                ok = ok and df >= TP.ENGRAVE_GAP - 1e-6
            chk(f'text_{pid}_{t["text"]}', f'{pid} 雕刻「{t["text"]}」離切割線', round(dd, 3), f'≥{TP.TEXT_CLEAR:g}', ok, note)
        if pid in ('S1-B', 'S1-C', 'S1-F', 'S1-P'):
            chk(f'text_{pid}_code', f'{pid} 有雕代號', [t['text'] for t in d['texts']], '有', bool(d['texts']),
                '代號字 em 2.5～3；放不下完整代號時只刻單字母')


def _flip_first_contact(g, E):
    """1 元以 #26 開口唇為軸往後翻 0～180°，第一次碰到 S1 模組實體或導流帽的角度（None＝不碰）。"""
    D = g['D']
    ang = E['ANG']
    tdir = np.array([math.cos(ang), math.sin(ang), 0.0])
    up = np.array([math.sin(ang), -math.cos(ang), 0.0])
    lipV = lambda U: E['LIP_V0'] + E['RAIL_M'] * (U - 114.5)
    rs, ph = np.linspace(0, 10, 11), np.linspace(0, 2 * np.pi, 73)
    RR, PH = np.meshgrid(rs, ph)
    sol = [g['mod'][k] for k in S1_SOLIDS]
    tri = g['S1H_WV']
    capU = g['cap_U']
    oc = (E['OPEN1'][0] + E['OPEN1'][1]) / 2
    first = []
    for Uc in (oc - 0.25, oc, oc + 0.25):
        P0 = np.array([Uc, lipV(Uc), -3.0])
        for th in range(0, 181):
            t = math.radians(th)
            e_up = up * math.cos(t) + np.array([0, 0, 1.0]) * math.sin(t)
            c = P0 + e_up * (COIN_D / 2 - 1.32)
            pts = (c[None, None, :] + RR[..., None] * (np.cos(PH)[..., None] * tdir + np.sin(PH)[..., None] * e_up)).reshape(-1, 3)
            U, V, W = pts[:, 0], pts[:, 1], pts[:, 2]
            hit = any(np.any((U > a) & (U < b) & (V > c_) & (V < d) & (W > e) & (W < f)) for a, b, c_, d, e, f in sol)
            if not hit:
                m = (U > capU[0]) & (U < capU[1])
                hit = bool(m.any() and shapely.contains_xy(tri, W[m], V[m]).any())
            if hit:
                first.append(th)
                break
    return min(first) if first else None


# ---------------------------------------------------------------------------
# 自我測試：與 geometry_s1_final.json 比對、牆頂 V38
# ---------------------------------------------------------------------------
def ref_module() -> dict:
    """s1wall_final 名目模組尺寸（geometry_s1_final.json 的 params.MOD）和 module_params() 不同的鍵 → 覆寫用 dict。

    使用者 2026-10-08 把 params.MODULE back_h 定為 2.0（＝S1 規格名目），所以目前是空 dict：
    params 實值就是規格名目，自我測試直接用 params 比對 json。實量後改了 params，這裡會列出不同的鍵，
    名目比對改用規格值覆寫，params 實值另外比（第 2 節）。"""
    mod = json.loads(REF_JSON.read_text(encoding='utf-8'))['params']['MOD']
    cur = module_params()
    return {k: v for k, v in mod.items() if k in cur and cur[k] != v}


def _hd(a, b) -> float:
    """兩個多邊形（或線）邊界的雙向最大距離（Hausdorff，密化取樣）。"""
    ba = a.boundary if hasattr(a, 'exterior') or isinstance(a, MultiPolygon) else a
    bb = b.boundary if hasattr(b, 'exterior') or isinstance(b, MultiPolygon) else b
    return float(shapely.hausdorff_distance(ba, bb, densify=0.02))


def _poly_json(c):
    if isinstance(c, dict):
        return Polygon(c['exterior'], c.get('holes', []))
    return Polygon(c)


def selftest(cat=None, verbose=True) -> dict:
    """名目參數下所有多邊形與 geometry_s1_final.json 比對（≤0.01 mm），並跑 params 實值與牆頂 V38。"""
    from .catalog import load_catalog
    cat = cat or load_catalog()
    ref = json.loads(REF_JSON.read_text(encoding='utf-8'))
    lines = []
    log = lambda s: (lines.append(s), print(s) if verbose else None)
    rows = []

    def cmp(name, a, b, tol=0.01):
        d = _hd(a, b)
        rows.append((name, d))
        log(f"  {'OK' if d <= tol else '!!'} {name}: {d:.4f}")
        return d

    ref_mod = ref_module()
    res = build(cat, module=ref_mod or None)
    g = geometry(cat, module_params(ref_mod), design_params())
    E = _env(cat)
    log('== 1. 名目參數（s1wall_final MOD/DES）vs geometry_s1_final.json ==')
    log('  params.MODULE 和 s1wall_final MOD ' + ('完全相同（back_h＝2.0，使用者 2026-10-08 決定），直接用 params 比對'
                                                  if not ref_mod else
                                                  '不同：' + '、'.join(f'{k}＝{module_params()[k]}（規格 {v}）' for k, v in ref_mod.items())
                                                  + '；本節用規格值覆寫'))
    # 推導量
    dmax = 0.0
    for k, v in ref['derived'].items():
        mine = g['D'][k]
        a = np.atleast_1d(np.asarray(mine, float))
        b = np.atleast_1d(np.asarray(v, float))
        dmax = max(dmax, float(np.max(np.abs(a - b))))
    log(f"  {'OK' if dmax <= 1e-9 else '!!'} 推導量 {len(ref['derived'])} 項最大差 {dmax:.2e}")
    rows.append(('推導量', dmax))
    dm = max(abs(a - b) for k in ref['module_boxes_UVW'] for a, b in zip(g['mod'][k], ref['module_boxes_UVW'][k]))
    log(f"  {'OK' if dm <= 0.001 else '!!'} 模組盒 7 個最大差 {dm:.4f}")
    rows.append(('模組盒', dm))
    # #13R
    org = np.array(cat['#13'].bbox[:2])
    tr = lambda q: affinity.translate(q, -org[0], -org[1])
    g13 = apply_edits(cat['#13'].geom, res['edits'], '#13')
    cmp('#13R 外形（原 #13 局部，含 3 個 #12 槽）', tr(g13), _poly_json(ref['#13R']['outline_local13']), tol=0.011)
    log(f"     （json 外形是 simplify(0.01)＋取 3 位小數，容許 0.011）；面積 {g13.area:.1f} vs json {ref['#13R']['area']['new']}")
    ops = {e['tag']: e['geom'] for e in res['edits'] if e['part'] == '#13' and 'geom' in e}
    tag_of = lambda key: [t for t in ops if key in t][0]
    ol = ref['#13R']['ops_local13']
    # json 各塊取 3 位小數，共用邊對不齊：先各脹 0.001 再縮回，把 0.001 以下的縫合起來
    ref_add = unary_union([Polygon(q).buffer(1e-3, join_style='mitre') for q in
                           [ol['raise_rect']] + ol['tabs_front'] + ol['tabs_back']]).buffer(-1e-3, join_style='mitre')
    cmp('#13R 加高區＋F1＋F2＋B1（聯集）', tr(ops[tag_of('加高')]), ref_add)
    A13, _ = _affine('#13', ('W', 'V'), _top_U('#13'))
    for name, q in g['tabs13_WV']:
        key = {'前榫 F1': ol['tabs_front'][0], '前榫 F2': ol['tabs_front'][1], '後榫 B1': ol['tabs_back'][0]}[name]
        cmp(f'#13R {name}', tr(affinity.affine_transform(q, A13)), Polygon(key))
    cmp('#13R 牆槽', tr(ops[tag_of('牆槽')]), Polygon(ol['wall_slot']))
    cmp('#13R 角落讓位', tr(ops[tag_of('角落讓位')]), Polygon(ol['corner_notch']))
    # #26
    for k, v in ref['#26']['slots'].items():
        e = [x for x in res['edits'] if x['part'] == '#26' and f'槽 {k}（' in x['tag']][0]
        cmp(f'#26 槽 {k}（頁座標）', e['geom'], Polygon(v['page']))
    # #37
    e37 = {x['tag']: x for x in res['edits'] if x['part'] == '#37' and 'geom' in x}
    win = [x for t, x in e37.items() if '卡匣窗' in t][0]['geom']
    cmp('#37 卡匣窗（頁座標）', win, Polygon(ref['#37']['window']['page']))
    o37 = np.array(cat['#37'].bbox[:2])
    cmp('#37 卡匣窗（局部）', affinity.translate(win, -o37[0], -o37[1]), Polygon(ref['#37']['window']['local']))
    b1 = [x for t, x in e37.items() if '槽 B1' in t][0]['geom']
    cmp('#37 槽 B1（頁座標）', b1, Polygon(ref['#37']['slots']['B1']['page']))
    holes = [x['geom'] for t, x in e37.items() if 'M3 孔' in t]
    for i, h in enumerate(ref['#37']['holes']):
        c = holes[i].centroid
        d = math.hypot(c.x - h['center_page'][0], c.y - h['center_page'][1])
        rows.append((f'#37 M3 孔 {i + 1} 中心', d))
        log(f"  {'OK' if d <= 0.01 else '!!'} #37 M3 孔 {i + 1} 中心（頁座標）: {d:.4f}；直徑 {2 * math.sqrt(holes[i].area / math.pi):.3f}")
    # 新零件
    NP = {p['id']: p for p in res['new_parts']}
    for pid in ('S1-B', 'S1-C', 'S1-H', 'S1-F', 'S1-P'):
        cmp(f'{pid} 外形（局部）', NP[pid]['geom'], _poly_json(ref['new_parts'][pid]['local']))
    jf = Polygon(ref['new_parts']['S1-C']['engrave_outline_S1B'])
    NPg = new_parts_geometry(g)
    cmp('S1-C 黏貼框（完整框）', NPg['S1-C']['frame_full'], jf)
    eng = NPg['S1-C']['engrave_geom']
    d_in = float(shapely.hausdorff_distance(eng, jf.exterior.intersection(eng.buffer(1e-3)), densify=0.02))
    rest = jf.exterior.difference(eng.buffer(1e-3))
    on_cut = NP['S1-C']['geom'].exterior.buffer(1e-3).contains(rest)
    log(f"  {'OK' if d_in <= 0.01 and on_cut else '!!'} S1-C 實際雕的框＝完整框扣掉和外框重合的段（差 {d_in:.4f}；扣掉的段都在切割線上：{on_cut}）")
    rows.append(('S1-C 黏貼框（雕刻段）', d_in))
    log(f"  S1-H 片數 {NP['S1-H']['qty']}（json {ref['new_parts']['S1-H']['qty']}）")
    # 文字中心
    log('  -- 雕刻文字中心（規格 vs 本模組；* 是刻意調整，見 deviations）--')
    T13 = [x for x in res['edits'] if x['op'] == 'add_engrave_text']
    for x in T13:
        cxy = np.array(_center_of(x))
        if x['part'] == '#13':
            j = [e for e in ref['#13R']['engrave'] if e['text'] == x['text']][0]
            d = float(np.hypot(*(cxy - org - j['at_local13'])))
            log(f"  {'OK' if d <= 0.01 else '!!'} #13R「{x['text']}」中心差 {d:.4f}，角度 {x['angle']:.2f}°")
            rows.append((f"#13R 文字「{x['text']}」", d))
        elif x['part'] == '#21':
            j = ref['#21']['engrave'][0]
            o21 = np.array(cat['#21'].bbox[:2])
            d = float(np.hypot(*(cxy - o21 - j['at_local21'])))
            log(f"  {'OK' if d <= 0.01 else '!!'} #21「{x['text']}」中心差 {d:.4f}，角度 {x['angle']:.2f}°")
            rows.append(('#21 文字', d))
        elif x['part'] == '#37':
            j = ref['#37']['engrave'][0]
            w = text_width_em(x['text']) * x['size']
            Uc = F.frame('#37').to_asm(*cxy, 0.0)[0] + w / 2
            log(f"  *  #37「{x['text']}」起點在 B1 槽右緣＋2；中心約 U{Uc:.2f}（規格 U{j['at_UV'][0]}），V 差 "
                f"{abs(F.frame('#37').to_asm(*cxy, 0.0)[1] - j['at_UV'][1]):.4f}")
    for pid, key in (('S1-C', 'engrave_text'), ('S1-F', 'engrave_text')):
        j = ref['new_parts'][pid][key]
        t = NP[pid]['texts'][0]
        cx, cy = _center_of(t)
        log(f"  *  {pid}「{t['text']}」中心 ({cx:.3f}, {cy:.3f})（規格 {tuple(j['at_local'])}，字高 {t['size']}／{j['h']}）")
    # 文字方向（不鏡像、字的上方＝−V）
    for x in T13:
        a = math.radians(x['angle'])
        fr = F.frame(x['part'])
        p0 = np.array([x['x'], x['y']])
        upv = fr.to_asm(*(p0 + [math.sin(a), -math.cos(a)]), 0.0) - fr.to_asm(*p0, 0.0)
        base = fr.to_asm(*(p0 + [math.cos(a), math.sin(a)]), 0.0) - fr.to_asm(*p0, 0.0)
        n = fr.top_face_normal()
        mirror = float(np.dot(np.cross(base, upv), n))   # (U,V,W') 左手系：不鏡像時 < 0
        log(f"  {'OK' if upv[1] < -0.99 and mirror < 0 else '!!'} {x['part']}「{x['text']}」字的上方 (U,V,W')="
            f"{np.round(upv, 3).tolist()}、基線 {np.round(base, 3).tolist()}、朝外法線 {np.round(n, 3).tolist()}")
    worst = max(d for _, d in rows)
    log(f'  名目比對最大差 {worst:.4f} mm（{len(rows)} 項）')
    ck_nom = res['checks']
    bad = [c for c in ck_nom if not c['ok']]
    log(f"  名目檢查 {len(ck_nom) - len(bad)}/{len(ck_nom)} OK" + (f"；不合格：{[c['key'] for c in bad]}" if bad else ''))
    _cmp_checks(ck_nom, log)

    log('\n== 2. params.py 實值與名目的差異（MODULE back_h=%s）==' % P.MODULE['back_h'])
    res2 = build(cat)
    diffs = []
    for e1, e2 in zip(res['edits'], res2['edits']):
        if 'geom' in e1:
            d = _hd(e1['geom'], e2['geom'])
            if d > 1e-6:
                diffs.append((e1['tag'], d))
    for p1, p2 in zip(res['new_parts'], res2['new_parts']):
        d = _hd(p1['geom'], p2['geom'])
        if d > 1e-6:
            diffs.append((p1['id'], d))
    for t, d in diffs:
        log(f'  差 {d:.3f}：{t}')
    if not diffs:
        log('  沒有差異')
    bad2 = [c for c in res2['checks'] if not c['ok']]
    log(f"  檢查 {len(res2['checks']) - len(bad2)}/{len(res2['checks'])} OK" + (f"；不合格：{[c['key'] for c in bad2]}" if bad2 else ''))

    log('\n== 3. 牆頂 V38（params.S1_WALL_TOP_V=38） ==')
    old = P.S1_WALL_TOP_V
    try:
        P.S1_WALL_TOP_V = 38.0
        res3 = build(cat)
    finally:
        P.S1_WALL_TOP_V = old
    g13b = apply_edits(cat['#13'].geom, res3['edits'], '#13')
    log(f'  #13R：{g13b.geom_type}，孔 {len(g13b.interiors)}，面積 {g13b.area:.1f}（V30：{g13.area:.1f}，少 {g13.area - g13b.area:.1f} mm²）')
    fr13 = F.frame('#13')
    for e in res3['edits']:
        if e['part'] in ('#13', '#37') and ('榫 B1' in e['tag'] or '槽 B1' in e['tag']):
            log(f"  {e['tag']}")
        if e['part'] == '#13' and e['op'] == 'add_engrave_text':
            a = fr13.to_asm(*_center_of(e), 0.0)
            log(f"  #13R 雕刻「{e['text']}」中心 W'{a[2]:.2f} V{a[1]:.2f}")
    bad3 = [c for c in res3['checks'] if not c['ok']]
    log(f"  檢查 {len(res3['checks']) - len(bad3)}/{len(res3['checks'])} OK" + (f"；不合格：{[(c['key'], c['value']) for c in bad3]}" if bad3 else ''))
    for w in res3['warnings']:
        log(f'  警告：{w}')
    return dict(worst=worst, rows=rows, nominal_bad=[c['key'] for c in bad], params_diffs=diffs,
                params_bad=[c['key'] for c in bad2], v38_bad=[c['key'] for c in bad3], lines=lines,
                v38_single=g13b.geom_type == 'Polygon', ref_module=ref_mod)


def _cmp_checks(ck, log):
    """與 s1wall_final/checks.json 的數字對照（同名項目）。"""
    p = REF_DIR / 'checks.json'
    if not p.exists():
        return
    ref = json.loads(p.read_text(encoding='utf-8'))
    for c in ck:
        r = ref.get(c['key'])
        if not isinstance(r, dict) or 'value' not in r:
            continue
        mine = [float(x) for x in re.findall(r'-?\d+\.?\d*', str(c['value']))]
        theirs = [float(x) for x in re.findall(r'-?\d+\.?\d*', str(r['value']))]
        if mine and any(abs(mine[0] - t) <= 0.011 for t in theirs):
            continue
        log(f"     對照 {c['key']}：本模組 {c['value']}｜checks.json {str(r['value'])[:80]}")


# ---------------------------------------------------------------------------
def summary(res: dict) -> str:
    L = ['S1 卡匣（方案 A）build() 摘要']
    L.append(f"renames {res['renames']}；groups {res['groups']}")
    by = {}
    for e in res['edits']:
        by.setdefault(e['part'], []).append(e)
    for pid, es in by.items():
        L.append(f'{pid}：{len(es)} 項修改')
        for e in es:
            L.append(f"  - {e['op']}：{e['tag']}")
    L.append('新零件：')
    for p in res['new_parts']:
        b = p['geom'].bounds
        L.append(f"  - {p['id']} ×{p['qty']} {b[2] - b[0]:.1f}×{b[3] - b[1]:.1f} mm，{p['geom'].area:.1f} mm²"
                 f"{'，group ' + p['group'] if p.get('group') else ''}：{p['name']}")
    k = res['keepout']
    L.append(f"電子盒 S1 禁區：U{k['U']} V{k['V']} W'{k['W']}")
    bad = [c for c in res['checks'] if not c['ok']]
    L.append(f"檢查 {len(res['checks']) - len(bad)}/{len(res['checks'])} OK")
    for c in res['checks']:
        L.append(f"  [{'OK' if c['ok'] else 'NG'}] {c['name']}：{c['value']}（要求 {c['expected']}）"
                 + (f"｜{c['note']}" if c['note'] else ''))
    for w in res['warnings']:
        L.append(f'警告：{w}')
    return '\n'.join(L)


if __name__ == '__main__':
    from .catalog import load_catalog
    _cat = load_catalog()
    if '--selftest' in sys.argv:
        r = selftest(_cat)
        ok = r['worst'] <= 0.011 and not r['nominal_bad'] and r['v38_single'] and not r['params_bad']
        print(f"\n自我測試：{'通過' if ok else '未通過'}（名目最大差 {r['worst']:.4f} mm；params 實值"
              + ('＝規格名目' if not r['ref_module'] else f"和名目差 {len(r['params_diffs'])} 項")
              + f"、檢查{'全過' if not r['params_bad'] else '有不合格：' + str(r['params_bad'])}）")
        sys.exit(0 if ok else 1)
    else:
        print(summary(build(_cat)))

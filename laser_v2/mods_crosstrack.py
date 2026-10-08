"""S5／S10／S50「滑升式感測座」（crosstrack）：v2 對原始零件的修改與新增零件。

規格與來源
----------
* 權威規格：laser_v2/design/crosstrack_final/spec.md（§1 座標、§2 參數、(b) 原始零件修改
  b-0～b-7、(c) 新零件、(d) Go/No-Go 與翼方向、(e) 干涉檢查）。
* 本模組把同資料夾的參考實作（geom.py／model.py／export.py／checks.py）移植成產生器的
  一部分：模組尺寸改讀 params.MODULE（以及 BEAM_H、C_SENSOR、T_PLY），路徑改成相對 repo，
  不再依賴寫死的 /tmp、/usr/share 路徑。design/ 底下的檔案只讀不改。
* 名目參數下，三種翼向（MODULE['wing'] = 'up'／'down'／'center'）的輸出都和
  geometry_final.json／geometry_final_wing_down.json／geometry_final_wing_center.json 比對過
  （python -m laser_v2.mods_crosstrack，見 selftest()）。

概念（spec §a-1）
----------------
每個間隔條（S5＝#7、S10＝#6、S50＝#5）下方，#24 與 #26 開同一個「階梯窗」，軌道下保留
2.3 mm（光耦段）／3.2 mm（PCB 翼段）的料。模組在窗的低位水平推入，往上滑 9.8，讓保留條
進入光耦槽；再把鎖塊（P1 黏在蓋板 C1 上）貼著 #24 正面由下往上抬到位、往後推 3 mm 讓 P1 進窗
頂住（不可從模組前方直接水平推入：P1 頂住凸塊會撞到前臂底下的焊腳，2026-10-07 改）。S50 的窗
低於 #24 下緣，改成開底缺口，蓋板兩側各一支插銷。軌道與四個分幣開口零改動。

座標（spec §1）
--------------
* 組裝座標 (U,V,W')：見 frames.py。
* 軌道：#24 斜槽下緣的直線擬合（由零件幾何算，名目 V＝0.364032·U＋9.9262）。
* 站座標 (s,n,W')：原點 O＝光束正下方的軌道點；s 沿軌往下游（T）、n 垂直軌道往上（N）；
  光束在 (0, h)。(U,V)＝O＋s·T＋n·N。
* edits：一律是各零件的「原始頁座標」。#24、#26 由 (U,V) 經 frames 的仿射換算；
  間隔條 #5／#6／#7 由 (W',V) 換算。
* new_parts 的區域座標（SVG 慣例，y 往下）：x＝s−s_min（往下游）、y＝n_max−n。
  從板子上面（雷切時朝上、雕刻面）看，等於站在 #24 後方往前看，所以
  **蓋板 C1 的雕刻面就是貼 #24 的背面**（P1 外框、插銷方塊、站名都刻在這面）。

用法
----
    from laser_v2 import mods_crosstrack as CT
    res = CT.build(cat)     # INTERFACE.md：edits／new_parts／notes／warnings／checks
    M = CT.model(cat)       # 內部幾何（站、窗、模組實體、隔板缺口…；組裝座標），給整合檢查用
    python -m laser_v2.mods_crosstrack    # 三種翼向自我測試＋印摘要（細節寫到 _work/crosstrack/）

修改清單（名目、翼朝上游；範圍以組裝座標寫）
------------------------------------------
* #24：S5／S10 階梯窗（封閉孔）、S50 開底缺口、S50 插銷孔 2.9×2.9 ×2、排線孔 10×4.5
  （U91.5～101.5×V103.5～108）；刪 #5、#6 長榫孔；雕刻「1」ΔV+18.5、「5」ΔV−52.5。
* #26：同形窗 ×3、平行四邊形光孔 ×3、#6 新小榫槽 2.9×6.9（V31.05～37.95）、排線孔；
  刪 #5、#6 長榫孔與 #7 中段小榫孔。（#26 齒孔修正 fix_26_tooth_hole() 由 compose 套用，
  本模組不做。）
* #7／#6／#5：缺口（擋面 W'7.8＋2 mm 導角＋深段 W'10.0），刪落在缺口內或剩不到 4 mm 的前榫；
  #6 長榫一律刪除並補上方小榫（V31～38）；#5 缺口直通斜底邊。各雕「S5 v2」「S10 v2」「S50 v2」。
* 新零件：P1-S5／P1-S10／P1-S50（鎖塊）、C1-S5／C1-S10／C1-S50（蓋板）、PIN-S50 ×2（插銷）。
* #37：本規格不改（感測器線孔由電子盒開，見 notes）。

檢查
----
checks.py 裡能由產生的幾何算出的項目都移植成 build()['checks']（窗／光孔／插銷孔／排線孔
到軌道、開口、其他孔與外緣的距離，保留條厚，模組各實體的餘隙，出口平面，隔板件數，
合成後 1 塊，新切割互距，雕刻搬移後的距離，翼的包絡與落幣區侵入）。
需要模擬或外部資料的項目略過（硬幣翻倒＋落下掃掠、相貼兩枚的弦長與空隙、排線長度、
實品偏差的敏感度），列在 notes。
"""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path as FsPath
from types import SimpleNamespace

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union
from svgpathtools import parse_path

from . import frames as F
from . import params as PR
from . import textpath as TP

REPO = FsPath(__file__).resolve().parents[1]
DESIGN_DIR = REPO / 'laser_v2' / 'design' / 'crosstrack_final'
WORK_DIR = REPO / 'laser_v2' / '_work' / 'crosstrack'

# ---------------------------------------------------------------------------
# 子系統設計參數（spec §2.2）。模組尺寸一律讀 params.MODULE，不放這裡。
# ---------------------------------------------------------------------------
DESIGN = dict(
    delta_u={'S5': 0.0, 'S10': 0.0, 'S50': 0.0},  # 光束 U 相對立柱中心的偏移（試切後可調，spec d-5）
    c_body=0.15,      # 窗窄段（光耦本體）單邊餘隙：重力 +s 讓本體貼窄段下游壁，光束落在 s＝0
    c_ntop=1.0,       # 隔板缺口在臂頂上方的餘隙
    g_strip=0.2,      # 保留條底到光耦槽底
    c_slide=1.0,      # 低位時臂頂到保留條底
    c_back=0.3,       # 後臂內面到 #26 背面（推到最前）
    c_stop=0.5,       # 擋面再讓 0.5（靜止時後臂外面貼擋面）
    c_v=0.3,          # 零件頂、焊點底的上下餘隙
    lh_u=1.8,         # #26 光孔沿 U 寬（左右邊沿 V，平行開口邊）
    lh_n=3.6,         # #26 光孔垂直軌道高（光束 ±1.8）
    fit=0.1,          # 新零件與窗、孔的繪製單邊間隙
    cap_m=3.0,        # 蓋板 C1 超出窗的邊寬
    cap_m_pin=7.0,    # 開底站（S50）蓋板兩側邊寬（放插銷）
    v_drawer=97.5,    # #24 前方任何東西的 V 上限（#24 下緣 V98，抽屜在下方）
    chamfer=2.0,      # 隔板擋面下端導角
    min_web=2.0,      # 新切割留下的料小於此值就併入開口；也是新切割互距、離開口／斜槽的下限
    open_ext=30.0,    # 開底時窗寬段往 −n 延伸量（超出外框即可）
    notch_w0=-6.5,    # 隔板缺口起點 W'（從 #24 前面之前開始，前榫一起切）
    tab_min=4.0,      # 前榫被缺口切到後剩不到這長度就整支刪除
    always_delete_long_tab=('S10',),  # spec b-3：#6 長榫一律刪除（翼朝上游時窗離長榫孔只剩 0.09）
    new_tab6_V=(31.0, 38.0),          # #6 v2 新增上方小榫的 V 範圍（取代長榫，插 #26 新槽）
    slot_shrink=0.05,  # 3 mm 榫的槽每邊少 0.05（原檔 3 mm 榫槽畫 2.9 的慣例）
    cable_hole_UV=(91.5, 101.5, 103.5, 108.0),   # 右下排線孔 U0,U1,V0,V1（#24、#26 同位置）
    pin=3.0,          # S50 插銷方塊邊長（3 mm 板切 3.0×3.0；#24 孔畫 pin−2·slot_shrink）
    pin_off=3.5,      # 插銷中心離窗寬段邊（沿 s）
    pin_web=2.0,      # 插銷孔四周 #24 料寬下限
    pin_cap_web=1.5,  # 插銷孔到蓋板邊下限
    pin_n=(-3.6, -40.0, 0.25),   # 插銷孔中心 n 的搜尋範圍與步距
    ear_gap=0.6,      # 開底站蓋板耳離 PCB 的 s 間隙
    ear_top=-1.0,     # 開底站蓋板耳往上長到軌下 1.0（n）
    ear_low=-45.0,    # 蓋板耳的下端（只是相減用，要低於蓋板本體）
    turn_clear=1.0,   # 蓋板離轉盤圍邊 #27／前蓋 #63 的距離
    engrave_hit=1.0,  # 雕刻外框離新切割（窗、蓋板、孔）小於此值就要搬
    engrave_clear=1.5,  # 雕刻新位置離所有切割、其他雕刻的距離下限（spec b-6）
    engrave_search=((-15.0, 15.0), (-60.0, 30.0), 0.25),   # 搬移搜尋範圍 ΔU、ΔV、步距
    div_text_size=3.0,                 # 隔板「S5 v2」字高（em，mm）
    div_text_at=(16.0, 21.5),          # 隔板文字中心偏好位置 (W', V)
    div_text_avoid=(-7.0, 4.0, 0.0, 33.0),   # 隔板文字避開 W'、V 範圍（電子盒會減 #5 前上角 W'≤2、V≤30.31）
    c1_text_sizes=(3.0, 2.8, 2.5, 2.2, 2.1, 2.0, 1.8),   # C1 站名 em（依序試；字墨離切割 ≥1.0、離框線／▲ ≥0.4）
    engrave_edge=0.3,   # 新零件上的雕刻線離切割邊的最小距離
    # 2026-10-07 補（檢查與雕刻記號用，不改任何切割外形）
    locate_wall_min=0.4,  # 窄段下游壁（光束定位面）本體貼得到的高度下限＝n_sb−n_shoulder（名目 0.7）；
                          # 0.4＝spec d-1 Go/No-Go 上限 comp_h 2.3 時的值（再高就和 d-1 矛盾）。不足時本體貼不到
                          # 窄段壁、改靠 PCB 邊定位，光束沿 s 可偏 ±c（spec b-1、a-1「沿軌」定位）
    insert_gap_min=0.1,   # 鎖塊塞法：P1 貼 #24 正面往上抬時，前臂內面到 #24 前面的縫要比 P1 厚多這麼多
    c1_mark_gap=0.4,      # C1 凸塊記號（▲）離 P1 外框線、離 C1 下緣的距離
)
HDR_LEN_DEFAULT = 8.0   # 3P 排針＋杜邦頭沿光束方向佔的長度（params.MODULE 沒有這一項時用）
HDR_W = 7.62            # 3P 排針沿 s 佔的寬（3×2.54）

# 原機參考值（上一輪 chute 分析；不是模組尺寸）
TURN_C = (58.0, 50.0)       # 轉盤軸 (U,V)
TURN_R_RING = 54.5          # 圍邊 #27 外緣（含板厚）／前蓋 #63 最大半徑
MOTOR_U = (43.8, 72.1)      # 馬達盒 U 範圍
RAIL_FIT_U = (80.0, 232.0)  # 軌道擬合取樣的 U 範圍
COINS = ('1', '5', '10', '50')
COIN_D = {'1': 20.0, '5': 22.0, '10': 26.0, '50': 28.0}   # 只用在落幣區侵入（資訊）
STATION_DEF = {   # 站：上游幣、下游幣、隔板
    'S5': ('1', '5', '#7'),
    'S10': ('5', '10', '#6'),
    'S50': ('10', '50', '#5'),
}
DRAWER_WALLS = ('#13', '#7', '#6', '#5', '#21')   # 抽屜之間的板（U 由小到大）
ENG_NAME = {'text16-7-2': '「1」', 'text11-4-1': '「5」', 'text2-1-3': '「10」',
            'text1-6-4': '「50」', 'path1-5-9': 'Logo'}
JSON_BY_WING = {'up': 'geometry_final.json', 'down': 'geometry_final_wing_down.json',
                'center': 'geometry_final_wing_center.json'}
AX = {'U': 0, 'V': 1, 'W': 2}


# ---------------------------------------------------------------------------
# 參數
# ---------------------------------------------------------------------------
def _params(module: dict | None = None) -> dict:
    """模組尺寸（params.MODULE）＋共用參數＋本模組設計參數 → 一個 dict（鍵名沿用 spec）。"""
    m = dict(PR.MODULE if module is None else module)
    if m.get('wing') not in ('up', 'down', 'center'):
        raise ValueError(f"params.MODULE['wing'] 必須是 'up'／'down'／'center'，目前是 {m.get('wing')!r}")
    P = dict(slot_w=m['slot_w'], slot_d=m['slot_d'], beam_sb=m['beam_sb'], arm_t=m['arm_t'],
             arm_w=m['arm_w'], arm_top=m['arm_top'], pcb_L=m['pcb_L'], pcb_W=m['pcb_W'],
             pcb_t=m['pcb_t'], pcb_e=m['body_e'], wing=m['wing'], comp_h=m['comp_h'],
             bump_h=m['back_h'], hdr_up=m['hdr_up'], hdr_len=m.get('hdr_len', HDR_LEN_DEFAULT),
             h=PR.BEAM_H, c=PR.C_SENSOR, t=PR.T_PLY)
    P.update(copy.deepcopy(DESIGN))
    return P


def derived(P: dict) -> dict:
    """spec §2.3 的推導量（站座標 n、W'）。"""
    D = {}
    D['n_sb'] = P['h'] - P['beam_sb']                           # 光耦槽底
    D['n_arm_top'] = D['n_sb'] + P['slot_d']                     # 臂頂
    D['n_pcb_top'] = D['n_sb'] - (P['arm_top'] - P['slot_d'])    # PCB 上面
    D['n_pcb_bot'] = D['n_pcb_top'] - P['pcb_t']                 # PCB 下面
    D['n_comp'] = D['n_pcb_top'] + P['comp_h']                   # 零件頂
    D['n_bump'] = D['n_pcb_bot'] - P['bump_h']                   # 焊點底
    D['n_strip'] = D['n_sb'] + P['g_strip']                      # 保留條底（窗窄段頂）
    D['n_shoulder'] = D['n_comp'] + P['c_v']                     # 窗寬段頂（PCB 翼上方）
    D['slide'] = D['n_arm_top'] - (D['n_strip'] - P['c_slide'])  # 上滑行程
    D['n_win_bot'] = D['n_bump'] - D['slide'] - P['c']           # 窗底
    a = P['arm_w'] / 2
    short = a + P['pcb_e']
    long_ = P['pcb_W'] - short
    if P['wing'] == 'up':
        D['pcb_up'], D['pcb_dn'] = long_, short
    elif P['wing'] == 'down':
        D['pcb_up'], D['pcb_dn'] = short, long_
    else:
        D['pcb_up'] = D['pcb_dn'] = P['pcb_W'] / 2
    D['W_stop'] = P['c_back'] + P['c_stop'] + P['arm_t']         # 隔板擋面
    D['W_ra'] = (D['W_stop'] - P['arm_t'], D['W_stop'])          # 後臂（靜止）
    D['W_fa'] = (D['W_ra'][0] - P['slot_w'] - P['arm_t'], D['W_ra'][0] - P['slot_w'])   # 前臂
    ov = (P['pcb_L'] - 2 * P['arm_t'] - P['slot_w']) / 2
    D['pcb_ov'] = ov
    D['W_pcb'] = (D['W_fa'][0] - ov, D['W_ra'][1] + ov)
    D['W_deep'] = D['W_pcb'][1] + P['c']                         # 隔板深缺口後壁
    D['t_strip'] = -D['n_strip']                                 # #24 保留條厚（光耦段）
    D['t_shoulder'] = -D['n_shoulder']                           # #24 肩部厚（PCB 翼段）
    return D


# ---------------------------------------------------------------------------
# 座標換算
# ---------------------------------------------------------------------------
def page_affine(pid: str, axes=('U', 'V')) -> list[float]:
    """(axes[0], axes[1]) → 該零件原始頁座標 (x, y) 的 shapely 仿射參數 [a,b,d,e,xoff,yoff]。
    板面要平行這兩軸（#24/#26 用 (U,V)，間隔條用 (W',V)）。"""
    T = F.frame(pid).T
    i, j = AX[axes[0]], AX[axes[1]]
    if abs(T[i, 2]) > 1e-9 or abs(T[j, 2]) > 1e-9:
        raise ValueError(f'{pid} 的板面不平行 {axes}')
    M = np.array([[T[i, 0], T[i, 1]], [T[j, 0], T[j, 1]]])
    off = np.array([T[i, 3], T[j, 3]])
    Mi = np.linalg.inv(M)
    o = -Mi @ off
    return [Mi[0, 0], Mi[0, 1], Mi[1, 0], Mi[1, 1], o[0], o[1]]


def to_page(pid: str, g, axes=('U', 'V')):
    return affinity.affine_transform(g, page_affine(pid, axes))


def _inv_affine(A) -> list[float]:
    """shapely 仿射參數 [a,b,d,e,xoff,yoff] 的反變換。"""
    a, b, d, e, xo, yo = (float(v) for v in A)
    M = np.linalg.inv(np.array([[a, b], [d, e]]))
    o = -M @ np.array([xo, yo])
    return [M[0, 0], M[0, 1], M[1, 0], M[1, 1], o[0], o[1]]


def _page_delta(pid: str, dA: float, dB: float, axes=('U', 'V')) -> tuple[float, float]:
    a, b, d, e, _, _ = page_affine(pid, axes)
    return a * dA + b * dB, d * dA + e * dB


class SN:
    """站座標 (s,n) ↔ 組裝座標 (U,V)。"""

    def __init__(self, O, T, N):
        self.O, self.T, self.N = np.asarray(O, float), np.asarray(T, float), np.asarray(N, float)

    def pt(self, s, n):
        return self.O + s * self.T + n * self.N

    def rect(self, s0, s1, n0, n1) -> Polygon:
        return Polygon([tuple(self.pt(s, n)) for s, n in ((s0, n0), (s1, n0), (s1, n1), (s0, n1))])

    def poly(self, pts) -> Polygon:
        return Polygon([tuple(self.pt(s, n)) for s, n in pts])

    def to_uv(self, g):
        T, N, O = self.T, self.N, self.O
        return affinity.affine_transform(g, [T[0], N[0], T[1], N[1], O[0], O[1]])

    def to_sn(self, g):
        T, N, O = self.T, self.N, self.O
        return affinity.affine_transform(affinity.translate(g, -O[0], -O[1]), [T[0], T[1], N[0], N[1], 0, 0])


# ---------------------------------------------------------------------------
# 原機基礎幾何（port geom.py）：全部由 catalog＋frames 算
# ---------------------------------------------------------------------------
def _base(cat: dict) -> SimpleNamespace:
    B = SimpleNamespace(cat=cat)

    def asm(pid, axes=('U', 'V')):
        fr = F.frame(pid)
        return fr.geom_asm(cat[pid].geom, fr.thickness / 2, axes)

    B.G24, B.G26 = asm('#24'), asm('#26')
    B.O24, B.O26 = Polygon(B.G24.exterior), Polygon(B.G26.exterior)
    B.H24 = [Polygon(h) for h in B.G24.interiors]
    B.H26 = [Polygon(h) for h in B.G26.interiors]
    B.SLOT24 = max(B.H24, key=lambda p: p.area)      # #24 斜槽（硬幣通道）

    # 軌道：#24 斜槽下緣直線擬合
    pts = []
    for U in np.arange(RAIL_FIT_U[0], RAIL_FIT_U[1], 1.0):
        L = LineString([(U, -5), (U, 130)]).intersection(B.SLOT24)
        if not L.is_empty:
            pts.append((U, L.bounds[3]))
    pts = np.array(pts)
    A = np.vstack([pts[:, 0], np.ones(len(pts))]).T
    B.RAIL_M, B.RAIL_B = np.linalg.lstsq(A, pts[:, 1], rcond=None)[0]
    B.RAIL_RES = float(np.abs(pts[:, 1] - (B.RAIL_M * pts[:, 0] + B.RAIL_B)).max())
    B.ANG = math.atan(B.RAIL_M)
    B.CA, B.SA = math.cos(B.ANG), math.sin(B.ANG)
    B.T = np.array([B.CA, B.SA])     # 沿軌往下游
    B.N = np.array([B.SA, -B.CA])    # 垂直軌道往上
    B.railV = lambda U: B.RAIL_M * np.asarray(U, float) + B.RAIL_B
    B.n_of = lambda U, V: (B.railV(U) - V) * B.CA

    # 分幣開口：#26 U>100 的四個大孔，由右到左＝1／5／10／50 元
    big = sorted([p for p in B.H26 if p.area > 300 and p.bounds[0] > 100], key=lambda p: p.bounds[0])
    if len(big) != 4:
        raise RuntimeError(f'#26 找到 {len(big)} 個分幣開口（應為 4）')
    B.OPS = dict(zip(COINS, big))
    B.op_U = lambda c: (B.OPS[c].bounds[0], B.OPS[c].bounds[2])
    B.LIP = {c: float(min(B.n_of(x, y) for x, y in np.array(p.exterior.coords))) for c, p in B.OPS.items()}

    B.ST = {}
    for k, (up, dn, div) in STATION_DEF.items():
        bar = (B.op_U(up)[1], B.op_U(dn)[0])
        pl = F.frame(div).plane()
        B.ST[k] = dict(up=up, dn=dn, div=div, bar=bar, Ubar=sum(bar) / 2, divU=(pl[1], pl[2]))

    B.DIVWV = {pid: asm(pid, ('W', 'V')) for pid in ('#5', '#6', '#7')}

    # 滑道出口平面＝隔板斜底邊（名目 W'0→V98、W'29→V82）
    def bottom_V(W):
        return LineString([(W, 0.0), (W, 200.0)]).intersection(B.DIVWV['#7']).bounds[3]
    Wa, Wb = 1.0, F.W37_IN - 1.0
    Va, Vb = bottom_V(Wa), bottom_V(Wb)
    slope = (Vb - Va) / (Wb - Wa)
    B.exitV = lambda W: Va + slope * (np.asarray(W, float) - Wa)

    # #24 雕刻外框（組裝座標）
    p24 = cat['#24']
    fwd = F.frame('#24')
    B.ENG24 = {}
    for e, src in zip(p24.engrave, p24.engrave_src):
        P_ = []
        for d in re.findall(r'\sd="([^"]+)"', e):
            for seg in parse_path(d):
                for t in np.linspace(0, 1, 10):
                    z = seg.point(t)
                    P_.append((z.real, z.imag))
        if P_:
            Aa = np.array(P_)
            Bb = fwd.to_asm(Aa[:, 0], Aa[:, 1], 0)
            B.ENG24[src] = box(Bb[:, 0].min(), Bb[:, 1].min(), Bb[:, 0].max(), Bb[:, 1].max())

    B.CAB13_U = tuple(F.frame('#13').plane()[1:])
    B.W37 = F.W37_IN
    B.TURN = Point(TURN_C)
    return B


# ---------------------------------------------------------------------------
# 模型（port model.py）
# ---------------------------------------------------------------------------
def module_boxes(P, D, dn=0.0):
    """模組各實體（站座標盒）：(名稱, s0, s1, n0, n1, W0, W1)。dn＝整體沿 n 位移（低位＝−slide）。"""
    a = P['arm_w'] / 2
    up, dw = D['pcb_up'], D['pcb_dn']
    Bx = [
        ('前臂', -a, a, D['n_pcb_top'], D['n_arm_top'], *D['W_fa']),
        ('後臂', -a, a, D['n_pcb_top'], D['n_arm_top'], *D['W_ra']),
        ('本體底座', -a, a, D['n_pcb_top'], D['n_sb'], D['W_fa'][0], D['W_ra'][1]),
        ('PCB', -up, dw, D['n_pcb_bot'], D['n_pcb_top'], *D['W_pcb']),
        ('PCB 零件區', -up, dw, D['n_pcb_top'], D['n_comp'], *D['W_pcb']),
        ('PCB 焊點區', -up, dw, D['n_bump'], D['n_pcb_bot'], *D['W_pcb']),
    ]
    # 排針＋杜邦頭（假設：PCB 前端、翼的遠端，直立朝上）
    hs = (-up, -up + HDR_W) if P['wing'] in ('up', 'center') else (dw - HDR_W, dw)
    Bx.append(('排針＋杜邦頭', hs[0], hs[1], D['n_pcb_top'], D['n_pcb_top'] + P['hdr_up'],
               D['W_pcb'][0], D['W_pcb'][0] + P['hdr_len']))
    return [(nm, s0, s1, n0 + dn, n1 + dn, w0, w1) for nm, s0, s1, n0, n1, w0, w1 in Bx]


def _stations(B, P, D) -> dict:
    T, N = B.T, B.N
    a, c, f = P['arm_w'] / 2, P['c'], P['fit']
    lim = box(0, 0, 246, P['v_drawer'])
    S = {}
    for k, st in B.ST.items():
        U_beam = st['Ubar'] + P['delta_u'][k]
        U_O = U_beam - P['h'] * N[0]
        O = np.array([U_O, float(B.railV(U_O))])
        sn = SN(O, T, N)
        R = dict(k=k, O=O, sn=sn, beam_UV=O + P['h'] * N, **st)
        s0w, s1w = -D['pcb_up'] - c, D['pcb_dn'] + c          # 窗寬段 s 範圍
        R['win_s'] = (s0w, s1w)
        # ---- 窗（#24、#26 同形）：窄段（光耦本體／後臂）＋寬段（PCB 翼）----
        cb = P['c_body']
        r_body = sn.rect(-a - 2 * cb, a, D['n_win_bot'], D['n_strip'])
        R['body_s'] = (-a - 2 * cb, a)
        r_pcb = sn.rect(s0w, s1w, D['n_win_bot'], D['n_shoulder'])
        R['r_pcb'] = r_pcb
        win = unary_union([r_body, r_pcb])
        R['breaks_edge'] = not B.O24.buffer(-P['min_web']).contains(win)
        if R['breaks_edge']:   # 開底：寬段沿 −n 直通下緣（不留楔形碎片）
            ext = sn.rect(s0w, s1w, D['n_win_bot'] - P['open_ext'], D['n_shoulder'])
            win = unary_union([win, ext]).intersection(box(0, 0, 246, 120))
        R['win'] = win
        R['win_in24'] = win.intersection(B.O24)
        R['win_in26'] = win.intersection(B.O26)
        # ---- #26 光孔：平行四邊形（上下緣平行軌道、左右邊沿 V）----
        Ub = R['beam_UV'][0]
        n0, n1 = P['h'] - P['lh_n'] / 2, P['h'] + P['lh_n'] / 2
        pts = []
        for nn, uu in ((n0, Ub - P['lh_u'] / 2), (n0, Ub + P['lh_u'] / 2),
                       (n1, Ub + P['lh_u'] / 2), (n1, Ub - P['lh_u'] / 2)):
            s = (uu - O[0] - nn * N[0]) / T[0]
            pts.append(tuple(O + s * T + nn * N))
        R['lh'] = Polygon(pts)
        # ---- 模組 ----
        R['mod_final'] = module_boxes(P, D, 0.0)
        R['mod_low'] = module_boxes(P, D, -D['slide'])
        # ---- 隔板缺口（(W',V) 平面）----
        Ua, Ub2 = st['divU']
        slab = box(Ua, -50, Ub2, 200)

        def vrange(s0, s1, n0_, n1_):
            g = sn.rect(s0, s1, n0_, n1_).intersection(slab)
            return None if g.is_empty else (g.bounds[1], g.bounds[3])
        va = vrange(-a, a, D['n_pcb_top'] - D['slide'], D['n_arm_top'])                  # 臂＋本體（上滑掃掠）
        vp = vrange(-D['pcb_up'], D['pcb_dn'], D['n_bump'] - D['slide'], D['n_comp'])   # PCB＋零件＋焊點
        R['notch_va'], R['notch_vp'] = va, vp
        R['notch_va_fin'] = vrange(-a, a, D['n_pcb_top'], D['n_arm_top'])
        deep = (vp[0] - c, vp[1] + c)
        stop = (va[0] - P['c_ntop'], va[1] + c)
        R['notch_open_bottom'] = False
        if deep[1] + P['min_web'] > B.exitV(D['W_deep']):   # 缺口底到斜底邊不足 → 直通底邊
            deep = (deep[0], 130.0)
            R['notch_open_bottom'] = True
        w0 = P['notch_w0']
        parts = [box(w0, deep[0], D['W_deep'], deep[1]), box(w0, stop[0], D['W_stop'], min(stop[1], deep[1]))]
        if stop[0] < deep[0]:   # 擋面下端導角
            ch = P['chamfer']
            parts.append(Polygon([(D['W_stop'], deep[0]), (D['W_deep'], deep[0]), (D['W_stop'], deep[0] - ch)]))
        R['stop_contact_V'] = (stop[0], deep[0] - P['chamfer'])
        notch = unary_union(parts)
        # 前榫：剩餘長度 < tab_min → 整支刪除；always_delete_long_tab 站的長榫一律刪除
        dv = B.DIVWV[st['div']]
        front = dv.intersection(box(w0, 0, -1e-3, 120))
        tabs = sorted(getattr(front, 'geoms', [front]), key=lambda g: g.bounds[1])
        R['tabs'] = []
        for g in tabs:
            b = g.bounds
            rem = g.difference(notch)
            rem_len = 0 if rem.is_empty else rem.bounds[3] - rem.bounds[1]
            full = b[3] - b[1]
            depth = -b[0]
            kill = rem_len < P['tab_min'] or (k in P['always_delete_long_tab'] and depth > P['t'] + 0.5)
            if rem_len < full - 1e-3 or kill:
                status = '刪除' if kill else '縮短'
            else:
                status = '保留'
            if kill:
                notch = notch.union(box(w0, b[1] - 0.01, 0.0, b[3] + 0.01))
            R['tabs'].append(dict(V=(round(b[1], 2), round(b[3], 2)), depth=round(depth, 2), status=status,
                                  remain_V=None if rem.is_empty or kill else (round(rem.bounds[1], 2), round(rem.bounds[3], 2))))
        new_div = dv.difference(notch)
        pieces = list(getattr(new_div, 'geoms', [new_div]))
        main = max(pieces, key=lambda g: g.area)
        R['div_pieces'] = len(pieces)
        cutter = notch
        if len(pieces) > 1:      # 碎片也切掉（compose 要求 1 塊）
            cutter = unary_union([notch] + [p.buffer(0.01) for p in pieces if p is not main])
        R['div_cutter'] = cutter
        R['div_add'] = None
        if k == 'S10':      # #6：新增上方小榫（插 #26 新槽）；往板內多 0.5 只為了合併乾淨
            v0, v1 = P['new_tab6_V']
            R['div_add'] = box(-P['t'], v0, 0.5, v1)
            main = main.union(box(-P['t'], v0, 0.0, v1))
        R['notch'] = dv.difference(main)
        R['div_new'] = main
        # ---- 鎖塊 P1（#24 平面）、蓋板 C1（#24 前方）----
        n_body = D['n_pcb_bot']
        n_wing = D['n_bump'] - P['c_v']
        p1_pts = lambda nb: [(s0w + f, nb), (s1w - f, nb), (s1w - f, n_wing), (a - f, n_wing), (a - f, n_body),
                             (-a - 2 * cb + f, n_body), (-a - 2 * cb + f, n_wing), (s0w + f, n_wing)]
        p1 = Polygon(p1_pts(D['n_win_bot']))
        m = P['cap_m'] if not R['breaks_edge'] else P['cap_m_pin']
        c1 = box(s0w - m, D['n_win_bot'] - P['cap_m'] - (40 if R['breaks_edge'] else 0), s1w + m, n_wing)
        if R['breaks_edge']:   # 插銷耳：PCB 範圍外往上長到軌下 1.0
            pcb_s0, pcb_s1 = -D['pcb_up'] - P['ear_gap'], D['pcb_dn'] + P['ear_gap']
            c1 = unary_union([c1, box(s0w - m, P['ear_low'], pcb_s0, P['ear_top']),
                              box(pcb_s1, P['ear_low'], s1w + m, P['ear_top'])])
        p1uv, c1uv = sn.to_uv(p1), sn.to_uv(c1)
        c1uv = c1uv.difference(B.TURN.buffer(TURN_R_RING + P['turn_clear'], 128))
        if R['breaks_edge']:   # 開底：P1 往下取到 v_drawer
            p1 = Polygon(p1_pts(D['n_win_bot'] - P['open_ext']))
            p1uv = sn.to_uv(p1).intersection(lim)
        c1uv = c1uv.intersection(lim).intersection(B.O24)
        if R['breaks_edge']:
            c1uv = max(getattr(c1uv, 'geoms', [c1uv]), key=lambda g: g.area)
        R['p1'], R['c1'] = p1uv, c1uv
        S[k] = R
    return S


def _deleted_holes(B, S, P) -> list[dict]:
    """被刪掉的前榫所對應的 #24／#26 孔（v2 不再切）。深度 > 板厚的榫（長榫）穿 #24 與 #26。"""
    out = []
    for k, R in S.items():
        U0, U1 = R['divU']
        for tb in R['tabs']:
            if tb['status'] != '刪除':
                continue
            V0, V1 = tb['V']
            reg = box(U0 - 0.6, V0 - 0.6, U1 + 0.6, V1 + 0.6)
            plates = ['#24', '#26'] if tb['depth'] > P['t'] + 0.5 else ['#26']
            for pid in plates:
                H = B.H24 if pid == '#24' else B.H26
                hit = [h for h in H if h.area < 300 and reg.contains(h.centroid)]
                why = {'#7': '#7 中段小榫已刪（落在 S5 窗與隔板缺口內）' if tb['depth'] <= P['t'] + 0.5 else '#7 長榫已刪',
                       '#6': '#6 長榫已刪' if tb['depth'] > P['t'] + 0.5 else '#6 小榫已刪',
                       '#5': '#5 長榫已刪（S50 缺口直通下緣）' if tb['depth'] > P['t'] + 0.5 else '#5 小榫已刪'}[R['div']]
                out.append(dict(part=pid, station=k, tab_V=(V0, V1), hole=hit[0] if len(hit) == 1 else None,
                                n_found=len(hit), why=why))
    return out


def _is_deleted(h, dels, part):
    b = h.bounds
    for d in dels:
        if d['part'] != part or d['hole'] is None:
            continue
        e = d['hole'].bounds
        if all(abs(b[i] - e[i]) < 0.1 for i in range(4)):
            return True
    return False


def _pins(B, S, P, dels):
    """開底站（S50）的插銷孔：窗兩側各一，在 #24 實料內、蓋板內，離其他孔 ≥2。"""
    sh = P['slot_shrink']
    hp = P['pin'] / 2 - sh          # 孔半寬（2.9／2）
    n_hi, n_lo, dn = P['pin_n']
    for k, R in S.items():
        R['pins'] = []
        if not R['breaks_edge']:
            continue
        sn, win, c1uv = R['sn'], R['win'], R['c1']
        s0w, s1w = R['win_s']
        mat = B.O24.difference(win)
        mat_in = mat.buffer(-P['pin_web'])
        c1_in = c1uv.buffer(-P['pin_cap_web'])
        avoid = [h for h in B.H24 if h.distance(R['r_pcb']) < 40 and not _is_deleted(h, dels, '#24')]
        for side, s_c in (('上游', s0w - P['pin_off']), ('下游', s1w + P['pin_off'])):
            ok = []
            for nn in np.arange(n_hi, n_lo, -dn):
                hole = sn.rect(s_c - hp, s_c + hp, nn - hp, nn + hp)
                if mat_in.contains(hole) and c1_in.contains(hole) and all(hole.distance(h) >= P['pin_web'] for h in avoid):
                    ok.append(nn)
            if ok:
                nn = float(np.median(ok))
                nn = round(nn * 4) / 4
                R['pins'].append(dict(side=side, s=s_c, n=nn, n_ok=(min(ok), max(ok)),
                                      hole=sn.rect(s_c - hp, s_c + hp, nn - hp, nn + hp)))
            else:
                R['pins'].append(None)


def _extra(B, P) -> dict:
    X = {}
    sh = P['slot_shrink']
    Uc6 = sum(B.ST['S10']['divU']) / 2
    v0, v1 = P['new_tab6_V']
    hw = P['t'] / 2 - sh
    X['slot26_tab6'] = box(Uc6 - hw, v0 + sh, Uc6 + hw, v1 - sh)
    u0, u1, w0, w1 = P['cable_hole_UV']
    X['cable_hole'] = box(u0, w0, u1, w1)
    return X


def _engrave_moves(B, S, X, dels, P) -> dict:
    """被新切割（窗、蓋板、插銷孔、排線孔）蓋到的 #24 雕刻，找最小平移（成本 |ΔV|+3|ΔU|）；
    新位置要在 #24 外框內縮 1.5、V≤v_drawer−1，且離所有切割、孔、轉盤區、其他雕刻 ≥ engrave_clear。"""
    new_cuts = unary_union([R['win_in24'] for R in S.values()] + [R['c1'] for R in S.values()] +
                           [p['hole'] for R in S.values() for p in R['pins'] if p] + [X['cable_hole']])
    small = [h for h in B.H24 if h.area < 300 and not _is_deleted(h, dels, '#24')]
    region = B.O24.buffer(-P['engrave_clear']).intersection(box(0, 0, 246, P['v_drawer'] - 1.0))
    ring = B.TURN.buffer(TURN_R_RING + 1.0, 128)
    (du0, du1), (dv0, dv1), stp = P['engrave_search']
    cands = []
    idx = 0
    for dU in np.arange(du0, du1 + 0.01, stp):
        for dV in np.arange(dv0, dv1 + 0.01, stp):
            cands.append((abs(dV) + 3 * abs(dU), idx, dU, dV))
            idx += 1
    cands.sort()
    moves = {}
    for src, b in B.ENG24.items():
        if not b.buffer(P['engrave_hit']).intersects(new_cuts):
            continue
        others = unary_union([bb for s2, bb in B.ENG24.items() if s2 != src])
        blk = unary_union([new_cuts, B.SLOT24, others] + small + [ring])
        shapely.prepare(blk)
        best = None
        for cost, _, dU, dV in cands:
            bb = affinity.translate(b, dU, dV)
            if region.contains(bb) and not bb.buffer(P['engrave_clear']).intersects(blk):
                best = (cost, dU, dV)
                break
        nb = None if best is None else affinity.translate(b, best[1], best[2])
        moves[src] = dict(name=ENG_NAME.get(src, src), old=b, new=nb,
                          dU=None if best is None else round(float(best[1]), 2),
                          dV=None if best is None else round(float(best[2]), 2),
                          clear=None if nb is None else float(nb.distance(blk)))
    return moves


def model(cat: dict | None = None, module: dict | None = None) -> dict:
    """完整內部模型（組裝座標）。module＝暫時取代 params.MODULE（自我測試換翼向用）。"""
    if cat is None:
        from .catalog import load_catalog
        cat = load_catalog()
    P = _params(module)
    D = derived(P)
    B = _base(cat)
    S = _stations(B, P, D)
    dels = _deleted_holes(B, S, P)
    _pins(B, S, P, dels)
    X = _extra(B, P)
    moves = _engrave_moves(B, S, X, dels, P)
    return dict(P=P, D=D, B=B, S=S, X=X, deleted=dels, moves=moves)


# ---------------------------------------------------------------------------
# 雷切輸出：edits、new_parts
# ---------------------------------------------------------------------------
def _cut_src_of(part, page_poly, tol=0.05):
    """原始零件裡外形與 page_poly 外框相同的封閉切割子路徑 → cut_src。"""
    b = page_poly.bounds
    for i, (d, src, cl) in enumerate(zip(part.cut_d, part.cut_src, part.cut_closed)):
        if i == 0 or not cl:
            continue
        x0, x1, y0, y1 = parse_path(d).bbox()
        if abs(x0 - b[0]) < tol and abs(y0 - b[1]) < tol and abs(x1 - b[2]) < tol and abs(y1 - b[3]) < tol:
            return src
    return None


def _place_text(region, text, sizes, *, avoid=None, prefer=None, angles=(0.0,), step=0.2):
    """在 region（零件實料，邊界＝切割線）放雕刻字：字墨外框離切割線 ≥ textpath.TEXT_CLEAR（1.0）、
    離 avoid（黏貼框、▲ 記號、插銷方塊、要留空的區域）≥ textpath.ENGRAVE_GAP（0.4）。
    sizes 依序試（先大字）；同一個字高下 angles 排前面的優先（橫排放得下就不直排）。
    回傳 textpath.fit_text 的 dict（text/x/y/size/angle/anchor＋ink、slack）；放不下回傳 None。"""
    return TP.fit_text(region, text, sizes, avoid=avoid, prefer=prefer, angles=angles, step=step, angle_penalty=100.0)


def _clipped_outline_d(g, clip) -> str:
    """多邊形 g 的外框線只留在 clip 裡面的部分 → SVG path d（雕刻用；整圈都在裡面時用 Z 閉合）。"""
    out = []
    for p in getattr(g, 'geoms', [g]):
        for r in [p.exterior] + list(p.interiors):
            seg = LineString(r.coords).intersection(clip)
            if seg.is_empty:
                continue
            if seg.geom_type == 'LineString' and seg.length > r.length - 1e-6:
                C = np.array(r.coords)[:-1]
                out.append('M ' + ' L '.join(f'{x:.4f},{y:.4f}' for x, y in C) + ' Z')
                continue
            lines = [q for q in getattr(seg, 'geoms', [seg]) if q.geom_type == 'LineString' and q.length > 0.05]
            if len(lines) > 1:
                from shapely.ops import linemerge
                mg = linemerge(lines)
                lines = [q for q in getattr(mg, 'geoms', [mg]) if q.length > 0.05]
            for q in lines:
                out.append('M ' + ' L '.join(f'{x:.4f},{y:.4f}' for x, y in q.coords))
    return ' '.join(out)


def _new_part_frame(R, g_uv):
    """新零件：UV 外形 → 站座標 → 區域座標（x＝s−s_min、y＝n_max−n）。回傳 (幾何, 變換函式, (s_min, n_min, n_max))。"""
    g = R['sn'].to_sn(g_uv)
    s0, n0, s1, n1 = g.bounds
    tf = lambda q: affinity.affine_transform(q, [1, 0, 0, -1, -s0, n1])
    return tf(g), tf, (s0, n0, n1)


def _edits_and_parts(M: dict, cat: dict):
    P, D, B, S, X = M['P'], M['D'], M['B'], M['S'], M['X']
    edits, new_parts, touched = [], [], {}

    def add(op, part, region='', **kw):
        e = dict(op=op, part=part, **kw)
        edits.append(e)
        touched.setdefault(part, []).append(f"{kw.get('tag', op)} {region}".strip())
        return e

    def uvr(g):
        b = g.bounds
        return f'U{b[0]:.1f}～{b[2]:.1f}×V{b[1]:.1f}～{b[3]:.1f}'

    def wvr(g):
        b = g.bounds
        return f"W'{b[0]:.1f}～{b[2]:.1f}×V{b[1]:.1f}～{b[3]:.1f}"

    for k, R in S.items():
        # 窗
        if R['breaks_edge']:
            w24 = R['win'].intersection(B.O24.buffer(5))
            w26 = R['win'].intersection(B.O26.buffer(5))
            tag = f'{k} 開底缺口（階梯形）'
        else:
            w24 = w26 = R['win']
            tag = f'{k} 階梯窗'
        add('subtract', '#24', uvr(R['win_in24']), geom=to_page('#24', w24), tag=tag)
        add('subtract', '#26', uvr(R['win_in26']), geom=to_page('#26', w26), tag=tag)
        add('subtract', '#26', uvr(R['lh']), geom=to_page('#26', R['lh']), tag=f'{k} 光孔（平行四邊形）')
        for p in R['pins']:
            if p:
                add('subtract', '#24', uvr(p['hole']), geom=to_page('#24', p['hole']), tag=f"{k} 插銷孔（{p['side']}）")
        # 隔板
        div = R['div']
        add('subtract', div, wvr(R['notch']), geom=to_page(div, R['div_cutter'], ('W', 'V')),
            tag=f'{k} 隔板缺口（擋面＋導角＋深段）' + ('，直通斜底邊' if R['notch_open_bottom'] else ''))
        if R['div_add'] is not None:
            add('union', div, wvr(R['div_add']), geom=to_page(div, R['div_add'], ('W', 'V')),
                tag=f'{div} v2 上方小榫（取代長榫，插 #26 新槽）')
    # #26 新槽、排線孔
    add('subtract', '#26', uvr(X['slot26_tab6']), geom=to_page('#26', X['slot26_tab6']), tag='#6 新小榫槽')
    for pid in ('#24', '#26'):
        add('subtract', pid, uvr(X['cable_hole']), geom=to_page(pid, X['cable_hole']), tag='感測器排線孔（右下）')
    # 不再切的原始孔
    for d in M['deleted']:
        if d['hole'] is None:
            continue
        src = _cut_src_of(cat[d['part']], to_page(d['part'], d['hole']))
        d['src'] = src
        if src is None:
            continue
        add('delete_cut', d['part'], uvr(d['hole']), src=src, tag=f"刪孔：{d['why']}")
    # 雕刻搬移
    for src, mv in M['moves'].items():
        if mv['new'] is None:
            continue
        dx, dy = _page_delta('#24', mv['dU'], mv['dV'])
        add('move_engrave', '#24', f"→{uvr(mv['new'])}", src=src, dx=round(float(dx), 4), dy=round(float(dy), 4),
            tag=f"雕刻{mv['name']}搬移 ΔU{mv['dU']:+g} ΔV{mv['dV']:+g}")
    # 隔板雕字「S5 v2」
    for k, R in S.items():
        div = R['div']
        text = f'{k} v2'
        g_new = R['div_new']
        if R['div_add'] is not None:
            g_new = g_new.union(R['div_add'])
        aw0, aw1, av0, av1 = P['div_text_avoid']
        # 在頁座標排（字一律 angle 0、和頁面同向）：實料＝v2 外形，避開電子盒會再減的前上角
        reg_pg = to_page(div, g_new, ('W', 'V'))
        av_pg = to_page(div, box(aw0, av0, aw1, av1), ('W', 'V'))
        pref = to_page(div, Point(*P['div_text_at']), ('W', 'V')).coords[0]
        pl = _place_text(reg_pg, text, (P['div_text_size'], 2.5, 2.0), avoid=av_pg, prefer=pref, step=0.5)
        if pl is None:
            R['div_text'] = None
            continue
        ink_wv = affinity.affine_transform(pl['ink'], _inv_affine(page_affine(div, ('W', 'V'))))
        c = ink_wv.centroid
        R['div_text'] = dict(text=text, W=c.x, V=c.y, size=pl['size'], box=ink_wv, clear=round(TP.TEXT_CLEAR + pl['slack'], 2))
        add('add_engrave_text', div, f"中心 W'{c.x:.1f} V{c.y:.1f}", **TP.text_spec(pl), tag=f'{div} 雕刻「{text}」')

    # ---- 新零件 ----
    for k, R in S.items():
        p1, _, _ = _new_part_frame(R, R['p1'])
        c1, tf, (cs0, cn0, cn1) = _new_part_frame(R, R['c1'])
        p1_on_c1 = tf(R['sn'].to_sn(R['p1']))
        inner = c1.buffer(-P['engrave_edge'])     # 雕刻線離切割邊至少 engrave_edge（P1 頂住凸塊伸出 C1 上緣的部分不刻）
        eng = [_clipped_outline_d(p1_on_c1, inner)]
        pin_sq = []
        for pn in R['pins']:
            if pn:
                q = box(pn['s'] - P['pin'] / 2, pn['n'] - P['pin'] / 2, pn['s'] + P['pin'] / 2, pn['n'] + P['pin'] / 2)
                q = affinity.affine_transform(q, [1, 0, 0, -1, -cs0, cn1])
                pin_sq.append(q)
                eng.append(_clipped_outline_d(q, inner))
        eng = [d for d in eng if d]
        # 凸塊記號（workshop-3）：S5／S10 的 P1 框左右對稱，P1 翻面也套得進，所以在 C1 下邊距、對齊頂住凸塊
        # 的 x 範圍刻一個尖端朝上的三角形 ▲（底邊＝凸塊寬），講師照記號把凸塊放在這一端。S50 外框不對稱，不需要。
        mark = None
        R['c1_mark'] = None
        if not R['breaks_edge']:
            cb0, cb1 = c1.bounds[1], c1.bounds[3]
            # 伸出 C1 上緣的才是頂住凸塊。P1 本體上緣和 C1 上緣同一條線（n_wing）：留 0.01，免得浮點誤差把整條
            # 上緣當成凸塊（back_h＝2.0 時曾經整個 P1 寬都被當成凸塊，▲ 變成全寬、站名沒地方放）
            bump = p1_on_c1.intersection(box(c1.bounds[0] - 1, cb0 - 20.0, c1.bounds[2] + 1, cb0 - 0.01))
            bump = unary_union([q for q in getattr(bump, 'geoms', [bump]) if q.geom_type == 'Polygon' and q.area > 1e-3]) \
                if not bump.is_empty else bump
            g_ = P['c1_mark_gap']
            y_top = p1_on_c1.bounds[3] + g_
            y_bot = cb1 - max(g_, P['engrave_edge'])
            if not bump.is_empty and y_bot - y_top >= 1.0:
                bx0, bx1 = bump.bounds[0], bump.bounds[2]
                mark = Polygon([(bx0, y_bot), ((bx0 + bx1) / 2, y_top), (bx1, y_bot)])
                eng.append('M ' + ' L '.join(f'{x:.4f},{y:.4f}' for x, y in list(mark.exterior.coords)[:-1]) + ' Z')
                R['c1_mark'] = dict(x=(round(bx0, 3), round(bx1, 3)), y=(round(y_top, 3), round(y_bot, 3)))
        # 站名：字墨離 C1 切割邊 ≥1.0、離 P1 黏貼框／插銷方塊／▲ ≥0.4（不可壓到）；有 ▲ 時放在另一端
        # （說明裡用「站名在另一端」輔助辨認）。直排、橫排都試，先取放得下的最大字。
        avoid = [p1_on_c1] + list(pin_sq)
        if mark is not None:
            avoid.append(mark)
            xm = (c1.bounds[0] + c1.bounds[2]) / 2
            avoid.append(box(xm, c1.bounds[1] - 1, c1.bounds[2] + 1, c1.bounds[3] + 1) if mark.centroid.x > xm
                         else box(c1.bounds[0] - 1, c1.bounds[1] - 1, xm, c1.bounds[3] + 1))
        pl = _place_text(c1, k, P['c1_text_sizes'], avoid=unary_union(avoid), angles=(0.0, -90.0, 90.0))
        texts = []
        R['c1_text'] = None
        if pl:
            texts.append(TP.text_spec(pl))
            R['c1_text'] = dict(size=pl['size'], angle=pl['angle'], clear=round(TP.TEXT_CLEAR + pl['slack'], 2))
        R['c1_local'], R['p1_local'], R['p1_on_c1'], R['pin_sq'] = c1, p1, p1_on_c1, pin_sq
        p1_where = '頂住凸塊在上緣' + ('、對齊 C1 下緣 ▲ 記號那一端' if mark is not None else '')
        new_parts.append(dict(id=f'P1-{k}', name=f'{k} 鎖塊 P1（黏在 C1 雕刻外框內，{p1_where}）',
                              material='合板', qty=1, geom=p1, engrave=[], texts=[]))
        new_parts.append(dict(id=f'C1-{k}', name=f'{k} 蓋板 C1（雕刻面＝貼 #24 的背面）', material='合板', qty=1,
                              geom=c1, engrave=eng, texts=texts))
    npins = sum(1 for R in S.values() for p in R['pins'] if p)
    if npins:
        ks = '／'.join(k for k, R in S.items() if any(R['pins']))
        # 3×3 極小零件：每套多切一整份備品（使用者 2026-10-08 決定 3；掉進蜂巢台或弄丟時用）
        new_parts.append(dict(id='PIN-' + ks.replace('／', '-'), name=f'{ks} 插銷（黏在 C1 雕刻方塊上）',
                              material='合板', qty=npins, spare=npins, geom=box(0, 0, P['pin'], P['pin']),
                              engrave=[], texts=[]))
    return edits, new_parts, touched


# ---------------------------------------------------------------------------
# 合成（只套本模組的 edits，給檢查用；正式合成由 compose.py 負責）
# ---------------------------------------------------------------------------
def apply_local(part, edits) -> Polygon | MultiPolygon:
    """把本模組對某零件的 edits 套到 Part.geom（頁座標）：delete_cut → union → subtract。"""
    g = part.geom
    mine = [e for e in edits if e['part'] == part.id]
    dels = [e['src'] for e in mine if e['op'] == 'delete_cut']
    if dels:
        boxes = [parse_path(part.cut_d[part.cut_src.index(s)]).bbox() for s in dels]
        keep = []
        for r in g.interiors:
            b = Polygon(r).bounds
            if any(abs(b[0] - x0) < 0.05 and abs(b[2] - x1) < 0.05 and abs(b[1] - y0) < 0.05 and abs(b[3] - y1) < 0.05
                   for x0, x1, y0, y1 in boxes):
                continue
            keep.append(r)
        g = Polygon(g.exterior, keep)
    for e in mine:
        if e['op'] == 'union':
            g = g.union(e['geom'])
    for e in mine:
        if e['op'] == 'subtract':
            g = g.difference(e['geom'])
    return g


def _pieces(g, min_area=0.01):
    return [p for p in getattr(g, 'geoms', [g]) if p.area >= min_area]


# ---------------------------------------------------------------------------
# 檢查（port checks.py 能由幾何算的部分）
# ---------------------------------------------------------------------------
def _r(x, d=2):
    if x is None:
        return None
    if isinstance(x, (list, tuple)):
        return [_r(v, d) for v in x]
    return round(float(x), d)


def _fall_zone(B, R, c, boxes):
    """d2 的「緊」落幣區：U∈開口、W'∈[0,硬幣直徑]、V 從唇到出口平面；模組（W'>0）侵入體積與深度。"""
    U0, U1 = B.op_U(c)
    Dm = COIN_D[c]
    O = R['O']
    lipV = lambda U: float(B.railV(U)) - B.LIP[c] / B.CA
    below_lip = Polygon([(U0, lipV(U0)), (U1, lipV(U1)), (U1, 300), (U0, 300)])
    vol = depth = 0.0
    for w in np.arange(0.125, Dm, 0.25):
        zone = below_lip.intersection(box(U0, -10, U1, float(B.exitV(w))))
        polys = [R['sn'].rect(b[1], b[2], b[3], b[4]) for b in boxes if b[5] < w < b[6]]
        if not polys or zone.is_empty:
            continue
        g = unary_union(polys).intersection(zone)
        if not g.is_empty:
            vol += g.area * 0.25
            b = g.bounds
            depth = max(depth, (b[2] - U0) if U0 > O[0] else (U1 - b[0]))
    return vol, depth


def _checks(M: dict, cat: dict, edits: list) -> tuple[list, dict]:
    """回傳 (checks, vals)。vals＝{(站或 'all', 參考鍵): 值}，自我測試拿來和 checks.json 比。"""
    P, D, B, S, X = M['P'], M['D'], M['B'], M['S'], M['X']
    dels = M['deleted']
    mw = P['min_web']
    checks, vals = [], {}

    def chk(scope, key, name, value, ok, expected, note=''):
        vals[(scope, key)] = value
        checks.append(dict(name=(f'{scope} ' if scope != 'all' else '') + name, ok=bool(ok),
                           value=value, expected=expected, note=note))

    back = lambda Bx: [b for b in Bx if b[6] > 0]
    others24 = [h for h in B.H24 if h.area < 300 and not _is_deleted(h, dels, '#24')]
    others26 = [h for h in B.H26 if h.area < 300 and not _is_deleted(h, dels, '#26')]
    ring = B.TURN.buffer(TURN_R_RING, 128)
    for k, R in S.items():
        up, dn = R['up'], R['dn']
        O, sn = R['O'], R['sn']
        win, lh, w24 = R['win'], R['lh'], R['win_in24']
        Ub, Vb = R['beam_UV']
        vals[(k, 'beam_UV')] = _r([Ub, Vb], 3)
        chk(k, 'beam_to_up_open_end_U', '光束離上游開口終點（U）', _r(Ub - B.op_U(up)[1]), Ub - B.op_U(up)[1] > 0, '>0')
        chk(k, 'beam_to_dn_open_start_U', '光束離下游開口起點（U）', _r(B.op_U(dn)[0] - Ub), B.op_U(dn)[0] - Ub > 0, '>0')
        v = min(win.distance(B.OPS[c]) for c in B.OPS)
        chk(k, 'win_to_openings', '窗到最近分幣開口', _r(v), v >= mw, f'≥{mw}', '開口零改動')
        v = win.distance(B.SLOT24)
        chk(k, 'win_to_slot24', '窗到斜槽（軌道）', _r(v), v >= mw, f'≥{mw}', '軌道零改動')
        v1, v2 = lh.distance(B.OPS[up]), lh.distance(B.OPS[dn])
        vals[(k, 'lh_to_open_up')], vals[(k, 'lh_to_open_dn')] = _r(v1), _r(v2)
        chk(k, 'lh_to_open', '光孔到上游／下游開口', [_r(v1), _r(v2)], min(v1, v2) >= mw, f'≥{mw}')
        v = lh.distance(win)
        chk(k, 'lh_to_win', '光孔到窗', _r(v), v >= mw, f'≥{mw}')
        vals[(k, 'lh_n_range')] = _r([P['h'] - P['lh_n'] / 2, P['h'] + P['lh_n'] / 2])
        a1, a2 = -D['n_strip'], -D['n_shoulder']
        vals[(k, 'strip24_body')], vals[(k, 'strip24_wing')] = _r(a1), _r(a2)
        chk(k, 'strip24', '#24 保留條厚（光耦段／肩部）', [_r(a1), _r(a2)], min(a1, a2) >= mw, f'≥{mw}',
            '估 31～60 N（spec d-4）')
        a1, a2 = B.LIP[up] - D['n_strip'], B.LIP[up] - D['n_shoulder']
        vals[(k, 'strip26_body')], vals[(k, 'strip26_wing')] = _r(a1), _r(a2)
        chk(k, 'strip26', '#26 窗頂到開口唇（光耦段／肩部）', [_r(a1), _r(a2)], min(a1, a2) >= mw, f'≥{mw}')
        vals[(k, 'breaks_edge')] = R['breaks_edge']
        if not R['breaks_edge']:
            v = B.O24.exterior.distance(w24)
            chk(k, 'win_to_24_bottom', '窗底到 #24 下緣', _r(v), v >= mw, f'≥{mw}（否則改開底）')
        else:
            chk(k, 'win_to_24_bottom', '窗破出 #24 下緣 → 開底缺口', '開底', True, '不留楔形碎片',
                '#24、#26 新外形＝外形.difference(窗)')
        v1 = min(w24.distance(h) for h in others24)
        v2 = min(R['win_in26'].distance(h) for h in others26)
        vals[(k, 'win_to_other_holes24')], vals[(k, 'win_to_other_holes26')] = _r(v1), _r(v2)
        chk(k, 'win_to_other_holes', '窗到其他保留孔（#24／#26）', [_r(v1), _r(v2)], min(v1, v2) >= mw, f'≥{mw}')
        hits = [ENG_NAME.get(s, s) for s, b in B.ENG24.items() if b.buffer(1.0).intersects(unary_union([w24, R['c1']]))]
        vals[(k, 'engrave_hits')] = hits
        v = R['c1'].distance(ring)
        chk(k, 'c1_to_turntable_ring', 'C1 到轉盤圍邊', _r(v), v >= P['turn_clear'] - 1e-6, f"≥{P['turn_clear']}")
        fin, low = R['mod_final'], R['mod_low']
        fa = [b for b in fin if b[0] == '前臂'][0]
        ra = [b for b in fin if b[0] == '後臂'][0]
        v1, v2 = -6.0 - fa[6], -6.0 - (fa[6] - P['c_stop'])
        vals[(k, 'front_arm_to_24front_rest')], vals[(k, 'front_arm_to_24front_fwd')] = _r(v1), _r(v2)
        chk(k, 'front_arm', '前臂內面到 #24 前面（靜止／推到最前）', [_r(v1), _r(v2)], min(v1, v2) > 0, '>0')
        v1, v2 = ra[5], ra[5] - P['c_stop']
        vals[(k, 'rear_arm_inner_to_26back_rest')], vals[(k, 'rear_arm_inner_to_26back_fwd')] = _r(v1), _r(v2)
        chk(k, 'rear_arm', '後臂內面到 #26 背面（靜止／推到最前）', [_r(v1), _r(v2)], min(v1, v2) >= 0, '≥0')
        mmax = max(b[6] for b in fin if b[0] != '排針＋杜邦頭')
        vals[(k, 'module_max_W')] = _r(mmax)
        chk(k, 'module_to_37', "模組最深 W' 到 #37 內面", _r(B.W37 - mmax), B.W37 - mmax > 0, '>0')
        vals[(k, 'slot_bottom_to_strip')] = _r(D['n_strip'] - D['n_sb'])
        v = D['n_strip'] - (D['n_arm_top'] - D['slide'])
        chk(k, 'arm_top_low_to_strip', '低位臂頂到保留條底（推入時）', _r(v), v > 0, '>0')
        # 窄段下游壁（光束沿軌定位面，spec b-1、a-1）：在 #24／#26 板厚內只有本體底座（n_pcb_top～n_sb），
        # 本體貼得到的壁高＝n_sb − n_shoulder（窗上量到的壁高 n_strip − n_shoulder 還多 g_strip，本體碰不到那段）。
        # 零件高 comp_h、槽深 slot_d、臂高 arm_top 實量偏差合計 0.7 就會讓這面壁消失，本體改靠 PCB 邊定位。
        wall = D['n_sb'] - D['n_shoulder']
        half_s = P['lh_u'] / 2 / B.T[0]                     # #26 光孔沿 s 的半寬
        ap = float(PR.MODULE.get('aperture', 1.0)) / 2
        m_ok, m_lost = half_s - ap, half_s - ap - P['c']
        chk(k, 'body_locate_wall', '窄段下游壁（光束定位面）本體貼得到的高度', _r(wall), wall >= P['locate_wall_min'] - 1e-9,
            f"≥{P['locate_wall_min']}",
            f"＝槽底 n_sb − 肩部 n_shoulder（comp_h、slot_d、arm_top 決定）。不足時本體貼不到窄段壁，改靠 PCB 邊定位，"
            f"光束沿 s 可偏 ±{P['c']:g}，#26 光孔餘量（扣光窗半寬 {ap:g}）從 {m_ok:.2f} 降到 {m_lost:.2f}；"
            '補救：確認實量值、改用矮零件的模組，或重新設計窗（寬段只在高零件那側開到肩部，要問使用者）')
        # 鎖塊塞法（assembly-1）：P1 頂住凸塊在光耦正下方（s −a～a），比 P1 其餘頂面高 n_pcb_bot−n_wing。
        # 從前方直接水平推入時，凸塊要從前臂底下的焊腳（n_bump～n_pcb_bot）穿過 → 會撞；
        # 所以改成 P1 先貼 #24 正面（在前臂內面與 #24 前面之間的縫裡）往上抬到位，再往後推 t。
        gap_w = -6.0 - fa[6]                                 # 前臂內面到 #24 前面（靜止）
        hit = D['n_pcb_bot'] - D['n_bump'] - P['g_strip']    # 水平推入：凸塊頂和前臂焊腳底在 n 的重疊（模組頂到最高）
        c1_pcb = sn.to_sn(R['c1']).intersection(box(-D['pcb_up'], -200.0, D['pcb_dn'], 200.0))   # PCB 下方那段 C1
        c1_top = D['n_bump'] - c1_pcb.bounds[3]              # 抬到位時 C1 頂到焊點底（C1 從前臂、排針底下經過）
        ok_ins = gap_w - P['t'] >= P['insert_gap_min'] - 1e-9 and c1_top >= P['insert_gap_min'] - 1e-9
        chk(k, 'lock_insert_path', '鎖塊塞法（P1 貼 #24 正面往上抬、再往後推 3）：縫寬 − P1 厚／C1 頂到焊點底',
            [_r(gap_w - P['t']), _r(c1_top)], ok_ins, f"≥{P['insert_gap_min']}",
            f"縫＝前臂內面到 #24 前面 {gap_w:.1f}（模組被導角帶前時更寬）")
        chk(k, 'lock_insert_direct', '從前方直接水平推入時，P1 凸塊和前臂底下焊腳在 n 的重疊（資訊）', _r(hit), True,
            '資訊（>0＝會撞，不可這樣塞）', '已把組裝說明改成「貼 #24 正面往上抬、再往後推」；焊點高 back_h ≤ g_strip 時才能直接推')
        # 後臂伸出立柱（UV 正投影，唇以上）
        Ua, Ub2 = R['bar']
        arm_uv = sn.rect(ra[1], ra[2], B.LIP[up], ra[4])
        prot = arm_uv.difference(box(Ua, 0, Ub2, 200))
        pu = prot.intersection(box(0, 0, Ua, 200))
        pd = prot.intersection(box(Ub2, 0, 300, 200))
        vals[(k, 'rear_arm_outside_bar_mm2')] = dict(
            up=_r(pu.area), dn=_r(pd.area), up_max=_r(Ua - pu.bounds[0]) if not pu.is_empty else 0,
            dn_max=_r(pd.bounds[2] - Ub2) if not pd.is_empty else 0)
        chk(k, 'rear_arm_outside_bar', '後臂伸出立柱陰影 mm²（上游／下游，資訊）',
            [vals[(k, 'rear_arm_outside_bar_mm2')]['up'], vals[(k, 'rear_arm_outside_bar_mm2')]['dn']],
            True, '資訊', 'spec d-5、R3：下游幣翻倒時可能擦到後臂頂角')
        # 落幣區侵入（d2 緊模型）
        fz = {}
        for cc in (up, dn):
            vol, dep = _fall_zone(B, R, cc, back(fin))
            fz[cc + '元'] = dict(vol_mm3=_r(vol, 0), depth_U=_r(dep))
        vals[(k, 'fall_zone_intrusion')] = fz
        chk(k, 'fall_zone', '翼侵入落幣區 mm³（資訊）', {kk: vv['vol_mm3'] for kk, vv in fz.items()}, True,
            '資訊', 'R1：試切 T3 驗收（每格 100 枚 0 卡幣）')
        # 翼在 #26 後方的包絡（給 S1 協調）
        wenv = unary_union([sn.rect(b[1], b[2], b[3], b[4]) for b in back(fin) if b[0].startswith('PCB')])
        Ud0, Ud1 = R['divU']
        wu = wenv.intersection(box(0, 0, Ud0, 200))
        wd = wenv.intersection(box(Ud1, 0, 300, 200))
        env = lambda g, into: None if g.is_empty else dict(U=_r([g.bounds[0], g.bounds[2]]), V=_r([g.bounds[1], g.bounds[3]]),
                                                         W=_r([0, D['W_pcb'][1]]), U_into=_r(into))
        vals[(k, 'wing_env_up')] = env(wu, Ud0 - wu.bounds[0] if not wu.is_empty else 0)
        vals[(k, 'wing_env_dn')] = env(wd, wd.bounds[2] - Ud1 if not wd.is_empty else 0)
        vals[(k, 'wing_top_below_lip_n')] = _r(B.LIP[up] - D['n_comp'])

        # 出口平面（W'>0 部分）
        def exit_clear(Bx):
            m = 1e9
            for b in back(Bx):
                if b[0] == '排針＋杜邦頭':
                    continue
                g = sn.rect(b[1], b[2], b[3], b[4])
                for w in np.linspace(max(b[5], 0), b[6], 6):
                    m = min(m, float(B.exitV(w)) - g.bounds[3])
            return m
        ef, el = exit_clear(fin), exit_clear(low)
        chk(k, 'exit_plane_clear_final', '最終位置離滑道出口平面', _r(ef), ef >= 0, '≥0',
            '<0：PCB 伸進抽屜區（翼方向 No-Go，spec d-3）' if ef < 0 else '')
        vals[(k, 'exit_plane_clear_low')] = _r(el)
        R['drawers_low'] = _drawers_below_exit(B, R, low) if el < 0 else []
        chk(k, 'exit_plane_clear_low', '低位（安裝時）離出口平面（資訊）', _r(el), True, '資訊',
            ('<0：安裝／拆換前要先抽出 ' + '、'.join(c + ' 元' for c in R['drawers_low']) + '抽屜') if el < 0 else '')
        front_parts = [sn.rect(b[1], b[2], b[3], b[4]) for b in fin if b[5] < -6.0] + [R['c1']]
        vmax = max(g.bounds[3] for g in front_parts)
        chk(k, 'front_parts_max_V', '#24 前方零件最大 V', _r(vmax), vmax <= P['v_drawer'] + 1e-6, f"≤{P['v_drawer']}")
        zworld = lambda V, W: -0.8660254 * np.asarray(V) - 0.5 * np.asarray(W)
        z_corner = zworld(98.0, -6.0)
        zmin = min(min(zworld(np.array(g.exterior.coords)[:, 1], wv)) for g, wv in
                   [(sn.rect(b[1], b[2], b[3], b[4]), b[6] if b[6] < -6 else -6) for b in fin if b[5] < -6.0] + [(R['c1'], -6.0)])
        vals[(k, 'front_parts_above_24corner_z')] = _r(zmin - z_corner)
        allfin = unary_union([sn.rect(b[1], b[2], b[3], b[4]) for b in fin])
        v1, v2 = allfin.bounds[0] - B.CAB13_U[1], allfin.bounds[0] - MOTOR_U[1]
        vals[(k, 'to_13_U')], vals[(k, 'to_motor_U')] = _r(v1), _r(v2)
        chk(k, 'to_13_U', '模組最右 U 到 #13（S1 牆）', _r(v1), v1 > 0, '>0')
        hb = [b for b in fin if b[0] == '排針＋杜邦頭'][0]
        vals[(k, 'header_W')] = _r([hb[5], hb[6]])
        hin = bool(hb[6] < -6.0 - 0.5)
        chk(k, 'header_in_front_of_24', '排針＋杜邦頭在 #24 前方', hin, hin, 'True',
            f"排針＋杜邦頭要在 PCB 前緣 {(-6.0 - 0.5) - D['W_pcb'][0]:.1f} mm 以內（Go/No-Go）")
        v = sn.rect(hb[1], hb[2], hb[3], hb[4]).distance(ring)
        chk(k, 'header_to_turntable', '排針到轉盤圍邊', _r(v), v > 0, '>0')
        # 隔板
        chk(k, 'divider_pieces', f"{R['div']} v2 切後件數", R['div_pieces'], R['div_pieces'] == 1, '1')
        sc = R['stop_contact_V']
        chk(k, 'stop_contact', f"{R['div']} 擋面接觸長（V）", _r(list(sc)), sc[1] - sc[0] > 2.0, '>2')
        vals[(k, 'divider')] = dict(pid=R['div'], pieces=R['div_pieces'], tabs=R['tabs'],
                                    notch_bounds=_r(list(R['notch'].bounds)), open_bottom=R['notch_open_bottom'],
                                    stop_contact_V=_r(list(sc)), area_removed=_r(R['notch'].area, 1))
        # 新零件
        vals[(k, 'P1_bounds_UV')], vals[(k, 'P1_area')] = _r(list(R['p1'].bounds)), _r(R['p1'].area, 1)
        vals[(k, 'C1_bounds_UV')], vals[(k, 'C1_area')] = _r(list(R['c1'].bounds)), _r(R['c1'].area, 1)
        inside = win.buffer(1e-6).contains(R['p1'])
        chk(k, 'p1_in_window', 'P1 在窗內（兩側繪製間隙）', inside, inside, 'True')
        pins = []
        for p in R['pins']:
            if p is None:
                pins.append(None)
                continue
            d1, d2, d3 = p['hole'].distance(B.SLOT24), B.O24.exterior.distance(p['hole']), p['hole'].distance(win)
            pins.append(dict(side=p['side'], s=_r(p['s']), n=_r(p['n']), n_ok=_r(list(p['n_ok'])),
                             center_UV=_r(list(p['hole'].centroid.coords[0])), to_slot=_r(d1), to_24_edge=_r(d2), to_win=_r(d3)))
            chk(k, f"pin_{p['side']}", f"插銷孔（{p['side']}）到斜槽／外緣／窗", [_r(d1), _r(d2), _r(d3)],
                min(d1, d2, d3) >= P['pin_web'], f"≥{P['pin_web']}")
        vals[(k, 'pins')] = pins
        if R['breaks_edge']:
            ok = len(R['pins']) == 2 and all(R['pins'])
            chk(k, 'pins_found', '開底站兩側插銷孔都找到', ok, ok, 'True')
    # ---- 全域：#6 新榫槽、排線孔 ----
    s6 = X['slot26_tab6']
    v1 = min(s6.distance(B.OPS[c]) for c in B.OPS)
    v2 = min(s6.distance(h) for h in B.H26 if h.area < 300 and h.distance(s6) > 0)
    ins = bool(B.O26.buffer(-2).contains(s6))
    vals[('all', 'slot26_tab6')] = dict(UV=_r(list(s6.bounds)), to_openings=_r(v1), to_other=_r(v2), inside26=ins)
    chk('all', 'slot26_tab6_chk', '#6 新小榫槽：到開口／其他孔、在 #26 內縮 2 內', [_r(v1), _r(v2), ins],
        min(v1, v2) >= mw and ins, f'≥{mw}、True')
    ch = X['cable_hole']
    cv = dict(UV=_r(list(ch.bounds)), in24=bool(B.O24.buffer(-2.5).contains(ch)), in26=bool(B.O26.buffer(-2.5).contains(ch)),
              to_holes24=_r(min(ch.distance(h) for h in B.H24)), to_holes26=_r(min(ch.distance(h) for h in B.H26)),
              to_24_edge=_r(B.O24.exterior.distance(ch)), to_26_edge=_r(B.O26.exterior.distance(ch)),
              to_turntable=_r(ch.distance(ring)), to_13=_r(B.CAB13_U[0] - ch.bounds[2]), to_motor=_r(ch.bounds[0] - MOTOR_U[1]))
    vals[('all', 'cable_hole')] = cv
    chk('all', 'cable_hole_chk', '排線孔：到孔（#24／#26）、到外緣（#24／#26）、到 #13',
        [cv['to_holes24'], cv['to_holes26'], cv['to_24_edge'], cv['to_26_edge'], cv['to_13']],
        cv['in24'] and cv['in26'] and min(cv['to_holes24'], cv['to_holes26'], cv['to_24_edge'], cv['to_26_edge']) >= mw
        and cv['to_13'] > 0 and cv['to_turntable'] > 0, f'≥{mw}、>0')
    # ---- 刪孔都找到 ----
    bad = [d for d in dels if d['hole'] is None or d.get('src') is None]
    chk('all', 'deleted_holes', '被刪榫對應的原始孔都找到（delete_cut）', f"{len(dels) - len(bad)}/{len(dels)}",
        not bad, '全部', '；'.join(f"{d['part']} {d['station']} V{d['tab_V']} 找到 {d['n_found']} 個" for d in bad))
    # ---- 雕刻搬移 ----
    for src, mv in M['moves'].items():
        ok = mv['new'] is not None and mv['clear'] >= P['engrave_clear'] - 1e-6
        chk('all', f'engrave_{src}', f"雕刻{mv['name']}搬移後離切割、孔、其他雕刻",
            None if mv['new'] is None else _r(mv['clear']), ok, f"≥{P['engrave_clear']}",
            '只用原始切割＋本模組的切割算；整合時要用最終切割（含電子盒的顯示窗、Logo 新位置）重算')
    # ---- 合成後 1 塊、新切割互距 ----
    for pid in ('#24', '#26', '#5', '#6', '#7'):
        g = apply_local(cat[pid], edits)
        n = len(_pieces(g))
        chk('all', f'pieces_{pid}', f'{pid} 套用本模組修改後件數', n, n == 1, '1', '只含本模組；compose 會再合其他子系統')
    for pid, items in (('#24', [(f'{k} 窗', R['win_in24']) for k, R in S.items()] +
                        [(f"{k} 插銷孔{p['side']}", p['hole']) for k, R in S.items() for p in R['pins'] if p] +
                        [('排線孔', X['cable_hole'])]),
                       ('#26', [(f'{k} 窗', R['win_in26']) for k, R in S.items()] +
                        [(f'{k} 光孔', R['lh']) for k, R in S.items()] +
                        [('#6 新槽', X['slot26_tab6']), ('排線孔', X['cable_hole'])])):
        dmin, pair = 1e9, ''
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                dd = items[i][1].distance(items[j][1])
                if dd < dmin:
                    dmin, pair = dd, f'{items[i][0]}↔{items[j][0]}'
        chk('all', f'new_cut_gap_{pid}', f'{pid} 新切割之間最小距（{pair}）', _r(dmin), dmin >= mw, f'≥{mw}')
    return checks, vals


def _new_part_checks(new_parts, P) -> list:
    """新零件：外形有效且 1 塊；雕刻線離切割邊 ≥ engrave_edge；字墨外框離切割線 ≥ TEXT_CLEAR、
    離雕刻線（P1 框、插銷方塊、▲）≥ ENGRAVE_GAP。"""
    out = []
    for p in new_parts:
        g = p['geom']
        ok_geom = g.is_valid and isinstance(g, Polygon)
        inner = g.buffer(-P['engrave_edge'] + 0.01)
        bad = 0
        lines = []
        for d in p['engrave']:
            for sp in parse_path(d).continuous_subpaths():
                pts = [sp.point(t) for t in np.linspace(0, 1, 50)]
                lines.append(LineString([(z.real, z.imag) for z in pts]))
                bad += sum(1 for z in pts if not inner.contains(Point(z.real, z.imag)))
        eng = unary_union(lines) if lines else None
        tx = []
        for t in p['texts']:
            ink = TP.ink_box(t['text'], t['x'], t['y'], t['size'], t.get('angle', 0.0), t.get('anchor', 'start'))
            dc = g.boundary.distance(ink) if g.contains(ink) else -1.0
            de = eng.distance(ink) if eng is not None else None
            tx.append(f"「{t['text']}」em {t['size']:g}、離切割 {dc:.2f}" + ('' if de is None else f'、離雕刻 {de:.2f}'))
            if dc < TP.TEXT_CLEAR - 1e-6 or (de is not None and de < TP.ENGRAVE_GAP - 1e-6):
                bad += 1
        out.append(dict(name=f"新零件 {p['id']}：外形 1 塊、雕刻在零件內、字離切割 ≥{TP.TEXT_CLEAR:g}、離雕刻線 ≥{TP.ENGRAVE_GAP:g}",
                        ok=bool(ok_geom and bad == 0), value=dict(valid=ok_geom, bad=bad), expected='valid、0',
                        note='；'.join(tx) or '沒有字'))
    return out


def _drawers_below_exit(B, R, Bx):
    """低位時伸到出口平面以下的部分落在哪些抽屜（抽屜＝兩片隔板／櫃側板之間）。"""
    walls = [F.frame(p).plane()[1:] for p in DRAWER_WALLS]
    below = []
    for b in Bx:
        if b[6] <= 0 or b[0] == '排針＋杜邦頭':
            continue
        g = R['sn'].rect(b[1], b[2], b[3], b[4])
        Vlim = float(B.exitV(b[6]))
        q = g.intersection(box(-10, Vlim, 300, 300))
        if not q.is_empty and q.area > 1e-3:
            below.append(q)
    if not below:
        return []
    u0, _, u1, _ = unary_union(below).bounds
    out = []
    for c, (wa, wb) in zip(COINS, zip(walls[:-1], walls[1:])):
        if u1 > wa[1] + 0.05 and u0 < wb[0] - 0.05:
            out.append(c)
    return out


# ---------------------------------------------------------------------------
# build()（INTERFACE.md）
# ---------------------------------------------------------------------------
def station_guide(M) -> str:
    """老師認站的說明（#24 正面不刻站名，使用者 2026-10-08 決定 4）：沿滑道由上游往下游（U 由小到大）
    每站的窗是第幾個、長什麼樣；原有雕刻「1」就在哪個窗旁邊也寫出來（它是 1 元開口的幣值，不是站名，
    最容易讓人把 S5 裝錯成 S10）。"""
    B, S = M['B'], M['S']
    order = sorted(S, key=lambda k: S[k]['win_in24'].centroid.x)       # U 小＝上游
    src1 = next((s for s, n in ENG_NAME.items() if n == '「1」'), None)
    g1 = None
    if src1 is not None:
        mv = M['moves'].get(src1)
        g1 = mv['new'] if mv and mv.get('new') is not None else B.ENG24.get(src1)
    near1 = None
    if g1 is not None:
        k1 = min(S, key=lambda k: g1.distance(S[k]['win_in24']))
        if g1.distance(S[k1]['win_in24']) < 10.0:
            near1 = k1
    items, nwin = [], 0
    for k in order:
        R = S[k]
        if R['breaks_edge']:
            npin = sum(1 for q in R['pins'] if q)
            desc = ('最下游、' if k == order[-1] else '') + '開到 #24 下緣的缺口' + (
                f'（兩側各有 1 個方孔，只有 {k} 的鎖塊塞得進）' if npin == 2 else '')
        else:
            nwin += 1
            desc = f'第 {nwin} 個感測窗' + ('（旁邊刻「1」）' if k == near1 else '')
        items.append(f'{desc}裝 {k}')
    same = [k for k in order if not S[k]['breaks_edge']]
    tail = ''
    if len(same) >= 2:
        tail = (f"。{'、'.join(same)} 的窗、模組、鎖塊形狀都一樣，裝反了要到 a-3 第 5 步丟硬幣才會發現"
                '（計數對調，程式的 C5≥C10≥C50 檢查會報錯）：把兩站的模組連同鎖塊對調即可')
    return ('認站：沿滑道從轉盤那端（上游）往下游數，' + '；'.join(items)
            + '。窗旁刻的數字是開口／抽屜的幣值，不是站名' + tail)


def build(cat: dict, module: dict | None = None) -> dict:
    """S5／S10／S50 滑升式感測座的修改（INTERFACE.md）。module＝暫時取代 params.MODULE（自我測試用）。"""
    return _run(cat, module)[1]


def _run(cat: dict, module: dict | None = None) -> tuple[dict, dict, dict]:
    """回傳 (內部模型 M, build() 結果, 檢查值 vals)。"""
    M = model(cat, module)
    P, D, S = M['P'], M['D'], M['S']
    edits, new_parts, touched = _edits_and_parts(M, cat)
    M['touched'] = touched
    checks, vals = _checks(M, cat, edits)
    checks += _new_part_checks(new_parts, P)
    warnings, notes = [], []

    # ---- Go/No-Go 與警告（spec d-1、d-3）----
    if P['slot_w'] < 7.5:
        warnings.append(f"No-Go：槽寬 slot_w={P['slot_w']} < 7.5（5 mm 槽寬模組不能用）")
    if P['comp_h'] > 2.3:
        warnings.append(f"翼上零件高 comp_h={P['comp_h']} > 2.3（可能有可變電阻）：要量它的 W' 位置，"
                        f"在 #24/#26 板厚（W'−6～0）或 #26 後方都要重算，可能 No-Go")
    for c in checks:
        if not c['ok']:
            warnings.append(f"檢查未過：{c['name']} = {c['value']}（應 {c['expected']}）" + (f"；{c['note']}" if c['note'] else ''))
    for k, R in S.items():
        if R['breaks_edge'] and k != 'S50':
            warnings.append(f'{k} 的窗也破出 #24 下緣（目前參數）：改成開底缺口＋兩側插銷，和 S50 同做法，請確認')
        if R['drawers_low'] and k != 'S50':
            warnings.append(f"{k} 低位離出口平面 {vals[(k, 'exit_plane_clear_low')]}：安裝／拆換前要先抽出 "
                            + '、'.join(c + ' 元' for c in R['drawers_low']) + '抽屜（組裝說明要加）')
    for d in M['deleted']:
        if d['hole'] is None:
            warnings.append(f"{d['part']} 找不到 {d['station']} 被刪榫（V{d['tab_V']}）對應的孔（找到 {d['n_found']} 個）")
    for src, mv in M['moves'].items():
        if mv['new'] is None:
            warnings.append(f"雕刻{mv['name']}被新切割蓋到，但找不到可搬的位置")
    for k, R in S.items():
        if R.get('div_text') is None:
            warnings.append(f"{R['div']} 放不下「{k} v2」雕刻字")
    if P['wing'] != 'up':
        warnings.append(f"MODULE['wing']='{P['wing']}'：spec d-3 名目是 'up'；S50 最終位置離出口平面 "
                        f"{vals[('S50', 'exit_plane_clear_final')]}（<0＝PCB 伸進抽屜區）")

    # ---- 說明 ----
    X = M['X']
    divtxt = {R['div']: R['div_text'] for R in S.values() if R.get('div_text')}
    t5 = divtxt.get('#5')
    s6 = X['slot26_tab6'].bounds
    v0, v1 = P['new_tab6_V']
    ch = X['cable_hole'].bounds
    ndel = {pid: sum(1 for d in M['deleted'] if d['part'] == pid and d.get('src')) for pid in ('#24', '#26')}
    guide = station_guide(M)
    notes += [
        f"S5／S10／S50 滑升式感測座（spec：laser_v2/design/crosstrack_final/spec.md）。光束高 h={P['h']}（params.BEAM_H），"
        f"翼方向 wing='{P['wing']}'；#24 保留條 {D['t_strip']:.1f}／肩部 {D['t_shoulder']:.1f}，上滑行程 {D['slide']:.1f}。",
        '模組尺寸是 params.MODULE 的暫定值；拿到實品先照 spec d-1 量（槽寬、槽深、光束離槽底、臂寬厚、臂頂離 PCB、'
        'PCB 長寬厚、本體位置與左右手性、排針位置方向、零件高、焊點高、固定耳），改 params.py 再重跑。',
        f"Go/No-Go：排針＋杜邦頭要在 PCB 沿光束方向離前緣 {(-6.0 - 0.5) - D['W_pcb'][0]:.1f} mm 以內（才在 #24 前面）；"
        'S50 的排針不可朝下；光耦本體不可有固定耳（有就要量並加寬窄段）。',
        '老師組裝（spec a-3）：換 v2 的 #7／#6／#5 → 依排線標籤把模組裝到對應的站（排線上貼 S5／S10／S50 標籤；'
        f'#24 正面不刻站名，使用者 2026-10-08 決定。{guide}）→ 每站模組兩臂朝上、排針朝自己，對準窗下半部水平推入 → 往上推約 '
        f"{D['slide']:.0f} mm，一手頂住 → 塞鎖塊：C1 拿在手上、P1 那面朝機身，先把 P1 背面貼住 #24 正面（窗的下方），"
        '沿 #24 正面往上推到 P1 頂住凸塊碰到 PCB 下面（S50 同時讓兩支插銷對準 #24 的方孔），再往後推 3 mm，讓 P1 進窗、'
        'C1 貼平 #24 → 放手，靠重力定位。不要從模組前方把鎖塊直接水平伸進去：P1 頂住凸塊在光耦正下方，水平推入時會撞到'
        f"前臂底下的光耦焊腳（n 方向重疊 {D['n_pcb_bot'] - D['n_bump'] - P['g_strip']:.1f}，模組頂到最高也一樣）。"
        'spec a-3 第 3.3 步「從前方塞進窗的下半部」照此更正。'
        '拆換（spec a-4）：先把鎖塊往前拉 3 mm 讓 P1 出窗（S50 連插銷一起），再往下拿開，模組自己落回低位。',
        '新零件的區域座標：x＝沿軌往下游、y＝往下（垂直軌道）。從雕刻面看＝從 #24 往前看，'
        '所以 C1 的雕刻面（P1 外框、插銷方塊、站名）是貼 #24 的背面；P1 照外框黏在 C1 上，頂住凸塊在上緣。'
        'S5／S10 的 P1 外框左右對稱（P1 翻面也套得進），所以 C1 下緣另刻一個 ▲，對齊頂住凸塊的位置（站名在另一端）：'
        '黏 P1 時凸塊要在 ▲ 那一端，翻面黏的話凸塊會跑到 PCB 翼和焊點底下。S50 的外框兩側不等長，不會黏反。'
        'P1 和 C1 齊平的邊（S5/S10 的上緣、S50 的上下緣）不刻線，只刻其餘邊（雕刻離切割邊 ≥0.3）。',
        '講師預組：C1-S50 的 2 支插銷黏在 C1 雕刻方塊上（先插進試切小樣的 #24 孔再壓 C1，最準）；'
        '建議每套多切 1 組 P1／C1（另備）。講師接感測器線時，在每條排線靠模組端貼站名標籤（S5／S10／S50）；'
        '盒端另貼插座標籤（例如 S5→G26，見電子盒 a-2 第 5 步）。',
        f"極小零件：插銷 PIN（{P['pin']:g}×{P['pin']:g}）每套多切 {sum(1 for R in S.values() for q in R['pins'] if q)} 個備品，"
        '排在同一份切割檔（parts.csv「備品」欄；使用者 2026-10-08 決定 3），掉進蜂巢台或弄丟時用。',
        'C1 站名：' + '、'.join(f"{k} em {R['c1_text']['size']:g}" + ('（直排）' if R['c1_text']['angle'] else '')
                               + f"、字墨離切割 {R['c1_text']['clear']:.2f}" for k, R in S.items() if R.get('c1_text'))
        + f"（要求 ≥{TP.TEXT_CLEAR:g}；離 P1 框、▲、插銷方塊 ≥{TP.ENGRAVE_GAP:g}）。所有 v2 雕刻（框線、▲、字）都是紅色 0.2 mm 線。",
        '#24 雕刻「1」「5」被窗／蓋板蓋到，用 move_engrave 移開：'
        + '；'.join(f"{mv['name']} ΔU{mv['dU']:+g} ΔV{mv['dV']:+g}（新位置 U{mv['new'].bounds[0]:.2f}～{mv['new'].bounds[2]:.2f}"
                   f"×V{mv['new'].bounds[1]:.2f}～{mv['new'].bounds[3]:.2f}）" for mv in M['moves'].values() if mv['new'] is not None)
        + f"，新位置離所有切割 ≥{P['engrave_clear']}。這是用「原始切割＋本模組的切割」算的，"
          '整合時要用最終切割（含電子盒的顯示窗、M2 孔、Logo 新位置）重算。',
        '#5：本模組刪長榫並開缺口（' + ('直通斜底邊' if S['S50']['notch_open_bottom'] else '不通底邊') + '）；'
        '電子盒還會再減前上角（電子盒規格 b-3：W\'≤2.0、V≤30.31，連上小榫一起刪），合併後只剩第二小榫＋後榫。'
        + (f"「S50 v2」雕字中心在 W'{t5['W']:.1f}、V{t5['V']:.1f}（字高 {t5['size']}），避開 W'≤{P['div_text_avoid'][1]:g}、"
           f"V≤{P['div_text_avoid'][3]:g} 那一角。" if t5 else ''),
        f"#26：本模組改窗 ×3、光孔 ×3、#6 新小榫槽、排線孔、刪 {ndel['#26']} 個孔；S1（#13R 新槽）與電子盒（L 形缺口）"
        '也會改 #26，另外 fix_26_tooth_hole() 修齒孔（compose 套用，本模組不做；該孔離本模組新切割約 15）。',
        (lambda wall: f"窄段定位壁：光束沿軌靠光耦本體貼窄段下游壁定位（spec a-1、b-1），本體貼得到的壁高＝n_sb−n_shoulder＝"
         f"{wall:.1f}（檢查要求 ≥{P['locate_wall_min']:g}；名目模組時等於 comp_h ≤2.3，與 spec d-1 Go／No-Go 相同）。"
         f"spec d-2 的「comp_h ≤2.9 時仍可行」指肩部降到和保留條同高，但那時這面壁已經消失（目前參數下 comp_h ≥"
         f"{P['comp_h'] + wall:.1f}、slot_d ≥{P['slot_d'] + wall:.1f} 或 arm_top ≤{P['arm_top'] - wall:.1f} 就會），"
         f"本體改靠 PCB 邊定位，光束沿 s 可偏 ±{P['c']:g}；實量值落在這個範圍要先問。")(D['n_sb'] - D['n_shoulder']),
        f"#6：長榫一律刪除，補一支上方小榫（W'−{P['t']:g}～0×V{v0:g}～{v1:g}，平面矩形），插 #26 新槽"
        f"（U{s6[0]:.2f}～{s6[2]:.2f}×V{s6[1]:.2f}～{s6[3]:.2f}）。",
        f"#37：本模組不改。三條感測器線走右下排線孔（#24/#26 U{ch[0]:g}～{ch[2]:g}×V{ch[1]:g}～{ch[3]:g}）→ 右側空腔 → "
        '#37 感測器線孔（由電子盒開；需在 U72.1～104.9 內 ≥10×5，電子盒規格是 U88～100×V40～46；S1 背蓋與 B1 槽不可和它重疊）。',
    ]
    for k in ('S5', 'S10', 'S50'):
        for side, key in (('上游', 'wing_env_up'), ('下游', 'wing_env_dn')):
            we = vals.get((k, key))
            if we and we['U_into'] > 1.0:
                notes.append(f"{k} 的 PCB 翼伸進{side}滑道：U{we['U'][0]}～{we['U'][1]}、V{we['V'][0]}～{we['V'][1]}、"
                             f"W'{we['W'][0]}～{we['W'][1]}" + ('（給 S1：導流件、模組、光束不可進入）' if k == 'S5' and side == '上游' else ''))
    for pid, items in touched.items():
        notes.append(f'修改範圍 {pid}（組裝座標）：' + '；'.join(items))
    lows = [f"{k}（{vals[(k, 'exit_plane_clear_low')]}；計算上伸進 " + '、'.join(c + ' 元' for c in R['drawers_low']) + '抽屜區）'
            for k, R in S.items() if R['drawers_low']]
    if lows:
        notes.append('低位（安裝時）會伸到出口平面以下的站：' + '；'.join(lows)
                     + '。spec a-3 的說明是「裝／拆 S50 前先抽出 10、50 元抽屜」（保守，兩格都抽）。')
    notes += [
        '未移植的檢查（需要模擬或外部資料）：硬幣翻倒＋落下掃掠（tip_fall_sweep）、相貼兩枚在光束高的空隙與光孔處弦長、'
        '前臂到硬幣前面（硬幣厚是估計）、排線長度估計、實品偏差敏感度（sens.py）。數字見 spec (e)、d-2。',
        '待決：光耦模組全部尺寸（照 params.MODULE 暫定值）',
        '待決：模組左右手性／翼方向（照預設 wing=\'up\'；若是 \'down\'，S50 會低於出口平面，要量抽屜側牆到滑道出口間隙或換鏡像模組）',
        '待決：試切卡幣時是否改用分離式紅外線對射（照預設：槽型模組）',
        '待決：排線走法（照預設：右下排線孔→右側空腔→#37 感測器線孔）',
        '待決：刪除 #5、#6 長榫與 #7 中段小榫、#6 補上方小榫（照預設：刪除並補）',
        '待決：裝／拆 S50 前先抽出 10、50 元抽屜（照預設：寫進老師組裝說明）',
        '待決：#5 合併後只剩 2 支榫（照預設：接受，試切 T5 確認不晃）',
    ]
    res = dict(edits=edits, new_parts=new_parts, notes=notes, warnings=warnings, checks=checks, bom=_bom(P, S),
               station_guide=guide)
    return M, res, vals


def _bom(P, S) -> list[dict]:
    """採購／備品清單（INTERFACE.md 的 bom；export 合併成 report.md「材料與採購」）。數量是每套。"""
    n = len(S)
    ks = '／'.join(S)
    npin = sum(1 for R in S.values() for q in R['pins'] if q)
    return [
        dict(cat='電子', item='槽型光耦模組（LM393，10 mm 槽寬）', qty=n, unit='個', who='講師預組',
             note=f'{ks} 各 1；先照 spec d-1 量（Go／No-Go），3.3 V 測試、插 3P 線、排針根部點熱熔膠', src='crosstrack a-2'),
        dict(cat='耗材', item='PI 膠帶或電工膠帶（厚 ≤0.15）', qty=None, unit='少量', who='講師預組',
             note='包 PCB 翼的零件面，讓落下的硬幣碰到平滑面；不可用 0.5 mm PET 片（會吃掉 0.3 的零件餘隙）', src='crosstrack a-2 第 4 步'),
        dict(cat='備品（不在切割檔）', item='光耦模組（備用）', qty=1, unit='個', who='講師',
             note='spec a-2 第 6 步「另備 1 組模組與鎖塊」', src='crosstrack a-2'),
        dict(cat='耗材', item=f'排線標籤貼紙 {ks}（模組端）', qty=n, unit='張', who='講師預組',
             note=f'每條感測器排線靠模組端貼一張（寫 {"、".join(S)}）；老師依排線標籤把模組裝到對應的站'
                  '（#24 正面不刻站名；認站方法見六、crosstrack「老師組裝」）。盒端標籤（例如 S5→G26）另列在電子盒',
             src='使用者 2026-10-08 決定 4'),
        dict(cat='備品（不在切割檔）', item=f'鎖塊組（P1＋C1：{ks} 各 1）', qty=1, unit='組',
             who='講師', note='spec (c)「另建議每套多附 1 組」；目前切割檔沒有排，要的話把同一份切割檔的新零件多切一份'
                              + (f'（插銷 PIN 的備品 ×{npin} 已排進切割檔，見「備品已排進切割檔」）' if npin else ''),
             src='crosstrack (c)'),
        dict(cat='備品（不在切割檔）', item='#24、#26（v2，開窗後較弱）', qty=None, per10='各 2 片', unit='片', who='講師',
             note='spec R4：每 10 套多切 2 片；發料時 #24 平放、拿取時避免扳', src='crosstrack R4'),
    ]


# ---------------------------------------------------------------------------
# 自我測試：三種翼向和 design/ 的 geometry json 比對
# ---------------------------------------------------------------------------
def _poly(pts):
    p = Polygon(pts)
    return p if p.is_valid else p.buffer(0)


def _largest(g):
    return max(getattr(g, 'geoms', [g]), key=lambda q: q.area)


def _cmp(a, b) -> tuple[float, float]:
    """(Hausdorff 距離, 對稱差面積)；只比外框（JSON 只存外框）。"""
    a, b = Polygon(_largest(a).exterior), Polygon(_largest(b).exterior)
    hd = shapely.hausdorff_distance(a.exterior, b.exterior, densify=0.1)
    return float(hd), float(a.symmetric_difference(b).area)


SPEC_MODULE_KEYS = {'slot_w': 'slot_w', 'slot_d': 'slot_d', 'beam_sb': 'beam_sb', 'arm_t': 'arm_t', 'arm_w': 'arm_w',
                    'arm_top': 'arm_top', 'pcb_L': 'pcb_L', 'pcb_W': 'pcb_W', 'pcb_t': 'pcb_t', 'pcb_e': 'body_e',
                    'comp_h': 'comp_h', 'bump_h': 'back_h', 'hdr_len': 'hdr_len', 'hdr_up': 'hdr_up'}   # spec 名 → MODULE 鍵


def spec_module(wing: str = 'up') -> tuple[dict, dict]:
    """crosstrack_final 的名目模組尺寸（geometry_final.json 的 params）→ (MODULE 格式, 和 params.MODULE 不同的鍵)。

    2026-10-08 使用者把 params.MODULE back_h 改成 2.0（S1 規格名目、較保守）；crosstrack 規格名目 bump_h 是 1.5，
    所以和 json 比對時用規格名目，params 實值另外跑檢查（selftest_params）。"""
    J = json.loads((DESIGN_DIR / JSON_BY_WING[wing]).read_text(encoding='utf-8'))['params']
    mod = dict(PR.MODULE)
    diff = {}
    for sk, mk in SPEC_MODULE_KEYS.items():
        if sk in J and mod.get(mk) != J[sk]:
            diff[mk] = (mod.get(mk), J[sk])
            mod[mk] = J[sk]
    mod['wing'] = wing
    for sk, cur in (('h', PR.BEAM_H), ('c', PR.C_SENSOR), ('t', PR.T_PLY)):
        if sk in J and abs(J[sk] - cur) > 1e-9:
            diff[sk] = (cur, J[sk])       # params 的共用值和規格不同（只列出，不覆寫）
    return mod, diff


def selftest(cat: dict | None = None, wings=('up', 'down', 'center'), log=print) -> dict:
    """三種翼向：規格名目模組尺寸下 build() 的幾何 vs geometry_final*.json（Hausdorff ≤0.01 mm），檢查值 vs checks.json。"""
    if cat is None:
        from .catalog import load_catalog
        cat = load_catalog()
    ref_checks = json.loads((DESIGN_DIR / 'checks.json').read_text(encoding='utf-8'))
    summary = {}
    for wing in wings:
        J = json.loads((DESIGN_DIR / JSON_BY_WING[wing]).read_text(encoding='utf-8'))
        mod, mdiff = spec_module(wing)
        if wing == wings[0]:
            log('規格名目 vs params.MODULE 不同的鍵（比對時用規格名目）：'
                + ('、'.join(f'{k}＝{a}（規格 {b}）' for k, (a, b) in mdiff.items()) or '沒有'))
        M, res, vals = _run(cat, mod)
        rows = []   # (項目, hausdorff, 對稱差面積)
        bad = []

        def rec(name, a, b):
            hd, sd = _cmp(a, b)
            rows.append((name, hd, sd))

        def num(name, mine, ref, tol=0.011):
            ok = mine == ref if not isinstance(ref, (int, float)) or isinstance(ref, bool) else abs(float(mine) - float(ref)) <= tol
            if not ok:
                bad.append(f'{name}: 本模組 {mine} ／ 參考 {ref}')
            return ok
        # 推導量
        for kk, vv in J['derived'].items():
            mine = M['D'][kk]
            if isinstance(vv, list):
                for i, (x, y) in enumerate(zip(mine, vv)):
                    num(f'derived.{kk}[{i}]', x, y, 1e-6)
            else:
                num(f'derived.{kk}', mine, vv, 1e-6)
        ed = res['edits']
        # INTERFACE 格式
        for e in ed:
            if e['op'] not in ('subtract', 'union', 'delete_cut', 'translate_cut', 'move_engrave', 'add_engrave',
                               'delete_engrave', 'add_engrave_text') or e['part'] not in cat:
                bad.append(f"edit 格式：{e['op']} {e['part']}")
            if e['op'] in ('subtract', 'union') and not (e['geom'].is_valid and e['geom'].geom_type in ('Polygon', 'MultiPolygon')):
                bad.append(f"edit 幾何無效：{e['part']} {e['tag']}")
            if e['op'] == 'delete_cut' and e['src'] not in cat[e['part']].cut_src:
                bad.append(f"delete_cut src 不存在：{e['part']} {e['src']}")
            if e['op'] == 'move_engrave' and e['src'] not in cat[e['part']].engrave_src:
                bad.append(f"move_engrave src 不存在：{e['part']} {e['src']}")
        for q in res['new_parts']:
            if not {'id', 'name', 'material', 'qty', 'geom', 'engrave', 'texts'} <= set(q):
                bad.append(f"new_part 欄位不全：{q.get('id')}")
        sub = lambda pid, tag: [e for e in ed if e['part'] == pid and e['op'] == 'subtract' and e['tag'] == tag]
        for k, e in J['stations'].items():
            R = M['S'][k]
            num(f'{k}.beam_UV', float(np.hypot(*(R['beam_UV'] - np.array(e['beam_UV'])))), 0.0, 0.0011)
            num(f'{k}.O_UV', float(np.hypot(*(R['O'] - np.array(e['O_UV'])))), 0.0, 0.0011)
            num(f'{k}.breaks_edge', R['breaks_edge'], e['breaks_edge'])
            tag = f'{k} 開底缺口（階梯形）' if R['breaks_edge'] else f'{k} 階梯窗'
            rec(f'{k} #24 窗', sub('#24', tag)[0]['geom'], _poly(e['win24']['page']))
            rec(f'{k} #26 窗', sub('#26', tag)[0]['geom'], _poly(e['win26']['page']))
            rec(f'{k} #26 光孔', sub('#26', f'{k} 光孔（平行四邊形）')[0]['geom'], _poly(e['lighthole26']['page']))
            for pj in e['pins24']:
                if pj is None:
                    continue
                mine = sub('#24', f"{k} 插銷孔（{pj['side']}）")
                if not mine:
                    bad.append(f"{k} 少了插銷孔 {pj['side']}")
                    continue
                rec(f"{k} #24 插銷孔{pj['side']}", mine[0]['geom'], _poly(pj['hole']['page']))
            if len([p for p in R['pins'] if p]) != len([p for p in e['pins24'] if p]):
                bad.append(f'{k} 插銷孔數不同')
            div = e['divider']['pid']
            g = apply_local(cat[div], ed)
            rec(f'{k} {div} v2 外形', g, _poly(e['divider']['new_outline']['page']))
            mt = {tuple(t['V']): t['status'] for t in R['tabs']}
            rt = {tuple(t['V']): t['status'] for t in e['divider']['tabs']}
            num(f'{k}.tabs', mt, rt)
            num(f'{k}.notch_open_bottom', R['notch_open_bottom'], e['divider']['notch_open_bottom'])
            # 新零件：區域座標（y 往下）→ JSON 的 local（y 往上）
            for nm, loc, ref in (('P1', R['p1_local'], e['P1']), ('C1', R['c1_local'], e['C1'])):
                H = loc.bounds[3]
                up_ = affinity.affine_transform(loc, [1, 0, 0, -1, 0, H])
                rec(f'{k} {nm}（區域座標）', up_, _poly(ref['local']))
            # P1 在 C1 上的偏移、插銷在 C1 上的位置（JSON：左下角，y 往上）
            Hc = R['c1_local'].bounds[3]
            pb = R['p1_on_c1'].bounds
            num(f'{k}.P1_on_C1_offset', float(np.hypot(pb[0] - e['P1_on_C1_offset'][0], (Hc - pb[3]) - e['P1_on_C1_offset'][1])), 0.0, 0.0011)
            if 'pins_on_C1' in e:
                for q, ref in zip(R['pin_sq'], e['pins_on_C1']):
                    b = q.bounds
                    num(f'{k}.pins_on_C1', float(np.hypot(b[0] - ref[0], (Hc - b[3]) - ref[1])), 0.0, 0.0011)
        Pj = J['parts']
        rec('#26 #6 新槽', sub('#26', '#6 新小榫槽')[0]['geom'], _poly(Pj['#26_slot_tab6']['page']))
        rec('#24 排線孔', sub('#24', '感測器排線孔（右下）')[0]['geom'], _poly(Pj['cable_hole_24']['page']))
        rec('#26 排線孔', sub('#26', '感測器排線孔（右下）')[0]['geom'], _poly(Pj['cable_hole_26']['page']))
        # 刪孔
        mine_del = [(d['part'], d['hole'].bounds) for d in M['deleted'] if d['hole'] is not None]
        for rd in Pj['deleted_holes']:
            hit = [b for p, b in mine_del if p == rd['part'] and abs(b[0] - rd['U'][0]) < 0.1 and abs(b[2] - rd['U'][1]) < 0.1
                   and abs(b[1] - rd['V'][0]) < 0.1 and abs(b[3] - rd['V'][1]) < 0.1]
            if not hit:
                bad.append(f"刪孔 {rd['part']} U{rd['U']} V{rd['V']} 本模組沒刪")
        num('刪孔數', len(mine_del), len(Pj['deleted_holes']))
        num('delete_cut 數', len([x for x in ed if x['op'] == 'delete_cut']), len(Pj['deleted_holes']))
        # 雕刻搬移
        for src, rm in Pj['engrave_moves_24'].items():
            mm = M['moves'].get(src)
            if mm is None:
                bad.append(f'雕刻 {src} 本模組沒搬')
                continue
            num(f'雕刻 {src} dU', mm['dU'], rm['dU'], 1e-6)
            num(f'雕刻 {src} dV', mm['dV'], rm['dV'], 1e-6)
        num('雕刻搬移數', len(M['moves']), len(Pj['engrave_moves_24']))
        # 檢查值 vs checks.json（同翼向）
        RC = ref_checks[wing]
        nchk = 0
        for (scope, key), mine in vals.items():
            ref = RC['stations'][scope].get(key) if scope != 'all' else RC.get(key)
            if ref is None and key not in ('wing_env_up', 'wing_env_dn'):
                continue
            nchk += 1
            if isinstance(ref, (int, float)) and not isinstance(ref, bool):
                num(f'checks.{scope}.{key}', mine, ref, 0.011)
            elif isinstance(ref, list) and ref and all(isinstance(x, (int, float)) for x in ref):
                for x, y in zip(mine, ref):
                    num(f'checks.{scope}.{key}', x, y, 0.011)
            elif isinstance(ref, dict) and key in ('fall_zone_intrusion',):
                for cc, dd in ref.items():
                    num(f'checks.{scope}.{key}.{cc}.vol', mine[cc]['vol_mm3'], dd['vol_mm3'], 1.01)
                    num(f'checks.{scope}.{key}.{cc}.depth', mine[cc]['depth_U'], dd['depth_U'], 0.011)
            elif isinstance(ref, dict) and key == 'divider':
                for kk in ('pieces', 'open_bottom', 'notch_bounds', 'stop_contact_V', 'area_removed'):
                    if isinstance(ref[kk], list):
                        for x, y in zip(mine[kk], ref[kk]):
                            num(f'checks.{scope}.divider.{kk}', x, y, 0.011)
                    else:
                        num(f'checks.{scope}.divider.{kk}', mine[kk], ref[kk], 0.051)
            elif isinstance(ref, dict) and key in ('slot26_tab6', 'cable_hole', 'rear_arm_outside_bar_mm2',
                                                   'wing_env_up', 'wing_env_dn'):
                for kk, y in ref.items():
                    x = mine[kk]
                    if isinstance(y, list):
                        for xi, yi in zip(x, y):
                            num(f'checks.{scope}.{key}.{kk}', xi, yi, 0.011)
                    else:
                        num(f'checks.{scope}.{key}.{kk}', x, y, 0.011)
            elif key in ('wing_env_up', 'wing_env_dn'):
                num(f'checks.{scope}.{key}', mine, ref)
            elif key == 'pins':
                for x, y in zip(mine, ref):
                    if x is None or y is None:
                        num(f'checks.{scope}.pins', x, y)
                        continue
                    for kk in ('to_slot', 'to_24_edge', 'to_win', 'n'):
                        num(f'checks.{scope}.pins.{kk}', x[kk], y[kk], 0.011)
            elif key == 'engrave_hits':
                num(f'checks.{scope}.engrave_hits', sorted(mine), sorted(ref))
            elif isinstance(ref, bool):
                num(f'checks.{scope}.{key}', mine, ref)
        hd_max = max(r[1] for r in rows)
        sd_max = max(r[2] for r in rows)
        nfail = sum(1 for c in res['checks'] if not c['ok'])
        ok = hd_max <= 0.01 and not bad
        summary[wing] = dict(ok=ok, n_poly=len(rows), hausdorff_max=hd_max, symdiff_max=sd_max,
                             worst=max(rows, key=lambda r: r[1])[0], n_values=nchk, mismatches=bad,
                             checks_failed=[c['name'] for c in res['checks'] if not c['ok']], n_checks=len(res['checks']),
                             warnings=res['warnings'], rows=rows)
        log(f"[{wing}] 多邊形 {len(rows)} 個：Hausdorff 最大 {hd_max:.4f} mm（{summary[wing]['worst']}）、"
            f"對稱差面積最大 {sd_max:.4f} mm²；數值比對 {nchk} 項，不符 {len(bad)}；"
            f"checks {len(res['checks'])} 項，未過 {nfail}；{'OK' if ok else '!! 不符'}")
        for b in bad[:20]:
            log('   不符：' + b)
    return summary


def selftest_params(cat: dict | None = None, log=print) -> dict:
    """params.py 實值（目前 MODULE，含 back_h）：checks 要全過；列出和規格名目（同翼向）相比幾何變了什麼。"""
    if cat is None:
        from .catalog import load_catalog
        cat = load_catalog()
    wing = PR.MODULE['wing']
    mod_ref, mdiff = spec_module(wing)
    M1, r1, v1 = _run(cat)
    M0, r0, v0 = _run(cat, mod_ref)
    log(f"\n== params 實值（wing='{wing}'；和規格名目不同：" + ('、'.join(f'{k} {b}→{a}' for k, (a, b) in mdiff.items()) or '沒有')
        + '）==')
    bad = [c for c in r1['checks'] if not c['ok']]
    log(f"checks {len(r1['checks'])} 項，未過 {len(bad)}" + (('：' + '；'.join(c['name'] for c in bad)) if bad else '（全過）'))
    for k in ('n_bump', 'n_win_bot', 'slide', 't_strip', 't_shoulder'):
        a, b = M1['D'][k], M0['D'][k]
        if abs(a - b) > 1e-9:
            log(f'  推導量 {k}：{b:.3f} → {a:.3f}（{a - b:+.3f}）')
    diffs = []
    for e1, e0 in zip(r1['edits'], r0['edits']):
        if e1['op'] in ('subtract', 'union') and 'geom' in e1:
            hd = float(shapely.hausdorff_distance(e1['geom'], e0['geom'], densify=0.1))
            if hd > 1e-6:
                da = e1['geom'].area - e0['geom'].area
                diffs.append(f"{e1['part']} {e1['tag']}：最大差 {hd:.2f}、面積 {da:+.1f} mm²")
        elif e1['op'] == 'move_engrave' and (abs(e1['dx'] - e0['dx']) > 1e-9 or abs(e1['dy'] - e0['dy']) > 1e-9):
            diffs.append(f"{e1['part']} {e1['tag']}（規格名目 {e0['tag']}）")
    for p1, p0 in zip(r1['new_parts'], r0['new_parts']):
        b1, b0 = p1['geom'].bounds, p0['geom'].bounds
        if max(abs(x - y) for x, y in zip(b1, b0)) > 1e-6 or abs(p1['geom'].area - p0['geom'].area) > 1e-6:
            diffs.append(f"新零件 {p1['id']}：{b0[2] - b0[0]:.2f}×{b0[3] - b0[1]:.2f} → {b1[2] - b1[0]:.2f}×{b1[3] - b1[1]:.2f}、"
                         f"面積 {p1['geom'].area - p0['geom'].area:+.1f} mm²")
    for d in diffs:
        log('  ' + d)
    for k in ('S5', 'S10', 'S50'):
        for key in ('win_to_24_bottom', 'exit_plane_clear_low', 'exit_plane_clear_final', 'lock_insert_path'):
            a, b = v1.get((k, key)), v0.get((k, key))
            if a is not None and a != b:
                log(f'  {k} {key}：{b} → {a}')
    texts = {p['id']: p['texts'] for p in r1['new_parts'] if p['texts']}
    log('  新零件的字：' + '；'.join(f"{pid} 「{t['text']}」em {t['size']:g}" + (f" {t['angle']:g}°" if t['angle'] else '')
                                     for pid, ts in texts.items() for t in ts))
    return dict(ok=not bad, failed=[c['name'] for c in bad], diffs=diffs, module_diff=mdiff)


def _touched_summary(res: dict) -> dict:
    out = {}
    for e in res['edits']:
        out.setdefault(e['part'], []).append(e)
    return out


if __name__ == '__main__':
    import sys
    from .catalog import load_catalog
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    cat = load_catalog()
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    log = lambda s: (print(s), lines.append(s))
    log('== mods_crosstrack 自我測試（三種翼向 vs design/crosstrack_final/geometry_final*.json）==')
    summ = selftest(cat, log=log)
    sp = selftest_params(cat, log=log)
    res = build(cat)
    log(f"\n== 目前 params（wing='{PR.MODULE['wing']}'）==")
    log(f"edits {len(res['edits'])}、new_parts {len(res['new_parts'])}、checks {len(res['checks'])}"
        f"（未過 {sum(1 for c in res['checks'] if not c['ok'])}）、warnings {len(res['warnings'])}")
    for pid, es in _touched_summary(res).items():
        log(f'  {pid}: ' + '；'.join(f"{e['op']}「{e.get('tag', '')}」" for e in es))
    for p in res['new_parts']:
        b = p['geom'].bounds
        log(f"  新零件 {p['id']} ×{p['qty']}：{b[2] - b[0]:.2f}×{b[3] - b[1]:.2f}，面積 {p['geom'].area:.1f}，"
            f"雕刻 {len(p['engrave'])}、文字 {[t['text'] for t in p['texts']]}")
    for w in res['warnings']:
        log('  警告：' + w)
    detail = ['== 詳細 ==']
    for wing, s in summ.items():
        detail.append(f'-- {wing} --')
        for name, hd, sd in s['rows']:
            detail.append(f'  {name}: Hausdorff {hd:.5f}  對稱差 {sd:.5f}')
        for b in s['mismatches']:
            detail.append('  不符：' + b)
        for w in s['warnings']:
            detail.append('  警告：' + w)
    detail.append('-- checks（目前 params）--')
    for c in res['checks']:
        detail.append(f"  {'OK ' if c['ok'] else '!! '}{c['name']} = {c['value']}（{c['expected']}）{('  ※' + c['note']) if c['note'] else ''}")
    detail.append('-- notes --')
    detail += ['  ' + n for n in res['notes']]
    (WORK_DIR / 'selftest.txt').write_text('\n'.join(lines + [''] + detail) + '\n', encoding='utf-8')
    print(f"\n細節寫到 {WORK_DIR / 'selftest.txt'}")
    ok_all = all(s['ok'] for s in summ.values()) and sp['ok']
    print(f"\nmods_crosstrack 自我測試：{'全部通過' if ok_all else '未通過'}（規格名目三翼向 vs json："
          f"{'OK' if all(s['ok'] for s in summ.values()) else '不符'}；params 實值 checks：{'全過' if sp['ok'] else '有未過'}）")
    sys.exit(0 if ok_all else 1)

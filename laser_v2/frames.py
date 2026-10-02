"""組裝座標 (U, V, W') ↔ 零件頁座標 互換。

座標約定（沿用上一輪 chute 分析，並用幾何驗證過，見 verify()）
--------------------------------------------------------------
* U ：沿機身長邊。0＝右端（轉盤側），246＝左端（從正面看，U 往左增加）。
* V ：沿傾斜面板往下。0＝面板頂，114＝#24 底邊。
* W'：深度，垂直面板往後。#26 背面＝0；#24 在 -6～-3、#26 在 -3～0、
      #37 內面＝W37_IN（預設 29.0，見下方說明）、#37 外面＝W37_IN+3。
* 機身後仰 30°（面板與水平夾 60°）。世界座標（Y 向上、Z 向後）：
      V 方向＝(Z -0.5, Y -0.866)，W' 方向＝(Z +0.866, Y -0.5)。
  所以 #12、#13 這些「櫃子」零件在 (V,W') 平面上是轉 30° 的。

零件座標
--------
* 頁座標 (x, y)：catalog.Part 的座標（原始檔該頁左上角為原點，mm）。
* z：板厚方向，0＝板子的「上面」（雷切時朝上、雕刻在這一面），3＝下面。
* 每個 Frame 是一個 4×4 仿射矩陣 T：[U, V, W', 1]ᵀ = T · [x, y, z, 1]ᵀ。
  雷切板 (x 右, y 下, z 往板內) 是右手系，(U 左, V 下, W' 往後) 是左手系，
  所以合法（不鏡像）的擺法 det(T[:3,:3]) 一定是 -1；本模組建構時會檢查。

主要 API
--------
    from laser_v2 import frames as F
    F.page_to_asm('#24', x, y, z=0)      # → (U, V, W')
    F.asm_to_page('#26', U, V, W)        # → (x, y, z)
    F.frame('#5').plane()                # → ('U', 198.376, 201.376)
    F.frame('#13').footprint(('U','V'))  # 投影到 (U,V) 的外形（shapely）
    F.frame('#13').placed(M)             # 零件被排版矩陣 M(3×3) 移動後的新 Frame
    F.verify()                           # → 驗證殘差 list[dict]

零件 ↔ 位置（兩組同形零件的分派是本模組的約定，原始檔本身不分左右）
------------------------------------------------------------------
* '#13' ＝ 右邊抽屜櫃側板，U 104.875～107.875（1 元滑道右牆位置；v2 方案 A 要改這片）
* '#21' ＝ 左邊抽屜櫃側板，U 236.125～239.125
  （#21 就是 #13 轉 180°，兩片完全同形，原始檔沒有任何可區分的特徵）
* '#31' ＝ 右端板（腳架）U 0～3；'#36' ＝ 左端板 U 243～246（兩片同形，#36＝#31 轉 180°）
* '#7' 1|5 間隔條 U 135.876～138.876；'#6' 5|10 U 165.626～168.626；'#5' 10|50 U 198.376～201.376

驗證結果（python -m laser_v2.frames）
------------------------------------
對位項目除下面標「原始檔問題」者外，最大殘差 0.275 mm（間隔條後榫 V 對 #37 槽）。
* 原始檔問題 1：#26 右側（U≈106）第 1 個 4 mm 齒孔（path131[19]）在 V85.025～88.975、
  U105.033～107.983，比 #24 同位置的孔（rect2[13]：V84.026～87.976、U104.925～107.825）
  偏 ΔV +1.000、ΔU +0.134（審查時補上 U 偏移）；左側（U≈237）與同排第 2 孔都沒有偏。
  右邊 #13 的第 1 齒（V83.98～88.03）因此只能和這個孔重疊約 3 mm。
  修法見 KNOWN_DEFECTS['26-tooth-hole'] 與 fix_26_tooth_hole()（v2 產生器套用；catalog 保持原樣）。
* 原始檔問題 2（審查時新增的檢查）：#37 下方開口是 U104.501～239.001、V82 以下，兩個內角 R2。
  抽屜櫃側板外面在 U104.875 與 239.125，所以左邊開口邊比 #21 外面窄 0.124 mm（V84～96），
  兩個 R2 內角也壓到側板頂後角，#37 底邊 V82 又和側板 30° 頂邊交疊。最大干涉深度：
  右（#13）W'30.5／31.85 處 0.13／0.55（只在 #37 外側那一半）；左（#21）W'29.15／30.5／31.85 處
  0.19／0.42／0.77（整個板厚）。實機做得出來（木材可壓、可磨），但 v2 改右櫃側板（方案 A）
  或新零件貼 #37 下緣時要留意。見 verify() 第 8 組。
* #37 內面：間隔條後肩與 #13/#21 後緣都在 W'=29.0；端板兩排槽中心距 34.68，
  比 #24 中心到 #37 中心的 35.0 少 0.32，所以端板用兩排最小平方擬合（各差 0.16）。
* 審查另以「精確截面法」（榫零件板體 ∩ 對方板厚內平面，在對方頁座標算四邊間隙）獨立重算
  25 組配對與 19 組 #24↔#26/#37 共用孔，結果與本檔一致；腳本在 scratchpad v2work/catalog_verify/。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from . import catalog as _cat

AXES = ('U', 'V', 'W')   # 'W' 代表 W'
AX = {'U': 0, 'V': 1, 'W': 2}

T_BOARD = 3.0            # 合板標稱厚度
W24 = (-6.0, -3.0)       # #24 的 W' 範圍
W26 = (-3.0, 0.0)        # #26 的 W' 範圍
W37_IN = 29.0            # #37 內面的 W'：#5/#6/#7 後肩（局部 x=35）與 #13/#21 後緣都落在 29.0；
                         # 上一輪寫 ≈28.8（由 #31 兩排槽距 34.7 推得），差 0.2～0.3
U26_OFF, V26_OFF = 40.0, 4.0     # #26 局部 (x,y) = (V-4, U-40)
V37_FLIP = 114.0                 # #37 局部 x = 114 - V（在 SVG 裡是鏡像）
DIV_V_OFF = 14.0                 # 間隔條局部 y = V - 14.0（前榫對 #24/#26 槽；上一輪寫 14.1）
DIV_W_OFF = -6.0                 # 間隔條局部 x = W' + 6
DIV_U_CENTER = {'#7': 137.376, '#6': 167.126, '#5': 199.876}   # = #24 長榫槽中心 U
CAB_U_CENTER = {'#13': 106.375, '#21': 237.625}                 # = #24 4mm 齒孔中心 U
CAB_ANGLE = 30.0                 # #13 局部座標裡，貼 #26 的鋸齒基線與 x 軸夾角
CAB_P0 = (0.0, 29.891)           # #13 局部座標裡，鋸齒基線起點（=頂邊與 #26 背面交點）
CAB_V0 = 75.003                  # 該點的 V（齒中心對 #24 齒孔中心擬合）
C12_U = 239.0                    # #12 局部 x = 239.0 - U
C12_X13 = 21.77                  # #12 局部 y 對應 #13 局部 x = y + 21.77
C12_Y13 = (4.0, 7.0)             # #12 板厚在 #13 局部 y 的範圍（#13 槽 4.05～6.95）
END_V_OFF = 4.0                  # 端板局部 y = V - 4.0
END_W_OFF = 7.99                 # 端板局部 x = W' + 7.99（兩排槽最小平方擬合）
END_U = {'#31': (0.0, 3.0), '#36': (243.0, 246.0)}

# ---------------------------------------------------------------------------
# 原始檔已知問題（catalog 照原檔輸出不改；v2 產生器依 apply 決定要不要修）
# 使用者已同意「順便修 bug」：apply=True 的項目 v2 應套用；apply=False 只記錄，改不改由產生器決定。
# ---------------------------------------------------------------------------
KNOWN_DEFECTS = {
    '26-tooth-hole': dict(
        part='#26', cut_src='path131[19]', apply=True,
        desc='#26 右側第 1 個 4 mm 齒孔（給右櫃側板 #13 第 1 齒）偏 ΔV +1.000、ΔU +0.134。'
             '應對齊 #24 rect2[13]、#26 左側 path131[18]（V）與同排 path131[26]（U）。',
        fix='fix_26_tooth_hole()：#26 頁座標平移 (dx, dy)≈(-1.000, -0.134)，'
            '修正後 V84.025～87.975、U104.899～107.849（與 path131[26] 同一欄）'),
    '37-cutout-corners': dict(
        part='#37', cut_src='path509-6[0]', apply=False,
        desc='#37 下方開口左邊 U239.001 比 #21 外面 U239.125 窄 0.124（V84～96）；兩個 R2 內角'
             '壓到 #13/#21 頂後角，#37 底邊 V82 也和側板 30° 頂邊交疊。最大干涉深度：右 0.55'
             '（只在 #37 外側一半）、左 0.77（整個板厚）。',
        fix='（可選）開口左邊移到 U≈239.4（與右側 0.37 間隙對稱）、內角改 R≤0.5 或做外凸避讓。'
            '方案 A 會改右櫃側板，右側內角 R2 也要一起看。'),
    'divider-rear-tenon': dict(
        part='#37', cut_src='path509-6', apply=False,
        desc='三片間隔條（#5/#6/#7）後榫 16.0 對 #37 槽 15.9，V 方向偏 0.22～0.27，最緊的一邊 -0.325。',
        fix='（可選）#37 三個 15.9×2.9 槽往 V 小的方向（#37 頁座標 x 變大）移 0.25；不改也組得起來。'),
    'endplate-row-spacing': dict(
        part='#31/#36', cut_src='path106/path44', apply=False,
        desc='端板兩排槽中心距 34.68，比 #24 中心到 #37 中心 35.0（W37_IN=29.0）少 0.32。',
        fix='不改；W37_IN 取 29.0（間隔條後肩、櫃側板後緣），端板兩排各差 0.16。'),
}


def fix_26_tooth_hole(part26):
    """回傳修正後的 #26 Part（只平移 path131[19] 那個齒孔，其他不動）。

    平移量由零件本身算：x（＝V 方向）對齊左側同位置的 path131[18]，y（＝U 方向）對齊
    同排第 2 孔 path131[26]。外框不變，所以 frame('#26') 仍然適用。"""
    import copy
    from svgpathtools import parse_path
    src = part26.cut_src
    i = src.index('path131[19]')
    bb = lambda k: parse_path(part26.cut_d[src.index(k)]).bbox()   # (xmin, xmax, ymin, ymax)
    cur, refx, refy = bb('path131[19]'), bb('path131[18]'), bb('path131[26]')
    dx, dy = refx[0] - cur[0], refy[2] - cur[2]
    if not (abs(dx + 1.0) < 0.02 and abs(dy + 0.134) < 0.02):
        raise RuntimeError(f'#26 齒孔偏移量和預期不同：dx={dx:.4f} dy={dy:.4f}')
    q = copy.copy(part26)
    q.cut_d = list(part26.cut_d)
    q.cut_src = list(part26.cut_src)
    q.cut_closed = list(part26.cut_closed)
    q.engrave = list(part26.engrave)
    q.engrave_src = list(part26.engrave_src)
    q.cut_d[i] = _cat.transform_d(part26.cut_d[i], _cat.translate_matrix(dx, dy))
    holes = []
    hit = 0
    for h in part26.geom.interiors:
        hb = Polygon(h).bounds
        if abs(hb[0] - cur[0]) < 0.05 and abs(hb[1] - cur[2]) < 0.05 and abs(hb[2] - cur[1]) < 0.05:
            holes.append(affinity.translate(Polygon(h), dx, dy).exterior)
            hit += 1
        else:
            holes.append(h)
    if hit != 1:
        raise RuntimeError(f'#26 geom 找到 {hit} 個符合的孔（應為 1）')
    q.geom = Polygon(part26.geom.exterior, holes)
    return q


# ---------------------------------------------------------------------------
@dataclass
class Frame:
    part: str
    desc: str
    T: np.ndarray                     # 4×4，頁座標 (x,y,z) → (U,V,W')
    thickness: float = T_BOARD
    notes: list[str] = field(default_factory=list)

    def __post_init__(self):
        det = float(np.linalg.det(self.T[:3, :3]))
        if abs(det + 1) > 1e-6:
            raise ValueError(f'{self.part} 的 Frame det={det:.6f}，不是合法擺法（應為 -1）')

    @property
    def Tinv(self) -> np.ndarray:
        return np.linalg.inv(self.T)

    def to_asm(self, x, y, z=0.0) -> np.ndarray:
        """頁座標 → (U,V,W')。x,y,z 可為純量或陣列，回傳 shape (...,3)。"""
        x, y, z = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float), np.asarray(z, float))
        P = np.stack([x, y, z, np.ones_like(x)], axis=-1)
        return (P @ self.T.T)[..., :3]

    def to_page(self, U, V, W) -> np.ndarray:
        """(U,V,W') → 頁座標 (x, y, z)。z 不在 0～厚度之間代表該點不在板內。"""
        U, V, W = np.broadcast_arrays(np.asarray(U, float), np.asarray(V, float), np.asarray(W, float))
        P = np.stack([U, V, W, np.ones_like(U)], axis=-1)
        return (P @ self.Tinv.T)[..., :3]

    def plane(self):
        """板面法線若平行某一軸，回傳 (軸名, 最小值, 最大值)；否則 None（如 #12、#13 以外的斜面）。"""
        n = self.T[:3, 2]
        k = int(np.argmax(np.abs(n)))
        if abs(abs(n[k]) - 1) > 1e-9:
            return None
        a = self.T[k, 3]
        b = a + n[k] * self.thickness
        return (AXES[k], round(float(min(a, b)), 6), round(float(max(a, b)), 6))

    def top_face_normal(self) -> np.ndarray:
        """板子上面（雕刻面）朝外的方向，以 (U,V,W') 單位向量表示。"""
        return -self.T[:3, 2] / np.linalg.norm(self.T[:3, 2])

    def placed(self, M: np.ndarray) -> 'Frame':
        """零件被 3×3 平面矩陣 M（頁座標→新頁座標）移動後，對應的新 Frame。"""
        M4 = np.eye(4)
        M4[:2, :2] = M[:2, :2]
        M4[:2, 3] = M[:2, 2]
        return Frame(self.part, self.desc, self.T @ np.linalg.inv(M4), self.thickness, list(self.notes))

    def geom_asm(self, geom, z: float = 0.0, axes=('U', 'V')):
        """把頁座標的 shapely 幾何（在板面 z 處）映到組裝座標的兩個軸上。"""
        i, j = AX[axes[0]], AX[axes[1]]
        A = self.T
        a, b, d, e = A[i, 0], A[i, 1], A[j, 0], A[j, 1]
        xo = A[i, 2] * z + A[i, 3]
        yo = A[j, 2] * z + A[j, 3]
        return affinity.affine_transform(geom, [a, b, d, e, xo, yo])

    def footprint(self, axes=('U', 'V'), geom=None):
        """板子（外形擠出厚度）投影到 axes 平面的範圍。板面平行投影面時保留孔。"""
        g = geom if geom is not None else _part_geom(self.part, self)
        i, j = AX[axes[0]], AX[axes[1]]
        s = np.array([self.T[i, 2], self.T[j, 2]]) * self.thickness
        g0 = self.geom_asm(g, 0.0, axes)
        if np.hypot(*s) < 1e-9:
            return g0
        polys = [g0, affinity.translate(g0, s[0], s[1])]
        rings = [g0.exterior] if isinstance(g0, Polygon) else [p.exterior for p in g0.geoms]
        for ring in rings:
            C = np.array(ring.coords)
            for k in range(len(C) - 1):
                a, b = C[k], C[k + 1]
                q = Polygon([a, b, b + s, a + s])
                if q.area > 1e-9:
                    polys.append(q)
        out = unary_union([p.buffer(0) for p in polys])
        return out


# ---------------------------------------------------------------------------
_PARTS = None


def _parts():
    global _PARTS
    if _PARTS is None:
        _PARTS = _cat.load_catalog()
    return _PARTS


def _part_geom(pid, fr=None):
    return _parts()[pid].geom


def _origin(pid):
    b = _parts()[pid].bbox
    return b[0], b[1]


def _make(pid, desc, R, t, local_pre=None, notes=()):
    """R、t：[U,V,W'] = R·[xl, yl, z] + t，xl,yl＝相對零件 bbox 左上角的局部座標。
    local_pre：額外的局部座標前處理（3×3），例如轉 180°。"""
    x0, y0 = _origin(pid)
    L = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1.0]])
    if local_pre is not None:
        L = local_pre @ L
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    # 把 L 擴成 4×4（作用在 x,y；z 不變）
    L4 = np.eye(4)
    L4[:2, :2] = L[:2, :2]
    L4[:2, 3] = L[:2, 2]
    return Frame(pid, desc, T @ L4, T_BOARD, list(notes))


def _rot180(pid):
    p = _parts()[pid]
    w, h = p.size
    return np.array([[-1, 0, w], [0, -1, h], [0, 0, 1.0]])


def _cab_frame(pid, uc, rot=False):
    c, s = math.cos(math.radians(CAB_ANGLE)), math.sin(math.radians(CAB_ANGLE))
    px, py = CAB_P0
    # V = V0 + (q·d)，W' = -(q·n)，q = (xl,yl) - P0，d=(c,s)，n=(-s,c)
    R = np.array([[0, 0, 1.0],
                  [c, s, 0],
                  [s, -c, 0]])
    t = np.array([uc - T_BOARD / 2,
                  CAB_V0 - (c * px + s * py),
                  -(s * px - c * py)])
    return _make(pid, '抽屜櫃側板（' + ('右，1 元滑道右牆位置' if not rot else '左') + '）', R, t,
                 local_pre=_rot180(pid) if rot else None,
                 notes=['局部 x 軸＝世界鉛直往下、局部 y 軸＝世界水平往前',
                        '#21 先轉 180° 再套與 #13 相同的對應'])


def _cab_local_to_VW(xl, yl):
    """#13 局部座標 → (V, W')（#12 會用到）。"""
    c, s = math.cos(math.radians(CAB_ANGLE)), math.sin(math.radians(CAB_ANGLE))
    qx, qy = xl - CAB_P0[0], yl - CAB_P0[1]
    return CAB_V0 + c * qx + s * qy, -(-s * qx + c * qy)


def _frame12():
    c, s = math.cos(math.radians(CAB_ANGLE)), math.sin(math.radians(CAB_ANGLE))
    # U = C12_U - xl；#13 局部 x13 = yl + C12_X13；#13 局部 y13 = C12_Y13[1] - z（τ=-1 才是合法擺法）
    # (V,W') = F13(x13, y13)
    R = np.array([[-1.0, 0, 0],
                  [0, c, -s],        # ∂V/∂z = s·∂y13/∂z = -s
                  [0, s, c]])        # ∂W'/∂z = -c·∂y13/∂z = +c
    V0, W0 = _cab_local_to_VW(C12_X13, C12_Y13[1])
    t = np.array([C12_U, V0, W0])
    return _make('#12', '抽屜櫃後板（世界鉛直）', R, t,
                 notes=['上面（雕刻 50/10/5/1）朝前、朝抽屜', 'U = 239.0 - 局部 x'])


def _build_frames():
    F = {}
    F['#24'] = _make('#24', '前面板', np.array([[0, 1, 0], [1, 0, 0], [0, 0, 1.0]]),
                     np.array([0, 0, W24[0]]), notes=['上面（雕刻）朝前'])
    F['#26'] = _make('#26', '內牆（分幣開口）', np.array([[0, 1, 0], [1, 0, 0], [0, 0, 1.0]]),
                     np.array([U26_OFF, V26_OFF, W26[0]]), notes=['上面朝前（貼 #24）'])
    F['#37'] = _make('#37', '後面板', np.array([[0, 1, 0], [-1, 0, 0], [0, 0, -1.0]]),
                     np.array([0, V37_FLIP, W37_IN + T_BOARD]), notes=['上面朝後（外側）'])
    for pid, desc in (('#7', '1|5 間隔條'), ('#6', '5|10 間隔條'), ('#5', '10|50 間隔條')):
        F[pid] = _make(pid, desc, np.array([[0, 0, 1.0], [0, 1, 0], [1, 0, 0]]),
                       np.array([DIV_U_CENTER[pid] - T_BOARD / 2, DIV_V_OFF, DIV_W_OFF]),
                       notes=['上面朝右（U 小的一側）'])
    F['#13'] = _cab_frame('#13', CAB_U_CENTER['#13'])
    F['#21'] = _cab_frame('#21', CAB_U_CENTER['#21'], rot=True)
    F['#12'] = _frame12()
    R_end = np.array([[0, 0, 1.0], [0, 1, 0], [1, 0, 0]])
    F['#31'] = _make('#31', '右端板（腳架）', R_end, np.array([END_U['#31'][0], END_V_OFF, -END_W_OFF]),
                     notes=['上面朝外（右）'])
    F['#36'] = _make('#36', '左端板（腳架）', R_end, np.array([END_U['#36'][0], END_V_OFF, -END_W_OFF]),
                     local_pre=_rot180('#36'), notes=['先轉 180°；上面朝內'])
    return F


_FRAMES = None


def frames() -> dict[str, Frame]:
    global _FRAMES
    if _FRAMES is None:
        _FRAMES = _build_frames()
    return dict(_FRAMES)


def frame(pid: str) -> Frame:
    return frames()[pid]


def page_to_asm(pid: str, x, y, z=0.0) -> np.ndarray:
    return frame(pid).to_asm(x, y, z)


def asm_to_page(pid: str, U, V, W) -> np.ndarray:
    return frame(pid).to_page(U, V, W)


def rail_V(U):
    """#24 斜槽下緣（軌道）在面板內的 V（上一輪量測：V=(9.35+0.342U)/0.94，坡度 20°）。"""
    return (9.35 + 0.342 * np.asarray(U, float)) / 0.94


# ---------------------------------------------------------------------------
# 驗證
# ---------------------------------------------------------------------------
def _asm_poly(pid, axes, z=None):
    fr = frame(pid)
    zz = fr.thickness / 2 if z is None else z
    return fr.geom_asm(_parts()[pid].geom, zz, axes)


def _components(g, min_area: float = 0.2):
    """拆成多邊形元件，丟掉面積 < min_area 的數值碎片。"""
    if g.is_empty:
        return []
    geoms = [g] if isinstance(g, Polygon) else list(getattr(g, 'geoms', []))
    return [h for h in geoms if isinstance(h, Polygon) and h.area >= min_area]


def _holes_asm(pid, axes):
    fr = frame(pid)
    p = _parts()[pid]
    return [fr.geom_asm(Polygon(h), fr.thickness / 2, axes) for h in p.geom.interiors]


def _nearest(geoms, pt):
    return min(geoms, key=lambda g: g.centroid.distance(Point(pt)))


def _ctr(g):
    b = g.bounds
    return np.array([(b[0] + b[2]) / 2, (b[1] + b[3]) / 2])


def _rec(group, item, measured, expected, tol=0.3, unit='mm', note=''):
    m = np.atleast_1d(np.asarray(measured, float))
    e = np.atleast_1d(np.asarray(expected, float))
    r = float(np.max(np.abs(m - e))) if len(m) == len(e) else float('nan')
    return dict(group=group, item=item, measured=[round(float(v), 3) for v in m],
                expected=[round(float(v), 3) for v in e], residual=round(r, 3),
                ok=bool(r < tol), note=note)


def _section_V(g, W):
    """(W',V) 平面上的零件外形與 W'=W 這條線的交集 → [(Vmin, Vmax), …]（由小到大）。"""
    ln = LineString([(W, -1e3), (W, 1e3)])
    x = g.intersection(ln)
    segs = [x] if isinstance(x, LineString) else [s for s in getattr(x, 'geoms', []) if isinstance(s, LineString)]
    iv = sorted((min(s.coords[0][1], s.coords[-1][1]), max(s.coords[0][1], s.coords[-1][1])) for s in segs if s.length > 0.05)
    return iv


def _hole_near(holes, uv):
    h = _nearest(holes, uv)
    b = h.bounds
    return (b[0], b[2]), (b[1], b[3])   # U 範圍、V 範圍


def _circle_center(points):
    x, y = points[:, 0], points[:, 1]
    A = np.c_[2 * x, 2 * y, np.ones(len(x))]
    c = np.linalg.lstsq(A, x ** 2 + y ** 2, rcond=None)[0]
    return np.array([c[0], c[1]]), math.sqrt(c[2] + c[0] ** 2 + c[1] ** 2)


def verify(tol: float = 0.3) -> list[dict]:
    """用幾何對位驗證所有 Frame，回傳每一項的實測/期望/殘差（mm）。"""
    out = []
    UV = ('U', 'V')

    # 1) #26 馬達圓孔中心 ↔ #24 轉盤軸孔中心
    def circle_in(pid, approx_uv, r=10.0):
        best = None
        for h in _holes_asm(pid, UV):
            if h.centroid.distance(Point(approx_uv)) < 15:
                P = np.array(h.exterior.coords)
                c, _ = _circle_center(P)
                d = np.hypot(P[:, 0] - c[0], P[:, 1] - c[1])
                c, rr = _circle_center(P[np.abs(d - r) < 0.4])
                if best is None or abs(rr - r) < abs(best[1] - r):
                    best = (c, rr)
        return best
    c24, r24 = circle_in('#24', (58, 50))
    c26, r26 = circle_in('#26', (58, 50))
    out.append(_rec('#24↔#26', f'#26 馬達孔 Ø{2 * r26:.2f} 圓心 ↔ #24 軸孔 Ø{2 * r24:.2f} 圓心 (U,V)', c26, c24, tol))

    # 2) #24 與 #26 共用的貫穿孔：隔板長榫槽 ×3、#13/#21 齒孔 ×4、馬達盒底板槽 ×3
    h24 = _holes_asm('#24', UV)
    h26 = _holes_asm('#26', UV)
    for name, uv in [('1|5 長榫槽', (137.38, 88.45)), ('5|10 長榫槽', (167.13, 88.45)), ('10|50 長榫槽', (199.88, 88.45)),
                     ('右櫃側板 齒孔 1', (106.38, 86.0)), ('右櫃側板 齒孔 2', (106.38, 93.5)),
                     ('左櫃側板 齒孔 1', (237.63, 86.0)), ('左櫃側板 齒孔 2', (237.63, 93.5)),
                     ('V104～107 板槽 U47.9', (47.94, 105.46)), ('V104～107 板槽 U57.9', (57.94, 105.46)),
                     ('V104～107 板槽 U67.9', (67.94, 105.46)),
                     ('V36～39 板槽 U51.9', (51.94, 37.46)), ('V36～39 板槽 U63.9', (63.94, 37.46))]:
        a = _ctr(_nearest(h24, uv))
        b = _ctr(_nearest(h26, uv))
        bad = name == '右櫃側板 齒孔 1'
        out.append(_rec('#24↔#26', f'{name} 中心 (U,V)', b, a, tol,
                        note=('原始檔問題：#26 這個孔偏 ΔU +0.13、ΔV +1.00（左邊同位置的孔沒有偏）；'
                              '見 KNOWN_DEFECTS["26-tooth-hole"]') if bad and np.max(np.abs(b - a)) > tol else ''))
    # 2b) 套用 fix_26_tooth_hole() 後，該孔應與 #24 的孔重合
    fixed = fix_26_tooth_hole(_parts()['#26'])
    fr26 = frame('#26')
    h26f = [fr26.geom_asm(Polygon(h), fr26.thickness / 2, UV) for h in fixed.geom.interiors]
    a = _ctr(_nearest(h24, (106.38, 86.0)))
    b = _ctr(_nearest(h26f, (106.38, 86.0)))
    out.append(_rec('#24↔#26', '（修正後）右櫃側板 齒孔 1 中心 (U,V)：fix_26_tooth_hole()', b, a, tol,
                    note='修正後殘差；U 方向孔寬 2.95 對 #24 的 2.9，兩邊各 0.025'))

    # 3) #24 ↔ #37 共用貫穿孔、兩端榫
    h37 = _holes_asm('#37', UV)
    for name, uv in [('V36～39 板槽 U51.9', (51.94, 37.46)), ('V36～39 板槽 U63.9', (63.94, 37.46)),
                     ('V104～107 板槽 U15.4', (15.44, 105.46)), ('V104～107 板槽 U32.4', (32.44, 105.46)),
                     ('V104～107 板槽 U47.9', (47.94, 105.46))]:
        b = _ctr(_nearest(h37, uv))
        a = _ctr(_nearest(h24, uv))
        out.append(_rec('#24↔#37', f'{name} 中心 (U,V)', b, a, tol))
    t24 = sorted(_components(_asm_poly('#24', UV).intersection(box(-1, -1, 2.99, 120))), key=lambda g: _ctr(g)[1])
    t37 = sorted(_components(_asm_poly('#37', UV).intersection(box(-1, -1, 2.99, 120))), key=lambda g: _ctr(g)[1])
    out.append(_rec('#24↔#37', '右端 5 個榫中心 V（#37 對 #24）', [_ctr(g)[1] for g in t37], [_ctr(g)[1] for g in t24], tol))

    # 4) 間隔條 #5/#6/#7
    for pid in ('#7', '#6', '#5'):
        fr = frame(pid)
        g = fr.geom_asm(_parts()[pid].geom, 0, ('W', 'V'))
        uc = DIV_U_CENTER[pid]
        s24 = _section_V(g, sum(W24) / 2)
        assert len(s24) == 1, (pid, s24)
        lo, hi = s24[0]
        (ua, ub), (va, vb) = _hole_near(h24, (uc, (lo + hi) / 2))
        a = np.array([(ua + ub) / 2, (va + vb) / 2])
        out.append(_rec(pid, f'{fr.desc} 前長榫 V 範圍 ↔ #24 槽', [lo, hi], [va, vb], tol,
                        note=f'榫長 {hi - lo:.2f}／槽長 {vb - va:.2f}'))
        (ua2, ub2), (va2, vb2) = _hole_near(h26, (uc, (lo + hi) / 2))
        out.append(_rec(pid, '前長榫 V 範圍 ↔ #26 槽', [lo, hi], [va2, vb2], tol))
        long_t = g.intersection(box(-7, lo - 1, -3.0, hi + 1))
        out.append(_rec(pid, '前長榫尖端 W\'（應＝#24 前面 -6）', [long_t.bounds[0]], [W24[0]], tol))
        # #26 中心深度 W'=-1.5 的剖面：小榫（只穿 #26）＋長榫
        for lo, hi in _section_V(g, sum(W26) / 2):
            Vs = (lo + hi) / 2
            (ua, ub), (va, vb) = _hole_near(h26, (uc, Vs))
            kind = '前長榫' if hi - lo < 9 and Vs > 84 else '前小榫'
            if kind == '前長榫':
                continue
            out.append(_rec(pid, f'{kind} V{lo:.2f}～{hi:.2f} 中心 (U,V) ↔ #26 槽 V{va:.2f}～{vb:.2f}',
                            [uc, Vs], [(ua + ub) / 2, (va + vb) / 2], tol,
                            note=f'榫長 {hi - lo:.2f}／槽長 {vb - va:.2f}'))
        rear = _components(g.intersection(box(g.bounds[2] - 2.5, 0, 60, 200)))
        assert len(rear) == 1, (pid, len(rear))
        Vr = _ctr(rear[0])[1]
        hr = _ctr(_nearest(h37, (uc, Vr)))
        out.append(_rec(pid, '後榫中心 (U,V) ↔ #37 槽', [uc, Vr], hr, tol))
        body = g.intersection(box(-0.5, 0, 60, rear[0].bounds[1] - 0.5))   # 後榫上方那段後緣
        out.append(_rec(pid, '後肩 W\'（應＝#37 內面）', [body.bounds[2]], [W37_IN], tol))
        out.append(_rec(pid, '板中心 U ↔ #24 槽中心 U', [uc], [a[0]], tol))

    # 5) 抽屜櫃側板 #13（右）/#21（左）
    for pid in ('#13', '#21'):
        fr = frame(pid)
        uc = CAB_U_CENTER[pid]
        g = fr.geom_asm(_parts()[pid].geom, 0, ('W', 'V'))
        sec24 = _section_V(g, sum(W24) / 2)     # #24 中心深度剖面：齒 1、齒 2、齒 3
        sec26 = _section_V(g, sum(W26) / 2)     # #26 中心深度剖面：齒 1、齒 2、（V98 以下整段）
        for k in range(2):
            lo, hi = sec24[k]
            (ua, ub), (va, vb) = _hole_near(h24, (uc, (lo + hi) / 2))
            out.append(_rec(pid, f'{fr.desc} 齒 {k + 1} V 範圍 ↔ #24 孔', [lo, hi], [va, vb], tol,
                            note=f'齒寬 {hi - lo:.2f}／孔 {vb - va:.2f}'))
            out.append(_rec(pid, f'齒 {k + 1} 板中心 U ↔ #24 孔中心 U', [uc], [(ua + ub) / 2], tol))
            lo, hi = sec26[k]
            (ua, ub), (va, vb) = _hole_near(h26, (uc, (lo + hi) / 2))
            out.append(_rec(pid, f'齒 {k + 1} V 範圍 ↔ #26 孔', [lo, hi], [va, vb], tol,
                            note=('原始檔問題：#26 這個孔比 #24 的孔偏 ΔV +1.00（另有 ΔU +0.13；左邊那片沒有）'
                                  if abs((va + vb) / 2 - (lo + hi) / 2) > 0.5 else '')))
        tip = g.intersection(box(-7, 80, -3.0, 97))
        out.append(_rec(pid, '齒 1、2 尖端 W\'（應＝#24 前面 -6）', [tip.bounds[0]], [W24[0]], tol))
        # 第 3 齒（V105～110）伸進 #24 底緣缺口
        lo, hi = sec24[2]
        p24 = _asm_poly('#24', UV)
        gap = box(uc - 1.5, 98.5, uc + 1.5, 114).difference(p24)
        gaps = sorted(_components(gap), key=lambda s: -s.area)
        out.append(_rec(pid, '第 3 齒 V 範圍 ↔ #24 底緣缺口 V 範圍', [lo, hi],
                        [gaps[0].bounds[1], gaps[0].bounds[3]], tol))
        step = g.intersection(box(-3.0, 97, 0, 99.5))
        out.append(_rec(pid, '貼 #24 背面的階 V 起點 ↔ #26 底邊 V', [step.bounds[1]],
                        [_asm_poly('#26', UV).intersection(box(uc - 1.5, 0, uc + 1.5, 200)).bounds[3]], tol))
        back = g.intersection(box(W37_IN - 1, 75.5, W37_IN + 0.5, 79.5))   # 頂邊後端那段直緣
        out.append(_rec(pid, '後緣 W\'（貼 #37 內面）', [back.bounds[2]], [W37_IN], tol))
        top = g.intersection(box(0, 60, 27, 80))
        out.append(_rec(pid, '頂邊 V（上一輪：≈75）', [top.bounds[1]], [75.0], tol))

    # 6) #12 ↔ #13 槽、#12 兩端
    fr12 = frame('#12')
    g12 = _parts()['#12'].geom
    x0, y0 = _origin('#12')
    w12 = _parts()['#12'].size[0]
    for pid, side in (('#13', box(x0 + w12 - 2.99, 0, x0 + w12 + 1, 1e4)), ('#21', box(x0 - 1, 0, x0 + 2.99, 1e4))):
        ten = sorted(_components(g12.intersection(side)), key=lambda s: _ctr(s)[1])
        frc = frame(pid)
        slots = [frc.geom_asm(Polygon(h), 1.5, ('V', 'W')) for h in _parts()[pid].geom.interiors]
        for s in ten:
            if s.area < 5:
                continue
            c3 = fr12.to_asm(*_ctr(s), 1.5)
            sl = _nearest(slots, (c3[1], c3[2]))
            out.append(_rec('#12', f'榫（V{c3[1]:.1f}）中心 (V,W\') ↔ {pid} 槽', c3[1:], _ctr(sl), tol))
        tipx = x0 + w12 if pid == '#13' else x0
        shx = x0 + w12 - 3 if pid == '#13' else x0 + 3
        Utip = fr12.to_asm(tipx, y0 + 10, 1.5)[0]
        Ush = fr12.to_asm(shx, y0 + 10, 1.5)[0]
        plo, phi = frame(pid).plane()[1:]
        out.append(_rec('#12', f'{pid} 端：榫尖/肩 U ↔ {pid} 外/內面 U', [Utip, Ush],
                        [plo, phi] if pid == '#13' else [phi, plo], tol))

    # 7) 端板 #31/#36 槽 ↔ #24、#37 兩端榫
    for pid, uedge in (('#31', 1.5), ('#36', 244.5)):
        fr = frame(pid)
        slots = [fr.geom_asm(Polygon(h), 1.5, ('W', 'V')) for h in _parts()[pid].geom.interiors]
        row24 = sorted([s for s in slots if _ctr(s)[0] < 12], key=lambda s: _ctr(s)[1])
        row37 = sorted([s for s in slots if _ctr(s)[0] > 12], key=lambda s: _ctr(s)[1])
        win = box(-1, -1, 2.99, 120) if pid == '#31' else box(243.01, -1, 247, 120)
        ten24 = sorted(_components(_asm_poly('#24', UV).intersection(win)), key=lambda g: _ctr(g)[1])
        ten37 = sorted(_components(_asm_poly('#37', UV).intersection(win)), key=lambda g: _ctr(g)[1])
        out.append(_rec(pid, f'{fr.desc} 前排槽中心 V ↔ #24 端榫', [_ctr(s)[1] for s in row24], [_ctr(g)[1] for g in ten24], tol))
        out.append(_rec(pid, '後排槽中心 V ↔ #37 端榫', [_ctr(s)[1] for s in row37], [_ctr(g)[1] for g in ten37], tol))
        out.append(_rec(pid, '前排槽中心 W\' ↔ #24 中心 -4.5', [np.mean([_ctr(s)[0] for s in row24])], [sum(W24) / 2], tol))
        out.append(_rec(pid, '後排槽中心 W\' ↔ #37 中心', [np.mean([_ctr(s)[0] for s in row37])], [W37_IN + 1.5], tol,
                        note='兩排槽中心距 34.68，比 #24 中心到 #37 中心 35.0 少 0.32'))
        b24 = _asm_poly('#24', UV).bounds
        outer = b24[0] if pid == '#31' else b24[2]
        face = fr.plane()[1] if pid == '#31' else fr.plane()[2]
        out.append(_rec(pid, '#24 端榫尖 U ↔ 端板外面 U（榫長＝板厚 3）', [outer], [face], tol))

    # 8) 抽屜櫃側板 #13/#21 ↔ #37 下方開口（審查時新增）：在 #37 板厚內三個深度取側板截面，
    #    算與 #37 實體的干涉面積與最大干涉深度（干涉點到側板截面邊界的最大距離）。
    g37 = _asm_poly('#37', UV)
    for pid in ('#13', '#21'):
        fr = frame(pid)
        g = fr.geom_asm(_parts()[pid].geom, 0, ('W', 'V'))
        plo, phi = fr.plane()[1:]
        areas, depths = [], []
        for W in (W37_IN + 0.15, W37_IN + 1.5, W37_IN + T_BOARD - 0.15):
            S = unary_union([box(plo, lo, phi, hi) for lo, hi in _section_V(g, W)])
            R = S.intersection(g37)
            areas.append(R.area)
            depths.append(_pen_depth(R, S))
        k = int(np.argmax(depths))
        out.append(_rec(pid, f"{fr.desc}：與 #37 開口干涉的最大深度（W'={W37_IN + 0.15:.2f}/{W37_IN + 1.5:.2f}/"
                             f"{W37_IN + T_BOARD - 0.15:.2f} 處面積 {'/'.join(f'{a:.2f}' for a in areas)} mm²）",
                        [max(depths)], [0.0], tol,
                        note=('原始檔問題：#37 開口邊／R2 內角壓到側板頂後角；見 KNOWN_DEFECTS["37-cutout-corners"]'
                              if max(depths) >= tol else '#37 底邊 V82 與側板 30° 頂邊在 #37 外側交疊（小）')))
    return out


def _pen_depth(R, S, step: float = 0.01) -> float:
    """干涉區 R（在截面 S 內）各點到 S 邊界的最大距離（格點取樣，step mm）。"""
    import shapely
    if R.is_empty or R.area < 1e-6:
        return 0.0
    x0, y0, x1, y1 = R.bounds
    X, Y = np.meshgrid(np.arange(x0, x1 + step, step), np.arange(y0, y1 + step, step))
    inside = shapely.contains_xy(R, X.ravel(), Y.ravel())
    if not inside.any():
        return 0.0
    pts = shapely.points(X.ravel()[inside], Y.ravel()[inside])
    return float(shapely.distance(pts, S.boundary).max())


def report(rows=None) -> str:
    rows = rows if rows is not None else verify()
    lines = []
    for r in rows:
        flag = 'OK ' if r['ok'] else '!! '
        lines.append(f"{flag}[{r['group']}] {r['item']}: 實測 {r['measured']} 期望 {r['expected']} "
                     f"殘差 {r['residual']:.3f}{'  ※' + r['note'] if r['note'] else ''}")
    return '\n'.join(lines)


if __name__ == '__main__':
    rows = verify()
    print(report(rows))
    bad = [r for r in rows if not r['ok']]
    known = [r for r in bad if '原始檔問題' in r['note']]
    rest = [r['residual'] for r in rows if '原始檔問題' not in r['note']]
    print(f'\n共 {len(rows)} 項；殘差 ≥0.3 mm：{len(bad)} 項（其中原始檔問題 {len(known)} 項）；'
          f'其餘最大殘差 {max(rest):.3f} mm')

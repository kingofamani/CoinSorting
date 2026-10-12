# 基礎幾何：唯讀匯入 repo 的 laser_v2（frames/catalog），換到組裝座標 (U,V,W')。
# 執行一律用 python3 -B（不寫 .pyc 進 repo）。
import sys, re
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/CoinSorting')
import numpy as np
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union
from shapely import affinity
from laser_v2 import frames as F, catalog as C
from svgpathtools import parse_path

PARTS = C.load_catalog()


def asm_poly(pid, axes=('U', 'V')):
    fr = F.frame(pid)
    return fr.geom_asm(PARTS[pid].geom, fr.thickness / 2, axes)


G24 = asm_poly('#24'); G26 = asm_poly('#26'); G37 = asm_poly('#37')
O24 = Polygon(G24.exterior); O26 = Polygon(G26.exterior); O37 = Polygon(G37.exterior)
H24 = [Polygon(h) for h in G24.interiors]
H26 = [Polygon(h) for h in G26.interiors]
SLOT24 = max(H24, key=lambda p: p.area)            # #24 斜槽（硬幣通道）

# ---- 軌道：#24 斜槽下緣擬合 ----
_pts = []
for U in np.arange(80, 232, 1.0):
    L = LineString([(U, -5), (U, 130)]).intersection(SLOT24)
    if not L.is_empty:
        _pts.append((U, L.bounds[3]))
_pts = np.array(_pts)
RAIL_M, RAIL_B = np.linalg.lstsq(np.vstack([_pts[:, 0], np.ones(len(_pts))]).T, _pts[:, 1], rcond=None)[0]
RAIL_RES = float(np.abs(_pts[:, 1] - (RAIL_M * _pts[:, 0] + RAIL_B)).max())
ANG = np.arctan(RAIL_M)
CA, SA = np.cos(ANG), np.sin(ANG)
T = np.array([CA, SA])      # 沿軌往下游（U 增）
N = np.array([SA, -CA])     # 垂直軌道往上（進入斜槽）


def railV(U):
    return RAIL_M * np.asarray(U, float) + RAIL_B


# ---- 分幣開口（#26 大孔，U 範圍）----
OPS = {}
for p in H26:
    b = p.bounds
    if p.area > 300 and b[0] > 100:
        for c, u0 in (('1', 114.1), ('5', 140.56), ('10', 170.19), ('50', 203.05)):
            if abs(b[0] - u0) < 1.0:
                OPS[c] = p
COIN_D = {'1': 20.0, '5': 22.0, '10': 26.0, '50': 28.0}
COIN_T = {'1': 1.85, '5': 2.0, '10': 2.0, '50': 2.4}   # 估計（未實量），只用在前面間隙


def op_U(c):
    b = OPS[c].bounds
    return b[0], b[2]


STATIONS = {   # 站：上游幣、下游幣、隔板
    'S5': dict(up='1', dn='5', div='#7'),
    'S10': dict(up='5', dn='10', div='#6'),
    'S50': dict(up='10', dn='50', div='#5'),
}
for k, st in STATIONS.items():
    st['bar'] = (op_U(st['up'])[1], op_U(st['dn'])[0])
    st['Ubar'] = sum(st['bar']) / 2
    pl = F.frame(st['div']).plane()
    st['divU'] = (pl[1], pl[2])

# 開口下緣（唇）離軌：取開口最低點的垂直距離
def n_of(U, V):
    """(U,V) 點離軌道的垂直距離（軌道上方為正）"""
    return (railV(U) - V) * CA


LIP = {c: float(min(n_of(x, y) for x, y in np.array(p.exterior.coords))) for c, p in OPS.items()}

# ---- 隔板（#5/#6/#7）在 (W',V) 的外形 ----
def div_WV(pid):
    fr = F.frame(pid)
    return fr.geom_asm(PARTS[pid].geom, fr.thickness / 2, ('W', 'V'))


DIVWV = {pid: div_WV(pid) for pid in ('#5', '#6', '#7')}


def exitV(W):
    """滑道出口平面（隔板斜底邊）：W'0→V98、W'29→V82"""
    return 98.0 - 16.0 * np.asarray(W, float) / 29.0


# ---- 雕刻（#24）在 (U,V) 的外框 ----
def engrave_boxes(pid):
    p = PARTS[pid]; fr = F.frame(pid); out = {}
    for e, src in zip(p.engrave, p.engrave_src):
        pts = []
        for d in re.findall(r'\sd="([^"]+)"', e):
            for seg in parse_path(d):
                for t in np.linspace(0, 1, 10):
                    z = seg.point(t); pts.append((z.real, z.imag))
        if pts:
            A = np.array(pts); B = fr.to_asm(A[:, 0], A[:, 1], 0)
            out[src] = box(B[:, 0].min(), B[:, 1].min(), B[:, 0].max(), B[:, 1].max())
    return out


ENG24 = engrave_boxes('#24')
ENG_NAME = {'text16-7-2': '「1」', 'text11-4-1': '「5」', 'text2-1-3': '「10」', 'text1-6-4': '「50」', 'path1-5-9': 'Logo'}

# ---- 其他參考 ----
TURN_C = (58.0, 50.0)       # 轉盤軸（U,V）
TURN_R_RING = 54.5          # 圍邊 #27 外緣（含板厚）／前蓋 #63 最大半徑
W37 = F.W37_IN              # 29.0
MOTOR_U = (43.8, 72.1)
CAB13_U = (104.875, 107.875)


def to_UV(O, s, n):
    return np.asarray(O) + np.multiply.outer(s, T) + np.multiply.outer(n, N) if np.ndim(s) else np.asarray(O) + s * T + n * N


def rect_sn(O, s0, s1, n0, n1):
    pts = [(s0, n0), (s1, n0), (s1, n1), (s0, n1)]
    return Polygon([tuple(np.asarray(O) + s * T + n * N) for s, n in pts])


def poly_sn(O, pts):
    return Polygon([tuple(np.asarray(O) + s * T + n * N) for s, n in pts])


def UV_to_sn(O, g):
    O = np.asarray(O)
    return affinity.affine_transform(affinity.translate(g, -O[0], -O[1]), [T[0], T[1], N[0], N[1], 0, 0])


if __name__ == '__main__':
    print('rail V = %.6f U + %.4f  (%.4f°, 殘差 %.4f)' % (RAIL_M, RAIL_B, np.degrees(ANG), RAIL_RES))
    for c, p in OPS.items():
        print('開口', c, 'U %.3f-%.3f' % op_U(c), '唇離軌 %.3f' % LIP[c])
    for k, st in STATIONS.items():
        print(k, 'bar U %.3f-%.3f 寬 %.3f 中心 %.3f' % (*st['bar'], st['bar'][1] - st['bar'][0], st['Ubar']),
              '隔板', st['div'], 'U %.3f-%.3f' % st['divU'], 'rail V@bar %.3f' % railV(st['Ubar']),
              '軌下到 V98 垂直 %.2f' % ((98 - railV(st['Ubar'])) * CA))
    for s, b in ENG24.items():
        print('雕刻', ENG_NAME.get(s, s), [round(x, 2) for x in b.bounds])

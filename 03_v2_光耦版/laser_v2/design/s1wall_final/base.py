"""S1 最終規格：共用基礎幾何。
唯讀匯入 repo 的 laser_v2（frames／catalog），一律 sys.dont_write_bytecode，不寫 .pyc 進 repo。
組裝座標 (U, V, W')：U 沿機身（0＝右端轉盤側）、V 沿面板往下、W' 深度（#26 背面＝0、#37 內面＝29.0）。
"""
import sys, os, math, json, importlib
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/CoinSorting')
import numpy as np
from shapely.geometry import Polygon, LineString, Point, box, MultiPolygon
from shapely.ops import unary_union
from shapely import affinity
from laser_v2 import frames as F, catalog as C

HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.dirname(HERE)
PARTS = C.load_catalog()


def asm_poly(pid, axes=('U', 'V')):
    fr = F.frame(pid)
    return fr.geom_asm(PARTS[pid].geom, fr.thickness / 2, axes)


G24, G26, G37 = asm_poly('#24'), asm_poly('#26'), asm_poly('#37')
O24, O26, O37 = Polygon(G24.exterior), Polygon(G26.exterior), Polygon(G37.exterior)
H24 = [Polygon(h) for h in G24.interiors]
H26 = [Polygon(h) for h in G26.interiors]
H37 = [Polygon(h) for h in G37.interiors]
SLOT24 = max(H24, key=lambda p: p.area)

# ---- 軌道：#24 斜槽下緣擬合（與 crosstrack_final 同法） ----
_pts = []
for _U in np.arange(80, 232, 1.0):
    _L = LineString([(_U, -5), (_U, 130)]).intersection(SLOT24)
    if not _L.is_empty:
        _pts.append((_U, _L.bounds[3]))
_pts = np.array(_pts)
RAIL_M, RAIL_B = np.linalg.lstsq(np.vstack([_pts[:, 0], np.ones(len(_pts))]).T, _pts[:, 1], rcond=None)[0]
ANG = math.atan(RAIL_M)
TT = np.array([math.cos(ANG), math.sin(ANG)])      # 沿軌往下游
NN = np.array([math.sin(ANG), -math.cos(ANG)])     # 垂直軌道往上


def railV(U):
    return RAIL_M * np.asarray(U, float) + RAIL_B


# ---- 1 元開口 ----
OP1 = [p for p in H26 if p.area > 300 and abs(p.bounds[0] - 114.1) < 1.0][0]
OPEN1 = (OP1.bounds[0], OP1.bounds[2])              # 114.104, 134.604

# ---- 牆、隔板、#37 ----
U13 = F.frame('#13').plane()[1:]                    # (104.875, 107.875)
U7 = F.frame('#7').plane()[1:]                      # (135.876, 138.876)
U21 = F.frame('#21').plane()[1:]
W37 = F.W37_IN                                      # 29.0
W37o = W37 + 3.0
COIN_D, COIN_T = 20.0, 1.85                         # 1 元：直徑 20、厚度（取保守 1.85；新幣約 1.55~1.85）


def exitV(W):
    """滑道出口平面（間隔條 #7 斜底邊）：貼 #26 V98、貼 #37 V82。"""
    return 98.0 - 16.0 * np.asarray(W, float) / 29.0


G_UVW = np.array([0.0, math.cos(math.radians(30)), 0.5])   # 世界鉛直往下（U,V,W'）


def slope_deg(dW, dV):
    """(W',V) 平面內方向 (dW,dV) 對世界水平的夾角（往下為正）。"""
    L = math.hypot(dW, dV)
    return math.degrees(math.asin((0.5 * dW + 0.866025 * dV) / L))


# ---- #13 局部 ↔ (V,W') ----
def local_origin(pid):
    b = PARTS[pid].bbox
    return b[0], b[1]


def asm_to_local(pid, U, V, W):
    p = F.frame(pid).to_page(U, V, W)
    x0, y0 = local_origin(pid)
    return np.stack([p[..., 0] - x0, p[..., 1] - y0, p[..., 2]], axis=-1)


def local_to_asm(pid, x, y, z=0.0):
    x0, y0 = local_origin(pid)
    return F.frame(pid).to_asm(np.asarray(x, float) + x0, np.asarray(y, float) + y0, z)


def WV_to_local13(W, V):
    p = asm_to_local('#13', np.full_like(np.asarray(V, float), U13[0]), V, W)
    return p[..., 0], p[..., 1]


def local13_to_WV(x, y):
    a = local_to_asm('#13', x, y, 0.0)
    return a[..., 2], a[..., 1]


def poly_WV_to_local13(g):
    def ring(c):
        c = np.array(c)
        x, y = WV_to_local13(c[:, 0], c[:, 1])
        return np.c_[x, y]
    return Polygon(ring(g.exterior.coords), [ring(r.coords) for r in g.interiors])


def UV_to_local26(g):
    return affinity.affine_transform(g, [0, 1, 1, 0, -4.0, -40.0])      # (x,y)=(V-4, U-40)


def UV_to_local37(g):
    return affinity.affine_transform(g, [0, -1, 1, 0, 114.0, 0.0])      # (x,y)=(114-V, U)


def ORIG13_WV():
    fr = F.frame('#13'); g = PARTS['#13'].geom
    return fr.geom_asm(g, 0.0, ('W', 'V'))


# ---- S5（crosstrack_final）模組實體：翼在 1 元滑道的範圍（最終位置＋低位安裝掃掠） ----
def s5_boxes(wing='up'):
    """回傳 dict(final=[(名稱, UV多邊形, (W0,W1))...], low=[...], sweep=UV 聯集(只取 W'≥0 的實體))。
    以 crosstrack_final/model.py 重算；wing 由環境變數 CT_OVR 控制，這裡用子程序隔離。"""
    import subprocess
    code = r'''
import sys, json, os
sys.dont_write_bytecode=True
sys.path.insert(0, %r)
os.chdir(%r)
from model import build, sn2uv
from params import P as P0
from shapely.geometry import box
P = dict(P0); P['wing'] = %r
_P, D, S, X = build(P)
st = S['S5']
to = sn2uv(st['O'])
out = {}
for key in ('mod_final', 'mod_low'):
    L = []
    for nm, s0, s1, n0, n1, w0, w1 in st[key]:
        g = to(box(s0, n0, s1, n1))
        L.append([nm, list(g.exterior.coords), [w0, w1]])
    out[key] = L
out['win26'] = list(st['win'].exterior.coords)
out['W_deep'] = D['W_deep']
print(json.dumps(out))
''' % (os.path.join(V2, 'crosstrack_final'), os.path.join(V2, 'crosstrack_final'), wing)
    r = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:])
    d = json.loads(r.stdout.strip().splitlines()[-1])
    res = {'win26_UV': Polygon(d['win26']), 'W_deep': d['W_deep']}
    for key in ('mod_final', 'mod_low'):
        res[key] = [(nm, Polygon(c), tuple(w)) for nm, c, w in d[key]]
    ch = []
    for key in ('mod_final', 'mod_low'):
        for nm, g, (w0, w1) in res[key]:
            if w1 > 0:
                ch.append(g)
    res['sweep_UV'] = unary_union(ch).convex_hull      # 上滑時連續掃過：取 final∪low 凸包（保守）
    res['W_max'] = max(w1 for key in ('mod_final', 'mod_low') for _, _, (w0, w1) in res[key])
    return res


def r3(v):
    return float(round(float(v), 3))

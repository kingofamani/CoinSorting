"""共用：唯讀載入 laser_v2（不寫 .pyc）、擠出實體 Solid、3D 距離。"""
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/CoinSorting')
import re, math, json
import numpy as np
import shapely
from shapely.geometry import Polygon, MultiPolygon, Point, MultiPoint, LineString, box
from shapely.ops import unary_union
from shapely import affinity
from svgpathtools import parse_path
from laser_v2 import frames as F, catalog as C

P = C.load_catalog()
FR = F.frames()
AXI = {'U': 0, 'V': 1, 'W': 2}
PLANE = {'W': ('U', 'V'), 'U': ('W', 'V'), 'V': ('U', 'W')}
HERE = '/tmp/claude-0/-home-user-CoinSorting/e4dcfae7-64f2-510b-91ab-d1c0e7dcce93/scratchpad/v2work/ebox_final'
CT = '/tmp/claude-0/-home-user-CoinSorting/e4dcfae7-64f2-510b-91ab-d1c0e7dcce93/scratchpad/v2work/crosstrack_final'


def rect(a0, a1, b0, b1):
    return box(min(a0, a1), min(b0, b1), max(a0, a1), max(b0, b1))


class Solid:
    """擠出體：截面 poly（PLANE[axis] 兩軸）× 擠出軸範圍 rng。"""
    def __init__(self, name, axis, poly, rng, kind=''):
        self.name, self.axis, self.poly, self.rng, self.kind = name, axis, poly, tuple(rng), kind

    def dist_points(self, P3):
        a, b = PLANE[self.axis]
        P3 = np.asarray(P3, float)
        pts = shapely.points(P3[:, AXI[a]], P3[:, AXI[b]])
        d2 = shapely.distance(self.poly, pts)
        c = P3[:, AXI[self.axis]]
        lo, hi = self.rng
        dc = np.maximum(0, np.maximum(lo - c, c - hi))
        return np.sqrt(d2 ** 2 + dc ** 2)

    def sample(self, step=0.4):
        a, b = PLANE[self.axis]
        x0, y0, x1, y1 = self.poly.bounds
        xs = np.arange(x0, x1 + 1e-9, step); ys = np.arange(y0, y1 + 1e-9, step)
        X, Y = np.meshgrid(xs, ys); X = X.ravel(); Y = Y.ravel()
        ins = shapely.contains_xy(self.poly.buffer(1e-6), X, Y)
        X, Y = X[ins], Y[ins]
        bds = [self.poly] if self.poly.geom_type == 'Polygon' else list(self.poly.geoms)
        bx, by = [], []
        for g in bds:
            for ring in [g.exterior] + list(g.interiors):
                L = ring.length
                ts = np.linspace(0, L, max(8, int(L / step)))
                pp = np.array([[ring.interpolate(t).x, ring.interpolate(t).y] for t in ts])
                bx.append(pp[:, 0]); by.append(pp[:, 1])
        X = np.r_[X, np.concatenate(bx)]; Y = np.r_[Y, np.concatenate(by)]
        lo, hi = self.rng
        cs = np.unique(np.r_[np.arange(lo, hi, step), hi])
        out = np.zeros((len(X) * len(cs), 3))
        for k, cv in enumerate(cs):
            blk = out[k * len(X):(k + 1) * len(X)]
            blk[:, AXI[a]] = X; blk[:, AXI[b]] = Y; blk[:, AXI[self.axis]] = cv
        return out

    def bounds3(self):
        a, b = PLANE[self.axis]
        x0, y0, x1, y1 = self.poly.bounds
        lo = [0.0] * 3; hi = [0.0] * 3
        lo[AXI[a]], hi[AXI[a]] = x0, x1
        lo[AXI[b]], hi[AXI[b]] = y0, y1
        lo[AXI[self.axis]], hi[AXI[self.axis]] = self.rng
        return np.array(lo), np.array(hi)


def boxsolid(name, u0, u1, v0, v1, w0, w1, kind=''):
    return Solid(name, 'W', rect(u0, u1, v0, v1), (min(w0, w1), max(w0, w1)), kind)


def dist(A, B, step=0.35):
    """A、B 最小距離（0＝接觸或重疊）。取樣體積較小者。"""
    la, ha = A.bounds3(); lb, hb = B.bounds3()
    gap = np.maximum(0, np.maximum(la - hb, lb - ha))
    if np.linalg.norm(gap) > 40:
        return float(np.linalg.norm(gap))
    va = np.prod(ha - la + 0.1); vb = np.prod(hb - lb + 0.1)
    S, O = (A, B) if va <= vb else (B, A)
    st = max(step, (min(va, vb) / 60000.0) ** (1 / 3))
    pts = S.sample(st)
    ls, hs = S.bounds3()
    m = 30.0
    keep = np.all((pts >= np.maximum(lb, la) - m) & (pts <= np.minimum(hb, ha) + m), axis=1) if False else slice(None)
    d = O.dist_points(pts[keep])
    return float(d.min())


def overlap_vol(A, B, step=0.3):
    pts = A.sample(step)
    return float((B.dist_points(pts) < 1e-6).sum() * step ** 3)


def asm_geom(pid, axes=('U', 'V')):
    fr = FR[pid]
    pl = fr.plane()
    z = (pl[1] + pl[2]) / 2 if pl else 0.0
    return fr.geom_asm(P[pid].geom, fr.thickness / 2, axes)


def holes_asm(pid, axes=('U', 'V')):
    fr = FR[pid]
    return [fr.geom_asm(Polygon(h), fr.thickness / 2, axes) for h in P[pid].geom.interiors]


def origin(pid):
    b = P[pid].bbox
    return float(b[0]), float(b[1])


def engrave_pts(pid):
    out = {}
    for e, src in zip(P[pid].engrave, P[pid].engrave_src):
        pts = []
        for d in re.findall(r'\sd="([^"]+)"', e):
            p = parse_path(d)
            for sp in p.continuous_subpaths():
                for t in np.linspace(0, 1, 300):
                    z = sp.point(t); pts.append((z.real, z.imag))
        out[src] = np.array(pts)
    return out


def asm2_to_page(pid, pts2, third=None):
    """零件板面平面上的組裝座標點 (N,2)（兩軸＝PLANE[法線軸]）→ 頁座標 (N,2)。third 省略取板中。"""
    pl = FR[pid].plane()
    ax = pl[0]
    if third is None:
        third = (pl[1] + pl[2]) / 2
    a, b = PLANE[ax]
    A = np.asarray(pts2, float)
    P3 = np.zeros((len(A), 3))
    P3[:, AXI[a]] = A[:, 0]; P3[:, AXI[b]] = A[:, 1]; P3[:, AXI[ax]] = third
    pg = FR[pid].to_page(P3[:, 0], P3[:, 1], P3[:, 2])
    return pg[:, :2]


def poly_to_page_local(pid, poly, third=None):
    """組裝平面多邊形 → (頁座標多邊形, 局部座標多邊形)。局部＝頁座標 − 零件 bbox 左上角。"""
    ext = asm2_to_page(pid, np.array(poly.exterior.coords), third)
    o = np.array(origin(pid))
    return Polygon(ext), Polygon(ext - o)


def r2(v, n=2):
    return round(float(v), n)


def coords(poly, nd=2):
    return [(round(float(x), nd), round(float(y), nd)) for x, y in poly.exterior.coords][:-1]

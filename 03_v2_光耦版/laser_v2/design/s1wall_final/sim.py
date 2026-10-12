"""S1 落幣 3D 剛體模擬（pybullet，簡化模型；只做方案間的相對比較，不是良率預測）。
模擬 1 元從軌道滾進 1 元開口、往後翻倒、落進 1 元滑道、穿過 S1 光束、從出口平面離開的全過程。
世界座標（右手系）：X=U、Y=V、Z=-W'（單位 mm、s、kg）。重力＝9810·(0, 0.866, -0.5)。
變體：
  A 背插卡匣、無導流帽、無 S5 翼        B 背插卡匣＋導流帽、無 S5 翼
  C 背插卡匣、無導流帽、S5 翼朝上游     D 背插卡匣＋導流帽、S5 翼朝上游
  E 角度 2 的整流板＋導流坡（參考）、無 S5 翼
  Z 只有加高牆、滑道內沒有任何模組（看自然落點）
輸出：sim.json、sim_out.txt
"""
import sys, json, math, time, itertools
sys.dont_write_bytecode = True
import numpy as np
import pybullet as p
import base as B
import design as DS

G = 9810.0
GV = np.array([0.0, 0.8660254, -0.5]) * G
DT = 1.0 / 3000
T_MAX = 1.0
COIN_R, COIN_H, COIN_M = 10.0, 1.6, 0.0038


def Z(w):
    return -w


def add_box(cid, U0, U1, V0, V1, W0, W1, tag, bodies):
    he = [(U1 - U0) / 2, (V1 - V0) / 2, (W1 - W0) / 2]
    col = p.createCollisionShape(p.GEOM_BOX, halfExtents=he, physicsClientId=cid)
    b = p.createMultiBody(0, col, basePosition=[(U0 + U1) / 2, (V0 + V1) / 2, Z((W0 + W1) / 2)], physicsClientId=cid)
    bodies[b] = tag
    return b


def add_rot_box(cid, center_uv, ang, L, H, W0, W1, tag, bodies):
    """沿軌道方向轉 ang 的盒子：L 沿 (cos,sin)，H 沿垂直方向。"""
    col = p.createCollisionShape(p.GEOM_BOX, halfExtents=[L / 2, H / 2, (W1 - W0) / 2], physicsClientId=cid)
    q = p.getQuaternionFromEuler([0, 0, ang])
    b = p.createMultiBody(0, col, basePosition=[center_uv[0], center_uv[1], Z((W0 + W1) / 2)],
                          baseOrientation=q, physicsClientId=cid)
    bodies[b] = tag
    return b


def add_prism_WV(cid, poly_WV, U0, U1, tag, bodies):
    """(W',V) 平面凸多邊形沿 U 擠出成凸殼。"""
    pts = np.array(poly_WV.exterior.coords)[:-1]
    verts = []
    for uu in (U0, U1):
        for w, v in pts:
            verts.append([uu, v, Z(w)])
    verts = np.array(verts)
    c = verts.mean(axis=0)
    col = p.createCollisionShape(p.GEOM_MESH, vertices=(verts - c).tolist(), physicsClientId=cid)
    b = p.createMultiBody(0, col, basePosition=c.tolist(), physicsClientId=cid)
    bodies[b] = tag
    return b


def add_poly_UV_box(cid, poly_UV, W0, W1, tag, bodies):
    pts = np.array(poly_UV.exterior.coords)[:-1]
    verts = [[u, v, Z(w)] for w in (W0, W1) for u, v in pts]
    verts = np.array(verts); c = verts.mean(axis=0)
    col = p.createCollisionShape(p.GEOM_MESH, vertices=(verts - c).tolist(), physicsClientId=cid)
    b = p.createMultiBody(0, col, basePosition=c.tolist(), physicsClientId=cid)
    bodies[b] = tag
    return b


ANG = B.ANG
TV = np.array([math.cos(ANG), math.sin(ANG)])
NV = np.array([math.sin(ANG), -math.cos(ANG)])      # 垂直軌道「往上」（V 減）
# 1 元開口下緣、上緣（直線擬合，忽略頂角圓角）
_ops = np.array(B.OP1.exterior.coords)
LIP_V = lambda U: 50.205 + B.RAIL_M * (U - 114.5)
TOP_V = lambda U: 31.134 + B.RAIL_M * (U - 118.0)


def build_world(cid, variant, geo):
    bodies = {}
    p.setGravity(*GV, physicsClientId=cid)
    # ---- #24 軌道（W' -6~-3）：軌道線以下 ----
    U_a, U_b = 88.0, 146.0
    Pm = np.array([(U_a + U_b) / 2, B.railV((U_a + U_b) / 2)])
    L = (U_b - U_a) / math.cos(ANG)
    c = Pm - NV * 10.0
    add_rot_box(cid, c, ANG, L, 20.0, -6.0, -3.0, '#24', bodies)
    # ---- #26（W' -3~0）：開口右側、立柱、唇下、開口上方 ----
    o0, o1 = B.OPEN1
    add_box(cid, 88.0, o0, -5.0, 105.0, -3.0, 0.0, '#26', bodies)
    add_box(cid, o1, 146.0, -5.0, 105.0, -3.0, 0.0, '#26', bodies)
    Um = (o0 + o1) / 2
    Lw = (o1 - o0) / math.cos(ANG) + 2.0
    lipP = np.array([Um, LIP_V(Um)])
    add_rot_box(cid, lipP - NV * 25.0, ANG, Lw, 50.0, -3.0, 0.0, '#26', bodies)
    topP = np.array([Um, TOP_V(Um)])
    add_rot_box(cid, topP + NV * 15.0, ANG, Lw, 30.0, -3.0, 0.0, '#26', bodies)
    # ---- 滑道：右牆 #13R、#7、#37 ----
    wall_top = geo['Dd']['wall_top']
    add_box(cid, 104.875, 107.875, wall_top, 98.0, 0.0, 29.0, 'wall', bodies)
    add_box(cid, 135.876, 138.876, 14.0, 98.0, 0.0, 29.0, '#7', bodies)
    add_box(cid, 95.0, 146.0, -10.0, 82.0, 29.0, 32.0, '#37', bodies)
    # ---- S1 ----
    m = geo['mod']
    if variant in ('A', 'B', 'C', 'D', 'F', 'G', 'H', 'I'):
        for k in ('pcb', 'comp', 'body', 'front_arm'):
            U0, U1, V0, V1, W0, W1 = m[k]
            add_box(cid, U0, U1, V0, V1, W0, min(W1, 29.0), 'S1_' + k, bodies)
        if variant in ('B', 'D', 'F', 'G', 'H', 'I'):
            U0 = geo['S1H_U'][0][0]; U1 = geo['S1H_U'][-1][1]
            add_prism_WV(cid, geo['S1H_WV'], U0, U1, 'S1_cap', bodies)
    if variant == 'E':
        # 角度 2：F1/F2 整流板（U107.875~113.875）＋導流坡 L1~L7（U113.875~134.875）
        add_box(cid, 107.875, 113.875, 12.0, 81.5, 0.3, 28.7, 'E_F', bodies)
        from shapely.geometry import Polygon
        ramp = Polygon([(0.3, 59.5), (9.3, 63.0), (19.3, 69.5), (19.3, 81.5), (0.3, 81.5)])
        add_prism_WV(cid, ramp, 113.875, 134.875, 'E_ramp', bodies)
    # ---- 左側導板（測試用）：貼 #7 右面，W'10.5~28.8，頂邊斜 ----
    if variant in ('H', 'I'):
        from shapely.geometry import Polygon
        lin = Polygon([(10.5, 62.0), (28.8, 72.0), (28.8, 82.0), (10.5, 92.0)])
        add_prism_WV(cid, lin, 132.876, 135.876, 'S1_liner', bodies)
    # ---- S5 翼 ----
    s5key = {'C': 's5_up', 'D': 's5_up', 'I': 's5_up', 'F': 's5_down', 'G': 's5_center'}.get(variant)
    if s5key:
        for nm, poly, (w0, w1) in geo[s5key]['mod_final']:
            if w1 <= 0:
                continue
            add_poly_UV_box(cid, poly, max(w0, 0.0), w1, 'S5_' + nm, bodies)
    return bodies


def beam_blocked(pos, orn, beam):
    R = np.array(p.getMatrixFromQuaternion(orn)).reshape(3, 3)
    ws = np.linspace(beam['w0'], beam['w1'], 41)
    pts = np.stack([np.full_like(ws, beam['U']), np.full_like(ws, beam['V']), -ws], axis=1)
    loc = (pts - np.array(pos)) @ R          # 轉到硬幣局部
    rr = np.hypot(loc[:, 0], loc[:, 1])
    return bool(np.any((np.abs(loc[:, 2]) <= COIN_H / 2) & (rr <= COIN_R)))


def run_one(variant, geo, v0, mu, e, du, tilt, spin, seed, th=None):
    global COIN_H
    COIN_H = th if th is not None else 1.6
    cid = p.connect(p.DIRECT)
    p.setPhysicsEngineParameter(fixedTimeStep=DT, numSolverIterations=60, physicsClientId=cid)
    bodies = build_world(cid, variant, geo)
    for b in bodies:
        p.changeDynamics(b, -1, lateralFriction=1.0, restitution=1.0, physicsClientId=cid)
    col = p.createCollisionShape(p.GEOM_CYLINDER, radius=COIN_R, height=COIN_H, physicsClientId=cid)
    U0 = 104.0 + du
    c_uv = np.array([U0, B.railV(U0)]) + NV * (COIN_R + 0.02)
    w_c = -3.0 - COIN_H / 2 - 0.02
    # 姿態：軸沿 Z；繞軌道方向小傾角（頂部往後靠 #26 → 往 +W' 即 -Z）
    q_tilt = p.getQuaternionFromAxisAngle([TV[0], TV[1], 0.0], math.radians(tilt))
    coin = p.createMultiBody(COIN_M, col, basePosition=[c_uv[0], c_uv[1], Z(w_c)], baseOrientation=q_tilt,
                             physicsClientId=cid)
    p.changeDynamics(coin, -1, lateralFriction=mu, restitution=e, rollingFriction=0.0, spinningFriction=0.0,
                     linearDamping=0.0, angularDamping=0.0, maxJointVelocity=20000.0, physicsClientId=cid)
    vel = TV * v0 * 1000.0
    p.resetBaseVelocity(coin, [vel[0], vel[1], 0.0], [0.0, 0.0, v0 * 1000.0 / COIN_R + spin], physicsClientId=cid)
    beam = geo['beam']
    n = int(T_MAX / DT)
    blocked_prev = False; pulses = []; t_on = None
    touched = set(); outcome = 'timeout'; still = 0.0
    minV_wall = 1e9; maxW = -1e9
    path = []
    for i in range(n):
        p.stepSimulation(physicsClientId=cid)
        t = (i + 1) * DT
        pos, orn = p.getBasePositionAndOrientation(coin, physicsClientId=cid)
        U, V, W = pos[0], pos[1], -pos[2]
        if i % 15 == 0:
            Rm = p.getMatrixFromQuaternion(orn)
            ax = (Rm[2], Rm[5], -Rm[8])       # 硬幣軸（法向）在 (U,V,W')
            path.append((round(t, 4), round(U, 2), round(V, 2), round(W, 2), round(ax[0], 3), round(ax[1], 3), round(ax[2], 3)))
        if W > 0.5 and U < 112.0:
            minV_wall = min(minV_wall, V)
        bl = beam_blocked(pos, orn, beam)
        if bl and not blocked_prev:
            t_on = t
        if (not bl) and blocked_prev:
            pulses.append((t_on, t))
        blocked_prev = bl
        if i % 6 == 0:
            for cp in p.getContactPoints(bodyA=coin, physicsClientId=cid):
                tag = bodies.get(cp[2], '?')
                if tag.startswith('S1_') or tag.startswith('S5_') or tag.startswith('E_'):
                    touched.add(tag)
        lv, av = p.getBaseVelocity(coin, physicsClientId=cid)
        sp = math.sqrt(sum(x * x for x in lv)); sa = math.sqrt(sum(x * x for x in av))
        if W > 0 and V > float(B.exitV(min(max(W, 0), 29))) + 3.0:
            outcome = 'exit'; break
        if U > 141.0 and W < 0:
            outcome = 'passed'; break
        if U < 104.0 and W > 0:
            outcome = 'cavity'; break
        if sp < 8.0 and sa < 2.0 and W > -1.0:
            still += DT
            if still > 0.25:
                outcome = 'stuck'; break
        else:
            still = 0.0
    if blocked_prev:
        pulses.append((t_on, t))
    p.disconnect(cid)
    # 去抖：間隔 < 3 ms 的脈衝合併
    merged = []
    for a, b in pulses:
        if merged and a - merged[-1][1] < 0.003:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return dict(variant=variant, v0=v0, mu=mu, e=e, du=du, tilt=tilt, spin=spin, th=COIN_H, outcome=outcome,
                pulses=len(merged), raw_pulses=len(pulses),
                widths_ms=[round((b - a) * 1000, 2) for a, b in merged],
                touched=sorted(touched), minV_wall=(None if minV_wall > 1e8 else round(minV_wall, 2)),
                t_end=round(t, 3), path=path)


def geo_for(Dd_over=None):
    import params as PR, copy
    M, Dd = copy.deepcopy(PR.MOD), copy.deepcopy(PR.DES)
    if Dd_over:
        for k, v in Dd_over.items():
            (M if k in M else Dd)[k] = v
    g = DS.build(M, Dd)
    g['s5_up'] = S5UP
    g['s5_down'] = S5DN
    g['s5_center'] = S5CE
    return g


S5UP = S5DN = S5CE = None


def main(quick=False, variants=None, over=None):
    global S5UP, S5DN, S5CE
    S5UP = B.s5_boxes('up'); S5DN = B.s5_boxes('down'); S5CE = B.s5_boxes('center')
    geo = geo_for(over)
    grid = list(itertools.product((0.15, 0.25, 0.35, 0.5), (0.25, 0.35, 0.45), (0.2, 0.5), (0.0, 2.5), (1.0, 4.0)))
    rng = np.random.default_rng(7)
    spins = rng.uniform(-6, 6, len(grid))
    variants = variants or ['Z', 'A', 'B', 'C', 'D', 'E']
    if quick:
        grid = grid[::8]; spins = spins[::8]
    res = []
    t0 = time.time()
    for var in variants:
        for (v0, mu, e, du, tilt), sp in zip(grid, spins):
            res.append(run_one(var, geo, v0, mu, e, du, tilt, float(sp), 0))
        print(var, 'done', round(time.time() - t0, 1), 's', flush=True)
    return geo, res


def main_random(n, variants, over_list, seed=11):
    global S5UP, S5DN, S5CE
    S5UP = B.s5_boxes('up'); S5DN = B.s5_boxes('down'); S5CE = B.s5_boxes('center')
    rng = np.random.default_rng(seed)
    ics = [dict(v0=float(rng.uniform(0.12, 0.55)), mu=float(rng.uniform(0.2, 0.5)), e=float(rng.uniform(0.15, 0.6)),
                du=float(rng.uniform(-1.0, 4.0)), tilt=float(rng.uniform(0.0, 5.0)), spin=float(rng.uniform(-8, 8)),
                th=float(rng.uniform(1.5, 1.85))) for _ in range(n)]
    res = []
    for var, over, tag in zip(variants, over_list, [None] * len(variants)):
        geo = geo_for(over)
        for ic in ics:
            r = run_one(var, geo, ic['v0'], ic['mu'], ic['e'], ic['du'], ic['tilt'], ic['spin'], 0, ic['th'])
            r['over'] = over
            res.append(r)
        print(var, over, 'done', flush=True)
    return res


def summarize(res):
    out = {}
    for var in sorted(set(r['variant'] for r in res)):
        R = [r for r in res if r['variant'] == var]
        fell = [r for r in R if r['outcome'] in ('exit', 'stuck', 'timeout', 'cavity')]
        n = len(R)
        d = dict(n=n,
                 exit=sum(r['outcome'] == 'exit' for r in R),
                 stuck=sum(r['outcome'] in ('stuck', 'timeout') and r['t_end'] > 0 for r in R if r['outcome'] != 'exit'),
                 passed=sum(r['outcome'] == 'passed' for r in R),
                 cavity=sum(r['outcome'] == 'cavity' for r in R),
                 count1=sum(r['pulses'] == 1 for r in fell),
                 count0=sum(r['pulses'] == 0 for r in fell),
                 count2p=sum(r['pulses'] >= 2 for r in fell),
                 touch_S1=sum(any(t.startswith('S1_') for t in r['touched']) for r in fell),
                 touch_cap=sum('S1_cap' in r['touched'] for r in fell),
                 touch_arm=sum('S1_front_arm' in r['touched'] for r in fell),
                 touch_S5=sum(any(t.startswith('S5_') for t in r['touched']) for r in fell),
                 touch_E=sum(any(t.startswith('E_') for t in r['touched']) for r in fell),
                 minV_wall=min([r['minV_wall'] for r in R if r['minV_wall'] is not None] or [None]),
                 width_ms=(lambda w: [round(min(w), 2), round(float(np.median(w)), 2), round(max(w), 2)] if w else None)(
                     [x for r in fell if r['pulses'] == 1 for x in r['widths_ms']]),
                 fell=len(fell))
        out[var] = d
    return out


if __name__ == '__main__':
    quick = '--quick' in sys.argv
    over = None; tag = ''
    for a in sys.argv[1:]:
        if a.startswith('--over='):
            over = json.loads(a[7:]); tag = '_' + '_'.join(f'{k}{v}' for k, v in over.items())
    vs = None
    for a in sys.argv[1:]:
        if a.startswith('--var='):
            vs = list(a[6:])
    geo, res = main(quick, vs, over)
    S = summarize(res)
    lines = []
    names = dict(Z='Z 只有牆（無模組）', A='A 卡匣、無帽、無 S5 翼', B='B 卡匣＋導流帽、無 S5 翼',
                 C='C 卡匣、無帽、S5 翼朝上游', D='D 卡匣＋導流帽、S5 翼朝上游', E='E 角度 2 導流坡（參考）')
    for k, d in S.items():
        lines.append(f"{names[k]}: n={d['n']} 落入={d['fell']} 出口={d['exit']} 卡住/逾時={d['stuck']} 滾過={d['passed']} 進空腔={d['cavity']} | "
                     f"脈衝 1 次={d['count1']} 0 次（漏）={d['count0']} ≥2 次（重複）={d['count2p']} | "
                     f"碰 S1={d['touch_S1']}（前臂 {d['touch_arm']}、帽 {d['touch_cap']}） 碰 S5={d['touch_S5']} 碰 E={d['touch_E']} | "
                     f"遮光 ms 最小/中位/最大={d['width_ms']} | 牆邊最高 V={d['minV_wall']}")
    txt = '\n'.join(lines)
    print(txt)
    fn = ('sim_quick' if quick else 'sim') + tag
    json.dump(dict(summary=S, runs=res), open(f'{fn}.json', 'w'), ensure_ascii=False)
    open(f'{fn}_out.txt', 'w').write(txt + '\n')

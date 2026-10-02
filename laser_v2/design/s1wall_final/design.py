"""S1 最終規格：所有新增／修改幾何（shapely）。全部由 params 推導，改參數重跑即可。
平面約定：
  (W',V) 平面零件（#13R、S1-B、S1-C、S1-H、S1-K）用座標 (W', V)；
  (U,V)  平面零件（#26、#37、S1-F、S1-P）用座標 (U, V)。
"""
import math, copy
import numpy as np
from shapely.geometry import Polygon, box, Point, MultiPolygon
from shapely.ops import unary_union
import base as B
import params as PR

T = 3.0


def rect(a0, a1, b0, b1):
    return box(min(a0, a1), min(b0, b1), max(a0, a1), max(b0, b1))


def circ(u, v, d, n=36):
    return Point(u, v).buffer(d / 2, n // 4)


def build(M=None, Dd=None):
    M = copy.deepcopy(PR.MOD if M is None else M)
    Dd = copy.deepcopy(PR.DES if Dd is None else Dd)
    D = PR.derived(M, Dd)
    g = PR.GEO
    ct, co, cp, fit = Dd['c_tab'], Dd['c_opt'], Dd['c_pcb'], Dd['fit']
    U_out, U_in = g['U13_out'], g['U13_in']
    W37, W37o = g['W37'], g['W37_out']
    out = dict(D=D, M=M, Dd=Dd)
    fa, ba, av = D['front_arm'], D['back_arm'], D['arm_v']
    pw0, pw1 = D['pcb_w']; pv0, pv1 = D['pcb_v']
    Ub0, Up = D['U_pcb_back'], D['U_pcb']

    # ---------------- 模組（組裝座標盒：U0,U1,V0,V1,W0,W1） ----------------
    hdr_v = (pv0 + (M['pcb_W'] - 7.62) / 2, pv0 + (M['pcb_W'] + 7.62) / 2)
    out['mod'] = dict(
        pcb=(Ub0, Up, pv0, pv1, pw0, pw1),
        comp=(Up, D['U_comp'], pv0, av[0], pw0, pw1),                 # 元件區（保守：本體以外整片）
        solder=(D['U_solder'], Ub0, pv0, pv1, pw0, pw1),
        body=(Up, D['U_sb'], av[0], av[1], fa[0], ba[1]),
        front_arm=(Up, D['U_tip'], av[0], av[1], fa[0], fa[1]),
        back_arm=(Up, D['U_tip'], av[0], av[1], ba[0], ba[1]),
        header=(Up, Up + 19.5, hdr_v[0], hdr_v[1], ba[1], pw1),  # 短端直立排針（塑膠座 2.5）＋杜邦母頭 14＋線彎 3
    )
    out['beam'] = dict(U=D['Ub'], V=D['Vb'], w0=D['wa'], w1=D['wb'])

    # ---------------- S1-H 前臂導流帽（(W',V) 剖面三角形，沿 U 疊 cap_layers 片） ----------------
    Vr = D['cap_Vr']
    cap_WV = Polygon([(fa[0], av[0]), (fa[0], Vr), (fa[1], av[0])])
    out['S1H_WV'] = cap_WV
    nl = Dd['cap_layers']
    out['S1H_U'] = [(D['U_sb'] + k * T, D['U_sb'] + (k + 1) * T) for k in range(nl)]
    out['cap_on'] = bool(Dd['cap'])
    out['cap_slope_deg'] = B.slope_deg(fa[1] - fa[0], av[0] - Vr)

    # ---------------- S1-B 座塊（牆槽內 U104.875~107.875） ----------------
    bv0, bv1 = pv0, pv1 - 1.0
    bw0 = pw0
    tabB_v = (bv0, bv0 + 6.0)
    sB = unary_union([rect(bw0, W37, bv0, bv1), rect(W37, W37o + T, tabB_v[0], tabB_v[1])])
    reliefB = rect(bw0 + 2.0, W37 - 3.0, bv0 + 3.0, bv1 - 2.0)      # 焊點讓位（>1 mm 泡棉膠厚的焊點才用到）；四邊料 2.0/3.0/3.0/2.0
    out['S1B_WV'] = sB.difference(reliefB)
    out['S1B_relief'] = reliefB
    out['tabB_v'] = tabB_v

    # ---------------- #13R 牆槽（開向 #37） ----------------
    wall_slot = rect(bw0 - 0.5, W37 + 1.0, bv0 - 0.2, bv1 + 0.2)
    out['wall_slot_WV'] = wall_slot

    # ---------------- S1-C 座板（空腔側 U101.875~104.875） ----------------
    cv0, cv1 = bv0 - 3.2, Dd['s1c_v1']
    cw0 = 0.6
    a, b = Dd['tabC_front_v']
    tabC = Polygon([(cw0, a), (cw0 - 2.0, a + 0.6), (cw0 - 2.6, a + 1.0), (cw0 - 2.6, b - 1.0),
                    (cw0 - 2.0, b - 0.6), (cw0, b)])
    tabC_back_v = tabB_v                         # 與 S1-B 後榫同 V：兩支並排＝6 mm 厚的一支，背蓋上合併成一個槽
    sC = unary_union([rect(cw0, W37, cv0, cv1), tabC, rect(W37, W37o + T, tabC_back_v[0], tabC_back_v[1])])
    out['S1C_WV'] = sC
    out['tabC_back_v'] = tabC_back_v
    out['S1C_v'] = (cv0, cv1)
    U_car = (U_out - T, U_out)

    # ---------------- #37 窗：卡匣通過 #37 時的 (U,V) 輪廓聯集 ----------------
    v_top_mod = (Vr if Dd['cap'] else av[0])
    parts = [
        rect(U_car[0] - 0.3, U_car[1], cv0 - 0.3, cv1 + 0.3),                       # S1-C
        rect(U_out, U_in, bv0 - 0.3, bv1 + 0.3),                                     # S1-B
        rect(min(U_in, Ub0) - 0.1, Up + co, pv0 - cp, pv1 + cp),                     # PCB＋泡棉膠
        rect(D['U_solder'] - 0.2, Ub0, pv0 - cp, pv1 + cp),                          # PCB 背面焊點（後臂腳在 W'29~36）
        rect(Up, Up + max(M['comp_h'] + co, T + 0.4), pv0 - cp, pv1 + cp),          # 元件帶
        rect(Up, D['U_tip'] + co, v_top_mod - co, av[1] + co),                      # 本體＋臂＋導流帽
    ]
    win = unary_union(parts).simplify(0.001)
    out['win37_UV'] = win
    out['win37_parts'] = parts

    # ---------------- S1-P 帽通道填塊（貼背蓋前面，W'29~32）、S1-K 元件帶填塊（可選） ----------------
    if Dd['cap']:
        # 左緣（U 小）齊背蓋元件帶缺口邊 U_comp+c_opt，下緣齊背蓋缺口 V(臂頂−c_opt)：講師把它塞進背蓋缺口的內角黏上
        out['S1P_UV'] = rect(D['U_comp'] + co, D['U_tip'] + co - fit, Vr - co + fit, av[0] - co)
    else:
        out['S1P_UV'] = None
    kb_u = (Up + 0.2, Up + 0.2 + T)
    k_v1 = (Vr - co + fit) if Dd['cap'] else (av[0] - co)
    out['S1K_UV'] = rect(kb_u[0], kb_u[1], pv0 - cp + 0.15, k_v1 - 0.15) if Dd.get('comp_band_free') else None

    # ---------------- S1-F 背蓋（貼 #37 外面 W'32~35） ----------------
    fb = win.bounds
    cover = rect(fb[0] - 10.0, fb[2] + 4.0, fb[1] - 3.5, Dd['cover_v1'])
    cut_mod = unary_union([
        rect(U_in - 0.1, Up + co, pv0 - cp, pv1 + cp),                               # PCB＋泡棉膠（V<70.4 段焊點 ≤1.1 由泡棉膠厚度吸收）
        (rect(Up, D['U_comp'] + co, pv0 - cp, av[0]) if not Dd.get('comp_band_free') else Polygon()),   # 元件面零件（W'32~35 段）
        rect(Up, D['U_tip'] + co, av[0] - co, av[1] + co),                           # 本體＋後臂
        box(min(U_in, D['U_solder']) - 0.2, av[0] - co, 400, 400),                   # 後臂以下整塊去掉（不留細條）
    ])
    slotsF = unary_union([rect(U_car[0] - ct, U_car[1] + ct, tabC_back_v[0] - ct, tabC_back_v[1] + ct),
                          rect(U_out - ct, U_in + ct, tabB_v[0] - ct, tabB_v[1] + ct)])
    sF = cover.difference(cut_mod).difference(slotsF)
    sF = sF.buffer(-0.7, join_style=2).buffer(0.7, join_style=2).intersection(cover)
    holes = [(fb[0] - 5.0, fb[1] + 2.0), (fb[0] - 5.0, Dd['cover_v1'] - 4.5)]
    for (u, v) in holes:
        sF = sF.difference(circ(u, v, Dd['screw_hole_cover']))
    out['S1F_UV'] = sF
    out['S1F_rect'] = cover
    out['screws_UV'] = holes

    # ---------------- #13R（(W',V) 平面） ----------------
    o13 = B.ORIG13_WV()
    orig = Polygon(o13.exterior)
    orig_holes = [Polygon(h) for h in o13.interiors]
    ext = rect(0.0, W37, Dd['wall_top'], 76.2)
    tl26, tl37 = Dd['tab_len_26'], Dd['tab_len_37']
    tabs = [rect(-tl26, 0.0, a, b) for a, b in Dd['tabs_front']] + [rect(W37, W37 + tl37, a, b) for a, b in Dd['tabs_back']]
    wall = unary_union([orig, ext] + tabs).difference(wall_slot)
    if Dd['corner_fix']:
        notch = rect(W37, W37o + 0.2, 77.0, Dd['corner_fix_V'])
        wall = wall.difference(notch)
        out['corner_notch_WV'] = notch
    for h in orig_holes:
        wall = wall.difference(h)
    out['wall13R_WV'] = wall
    out['orig13_WV'] = o13

    # ---------------- #26 新槽 ----------------
    s26 = {f'F{i+1}': rect(U_out - ct, U_in + ct, a - ct, b + ct) for i, (a, b) in enumerate(Dd['tabs_front'])}
    s26['C'] = rect(U_car[0] - ct, U_car[1] + ct, Dd['tabC_front_v'][0] - ct, Dd['tabC_front_v'][1] + ct)
    out['slots26_UV'] = s26

    # ---------------- #37 新槽與螺絲孔 ----------------
    out['slots37_UV'] = {f'B{i+1}': rect(U_out - ct, U_in + ct, a - ct, b + ct) for i, (a, b) in enumerate(Dd['tabs_back'])}
    out['holes37_UV'] = [circ(u, v, Dd['screw_hole_37']) for (u, v) in holes]
    return out


# ---------------- 局部座標（給產生器） ----------------
def local_WV(g, W0=None, V0=None):
    """(W',V) 平面新零件 → 局部 (x,y)=(W'-W0, V-V0)；上面（z=0，雕刻面）朝 −U（空腔側）。"""
    from shapely import affinity
    b = g.bounds
    W0 = b[0] if W0 is None else W0
    V0 = b[1] if V0 is None else V0
    return affinity.translate(g, -W0, -V0), (W0, V0)


def local_UV(g, U0=None, V0=None):
    """(U,V) 平面新零件 → 局部 (x,y)=(U-U0, V-V0)＝從機身背面看；上面朝 +W'（朝後、看得到）。"""
    from shapely import affinity
    b = g.bounds
    U0 = b[0] if U0 is None else U0
    V0 = b[1] if V0 is None else V0
    return affinity.translate(g, -U0, -V0), (U0, V0)


if __name__ == '__main__':
    o = build()
    for k in ('S1B_WV', 'S1C_WV', 'S1H_WV', 'win37_UV', 'S1F_UV', 'S1P_UV', 'S1K_UV', 'wall13R_WV'):
        gm = o[k]
        if gm is None:
            continue
        print(k, gm.geom_type, 'bounds', [round(v, 3) for v in gm.bounds], 'area', round(gm.area, 1),
              'parts', len(getattr(gm, 'geoms', [gm])))
    print('beam', o['beam'], 'cap slope', round(o['cap_slope_deg'], 1), 'cap U', o['S1H_U'])
    for k, v in o['mod'].items():
        print(' mod', k, [round(x, 3) for x in v])

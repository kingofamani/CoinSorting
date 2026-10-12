"""ebox_final 幾何：顯示器（#24 左上，沿用 D2）、#24/#26/#5/#37 修改、電子盒 7 片（電池帶版）、
盒內元件、線路、硬幣區。build(pr) 回傳 SimpleNamespace，sens.py 會用改過的 pr 重建。"""
from types import SimpleNamespace as NS
import copy
from base import *
import params as PR0

CTJ = json.load(open(CT + '/geometry_final.json'))

# ------------------------------------------------------------------ 原始零件（不隨參數變）
G24 = asm_geom('#24'); G26 = asm_geom('#26'); G37 = asm_geom('#37')
H24 = holes_asm('#24'); H26 = holes_asm('#26')
SLOT24 = max(H24, key=lambda h: h.area)                       # 斜槽
ENG = {k: FR['#24'].to_asm(v[:, 0], v[:, 1], 0)[:, :2] for k, v in engrave_pts('#24').items()}
HULL = lambda s, d=(0, 0): affinity.translate(MultiPoint([tuple(p) for p in ENG[s]]).convex_hull, *d)
LOGO_SRC = 'path1-5-9'
_logo_h = HULL(LOGO_SRC)
LOGO_HOLES = [h for h in H24 if h.area < 6 and _logo_h.buffer(0.5).contains(h)]
LOGO = unary_union([_logo_h] + LOGO_HOLES)
MV = CTJ['parts']['engrave_moves_24']                          # crosstrack_final 已搬的「5」「1」
ENG_NEW = {'「50」': HULL('text1-6-4'), '「10」': HULL('text2-1-3'),
           '「5」(crosstrack 新位)': HULL('text11-4-1', (MV['text11-4-1']['dU'], MV['text11-4-1']['dV'])),
           '「1」(crosstrack 新位)': HULL('text16-7-2', (MV['text16-7-2']['dU'], MV['text16-7-2']['dV']))}
CT_WIN24 = unary_union([Polygon(CTJ['stations'][s]['win24']['UV']) for s in ('S5', 'S10', 'S50')])
OTHER_H24 = [h for h in H24 if h is not SLOT24 and not any(h.equals(x) for x in LOGO_HOLES)]
# 隔板：crosstrack_final v2 外形（(W',V)）
DIV_V2 = {pid: Polygon(CTJ['stations'][st]['divider']['new_outline']['WV'])
          for st, pid in (('S5', '#7'), ('S10', '#6'), ('S50', '#5'))}
DIV_V2_LOCAL = {pid: Polygon(CTJ['stations'][st]['divider']['new_outline']['local'])
                for st, pid in (('S5', '#7'), ('S10', '#6'), ('S50', '#5'))}
DIV_U = {pid: FR[pid].plane()[1:] for pid in ('#7', '#6', '#5')}
# #12（斜放）在 (W',V) 的外包
_e12 = np.array(P['#12'].geom.exterior.coords)
_A = np.vstack([FR['#12'].to_asm(_e12[:, 0], _e12[:, 1], z) for z in (0.0, 3.0)])
G12_WV = MultiPoint([tuple(p) for p in _A[:, [2, 1]]]).convex_hull
G21_WV = FR['#21'].geom_asm(P['#21'].geom, 1.5, ('W', 'V'))
G36_WV = FR['#36'].geom_asm(P['#36'].geom, 1.5, ('W', 'V'))
G13_WV = FR['#13'].geom_asm(P['#13'].geom, 1.5, ('W', 'V'))

# 硬幣區（同 D2 的模型；W'37 內面取 29.0）
COIN_D = {'1': 20.0, '5': 22.0, '10': 26.0, '50': 28.0}
CHUTE_U = {'1': (107.875, 135.876), '5': (138.876, 165.626), '10': (168.626, 198.376), '50': (201.376, 243.0)}
EXIT = lambda W: 98.0 - 16.0 * W / 29.0
OPEN = {}
for h in sorted([h for h in H26 if h.area > 400 and h.bounds[0] > 110], key=lambda h: h.bounds[0]):
    OPEN[['1', '5', '10', '50'][len(OPEN)]] = h


def coin_zones():
    Z = [Solid('斜槽滾動區（#24 板厚內）', 'W', SLOT24, (-6.0, -3.0), 'coin')]
    for c, op in OPEN.items():
        Z.append(Solid(f'{c} 元開口（#26 板厚內）', 'W', op, (-3.0, 0.0), 'coin'))
        Z.append(Solid(f'{c} 元翻倒掃掠（開口×W\'0~D）', 'W', op, (0.0, COIN_D[c]), 'coin'))
        u0, u1 = CHUTE_U[c]; vt = op.bounds[1]
        Z.append(Solid(f'{c} 元滑道落下區（保守：V≥開口頂 {vt:.1f} 整個深度）', 'U',
                       Polygon([(0.0, vt), (29.0, vt), (29.0, EXIT(29.0)), (0.0, EXIT(0.0))]), (u0, u1), 'coin'))
    return Z


def coin_arcs(step=2.0, shift=10.0):
    """翻倒弧＋落下（沿 U 分片；每片用 max(開口右端, U−shift) 的唇高）。"""
    out = []
    for c, op in OPEN.items():
        Dc = COIN_D[c]; U0 = op.bounds[0]; u0, u1 = CHUTE_U[c]
        for ua in np.arange(u0, u1, step):
            ub = min(ua + step, u1)
            Vlip = float(F.rail_V(max(U0, ua - shift))) - 1.31 / 0.94
            ws = np.linspace(0, 29.0, 59)
            top = [(w, Vlip - math.sqrt(max(0.0, Dc ** 2 - w ** 2)) / 0.94) for w in ws]
            poly = Polygon(top + [(29.0, max(EXIT(29.0), Vlip)), (0.0, EXIT(0.0))]).buffer(0)
            out.append(Solid(f'{c} 元翻倒弧＋落下（U{ua:.0f}~{ub:.0f}）', 'U', poly, (ua, ub), 'coin'))
    return out


COIN = coin_zones()
COIN_ARC = coin_arcs()


# ================================================================== build
def build(pr=PR0, logo_search=False):
    M = NS()
    T = pr.T
    D = dict(pr.DISP)
    M.D = D
    M.Vp = None
    # ---------------- 顯示器
    w, h = D['pcb_w'], D['pcb_h']
    Ur = pr.DISP_UR
    if pr.DISP_VP is not None:
        Vp = pr.DISP_VP
    elif D['use_screws']:      # 上排 M2 孔到 #24 頂邊 V4 料寬 ≥ MIN_WEB；PCB 上緣至少 V5（藏在頂邊下 1 mm）
        need = 4.0 + pr.MIN_WEB + D['hole_d'] / 2 + pr.C_SCREW + D['hole_dy'] - D['pcb_h'] / 2
        Vp = max(5.0, math.ceil(need * 2 - 1e-9) / 2)
    else:
        Vp = 5.0
    Uc, Vc = Ur + w / 2, Vp + h / 2
    Wf = -3.0; Wb = Wf + D['pcb_t']
    g = {}
    g['PCB'] = (Ur, Ur + w, Vp, Vp + h, Wf, Wb)
    bu, bv = Uc - D['body_dx'], Vc + D['body_dy']
    g['LED 塊'] = (bu - D['body_w'] / 2, bu + D['body_w'] / 2, bv - D['body_h'] / 2, bv + D['body_h'] / 2, Wf - D['body_H'], Wf)
    i = D['back_inset']
    g['背面零件'] = (Ur + i, Ur + w - i, Vp + i, Vp + h - i, Wb, Wb + D['back_h'])
    Vh = Vc + D['hdr_dy']; half = D['hdr_pins'] * D['hdr_pitch'] / 2
    nW = D['hdr_pins'] * pr.WIRE_D
    pc = Wb + D['pin_h']
    if D['hdr_mode'] == 'RA':
        g['排針座'] = (Ur, Ur + D['hdr_body'], Vh - half, Vh + half, Wb, Wb + D['hdr_body'])
        u1 = Ur - D['dup_gap']; u0 = u1 - D['dup_len']
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
    g['線：上升段'] = (riser[0], riser[1], V_run0, Vh + half, -3.0, 1.4)
    cu = pr.CABLE_U
    g['線：#24 背面水平段'] = (cu - nW / 2, riser[1], V_run0, V_run1, -3.0, -1.4)
    holes = [(Uc + sx * D['hole_dx'], Vc + sy * D['hole_dy']) for sx in (-1, 1) for sy in (-1, 1)] if D['use_screws'] else []
    rn = pr.NUT_M2['d_circ'] / 2
    for k, (u, v) in enumerate(holes):
        g[f'M2 螺帽{k + 1}'] = (u - rn, u + rn, v - rn, v + rn, Wb, Wb + pr.NUT_M2['t'])
        tip = -6.0 + pr.SCREW_M2['L']
        g[f'M2 螺絲尖{k + 1}'] = (u - 1.0, u + 1.0, v - 1.0, v + 1.0, Wb + pr.NUT_M2['t'], tip)
    M.Vp = Vp
    M.disp = g; M.Uc, M.Vc, M.Vh, M.half, M.holes, M.riser, M.L_B = Uc, Vc, Vh, half, holes, riser, L_B
    M.disp_solids = [boxsolid(n, *bx, kind='disp') for n, bx in g.items()]
    hd = pr.SCREW_M2['head_d'] / 2
    M.screw_heads = [Point(u, v).buffer(hd, 32) for u, v in holes]
    M.head_solids = [Solid(f'M2 螺絲頭{k + 1}（#24 正面）', 'W', hh, (-6.0 - pr.SCREW_M2['head_h'], -6.0), 'disp')
                     for k, hh in enumerate(M.screw_heads)]
    # ---------------- #24
    l0, l1, v0, v1 = g['LED 塊'][:4]
    M.WIN = rect(l0 - pr.C_WIN, l1 + pr.C_WIN, v0 - pr.C_WIN, v1 + pr.C_WIN)
    M.SCREW_HOLES = [Point(u, v).buffer(D['hole_d'] / 2 + pr.C_SCREW, 32) for u, v in holes]
    keep = unary_union([M.WIN, SLOT24, CT_WIN24, rect(0, 113, 0, 114)] + M.screw_heads + list(ENG_NEW.values()))
    outer24 = Polygon(G24.exterior)
    notch_see = None  # 下方 #26 缺口算完後再判斷

    # ---------------- #26 缺口
    hu = [u for u, v in holes] or [Ur + w / 2]; hv = [v for u, v in holes] or [Vp + h / 2]
    rr = rn if holes else 0.0
    A_u0 = min(Ur, min(hu) - rr) - pr.C_NOTCH; A_u1 = max(Ur + w, max(hu) + rr) + pr.C_NOTCH
    A_v1 = max(Vp + h, max(hv) + rr) + pr.C_NOTCH
    M.NOTCH_A = rect(A_u0, A_u1, 9.0, A_v1)
    if D['hdr_mode'] == 'RA':
        M.NOTCH_B = rect(Ur - L_B - pr.C_NOTCH, A_u0 + 0.01, 9.0, Vh + half + pr.C_NOTCH)
        M.NOTCH26 = unary_union([M.NOTCH_A, M.NOTCH_B])
    else:
        M.NOTCH_B = None; M.NOTCH26 = M.NOTCH_A
    M.G26_V2 = G26.difference(M.NOTCH26)
    see = unary_union([M.NOTCH26, rect(*g['線：上升段'][:4]), rect(*g['線：#24 背面水平段'][:4])])
    # ---------------- Logo
    lshift = pr.LOGO_SHIFT

    def logo_eval(dU, dV):
        L = affinity.translate(LOGO, dU, dV)
        lh = unary_union([affinity.translate(x, dU, dV) for x in LOGO_HOLES])
        inside = outer24.buffer(-3).contains(L)
        return dict(clear=L.distance(keep), hole_clear=lh.distance(unary_union(OTHER_H24)),
                    see=lh.intersection(see).area, inside=inside, L=L, lh=lh)
    M.logo = logo_eval(*lshift); M.logo_alt = logo_eval(*pr.LOGO_SHIFT_ALT)
    M.LOGO_SHIFT = lshift
    if logo_search:
        best = []
        for dU in np.arange(-60, 5, 0.25):
            for dV in np.arange(-5, 25, 0.25):
                e = logo_eval(dU, dV)
                if e['inside'] and e['clear'] >= 3.0 and e['hole_clear'] >= 2.0 and e['see'] == 0:
                    best.append((round(e['clear'], 2), -math.hypot(dU, dV), dU, dV))
        best.sort(reverse=True)
        M.logo_search = best[:12]
    G24v = G24
    for x in LOGO_HOLES:
        G24v = G24v.union(x.buffer(0.01))
    M.G24_V2 = G24v.difference(unary_union([M.logo['lh'], M.WIN] + M.SCREW_HOLES))
    # ---------------- #5（crosstrack v2 再減前上角）
    M.DIV5_CUT_W = g['背面零件'][5] + pr.C_DIV                  # W'
    M.DIV5_CUT_V = A_v1
    cut_wv = rect(-7.0, M.DIV5_CUT_W, 13.0, M.DIV5_CUT_V)
    M.DIV5_WV = DIV_V2['#5'].difference(cut_wv)
    M.DIV5_LOCAL = DIV_V2_LOCAL['#5'].difference(rect(-1.0, M.DIV5_CUT_W + 6.0, -1.0, M.DIV5_CUT_V - 14.0))
    # ---------------- 電子盒
    BX = pr.BOX; HK = pr.HOOK; BD = pr.BOARD; Bt = pr.BATT; SW = pr.SWITCH
    U_L0 = BX['U_WL']; U_L1 = U_L0 + T
    U_R0 = BX['U_WR']; U_R1 = U_R0 + T
    Vt = BX['V_top']; Wfr = BX['W_front']; Wbk = BX['W_back']
    W_B0 = 32.0 + BX['gap']; W_B1 = W_B0 + T
    # 電池帶
    Lp, Wp, Tp = max(Bt['L'], 48.5), max(Bt['W'], 26.5), max(Bt['Tk'], 17.5)   # 口袋用 9V 標準最大值，實品較小不縮
    V_bat0 = Vt - Bt['proud']; V_bat1 = V_bat0 + Tp
    V_F0 = V_bat1 + Bt['c']; V_F1 = V_F0 + T                   # 電池架 EB-F
    W_bat0 = 32.0 + 0.3; W_bat1 = W_bat0 + Wp
    W_S0 = W_bat1 + 0.3; W_S1 = W_S0 + T                        # 電池後擋 EB-S
    U_bat1 = U_R0 - Bt['c']; U_bat0 = U_bat1 - Lp
    U_E1 = U_bat0 - Bt['clip']; U_E0 = U_E1 - T                 # 電池端擋 EB-E
    W_F1 = W_S1 + 2.9                                           # EB-F 後緣（EB-S 榫槽後留 2.8）
    V_T0, V_T1 = Vt, Vt + T                                     # 頂板
    # 主板
    U_bd1 = U_R0 - BD['c_end']; U_bd0 = U_bd1 - BD['L']
    V_bd0 = V_F1 + BD['c_top']; V_bd1 = V_bd0 + BD['W']
    V_B0 = V_F1; V_B1 = V_bd1 + BD['c_bot']                             # 底板 EB-B（上緣頂住電池架下面）
    Vb = V_B1                                                   # 盒底
    W_bd0 = W_B1 + BD['standoff']; W_bd1 = W_bd0 + BD['t']
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
    M.CABLE_NOTCH = rect(cu - cw / 2, cu + cw / 2, 2.0, 4.0 + cd)      # 上緣畫到板外 2 mm
    M.SENSOR_HOLE = rect(*pr.SENSOR_HOLE_37)
    M.G37_V2 = G37.difference(unary_union(M.SLOTS37 + [M.CABLE_NOTCH, M.SENSOR_HOLE]))

    def hooked_wall(w_back):
        out = rect(Wfr, w_back, Vt, Vb)
        for n0 in HK['levels']:
            neck = rect(HK['lip_back'], Wfr + 0.01, n0, n0 + HK['neck_h'])
            ch = HK['chamfer']; vlo = n0 + HK['neck_h'] + HK['lip_len']
            lip = Polygon([(HK['lip_W0'], n0), (HK['lip_back'], n0), (HK['lip_back'], vlo),
                           (HK['lip_W0'] + ch, vlo), (HK['lip_W0'], vlo - ch)])
            out = unary_union([out, neck, lip])
        return out
    slot_wv = lambda w0, w1, v0, v1, c=pr.C_TAB: rect(w0 - c, w1 + c, v0 - c, v1 + c)
    TAB_B_V = [(22.0, 32.0), (Vb - 12.0, Vb - 2.0)]           # EB-B 側榫（V）
    TAB_T_WL = (55.0, 65.0); TAB_T_WR = (61.0, 68.0)              # EB-T 端榫（W'）
    TAB_S_V = (10.0, 16.0)                                        # EB-S 端榫（V）
    TAB_F_W = (40.0, 50.0)                                        # EB-F 端榫（W'，只進 EB-E）
    TAB_E_W = (62.0, 68.0)                                        # EB-E 頂榫（W'，進 EB-T）
    TAB_SF_U = [(U_bat0 + 4.0, U_bat0 + 14.0), (U_bat1 - 14.0, U_bat1 - 4.0)]   # EB-S 下榫（U，進 EB-F）
    M.tabs = dict(TAB_B_V=TAB_B_V, TAB_T_WL=TAB_T_WL, TAB_T_WR=TAB_T_WR, TAB_S_V=TAB_S_V, TAB_F_W=TAB_F_W,
                  TAB_E_W=TAB_E_W, TAB_SF_U=TAB_SF_U)
    sl_B = [slot_wv(W_B0, W_B1, a, b) for a, b in TAB_B_V]
    nT = lambda wr: rect(wr[0] - pr.C_TAB, wr[1] + pr.C_TAB, Vt - 1.0, V_T1 + pr.C_TAB)   # 頂緣開口缺口
    WLn = BX['wl_notch']
    WL_WV = hooked_wall(Wbk).difference(unary_union(sl_B + [nT(TAB_T_WL), rect(WLn[0] - 1.0, WLn[1], WLn[2], WLn[3])]))
    # 服務窗（USB＋DC 插頭外殼外包）
    dev_u1 = U_bd1 - BD['usb_inset']; dev_u0 = dev_u1 - BD['dev_len']
    dev_vc = V_bd0 + BD['usb_V_off']
    W_dev0 = W_bd1 + BD['hdr_h']; W_dev1 = W_dev0 + BD['dev_t']
    usb_wc = W_dev1 + BD['usb_h'] / 2
    dc_vc = V_bd0 + BD['dc_V_off']; dc_wc = W_bd1 + BD['dc_h'] / 2
    c_sw = pr.SERVICE_WIN_C
    pv, pw = BD['usb_plug']; rdc = BD['dc_plug_d'] / 2
    M.SERVICE_WIN = unary_union([rect(dc_wc - rdc - c_sw, dc_wc + rdc + c_sw, dc_vc - rdc - c_sw, dc_vc + rdc + c_sw),
                                 rect(usb_wc - pw / 2 - c_sw, usb_wc + pw / 2 + c_sw, dev_vc - pv / 2 - c_sw, dev_vc + pv / 2 + c_sw)]).envelope
    M.WR_CABLE_NOTCH = rect(W_S1 + 2.9, Wbk + 1.0, 9.5, 16.5)     # 右牆後緣 DC 線出口
    WR_WV = hooked_wall(Wbk).difference(unary_union(sl_B + [nT(TAB_T_WR), slot_wv(W_S0, W_S1, *TAB_S_V), M.SERVICE_WIN,
                                                            M.WR_CABLE_NOTCH]))
    # EB-B（U,V）
    EBB = unary_union([rect(U_L1, U_R0, V_B0, V_B1)] + [rect(U_L0, U_L1, a, b) for a, b in TAB_B_V]
                      + [rect(U_R0, U_R1, a, b) for a, b in TAB_B_V])
    ins = BD['hole_inset']
    M.BOARD_HOLES = [(U_bd0 + ins, V_bd0 + ins), (U_bd1 - ins, V_bd0 + ins), (U_bd0 + ins, V_bd1 - ins), (U_bd1 - ins, V_bd1 - ins)]
    EBB = EBB.difference(unary_union([Point(u, v).buffer(BD['hole_d'] / 2, 32) for u, v in M.BOARD_HOLES]))
    # EB-T（U,W'）：開關區（W' top_W0~70）＋電池後方條（W'S0~70）
    W_T_front = BX['top_W0']
    EBT = unary_union([rect(U_L1, U_E1, W_T_front, Wbk), rect(U_E1 - 0.01, U_R0, W_S0, Wbk),
                       rect(U_L0, U_L1, *TAB_T_WL), rect(U_R0, U_R1, *TAB_T_WR)])
    M.SW_CUT = rect(SW['U0'], SW['U0'] + SW['cut_a'], SW['W0'], SW['W0'] + SW['cut_b'])
    EBT = EBT.difference(unary_union([M.SW_CUT, rect(U_E0 - pr.C_TAB, U_E1 + pr.C_TAB, TAB_E_W[0] - pr.C_TAB, TAB_E_W[1] + pr.C_TAB)]))
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
    # 防拔鍵（選用）：塞進上層槽上段
    n_top = HK['levels'][0]
    M.KEY_WV = unary_union([rect(29.0, 32.0, n_top - SLIDE + 0.1, n_top - 0.1), rect(25.5, 29.0, n_top - SLIDE - 2.0, n_top + 1.5)])
    M.BOX = [Solid('EB-WL 左牆', 'U', WL_WV, (U_L0, U_L1), 'box'),
             Solid('EB-WR 右牆', 'U', WR_WV, (U_R0, U_R1), 'box'),
             Solid('EB-B 主板底板', 'W', EBB, (W_B0, W_B1), 'box'),
             Solid('EB-T 頂板', 'V', EBT, (V_T0, V_T1), 'box'),
             Solid('EB-S 電池後擋', 'W', EBS, (W_S0, W_S1), 'box'),
             Solid('EB-F 電池架', 'V', EBF, (V_F0, V_F1), 'box'),
             Solid('EB-E 電池端擋', 'U', EBE, (U_E0, U_E1), 'box')]
    # ---------------- 盒內元件
    # GPIO 欄位（沿用 DevKit 38P 左排；USB 在 +U 端 → 用到的列在下）
    order = ['3V3', 'EN', 'VP', 'VN', '34', '35', '32', '33', '25', '26', '27', '14', '12', 'GND', '13', 'D2', 'D3', 'CMD', '5V']
    p1 = dev_u0 + BD['pin1_from_antenna']
    M.GPIO_U = {n: p1 + k * BD['pitch'] for k, n in enumerate(order)}
    gvs_vc = V_bd1 - BD['gvs_V_off']
    row_u0 = min(M.GPIO_U.values()) - 2.0; row_u1 = max(M.GPIO_U.values()) + 2.0
    Wgvs1 = W_bd1 + BD['male_h'] + BD['dup_len'] + BD['bend']
    C_ = {}
    C_['9V 電池'] = M.bat
    C_['電池扣（含線彎）'] = (U_E1 + 0.25, U_bat0, V_bat0 + 1.0, V_bat1 - 1.0, W_bat0 + 1.0, W_bat1 - 1.0)
    C_['擴展板 PCB'] = M.board
    C_['墊高螺帽＋螺絲區'] = (U_bd0, U_bd1, V_bd0, V_bd1, W_B1, W_bd0)
    C_['ESP32 開發板＋母座'] = (dev_u0, dev_u1, dev_vc - BD['dev_w'] / 2, dev_vc + BD['dev_w'] / 2, W_bd1, W_dev1 + BD['dev_comp'])
    C_['USB 座'] = (dev_u1 - 5.5, dev_u1 + 0.5, dev_vc - 4.0, dev_vc + 4.0, W_dev1, W_dev1 + BD['usb_h'])
    C_['DC 座'] = (U_bd1 - BD['dc_len'], U_bd1, dc_vc - BD['dc_d'] / 2, dc_vc + BD['dc_d'] / 2, W_bd1, W_bd1 + BD['dc_h'])
    C_['未用排針列（上）'] = (row_u0, row_u1, V_bd0 + BD['gvs_V_off'] - 3.81, V_bd0 + BD['gvs_V_off'] + 3.81, W_bd1, W_bd1 + 8.5)
    C_['用到的 GVS 列＋杜邦頭＋彎線（下）'] = (row_u0, row_u1, gvs_vc - 3.81, gvs_vc + 3.81, W_bd1, Wgvs1)
    C_['開關本體'] = (SW['U0'] - 1.0, SW['U0'] + SW['cut_a'] + 1.0, V_T1, V_T1 + SW['body_depth'], SW['W0'] - 0.5, SW['W0'] + SW['cut_b'] + 0.5)
    for k, (u, v) in enumerate(M.BOARD_HOLES):
        C_[f'M3 螺帽{k + 1}（底板前）'] = (u - 3.2, u + 3.2, v - 3.2, v + 3.2, W_B0 - 2.4, W_B0)
        C_[f'M3 螺絲尖{k + 1}'] = (u - 1.5, u + 1.5, v - 1.5, v + 1.5, W_B0 - 2.6, W_B0 - 2.4)
    M.CONTENTS = C_
    M.dev = (dev_u0, dev_u1, dev_vc, W_dev1)
    M.usb_c = (dev_u1, dev_vc, usb_wc); M.dc_c = (U_bd1, dc_vc, dc_wc)
    M.EN_BTN = [(dev_u1 - 4.0, dev_vc - BD['btn_dv']), (dev_u1 - 4.0, dev_vc + BD['btn_dv'])]
    M.USB_PLUG = (dev_u1, dev_u1 + 38.0, dev_vc - pv / 2, dev_vc + pv / 2, usb_wc - pw / 2, usb_wc + pw / 2)
    M.DC_PLUG = (U_bd1, U_bd1 + 40.0, dc_vc - rdc, dc_vc + rdc, dc_wc - rdc, dc_wc + rdc)
    # ---------------- 線路中心線（組裝座標）
    Wq = Wgvs1 - 2.0
    M.WIRES = {}
    M.WIRES['顯示器 4P（G14/G13/V/G）'] = np.array([
        (g['杜邦頭'][0], Vh, pc), (riser[0] + nW / 2, Vh, pc), (riser[0] + nW / 2, (V_run0 + V_run1) / 2, -2.2),
        (cu, (V_run0 + V_run1) / 2, -2.2), (cu, 7.6, -2.2), (cu, 7.6, 33.2), (cu, V_F1 - 1.0, 33.2),
        (cu, V_F1 - 1.0, Wq), (cu, gvs_vc, Wq), (M.GPIO_U['14'], gvs_vc, Wq)])
    hx = pr.SENSOR_HOLE_37; hc = ((hx[0] + hx[1]) / 2, (hx[2] + hx[3]) / 2)
    nv = ((WLn[2] + WLn[3]) / 2)
    bay_u = (U_L1 + U_bd0) / 2
    back = [(hc[0], hc[1], 33.2), (U_L0 - 3.0, nv, 33.2), (U_L1 + 1.0, nv, 37.0), (bay_u, nv, Wq), (bay_u, gvs_vc, Wq)]
    ct_front = {'S5': 137.580, 'S10': 167.177, 'S50': 199.846}
    for s, ubeam in ct_front.items():
        hu_ = ubeam - 16.0                                       # 排針在翼遠端（wing=up，往上游約 14~16）
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
    M.ct_seg_len = {}
    for k, v in M.WIRES.items():
        if k[:2] == 'S5' or k[:3] in ('S10', 'S50'):
            M.ct_seg_len[k] = float(np.sum(np.linalg.norm(np.diff(v[:7], axis=0), axis=1)))
    # 線路的實體近似（用於干涉）：每段做 1.4×5.6 的方管外包
    M.WIRE_SOLIDS = []
    for k, v in M.WIRES.items():
        for j in range(len(v) - 1):
            a, b = v[j], v[j + 1]
            lo = np.minimum(a, b) - 1.0; hi = np.maximum(a, b) + 1.0
            M.WIRE_SOLIDS.append((k, j, boxsolid(f'{k} 第{j + 1}段', lo[0], hi[0], lo[1], hi[1], lo[2], hi[2], 'wire')))
    M.pr = pr
    return M


if __name__ == '__main__':
    M = build(logo_search=True)
    print('LED 窗', [r2(v) for v in M.WIN.bounds], '螺絲孔', [(r2(u), r2(v)) for u, v in M.holes])
    print('#26 缺口 A', [r2(v) for v in M.NOTCH_A.bounds], 'B', [r2(v) for v in M.NOTCH_B.bounds] if M.NOTCH_B else None)
    print('#5 減除 W\'<=', r2(M.DIV5_CUT_W), 'V<=', r2(M.DIV5_CUT_V), '件數', 1 if M.DIV5_WV.geom_type == 'Polygon' else len(M.DIV5_WV.geoms))
    print('Logo 名目', M.LOGO_SHIFT, {k: (r2(v) if isinstance(v, float) else v) for k, v in M.logo.items() if k in ('clear', 'hole_clear', 'see', 'inside')},
          'bbox', [r2(v) for v in M.logo['L'].bounds])
    print('Logo 備案', {k: (r2(v) if isinstance(v, float) else v) for k, v in M.logo_alt.items() if k in ('clear', 'hole_clear', 'see', 'inside')},
          'bbox', [r2(v) for v in M.logo_alt['L'].bounds])
    print('Logo 搜尋（clear 大→小）', M.logo_search[:8])
    print('#37 槽', [[r2(v) for v in s.bounds] for s in M.SLOTS37], '線缺口', [r2(v) for v in M.CABLE_NOTCH.bounds])
    print('盒 U', M.U_L0, M.U_R1, 'V', M.Vt, r2(M.Vb), '電池', [r2(v) for v in M.bat], 'EB-E U', r2(M.U_E0), r2(M.U_E1))
    print('主板', [r2(v) for v in M.board], '服務窗(W,V)', [r2(v) for v in M.SERVICE_WIN.bounds])
    for s in M.BOX:
        print(s.name, s.axis, [r2(v) for v in s.poly.bounds], s.rng, 'area', r2(s.poly.area),
              'pieces', 1 if s.poly.geom_type == 'Polygon' else len(s.poly.geoms))
    print('GPIO U', {k: r2(v) for k, v in M.GPIO_U.items() if k in ('33', '25', '26', '27', '14', '13')})
    for k, v in M.WIRE_LEN.items():
        print('線長', k, r2(v), '(其中 crosstrack 前段到 #37 內面', r2(M.ct_seg_len.get(k, 0)), ')')

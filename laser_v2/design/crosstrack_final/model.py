# 最終方案幾何：滑升式感測座（d3 為底）＋階梯窗、h=2.5、平行四邊形光孔、S50 開底缺口＋兩側插銷
# 站座標 (s, n, W')：原點 O＝光束正下方的軌道點；s 沿軌往下游、n 垂直軌道往上；光束在 (0, h)。
from geom import *
from params import P as P0, derived

NEW_TAB6 = (31.0, 38.0)      # #6 v2 新增前小榫的 V 範圍（取代被刪的長榫）

# v2 刪除（不再切）的原始孔：(零件, U0, U1, V0, V1, 理由)
DELETED_HOLES = [
    ('#24', 198.43, 201.33, 84.50, 92.40, '#5 長榫已刪（S50 缺口直通下緣）'),
    ('#26', 198.42, 201.32, 84.50, 92.40, '#5 長榫已刪'),
    ('#24', 165.68, 168.58, 84.50, 92.40, '#6 長榫已刪'),
    ('#26', 165.67, 168.57, 84.50, 92.40, '#6 長榫已刪'),
    ('#26', 135.93, 138.83, 64.50, 74.40, '#7 中段小榫已刪（落在 S5 窗與隔板缺口內）'),
]


def is_deleted_hole(h, part=None):
    b = h.bounds
    for p, u0, u1, v0, v1, _ in DELETED_HOLES:
        if (part is None or p == part) and abs(b[0] - u0) < 0.1 and abs(b[2] - u1) < 0.1 and abs(b[1] - v0) < 0.1 and abs(b[3] - v1) < 0.1:
            return True
    return False


def station_origin(k, P):
    st = STATIONS[k]
    U_beam = st['Ubar'] + P['delta_u'][k]
    U_O = U_beam - P['h'] * N[0]
    return np.array([U_O, railV(U_O)])


def sn2uv(O):
    return lambda g: affinity.affine_transform(g, [T[0], N[0], T[1], N[1], O[0], O[1]])


def module_boxes(P, D, dn=0.0):
    """模組各實體（站座標盒）：(名稱, s0, s1, n0, n1, W0, W1)。dn＝整體沿 n 位移（低位＝-slide）"""
    a = P['arm_w'] / 2
    up, dw = D['pcb_up'], D['pcb_dn']
    B = [
        ('前臂', -a, a, D['n_pcb_top'], D['n_arm_top'], *D['W_fa']),
        ('後臂', -a, a, D['n_pcb_top'], D['n_arm_top'], *D['W_ra']),
        ('本體底座', -a, a, D['n_pcb_top'], D['n_sb'], D['W_fa'][0], D['W_ra'][1]),
        ('PCB', -up, dw, D['n_pcb_bot'], D['n_pcb_top'], *D['W_pcb']),
        ('PCB 零件區', -up, dw, D['n_pcb_top'], D['n_comp'], *D['W_pcb']),
        ('PCB 焊點區', -up, dw, D['n_bump'], D['n_pcb_bot'], *D['W_pcb']),
    ]
    # 排針＋杜邦頭（假設：PCB 前端、翼的遠端，直立朝上）
    hs = (-up, -up + 7.62) if P['wing'] in ('up', 'center') else (dw - 7.62, dw)
    B.append(('排針＋杜邦頭', hs[0], hs[1], D['n_pcb_top'], D['n_pcb_top'] + P['hdr_up'],
              D['W_pcb'][0], D['W_pcb'][0] + P['hdr_len']))
    return [(nm, s0, s1, n0 + dn, n1 + dn, w0, w1) for nm, s0, s1, n0, n1, w0, w1 in B]


def build(P=P0):
    D = derived(P)
    S = {}
    a = P['arm_w'] / 2; c = P['c']; f = P['fit']
    lim = box(0, 0, 246, P['v_drawer'])
    for k, st in STATIONS.items():
        O = station_origin(k, P); to = sn2uv(O)
        R = dict(O=O, k=k, beam_UV=O + P['h'] * N)
        s0w, s1w = -D['pcb_up'] - c, D['pcb_dn'] + c          # 窗寬段 s 範圍
        R['win_s'] = (s0w, s1w)
        # ---------- 窗（#24、#26 同形）：窄段（光耦本體／後臂）＋寬段（PCB 翼）----------
        cb = P['c_body']
        r_body = rect_sn(O, -a - 2 * cb, a, D['n_win_bot'], D['n_strip'])   # 重力 +s：本體貼下游壁 → 光束在 s=0
        R['body_s'] = (-a - 2 * cb, a)
        r_pcb = rect_sn(O, s0w, s1w, D['n_win_bot'], D['n_shoulder'])
        win = unary_union([r_body, r_pcb])
        R['breaks_edge'] = not O24.buffer(-P['min_web']).contains(win)
        if R['breaks_edge']:   # 開底：寬段沿 -n 直通下緣（不留楔形碎片）
            ext = rect_sn(O, s0w, s1w, D['n_win_bot'] - 30, D['n_shoulder'])
            win = unary_union([win, ext]).intersection(box(0, 0, 246, 120))
        R['win'] = win                       # 未裁切（產生器：#24/#26 新外形 = 外形.difference(win)）
        R['win_in24'] = win.intersection(O24)
        # ---------- #26 光孔：平行四邊形（上下緣平行軌道、左右邊沿 V＝平行開口邊）----------
        Ub = R['beam_UV'][0]
        n0, n1 = P['h'] - P['lh_n'] / 2, P['h'] + P['lh_n'] / 2
        pts = []
        for nn, uu in ((n0, Ub - P['lh_u'] / 2), (n0, Ub + P['lh_u'] / 2), (n1, Ub + P['lh_u'] / 2), (n1, Ub - P['lh_u'] / 2)):
            s = (uu - O[0] - nn * N[0]) / T[0]
            pts.append(tuple(O + s * T + nn * N))
        R['lh'] = Polygon(pts)
        # ---------- 模組 ----------
        R['mod_final'] = module_boxes(P, D, 0.0)
        R['mod_low'] = module_boxes(P, D, -D['slide'])
        # ---------- 隔板缺口（(W',V) 平面）----------
        Ua, Ub2 = st['divU']; slab = box(Ua, -50, Ub2, 200)

        def vrange(s0, s1, n0, n1):
            g = rect_sn(O, s0, s1, n0, n1).intersection(slab)
            return None if g.is_empty else (g.bounds[1], g.bounds[3])
        va = vrange(-a, a, D['n_pcb_top'] - D['slide'], D['n_arm_top'])          # 臂＋本體（上滑掃掠）
        vp = vrange(-D['pcb_up'], D['pcb_dn'], D['n_bump'] - D['slide'], D['n_comp'])  # PCB＋零件＋焊點
        va_fin = vrange(-a, a, D['n_pcb_top'], D['n_arm_top'])
        R['notch_va'], R['notch_vp'], R['notch_va_fin'] = va, vp, va_fin
        deep = (vp[0] - c, vp[1] + c); stop = (va[0] - P['c_ntop'], va[1] + c)
        # 缺口底到隔板斜底邊的殘料 < min_web → 直通底邊
        R['notch_open_bottom'] = False
        if deep[1] + P['min_web'] > exitV(D['W_deep']):
            deep = (deep[0], 130.0); R['notch_open_bottom'] = True
        parts = [box(-6.5, deep[0], D['W_deep'], deep[1]), box(-6.5, stop[0], D['W_stop'], min(stop[1], deep[1]))]
        if stop[0] < deep[0]:   # 擋面下端導角
            ch = P['chamfer']
            parts.append(Polygon([(D['W_stop'], deep[0]), (D['W_deep'], deep[0]), (D['W_stop'], deep[0] - ch)]))
        R['stop_contact_V'] = (stop[0], deep[0] - P['chamfer'])
        notch = unary_union(parts)
        # 前榫：剩餘長度 < 4 → 整支刪除；#6 長榫一律刪除（見 spec b-3）
        dv = DIVWV[st['div']]
        front = dv.intersection(box(-6.5, 0, -1e-3, 120))
        R['tabs'] = []
        for g in getattr(front, 'geoms', [front]):
            b = g.bounds; rem = g.difference(notch)
            rem_len = 0 if rem.is_empty else rem.bounds[3] - rem.bounds[1]
            full = b[3] - b[1]
            kill = rem_len < 4.0 or (st['div'] == '#6' and b[1] > 80)
            if rem_len < full - 1e-3 or kill:
                status = '刪除' if kill else '縮短'
            else:
                status = '保留'
            if kill:
                notch = notch.union(box(-6.5, b[1] - 0.01, 0.0, b[3] + 0.01))
            R['tabs'].append(dict(V=(round(b[1], 2), round(b[3], 2)), depth=round(-b[0], 2), status=status,
                                  remain_V=None if rem.is_empty or kill else (round(rem.bounds[1], 2), round(rem.bounds[3], 2))))
        new_div = dv.difference(notch)
        pieces = list(getattr(new_div, 'geoms', [new_div]))
        main = max(pieces, key=lambda g: g.area)
        R['div_pieces'] = len(pieces)
        if st['div'] == '#6':     # 新增前小榫（插 #26 新槽）
            main = main.union(box(-3.0, NEW_TAB6[0], 0.0, NEW_TAB6[1]))
        R['notch'] = dv.difference(main)
        R['div_new'] = main
        # ---------- 鎖塊 P1（#24 平面）、蓋板 C1（#24 前方）----------
        n_body = D['n_pcb_bot']; n_wing = D['n_bump'] - P['c_v']
        p1 = Polygon([(s0w + f, D['n_win_bot']), (s1w - f, D['n_win_bot']), (s1w - f, n_wing),
                      (a - f, n_wing), (a - f, n_body), (-a - 2 * cb + f, n_body),
                      (-a - 2 * cb + f, n_wing), (s0w + f, n_wing)])
        m = P['cap_m'] if not R['breaks_edge'] else 7.0
        c1 = box(s0w - m, D['n_win_bot'] - P['cap_m'] - (40 if R['breaks_edge'] else 0), s1w + m, n_wing)
        if R['breaks_edge']:   # 插銷耳：PCB 範圍外可往上長到軌下 1.0
            pcb_s0, pcb_s1 = -D['pcb_up'] - 0.6, D['pcb_dn'] + 0.6
            c1 = unary_union([c1, box(s0w - m, -45, pcb_s0, -1.0), box(pcb_s1, -45, s1w + m, -1.0)])
        p1uv, c1uv = to(p1), to(c1)
        # 不得壓到轉盤圍邊 #27／前蓋 #63（半徑 54.5）＋1 mm
        c1uv = c1uv.difference(Point(TURN_C).buffer(TURN_R_RING + 1.0, 128))
        if R['breaks_edge']:
            p1 = rect_sn(O, s0w + f, s1w - f, D['n_win_bot'] - 30, 0)  # 開底：往下取到 V97.5
            p1 = Polygon([(s0w + f, D['n_win_bot'] - 30), (s1w - f, D['n_win_bot'] - 30), (s1w - f, n_wing),
                          (a - f, n_wing), (a - f, n_body), (-a - 2 * cb + f, n_body),
                          (-a - 2 * cb + f, n_wing), (s0w + f, n_wing)])
            p1uv = to(p1).intersection(lim)
        c1uv = c1uv.intersection(lim).intersection(O24)
        if R['breaks_edge']:
            c1uv = max(getattr(c1uv, 'geoms', [c1uv]), key=lambda g: g.area)
        R['p1'], R['c1'] = p1uv, c1uv
        # ---------- S50：插銷孔（窗兩側各一，#24 實料內、蓋板內）----------
        R['pins'] = []
        if R['breaks_edge']:
            mat = O24.difference(win)
            avoid = [h for h in H24 if h.distance(r_pcb) < 40 and not is_deleted_hole(h)]
            for side, s_c in (('上游', s0w - 3.5), ('下游', s1w + 3.5)):
                ok = []
                for nn in np.arange(-3.6, -40, -0.25):
                    hole = rect_sn(O, s_c - 1.45, s_c + 1.45, nn - 1.45, nn + 1.45)
                    if (mat.buffer(-2.0).contains(hole) and c1uv.buffer(-1.5).contains(hole)
                            and all(hole.distance(h) >= 2.0 for h in avoid)):
                        ok.append(nn)
                if ok:
                    nn = float(np.median(ok)); nn = round(nn * 4) / 4
                    best = dict(side=side, s=s_c, n=nn, n_ok=(min(ok), max(ok)),
                                hole=rect_sn(O, s_c - 1.45, s_c + 1.45, nn - 1.45, nn + 1.45))
                else:
                    best = None
                R['pins'].append(best)
        S[k] = R
    # ---------- #26：#6 新小榫槽（2.9×(7-0.1)，和原檔同規格）、排線孔 ----------
    extra = {}
    Uc6 = sum(STATIONS['S10']['divU']) / 2
    extra['slot26_tab6'] = box(Uc6 - 1.45, NEW_TAB6[0] + 0.05, Uc6 + 1.45, NEW_TAB6[1] - 0.05)
    extra['cable_hole'] = box(91.5, 103.5, 101.5, 108.0)     # #24、#26 同位置（d1 的位置，經核對）
    return P, D, S, extra


if __name__ == '__main__':
    P, D, S, X = build()
    for k, R in S.items():
        print('==', k, 'O', np.round(R['O'], 3), 'beam', np.round(R['beam_UV'], 3), '破出下緣', R['breaks_edge'])
        print('  窗(#24內) bounds', [round(x, 2) for x in R['win_in24'].bounds], ' 面積', round(R['win_in24'].area, 1))
        print('  光孔', [tuple(np.round(p, 3)) for p in np.array(R['lh'].exterior.coords)[:-1]])
        print('  隔板 va', np.round(R['notch_va'], 2), 'vp', np.round(R['notch_vp'], 2), '缺口 bounds', np.round(R['notch'].bounds, 2),
              '開底', R['notch_open_bottom'], '擋面接觸 V', np.round(R['stop_contact_V'], 2), '碎片', R['div_pieces'])
        print('  榫', R['tabs'])
        print('  P1', np.round(R['p1'].bounds, 2), round(R['p1'].area, 1), 'C1', np.round(R['c1'].bounds, 2), round(R['c1'].area, 1))
        for pn in R['pins']:
            print('  pin', None if pn is None else (pn['side'], round(pn['s'], 2), round(pn['n'], 2), np.round(pn['hole'].centroid.coords[0], 2)))

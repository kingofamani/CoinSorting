# 干涉與可靠度檢查（shapely）→ checks.json、checks_out.txt
import json, math
from model import *

GZ = np.array([T[0] * 0 + 0.0, 0, 0])
# 世界鉛直向下在 (U,V,W') 的分量：(0, 0.866, 0.5)；在站座標 (s,n,W')：
G_SNW = np.array([0.8660 * T[1], 0.8660 * N[1], 0.5])      # (≈0.296, ≈-0.814, 0.5)


def zworld(V, W):
    """離桌高（相對值）：Y = -0.866 V - 0.5 W'（frames 的世界座標，常數略）"""
    return -0.8660254 * np.asarray(V) - 0.5 * np.asarray(W)


def box_uv(O, b):
    nm, s0, s1, n0, n1, w0, w1 = b
    return rect_sn(O, s0, s1, n0, n1)


def r(x, d=2):
    if x is None:
        return None
    if isinstance(x, (list, tuple)):
        return [r(v, d) for v in x]
    return round(float(x), d)


def s_edge(O, U, n):
    """開口邊（U＝常數的 V 線）在高度 n 的 s 位置"""
    return (U - O[0] - n * N[0]) / T[0]


def coin_tip_range(O, c, lip):
    """硬幣 c 能翻入自己開口時的中心 s 範圍（開口兩邊在每個 n 都要包住硬幣弦）"""
    R_ = COIN_D[c] / 2; U0, U1 = op_U(c)
    lo, hi = -1e9, 1e9
    for npp in np.linspace(lip + 0.01, 2 * R_ - 0.01, 200):
        ch = math.sqrt(max(R_ ** 2 - (npp - R_) ** 2, 0))
        lo = max(lo, s_edge(O, U0, npp) + ch)
        hi = min(hi, s_edge(O, U1, npp) - ch)
    return lo, hi


def tip_sweep(O, c, lip, boxes, sc_list, kappas=(0.0, 0.3, 0.6)):
    """硬幣以唇為軸往後翻（0~180°），翻過 90° 後同時沿重力落下並往下游漂。回傳與各盒的最大侵入深度"""
    R_ = COIN_D[c] / 2
    rr = np.linspace(0, R_, 12); tt = np.linspace(0, 2 * np.pi, 72, endpoint=False)
    out = {}
    for sc in sc_list:
        S_ = (sc + np.outer(rr, np.cos(tt))).ravel(); Np = (R_ + np.outer(rr, np.sin(tt))).ravel()
        hi = Np > lip; S_, Np = S_[hi], Np[hi]; rad = Np - lip
        for th in np.radians(np.arange(0, 181, 5)):
            n1 = lip + rad * np.cos(th); w1 = -3.0 + rad * np.sin(th)
            falls = [0.0] if th < np.radians(90) else np.arange(0, 30.1, 1.0)
            for kap in kappas:
                for fd in falls:
                    s2 = S_ + fd * (G_SNW[0] + kap); n2 = n1 + fd * G_SNW[1]; w2 = w1 + fd * G_SNW[2]
                    for b in boxes:
                        nm, s0, s1, n0, n1b, w0, w1b = b
                        m = (s2 > s0) & (s2 < s1) & (n2 > n0) & (n2 < n1b) & (w2 > max(w0, 0)) & (w2 < w1b)
                        if m.any():
                            dep = np.minimum.reduce([s2[m] - s0, s1 - s2[m], n2[m] - n0, n1b - n2[m], w2[m] - max(w0, 0), w1b - w2[m]]).max()
                            key = nm
                            if key not in out or dep > out[key][0]:
                                out[key] = (float(dep), float(np.degrees(th)), float(fd), kap, float(sc))
    return out


def fall_zone_intrusion(O, c, boxes):
    """d2 的『緊』落幣區：U∈開口範圍、W'∈[0,D]、V 從唇到出口平面。模組在 W'>0 部分的侵入體積（W' 每 0.25 切片）"""
    U0, U1 = op_U(c); Dm = COIN_D[c]
    lipV = lambda U: railV(U) - LIP[c] / CA
    vol = 0.0; depth = 0.0; vmin = None
    below_lip = Polygon([(U0, lipV(U0)), (U1, lipV(U1)), (U1, 300), (U0, 300)])
    for w in np.arange(0.125, Dm, 0.25):
        zone = below_lip.intersection(box(U0, -10, U1, float(exitV(w))))
        polys = [box_uv(O, b) for b in boxes if b[5] < w < b[6]]
        if not polys or zone.is_empty:
            continue
        g = unary_union(polys).intersection(zone)
        if not g.is_empty:
            vol += g.area * 0.25
            b = g.bounds
            depth = max(depth, (b[2] - U0) if U0 > O[0] else (U1 - b[0]))
    return vol, depth


def run(P=None, quiet=False):
    P_, D, S, X = build(P) if P else build()
    P = P_
    C = dict(params=P, derived={k: (r(v, 3) if not isinstance(v, tuple) else r(v, 3)) for k, v in D.items()},
             rail=dict(V='%.6f*U+%.4f' % (RAIL_M, RAIL_B), deg=r(np.degrees(ANG), 4), resid=r(RAIL_RES, 4)),
             stations={})
    back = lambda B: [b for b in B if b[6] > 0]
    for k, R_ in S.items():
        st = STATIONS[k]; O = R_['O']; out = {}
        up, dn = st['up'], st['dn']
        Ub, Vb = R_['beam_UV']
        out['beam_UV'] = r([Ub, Vb], 3)
        out['beam_to_up_open_end_U'] = r(Ub - op_U(up)[1])
        out['beam_to_dn_open_start_U'] = r(op_U(dn)[0] - Ub)
        # ---- 開口、軌道：零改動 ----
        win = R_['win']; lh = R_['lh']
        out['win_to_openings'] = r(min(win.distance(OPS[c]) for c in OPS))
        out['win_to_slot24'] = r(win.distance(SLOT24))
        out['lh_to_open_up'] = r(lh.distance(OPS[up])); out['lh_to_open_dn'] = r(lh.distance(OPS[dn]))
        out['lh_to_win'] = r(lh.distance(win))
        out['lh_n_range'] = r([P['h'] - P['lh_n'] / 2, P['h'] + P['lh_n'] / 2])
        out['strip24_body'] = r(-D['n_strip']); out['strip24_wing'] = r(-D['n_shoulder'])
        out['strip26_body'] = r(LIP[up] - D['n_strip']); out['strip26_wing'] = r(LIP[up] - D['n_shoulder'])
        # 窗底到 #24 下緣
        w24 = R_['win_in24']
        out['breaks_edge'] = R_['breaks_edge']
        if not R_['breaks_edge']:
            out['win_to_24_bottom'] = r(O24.exterior.distance(w24))
        # 其他孔（不含已刪孔、斜槽、開口）
        others24 = [h for h in H24 if h.area < 300 and not is_deleted_hole(h, '#24')]
        others26 = [h for h in H26 if h.area < 300 and not is_deleted_hole(h, '#26')]
        out['win_to_other_holes24'] = r(min(w24.distance(h) for h in others24))
        out['win_to_other_holes26'] = r(min(win.intersection(O26).distance(h) for h in others26))
        # 雕刻
        out['engrave_hits'] = [ENG_NAME.get(s, s) for s, b in ENG24.items()
                               if b.buffer(1.0).intersects(unary_union([w24, R_['c1']]))]
        # 轉盤
        out['c1_to_turntable_ring'] = r(R_['c1'].distance(Point(TURN_C).buffer(TURN_R_RING, 128)))
        # ---- 模組 ----
        fin = R_['mod_final']; low = R_['mod_low']
        fa = [b for b in fin if b[0] == '前臂'][0]; ra = [b for b in fin if b[0] == '後臂'][0]
        out['front_arm_to_24front_rest'] = r(-6.0 - fa[6]); out['front_arm_to_24front_fwd'] = r(-6.0 - (fa[6] - P['c_stop']))
        out['front_arm_to_coin_front'] = {c: r((-3.0 - COIN_T[c]) - (fa[6] - P['c_stop'])) for c in ('5', '10', '50')}
        out['rear_arm_inner_to_26back_rest'] = r(ra[5]); out['rear_arm_inner_to_26back_fwd'] = r(ra[5] - P['c_stop'])
        out['module_max_W'] = r(max(b[6] for b in fin if b[0] != '排針＋杜邦頭'))
        out['module_to_37'] = r(W37 - out['module_max_W'])
        out['slot_bottom_to_strip'] = r(D['n_strip'] - D['n_sb'])
        out['arm_top_low_to_strip'] = r(D['n_strip'] - (D['n_arm_top'] - D['slide']))
        # 後臂伸出立柱（UV 正投影，唇以上）
        Ua, Ub2 = st['bar']
        arm_uv = rect_sn(O, ra[1], ra[2], LIP[up], ra[4])
        bar_strip = box(Ua, 0, Ub2, 200)
        prot = arm_uv.difference(bar_strip)
        pu = prot.intersection(box(0, 0, Ua, 200)); pd = prot.intersection(box(Ub2, 0, 300, 200))
        out['rear_arm_outside_bar_mm2'] = dict(up=r(pu.area), dn=r(pd.area),
                                               up_max=r(Ua - pu.bounds[0]) if not pu.is_empty else 0,
                                               dn_max=r(pd.bounds[2] - Ub2) if not pd.is_empty else 0)
        # 翻倒掃掠（上游幣：最晚翻；下游幣：最早翻）
        bx = [(b[0], b[1], b[2], b[3], b[4], max(b[5], 0.0), b[6]) for b in back(fin)
              if b[0] in ('後臂', 'PCB', 'PCB 零件區', 'PCB 焊點區')]
        sw = {}
        for c, which in ((up, 'up'), (dn, 'dn')):
            lo, hi = coin_tip_range(O, c, LIP[c])
            scs = [hi, hi - 1.0] if which == 'up' else [lo, lo + 1.0]
            res = tip_sweep(O, c, LIP[c], bx, scs)
            sw[c + '元'] = dict(tip_range_s=r([lo, hi]), hits={kk: dict(depth=r(v[0]), theta=r(v[1], 0), fall=r(v[2], 1), drift=v[3])
                                                               for kk, v in res.items()})
        out['tip_fall_sweep'] = sw
        # 落幣區侵入（d2 緊模型）
        fz = {}
        for c in (up, dn):
            vol, dep = fall_zone_intrusion(O, c, back(fin))
            fz[c + '元'] = dict(vol_mm3=r(vol, 0), depth_U=r(dep))
        out['fall_zone_intrusion'] = fz
        # 翼在 #26 後方的包絡（給 S1 協調）
        wing_parts = [box_uv(O, b) for b in back(fin) if b[0].startswith('PCB')]
        wenv = unary_union(wing_parts)
        Ud0, Ud1 = st['divU']
        wu = wenv.intersection(box(0, 0, Ud0, 200)); wd = wenv.intersection(box(Ud1, 0, 300, 200))
        out['wing_env_up'] = None if wu.is_empty else dict(U=r([wu.bounds[0], wu.bounds[2]]), V=r([wu.bounds[1], wu.bounds[3]]),
                                                          W=r([0, D['W_pcb'][1]]), U_into=r(Ud0 - wu.bounds[0]))
        out['wing_env_dn'] = None if wd.is_empty else dict(U=r([wd.bounds[0], wd.bounds[2]]), V=r([wd.bounds[1], wd.bounds[3]]),
                                                          W=r([0, D['W_pcb'][1]]), U_into=r(wd.bounds[2] - Ud1))
        # 翼頂離唇（V 差、垂直軌道）
        out['wing_top_below_lip_n'] = r(LIP[up] - D['n_comp'])
        # 出口平面（W'>0 部分）最終／低位
        def exit_clear(B):
            m = 1e9
            for b in back(B):
                if b[0] == '排針＋杜邦頭':
                    continue
                g = box_uv(O, b)
                for w in np.linspace(max(b[5], 0), b[6], 6):
                    m = min(m, exitV(w) - g.bounds[3])
            return m
        out['exit_plane_clear_final'] = r(exit_clear(fin))
        out['exit_plane_clear_low'] = r(exit_clear(low))
        # #24 前方（W'<-6）的東西：最低 V、世界高度相對 #24 前下角
        front_parts = [box_uv(O, b) for b in fin if b[5] < -6.0] + [R_['c1']]
        vmax = max(g.bounds[3] for g in front_parts)
        out['front_parts_max_V'] = r(vmax)
        z_corner = zworld(98.0, -6.0)
        zmin = min(min(zworld(np.array(g.exterior.coords)[:, 1], wv)) for g, wv in
                   [(box_uv(O, b), b[6] if b[6] < -6 else -6) for b in fin if b[5] < -6.0] + [(R_['c1'], -6.0)])
        out['front_parts_above_24corner_z'] = r(zmin - z_corner)
        # #13（右櫃側板／S1 牆）、馬達盒、#37
        allfin = unary_union([box_uv(O, b) for b in fin])
        out['to_13_U'] = r(allfin.bounds[0] - CAB13_U[1])
        out['to_motor_U'] = r(allfin.bounds[0] - MOTOR_U[1])
        # 排針＋杜邦頭
        hb = [b for b in fin if b[0] == '排針＋杜邦頭'][0]
        out['header_W'] = r([hb[5], hb[6]]); out['header_in_front_of_24'] = bool(hb[6] < -6.0 - 0.5)
        out['header_to_turntable'] = r(box_uv(O, hb).distance(Point(TURN_C).buffer(TURN_R_RING, 128)))
        # 計數：弦長、相貼兩枚空隙
        h = P['h']; hn0, hn1 = out['lh_n_range']
        def chord(Dm, nn): Rr = Dm / 2; return 2 * math.sqrt(max(Rr ** 2 - (Rr - nn) ** 2, 0))
        def gap(D1, D2, nn):
            return 2 * math.sqrt(D1 / 2 * D2 / 2) - chord(D1, nn) / 2 - chord(D2, nn) / 2
        passing = {'S5': ['5', '10', '50'], 'S10': ['10', '50'], 'S50': ['50']}[k]
        out['chord_at_hole_bottom'] = {c: r(chord(COIN_D[c], hn0)) for c in passing}
        lhs = P['lh_u'] / T[0]   # 光孔沿 s 寬
        gp = {}
        for i, c1_ in enumerate(passing):
            for c2_ in passing:
                gp[c1_ + '-' + c2_] = dict(at_beam=r(gap(COIN_D[c1_], COIN_D[c2_], h)),
                                          at_hole_top_minus_hole=r(gap(COIN_D[c1_], COIN_D[c2_], hn1) - lhs))
        out['touching_gap'] = gp
        # 隔板
        dv_new = R_['div_new']
        out['divider'] = dict(pid=st['div'], pieces=R_['div_pieces'], tabs=R_['tabs'],
                              notch_bounds=r(list(R_['notch'].bounds)), open_bottom=R_['notch_open_bottom'],
                              stop_contact_V=r(list(R_['stop_contact_V'])),
                              area_removed=r(R_['notch'].area, 1))
        # 新零件
        out['P1_bounds_UV'] = r(list(R_['p1'].bounds)); out['P1_area'] = r(R_['p1'].area, 1)
        out['C1_bounds_UV'] = r(list(R_['c1'].bounds)); out['C1_area'] = r(R_['c1'].area, 1)
        out['pins'] = [None if p is None else dict(side=p['side'], s=r(p['s']), n=r(p['n']), n_ok=r(list(p['n_ok'])),
                                                   center_UV=r(list(p['hole'].centroid.coords[0])),
                                                   to_slot=r(p['hole'].distance(SLOT24)),
                                                   to_24_edge=r(O24.exterior.distance(p['hole'])),
                                                   to_win=r(p['hole'].distance(win)))
                       for p in R_['pins']]
        C['stations'][k] = out
    # 全域：#6 新榫槽、排線孔
    s6 = X['slot26_tab6']
    C['slot26_tab6'] = dict(UV=r(list(s6.bounds)), to_openings=r(min(s6.distance(OPS[c]) for c in OPS)),
                            to_other=r(min(s6.distance(h) for h in H26 if h.area < 300 and h.distance(s6) > 0)),
                            inside26=bool(O26.buffer(-2).contains(s6)))
    ch = X['cable_hole']
    C['cable_hole'] = dict(UV=r(list(ch.bounds)),
                           in24=bool(O24.buffer(-2.5).contains(ch)), in26=bool(O26.buffer(-2.5).contains(ch)),
                           to_holes24=r(min(ch.distance(h) for h in H24)), to_holes26=r(min(ch.distance(h) for h in H26)),
                           to_24_edge=r(O24.exterior.distance(ch)), to_26_edge=r(O26.exterior.distance(ch)),
                           to_turntable=r(ch.distance(Point(TURN_C).buffer(TURN_R_RING, 128))),
                           to_13=r(CAB13_U[0] - ch.bounds[2]), to_motor=r(ch.bounds[0] - MOTOR_U[1]))
    # 排線長度（模組排針 → 沿 #24 正面 V95 → 排線孔 → 空腔 → #37 背面）
    L = {}
    for k, R_ in S.items():
        hb = [b for b in R_['mod_final'] if b[0] == '排針＋杜邦頭'][0]
        hp = box_uv(R_['O'], hb).centroid
        L[k] = r(abs(hp.y - 95.0) + abs(hp.x - 101.5) + 8 + 35 + 60, 0)
    C['cable_len_est'] = L
    return C


def fmt(C):
    lines = []
    for k, o in C['stations'].items():
        lines.append('===== %s =====' % k)
        for kk, v in o.items():
            lines.append('  %-34s %s' % (kk, json.dumps(v, ensure_ascii=False)))
    for kk in ('slot26_tab6', 'cable_hole', 'cable_len_est', 'rail'):
        lines.append('%-36s %s' % (kk, json.dumps(C[kk], ensure_ascii=False)))
    return '\n'.join(lines)


if __name__ == '__main__':
    import copy, os
    allc = {}
    for wing in ('up', 'down', 'center'):
        P = copy.deepcopy(P0); P['wing'] = wing
        C = run(P)
        allc[wing] = C
        txt = fmt(C)
        open('checks_out_%s.txt' % wing, 'w').write(txt)
        if wing == 'up':
            print(txt)
    json.dump(allc, open('checks.json', 'w'), ensure_ascii=False, indent=1, default=str)

# 輸出給產生器的幾何：geometry_final.json
#   每個多邊形都給：組裝座標 UV（及 W' 平面）、零件局部座標（bbox 原點，同 laser_v2.frames）、原始頁座標（frames.asm_to_page）
import json, copy
from model import *


def ring(g):
    if g.geom_type == 'MultiPolygon':
        g = max(g.geoms, key=lambda q: q.area)
    g = g.simplify(0.002)
    return [tuple(map(float, p)) for p in np.array(g.exterior.coords)[:-1]]


def r3(pts):
    return [[round(a, 3), round(b, 3)] for a, b in pts]


def plate_out(pid, poly_uv, W):
    """#24/#26/#37：UV 多邊形 → 局部、頁座標"""
    pts = ring(poly_uv)
    U = np.array([p[0] for p in pts]); V = np.array([p[1] for p in pts])
    pg = F.asm_to_page(pid, U, V, np.full_like(U, W))
    x0, y0 = PARTS[pid].bbox[:2]
    return dict(UV=r3(pts), local=r3(list(zip(pg[:, 0] - x0, pg[:, 1] - y0))), page=r3(list(zip(pg[:, 0], pg[:, 1]))))


def div_out(pid, poly_wv):
    pts = ring(poly_wv)
    Wp = np.array([p[0] for p in pts]); V = np.array([p[1] for p in pts])
    Uc = sum(F.frame(pid).plane()[1:]) / 2
    pg = F.asm_to_page(pid, np.full_like(Wp, Uc), V, Wp)
    x0, y0 = PARTS[pid].bbox[:2]
    return dict(WV=r3(pts), local=r3(list(zip(pg[:, 0] - x0, pg[:, 1] - y0))), page=r3(list(zip(pg[:, 0], pg[:, 1]))))


def sn_out(O, poly_uv):
    """新零件：站座標 (s,n) 外形，再平移到零件自己的局部座標（左下角＝0）"""
    g = UV_to_sn(O, poly_uv)
    pts = ring(g)
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, y0 = min(xs), min(ys)
    return dict(sn=r3(pts), local=r3([(x - x0, y - y0) for x, y in pts]), size=[round(max(xs) - x0, 2), round(max(ys) - y0, 2)],
                origin_sn=[round(x0, 3), round(y0, 3)])


def engrave_moves(S, X):
    """被新切割（窗、蓋板、插銷、排線孔）蓋到的雕刻，找最小平移；新位置要避開所有切割與孔、留 1.5 mm"""
    new_cuts = unary_union([R['win_in24'] for R in S.values()] + [R['c1'] for R in S.values()] +
                           [p['hole'] for R in S.values() for p in R['pins'] if p] + [X['cable_hole']])
    block = unary_union([new_cuts, SLOT24] + [h for h in H24 if h.area < 300 and not is_deleted_hole(h, '#24')] +
                        [Point(TURN_C).buffer(TURN_R_RING + 1.0, 128)] + [b for b in ENG24.values()])
    region = O24.buffer(-1.5).intersection(box(0, 0, 246, 96.5))
    moves = {}
    for src, b in ENG24.items():
        if not b.buffer(1.0).intersects(new_cuts):
            continue
        others = unary_union([bb for s2, bb in ENG24.items() if s2 != src])
        blk = unary_union([new_cuts, SLOT24, others] + [h for h in H24 if h.area < 300 and not is_deleted_hole(h, '#24')] +
                          [Point(TURN_C).buffer(TURN_R_RING + 1.0, 128)])
        best = None
        for dU in np.arange(-15, 15.01, 0.25):
            for dV in np.arange(-60, 30.01, 0.25):
                cost = abs(dV) + 3 * abs(dU)
                if best is not None and cost >= best[0]:
                    continue
                bb = affinity.translate(b, dU, dV)
                if region.contains(bb) and not bb.buffer(1.5).intersects(blk):
                    best = (cost, dU, dV)
        moves[src] = dict(name=ENG_NAME.get(src, src), old_UV=[round(x, 2) for x in b.bounds],
                          dU=None if best is None else round(best[1], 2), dV=None if best is None else round(best[2], 2),
                          new_UV=None if best is None else [round(x, 2) for x in affinity.translate(b, best[1], best[2]).bounds])
    return moves


def export(P=P0, fn='geometry_final.json'):
    P, D, S, X = build(P)
    J = dict(note='crosstrack_final：滑升式感測座。座標約定見 spec.md §1；局部＝零件 bbox 左上角原點（同 laser_v2.frames），page＝原始檔該頁座標（mm）。',
             params=P, derived={k: v for k, v in D.items()}, stations={}, parts={})
    for k, R in S.items():
        st = STATIONS[k]
        e = dict(beam_UV=[round(float(x), 3) for x in R['beam_UV']], O_UV=[round(float(x), 3) for x in R['O']],
                 T_UV=[round(float(x), 6) for x in T], N_UV=[round(float(x), 6) for x in N],
                 breaks_edge=R['breaks_edge'])
        if R['breaks_edge']:
            e['win_mode'] = '外形相減：#24、#26 新外形 = 原外形.difference(win)'
        else:
            e['win_mode'] = '新增封閉孔'
        e['win24'] = plate_out('#24', R['win'].intersection(O24.buffer(5)) if R['breaks_edge'] else R['win'], -6.0)
        e['win26'] = plate_out('#26', R['win'].intersection(O26.buffer(5)) if R['breaks_edge'] else R['win'], -3.0)
        e['lighthole26'] = plate_out('#26', R['lh'], -3.0)
        e['pins24'] = [None if p is None else dict(side=p['side'], hole=plate_out('#24', p['hole'], -6.0)) for p in R['pins']]
        e['divider'] = dict(pid=st['div'], new_outline=div_out(st['div'], R['div_new']), tabs=R['tabs'],
                            notch_open_bottom=R['notch_open_bottom'])
        e['P1'] = sn_out(R['O'], R['p1']); e['C1'] = sn_out(R['O'], R['c1'])
        e['P1_on_C1_offset'] = [round(e['P1']['origin_sn'][0] - e['C1']['origin_sn'][0], 3),
                                round(e['P1']['origin_sn'][1] - e['C1']['origin_sn'][1], 3)]
        if R['pins'] and all(R['pins']):
            e['pins_on_C1'] = [[round(p['s'] - 1.5 - e['C1']['origin_sn'][0], 3), round(p['n'] - 1.5 - e['C1']['origin_sn'][1], 3)]
                               for p in R['pins']]
        J['stations'][k] = e
    J['parts']['#26_slot_tab6'] = plate_out('#26', X['slot26_tab6'], -3.0)
    J['parts']['cable_hole_24'] = plate_out('#24', X['cable_hole'], -6.0)
    J['parts']['cable_hole_26'] = plate_out('#26', X['cable_hole'], -3.0)
    J['parts']['deleted_holes'] = [dict(part=p, U=[u0, u1], V=[v0, v1], why=w) for p, u0, u1, v0, v1, w in DELETED_HOLES]
    J['parts']['engrave_moves_24'] = engrave_moves(S, X)
    J['parts']['pin'] = dict(size=[3.0, 3.0], note='3 mm 板切 3.0×3.0 方塊；#24 孔畫 2.9×2.9（同原檔 3 mm 榫槽畫 2.9 的慣例）')
    json.dump(J, open(fn, 'w'), ensure_ascii=False, indent=1, default=float)
    return J


if __name__ == '__main__':
    J = export()
    for k, e in J['stations'].items():
        print(k, 'P1', e['P1']['size'], 'C1', e['C1']['size'], 'P1 在 C1 上偏移', e['P1_on_C1_offset'], 'pins', e.get('pins_on_C1'))
        print('  P1 local', e['P1']['local'])
        print('  C1 local', e['C1']['local'])
    print(json.dumps(J['parts']['engrave_moves_24'], ensure_ascii=False))
    for w in ('down', 'center'):
        P = copy.deepcopy(P0); P['wing'] = w
        Jw = export(P, 'geometry_final_wing_%s.json' % w)
        print(w, json.dumps(Jw['parts']['engrave_moves_24'], ensure_ascii=False))

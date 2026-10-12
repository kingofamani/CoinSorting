"""輸出 geometry_final.json：原始零件修改（組裝 UV／局部／頁座標）、新增零件局部外形、盒內元件、線路。"""
from model import *
import params as PR

M = build(PR)
OUT = dict(note='ebox_final：座標約定見 spec.md §1。局部＝零件 bbox 左上角原點（同 laser_v2.frames）；page＝原始檔該頁座標。'
                '新增零件局部 (a,b) 見各零件 mapping。',
           params={k: getattr(PR, k) for k in dir(PR) if k.isupper()}, mods={}, new_parts={})


def P3(pid, poly, label, third=None):
    pg, loc = poly_to_page_local(pid, poly, third)
    pl = FR[pid].plane()
    return dict(label=label, asm_axes=PLANE[pl[0]], asm=coords(poly, 3), local=coords(loc, 3), page=coords(pg, 3))


def circ(pid, u, v, d, label):
    pg = asm2_to_page(pid, [[u, v]])[0]; o = origin(pid)
    return dict(label=label, kind='circle', d=d, asm_center=(r2(u, 3), r2(v, 3)), local_center=(r2(pg[0] - o[0], 3), r2(pg[1] - o[1], 3)),
                page_center=(r2(pg[0], 3), r2(pg[1], 3)))


m = {}
# ---------------- #24
m['#24'] = [P3('#24', M.WIN, 'LED 窗（切穿，直角）')]
for k, (u, v) in enumerate(M.holes):
    m['#24'].append(circ('#24', u, v, M.D['hole_d'] + 2 * PR.C_SCREW, f'M2 孔 {k + 1}'))
dU, dV = M.LOGO_SHIFT
pg0 = asm2_to_page('#24', [[0, 0], [dU, dV]])
m['#24'].append(dict(label='Logo 整組平移（雕刻 path1-5-9＋9 個菱形切穿孔）', asm_delta=(dU, dV),
                     page_delta=(r2(pg0[1][0] - pg0[0][0], 3), r2(pg0[1][1] - pg0[0][1], 3)),
                     old_bbox_asm=[r2(v) for v in LOGO.bounds], new_bbox_asm=[r2(v) for v in M.logo['L'].bounds],
                     old_holes_page=[coords(poly_to_page_local('#24', h)[0], 3) for h in LOGO_HOLES],
                     new_holes=[P3('#24', affinity.translate(h, dU, dV), f'Logo 新孔 {k + 1}') for k, h in enumerate(LOGO_HOLES)],
                     how='原 9 個孔不輸出（補回實料）；輸出平移後 9 個孔；雕刻 path1-5-9 整組套 page_delta 平移'))
# ---------------- #26
m['#26'] = [P3('#26', M.NOTCH26.intersection(rect(0, 300, 13.0, 200)).simplify(0.001),
               '頂邊 L 形缺口（多邊形上緣 V13 在板外 1 mm，確保切穿頂邊 V14）')]
# ---------------- #5（crosstrack v2 外形再減前上角）
g5 = M.DIV5_LOCAL.simplify(0.001)
o5 = origin('#5')
m['#5'] = [dict(label='v2 外形＝crosstrack_final #5 v2 外形 − 局部矩形', remove_local=[-1.0, -1.0, r2(M.DIV5_CUT_W + 6.0, 3), r2(M.DIV5_CUT_V - 14.0, 3)],
                remove_WV=[-7.0, 13.0, r2(M.DIV5_CUT_W, 3), r2(M.DIV5_CUT_V, 3)],
                new_outline_local=coords(g5, 3), new_outline_page=coords(affinity.translate(g5, *o5), 3),
                new_outline_WV=coords(M.DIV5_WV.simplify(0.001), 3))]
# ---------------- #37
m['#37'] = [P3('#37', s, f'掛勾槽 {k + 1}（{"左牆 WL" if k < 2 else "右牆 WR"}，{"上" if k % 2 == 0 else "下"}層）')
            for k, s in enumerate(M.SLOTS37)]
m['#37'].append(P3('#37', M.CABLE_NOTCH, '頂邊顯示器線 U 形缺口（多邊形上緣 V2 在板外 2 mm）'))
m['#37'].append(P3('#37', M.SENSOR_HOLE, '感測器線孔（右側空腔→背面；crosstrack_final 要求的 ≥10×5）'))
OUT['mods'] = m


# ---------------- 新增零件
def new_part(s, qty=1, note=''):
    g = s.poly.buffer(0.02, join_style=2).buffer(-0.02, join_style=2).simplify(0.02)   # 清掉 0.01 mm 接縫
    b = g.bounds
    loc = affinity.translate(g, -b[0], -b[1])
    a1, a2 = PLANE[s.axis]
    OUT['new_parts'][s.name] = dict(qty=qty, material='3 mm 合板', size=(r2(b[2] - b[0]), r2(b[3] - b[1])), net_area=r2(g.area),
                                   mapping=f"局部 a＝{a1}−{b[0]:.3f}、b＝{a2}−{b[1]:.3f}；板厚方向 {s.axis} {s.rng[0]:.3f}~{s.rng[1]:.3f}",
                                   outline_local=coords(Polygon(loc.exterior), 3),
                                   holes_local=[coords(Polygon(r), 3) for r in loc.interiors], note=note)


for s in M.BOX:
    new_part(s)
new_part(Solid('EB-K 防拔鍵（選用）', 'U', M.KEY_WV, (M.U_L0, M.U_L1)), qty=2, note='兩片同形，WL、WR 各一')
OUT['contents_asm'] = {k: [r2(v) for v in bx] for k, bx in M.CONTENTS.items()}
OUT['display_asm'] = {k: [r2(v) for v in bx] for k, bx in M.disp.items()}
OUT['wires_asm'] = {k: [[r2(x) for x in p] for p in v] for k, v in M.WIRES.items()}
OUT['wire_len'] = {k: r2(v) for k, v in M.WIRE_LEN.items()}
OUT['gpio_U'] = {k: r2(v) for k, v in M.GPIO_U.items()}
OUT['en_boot_UV'] = [[r2(u), r2(v)] for u, v in M.EN_BTN]
OUT['service_window_WV'] = [r2(v) for v in M.SERVICE_WIN.bounds]
OUT['origins_page'] = {pid: origin(pid) for pid in ('#24', '#26', '#37', '#5')}
json.dump(OUT, open(HERE + '/geometry_final.json', 'w'), ensure_ascii=False, indent=1, default=float)
if __name__ == '__main__':
    for pid, recs in m.items():
        for r in recs:
            print(pid, r.get('label'), r.get('asm') or r.get('asm_center') or r.get('asm_delta'), '→ local', r.get('local') or r.get('local_center') or r.get('remove_local'),
                  '→ page', r.get('page') or r.get('page_center') or r.get('page_delta'))
    for k, v in OUT['new_parts'].items():
        print(k, v['size'], v['net_area'], v['mapping'])
        print('   outline', v['outline_local'])
        for h in v['holes_local']:
            print('   hole', h)

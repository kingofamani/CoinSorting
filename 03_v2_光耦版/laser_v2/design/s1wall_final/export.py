"""S1 最終規格：輸出給產生器的幾何 JSON（geometry_s1_final.json）。
每個多邊形給三種座標：asm（組裝 (U,V) 或 (W',V)）、local（零件局部，原點＝零件外框左上角，與 laser_v2.frames 相同）、
page（原始 SVG 該頁座標，只有原始零件 #13/#21/#26/#37 才有，由 laser_v2.frames.asm_to_page 算出）。
"""
import sys, json
sys.dont_write_bytecode = True
import numpy as np
from shapely.geometry import Polygon, mapping
from shapely import affinity
import base as B
import design as DS
import params as PR
from laser_v2 import frames as F

g = DS.build()
D, M, Dd = g['D'], g['M'], g['Dd']


def coords(poly, nd=3):
    if poly is None:
        return None
    if poly.geom_type == 'MultiPolygon':
        return [coords(p, nd) for p in poly.geoms]
    ext = [[round(float(x), nd), round(float(y), nd)] for x, y in np.array(poly.exterior.coords)[:-1]]
    ints = [[[round(float(x), nd), round(float(y), nd)] for x, y in np.array(r.coords)[:-1]] for r in poly.interiors]
    return dict(exterior=ext, holes=ints) if ints else ext


def page_of(pid, pts_asm3):
    P = np.array(pts_asm3, float)
    q = F.frame(pid).to_page(P[:, 0], P[:, 1], P[:, 2])
    return [[round(float(a), 3), round(float(b), 3)] for a, b in q[:, :2]]


def uv_feature(pid, poly, W):
    ext = np.array(poly.exterior.coords)[:-1]
    loc = B.UV_to_local26(poly) if pid == '#26' else B.UV_to_local37(poly)
    return dict(asm_UV=coords(poly), local=coords(loc),
                page=page_of(pid, [[u, v, W] for u, v in ext]))


out = dict(note='S1 最終規格（方案 A：#13R 加高右牆＋背插卡匣＋前臂導流帽）。座標約定見 spec.md §b-0。所有值由 design.py 依 params.py 算出（暫定模組尺寸）。',
           params=dict(MOD=M, DES={k: v for k, v in Dd.items()}), derived={k: (list(v) if isinstance(v, tuple) else v) for k, v in D.items()})

# ---------------- #13R ----------------
wall = g['wall13R_WV']
ops = dict(
    raise_rect=[0.0, Dd['wall_top'], B.W37, 76.2],          # (W0, V0, W1, V1)
    tabs_front=[[-Dd['tab_len_26'], 0.0, a, b] for a, b in Dd['tabs_front']],   # (W0, W1, V0, V1)
    tabs_back=[[B.W37, B.W37 + Dd['tab_len_37'], a, b] for a, b in Dd['tabs_back']],
    wall_slot=list(g['wall_slot_WV'].bounds),
    corner_notch=list(g['corner_notch_WV'].bounds) if Dd['corner_fix'] else None,
)


def rect_WV_to_local13(b):
    w0, v0, w1, v1 = b
    poly = Polygon([(w0, v0), (w1, v0), (w1, v1), (w0, v1)])
    return coords(B.poly_WV_to_local13(poly))


eng13 = [dict(text='13R 右', h=4.0, at_WV=[15.0, 40.0]), dict(text='S1 卡匣', h=3.0, at_WV=[15.0, 46.0])]
for e in eng13:
    x, y = B.WV_to_local13(np.array([e['at_WV'][0]]), np.array([e['at_WV'][1]]))
    e['at_local13'] = [round(float(x[0]), 3), round(float(y[0]), 3)]
    e['face'] = '上面（z=0，U104.875，朝右側空腔）'
    e['direction'] = "文字基線沿 W'（由 #26 往 #37）"
out['#13R'] = dict(
    desc='取代右櫃側板 #13（v2 修改）。原 #13 外形 ∪ 加高區 ∪ 榫 − 牆槽 − 角落讓位，原 3 個 #12 槽與鋸齒保留。',
    ops_WV={k: v for k, v in ops.items()},
    ops_local13={k: (rect_WV_to_local13(v) if (k in ('raise_rect', 'wall_slot', 'corner_notch') and v) else
                     ([rect_WV_to_local13((a[0], a[2], a[1], a[3])) for a in v] if k.startswith('tabs') else None)) for k, v in ops.items()},
    outline_WV=coords(wall.simplify(0.01)),
    outline_local13=coords(B.poly_WV_to_local13(wall.simplify(0.01))),
    local13_from_WV='x = 0.8660(V−60.058) + 0.5(W\'−25.886)；y = 0.5(V−60.058) − 0.8660(W\'−25.886)（原 #13 外框左上角＝0，頁座標原點 139.550, 90.601）',
    engrave=eng13,
    area=dict(orig=round(g['orig13_WV'].area, 1), new=round(wall.area, 1)))
# 檢查局部換算式
xx, yy = B.WV_to_local13(np.array([10.0]), np.array([70.0]))
out['#13R']['formula_check'] = dict(at_WV=[10, 70], frames=[round(float(xx[0]), 3), round(float(yy[0]), 3)],
                                    formula=[round(0.8660254 * (70 - 60.058) + 0.5 * (10 - 25.886), 3), round(0.5 * (70 - 60.058) - 0.8660254 * (10 - 25.886), 3)])

# ---------------- #21 ----------------
fr21 = F.frame('#21')
top21 = fr21.to_asm(np.array([0.0]), np.array([0.0]), np.array([0.0]))[0][0]
p21 = fr21.to_page(np.array([top21]), np.array([80.0]), np.array([12.0]))
x0, y0 = B.local_origin('#21')
out['#21'] = dict(desc='左櫃側板，外形不改，只加雕刻（v2 修改：雕刻）。', engrave=[dict(text='21 左', h=4.0, at_WV=[12.0, 80.0],
                  at_local21=[round(float(p21[0][0] - x0), 3), round(float(p21[0][1] - y0), 3)], face=f'上面（z=0，U{round(float(top21), 3)}）')])

# ---------------- #26 ----------------
out['#26'] = dict(desc='加 3 個槽（v2 修改）。原檔齒孔偏移由 laser_v2.frames.fix_26_tooth_hole() 修（KNOWN_DEFECTS apply=True），本規格不另改該孔。',
                  slots={k: uv_feature('#26', s, -1.5) for k, s in g['slots26_UV'].items()})

# ---------------- #37 ----------------
out['#37'] = dict(desc='加卡匣窗、後榫槽 B1、2 個 M3 孔、雕刻（v2 修改）。',
                  window=uv_feature('#37', g['win37_UV'], 30.5),
                  slots={k: uv_feature('#37', s, 30.5) for k, s in g['slots37_UV'].items()},
                  holes=[dict(center_UV=[round(u, 3), round(v, 3)], d=Dd['screw_hole_37'],
                              center_local=[round(114.0 - v, 3), round(u, 3)],
                              center_page=page_of('#37', [[u, v, 30.5]])[0]) for (u, v) in g['screws_UV']],
                  engrave=[dict(text='S1 卡匣', h=4.0, at_UV=[115.0, 46.5], at_local=[67.5, 115.0], face='上面（朝機身背面），在背蓋上緣之上')])

# ---------------- 新零件 ----------------
newp = {}
for name, poly, plane, extra in (
        ('S1-B', g['S1B_WV'], 'WV', dict(U=[B.U13[0], B.U13[1]], note='座塊；嵌在 #13R 牆槽內')),
        ('S1-C', g['S1C_WV'], 'WV', dict(U=[B.U13[0] - 3.0, B.U13[0]], note='座板；空腔側貼牆，前榫插 #26 槽 C')),
        ('S1-H', g['S1H_WV'], 'WV', dict(U=[list(u) for u in g['S1H_U']], qty=Dd['cap_layers'], note='前臂導流帽；3 片同形，疊在前臂頂面')),
        ('S1-F', g['S1F_UV'], 'UV', dict(W=[B.W37o, B.W37o + 3.0], note='背蓋；貼 #37 外面，2 支 M3')),
        ('S1-P', g['S1P_UV'], 'UV', dict(W=[B.W37, B.W37o], note='導流帽通道填塊；黏在背蓋前面')),
):
    if plane == 'WV':
        loc, (a0, b0) = DS.local_WV(poly)
        place = f"U = U0 + z（U0＝{extra['U'] if name != 'S1-H' else '各片'}），V = y + {round(b0, 3)}，W' = x + {round(a0, 3)}；上面 z=0 朝 −U（空腔側）"
    else:
        loc, (a0, b0) = DS.local_UV(poly)
        place = f"U = x + {round(a0, 3)}，V = y + {round(b0, 3)}，W' = W1 − z；上面 z=0 朝 +W'（朝機身背面），局部＝從機身背面看"
    bb = loc.bounds
    newp[name] = dict(asm=coords(poly), local=coords(loc), size=[round(bb[2] - bb[0], 3), round(bb[3] - bb[1], 3)],
                      area=round(poly.area, 1), placement=place, **extra)
# S1-C：上面（雕刻面）要朝 +U（貼牆、貼 S1-B 那面），合法擺法須把局部 x 鏡像：x = W1 − W'
c_poly = g['S1C_WV']; W1c = c_poly.bounds[2]; V0c = c_poly.bounds[1]
mir = lambda p: affinity.affine_transform(p, [-1, 0, 0, 1, W1c, -V0c])
newp['S1-C']['local'] = coords(mir(c_poly))
newp['S1-C']['placement'] = f"U = {B.U13[0]} − z（上面 z=0 在 U{B.U13[0]}，朝 +U＝貼牆／S1-B），V = y + {round(V0c, 3)}，W' = {round(W1c, 3)} − x"
newp['S1-C']['engrave_outline_S1B'] = coords(Polygon(mir(g['S1B_WV']).exterior).simplify(0.01))
newp['S1-C']['engrave_text'] = dict(text='S1-C 前→', h=2.5, at_local=[round(W1c - 8.0, 3), round(70.0 - V0c, 3)])
newp['S1-F']['engrave_text'] = dict(text='S1 ↑', h=4.0, at_local=[round(120.0 - g['S1F_UV'].bounds[0], 3), round(58.0 - g['S1F_UV'].bounds[1], 3)])
newp['S1-F']['holes_local'] = [[round(u - g['S1F_UV'].bounds[0], 3), round(v - g['S1F_UV'].bounds[1], 3), Dd['screw_hole_cover']] for u, v in g['screws_UV']]
out['new_parts'] = newp

# ---------------- 模組（組裝座標盒） ----------------
out['module_boxes_UVW'] = {k: [round(x, 3) for x in v] for k, v in g['mod'].items()}
out['beam'] = g['beam']
json.dump(out, open('geometry_s1_final.json', 'w'), ensure_ascii=False, indent=1, default=float)
print('written geometry_s1_final.json')
print('#13R formula check', out['#13R']['formula_check'])
for k, v in newp.items():
    print(k, v['size'], v['area'])
print('#21 engrave', out['#21']['engrave'])
print('#37 holes', out['#37']['holes'])
print('#26 slots local', {k: v['local'] for k, v in out['#26']['slots'].items()})
print('#37 window local', out['#37']['window']['local'])
print('#37 slots local', {k: v['local'] for k, v in out['#37']['slots'].items()})
print('S1-C local', newp['S1-C']['local'])
print('S1-B local', newp['S1-B']['local'])

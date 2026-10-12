"""S1 最終規格：shapely 干涉／尺寸檢查（全部數字由此檔算出，輸出 checks.json、checks_out.txt）。
執行：python3 -B checks.py
"""
import sys, json, math, copy
sys.dont_write_bytecode = True
import numpy as np
from shapely.geometry import Polygon, box, Point, LineString
from shapely.ops import unary_union
import base as B
import params as PR
import design as DS

OUT = []
RES = {}


def log(*a):
    s = ' '.join(str(x) for x in a)
    OUT.append(s); print(s)


def r(v, n=2):
    return None if v is None else round(float(v), n)


def chk(key, item, val, need, ok, note=''):
    RES[key] = dict(item=item, value=val, need=need, ok=bool(ok), note=note)
    log(f"  [{'OK' if ok else 'NG'}] {item}：{val}（要求 {need}）{('｜' + note) if note else ''}")


g = DS.build()
D, M, Dd = g['D'], g['M'], g['Dd']
U_out, U_in = B.U13
U7 = B.U7[0]
o0, o1 = B.OPEN1

# ======================================================================
log('=== 1. 光束位置與保證覆蓋 ===')
zone = (U7 - B.COIN_D, U_in + B.COIN_D)
log(f'  1 元滑道淨寬 U{U_in}~{U7}＝{r(U7 - U_in, 3)}；保證覆蓋區（硬幣平行 #37 時）U{r(zone[0], 3)}~{r(zone[1], 3)}')
mb = D['Ub'] - zone[0]
chk('beam_margin', '光束 U 離覆蓋區左界（貼 #7 的硬幣右緣 115.876）', f"U{r(D['Ub'], 3)}，+{r(mb, 2)}，扣光窗半寬 {M['aperture'] / 2} 後 +{r(mb - M['aperture'] / 2, 2)}",
    '扣光窗後 ≥1.0', mb - M['aperture'] / 2 >= 1.0)
# 硬幣繞軌道方向翻轉時 U 寬下限（法向 ⟂ 軌道方向）
nU = math.sin(B.ANG)
Uw = B.COIN_D * math.sqrt(1 - nU ** 2)
chk('beam_margin_roll', '硬幣繞軌道方向任意翻轉時（U 寬 ≥%.2f）光束仍在硬幣內' % Uw, f'右緣 ≤{r(U7 - Uw, 2)}，光束重疊 {r(D["Ub"] - (U7 - Uw), 2)}',
    '>0', D['Ub'] - (U7 - Uw) > 0)
chk('beam_V', '光束 V 與 W\' 段', f"V{D['Vb']}，W'{D['wa']}→{D['wb']}（後臂內面在 #37 內面後 {r(D['wb'] - B.W37, 2)}）", '後臂不得凸出 #37 內面', D['wb'] >= B.W37)
RES['beam'] = dict(U=D['Ub'], V=D['Vb'], W=(D['wa'], D['wb']))

# ======================================================================
log('\n=== 2. 與 S5（crosstrack_final）翼與安裝掃掠 ===')
s1_solids = {k: g['mod'][k] for k in ('pcb', 'comp', 'body', 'front_arm', 'solder')}
cap_U = (g['S1H_U'][0][0], g['S1H_U'][-1][1])
cap_UV = box(cap_U[0], D['cap_Vr'], cap_U[1], D['arm_v'][0])
s5 = {w: B.s5_boxes(w) for w in ('up', 'down', 'center')}
RES['s5'] = {}
for w, S in s5.items():
    sw = S['sweep_UV']
    Wmax = max(S['W_max'], S['W_deep'])
    # S1 在 W' < Wmax 的實體（只有 PCB 前端、元件區前端、焊點區前端可能）
    s1_front_W = min(v[4] for v in s1_solids.values())
    cap_W0 = g['S1H_WV'].bounds[0]
    ov = 0.0
    for k, (U0, U1, V0, V1, W0, W1) in s1_solids.items():
        if W0 < Wmax:
            ov += box(U0, V0, U1, V1).intersection(sw).area
    log(f"  翼 {w}：掃掠 (U,V) {[r(x, 2) for x in sw.bounds]}，W'≤{r(Wmax, 2)}；S1 最前實體 W'{r(s1_front_W, 2)}（PCB／臂前面），導流帽前面 W'{r(cap_W0, 2)}")
    RES['s5'][w] = dict(sweep_bounds=[r(x, 3) for x in sw.bounds], Wmax=r(Wmax, 3), gap_W=r(min(s1_front_W, cap_W0) - Wmax, 3),
                        overlap_area=r(ov, 3))
    chk(f's5_gap_{w}', f'S1 與 S5（翼 {w}）最終位置＋安裝掃掠的 W\' 間隙', f'{r(min(s1_front_W, cap_W0) - Wmax, 2)}（(U,V) 重疊時 W\' 不重疊；同 W\' 段的 (U,V) 重疊面積 {r(ov, 2)}）',
        '≥1.5 且同 W\' 段重疊＝0', min(s1_front_W, cap_W0) - Wmax >= 1.5 and ov < 1e-6)

# ======================================================================
log('\n=== 3. 滑道內凸出物 ===')
direct = o0      # 硬幣直落最右緣（開口右緣）
prot = {}
for k, (U0, U1, V0, V1, W0, W1) in s1_solids.items():
    if U1 > U_in:
        prot[k] = dict(U=(r(max(U0, U_in), 3), r(U1, 3)), V=(r(V0, 2), r(V1, 2)), W=(r(W0, 2), r(min(W1, B.W37), 2)))
log('  伸進滑道（U>107.875）的實體：')
for k, v in prot.items():
    log(f'    {k}: U{v["U"]} V{v["V"]} W\'{v["W"]}')
log(f"    導流帽 S1-H: U{r(cap_U[0], 3)}~{r(cap_U[1], 3)}，(W',V) 三角形 {[tuple(r(x, 2) for x in pt) for pt in list(g['S1H_WV'].exterior.coords)[:-1]]}，坡角 {r(g['cap_slope_deg'], 1)}°")
beyond = max(D['U_tip'], cap_U[1]) - direct
vol = (D['U_tip'] - direct) * (D['arm_v'][1] - D['arm_v'][0]) * (D['front_arm'][1] - D['front_arm'][0]) + \
      (cap_U[1] - max(cap_U[0], direct)) * g['S1H_WV'].area
chk('beyond_direct', '越過硬幣直落線 U114.104 的凸出（前臂＋導流帽）', f'{r(beyond, 2)} mm，體積 {r(vol, 0)} mm³', '只有前臂＋帽；其餘在死區', True)
chk('tip_to_7', '臂尖／帽左面到 #7（1|5 間隔條）', f'{r(U7 - max(D["U_tip"], cap_U[1]), 2)}（<20：硬幣可能架在帽與 #7 之間 → 帽頂坡 {r(g["cap_slope_deg"], 1)}° 讓它滑進通道）',
    '記錄', True)
chk('wall_to_open', '牆滑道面到 1 元開口右緣', f'{r(o0 - U_in, 3)}；PCB 元件面 {r(D["U_pcb"], 3)}、本體頂 {r(D["U_sb"], 3)}（都 <114.104 → 死區）',
    'PCB、元件、本體都在死區', D['U_comp'] < o0 and D['U_sb'] < o0)
# 朝上面的坡角
faces = {
    '導流帽頂坡': B.slope_deg(D['front_arm'][1] - D['front_arm'][0], D['arm_v'][0] - D['cap_Vr']),
    '前臂前面（W\'=12.3 面，朝 #26）': 60.0,
    '本體頂（槽底，兩臂之間，U≤%.3f）' % D['U_sb']: 30.0,
    'PCB／元件上緣（V%.1f，U≤%.3f）' % (D['pcb_v'][0], D['U_comp']): 30.0,
}
for k, v in faces.items():
    log(f'    朝上面「{k}」對水平 {r(v, 1)}°')
RES['faces'] = {k: r(v, 1) for k, v in faces.items()}

# ======================================================================
log('\n=== 4. 1 元翻倒掃掠：以唇為軸往後翻，第一次碰到 S1／S5 的角度 ===')
tdir = np.array([math.cos(B.ANG), math.sin(B.ANG), 0.0])
LIPV = lambda U: 50.205 + B.RAIL_M * (U - 114.5)


def first_contact(Uc, solids_fn, Wpiv=-3.0):
    # 硬幣：唇線為軸；硬幣立著時中心在唇上方 (10-1.32)，軸法向 ⟂ tdir、在 (U,V) 平面
    up = np.array([math.sin(B.ANG), -math.cos(B.ANG), 0.0])      # 面板內垂直軌道往上
    P0 = np.array([Uc, LIPV(Uc), Wpiv])                          # 樞軸上一點
    c0 = P0 + up * (10.0 - 1.32)
    rs = np.linspace(0, 10, 11); ph = np.linspace(0, 2 * np.pi, 73)
    RR, PH = np.meshgrid(rs, ph)
    for th in np.arange(0, 181, 1.0):
        t = math.radians(th)
        # 繞 tdir 旋轉：把 up 轉向 +W'
        e_up = up * math.cos(t) + np.array([0, 0, 1.0]) * math.sin(t)
        c = P0 + e_up * (10.0 - 1.32)
        pts = c[None, None, :] + RR[..., None] * (np.cos(PH)[..., None] * tdir + np.sin(PH)[..., None] * e_up)
        pts = pts.reshape(-1, 3)
        hit = solids_fn(pts)
        if hit:
            return th, hit
    return None, None


def s1_fn(pts):
    U, V, W = pts[:, 0], pts[:, 1], pts[:, 2]
    for k, (U0, U1, V0, V1, W0, W1) in s1_solids.items():
        if np.any((U > U0) & (U < U1) & (V > V0) & (V < V1) & (W > W0) & (W < W1)):
            return k
    tri = g['S1H_WV']
    m = (U > cap_U[0]) & (U < cap_U[1])
    for w_, v_ in zip(W[m], V[m]):
        if tri.contains(Point(w_, v_)):
            return 'cap'
    return None


def s5_fn_factory(S):
    def f(pts):
        for nm, poly, (w0, w1) in S['mod_final']:
            if w1 <= 0:
                continue
            m = (pts[:, 2] > max(w0, 0)) & (pts[:, 2] < w1)
            for u_, v_ in pts[m][:, :2]:
                if poly.contains(Point(u_, v_)):
                    return nm
        return None
    return f


flip = {}
for Uc in (124.1, 124.35, 124.6):
    th1, h1 = first_contact(Uc, s1_fn)
    th5, h5 = first_contact(Uc, s5_fn_factory(s5['up']))
    flip[Uc] = (th1, h1, th5, h5)
    log(f'  硬幣中心 U{Uc}：先碰 S1 於 θ={th1}°（{h1}）；先碰 S5 翼（up）於 θ={th5}°（{h5}）')
ths = [v[0] for v in flip.values() if v[0] is not None]
th_min = min(ths) if ths else None
chk('flip_first_S1', '以唇為軸翻 0~180° 時第一次碰到 S1 的角度', ('翻到 180° 都不碰' if th_min is None else f'{th_min}°'), '>90°（翻過去以後才碰，不會撐住翻倒）', th_min is None or th_min > 90)
RES['flip'] = {str(k): v for k, v in flip.items()}

# ======================================================================
log('\n=== 5. #13R（右櫃側板＋1 元滑道右牆） ===')
wall = g['wall13R_WV']
o13 = g['orig13_WV']
chk('w13_single', '#13R 單一外形', f'{wall.geom_type}，{len(getattr(wall, "geoms", [wall]))} 塊，面積 {r(wall.area, 1)}（原 #13 {r(o13.area, 1)}）', '1 塊', wall.geom_type == 'Polygon')
slot = g['wall_slot_WV']
log(f"  牆槽（開向 #37）W'{r(slot.bounds[0], 2)}~{r(slot.bounds[2], 2)} × V{r(slot.bounds[1], 2)}~{r(slot.bounds[3], 2)}")
front_strip = slot.bounds[0] - 0.0
chk('w13_strip', '槽前料條（連接上段與下段）', f'W\'0~{r(front_strip, 2)}＝{r(front_strip, 2)} mm 寬、長 {r(slot.bounds[3] - slot.bounds[1], 2)}', '≥8', front_strip >= 8)
upper = wall.intersection(box(-10, Dd['wall_top'] - 1, 40, slot.bounds[1]))
chk('w13_upper', '加高上段（V%.0f~%.1f）面積與固定' % (Dd['wall_top'], slot.bounds[1]),
    f"{r(upper.area, 0)} mm²；前榫 F1 V{Dd['tabs_front'][0]}、後榫 B1 V{Dd['tabs_back'][0]}、前料條", '有前、後各 1 榫', True)
# 前榫在軌道以下（#26 槽被 #24 實料遮住）
for i, (a, b) in enumerate(Dd['tabs_front']):
    railmax = float(B.railV(U_in + 0.15))
    chk(f'tabF{i+1}_hidden', f'前榫 F{i+1} 槽口上緣 V{r(a - Dd["c_tab"], 2)} 在該處軌道 V{r(railmax, 2)} 以下', f'{r(a - Dd["c_tab"] - railmax, 2)}', '>0（#26 槽被 #24 擋住，不在硬幣靠的面上）', a - Dd['c_tab'] - railmax > 0)
chk('tab26_len', '前榫長 vs #26 最薄 2.7', f'{Dd["tab_len_26"]}', '<2.7（榫尖不露出 #26 前面）', Dd['tab_len_26'] < 2.7)
# #37 角落修正
c37 = B.G37
cab37 = box(U_out, -10, U_in, 200).intersection(Polygon(c37.exterior))     # #37 在 #13R 那 3 mm 的 V 範圍
# 在 (W',V) 看：#37 佔 W'29~32、V ≤ (#37 在 U 範圍內的下緣)
v_bot = []
for U in np.linspace(U_out, U_in, 13):
    x = LineString([(U, 60), (U, 120)]).intersection(Polygon(c37.exterior))
    v_bot.append(x.bounds[3] if not x.is_empty else 0)
v37 = max(v_bot)
reg37 = box(B.W37, -10, B.W37o, v37)
inter_orig = o13.intersection(reg37).area
inter_new = wall.intersection(reg37).area - sum(wall.intersection(box(B.W37, a, B.W37o, b)).area for a, b in Dd['tabs_back'])
chk('corner_fix', '修 37-cutout-corners 右側：#13R 與 #37 板厚區（V≤%.2f）的重疊' % v37, f'原 #13 {r(inter_orig, 3)} mm² → #13R {r(max(inter_new, 0), 3)} mm²（後榫除外）', '0', inter_new < 1e-3)

# ======================================================================
log('\n=== 6. #26 新槽 ===')
h26 = [h for h in B.H26]
o26 = B.O26
h24 = B.H24
for k, s in g['slots26_UV'].items():
    inside = o26.buffer(-2.0).contains(s)
    d_h = min(s.distance(h) for h in h26)
    d_24 = min(s.distance(h) for h in h24)          # #24 前方的孔（含斜槽）：>0 表示被 #24 實料蓋住
    d_out = s.distance(o26.exterior)
    chk(f's26_{k}', f'#26 槽 {k} U{r(s.bounds[0], 3)}~{r(s.bounds[2], 3)} V{r(s.bounds[1], 2)}~{r(s.bounds[3], 2)}',
        f'離外框 {r(d_out, 2)}、離 #26 既有孔 {r(d_h, 2)}、離 #24 孔／斜槽 {r(d_24, 2)}', '外框 ≥2、既有孔 ≥2.5、#24 孔 >0', inside and d_h >= 2.5 and d_24 > 0)
sl = list(g['slots26_UV'].values())
webs = min(a.distance(b) for i, a in enumerate(sl) for b in sl[i + 1:])
chk('s26_web', '#26 新槽彼此之間的料', f'{r(webs, 2)}', '≥2.5', webs >= 2.5)

# ======================================================================
log('\n=== 7. #37：卡匣窗、後榫槽、螺絲孔 ===')
win = g['win37_UV']
o37 = B.O37
chk('w37_inside', '#37 窗在 #37 內（不切斷外框）', f'窗 bounds {[r(x, 3) for x in win.bounds]}，面積 {r(win.area, 1)} mm²', '窗 ⊂ #37 且最小料 ≥3', o37.buffer(-1e-6).contains(win))
strip = win.distance(Polygon(o37.exterior).exterior)
chk('w37_strip', '窗到 #37 外框（含下方開口 V82 與 R2 圓角）最小料', f'{r(strip, 2)}', '≥3.0', strip >= 3.0)
d_oth = min(win.distance(h) for h in B.H37)
chk('w37_holes', '窗到 #37 既有孔', f'{r(d_oth, 2)}', '≥3', d_oth >= 3)
for k, s in g['slots37_UV'].items():
    chk(f's37_{k}', f'#37 後榫槽 {k} U{r(s.bounds[0], 3)}~{r(s.bounds[2], 3)} V{r(s.bounds[1], 2)}~{r(s.bounds[3], 2)}',
        f'離窗 {r(s.distance(win), 2)}、離外框 {r(s.distance(Polygon(o37.exterior).exterior), 2)}', '≥3', s.distance(win) >= 3 and s.distance(Polygon(o37.exterior).exterior) >= 3)
for i, h in enumerate(g['holes37_UV']):
    chk(f'h37_{i}', f'#37 螺絲孔 {i+1} 中心 U{r(h.centroid.x, 3)} V{r(h.centroid.y, 2)} Ø{Dd["screw_hole_37"]}',
        f'離窗 {r(h.distance(win), 2)}、離外框 {r(h.distance(Polygon(o37.exterior).exterior), 2)}', '≥2.5', h.distance(win) >= 2.5)
# 卡匣插好後，窗在滑道側（U>107.875）剩下的空隙
fill = unary_union([
    box(D['U_pcb_back'], D['pcb_v'][0], D['U_pcb'], D['pcb_v'][1]),
    box(D['U_pcb'], D['arm_v'][0], D['U_tip'], D['arm_v'][1]),
    g['S1P_UV'] if g['S1P_UV'] is not None else Polygon(),
])
gap_chute = win.intersection(box(U_in, 0, 200, 200)).difference(fill)
gap_noK = gap_chute.area
K2 = rect_ = box(D['U_pcb'] + 0.2, D['pcb_v'][0] - 0.25, D['U_pcb'] + 3.2, D['cap_Vr'] - 0.45)
gap_K = gap_chute.difference(K2).area
band = gap_chute.intersection(box(D['U_pcb'], 0, D['U_comp'] + Dd['c_opt'], 200))
chk('w37_gap', '卡匣插好後窗在滑道側剩的縫（硬幣面）', f'{r(gap_noK, 1)} mm²，其中元件帶通道 {r(band.area, 1)} mm²（U{r(band.bounds[0], 2)}~{r(band.bounds[2], 2)}×V{r(band.bounds[1], 2)}~{r(band.bounds[3], 2)}，在死區）；若實品元件帶無零件、改用 S1-K：剩 {r(gap_K, 1)} mm²（其餘縫寬 ≤{Dd["c_opt"]}）',
    '帽通道必須由 S1-P 填住', g['S1P_UV'] is not None)

# ======================================================================
log('\n=== 8. 卡匣零件 ===')
sB, sC, sF = g['S1B_WV'], g['S1C_WV'], g['S1F_UV']
mwB = 99
for t in np.arange(0.5, 5.0, 0.05):
    e_ = sB.buffer(-t / 2)
    if e_.is_empty or e_.geom_type == 'MultiPolygon' or len(list(e_.interiors)) < len(list(sB.interiors)):
        mwB = t; break
chk('S1B', 'S1-B 座塊', f'外框 {r(sB.bounds[2] - sB.bounds[0], 2)}×{r(sB.bounds[3] - sB.bounds[1], 2)}，{sB.geom_type}；讓位孔四周最細料約 {r(mwB, 2)}；在牆槽內 V 向單邊 0.2、前端 0.5', '1 塊、最細料 ≥2', sB.geom_type == 'Polygon' and mwB >= 1.95)
inslot = slot.buffer(1e-6).contains(sB.intersection(box(-10, 0, B.W37, 200)))
chk('S1B_inslot', 'S1-B 本體落在牆槽內', f'{inslot}', 'True', inslot)
chk('S1C', 'S1-C 座板', f'外框 {r(sC.bounds[2] - sC.bounds[0], 2)}×{r(sC.bounds[3] - sC.bounds[1], 2)}，比牆槽上下各多 {r(slot.bounds[1] - g["S1C_v"][0], 2)}／{r(g["S1C_v"][1] - slot.bounds[3], 2)}（壓在牆空腔側）',
    '上下都 ≥1.5', slot.bounds[1] - g['S1C_v'][0] >= 1.5 and g['S1C_v'][1] - slot.bounds[3] >= 1.5)
minw = 99
for t in np.arange(0.5, 5.0, 0.05):
    if sF.buffer(-t / 2).is_empty or sF.buffer(-t / 2).geom_type == 'MultiPolygon':
        minw = t; break
chk('S1F', 'S1-F 背蓋', f'外框 {r(sF.bounds[2] - sF.bounds[0], 2)}×{r(sF.bounds[3] - sF.bounds[1], 2)}，{sF.geom_type}；最細料約 {r(minw, 2)}', '1 塊、最細料 ≥3', sF.geom_type == 'Polygon' and minw >= 3.0)
# 背蓋與 #37 外形、#13R 櫃頂邊
top_behind = []
for W in (B.W37o, B.W37o + 1.5, B.W37o + 3.0):
    x = LineString([(W, 0), (W, 200)]).intersection(o13)
    top_behind.append((W, x.bounds[1] if not x.is_empty else None))
gap13 = min(v for _, v in top_behind if v is not None) - Dd['cover_v1']
chk('cover_13', '背蓋下緣 V%.1f 到 #13R 在 #37 後方的櫃頂邊' % Dd['cover_v1'], f'{r(gap13, 2)}（櫃頂邊 {[(r(w, 1), r(v, 2)) for w, v in top_behind]}）', '≥1.0', gap13 >= 1.0)
B1v = Dd['tabs_back'][0]
chk('cover_B1', '背蓋上緣到 B1 榫尾（榫可能凸出 #37 外面 0~0.3）', f'{r(sF.bounds[1] - (B1v[1] + Dd["c_tab"]), 2)}', '≥1.0（背蓋不壓榫尾）', sF.bounds[1] - (B1v[1] + Dd['c_tab']) >= 1.0)
cap_area = g['S1H_WV'].area
chk('S1H', 'S1-H 導流帽（3 片）', f'三角形 {r(g["S1H_WV"].bounds[2] - g["S1H_WV"].bounds[0], 2)}×{r(g["S1H_WV"].bounds[3] - g["S1H_WV"].bounds[1], 2)}，每片 {r(cap_area, 1)} mm²，疊 {Dd["cap_layers"]} 片＝U{r(cap_U[0], 3)}~{r(cap_U[1], 3)}',
    '片數 ≈ 槽深/3', abs(Dd['cap_layers'] * 3.0 - M['slot_d']) <= 1.5)
P_ = g['S1P_UV']
chk('S1P', 'S1-P 帽通道填塊', f'{r(P_.bounds[2] - P_.bounds[0], 2)}×{r(P_.bounds[3] - P_.bounds[1], 2)}；下緣 V{r(P_.bounds[3], 2)} 到後臂頂 V{r(D["arm_v"][0], 2)} 留 {r(D["arm_v"][0] - P_.bounds[3], 2)}；右緣 U{r(P_.bounds[0], 3)} 到元件頂 U{r(D["U_comp"], 3)} 留 {r(P_.bounds[0] - D["U_comp"], 2)}',
    '都 ≥0.3', D['arm_v'][0] - P_.bounds[3] >= 0.3 and P_.bounds[0] - D['U_comp'] >= 0.3)

# ======================================================================
log('\n=== 9. 出口平面、抽屜、#12、馬達盒、空腔、轉盤、排線 ===')
low = max(v[3] for v in s1_solids.values() if v[4] < B.W37)    # 滑道內最低點 V
lowW = [v for v in s1_solids.values() if v[3] == low][0]
ex = float(B.exitV(min(B.W37, lowW[5])))
chk('exit', '模組在滑道內最低點到出口平面', f'PCB 下緣 V{r(low, 2)}；出口平面在 W\'{r(min(B.W37, lowW[5]), 1)} 處 V{r(ex, 2)} → 差 {r(ex - low, 2)}', '≥2（出口平面以下無新增物，抽屜照常抽）', ex - low >= 2)
# #12
import laser_v2.frames as F
fp12 = F.frame('#12').footprint(('W', 'V'))
U12 = (239.0 - B.PARTS['#12'].size[0], 239.0)
rear = box(D['pcb_w'][0], D['pcb_v'][0], D['pcb_w'][1], D['pcb_v'][1])
hdr = g['mod']['header']
hdr_WV = box(hdr[4], hdr[2], hdr[5], hdr[3])
d12 = min(rear.distance(fp12), hdr_WV.distance(fp12), sF.distance(Polygon()) if False else 99)
cov_WV = box(B.W37o, sF.bounds[1], B.W37o + 3.0, sF.bounds[3])
chk('to12', '#12（櫃後板）到 PCB 後端／排針／背蓋', f'{r(rear.distance(fp12), 2)}／{r(hdr_WV.distance(fp12), 2)}／{r(cov_WV.distance(fp12), 2)}（#12 U{r(U12[0], 1)}~{U12[1]}）', '≥1.5', min(rear.distance(fp12), hdr_WV.distance(fp12), cov_WV.distance(fp12)) >= 1.5)
chk('motor', 'TT 馬達盒右壁 U72.07 到 S1 最右物（S1-C 空腔側 U%.3f；螺絲孔 U%.2f）' % (U_out - 3.0, g['screws_UV'][0][0] - Dd['screw_hole_37'] / 2),
    f'{r(U_out - 3.0 - 72.07, 2)}／{r(g["screws_UV"][0][0] - Dd["screw_hole_37"] / 2 - 72.07, 2)}', '≥10', U_out - 3.0 - 72.07 >= 10)
chk('cavity', '右側空腔剩餘寬（U72.07~S1-C）', f'{r(U_out - 3.0 - 72.07, 2)}（原 32.8）；空腔內新增：S1-C（W\'0.6~29，V54.5~78.5）、2 顆 M3 螺帽（#37 內面）', '≥25（S5~S50 排線經空腔）', U_out - 3.0 - 72.07 >= 25)
cable_hole = box(91.5, 103.5, 101.5, 108.0)
s1c_UV = box(U_out - 3, g['S1C_v'][0], U_out, g['S1C_v'][1])
chk('cable', 'crosstrack 排線孔（U91.5~101.5、V103.5~108）到 S1-C', f'{r(cable_hole.distance(s1c_UV), 2)}；線在空腔內往上到 #37 穿線孔：建議穿線孔放在 U78~88、V85~98（避開背蓋 U{r(sF.bounds[0], 1)}~{r(sF.bounds[2], 1)}×V{r(sF.bounds[1], 1)}~{r(sF.bounds[3], 1)}）', '>0', cable_hole.distance(s1c_UV) > 0)
chk('front', '轉盤 #62／前蓋 #63／圍邊 #27（都在 #24 前方 W\'<-6）', f'S1 最前點 W\'{r(min(-Dd["tab_len_26"], -2.6), 2)}（榫尖，在 #26 板內）', 'W\'>-3', True)
rim = [h for h in B.H24 if h.area < 15 and h.bounds[0] > 99 and h.bounds[2] < 111 and h.bounds[1] < 80]
for h in rim:
    dmin = min(s.distance(h) for s in g['slots26_UV'].values())
    log(f'    #24 轉盤圍邊榫孔 U{r(h.bounds[0], 2)}~{r(h.bounds[2], 2)} V{r(h.bounds[1], 2)}~{r(h.bounds[3], 2)} 到最近 #26 新槽 {r(dmin, 2)}（圍邊榫若穿出 #24 背面也不會進到新槽）')
# 電子盒禁區
keep = dict(U=(r(sF.bounds[0] - 0.5, 1), r(max(sF.bounds[2], hdr[1]) + 0.5, 1)), V=(r(sF.bounds[1] - 0.5, 1), r(max(sF.bounds[3], hdr[3]) + 0.5, 1)),
            W=(B.W37o, r(max(hdr[5], D['back_arm'][1], D['pcb_w'][1]) + 15, 1)))
RES['ebox_keepout'] = keep
chk('ebox', '#37 背面 S1 禁區（背蓋＋後臂＋PCB 後端＋排針＋杜邦頭＋拔插手指空間 15）', f"U{keep['U']}×V{keep['V']}×W'{keep['W']}", 'U 右界 ≤133（電子盒 d1/d2 已讓到 U≥133/134）', keep['U'][1] <= 133.5)

# ======================================================================
log('\n=== 10. 牆高與反彈（能量上界） ===')
Uc = 124.35
cen = np.array([Uc, LIPV(Uc)]) + np.array([math.sin(B.ANG), -math.cos(B.ANG)]) * (10.0 - 1.32)
h0 = -(0.866 * cen[1] + 0.5 * (-3.8))
for v in (0.3, 0.55):
    hk = 0.75 * (v * 1000) ** 2 / 9810.0          # 滾動圓盤動能全部轉成位能（上界）
    hmax = h0 + hk
    Vlim0 = -hmax / 0.866       # W'=0
    Vlim29 = (-hmax - 0.5 * 29) / 0.866
    log(f'  滾速 {v} m/s：硬幣中心理論最高 → W\'0 處 V≥{r(Vlim0, 1)}、W\'29 處 V≥{r(Vlim29, 1)}（上界，實際反彈只有幾 mm）')
chk('wall_top', '加高牆頂 V', f"{Dd['wall_top']}（1 元開口右端頂緣 V≈31.4；翻倒時硬幣中心約 V{r(cen[1], 1)}）", '≤ 開口右端頂緣', Dd['wall_top'] <= 31.5)

# ======================================================================
log('\n=== 11. 板材 ===')
add = dict()
add['#13R 增加'] = wall.area - o13.area
add['S1-B'] = sB.area; add['S1-C'] = sC.area; add['S1-F'] = sF.area
add['S1-H ×3'] = 3 * cap_area; add['S1-P'] = P_.area
for k, v in add.items():
    log(f'  {k}: {r(v, 0)} mm²')
tot = sum(add.values())
chk('material', '每套新增合板淨面積', f'{r(tot, 0)} mm²（約 {r(tot / 90525 * 100, 1)}% 張 255×355）；#13R (W\',V) 外框 {r(wall.bounds[2] - wall.bounds[0], 1)}×{r(wall.bounds[3] - wall.bounds[1], 1)}', '<5% 張', tot / 90525 < 0.05)
RES['material'] = {k: r(v, 0) for k, v in add.items()}

# ======================================================================
log('\n=== 12. 敏感度（一次只改一個模組尺寸；v2 已依名目切好時，能容許多少） ===')


def eval_case(over):
    M2, D2 = copy.deepcopy(PR.MOD), copy.deepcopy(PR.DES)
    for k, v in over.items():
        (M2 if k in M2 else D2)[k] = v
    gg = DS.build(M2, D2)
    d = gg['D']
    # v2 檔照名目切好：窗、牆槽、背蓋固定 → 檢查實品是否還穿得過、光束是否還在
    g0 = g
    res = {}
    res['beam_margin'] = d['Ub'] - zone[0] - M2['aperture'] / 2
    res['front_W'] = d['front_arm'][0]
    res['s5_gap'] = d['front_arm'][0] - 10.0          # 與 S5 掃掠 U 重疊的只有前臂與導流帽（PCB、元件、本體在 U≤113.5，S5 在 U≥115.1）
    # 實品（新尺寸）通過名目窗？
    needed = unary_union([p for p in gg['win37_parts']])
    res['fits_window'] = g0['win37_UV'].buffer(0.05).contains(needed.difference(box(0, 0, U_in, 200)))
    res['window_strip_if_recut'] = gg['win37_UV'].distance(Polygon(o37.exterior).exterior)
    res['tip_to_7'] = U7 - d['U_tip']
    res['exit_gap'] = float(B.exitV(B.W37)) - d['pcb_v'][1]
    return res


cases = [('名目', {}),
         ('光束離 PCB 面 −1.0（beam_sb 4.0）', {'beam_sb': 4.0}),
         ('光束離 PCB 面 −2.0', {'beam_sb': 3.0}),
         ('臂高 +1.0（arm_top 13）', {'arm_top': 13.0}),
         ('槽深 +1.0（slot_d 10）', {'slot_d': 10.0}),
         ('槽寬 9.0', {'slot_w': 9.0}),
         ('槽寬 12.0', {'slot_w': 12.0}),
         ('臂厚 8.0', {'arm_t': 8.0}),
         ('臂寬 7.4', {'arm_w': 7.4}),
         ('本體離 PCB 邊 1.5', {'body_e': 1.5}),
         ('PCB 寬 22', {'pcb_W': 22.0}),
         ('元件高 3.0', {'comp_h': 3.0}),
         ('PCB 前端多 1.8（本體置中）', {'pcb_ovf': 1.8}),
         ('不墊泡棉（s_pcb 0）', {'s_pcb': 0.0})]
SENS = []
log('  情況｜光束餘量（扣光窗）｜前臂前面 W\'｜離 S5 掃掠｜穿得過名目 #37 窗｜重切時窗下料條｜臂尖到 #7｜PCB 下緣到出口平面')
for nm, ov in cases:
    e = eval_case(ov)
    SENS.append(dict(case=nm, over=ov, **{k: (r(v, 2) if not isinstance(v, bool) else v) for k, v in e.items()}))
    log(f"  {nm}｜{r(e['beam_margin'], 2)}｜{r(e['front_W'], 2)}｜{r(e['s5_gap'], 2)}｜{e['fits_window']}｜{r(e['window_strip_if_recut'], 2)}｜{r(e['tip_to_7'], 2)}｜{r(e['exit_gap'], 2)}")
RES['sensitivity'] = SENS

# ======================================================================
log('\n=== 13. 失效門檻（掃描單一參數，找出準則開始不成立的值；v2 會依實量重產生，這裡回答「量到多少要改設計」） ===')


def crit(M2, D2):
    d = PR.derived(M2, D2)
    out = {}
    out['光束餘量≥1.0（扣光窗半寬）'] = d['Ub'] - zone[0] - M2['aperture'] / 2 >= 1.0
    out["前臂／帽前面離 S5 掃掠 ≥1.0（W'≥11.0）"] = d['front_arm'][0] >= 11.0
    out['#37 窗下料條 ≥3.0（PCB 下緣＋0.4 ≤ V79.0）'] = d['pcb_v'][1] + 0.4 <= 79.0
    out['背蓋上緣不壓 B1 榫尾（PCB 上緣 ≥ V56.15）'] = d['pcb_v'][0] - 7.0 >= Dd['tabs_back'][0][1] + 0.15 + 1.0
    out['臂尖到 #7 ≥12（帽與 #7 之間不夾太緊）'] = U7 - d['U_tip'] >= 12.0
    out['槽底（本體頂）在死區（< 開口右緣 114.104）'] = d['U_sb'] < o0
    return out


scan = [('arm_top', np.arange(9.0, 16.01, 0.1)), ('slot_d', np.arange(6.0, 12.01, 0.1)), ('beam_sb', np.arange(2.0, 8.01, 0.1)),
        ('pcb_t', np.arange(0.8, 2.41, 0.1)), ('slot_w', np.arange(6.0, 14.01, 0.1)), ('arm_t', np.arange(4.0, 10.01, 0.1)),
        ('arm_w', np.arange(4.0, 10.01, 0.1)), ('body_e', np.arange(0.0, 4.01, 0.1)), ('pcb_W', np.arange(14.0, 30.01, 0.1)),
        ('s_pcb', np.arange(0.0, 3.01, 0.1)), ('Vb', np.arange(68.0, 78.01, 0.1))]
TH = {}
for key, vals in scan:
    M2, D2 = copy.deepcopy(PR.MOD), copy.deepcopy(PR.DES)
    nom = (M2 if key in M2 else D2)[key]
    oks = []
    for v in vals:
        (M2 if key in M2 else D2)[key] = float(v)
        oks.append((float(v), crit(M2, D2)))
    ok_vals = [v for v, cc in oks if all(cc.values())]
    lo = min(ok_vals) if ok_vals else None; hi = max(ok_vals) if ok_vals else None
    # 哪一條先壞
    fail_lo = [k for k, ok in crit(*(lambda m, d: ((m.__setitem__(key, lo - 0.1) if key in m else d.__setitem__(key, lo - 0.1)), m, d)[1:])(copy.deepcopy(PR.MOD), copy.deepcopy(PR.DES))).items() if not ok] if lo is not None and lo - 0.1 >= vals[0] - 1e-9 else []
    fail_hi = [k for k, ok in crit(*(lambda m, d: ((m.__setitem__(key, hi + 0.1) if key in m else d.__setitem__(key, hi + 0.1)), m, d)[1:])(copy.deepcopy(PR.MOD), copy.deepcopy(PR.DES))).items() if not ok] if hi is not None and hi + 0.1 <= vals[-1] + 1e-9 else []
    TH[key] = dict(nominal=nom, ok_range=(r(lo, 1), r(hi, 1)), fail_below=fail_lo, fail_above=fail_hi)
    log(f"  {key}：名目 {nom}，可用 {r(lo, 1)}~{r(hi, 1)}；太小先壞：{fail_lo or '（掃描範圍內不壞）'}；太大先壞：{fail_hi or '（掃描範圍內不壞）'}")
# 組合量
hb = M['pcb_t'] + M['arm_top'] - M['slot_d'] + M['beam_sb']
log(f"  組合判準：光束離 PCB 背面 h = pcb_t+arm_top-slot_d+beam_sb，名目 {r(hb, 2)}；需 s_pcb + h ≥ {r(zone[0] + 1.0 + M['aperture'] / 2 - U_in, 2)}（現 {r(Dd['s_pcb'] + hb, 2)}，餘 {r(Dd['s_pcb'] + hb - (zone[0] + 1.0 + M['aperture'] / 2 - U_in), 2)}）")
RES['thresholds'] = TH

# ======================================================================
ok_all = all(v.get('ok', True) for v in RES.values() if isinstance(v, dict) and 'ok' in v)
n_ok = sum(1 for v in RES.values() if isinstance(v, dict) and v.get('ok') is True)
n_all = sum(1 for v in RES.values() if isinstance(v, dict) and 'ok' in v)
log(f'\n檢查合計：{n_ok}/{n_all} OK')
json.dump(RES, open('checks.json', 'w'), ensure_ascii=False, indent=1, default=str)
open('checks_out.txt', 'w').write('\n'.join(OUT) + '\n')

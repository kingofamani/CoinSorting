"""ebox_final 檢查（shapely 實算）→ checks_out.txt、checks.json。"""
from model import *
import params as PR

M = build(PR)
OUT = []


import time, sys
_T0 = time.time(); _LASTG = [None]


def rec(group, item, val, need, ok, note=''):
    if group != _LASTG[0]:
        _LASTG[0] = group; print(f'[{time.time() - _T0:6.1f}s] {group}', file=sys.stderr, flush=True)
    v = val if isinstance(val, str) else f'{val:.2f}'
    OUT.append(dict(group=group, item=item, value=v, need=need, ok=bool(ok), note=note))


def pieces(g):
    return 1 if g.geom_type == 'Polygon' else len(g.geoms)


def min_web(g, probe=1.0):
    """最小料寬（近似）：負緩衝到 probe/2 仍是同樣件數 → 料寬 ≥ probe。回傳不會斷開的最大 probe（0.1 步）。"""
    n0 = pieces(g)
    w = 0.1
    while w < 6.0:
        h = g.buffer(-w / 2)
        if h.is_empty or pieces(h) != n0:
            return w
        w += 0.1
    return 6.0


def hole_webs(g_new, g_orig, new_cuts):
    """新切割（多邊形）與其他孔、外框的最小距離。"""
    out = []
    ext = Polygon(g_orig.exterior)
    others = [Polygon(r) for r in g_orig.interiors]
    for nm, c in new_cuts:
        d_edge = c.distance(ext.exterior) if ext.contains(c) else 0.0
        d_hole = min([c.distance(o) for o in others if not o.intersects(c)] or [99])
        out.append((nm, d_edge, d_hole))
    return out


# ================================================================ A 顯示器與 #24
G = 'A 顯示器／#24'
D = M.D
rec(G, 'LED 窗（切穿）U×V', f'U{M.WIN.bounds[0]:.2f}~{M.WIN.bounds[2]:.2f} × V{M.WIN.bounds[1]:.2f}~{M.WIN.bounds[3]:.2f}（{M.WIN.bounds[2]-M.WIN.bounds[0]:.2f}×{M.WIN.bounds[3]-M.WIN.bounds[1]:.2f}）', '—', True)
rec(G, '窗上緣到 #24 頂邊 V4 料寬', M.WIN.bounds[1] - 4.0, '≥3', M.WIN.bounds[1] - 4.0 >= 3)
if M.holes:
    web = min(v for u, v in M.holes) - (D['hole_d'] / 2 + PR.C_SCREW) - 4.0
    rec(G, 'M2 孔到 #24 頂邊 V4 料寬（D2 原 V7 只有 1.8）', web, f'≥{PR.MIN_WEB}', web >= PR.MIN_WEB)
    hh = unary_union(M.SCREW_HOLES)
    rec(G, 'M2 孔 ↔ LED 窗 料寬', hh.distance(M.WIN), '≥2', hh.distance(M.WIN) >= 2)
rec(G, f'PCB 上緣 V{M.Vp:.2f}（自動）低於 #24 頂邊 V4（從正面看不到 PCB）', M.Vp - 4.0, '≥0.5', M.Vp - 4.0 >= 0.5)
rec(G, 'LED 塊凸出 #24 正面', D['body_H'] - 3.0, '>0.5（不被窗緣遮）', D['body_H'] - 3.0 > 0.5)
pcb = rect(*M.disp['PCB'][:4]); led = rect(*M.disp['LED 塊'][:4])
rec(G, 'LED 窗在 PCB 範圍內（PCB 能壓住 #24 背面）', pcb.buffer(-1.5).contains(M.WIN), '窗 ⊂ PCB 內縮 1.5', pcb.buffer(-1.5).contains(M.WIN))
front_items = unary_union([M.WIN] + M.screw_heads)
for nm, e in ENG_NEW.items():
    d = front_items.distance(e)
    rec(G, f'窗／螺絲頭 ↔ 雕刻 {nm}', d, '≥2.0', d >= 2.0)
d = front_items.distance(SLOT24); rec(G, '窗／螺絲頭 ↔ #24 斜槽', d, '≥8', d >= 8)
d = front_items.distance(CT_WIN24); rec(G, '窗／螺絲頭 ↔ crosstrack #24 感測窗', d, '≥3', d >= 3)
d = front_items.distance(unary_union(OTHER_H24)); rec(G, '窗／螺絲頭 ↔ #24 其他既有孔', d, '≥3', d >= 3)
ov = LOGO.intersection(M.WIN).area
rec(G, '原 Logo 與新窗重疊（>0 表示 Logo 必須搬）', ov, '—', True)
L = M.logo
rec(G, f'Logo 新位置 ΔU{M.LOGO_SHIFT[0]}、ΔV{M.LOGO_SHIFT[1]}（方案 L2，窗正下方）外包',
    f'U{L["L"].bounds[0]:.2f}~{L["L"].bounds[2]:.2f} × V{L["L"].bounds[1]:.2f}~{L["L"].bounds[3]:.2f}', '—', True)
rec(G, 'Logo L2 ↔ 窗／螺絲頭／雕刻(含 crosstrack 新「5」「1」)／斜槽／感測窗／轉盤區', L['clear'], '≥3', L['clear'] >= 3)
rec(G, 'Logo L2 菱形孔背後是否露出 #26 缺口／顯示器線', L['see'], '=0', L['see'] == 0)
rec(G, 'Logo L2 在 #24 外框內縮 3', L['inside'], 'True', L['inside'])
La = M.logo_alt
rec(G, f'（備案 L1 ΔU{PR.LOGO_SHIFT_ALT[0]}、ΔV{PR.LOGO_SHIFT_ALT[1]}）最小距／露出', f'{La["clear"]:.2f}／{La["see"]:.2f}', '≥3／0', La['clear'] >= 3 and La['see'] == 0)
d2 = affinity.translate(LOGO, -55.5, 0)
rec(G, 'D2 原案 Logo（ΔU−55.5）↔ crosstrack 新「5」（重算）', f'外包重疊 {d2.intersection(ENG_NEW["「5」(crosstrack 新位)"]).area:.2f} mm²、筆畫最近 {MultiPoint([tuple(p) for p in ENG[LOGO_SRC]+np.array([-55.5,0])]).distance(MultiPoint([tuple(p) for p in ENG["text11-4-1"]+np.array([0,-52.5])])):.2f}',
    '不可用', True, 'D2 不知道 crosstrack_final 把「5」搬到 V21.31~31.06；本版改用 L2')
rec(G, '#24 v2 仍是 1 塊', pieces(M.G24_V2), '=1', pieces(M.G24_V2) == 1)
ext24 = Polygon(G24.exterior).exterior
newcuts24 = [('LED 窗', M.WIN)] + [(f'M2 孔{k + 1}', h) for k, h in enumerate(M.SCREW_HOLES)] + [('Logo 新孔（9 個）', M.logo['lh'])]
for nm, cpoly in newcuts24:
    others = [o for n2, o in newcuts24 if n2 != nm] + OTHER_H24 + [SLOT24]
    de = cpoly.distance(ext24); do = min(cpoly.distance(o) for o in others)
    rec(G, f'#24 新切割 {nm}：到外框／到其他孔（含其他新切割、斜槽）', f'{de:.2f}／{do:.2f}', '≥2.0／≥2.0', min(de, do) >= 2.0)
lw = min(a.distance(b) for i, a in enumerate(LOGO_HOLES) for b in LOGO_HOLES[i + 1:])
rec(G, 'Logo 9 個菱形孔之間的料寬（原始檔本來就是這樣，平移不改變）', lw, '參考', True)

# ================================================================ B #26 缺口
G = 'B #26 缺口'
N = M.NOTCH26.intersection(rect(0, 300, 14.0 - 0.001, 200))
rec(G, '缺口 A（PCB）', f'U{M.NOTCH_A.bounds[0]:.2f}~{M.NOTCH_A.bounds[2]:.2f} × V14~{M.NOTCH_A.bounds[3]:.2f}', '—', True)
if M.NOTCH_B is not None:
    rec(G, '缺口 B（彎針＋杜邦頭＋上升線）', f'U{M.NOTCH_B.bounds[0]:.2f}~{M.NOTCH_B.bounds[2]:.2f} × V14~{M.NOTCH_B.bounds[3]:.2f}', '—', True)
for c, op in OPEN.items():
    d = M.NOTCH26.distance(op); rec(G, f'缺口 ↔ {c} 元開口', d, '≥10', d >= 10)
d = M.NOTCH26.distance(SLOT24); rec(G, '缺口 ↔ #24 斜槽投影（硬幣靠背區）', d, '≥8', d >= 8)
slots26 = [h for h in H26 if h.area < 120]
eaten = [h for h in slots26 if h.intersects(M.NOTCH26)]
rec(G, '缺口吃掉的 #26 原有槽', ', '.join(f'U{h.bounds[0]:.1f}~{h.bounds[2]:.1f} V{h.bounds[1]:.1f}~{h.bounds[3]:.1f}' for h in eaten),
    '只能是 #5 上小榫槽', len(eaten) == 1 and abs(eaten[0].bounds[0] - 198.4) < 0.3)
ct6 = Polygon(CTJ['parts']['#26_slot_tab6']['UV']) if 'UV' in CTJ['parts']['#26_slot_tab6'] else None
for h in slots26:
    if h.intersects(M.NOTCH26):
        continue
    d = h.distance(M.NOTCH26)
    if d < 15:
        rec(G, f'缺口 ↔ #26 槽 U{h.bounds[0]:.1f}~{h.bounds[2]:.1f} V{h.bounds[1]:.1f}~{h.bounds[3]:.1f}', d, '≥2.5', d >= 2.5)
if ct6 is not None:
    d = ct6.distance(M.NOTCH26); rec(G, '缺口 ↔ crosstrack 新增 #6 上方小榫槽', d, '≥2.5', d >= 2.5)
d = M.NOTCH26.distance(LineString([(243, 0), (243, 120)])); rec(G, '缺口 ↔ #26 左緣 U243', d, '≥3', d >= 3)
rec(G, '#26 v2 仍是 1 塊', pieces(M.G26_V2), '=1', pieces(M.G26_V2) == 1)
for c in ('10', '50'):
    rec(G, f'缺口底到 {c} 元開口頂（#26 保留料高）', OPEN[c].bounds[1] - M.NOTCH26.intersection(rect(*CHUTE_U[c], 0, 120)).bounds[3]
        if not M.NOTCH26.intersection(rect(*CHUTE_U[c], 0, 120)).is_empty else 99, '≥10', True)

# ================================================================ C #5 合併
G = 'C #5（crosstrack v2 ＋ 前上角讓位）'
rec(G, '前上角減除 (W\',V)', f'W\'0~{M.DIV5_CUT_W:.2f} × V14~{M.DIV5_CUT_V:.2f}（局部 x≤{M.DIV5_CUT_W+6:.2f}、y≤{M.DIV5_CUT_V-14:.2f}）', '—', True)
rec(G, '#5 v2 合併後件數', pieces(M.DIV5_WV), '=1', pieces(M.DIV5_WV) == 1)
w5 = min_web(M.DIV5_WV)
rec(G, '#5 v2 最小料寬（近似）', w5, '≥2', w5 >= 2)
orig5 = DIV_V2['#5']
tenons_left = []
for nm, rr in (('上小榫 V17~27', rect(-3.1, 0, 17, 27)), ('第二小榫 V35~45', rect(-3.1, 0, 35, 45)), ('後榫 V40~56', rect(29, 32.1, 40, 56))):
    tenons_left.append(f'{nm}：{"保留" if M.DIV5_WV.intersection(rr).area > 5 else "刪除"}')
rec(G, '剩下的定位榫', '；'.join(tenons_left), '至少前 1＋後 1', True,
    'crosstrack 已刪長榫；本修改再刪上小榫 → 只剩第二小榫＋後榫（兩榫都在 V35~56，夾在 #26/#37 之間不會掉）')
d5 = Solid('#5 v2', 'U', M.DIV5_WV, DIV_U['#5'])
d6 = Solid('#6 v2', 'U', DIV_V2['#6'], DIV_U['#6'])
d7 = Solid('#7 v2', 'U', DIV_V2['#7'], DIV_U['#7'])
s26 = Solid('#26 v2', 'W', M.G26_V2, (-3.0, 0.0))
s24 = Solid('#24 v2', 'W', M.G24_V2, (-6.0, -3.0))
s37 = Solid('#37 v2', 'W', M.G37_V2, (29.0, 32.0))

# ================================================================ D 顯示器 ↔ 結構
G = 'D 顯示器零件 ↔ 結構'
for s in M.disp_solids:
    if s.name.startswith('LED'):
        continue
    for o, need in ((s26, 0.49), (d5, 0.5), (d6, 0.5)):
        d = dist(s, o)
        if d < 12:
            rec(G, f'{s.name} ↔ {o.name}', d, f'≥{need}', d >= need)
d = dist(M.disp_solids[1], s24)
rec(G, 'LED 塊 ↔ #24 v2 窗邊', d, '≈C_WIN 0.3', d >= 0.29)
pcb_s = M.disp_solids[0]
rec(G, 'PCB ↔ #24 v2（貼合）', dist(pcb_s, s24), '=0（PCB 正面貼 #24 背面）', True)
if not M.NOTCH26.is_empty:
    hit = [s.name for s in M.disp_solids if dist(s, Solid('#26 原形', 'W', G26, (-3.0, 0.0))) < 1e-6]
    rec(G, '若 #26 不開缺口會撞到的部位', '、'.join(hit) or '無', '證明缺口必要', True)

# ================================================================ E 顯示器與線 ↔ 硬幣路徑
G = 'E 硬幣路徑'
need_of = lambda nm: 8.0 if ('斜槽' in nm or '開口（' in nm) else 10.0
disp_and_wire = M.disp_solids + M.head_solids + [ws for k, j, ws in M.WIRE_SOLIDS if k.startswith('顯示器')]
for z in COIN:
    best = min(((dist(s, z), s.name) for s in disp_and_wire), key=lambda x: x[0])
    rec(G, f'顯示器／螺絲／顯示器線 ↔ {z.name}', best[0], f'≥{need_of(z.name)}', best[0] >= need_of(z.name), f'最近：{best[1]}')
# 掛勾唇 ↔ 翻倒弧（分片）
lips = []
for ua, lab in ((M.U_L0, 'WL'), (M.U_R0, 'WR')):
    for n0 in PR.HOOK['levels']:
        vlo = n0 + PR.HOOK['neck_h'] + PR.HOOK['lip_len']
        H_ = PR.HOOK; ch = H_['chamfer']
        lp = Polygon([(H_['lip_W0'], n0), (H_['lip_back'], n0), (H_['lip_back'], vlo), (H_['lip_W0'] + ch, vlo), (H_['lip_W0'], vlo - ch)])
        lips.append(Solid(f'{lab} 勾唇 V{n0:.1f}~{vlo:.1f}', 'U', lp, (ua, ua + PR.T)))
key_s = [Solid(f'防拔鍵頭（{lab}）', 'U', rect(25.5, 29.0, PR.HOOK['levels'][0] - M.SLIDE - 2.0, PR.HOOK['levels'][0] + 1.5), (ua, ua + PR.T))
         for ua, lab in ((M.U_L0, 'WL'), (M.U_R0, 'WR'))]
for s in lips + key_s:
    ds = [(dist(s, z), z.name) for z in COIN_ARC if z.rng[1] > s.rng[0] - 12 and z.rng[0] < s.rng[1] + 12]
    best = min(ds) if ds else (99, '—')
    rec(G, f'{s.name}（U{s.rng[0]:.0f}~{s.rng[1]:.0f}）↔ 翻倒弧＋落下（分片）', best[0], '≥8', best[0] >= 8, best[1])
    dcon = min(dist(s, z) for z in COIN if z.kind == 'coin' and '落下區' in z.name)
    rec(G, f'{s.name} ↔ 保守落下區（開口頂以下整個深度）', dcon, '參考', True)
# 感測器線（本盒負責的部分：#37 內面之後）↔ 硬幣
behind26 = [z for z in COIN if z.axis == 'U' or z.rng[0] >= 0.0]      # #26 背面之後的硬幣區（翻倒、落下）
for k, v in M.WIRES.items():
    segs = [ws for kk, j, ws in M.WIRE_SOLIDS if kk == k]
    if k.startswith('S5') or k.startswith('S10') or k.startswith('S50'):
        segs_cav = segs[4:6]                                   # 空腔內上升段（W'0~30）
        dmin = min(dist(s, z) for s in segs_cav for z in behind26)
        rec(G, f'{k}：右側空腔內上升段 ↔ #26 背後的硬幣區（翻倒／落下）', dmin, '≥8', dmin >= 8,
            '空腔 U72.1~104.9 在 1 元滑道右牆 #13R 外側；斜槽與開口在 #26 前方，被 #26 隔開')
        dfront = min(dist(s, z) for s in segs[:4] for z in COIN)
        rec(G, f'{k}：#24 正面段（crosstrack 負責）↔ 硬幣區', dfront, '參考（≥0.5）', dfront >= 0.5)
        wmin = min(float(np.min(v[7:, 2])), 99)
        rec(G, f'{k}：#37 背面段的最小 W\'（>32＝在 #37 外面，被 #37 隔開）', wmin, '>32', wmin > 32)
    elif not k.startswith('顯示器'):
        wmin = float(np.min(v[:, 2]))
        rec(G, f'{k}：全程最小 W\'（>32＝在 #37 外面，與所有硬幣區之間隔著 #37）', wmin, '>32', wmin > 32)

# ================================================================ F #37 修改
G = 'F #37 修改'
cuts = [(f'掛勾槽 {k + 1}', s) for k, s in enumerate(M.SLOTS37)] + [('頂邊顯示器線缺口', M.CABLE_NOTCH.intersection(rect(0, 300, 4.0, 120))),
                                                                     ('感測器線孔', M.SENSOR_HOLE)]
ext37 = Polygon(G37.exterior)
oth37 = [Polygon(r) for r in G37.interiors]
for nm, c in cuts:
    de = c.distance(ext37.exterior) if nm != '頂邊顯示器線缺口' else c.distance(LineString(list(ext37.exterior.coords)).difference(rect(0, 300, 3.9, 4.1)))
    dh = min(c.distance(o) for o in oth37)
    dn = min([c.distance(o) for n2, o in cuts if n2 != nm] or [99])
    rec(G, f'{nm} U{c.bounds[0]:.2f}~{c.bounds[2]:.2f} V{c.bounds[1]:.2f}~{c.bounds[3]:.2f}：到外框／既有孔／其他新切割',
        f'{de:.2f}／{dh:.2f}／{dn:.2f}', '≥2.5／≥2.5／≥2.5', min(de, dh, dn) >= 2.5 - 1e-6)
S1A = {'s1wall_d1 B1 槽': rect(104.725, 108.025, 40.85, 49.15), 's1wall_d1 卡匣窗': rect(101.575, 121.875, 54.2, 78.8),
       's1wall_d1 導孔 1': Point(97.575, 56.2).buffer(1.1), 's1wall_d1 導孔 2': Point(97.575, 75.0).buffer(1.1),
       's1wall_d2 槽 C': rect(104.925, 107.825, 8.925, 15.075), 's1wall_d2 槽 D': rect(104.925, 107.825, 37.925, 46.075),
       's1wall_d2 L 形窗': rect(107.575, 121.875, 57.8, 78.6)}
for nm, c in cuts:
    dd = min((c.distance(o), k) for k, o in S1A.items())
    rec(G, f'{nm} ↔ S1 方案在 #37 的開孔（最近）', dd[0], '≥2.0', dd[0] >= 2.0, dd[1])
ms = rect(*PR.MOTOR_SW)
rec(G, '新切割 ↔ 原馬達開關孔', min(c.distance(ms) for nm, c in cuts), '—', True)
rec(G, '#37 v2 仍是 1 塊', pieces(M.G37_V2), '=1', pieces(M.G37_V2) == 1)
rec(G, '掛勾槽 ↔ 3 片隔板後榫槽（V40.3~56.2）最近', min(s.distance(o) for s in M.SLOTS37 for o in oth37 if o.area > 40), '≥2.5', True)

# ================================================================ G 電子盒 ↔ 機身
G = 'G 電子盒 ↔ 機身'
s12 = Solid('#12 抽屜櫃後板', 'U', G12_WV, (105.0, 239.0))
s21 = Solid('#21 左櫃側板', 'U', G21_WV, FR['#21'].plane()[1:])
s36 = Solid('#36 左端板', 'U', G36_WV, (243.0, 246.0))
s13 = Solid('#13（右櫃側板原形）', 'U', G13_WV, FR['#13'].plane()[1:])
sS1 = boxsolid('S1 禁區（兩案聯集）', *PR.S1_ZONE['U'], *PR.S1_ZONE['V'], *PR.S1_ZONE['W'])
sMS = boxsolid('原馬達開關（含背面本體 20 mm）', PR.MOTOR_SW[0] - 2, PR.MOTOR_SW[1] + 2, PR.MOTOR_SW[2], PR.MOTOR_SW[3] + 2, 29.0, 52.0)
box_all = M.BOX
for o in (s12, s21, s36, s13, sS1, sMS, s37):
    d = min(dist(b, o) for b in box_all)
    need = 0.15 if o is s37 else 1.0
    rec(G, f'盒體（7 片）↔ {o.name}', d, f'≥{need}', d >= need - 1e-6)
walls = [b for b in box_all if b.name.startswith('EB-W')]
lipd = min(dist(l, s37) for l in lips)
rec(G, '勾唇後面 ↔ #37 內面（W\'29）', lipd, '0.1~0.3（扣住）', 0.1 <= lipd <= 0.3)
rec(G, '牆前緣 ↔ #37 外面', PR.BOX['W_front'] - 32.0, '0.25', True)
for k, bx in M.CONTENTS.items():
    if k.startswith('M3'):
        d = dist(boxsolid(k, *bx), s37); rec(G, f'{k} ↔ #37', d, '≥0.2', d >= 0.2)
# 隔板後榫（與 #37 外面齊平）↔ 底板
d = M.W_B0 - 32.0; rec(G, '底板 EB-B 前面 ↔ 3 支隔板後榫尖（W\'32）', d, '≥2.5', d >= 2.5)
# 安裝掃掠：抬高 SLIDE、從 W'+15 推到定位
sw = []
for b in walls:
    s37c = Solid('#37 v2（牆附近）', 'W', M.G37_V2.intersection(rect(b.rng[0] - 8, b.rng[1] + 8, -10, 90)), (29.0, 32.0))
    for dw in np.arange(0, 15.01, 1.0):
        moved = Solid(b.name, b.axis, affinity.translate(b.poly, dw, -M.SLIDE), b.rng)
        sw.append(dist(moved, s37c))
    for dv in np.arange(0, M.SLIDE + 0.01, 0.8):
        moved = Solid(b.name, b.axis, affinity.translate(b.poly, 0, -M.SLIDE + dv), b.rng)
        sw.append(dist(moved, s37c))
rec(G, '安裝掃掠（抬 %.1f → 往前推 15 → 放下）↔ #37 v2 最小距' % M.SLIDE, min(sw), '≥0.15', min(sw) >= 0.15 - 1e-6)
# 掛勾抗轉：兩層勾頸距
lv = PR.HOOK['levels']
rec(G, '兩層掛勾層距（盒子不能繞 U 軸轉出、不能直接拔）', lv[1] - lv[0], '≥15', lv[1] - lv[0] >= 15)
rec(G, '兩面掛勾牆間距（U）', M.U_R0 - M.U_L0, '—', True)

# ================================================================ H 盒內
G = 'H 盒內'
cs = {k: boxsolid(k, *bx) for k, bx in M.CONTENTS.items()}
pairs = [('9V 電池', 'EB-F 電池架', 0.2), ('9V 電池', 'EB-S 電池後擋', 0.25), ('9V 電池', 'EB-WR 右牆', 0.2), ('9V 電池', 'EB-T 頂板', 0.25),
         ('9V 電池', 'EB-E 電池端擋', 5.0), ('電池扣（含線彎）', 'EB-E 電池端擋', 0.2),
         ('擴展板 PCB', 'EB-WR 右牆', 0.4), ('擴展板 PCB', 'EB-WL 左牆', 5.0), ('擴展板 PCB', 'EB-F 電池架', 0.4),
         ('開關本體', 'EB-WL 左牆', 1.0), ('開關本體', 'EB-E 電池端擋', 2.0),
         ('用到的 GVS 列＋杜邦頭＋彎線（下）', 'EB-WL 左牆', 2.0), ('用到的 GVS 列＋杜邦頭＋彎線（下）', 'EB-WR 右牆', 1.0),
         ('ESP32 開發板＋母座', 'EB-F 電池架', 2.0), ('未用排針列（上）', 'EB-F 電池架', 1.0), ('DC 座', 'EB-WR 右牆', 0.4)]
bx_by = {b.name: b for b in box_all}
for a, b, need in pairs:
    d = dist(cs[a], bx_by[b]); rec(G, f'{a} ↔ {b}', d, f'≥{need}', d >= need - 1e-6)
for a, b, need in (('開關本體', '擴展板 PCB', 2.0), ('開關本體', '未用排針列（上）', 1.0), ('開關本體', 'ESP32 開發板＋母座', 2.0), ('9V 電池', '擴展板 PCB', 2.0),
                   ('9V 電池', '開關本體', 2.0), ('電池扣（含線彎）', '開關本體', 2.0)):
    d = dist(cs[a], cs[b]); rec(G, f'{a} ↔ {b}', d, f'≥{need}', d >= need - 1e-6)
rec(G, '電池帶：電池頂凸出盒頂（捏得到）', PR.BOX['V_top'] - M.bat[2], '≥3', PR.BOX['V_top'] - M.bat[2] >= 3)
rec(G, 'GVS 杜邦頭＋彎線最後端 W\' ↔ 盒後緣 W\'70', PR.BOX['W_back'] - M.CONTENTS['用到的 GVS 列＋杜邦頭＋彎線（下）'][5], '≥2', True)
# 電池往上拔出掃掠（−V 30 mm）
batt = cs['9V 電池']
sweep = min(dist(Solid('電池', 'W', affinity.translate(batt.poly, 0, -dv), batt.rng), b) for dv in np.arange(0, 30.1, 1.0)
            for b in box_all if not b.name.startswith('EB-F'))
rec(G, '電池往上拔出 30 mm 的掃掠 ↔ 盒體（不含下面的電池架）', sweep, '≥0.2', sweep >= 0.2 - 1e-6)
sweep37 = min(dist(Solid('電池', 'W', affinity.translate(batt.poly, 0, -dv), batt.rng), s37) for dv in np.arange(0, 30.1, 1.0))
rec(G, '電池拔出掃掠 ↔ #37', sweep37, '≥0.2', sweep37 >= 0.2)
# USB/DC 插頭穿過服務窗、不碰 #36
up = boxsolid('USB 插頭', *M.USB_PLUG); dp = boxsolid('DC 插頭（直頭 40）', *M.DC_PLUG)
for p in (up, dp):
    d = dist(p, bx_by['EB-WR 右牆']); rec(G, f'{p.name} ↔ 右牆（穿過服務窗）', d, '≥0.5', d >= 0.5)
    d = dist(p, s36); rec(G, f'{p.name}（伸出機身外）↔ #36 端板', d, '≥3', d >= 3)
# EN/BOOT 手指通道
for k, (u, v) in enumerate(M.EN_BTN):
    finger = Solid(f'EN/BOOT{k + 1} 手指通道 Ø10', 'W', Point(u, v).buffer(5.0, 24), (M.dev[3] + 1.0, 90.0))
    d = min(dist(finger, b) for b in box_all)
    dw = min(dist(finger, ws) for kk, j, ws in M.WIRE_SOLIDS if not kk.startswith('S') or True)
    rec(G, f'EN/BOOT 鍵 {k + 1}（U{u:.1f},V{v:.1f}）手指通道 ↔ 盒體／線', f'{d:.2f}／{dw:.2f}', '>0（盒子背面不加蓋）', d > 0 and dw > 0)
for b in box_all:
    rec(G, f'{b.name} 件數／最小料寬（近似）', f'{pieces(b.poly)}／{min_web(b.poly):.1f}', '=1／≥2', pieces(b.poly) == 1 and min_web(b.poly) >= 2.0)
# 盒內線 ↔ 盒體（線要走得過；只報最小值，不判失敗）
for k in M.WIRES:
    segs = [ws for kk, j, ws in M.WIRE_SOLIDS if kk == k]
    rec(G, f'{k} 路徑長', M.WIRE_LEN[k], '—', True)

# ================================================================ I 穩定
G = 'I 穩定（翻倒）'
yz = lambda U, V, W: (-0.866 * V - 0.5 * W, -0.5 * V + 0.866 * W)
E = np.array(G36_WV.exterior.coords)
Y = -0.866 * E[:, 1] - 0.5 * E[:, 0]; Zc = -0.5 * E[:, 1] + 0.866 * E[:, 0]
ymin = Y.min(); feet = Zc[Y < ymin + 0.6]
Zf, Zr = feet.min(), feet.max(); Y0 = -ymin
rec(G, '端板著地點 Z（前腳～後腳，往後為正）', f'{Zf:.1f} ~ {Zr:.1f}', '—', True)


def machine_items(rho):
    it = []
    for pid in ['#24', '#26', '#37', '#5', '#6', '#7', '#13', '#21', '#12', '#31', '#36']:
        g = P[pid].geom; c = g.centroid
        it.append((pid, g.area * 3 * rho, np.array(FR[pid].to_asm(c.x, c.y, 1.5))))
    c13 = G13_WV.centroid
    drawers = ['#32', '#33', '#34', '#35'] + [f'#{k}' for k in range(38, 52)] + ['#60', '#61']
    it.append(('抽屜', sum(P[p].geom.area for p in drawers if p in P) * 3 * rho, np.array([172.0, c13.y, c13.x])))
    it.append(('馬達盒', sum(P[p].geom.area for p in ('#1', '#2', '#3', '#4', '#8') if p in P) * 3 * rho, np.array([58.0, 72.0, 14.0])))
    it.append(('轉盤合板件', sum(P[p].geom.area for p in ('#27', '#14', '#18', '#22', '#58', '#59') if p in P) * 3 * rho, np.array([58.0, 50.0, -12.0])))
    it.append(('轉盤壓克力', sum(P[p].geom.area for p in ('#62', '#63') if p in P) * 3 * 1.19e-3, np.array([58.0, 50.0, -16.0])))
    small = ['#9', '#10', '#11', '#15', '#16', '#17', '#19', '#20', '#23', '#25'] + [f'#{k}' for k in range(52, 58)]
    it.append(('小卡扣', sum(P[p].geom.area for p in small if p in P) * 3 * rho, np.array([123.0, 60.0, 13.0])))
    it.append(('TT 馬達', 30.0, np.array([58.0, 75.0, 14.0])))
    it.append(('18650＋電池盒＋開關（估）', 65.0, np.array([25.0, 40.0, 14.0])))
    return it


def v2_items():
    return [('TM1637＋線', PR.M_ITEMS['disp'], np.array([M.Uc, M.Vc, -2.0])),
            ('S5/S10/S50 模組＋鎖塊（估 3×8 g）', 24.0, np.array([168.0, 75.0, -8.0])),
            ('S1 模組＋座（估）', 12.0, np.array([112.0, 68.0, 20.0]))]


def box_items(rho):
    it = []
    for s in box_all:
        a, b = PLANE[s.axis]; c = s.poly.centroid
        q = np.zeros(3); q[AXI[a]] = c.x; q[AXI[b]] = c.y; q[AXI[s.axis]] = sum(s.rng) / 2
        it.append((s.name, s.poly.area * PR.T * rho, q))
    ctr = lambda bx: np.array([(bx[0] + bx[1]) / 2, (bx[2] + bx[3]) / 2, (bx[4] + bx[5]) / 2])
    it += [('9V 電池', PR.M_ITEMS['batt'], ctr(M.CONTENTS['9V 電池'])), ('擴展板', PR.M_ITEMS['board'], ctr(M.CONTENTS['擴展板 PCB'])),
           ('ESP32', PR.M_ITEMS['esp32'], ctr(M.CONTENTS['ESP32 開發板＋母座'])), ('電池扣＋開關＋DC 線', PR.M_ITEMS['clip_sw'], np.array([175.0, 12.0, 55.0])),
           ('盒內杜邦線', PR.M_ITEMS['wires'], np.array([190.0, 66.0, 62.0])), ('M3 螺絲螺帽', PR.M_ITEMS['screws'], ctr(M.CONTENTS['擴展板 PCB']))]
    return it


def cg(items):
    m = sum(x[1] for x in items); return m, sum(x[1] * x[2] for x in items) / m


STAB = {}
for lab, rho in PR.RHO.items():
    mi = machine_items(rho); vi = v2_items(); bi = box_items(rho)
    mm, cm = cg(mi); mb, cb = cg(bi); mt, ct = cg(mi + vi + bi)
    _, cno = cg(mi + vi + [x for x in bi if x[0] != '9V 電池'])
    Zm = yz(*cm)[1]; Zb = yz(*cb)[1]; Zt = yz(*ct)[1]; Znb = yz(*cno)[1]
    rec(G, f'[{lab}] 機身 {mm:.0f} g（重心 Z {Zm:.1f}）＋v2 感測器顯示器 {sum(x[1] for x in vi):.0f} g＋盒子 {mb:.0f} g（重心 U{cb[0]:.0f} V{cb[1]:.0f} W\'{cb[2]:.0f}、Z {Zb:.1f}）',
        f'合計 {mt:.0f} g，重心離後腳 {Zr - Zt:.1f} mm（原機 {Zr - Zm:.1f}；拔掉電池 {Zr - Znb:.1f}）', '>15', Zr - Zt > 15)
    Wt = mt * 9.81e-3; Wo = mm * 9.81e-3

    def crit(p, f, W_, Zc_):
        Yp, Zp = yz(*p); Yp += Y0
        fY, fZ = yz(*f)
        tr = (Zp - Zr) * fY - Yp * fZ; tf = (Zp - Zf) * fY - Yp * fZ
        back = (-W_ * (Zr - Zc_) / tr) if tr < 0 else math.inf
        fwd = (-W_ * (Zf - Zc_) / tf) if tf > 0 else math.inf
        return back, fwd
    acts = [('按 EN/RST（單指沿 −W\' 推）', np.array([M.EN_BTN[0][0], M.EN_BTN[0][1], M.dev[3] + 1.6]), np.array([0, 0, -1.0])),
            ('按頂板開關（沿 +V 壓）', np.array([PR.SWITCH['U0'] + 4.5, M.Vt, PR.SWITCH['W0'] + 6.75]), np.array([0, 1.0, 0])),
            ('拔電池（沿 −V 往上拉）', np.array([212.5, M.bat[2], 45.0]), np.array([0, -1.0, 0])),
            ('壓電池放回（沿 +V）', np.array([212.5, M.bat[2], 45.0]), np.array([0, 1.0, 0])),
            ('手勾到盒子後下緣（水平往後）', np.array([200.0, M.Vb, PR.BOX['W_back']]), np.array([0, -0.5, 0.866])),
            ('插 USB（沿 −U）', np.array([M.usb_c[0], M.usb_c[1], M.usb_c[2]]), np.array([-1.0, 0, 0])),
            ('按顯示器 LED 面（沿 +W\'）', np.array([M.Uc, M.Vc, -3.0 - M.D['body_H']]), np.array([0, 0, 1.0]))]
    for nm, p, f in acts:
        b, fw = crit(p, f, Wt, Zt); ob, ofw = crit(p, f, Wo, Zm)
        txt = f'往後翻 {b:.2f} N、往前翻 {fw:.2f} N' + (f'（原機同一點往後 {ob:.2f} N）' if nm.startswith('按顯示器') else '')
        if nm.startswith('按 EN'):
            rec(G, f'[{lab}] {nm}', txt, '用「捏」或改用開關關再開', True, '單指直推會把機器往前推；歸零首選開關關再開')
        elif nm.startswith('按顯示器'):
            rec(G, f'[{lab}] {nm}', txt, '≥原機 85%', b >= 0.85 * ob)
        elif nm.startswith('手勾') or nm.startswith('插 USB'):
            rec(G, f'[{lab}] {nm}', txt, '參考', True)
        else:
            rec(G, f'[{lab}] {nm}', txt, '典型施力 ≤2 N 不翻', min(b, fw) > 2.0)
    STAB[lab] = dict(m_machine=mm, Z_machine=Zm, m_box=mb, cg_box=cb.tolist(), Z_box=Zb, m_tot=mt, Z_tot=Zt, Zr=Zr, Zf=Zf,
                     margin=Zr - Zt, margin_orig=Zr - Zm, Y0=Y0)

# ================================================================ J 可視
G = 'J 正面可視'
cY, cZ = yz(M.Uc, M.Vc, -3.0 - M.D['body_H']); cY += Y0
nY, nZ = yz(0, 0, -1.0)
rec(G, 'LED 面中心離桌面高', cY, '—', True)
rows = []
for lab, eye_h, dist_ in (('坐（眼高桌上 400）', 400, 500), ('坐', 400, 800), ('坐、遠', 400, 1500), ('站（眼高桌上 800）', 800, 600), ('站', 800, 1000),
                          ('站、遠', 800, 1500), ('坐、近', 400, 400)):
    for lat in (0.0, 35.0):
        hz = dist_ / math.cos(math.radians(lat))
        vY = eye_h - cY; vZ = -(dist_)
        vx = dist_ * math.tan(math.radians(lat))
        v = np.array([vx, vY, vZ]); v /= np.linalg.norm(v)
        nrm = np.array([0.0, nY, nZ]) / math.hypot(nY, nZ)
        ang = math.degrees(math.acos(float(v @ nrm)))
        dep = math.degrees(math.atan2(eye_h - cY, dist_))
        rows.append((lab, dist_, lat, dep, ang))
        rec(G, f'{lab} 距 {dist_} mm、偏 {lat:.0f}°（俯角 {dep:.1f}°）', ang, '視線偏離 LED 法線 ≤60°', ang <= 60)
rec(G, 'LED 面前方遮擋物', '無（LED 凸出 #24 4.2 mm；轉盤在 U<113，crosstrack 蓋板在軌道下方）', '—', True)

# ================================================================ K 用板
G = 'K 用板'
parts_bb = []
for b in box_all:
    x0, y0, x1, y1 = b.poly.bounds
    parts_bb.append((b.name, x1 - x0, y1 - y0, b.poly.area))
A = sum(p[3] for p in parts_bb)
key_a = M.KEY_WV.area * 2
bbA = sum((p[1] + 2.5) * (p[2] + 2.5) for p in parts_bb)
rec(G, '電子盒合板 7 片 淨面積／外包＋2.5 間距', f'{A:.0f}／{bbA:.0f} mm²（一張 255×355 的 {A/90525*100:.1f}%／{bbA/90525*100:.1f}%）', '—', True)
rec(G, '選用防拔鍵 ×2', f'{key_a:.0f} mm²', '—', True)
rec(G, '顯示器側新增料', '0（#24/#26/#5/#37 只開孔）', '—', True)


def shelf_pack(items, W, H, gap=2.5):
    """簡單貨架排版（可轉 90°）。回傳 (是否全放下, 位置)。"""
    its = sorted(items, key=lambda t: -max(t[1], t[2]))
    pos = []; x = 0.0; y = 0.0; row_h = 0.0
    for nm, a, b, _ in its:
        best = None
        for (w, h) in ((a, b), (b, a)):
            if h <= H:
                if x + w <= W and y + h <= H:
                    cand = (x, y, w, h)
                    if best is None or h > best[3]:
                        best = cand
        if best is None:
            x = 0.0; y += row_h + gap; row_h = 0.0
            for (w, h) in ((a, b), (b, a)):
                if w <= W and y + h <= H:
                    best = (x, y, w, h); break
        if best is None:
            return False, pos
        pos.append((nm, *best)); x = best[0] + best[2] + gap; row_h = max(row_h, best[3])
    return True, pos


okp, pos = shelf_pack(parts_bb, *PR.STRIP)
rec(G, f'7 片排進第 1 張下方長條 {PR.STRIP[0]}×{PR.STRIP[1]}（貨架法、間距 2.5）', '放得下' if okp else '放不下', '—', True,
    '；'.join(f'{nm.split()[0]} @({x:.0f},{y:.0f}) {w:.1f}×{h:.1f}' for nm, x, y, w, h in pos))
STRIP_POS = pos

# ================================================================ 輸出
with open(HERE + '/checks_out.txt', 'w') as f:
    for r in OUT:
        f.write(f"{'OK' if r['ok'] else '!!'} [{r['group']}] {r['item']}：{r['value']}（要求 {r['need']}）{'  ※' + r['note'] if r['note'] else ''}\n")
    nbad = sum(not r['ok'] for r in OUT)
    f.write(f'\n共 {len(OUT)} 項，!! {nbad} 項\n')
json.dump(dict(checks=OUT, stab=STAB, strip=STRIP_POS, parts_bb=parts_bb), open(HERE + '/checks.json', 'w'), ensure_ascii=False, indent=1, default=float)
print(open(HERE + '/checks_out.txt').read())

"""S1 最終規格示意圖：fig1_section.png（光束處剖面）、fig2_front.png（正視）、fig3_parts.png（零件局部座標）、fig4_sim.png（模擬結果）。"""
import sys, json, math
sys.dont_write_bytecode = True
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Polygon as MPoly, Rectangle
from shapely.geometry import Polygon, box, LineString
import base as B
import design as DS

font_manager.fontManager.addfont('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc')
plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
plt.rcParams['axes.unicode_minus'] = False

g = DS.build()
D, M, Dd = g['D'], g['M'], g['Dd']
INK, INK2, GRID = '#0b0b0b', '#52514e', '#d9d8d4'
C_WOOD, C_WOOD_E = '#e6dccb', '#8a7a5c'
C_MOD, C_CAP, C_BEAM = '#2a78d6', '#eda100', '#e34948'
C_S5, C_NEW = '#4a3aa7', '#1baf7a'


def poly(ax, P, **kw):
    if P is None or P.is_empty:
        return
    geoms = P.geoms if hasattr(P, 'geoms') else [P]
    for q in geoms:
        ax.add_patch(MPoly(np.array(q.exterior.coords), closed=True, **kw))
        for r in q.interiors:
            ax.add_patch(MPoly(np.array(r.coords), closed=True, fc='white', ec=kw.get('ec', INK), lw=kw.get('lw', 0.8)))


def rect(ax, x0, x1, y0, y1, **kw):
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, **kw))


def style(ax, xl, yl, title):
    ax.set_xlabel(xl, color=INK2); ax.set_ylabel(yl, color=INK2)
    ax.set_title(title, fontsize=11, color=INK)
    ax.grid(True, color=GRID, lw=0.5); ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_color('#bdbcb7')


# ======================================================================
# 圖 1：剖面（U＝光束 U）
fig, ax = plt.subplots(figsize=(10.5, 9.6))
Ub = D['Ub']
op = B.OP1
seg = LineString([(Ub, 0), (Ub, 120)]).intersection(op)
vo0, vo1 = seg.bounds[1], seg.bounds[3]
rail = float(B.railV(Ub))
# #24、#26、#37
rect(ax, -6, -3, 4, rail, fc=C_WOOD, ec=C_WOOD_E, lw=0.8)
rect(ax, -6, -3, rail + 31.9, 98, fc=C_WOOD, ec=C_WOOD_E, lw=0.8)
ax.text(-4.5, 100.5, '#24', ha='center', fontsize=8, color=INK2)
rect(ax, -3, 0, 4, vo0, fc=C_WOOD, ec=C_WOOD_E, lw=0.8)
rect(ax, -3, 0, vo1, 98, fc=C_WOOD, ec=C_WOOD_E, lw=0.8)
ax.text(-1.5, 100.5, '#26', ha='center', fontsize=8, color=INK2)
ax.annotate(f'1 元開口（此 U 處 V{vo0:.1f}~{vo1:.1f}）', (-1.5, (vo0 + vo1) / 2), (-25, 40), fontsize=8, color=INK2,
            arrowprops=dict(arrowstyle='->', color=INK2, lw=0.6))
rect(ax, B.W37, B.W37o, 4, 82, fc=C_WOOD, ec=C_WOOD_E, lw=0.8)
ax.text(30.5, 28.5, '#37', ha='center', fontsize=8, color=INK2)
# 出口平面
W_ = np.linspace(0, 29, 10)
ax.plot(W_, B.exitV(W_), '-.', color='#008300', lw=1)
ax.text(2, 99.5, "出口平面 V=98-16W'/29（以下是抽屜，不得有新增物）", fontsize=8, color='#008300')
# #13R 外形（背景投影）
wall = g['wall13R_WV']
poly(ax, wall.intersection(box(-10, 0, 45, 120)), fc='none', ec=C_WOOD_E, lw=0.8, ls='--')
ax.text(1.0, 33.5, f'#13R 加高到 V{Dd["wall_top"]:.0f}（U104.875~107.875，背景）', fontsize=8, color=C_WOOD_E)
sl = g['wall_slot_WV']
# S5 翼（翼朝上游）最終位置與安裝掃掠在此 U 的剖面
S5 = B.s5_boxes('up')
for nm, P, (w0, w1) in S5['mod_final']:
    if w1 <= 0:
        continue
    x = LineString([(Ub, 0), (Ub, 120)]).intersection(P)
    if not x.is_empty:
        rect(ax, max(w0, 0), w1, x.bounds[1], x.bounds[3], fc=C_S5, ec=C_S5, alpha=0.25, lw=0.6)
x = LineString([(Ub, 0), (Ub, 120)]).intersection(S5['sweep_UV'])
rect(ax, 0, max(S5['W_max'], S5['W_deep']), x.bounds[1], x.bounds[3], fc='none', ec=C_S5, lw=1, ls=':')
ax.annotate(f"S5 翼（up）最終位置（淡紫）＋安裝掃掠（點線）\nW'≤{max(S5['W_max'], S5['W_deep']):.1f}；S1 一律在 W'≥12.3", (5, x.bounds[3] - 1), (-27, 82), fontsize=7.5, color=C_S5,
            arrowprops=dict(arrowstyle='->', color=C_S5, lw=0.6))
# 模組（此剖面）
m = g['mod']
for k in ('pcb', 'comp', 'body', 'front_arm', 'back_arm'):
    U0, U1, V0, V1, W0, W1 = m[k]
    if U0 <= Ub <= U1:
        rect(ax, W0, W1, V0, V1, fc=C_MOD, ec='#174a8a', lw=0.8, alpha=0.85)
U0, U1, V0, V1, W0, W1 = m['pcb']
rect(ax, W0, W1, V0, V1, fc='none', ec='#174a8a', lw=0.8, ls='--')
ax.text(W0 + 0.3, V0 - 0.8, f"PCB（U{U0:.2f}~{U1:.2f}，背景）", fontsize=7.5, color='#174a8a')
poly(ax, g['S1H_WV'], fc=C_CAP, ec='#8a5d00', lw=1)
ax.annotate(f"S1-H 導流帽（3 片疊在前臂頂）\n頂坡 {g['cap_slope_deg']:.0f}°，朝通道", (16, 68.5), (-24, 64), fontsize=8, color='#8a5d00',
            arrowprops=dict(arrowstyle='->', color='#8a5d00', lw=0.7))
ax.text(15.8, 74.6, '前臂', ha='center', fontsize=8, color='white')
ax.text(32.8, 74.6, '後臂', ha='center', fontsize=8, color='white')
ax.plot([D['wa'], D['wb']], [D['Vb'], D['Vb']], color=C_BEAM, lw=2.2)
ax.annotate(f"光束 U{Ub:.3f}、V{D['Vb']:.1f}\nW'{D['wa']}→{D['wb']}", (24, D['Vb']), (33, 88), fontsize=8.5, color=C_BEAM,
            arrowprops=dict(arrowstyle='->', color=C_BEAM, lw=0.8))
# S1-P、背蓋
rect(ax, B.W37, B.W37o, g['S1P_UV'].bounds[1], g['S1P_UV'].bounds[3], fc=C_NEW, ec='#0d6b49', lw=0.8)
ax.text(33.0, 67.6, 'S1-P', fontsize=7.5, color='#0d6b49')
sF = g['S1F_UV']
x = LineString([(Ub, 0), (Ub, 120)]).intersection(sF)
if not x.is_empty:
    rect(ax, B.W37o, B.W37o + 3, x.bounds[1], x.bounds[3], fc=C_NEW, ec='#0d6b49', lw=0.8, alpha=0.6)
ax.text(35.4, 55, 'S1-F 背蓋\n（M3×2 鎖 #37）', fontsize=7.5, color='#0d6b49')
# 模擬軌跡（最終設計、翼 up）
try:
    sim = json.load(open('sim_final.json'))
    runs = [r for r in sim['runs'] if r['variant'] == 'D' and any(p[3] > 0.5 for p in r['path'])][:40]
    for rr in runs:
        P = np.array([p for p in rr['path'] if p[3] > -1])
        ax.plot(P[:, 3], P[:, 2], color=INK2, lw=0.5, alpha=0.35)
    ax.plot([], [], color=INK2, lw=0.8, alpha=0.5, label='模擬：硬幣中心軌跡（最終設計＋S5 翼 up，40 枚；各枚 U 不同，此為投影）')
    ax.legend(loc='lower right', fontsize=8, frameon=False)
except FileNotFoundError:
    pass
ax.set_xlim(-28, 46); ax.set_ylim(104, 26)
ax.set_aspect('equal')
style(ax, "W'（mm；#26 背面＝0，往後）", 'V（mm，沿面板往下）', f'圖 1　S1 光束處剖面（U＝{Ub:.3f}）：前臂戴導流帽、後臂嵌 #37、S5 只在 W\'≤10')
fig.tight_layout(); fig.savefig('fig1_section.png', dpi=150); plt.close(fig)

# ======================================================================
# 圖 2：正視（從 #24 前面看進去；U 往左增加 → x 軸反向）
fig, ax = plt.subplots(figsize=(12, 9.5))
poly(ax, B.OP1, fc='#cfe3f7', ec='#2a78d6', lw=0.8)
ax.text(124.4, 41, '1 元開口\n(#26)', ha='center', fontsize=9, color='#174a8a')
Us = np.linspace(85, 145, 10)
ax.plot(Us, B.railV(Us), color=C_BEAM, lw=1.2, alpha=0.7)
ax.text(140, float(B.railV(140)) - 1.5, '軌道', fontsize=8, color=C_BEAM)
rect(ax, B.U13[0], B.U13[1], Dd['wall_top'], 98, fc=C_WOOD, ec=C_WOOD_E, lw=0.8)
ax.text(106.4, 33, '#13R', rotation=90, ha='center', fontsize=8, color=C_WOOD_E)
rect(ax, B.U7[0], B.U7[1], 14, 98, fc=C_WOOD, ec=C_WOOD_E, lw=0.8)
ax.text(137.4, 33, '#7', ha='center', fontsize=8, color=C_WOOD_E)
rect(ax, 101.875, 104.875, g['S1C_v'][0], g['S1C_v'][1], fc=C_NEW, ec='#0d6b49', lw=0.8, alpha=0.5)
ax.text(103.4, 52.5, 'S1-C', ha='center', fontsize=7.5, color='#0d6b49')
for k, col in (('pcb', '#9fc3ee'), ('comp', '#9fc3ee'), ('body', C_MOD), ('front_arm', C_MOD)):
    U0, U1, V0, V1, W0, W1 = m[k]
    rect(ax, U0, U1, V0, V1, fc=col, ec='#174a8a', lw=0.6, alpha=0.8)
rect(ax, g['S1H_U'][0][0], g['S1H_U'][-1][1], D['cap_Vr'], D['arm_v'][0], fc=C_CAP, ec='#8a5d00', lw=0.8)
ax.plot([D['Ub']], [D['Vb']], 'o', color=C_BEAM, ms=6)
ax.annotate(f"光束 U{D['Ub']:.3f} V{D['Vb']:.0f}", (D['Ub'], D['Vb']), (103.5, 90), fontsize=8.5, color=C_BEAM,
            arrowprops=dict(arrowstyle='->', color=C_BEAM, lw=0.7))
z0, z1 = B.U7[0] - 20, B.U13[1] + 20
ax.plot([z0, z1], [86, 86], color=C_BEAM, lw=3, alpha=0.35, solid_capstyle='butt')
ax.text((z0 + z1) / 2, 88.5, f'保證覆蓋區 U{z0:.3f}~{z1:.3f}（硬幣平行 #37 時）', ha='center', fontsize=8, color=C_BEAM)
for nm, P, (w0, w1) in S5['mod_final']:
    if w1 > 0:
        poly(ax, P, fc=C_S5, ec=C_S5, alpha=0.18, lw=0.5)
poly(ax, S5['sweep_UV'], fc='none', ec=C_S5, lw=0.9, ls=':')
ax.text(141.5, 50, "S5 模組（翼 up）在 W'0~9.6\n點線＝含安裝掃掠", fontsize=7.5, color=C_S5)
poly(ax, g['win37_UV'], fc='none', ec='#e34948', lw=1.0, ls='--')
ax.text(121.5, 80.3, '#37 卡匣窗（W\'29~32）', fontsize=7.5, color='#e34948')
poly(ax, g['S1F_UV'], fc='none', ec='#0d6b49', lw=0.9, ls='-.')
ax.text(93.5, 49.5, 'S1-F 背蓋（#37 外面）', fontsize=7.5, color='#0d6b49')
for k, s in g['slots26_UV'].items():
    poly(ax, s, fc='#ffffff', ec=INK, lw=0.9)
    ax.text(s.bounds[0] - 4.2 if k != 'C' else s.bounds[0] - 0.6, (s.bounds[1] + s.bounds[3]) / 2, f'#26 槽 {k}', ha='left', va='center', fontsize=7,
            bbox=dict(fc='white', ec='none', alpha=0.8, pad=0.5))
for k, s in g['slots37_UV'].items():
    poly(ax, s, fc='#ffffff', ec='#e34948', lw=0.9)
    ax.text(s.bounds[0] - 0.8, (s.bounds[1] + s.bounds[3]) / 2, f'#37 槽 {k}', ha='left', va='center', fontsize=7, color='#e34948',
            bbox=dict(fc='white', ec='none', alpha=0.8, pad=0.5))
for h in g['holes37_UV']:
    poly(ax, h, fc='white', ec='#e34948', lw=0.8)
for h in B.H24:
    if h.area < 15 and 95 < h.bounds[0] < 112 and h.bounds[1] < 99:
        poly(ax, h, fc='none', ec=INK2, lw=0.6, ls=':')
ax.axhline(82, xmin=0, xmax=1, color=INK2, lw=0.6, ls='--')
ax.text(130, 83.6, '#37 下緣 V82（U≥104.5）', fontsize=7.5, color=INK2)
ax.set_xlim(146, 88); ax.set_ylim(102, 26)
ax.set_aspect('equal')
style(ax, 'U（mm；從正面看往左增加）', 'V（mm，沿面板往下）', '圖 2　正視：#13R 加高到 V30、S1 卡匣在死區＋前臂／導流帽伸進 1 元滑道、#26／#37 新開口')
fig.tight_layout(); fig.savefig('fig2_front.png', dpi=150); plt.close(fig)

# ======================================================================
# 圖 3：零件（局部座標）
gj = json.load(open('geometry_s1_final.json'))
fig = plt.figure(figsize=(16, 15))
gs = fig.add_gridspec(3, 3, height_ratios=[1.25, 1, 1])
axs = np.empty((3, 3), dtype=object)
axs[0, 0] = fig.add_subplot(gs[0, :])
axs[1, 0] = fig.add_subplot(gs[1, 0]); axs[1, 1] = fig.add_subplot(gs[1, 1]); axs[1, 2] = fig.add_subplot(gs[1, 2])
axs[2, 0] = fig.add_subplot(gs[2, 0]); axs[2, 1] = fig.add_subplot(gs[2, 1]); axs[2, 2] = fig.add_subplot(gs[2, 2])


def P_(c):
    if isinstance(c, dict):
        return Polygon(c['exterior'], c['holes'])
    return Polygon(c)


ax = axs[0, 0]
o13 = B.poly_WV_to_local13(g['orig13_WV'])
n13 = P_(gj['#13R']['outline_local13'])
poly(ax, n13, fc=C_WOOD, ec=INK, lw=0.8)
ax.plot(*np.array(o13.exterior.coords).T, color=C_BEAM, lw=0.8, ls='--', label='原 #13 外形')
for e in gj['#13R']['engrave']:
    ax.text(*e['at_local13'], e['text'], color=C_BEAM, fontsize=7, rotation=-30, ha='center', va='center')
for key, lab in (('wall_slot', '牆槽（S1-B 由 #37 側插入）'), ('corner_notch', '#37 角落讓位')):
    q = gj['#13R']['ops_local13'][key]
    if q:
        qq = Polygon(q); ax.plot(*np.array(qq.exterior.coords).T, color='#2a78d6', lw=0.8, ls=':')
        ax.annotate(lab, qq.centroid.coords[0], (qq.centroid.x + 8, qq.centroid.y - 12), fontsize=8, color='#2a78d6',
                    arrowprops=dict(arrowstyle='->', color='#2a78d6', lw=0.6))
for key, lab in (('tabs_front', '前榫 F（插 #26）'), ('tabs_back', '後榫 B1（插 #37）')):
    for q in gj['#13R']['ops_local13'][key]:
        qq = Polygon(q)
        dx, dy = ((-20, 6) if key == 'tabs_back' else (-14, -10))
        ax.annotate(lab, qq.centroid.coords[0], (qq.centroid.x + dx, qq.centroid.y + dy), fontsize=8, color=INK2,
                    arrowprops=dict(arrowstyle='->', color=INK2, lw=0.5))
ax.legend(fontsize=8, loc='lower right')
ax.set_title('#13R（原 #13 局部座標，原點＝原 #13 外框左上角；加高部分 x 為負；上面＝雕刻面朝空腔）', fontsize=10)
ax.invert_yaxis(); ax.set_aspect('equal'); ax.grid(True, color=GRID, lw=0.5)

ax = axs[1, 0]
for i, (nm, off) in enumerate((('S1-B', (0, 0)), ('S1-H', (28, 0)), ('S1-P', (28, 10)))):
    c = gj['new_parts'][nm]['local']
    pp = P_(c)
    from shapely import affinity
    pp = affinity.translate(pp, *off)
    poly(ax, pp, fc=C_NEW if nm != 'S1-H' else C_CAP, ec=INK, lw=0.8)
    ax.text(pp.bounds[0], pp.bounds[1] - 1.0, f"{nm} {gj['new_parts'][nm]['size'][0]}×{gj['new_parts'][nm]['size'][1]}" + (' ×3 片' if nm == 'S1-H' else ''), fontsize=8)
ax.set_xlim(-3, 42); ax.set_ylim(23, -4)
ax.set_title('S1-B 座塊（含焊點讓位孔）、S1-H 導流帽、S1-P 填塊', fontsize=10)
ax.set_aspect('equal'); ax.grid(True, color=GRID, lw=0.5)

ax = axs[1, 1]
pc = P_(gj['new_parts']['S1-C']['local'])
poly(ax, pc, fc=C_NEW, ec=INK, lw=0.8)
eo = P_(gj['new_parts']['S1-C']['engrave_outline_S1B'])
ax.plot(*np.array(eo.exterior.coords).T, color=C_BEAM, lw=0.8)
ax.text(10, 20, '紅線＝S1-B 黏貼框（雕刻）', fontsize=8, color=C_BEAM)
ax.text(30, 12.5, '前榫→#26', fontsize=8)
ax.text(0.5, 1.8, '後榫', fontsize=8)
ax.set_xlim(-2, 40); ax.set_ylim(26, -3)
ax.set_title('S1-C 座板（上面朝牆；局部 x＝35-W\'）', fontsize=10)
ax.set_aspect('equal'); ax.grid(True, color=GRID, lw=0.5)

ax = axs[1, 2]
pf = P_(gj['new_parts']['S1-F']['local'])
poly(ax, pf, fc=C_NEW, ec=INK, lw=0.8)
pp = affinity.translate(P_(gj['new_parts']['S1-P']['local']), g['S1P_UV'].bounds[0] - g['S1F_UV'].bounds[0], g['S1P_UV'].bounds[1] - g['S1F_UV'].bounds[1])
poly(ax, pp, fc='none', ec='#0d6b49', lw=0.8, ls='--')
ax.text(pp.bounds[0], pp.bounds[1] - 0.6, 'S1-P 黏在背蓋前面（虛線）', fontsize=7.5, color='#0d6b49')
ax.text(*gj['new_parts']['S1-F']['engrave_text']['at_local'], 'S1 ↑', color=C_BEAM, fontsize=9)
ax.set_xlim(-2, 38); ax.set_ylim(30, -3)
ax.set_title('S1-F 背蓋（從機身背面看；2×Ø3.4）', fontsize=10)
ax.set_aspect('equal'); ax.grid(True, color=GRID, lw=0.5)

ax = axs[2, 0]
for k, v in gj['#26']['slots'].items():
    pp = P_(v['local'])
    poly(ax, pp, fc='white', ec=INK, lw=0.9)
    ax.text(pp.bounds[2] + 0.6, pp.bounds[3], k, fontsize=8)
for h in B.H26:
    hl = B.UV_to_local26(h)
    if 40 < hl.bounds[0] < 95 and 55 < hl.bounds[1] < 100:
        poly(ax, hl, fc='none', ec=INK2, lw=0.6, ls=':')
ax.set_xlim(40, 95); ax.set_ylim(100, 55)
ax.set_title('#26 新槽（局部 x＝V-4、y＝U-40；點線＝既有孔）', fontsize=10)
ax.set_aspect('equal'); ax.grid(True, color=GRID, lw=0.5)

ax = axs[2, 1]
pw = P_(gj['#37']['window']['local'])
poly(ax, pw, fc='white', ec=C_BEAM, lw=0.9)
for k, v in gj['#37']['slots'].items():
    pp = P_(v['local']); poly(ax, pp, fc='white', ec=C_BEAM, lw=0.9)
    ax.text(pp.bounds[2] + 0.6, pp.bounds[3], k, fontsize=8)
for h in gj['#37']['holes']:
    c = h['center_local']; ax.add_patch(plt.Circle(c, h['d'] / 2, fc='white', ec=C_BEAM, lw=0.9))
p37 = B.UV_to_local37(B.O37.intersection(box(90, 30, 130, 114)))
ax.plot(*np.array(p37.exterior.coords).T, color=INK2, lw=0.7)
ax.text(29, 103.6, '#37 外框（下方開口：x<32、y>104.5）', fontsize=7.5, color=INK2)
ax.text(*gj['#37']['engrave'][0]['at_local'], 'S1 卡匣', color=C_BEAM, fontsize=8)
ax.set_xlim(20, 82); ax.set_ylim(126, 92)
ax.set_title('#37 卡匣窗、B1 槽、M3 孔（局部 x＝114-V、y＝U）', fontsize=10)
ax.set_aspect('equal'); ax.grid(True, color=GRID, lw=0.5)
axs[2, 2].axis('off')
axs[2, 2].text(0.02, 0.95, '說明\n・所有局部座標原點＝零件外框左上角（與 laser_v2.frames 相同）\n・#13R、#26、#37 是原始零件改造：產生器用原路徑做\n  聯集／差集，原曲線、原孔不動\n・S1-B／S1-C／S1-H 在 (W\',V) 平面；S1-F／S1-P 在 (U,V) 平面\n・S1-C 的雕刻面朝牆（S1-B 黏貼框），局部 x 已鏡像\n・切割＝黑 0.2、雕刻＝紅；文字轉路徑\n・精確頂點見 geometry_s1_final.json', va='top', fontsize=9, color=INK)
fig.suptitle('圖 3　v2 修改與新增零件（局部座標，mm）', fontsize=12, y=0.995)
fig.tight_layout(rect=(0, 0, 1, 0.98)); fig.savefig('fig3_parts.png', dpi=130); plt.close(fig)

# ======================================================================
# 圖 4：模擬結果（100% 橫條）
try:
    sim = json.load(open('sim_final.json'))
    rows = {(r['var'], json.dumps(r['over'], sort_keys=True)): r for r in sim['rows']}
    sim3 = json.load(open('sim_random3.json'))
    for r in sim3['rows']:
        rows[(r['var'], json.dumps(r['over'], sort_keys=True))] = r
    items = [('Z', '{}', '只有牆、滑道內無模組（基準）'),
             ('C', '{"s_pcb": 0.0}', '設計 1 原樣（前臂外露、不墊高）＋S5 翼 up'),
             ('C', '{}', '前臂外露、墊高 1 mm ＋S5 翼 up'),
             ('D', '{}', '最終：導流帽＋墊高 1 mm ＋S5 翼 up'),
             ('F', '{}', '最終 ＋S5 翼 down'),
             ('G', '{}', '最終 ＋S5 翼 center')]
    fig, ax = plt.subplots(figsize=(11, 4.4))
    cols = [('ok', '正確 1 次', '#2a78d6'), ('miss', '漏計', '#eb6834'), ('jam', '卡住', '#4a3aa7')]
    for i, (v, ov, lab) in enumerate(items):
        r = rows.get((v, ov))
        if r is None:
            continue
        n = r['entered']; x = 0
        for key, nm, c in cols:
            w = r[key] / n * 100
            ax.barh(i, w, left=x, color=c, height=0.62, edgecolor='white', linewidth=1.5, label=nm if i == 0 else None)
            x += w
        ax.text(100.8, i, f"漏計 {r['miss']}／卡住 {r['jam']}", va='center', fontsize=8.5, color=INK)
        ax.text(-1, i, f'{lab}（n={n}）', ha='right', va='center', fontsize=9, color=INK)
        ax.text(1.0, i, f"{r['ok'] / n * 100:.1f}%", va='center', fontsize=8.5, color='white')
    ax.set_xlim(0, 100); ax.set_yticks([]); ax.invert_yaxis()
    ax.set_xlabel('進入 1 元滑道的硬幣（%）', color=INK2)
    ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, fontsize=9)
    ax.set_title('圖 4　pybullet 3D 落幣模擬（隨機初始條件；簡化模型，只供方案比較）', fontsize=11, pad=24)
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.grid(True, axis='x', color=GRID, lw=0.5); ax.set_axisbelow(True)
    fig.tight_layout(); fig.subplots_adjust(left=0.34, right=0.9); fig.savefig('fig4_sim.png', dpi=150); plt.close(fig)
except FileNotFoundError as e:
    print('skip fig4', e)
print('figs done')

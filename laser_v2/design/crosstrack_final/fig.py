# 示意圖：fig_front.png（正視）、fig_section.png（S50 剖面＋隔板 v2）、fig_parts.png（新零件）
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Polygon as MPoly
from model import *

FP = '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'
font_manager.fontManager.addfont(FP)
plt.rcParams['font.family'] = font_manager.FontProperties(fname=FP).get_name()
plt.rcParams['axes.unicode_minus'] = False

P, D, S, X = build()
J = json.load(open('geometry_final.json'))
INK = '#222222'; GRID = '#dddddd'
C_WIN = '#d62728'; C_LH = '#f2b800'; C_MOD = '#4c72b0'; C_LOW = '#4c72b0'; C_P1 = '#2ca02c'; C_C1 = '#ff7f0e'
C_DIV = '#8c564b'; C_OP = '#9ecae1'; C_WING = '#9467bd'


def draw(ax, g, **kw):
    if g is None or g.is_empty:
        return
    for p in getattr(g, 'geoms', [g]):
        if p.geom_type != 'Polygon':
            continue
        ax.add_patch(MPoly(np.array(p.exterior.coords), closed=True, **kw))
        for h in p.interiors:
            ax.add_patch(MPoly(np.array(h.coords), closed=True, fill=False, edgecolor=kw.get('edgecolor', INK), lw=kw.get('lw', 0.8)))


# ======================= 正視圖 =======================
fig, ax = plt.subplots(figsize=(17, 9.6))
draw(ax, O24, facecolor='#f6f1e7', edgecolor=INK, lw=1.0)
draw(ax, SLOT24, facecolor='white', edgecolor=INK, lw=1.2)
for c, p in OPS.items():
    draw(ax, p, facecolor=C_OP, edgecolor='#3182bd', lw=0.8, alpha=0.55)
    b = p.bounds; ax.text((b[0] + b[2]) / 2, b[1] + 5, '%s元開口\n(#26)' % c, ha='center', va='top', fontsize=9, color='#08519c')
for h in H24:
    if h.area < 300 and h.bounds[0] > 90:
        dele = is_deleted_hole(h, '#24')
        draw(ax, h, facecolor='white', edgecolor='#999999' if dele else INK, lw=0.7, ls='--' if dele else '-')
Ux = np.array([75, 236]); ax.plot(Ux, railV(Ux), color='#c00000', lw=2.0, label='軌道（#24 斜槽下緣，不動）')
for k, R in S.items():
    st = STATIONS[k]
    for nm, s0, s1, n0, n1, w0, w1 in R['mod_low']:
        if nm in ('PCB', '後臂', '前臂'):
            draw(ax, rect_sn(R['O'], s0, s1, n0, n1), fill=False, edgecolor=C_LOW, lw=0.8, ls=':')
    for nm, s0, s1, n0, n1, w0, w1 in R['mod_final']:
        if nm == 'PCB':
            draw(ax, rect_sn(R['O'], s0, s1, n0, n1), facecolor=C_MOD, edgecolor=C_MOD, alpha=0.30, lw=0.8)
        if nm == '前臂':
            draw(ax, rect_sn(R['O'], s0, s1, n0, n1), facecolor=C_MOD, edgecolor=C_MOD, alpha=0.55, lw=0.8)
        if nm == '排針＋杜邦頭':
            draw(ax, rect_sn(R['O'], s0, s1, n0, n1), facecolor='#555555', edgecolor='#333333', alpha=0.35, lw=0.6)
    draw(ax, R['c1'], fill=False, edgecolor=C_C1, lw=1.2, ls='--')
    draw(ax, R['p1'], facecolor=C_P1, edgecolor=C_P1, alpha=0.35, lw=0.8)
    draw(ax, R['win_in24'], fill=False, edgecolor=C_WIN, lw=1.8)
    draw(ax, R['lh'], facecolor=C_LH, edgecolor='#a07000', lw=0.8)
    for p in R['pins']:
        if p:
            draw(ax, p['hole'], facecolor='white', edgecolor=C_WIN, lw=1.2)
    Ua, Ub = st['divU']
    ax.add_patch(plt.Rectangle((Ua, 14), Ub - Ua, 84, facecolor=C_DIV, alpha=0.12, edgecolor=C_DIV, lw=0.6, ls='--'))
    bx, by = R['beam_UV']
    ax.plot(bx, by, 'x', color='#c00000', ms=9, mew=2)
    ax.annotate('%s 光束\nU%.2f V%.2f\n離軌 %.1f' % (k, bx, by, P['h']), (bx, by), (bx + 9, by - 22), fontsize=9,
                arrowprops=dict(arrowstyle='->', color='#c00000', lw=0.8), color='#c00000')
for src, mv in J['parts']['engrave_moves_24'].items():
    b0 = mv['old_UV']; b1 = mv['new_UV']
    ax.add_patch(plt.Rectangle((b0[0], b0[1]), b0[2] - b0[0], b0[3] - b0[1], fill=False, edgecolor='#e377c2', ls=':', lw=1))
    ax.add_patch(plt.Rectangle((b1[0], b1[1]), b1[2] - b1[0], b1[3] - b1[1], fill=False, edgecolor='#e377c2', lw=1.4))
    ax.annotate('', (b1[0] + 1, (b1[1] + b1[3]) / 2), (b0[0] + 1, (b0[1] + b0[3]) / 2), arrowprops=dict(arrowstyle='->', color='#e377c2'))
    ax.text(b1[2] + 0.8, b1[1] + 2, '雕刻%s移到此' % mv['name'], fontsize=8, color='#ad1f78')
ch = X['cable_hole']; draw(ax, ch, facecolor='white', edgecolor=C_WIN, lw=1.5)
ax.text(ch.bounds[0] - 1, ch.bounds[3] + 3.2, '排線孔 10×4.5\n(#24、#26 同位)', fontsize=8, color=C_WIN, ha='left')
# 排線路徑示意
for k, R in S.items():
    hb = [b for b in R['mod_final'] if b[0] == '排針＋杜邦頭'][0]
    c = rect_sn(R['O'], hb[1], hb[2], hb[3], hb[4]).centroid
    ax.plot([c.x, c.x, 101.5, 96.5], [c.y, 95.3, 95.3, 105.7], color='#17becf', lw=1.2, ls='-.')
ax.plot([], [], color='#17becf', lw=1.2, ls='-.', label='排線（#24 正面 V≈95 往右 → 排線孔 → 右側空腔 → #37）')
ax.add_patch(plt.Circle(TURN_C, TURN_R_RING, fill=False, edgecolor='#7f7f7f', lw=0.8, ls='--'))
ax.text(70, 7, '轉盤圍邊 #27／前蓋 #63（R54.5）', fontsize=8, color='#7f7f7f')
# 圖例
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
hand = [Line2D([], [], color='#c00000', lw=2, label='軌道（不動）'), Patch(facecolor=C_OP, alpha=0.55, label='#26 分幣開口（不動）'),
        Line2D([], [], color=C_WIN, lw=1.8, label='#24／#26 新窗（同形；S50 直通下緣）'), Patch(facecolor=C_LH, label='#26 光孔（平行四邊形）'),
        Patch(facecolor=C_MOD, alpha=0.3, label='模組 PCB（最終位置）'), Patch(facecolor=C_MOD, alpha=0.55, label='前臂'),
        Line2D([], [], color=C_LOW, ls=':', label='低位（推入時，再上滑 9.8）'), Patch(facecolor=C_P1, alpha=0.35, label='鎖塊 P1（#24 平面內）'),
        Line2D([], [], color=C_C1, ls='--', lw=1.2, label='蓋板 C1（#24 前方）'), Patch(facecolor=C_DIV, alpha=0.12, label='隔板 #7／#6／#5（#26 後方）'),
        Patch(facecolor='#555555', alpha=0.35, label='排針＋杜邦頭（假設位置）'), Line2D([], [], color='#17becf', ls='-.', label='排線')]
ax.legend(handles=hand, loc='upper left', fontsize=8.5, ncol=2, framealpha=0.95)
ax.set_xlim(246, 85); ax.set_ylim(116, 0)
ax.set_aspect('equal'); ax.grid(color=GRID, lw=0.5)
ax.set_xlabel("U（mm，0＝右端轉盤側；圖左＝U 大＝下游）"); ax.set_ylabel('V（mm，沿面板往下）')
ax.set_title('最終方案（滑升式感測座＋階梯窗）正視圖：#24 前面看進去（暫定模組、翼朝上游 wing=up、h=2.5）', fontsize=12)
fig.tight_layout(); fig.savefig('fig_front.png', dpi=130); plt.close(fig)

# ======================= S50 剖面 ＋ 隔板 v2 =======================
fig = plt.figure(figsize=(17, 8.6))
ax = fig.add_axes([0.04, 0.08, 0.50, 0.84])
R = S['S50']; O = R['O']
# 剖面取 s=0（光束處）：#24、#26 在 (W', n)
def n_at_V(V, s=0.0):
    # 站座標 s 固定時，(U,V) 上的點：V = O_V + s*T_V + n*N_V → n
    return (V - O[1] - s * T[1]) / N[1]
nb = n_at_V(98.0)
ax.add_patch(plt.Rectangle((-6, D['n_strip']), 3, 0 - D['n_strip'], facecolor='#e8d9b5', edgecolor=INK, lw=0.8))   # #24 保留條
ax.add_patch(plt.Rectangle((-3, D['n_strip']), 3, LIP['10'] - D['n_strip'], facecolor='#d9c49a', edgecolor=INK, lw=0.8))   # #26 唇
ax.add_patch(plt.Rectangle((-3, LIP['10'] + 0.0), 3, 28, facecolor='#d9c49a', edgecolor=INK, lw=0.8, alpha=0.6))     # 立柱
ax.text(-1.5, 16, '#26 立柱\n(光孔 n %.1f～%.1f)' % (P['h'] - P['lh_n'] / 2, P['h'] + P['lh_n'] / 2), ha='center', fontsize=8, rotation=90)
ax.add_patch(plt.Rectangle((-3, P['h'] - P['lh_n'] / 2), 3, P['lh_n'], facecolor=C_LH, edgecolor='#a07000', lw=0.8))
ax.text(-4.5, -1.2, '保留條\n%.1f' % (-D['n_strip']), ha='center', fontsize=8)
# 模組（最終＋低位）
for B, sty in ((R['mod_low'], dict(fill=False, edgecolor=C_LOW, ls=':', lw=1.0)),
               (R['mod_final'], dict(facecolor=C_MOD, edgecolor=C_MOD, alpha=0.35, lw=1.0))):
    for nm, s0, s1, n0, n1, w0, w1 in B:
        if nm in ('前臂', '後臂', '本體底座', 'PCB'):
            ax.add_patch(plt.Rectangle((w0, n0), w1 - w0, n1 - n0, **sty))
# P1、C1、插銷（s=0 剖面）
ax.add_patch(plt.Rectangle((-6, max(nb, D['n_win_bot'] - 3)), 3, D['n_pcb_bot'] - max(nb, D['n_win_bot'] - 3), facecolor=C_P1, alpha=0.45, edgecolor=C_P1))
ax.add_patch(plt.Rectangle((-9, max(nb, -40)), 3, D['n_bump'] - P['c_v'] - max(nb, -40), facecolor=C_C1, alpha=0.35, edgecolor=C_C1))
ax.text(-7.5, nb + 1.5, 'C1', ha='center', fontsize=9); ax.text(-4.5, D['n_pcb_bot'] - 3, 'P1', ha='center', fontsize=9)
ax.axhline(nb, color='#7f7f7f', lw=0.8, ls='--'); ax.text(-24, nb - 0.8, '#24/#26 下緣 V98（此處已開底）', fontsize=8, color='#555555')
ax.plot([-6, -3], [0, 0], color='#c00000', lw=2.5); ax.text(-25, 0.6, '軌道 n=0', color='#c00000', fontsize=9)
ax.plot([D['W_fa'][1], D['W_ra'][0]], [P['h'], P['h']], color='#c00000', lw=1.5, ls='--'); ax.text(-15.5, P['h'] + 0.6, '光束 h=%.1f' % P['h'], color='#c00000', fontsize=9)
# 50 元硬幣立著
ax.add_patch(plt.Rectangle((-3 - COIN_T['50'], 0), COIN_T['50'], 28, facecolor='#f4c2c2', edgecolor='#b03060', lw=0.8, alpha=0.8))
ax.text(-4.2, 22, '50元', fontsize=8, rotation=90, ha='center')
# 隔板 #5 v2 在 (W', n)：以 V→n（s≈0 於隔板中心）
dv = R['div_new']
pts = np.array(dv.exterior.coords)
Uc = sum(STATIONS['S50']['divU']) / 2
s_div = (Uc - O[0] - 0) / T[0]
nn = np.array([(v - O[1] - ((Uc - O[0]) - n * N[0]) / T[0] * T[1]) for v in pts[:, 1] for n in [0]])
# 精確：U 固定、V 給定 → 解 (s,n)
def sn_of(U, V):
    d = np.array([U - O[0], V - O[1]]); return d @ T, d @ N
ptsn = np.array([[w, sn_of(Uc, v)[1]] for w, v in pts])
ax.add_patch(MPoly(ptsn, closed=True, facecolor=C_DIV, alpha=0.15, edgecolor=C_DIV, lw=1.0))
ax.text(14, n_at_V(70.0), '#5 v2（隔板，U%.1f 平面投影）' % Uc, fontsize=8, color=C_DIV)
# 出口平面、#37
Ws = np.linspace(0, 29, 30); ax.plot(Ws, [sn_of(Uc, exitV(w))[1] for w in Ws], color='#8c564b', lw=1.2, ls='-.')
ax.text(12, sn_of(Uc, exitV(12))[1] - 1.5, '滑道出口平面（下方＝抽屜）', fontsize=8, color='#8c564b')
ax.axvline(W37, color=INK, lw=2); ax.text(W37 - 0.6, 18, '#37 內面 W\'29.0', rotation=90, fontsize=8, ha='right')
ax.annotate('擋面 W\'%.1f\n（重力 0.5g 把後臂壓在這）' % D['W_stop'], (D['W_stop'], 3), (13, 9), fontsize=8, arrowprops=dict(arrowstyle='->'))
ax.annotate('低位：水平推入，再上滑 %.1f\n（低位會伸到出口平面以下約 8 mm，\n裝 S50 前先抽出 10、50 元抽屜）' % D['slide'], (2, D['n_pcb_top'] - D['slide'] + 2), (10, -26), fontsize=8, color=C_LOW,
            arrowprops=dict(arrowstyle='->', color=C_LOW))
ax.set_xlim(-26, 31); ax.set_ylim(-34, 26); ax.set_aspect('equal'); ax.grid(color=GRID, lw=0.5)
ax.set_xlabel("W'（mm，#26 背面＝0，往後為正）"); ax.set_ylabel('n（mm，垂直軌道，軌道面＝0）')
ax.set_title('S50 剖面（沿光束，s=0）：#24 保留條 2.3、#26 光孔、模組最終／低位、P1/C1、#5 v2', fontsize=11)
# 右側：三片隔板 v2
for i, (k, R2) in enumerate(S.items()):
    a2 = fig.add_axes([0.57 + i * 0.145, 0.08, 0.13, 0.84])
    pid = STATIONS[k]['div']
    g0 = DIVWV[pid]
    a2.add_patch(MPoly(np.array(g0.exterior.coords), closed=True, fill=False, edgecolor='#aaaaaa', lw=0.8, ls='--'))
    a2.add_patch(MPoly(np.array(R2['div_new'].exterior.coords), closed=True, facecolor='#e8d9b5', edgecolor=C_DIV, lw=1.0))
    a2.set_xlim(-8, 34); a2.set_ylim(100, 10); a2.set_aspect('equal'); a2.grid(color=GRID, lw=0.5)
    a2.set_title('%s v2（%s）\n灰虛線＝原形' % (pid, k), fontsize=9)
    a2.set_xlabel("W'"); a2.tick_params(labelsize=7)
    if i == 0:
        a2.set_ylabel('V')
fig.savefig('fig_section.png', dpi=130); plt.close(fig)

# ======================= 新零件 =======================
fig, axs = plt.subplots(1, 4, figsize=(17, 5.2))
def dim_plot(a, loc, title, holes=()):
    pts = np.array(loc + [loc[0]])
    a.add_patch(MPoly(np.array(loc), closed=True, facecolor='#f3e3c3', edgecolor=INK, lw=1.0))
    for hp in holes:
        a.add_patch(MPoly(np.array(hp), closed=True, facecolor='white', edgecolor=INK, lw=0.8))
    a.set_aspect('equal'); a.grid(color=GRID, lw=0.5); a.set_title(title, fontsize=10)
    xs, ys = pts[:, 0], pts[:, 1]
    a.set_xlim(xs.min() - 3, xs.max() + 3); a.set_ylim(ys.min() - 3, ys.max() + 3)
e5 = J['stations']['S5']; e50 = J['stations']['S50']
dim_plot(axs[0], e5['P1']['local'], 'P1 鎖塊（S5、S10 同形）%.1f×%.1f\n頂面：中段 6.5 寬頂住 PCB，兩側低 %.1f 讓焊點' % (e5['P1']['size'][0], e5['P1']['size'][1], D['n_pcb_bot'] - (D['n_bump'] - P['c_v'])))
dim_plot(axs[1], e5['C1']['local'], 'C1 蓋板（S5、S10）%.1f×%.1f\nP1 黏在 (%.1f, %.1f)' % (e5['C1']['size'][0], e5['C1']['size'][1], *e5['P1_on_C1_offset']))
dim_plot(axs[2], e50['P1']['local'], 'P1 鎖塊（S50）%.1f×%.2f\n底邊被 V97.5 截斜' % tuple(e50['P1']['size']))
pins = [[(x, y), (x + 3, y), (x + 3, y + 3), (x, y + 3)] for x, y in e50['pins_on_C1']]
dim_plot(axs[3], e50['C1']['local'], 'C1 蓋板（S50）%.1f×%.1f，兩側耳＋插銷\nP1 黏在 (%.1f, %.1f)；方塊＝3×3 插銷位置' % (e50['C1']['size'][0], e50['C1']['size'][1], *e50['P1_on_C1_offset']), holes=pins)
for a in axs:
    a.set_xlabel('x（沿軌道往下游，mm）'); a.set_ylabel('y（垂直軌道往上，mm）')
fig.suptitle('v2 新增零件（3 mm 合板；局部座標，原點＝左下角；繪製尺寸未含切縫補償）', fontsize=12)
fig.tight_layout(); fig.savefig('fig_parts.png', dpi=130); plt.close(fig)
print('ok')

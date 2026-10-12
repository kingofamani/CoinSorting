"""ebox_final 示意圖：fig1 正視（#24 左上）、fig2 側剖（世界座標）、fig3 背視（#37＋電子盒）、fig4 零件展開。"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Polygon as MPoly, Rectangle, Circle
from model import *
import params as PR

font_manager.fontManager.addfont('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc')
plt.rcParams['font.family'] = 'WenQuanYi Zen Hei'
plt.rcParams['axes.unicode_minus'] = False
M = build(PR)
STAB = json.load(open(HERE + '/checks.json'))['stab'] if __import__('os').path.exists(HERE + '/checks.json') else None
C_CUT = '#222222'; C_NEW = '#d62728'; C_HID = '#1f77b4'; C_COIN = '#f2c14e'; C_BOX = '#2ca02c'; C_ENG = '#e377c2'; C_WIRE = '#9467bd'


def polys(g):
    if g.is_empty:
        return []
    return [g] if g.geom_type == 'Polygon' else [q for q in getattr(g, 'geoms', []) if q.geom_type == 'Polygon']


def draw(ax, g, tf=lambda x, y: (x, y), fill=None, alpha=0.25, holes=True, **kw):
    for q in polys(g):
        x, y = np.array(q.exterior.coords).T
        X, Y = tf(x, y)
        if fill:
            ax.fill(X, Y, color=fill, alpha=alpha, lw=0)
        ax.plot(X, Y, **kw)
        if holes:
            for r in q.interiors:
                x, y = np.array(r.coords).T
                X, Y = tf(x, y)
                ax.plot(X, Y, **kw)


# ============================================================== fig1 正視
fr = lambda x, y: (246.0 - np.asarray(x), -np.asarray(y))      # 從正面看：U 往左增加；V 往下
fig, ax = plt.subplots(figsize=(16, 9.5))
reg = rect(110, 246, 0, 100)
draw(ax, M.G24_V2.intersection(reg), fr, color=C_CUT, lw=1.0)
draw(ax, SLOT24.intersection(reg), fr, fill='#e8d3a8', alpha=0.6, color=C_CUT, lw=1.0)
for c, op in OPEN.items():
    draw(ax, op, fr, color='#b08d3c', lw=0.8, ls=':')
    ax.text(*fr(op.centroid.x, op.centroid.y), f'{c} 元開口\n(#26)', ha='center', va='center', fontsize=8, color='#8a6d1f')
draw(ax, CT_WIN24, fr, fill='#cccccc', alpha=0.5, color='#888888', lw=0.8)
for nm, e in ENG_NEW.items():
    draw(ax, e, fr, fill=C_ENG, alpha=0.15, color=C_ENG, lw=0.8)
    ax.text(*fr(e.centroid.x, e.centroid.y), nm.split('(')[0], ha='center', va='center', fontsize=8, color='#a0306a')
draw(ax, LOGO, fr, color='#999999', lw=0.9, ls='--')
draw(ax, M.logo['L'], fr, fill=C_ENG, alpha=0.2, color=C_ENG, lw=1.0)
draw(ax, M.logo['lh'], fr, color=C_CUT, lw=0.9)
draw(ax, M.logo_alt['L'], fr, color='#2ca02c', lw=1.0, ls=':')
draw(ax, affinity.translate(LOGO, -55.5, 0), fr, color='#ff7f0e', lw=0.9, ls=':')
draw(ax, M.WIN, fr, fill='#333333', alpha=0.85, color=C_NEW, lw=1.6)
ax.text(*fr(M.Uc, M.Vc), '8.8.:8.8', color='#ff4444', fontsize=15, ha='center', va='center', fontweight='bold')
for hd in M.screw_heads:
    draw(ax, hd, fr, color=C_NEW, lw=1.0)
draw(ax, rect(*M.disp['PCB'][:4]), fr, color=C_HID, lw=1.0, ls='--')
draw(ax, M.NOTCH26.intersection(rect(0, 300, 14, 100)), fr, fill=C_HID, alpha=0.08, color=C_HID, lw=0.8, ls='-.')
for nm in ('杜邦頭', '線：上升段', '線：#24 背面水平段'):
    if nm in M.disp:
        draw(ax, rect(*M.disp[nm][:4]), fr, fill=C_WIRE, alpha=0.3, color=C_WIRE, lw=0.8, ls='--')
cu = PR.CABLE_U
ax.annotate('', xy=fr(cu, 1.0), xytext=fr(cu, 8.0), arrowprops=dict(arrowstyle='->', color=C_WIRE, lw=1.5))
for pid, uu in (('#7', 137.376), ('#6', 167.126), ('#5', 199.876)):
    ax.plot(*fr([uu, uu], [14, 98]), color='#aaaaaa', lw=0.6, ls=':')
    ax.text(*fr(uu, 99.5), pid, fontsize=7, color='#888', ha='center')
calls = [
    ('LED 窗 30.6×14.6（紅框）＋M2 螺絲頭 ×4（紅圈）', (229.8, 17.5), C_NEW),
    ('PCB 42×24（藍虛線）與 #26 L 形缺口（藍點劃線）\n藏在 #24 後面，正面看不到', (236.0, 29.0), C_HID),
    ('原 Logo 位置（灰虛線）：被窗佔掉', (228.0, 12.0), '#777777'),
    ('Logo 新位置 L2：ΔU -13.5、ΔV +17.0\n（雕刻＋9 個菱形切穿孔整組；離四周 ≥3.38）', (217.0, 38.0), '#a0306a'),
    ('Logo 備案 L1（綠點線）：ΔU -50.5、ΔV +7.0（≥3.50）', (171.0, 30.0), '#2ca02c'),
    ('D2 原案 Logo（橘點線）：壓到 crosstrack 新「5」→ 不用', (162.0, 22.0), '#ff7f0e'),
    (f'顯示器線（紫）：杜邦頭→上折→#24 背面往右→\nU{cu - 2.8:.1f}~{cu + 2.8:.1f} 越過機頂→#37 頂邊缺口', (cu, 7.5), C_WIRE),
]
for k, (txt, pt, col) in enumerate(calls):
    ty = -(6 + k * 13.5)
    ax.annotate(txt, xy=fr(*pt), xytext=(-118, ty), fontsize=8.5, color=col, ha='left', va='center',
                arrowprops=dict(arrowstyle='->', color=col, lw=0.8, shrinkA=2, shrinkB=2))
ax.set_aspect('equal'); ax.grid(alpha=0.25)
ax.set_xlim(-120, 137); ax.set_ylim(-102, 3)
xt = np.arange(110, 247, 10)
ax.set_xticks(246 - xt); ax.set_xticklabels([f'{v:.0f}' for v in xt])
ax.set_yticks(-np.arange(0, 101, 10)); ax.set_yticklabels([f'{v:.0f}' for v in np.arange(0, 101, 10)])
ax.set_xlabel('U（mm；從正面看往左增加）'); ax.set_ylabel('V（mm，沿面板往下）')
ax.set_title('圖 1　正視 #24（U110~246）：TM1637 LED 塊穿出 #24 窗；Logo 移到窗正下方（L2）；顯示器線藏在 #24 後越過機頂', fontsize=12)
fig.tight_layout(); fig.savefig(HERE + '/fig1_front.png', dpi=125); plt.close(fig)

# ============================================================== fig2 側剖（世界座標）
Y0 = STAB['椴木合板 0.55']['Y0'] if STAB else 0.0
wy = lambda W, V: (-0.5 * np.asarray(V) + 0.866 * np.asarray(W), -0.866 * np.asarray(V) - 0.5 * np.asarray(W) + Y0)


def section_of(s, u):
    """Solid 在 U=u 的截面（(W',V) 多邊形 list）。"""
    out = []
    if s.axis == 'U':
        if s.rng[0] - 1e-6 <= u <= s.rng[1] + 1e-6:
            out = polys(s.poly)
    elif s.axis == 'W':
        cut = s.poly.intersection(LineString([(u, -50), (u, 200)]))
        for seg in ([cut] if cut.geom_type == 'LineString' else list(getattr(cut, 'geoms', []))):
            if seg.is_empty or seg.length == 0:
                continue
            v0, v1 = seg.bounds[1], seg.bounds[3]
            out.append(rect(s.rng[0], s.rng[1], v0, v1))
    elif s.axis == 'V':
        cut = s.poly.intersection(LineString([(u, -50), (u, 200)]))
        for seg in ([cut] if cut.geom_type == 'LineString' else list(getattr(cut, 'geoms', []))):
            if seg.is_empty or seg.length == 0:
                continue
            w0, w1 = seg.bounds[1], seg.bounds[3]
            out.append(rect(w0, w1, s.rng[0], s.rng[1]))
    return out


def tfw(x, y):          # x=W', y=V → world
    return wy(x, y)


fig, axs = plt.subplots(1, 2, figsize=(17, 9))
s24 = Solid('#24 v2', 'W', M.G24_V2, (-6, -3)); s26 = Solid('#26 v2', 'W', M.G26_V2, (-3, 0)); s37 = Solid('#37 v2', 'W', M.G37_V2, (29, 32))
divs = [Solid('#5 v2', 'U', M.DIV5_WV, DIV_U['#5']), Solid('#6 v2', 'U', DIV_V2['#6'], DIV_U['#6']), Solid('#7 v2', 'U', DIV_V2['#7'], DIV_U['#7'])]
for ax, u, ttl in ((axs[0], 212.0, 'U=212 剖面（顯示器、電池帶、主板；50 元滑道）'), (axs[1], 168.0, 'U=168 剖面（顯示器線越頂處、開關旁；10 元滑道）')):
    # 端板（背景）
    draw(ax, G36_WV, tfw, color='#bbbbbb', lw=0.7, ls=':')
    draw(ax, G12_WV, tfw, fill='#d9c7a0', alpha=0.6, color='#8c6d3a', lw=0.8)
    ax.text(*wy(45, 118), '#12', fontsize=9)
    for c in CHUTE_U:
        if CHUTE_U[c][0] <= u <= CHUTE_U[c][1]:
            for z in COIN_ARC:
                if z.name.startswith(c + ' ') and z.rng[0] <= u < z.rng[1]:
                    draw(ax, z.poly, tfw, fill=C_COIN, alpha=0.35, color=C_COIN, lw=0.6)
            ax.text(*wy(14, 80), f'{c} 元翻倒弧＋落下區', fontsize=8, color='#a07a10', ha='center')
    for s, col in ((s24, '#c8a165'), (s26, '#b38b4d'), (s37, '#c8a165')):
        for q in section_of(s, u):
            draw(ax, q, tfw, fill=col, alpha=0.9, color='#5a4220', lw=0.6)
    for d in divs:
        draw(ax, d.poly, tfw, color='#999999', lw=0.6, ls='--')
    for b in M.BOX:
        if b.axis == 'U' and not (b.rng[0] <= u <= b.rng[1]):
            draw(ax, b.poly, tfw, color=C_BOX, lw=0.6, ls='--')       # 背景牆
        for q in section_of(b, u):
            draw(ax, q, tfw, fill=C_BOX, alpha=0.75, color='#145a14', lw=0.6)
    for nm, bx in M.CONTENTS.items():
        if bx[0] <= u <= bx[1]:
            col = {'9V 電池': '#ff9896', '擴展板 PCB': '#9467bd', 'ESP32 開發板＋母座': '#555555', '開關本體': '#e377c2'}.get(nm, '#aaaaaa')
            draw(ax, rect(bx[4], bx[5], bx[2], bx[3]), tfw, fill=col, alpha=0.55, color=col, lw=0.5)
    for nm, bx in M.disp.items():
        if bx[0] <= u <= bx[1]:
            col = '#222222' if nm.startswith('LED') else ('#1f77b4' if nm.startswith('PCB') else C_WIRE)
            draw(ax, rect(bx[4], bx[5], bx[2], bx[3]), tfw, fill=col, alpha=0.8, color=col, lw=0.5)
    wpath = M.WIRES['顯示器 4P（G14/G13/V/G）']
    X, Y = wy(wpath[:, 2], wpath[:, 1])
    ax.plot(X, Y, color=C_WIRE, lw=1.8, alpha=0.8, label='顯示器線（投影）')
    # 視線
    cZ, cY = wy(-3 - M.D['body_H'], M.Vc)
    for dep, ls_, lab in ((15, '-', '坐 俯角 15°'), (27, '-', '坐 俯角 27°'), (45, '--', '站 俯角 45°')):
        L_ = 95
        ax.plot([cZ, cZ - L_ * math.cos(math.radians(dep))], [cY, cY + L_ * math.sin(math.radians(dep))], color='#555', lw=0.8, ls=ls_)
        ax.text(cZ - L_ * math.cos(math.radians(dep)), cY + L_ * math.sin(math.radians(dep)) + 2, lab, fontsize=7.5, color='#555')
    if STAB:
        st = STAB['椴木合板 0.55']
        for z, col, lab in ((st['Zr'], 'g', '後腳'), (st['Zf'], 'g', '前腳'), (st['Z_tot'], 'b', '合計重心'), (st['Z_machine'], 'k', '原機重心')):
            ax.plot([z, z], [0, 8], color=col, lw=2); ax.text(z, 10, lab, fontsize=7.5, color=col, ha='center', rotation=90, va='bottom')
    ax.axhline(0, color='k', lw=1)
    ax.set_aspect('equal'); ax.grid(alpha=0.25); ax.set_xlim(-110, 95); ax.set_ylim(-5, 230)
    ax.set_xlabel('Z（mm，往機身後方為正）'); ax.set_ylabel('離桌高 Y（mm）'); ax.set_title(ttl, fontsize=11)
axs[0].text(-105, 222, '綠＝電子盒（實線剖到、虛線背景牆）；粉紅＝9V 電池；紫框＝擴展板；灰＝開發板；黃＝硬幣區；紫線＝顯示器線', fontsize=8)
fig.suptitle('圖 2　側剖（機身後仰 30°）：TM1637 在 #24 正面左上；電子盒掛 #37 背面，電池帶在盒頂、頂面凸出 4 mm', fontsize=12)
fig.tight_layout(); fig.savefig(HERE + '/fig2_section.png', dpi=120); plt.close(fig)

# ============================================================== fig3 背視
fb = lambda x, y: (np.asarray(x), -np.asarray(y))
fig, ax = plt.subplots(figsize=(17, 9))
draw(ax, M.G37_V2, fb, fill='#f1e3c6', alpha=0.6, color=C_CUT, lw=0.9)
for s in M.SLOTS37 + [M.CABLE_NOTCH.intersection(rect(0, 300, 4, 100)), M.SENSOR_HOLE]:
    draw(ax, s, fb, fill=C_NEW, alpha=0.5, color=C_NEW, lw=1.0)
draw(ax, rect(105, 239, 82, 114), fb, fill='#dddddd', alpha=0.5, color='#999', lw=0.6, ls=':')
ax.text(172, -100, '#12 抽屜櫃後板（#37 下緣 V82 之下、往後）', ha='center', fontsize=8, color='#777')
draw(ax, rect(*PR.S1_ZONE['U'], *PR.S1_ZONE['V']), fb, fill='#ffbb78', alpha=0.35, color='#ff7f0e', lw=0.8, ls='--')
ax.text(113.5, -66, 'S1 禁區\n（s1wall 兩案聯集）', ha='center', fontsize=8, color='#c45a00')
draw(ax, rect(*PR.MOTOR_SW), fb, fill='#333', alpha=0.6, color='#000', lw=0.6)
ax.text(47, -24, '原馬達開關', ha='center', fontsize=8)
for b in M.BOX:
    if b.axis == 'U':
        x0, x1 = b.rng; y0, y1 = M.Vt, M.Vb
        draw(ax, rect(x0, x1, y0, y1), fb, fill=C_BOX, alpha=0.6, color='#145a14', lw=0.8)
    elif b.axis == 'W':
        draw(ax, b.poly, fb, fill=C_BOX, alpha=0.12, color='#145a14', lw=0.8)
    else:
        x0, w0, x1, w1 = b.poly.bounds
        draw(ax, rect(x0, x1, b.rng[0], b.rng[1]), fb, fill=C_BOX, alpha=0.5, color='#145a14', lw=0.8)
for nm, bx in M.CONTENTS.items():
    if nm.startswith('M3 螺絲尖'):
        continue
    col = {'9V 電池': '#ff9896', '電池扣（含線彎）': '#ffbbaa', '擴展板 PCB': '#c5b0d5', 'ESP32 開發板＋母座': '#666666', '開關本體': '#e377c2',
           'USB 座': '#17becf', 'DC 座': '#17becf'}.get(nm, '#bbbbbb')
    a = 0.35 if nm.startswith(('擴展板', '墊高', '未用', '用到')) else 0.7
    draw(ax, rect(bx[0], bx[1], bx[2], bx[3]), fb, fill=col, alpha=a, color=col, lw=0.6)
    if nm in ('9V 電池', 'ESP32 開發板＋母座', '開關本體', '用到的 GVS 列＋杜邦頭＋彎線（下）', '電池扣（含線彎）'):
        ax.text((bx[0] + bx[1]) / 2, -(bx[2] + bx[3]) / 2, nm.replace('（下）', ''), ha='center', va='center', fontsize=7.5)
for nm, bx in (('USB 插頭', M.USB_PLUG), ('DC 插頭', M.DC_PLUG)):
    draw(ax, rect(bx[0], bx[1], bx[2], bx[3]), fb, fill='#17becf', alpha=0.25, color='#17becf', lw=0.8, ls='--')
    ax.text(bx[1] - 2, -(bx[2] + bx[3]) / 2, nm, fontsize=7.5, ha='right', va='center', color='#0e7c86')
for u, v in M.EN_BTN:
    ax.add_patch(Circle(fb(u, v), 1.6, color='orange'))
ax.text(M.EN_BTN[0][0] - 3, -M.EN_BTN[0][1], 'EN／BOOT', fontsize=7.5, color='#c46200', ha='right')
for k, g_ in M.GPIO_U.items():
    if k in ('33', '25', '26', '27', '14', '13'):
        ax.plot([g_, g_], [-(M.board[3] - 9.0), -(M.board[3] - 4.0)], color='#d62728', lw=1.2)
        ax.text(g_, -(M.board[3] - 2.0), 'G' + k, fontsize=6, ha='center', color='#d62728', rotation=90, va='top')
cols = {'顯示器': '#9467bd', 'S5': '#2ca02c', 'S10': '#ff7f0e', 'S50': '#1f77b4', 'S1': '#8c564b', '電池扣': '#e377c2'}
for k, v in M.WIRES.items():
    c = [cc for kk, cc in cols.items() if k.startswith(kk)][0]
    vv = v[v[:, 2] > 28.0] if not k.startswith('電池扣') else v
    if k.startswith('顯示器'):
        vv = v[5:]
    off = {'S5': -1.6, 'S10': 0.0, 'S50': 1.6}.get(k.split()[0], 0.0)
    ax.plot(vv[:, 0] + off, -vv[:, 1] - off, color=c, lw=1.6, alpha=0.85, label=f'{k}（全長 {M.WIRE_LEN[k]:.0f} mm）')
ax.legend(loc='lower left', fontsize=8)
ax.text(94, -36, '感測器線孔\n12×6', fontsize=7.5, color=C_NEW, ha='center')
ax.text(147.5, 2.5, 'WL 掛勾槽', fontsize=7.5, color=C_NEW, ha='center'); ax.text(238.5, 2.5, 'WR 掛勾槽', fontsize=7.5, color=C_NEW, ha='center')
ax.text(168, 5.5, '顯示器線缺口', fontsize=7.5, color=C_NEW, ha='center')
ax.set_aspect('equal'); ax.grid(alpha=0.25); ax.set_xlim(-2, 262); ax.set_ylim(-118, 9)
ax.set_yticks(-np.arange(0, 120, 10)); ax.set_yticklabels([f'{v:.0f}' for v in np.arange(0, 120, 10)])
ax.set_xlabel('U（mm；從背面看往右增加）'); ax.set_ylabel('V（mm）')
ax.set_title('圖 3　從背面看 #37（紅＝v2 新開孔）與電子盒（綠＝盒體；粉紅＝橫躺電池帶；紫＝擴展板）；彩線＝排線中心線', fontsize=12)
fig.tight_layout(); fig.savefig(HERE + '/fig3_back.png', dpi=120); plt.close(fig)

# ============================================================== fig4 零件展開
parts = [(b.name, b.poly, PLANE[b.axis]) for b in M.BOX] + [('EB-K 防拔鍵（選用）×2', M.KEY_WV, ('W', 'V')),
                                                            ('#5 v2（局部；灰虛線＝crosstrack v2）', M.DIV5_LOCAL, ('x', 'y'))]
fig, axs = plt.subplots(3, 3, figsize=(17, 13))
for ax, (nm, g, ax2) in zip(axs.ravel(), parts):
    b = g.bounds
    loc = affinity.translate(g, -b[0], -b[1]) if not nm.startswith('#5') else g
    if nm.startswith('#5'):
        draw(ax, DIV_V2_LOCAL['#5'], color='#999', lw=0.8, ls='--')
        draw(ax, rect(-1, M.DIV5_CUT_W + 6, -1, M.DIV5_CUT_V - 14), fill=C_NEW, alpha=0.2, color=C_NEW, lw=0.6)
    draw(ax, loc, fill='#e8d3a8', alpha=0.6, color=C_CUT, lw=0.9)
    for q in polys(loc):
        for r in q.interiors:
            x, y = np.array(r.coords).T; ax.fill(x, y, color='white')
    ax.set_aspect('equal'); ax.grid(alpha=0.3); ax.invert_yaxis()
    w_, h_ = b[2] - b[0], b[3] - b[1]
    ax.set_title(f'{nm}\n{w_:.1f}×{h_:.1f}（a＝{ax2[0]}-{b[0]:.2f}、b＝{ax2[1]}-{b[1]:.2f}）' if not nm.startswith('#5') else nm, fontsize=9)
fig.suptitle('圖 4　電子盒 7 片＋防拔鍵（局部座標 a→右、b→下；3 mm 合板）與 #5 v2', fontsize=13)
fig.tight_layout(); fig.savefig(HERE + '/fig4_parts.png', dpi=110); plt.close(fig)
print('figs done')

"""光耦測試原型組裝教學網頁的圖。

只讀 make_proto.py 的幾何（import，不執行它的 main、不改任何檔）與它輸出的 示意圖.png、預覽.png，
另外複製接線圖 PNG。輸出到 組裝教學/img/。

執行（repo 根目錄）：.venv/Scripts/python.exe -B 04_光耦測試原型/組裝教學/make_figures.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(HERE)
IMG = os.path.join(HERE, 'img')
sys.path.insert(0, PROTO)

import matplotlib                                  # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt                    # noqa: E402
from matplotlib import font_manager                # noqa: E402
from matplotlib.patches import FancyArrowPatch, Polygon as MPoly, Rectangle  # noqa: E402
from PIL import Image                              # noqa: E402

import make_proto as P                             # noqa: E402

font_manager.fontManager.addfont(P.FONT_PATH)
plt.rcParams['font.family'] = font_manager.FontProperties(fname=P.FONT_PATH).get_name()
plt.rcParams['axes.unicode_minus'] = False

C_WOOD, C_WOOD_EDGE = '#ecdcc2', '#9c8a6c'
C_D = '#d9b88a'                       # 擋幣板 D 深一點，和背牆 B 分開
C_PCB, C_ARM, C_SOLDER = '#5aa469', '#2f5d43', '#a9d3b0'
C_SHIM, C_NEW = '#f0a640', '#0f7c8a'
C_INK, C_MUTED = '#2b2620', '#6b6357'
DPI = 140


def save(fig, name):
    os.makedirs(IMG, exist_ok=True)
    fig.savefig(os.path.join(IMG, name), dpi=DPI, bbox_inches='tight', pad_inches=0.08, facecolor='white')
    plt.close(fig)
    print('完成', name)


def poly(ax, g, fc, ec='#555', lw=0.8, alpha=1.0, ls='-', z=2):
    for p in getattr(g, 'geoms', [g]):
        ax.add_patch(MPoly(list(p.exterior.coords), closed=True, fc=fc, ec=ec, lw=lw, alpha=alpha, ls=ls, zorder=z))


def arrow(ax, a, b, color=C_NEW):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=16, lw=2, color=color, zorder=10))


def note(ax, x, y, s, color=C_INK, size=9, ha='left', va='center'):
    ax.text(x, y, s, fontsize=size, color=color, ha=ha, va=va, zorder=12)


# ---------------------------------------------------------------------------
# 1. 現成的圖：預覽（零件辨識）、示意圖拆成三張、接線圖
# ---------------------------------------------------------------------------
def copy_assets(max_w=1600):
    os.makedirs(IMG, exist_ok=True)
    im = Image.open(os.path.join(PROTO, '預覽.png'))
    im.resize((1200, round(im.height * 1200 / im.width)), Image.LANCZOS).save(os.path.join(IMG, 'parts.png'), optimize=True)
    fig = Image.open(os.path.join(PROTO, '示意圖.png')).convert('RGB')
    w, h = fig.size
    fig.save(os.path.join(IMG, 'schematic.png'), optimize=True)
    # 示意圖 ① 正視、③ 側視單獨切出來（② 的說明字和 ③ 的軸標籤左右重疊，② 只放整張）
    fig.crop((0, 45, int(w * 0.437), h)).save(os.path.join(IMG, 'view-front.png'), optimize=True)
    x0 = int(w * 0.705)
    side = fig.crop((x0, 100, w, h))
    side.paste((255, 255, 255), (0, 398, 20, 420))   # 蓋掉 ② 說明字伸過來的字尾
    side.paste((255, 255, 255), (0, 255, 6, 290))
    side.save(os.path.join(IMG, 'view-side.png'), optimize=True)
    wi = Image.open(os.path.join(PROTO, '接線圖', '光耦測試原型_ESP32_接線圖.png'))
    wi.resize((max_w, round(wi.height * max_w / wi.width)), Image.LANCZOS).save(os.path.join(IMG, 'wiring.png'), optimize=True)
    print('完成 現成的圖')


# ---------------------------------------------------------------------------
# 2. 4-1 對位：B 平放、墊紙＋F 在窗裡、D 套上去（沿軌道方向的剖面，厚度放大）
# ---------------------------------------------------------------------------
def align_figure():
    K = 4.0                             # 厚度方向放大倍數
    t = P.T_PLY * K
    ww = P.WIN_W                        # 窗寬（沿軌道）
    fw = ww - 2 * P.C_TAB               # F 寬
    pad_t, pad_w = 1.5 * K, 22.0        # 墊紙
    x0, x1 = -45.0, 45.0
    fig, axes = plt.subplots(1, 2, figsize=(12, 2.8))
    for k, ax in enumerate(axes):
        ax.plot([x0 - 4, x1 + 4], [0, 0], color=C_INK, lw=1.5)
        note(ax, x1 + 4, -2.5, '桌面', C_MUTED, ha='right', va='top')
        # B：窗兩側
        for a, b in ((x0, -ww / 2), (ww / 2, x1)):
            ax.add_patch(Rectangle((a, 0), b - a, t, fc=C_WOOD, ec=C_WOOD_EDGE, lw=0.8, zorder=2))
        # 墊紙、F
        ax.add_patch(Rectangle((-pad_w / 2, 0), pad_w, pad_t, fc='#f6f3ea', ec='#999', lw=0.8, hatch='///', zorder=3))
        ax.add_patch(Rectangle((-fw / 2, pad_t), fw, t, fc='#c9e4ea', ec=C_NEW, lw=1.2, zorder=3))
        note(ax, 0, pad_t + t / 2, 'F', C_NEW, 11, ha='center')
        note(ax, x0 + 2, t / 2, 'B 背牆（正面朝上）', C_INK, 9)
        if k == 0:
            ax.set_title('① B 平放；墊紙放進窗、F 坐在墊紙上（凸出 B 約 1.5 mm）', fontsize=10, color=C_INK)
            note(ax, 0, -2.5, '墊紙（5 張名片，約 1.5 mm）', C_MUTED, 8.5, ha='center', va='top')
            note(ax, fw / 2 + 2, pad_t + t + 3, 'F 四邊包保鮮膜', C_NEW, 8.5)
            ax.annotate('', xy=(ww / 2 + 6, pad_t + t), xytext=(ww / 2 + 6, t),
                        arrowprops=dict(arrowstyle='<->', color=C_MUTED, lw=1))
            note(ax, ww / 2 + 8, t + (pad_t) / 2, '1.5', C_MUTED, 8.5)
            ax.set_ylim(-6, 3 * t + 6)
        else:
            ax.set_title('② D 正面朝上，窗套進凸出來的 F；壓書、擦掉擠出來的膠', fontsize=10, color=C_INK)
            yD = t + 0.25 * K
            for a, b in ((x0, -ww / 2), (ww / 2, x1)):
                ax.add_patch(Rectangle((a, yD), b - a, t, fc=C_D, ec=C_WOOD_EDGE, lw=0.8, zorder=2))
                # 白膠：窗邊留 2 mm 不塗
                ga, gb = (a, b - 2) if b < 0 else (a + 2, b)
                ax.add_patch(Rectangle((ga, t), gb - ga, yD - t, fc='#ffffff', ec='#8aa', lw=0.6, hatch='....', zorder=2))
            note(ax, x0 + 2, yD + t / 2, 'D 擋幣板（正面朝上）', C_INK, 9)
            note(ax, ww / 2 + 4, yD + t + 3, '白膠：窗邊留 2 mm 不塗', C_MUTED, 8.5)
            arrow(ax, (x0 + 30, yD + t + 9), (x0 + 30, yD + t + 1))
            note(ax, x0 + 32, yD + t + 7, '壓書', C_NEW, 8.5)
            ax.set_ylim(-6, 3 * t + 6)
        ax.set_xlim(x0 - 6, x1 + 6)
        ax.set_aspect('equal')
        ax.axis('off')
    fig.text(0.5, -0.02, '沿軌道方向切開的剖面；厚度方向放大 4 倍。30 分鐘後拿掉墊紙，從背面把 F 頂出來。',
             ha='center', fontsize=9, color=C_MUTED)
    save(fig, 'align.png')


# ---------------------------------------------------------------------------
# 3. 第 6 節：模組 低位推入 → 抬到頂 → 塞墊片（沿光束的剖面，同示意圖 ②）
# ---------------------------------------------------------------------------
def _boards(ax):
    s_beam = dict(P.LH_S)[P.M['wing']]
    for name, g in P.boards_section(s_beam).items():
        poly(ax, g, C_D if name.startswith('擋幣板') else C_WOOD, C_WOOD_EDGE, z=2)


def _module(ax, n_sb, dw=0.0, ghost=False):
    parts = P.module_section(n_sb, w_fa=-P.T_PLY + dw)
    col = {'前臂': C_ARM, '後臂': C_ARM, '本體': C_ARM, 'PCB': C_PCB, '焊點': C_SOLDER, '元件': '#8cc79a', '排針': '#333'}
    for k in ('焊點', 'PCB', '元件', '排針', '本體', '前臂', '後臂'):
        poly(ax, parts[k], 'none' if ghost else col[k], '#7a7a7a' if ghost else '#1f3a2a',
             lw=0.8, ls='--' if ghost else '-', alpha=1.0, z=1 if ghost else 4)
    if not ghost:
        nb = n_sb + P.M['beam_sb']
        ax.plot([-P.T_PLY + dw, -P.T_PLY + dw + P.M['slot_w']], [nb, nb], color='#d7263d', lw=1.4, ls='-.', zorder=6)


def install_figure():
    n_low, n_top = P.n_sb_low(), P.N_STRIP
    H = P.H0
    n_shim = min(P.n_sb_on(H), P.N_STRIP)
    back = P.T_PLY + P.M['arm_t'] + P.T_PLY + 4.0          # 推入前：前臂整個在背牆後面
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4))
    titles = ('① 低位推入：PCB 靠窗底，垂直背牆往前推', '② 往上抬到頂：軌道條進到兩臂中間',
              f'③ 從前面塞墊片（以暫定尺寸是 E7 {H:.1f}）')
    for k, ax in enumerate(axes):
        _boards(ax)
        if k == 0:
            _module(ax, n_low, dw=back, ghost=True)
            _module(ax, n_low)
            arrow(ax, (28, P.N_WB - 6), (8, P.N_WB - 6))
            note(ax, 18, P.N_WB - 9, '往前推', C_NEW, 9, ha='center', va='top')
        elif k == 1:
            _module(ax, n_low, ghost=True)
            _module(ax, n_top)
            arrow(ax, (22, n_low + 2), (22, n_top + 2))
            note(ax, 23, (n_low + n_top) / 2 + 2, '抬起約\n12.5 mm', C_NEW, 9)
        else:
            poly(ax, P.shim_poly(H), C_SHIM, '#9a5800', lw=1, z=3)
            _module(ax, n_shim)
            arrow(ax, (-26, P.N_WB + H / 2), (-10, P.N_WB + H / 2))
            note(ax, -26, P.N_WB - 7, '墊片：雕字朝右，\n擋耳在前、往下垂', C_INK, 8.5, ha='left', va='top')
        ax.axhline(0, color='#c0392b', lw=0.6, ls=':', zorder=1)
        note(ax, -26, 1.2, '軌道', '#c0392b', 8.5, va='bottom')
        note(ax, -26, 21, '← 正面（前）', C_MUTED, 8.5, va='top')
        note(ax, 32, 21, '背後 →', C_MUTED, 8.5, ha='right', va='top')
        ax.set_xlim(-27, 33)
        ax.set_ylim(P.N_WB - 16, 22)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(titles[k], fontsize=10, color=C_INK)
    fig.text(0.5, 0.0, '沿光束切開的剖面（同示意圖 ②）：淺木色＝背牆 B、深木色＝擋幣板 D、綠＝光耦模組、橘＝墊片、'
             '紅虛線＝光束；虛線框＝上一個位置。尺寸是暫定值。', ha='center', fontsize=9, color=C_MUTED)
    save(fig, 'install.png')


def main():
    copy_assets()
    align_figure()
    install_figure()


if __name__ == '__main__':
    main()

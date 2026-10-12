"""組裝教學網頁的圖：零件在哪張板、組裝示意圖（正視＋側視）、零件攤平圖。

只讀 v2 產生器（laser_v2）與它的輸出，不改任何東西：
  - 零件位置：laser_v2/out/sheet_*.svg（上雷切機用的分頁檔，每個零件一個群組，data-part＝代號）
  - 零件外形：在記憶體裡跑 子系統 → 合成（和 build_v2 相同），得到 v2 版零件（原始頁座標）
  - 組裝座標：laser_v2/frames.py（機身 11 片：#24 #26 #37 #5 #6 #7 #13 #21 #12 #31 #36）

執行（在 03_v2_光耦版 資料夾）：../.venv/Scripts/python.exe -B 組裝教學/make_figures.py
輸出：組裝教學/img/*.png；步驟定義在 steps.py。
"""
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
V2 = os.path.dirname(HERE)
sys.path.insert(0, V2)
IMG = os.path.join(HERE, 'img')
SHEETS = [('合板1', 'sheet_合板_1.svg'), ('合板2', 'sheet_合板_2.svg'), ('合板3', 'sheet_合板_3.svg'),
          ('壓克力1', 'sheet_壓克力_1.svg')]

import matplotlib                                  # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt                    # noqa: E402
from matplotlib import font_manager                # noqa: E402
from matplotlib.patches import PathPatch           # noqa: E402
from matplotlib.path import Path as MPath          # noqa: E402
import numpy as np                                 # noqa: E402
from shapely import affinity                       # noqa: E402
from shapely.geometry import MultiPolygon, Polygon  # noqa: E402
from svgpathtools import parse_path                # noqa: E402

from laser_v2 import params                        # noqa: E402

font_manager.fontManager.addfont(params.FONT_PATH)
plt.rcParams['font.family'] = font_manager.FontProperties(fname=params.FONT_PATH).get_name()

# 色票（和網頁的色調一致：木色零件、深青強調）
C_WOOD = '#e9d9bf'       # 已裝好的零件
C_WOOD_EDGE = '#9c8a6c'
C_NEW = '#0f7c8a'        # 這一步新加的零件
C_NEW_FILL = '#9fd6dc'
C_INK = '#2b2620'
C_FAINT = '#c8c0b2'
DPI = 140


# ---------------------------------------------------------------------------
# 共用：shapely 幾何畫成 matplotlib 圖形
# ---------------------------------------------------------------------------
def _polys(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return list(g.geoms)
    return [p for p in getattr(g, 'geoms', []) if isinstance(p, Polygon)]


def draw_geom(ax, g, face, edge, lw=0.8, alpha=1.0, z=1):
    for p in _polys(g):
        verts, codes = [], []
        for ring in [p.exterior] + list(p.interiors):
            c = np.asarray(ring.coords)
            verts.extend(c.tolist())
            codes.extend([MPath.MOVETO] + [MPath.LINETO] * (len(c) - 2) + [MPath.CLOSEPOLY])
        ax.add_patch(PathPatch(MPath(verts, codes), facecolor=face, edgecolor=edge, lw=lw, alpha=alpha, zorder=z))


def _fit(ax, geoms, pad=6):
    """add_patch 不會自動調整座標範圍：依幾何範圍明確設定（y 往下為正）。"""
    bs = [g.bounds for g in geoms if g is not None and not g.is_empty]
    if not bs:
        return
    x0, y0 = min(b[0] for b in bs) - pad, min(b[1] for b in bs) - pad
    x1, y1 = max(b[2] for b in bs) + pad, max(b[3] for b in bs) + pad
    ax.set_xlim(x0, x1)
    ax.set_ylim(y1, y0)
    ax.set_aspect('equal')


def label(ax, x, y, s, color=C_NEW, size=9, z=20):
    ax.text(x, y, s, color=color, fontsize=size, ha='center', va='center', zorder=z, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.15', fc='white', ec=color, lw=0.6, alpha=0.9))


def save(fig, name):
    os.makedirs(IMG, exist_ok=True)
    path = os.path.join(IMG, name)
    fig.savefig(path, dpi=DPI, bbox_inches='tight', pad_inches=0.08, facecolor='white')
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 1. 零件在哪張板（讀上雷切機用的分頁 SVG）
# ---------------------------------------------------------------------------
_SHEET_CACHE = None


def _sample(d, step=0.6):
    p = parse_path(d)
    n = max(2, int(p.length() / step) + 1) if p.length() > 0 else 2
    pts = [p.point(t) for t in np.linspace(0, 1, n)]
    return np.array([[z.real, z.imag] for z in pts])


def load_sheets():
    """{板名: [(代號, 是否備品, outline 多邊形或 None, [線段點列])]}"""
    global _SHEET_CACHE
    if _SHEET_CACHE is not None:
        return _SHEET_CACHE
    ns = {'s': 'http://www.w3.org/2000/svg'}
    out = {}
    for name, fn in SHEETS:
        root = ET.parse(os.path.join(V2, 'laser_v2', 'out', fn)).getroot()
        items = []
        for g in root.iter('{http://www.w3.org/2000/svg}g'):
            pid = g.get('data-part')
            if not pid:
                continue
            outline, lines = None, []
            for p in g.findall('s:path', ns):
                if '#000000' not in (p.get('style') or ''):
                    continue                      # 只畫切割線（雕刻略過）
                pts = _sample(p.get('d'))
                lines.append(pts)
                if p.get('data-kind') == 'outer' and len(pts) >= 4:
                    outline = Polygon(pts).buffer(0)
            items.append((pid, g.get('data-spare') == '1', outline, lines))
        out[name] = items
    _SHEET_CACHE = out
    return out


def sheet_locator(ids, fname, title=None):
    """4 張板的縮圖，ids 裡的零件塗強調色並標代號。只有用到的板會放大標題。"""
    ids = set(ids)
    sheets = load_sheets()
    used = [n for n, _ in SHEETS if any(pid in ids for pid, _, _, _ in sheets[n])]
    fig, axes = plt.subplots(1, 4, figsize=(13, 4.6))
    for ax, (name, _) in zip(axes, SHEETS):
        w, h = (255, 355)
        ax.add_patch(plt.Rectangle((0, 0), w, h, fc='#faf7f2', ec=C_FAINT, lw=0.8, zorder=0))
        for pid, spare, outline, lines in sheets[name]:
            hit = pid in ids and not spare
            if hit and outline is not None:
                draw_geom(ax, outline, C_NEW_FILL, C_NEW, lw=0.9, z=2)
            for pts in lines:
                ax.plot(pts[:, 0], pts[:, 1], color=C_NEW if hit else C_FAINT, lw=0.7 if hit else 0.35, zorder=3)
            if hit and outline is not None:
                c = outline.representative_point()
                label(ax, c.x, c.y, pid, size=7)
        ax.set_xlim(-4, w + 4)
        ax.set_ylim(h + 4, -4)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(name + ('　← 這一步用到' if name in used else ''), fontsize=11,
                     color=C_NEW if name in used else '#8a8378', fontweight='bold' if name in used else 'normal')
    if title:
        fig.suptitle(title, fontsize=12, color=C_INK)
    return save(fig, fname)


# ---------------------------------------------------------------------------
# 2. v2 版零件外形（記憶體裡跑 子系統 → 合成，和 build_v2 相同；不輸出檔案）
# ---------------------------------------------------------------------------
_PARTS = None


def v2_parts():
    global _PARTS
    if _PARTS is None:
        from laser_v2 import build_v2, compose, integrate
        cat = build_v2.load_parts()
        results = build_v2.run_subsystems(cat)
        results['ebox'], _ = integrate.ebox_integrated(cat, results)
        _PARTS = {p.id: p for p in compose.compose(cat, results)}
    return _PARTS


def _frame(pid):
    from laser_v2 import frames as F
    p = v2_parts()[pid]
    oid = getattr(p, 'orig_id', None) or pid
    try:
        return F.frame(oid)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 3. 組裝示意圖：左＝正視（垂直面板看，U 往左增加、V 往下），右＝側視（從右端看，機身後仰 30°）
# ---------------------------------------------------------------------------
TILT = math.radians(30)


def _side(g):
    c, s = math.cos(TILT), math.sin(TILT)
    return affinity.affine_transform(g, [c, -s, s, c, 0, 0])     # (W', V) → (往後, 往下)


def assembly_view(installed, new, fname, title=None, side=True):
    parts = v2_parts()
    items = []
    for pid in list(installed) + list(new):
        fr = _frame(pid)
        if fr is None:
            print(f'（略過）{pid} 沒有組裝座標')
            continue
        p = parts[pid]
        gF = fr.footprint(('U', 'V'), geom=p.geom)
        gS = _side(fr.footprint(('W', 'V'), geom=p.geom))
        wc = fr.footprint(('W', 'V'), geom=p.geom).centroid.x
        uc = gF.centroid.x
        items.append(dict(pid=pid, new=pid in new, front=affinity.scale(gF, -1, 1, origin=(0, 0)), side=gS,
                          w=wc, u=uc))
    ncol = 2 if side else 1
    fig, axes = plt.subplots(1, ncol, figsize=(12 if side else 8, 5.0),
                             gridspec_kw=dict(width_ratios=[2.4, 1] if side else [1]))
    axes = np.atleast_1d(axes)
    # 正視：後面的先畫（W' 大的在後）
    ax = axes[0]
    for it in sorted(items, key=lambda d: -d['w']):
        draw_geom(ax, it['front'], C_NEW_FILL if it['new'] else C_WOOD, C_NEW if it['new'] else C_WOOD_EDGE,
                  lw=1.1 if it['new'] else 0.6, alpha=0.85 if it['new'] else 0.6, z=3 if it['new'] else 2)
    for it in items:
        if it['new']:
            c = it['front'].representative_point()
            label(ax, c.x, c.y, it['pid'])
    _fit(ax, [it['front'] for it in items])
    ax.axis('off')
    ax.set_title('正視（從正面看，面板攤平）', fontsize=10, color='#6b6357')
    if side:
        ax = axes[1]
        for it in sorted(items, key=lambda d: -d['u']):     # 離觀看者（右端，U 小）近的後畫
            draw_geom(ax, it['side'], C_NEW_FILL if it['new'] else C_WOOD, C_NEW if it['new'] else C_WOOD_EDGE,
                      lw=1.1 if it['new'] else 0.6, alpha=0.8 if it['new'] else 0.55, z=3 if it['new'] else 2)
        ys = [it['side'].bounds[3] for it in items]
        xs = [b for it in items for b in (it['side'].bounds[0], it['side'].bounds[2])]
        if ys:
            ax.plot([min(xs) - 10, max(xs) + 10], [max(ys), max(ys)], color=C_INK, lw=1.2)
            ax.text(min(xs) - 8, max(ys) + 6, '前', fontsize=9, color='#6b6357', va='top')
            ax.text(max(xs) + 8, max(ys) + 6, '後', fontsize=9, color='#6b6357', va='top', ha='right')
        placed = []
        for it in items:
            if it['new']:
                c = it['side'].representative_point()
                if any(abs(c.x - x) < 14 and abs(c.y - y) < 8 for x, y in placed):
                    continue                          # 側視時重疊的零件（例如三片間隔條）只標一個
                placed.append((c.x, c.y))
                label(ax, c.x, c.y, it['pid'], size=8)
        _fit(ax, [it['side'] for it in items], pad=14)
        ax.axis('off')
        ax.set_title('側視（從右端看，後仰 30°）', fontsize=10, color='#6b6357')
    if title:
        fig.suptitle(title, fontsize=12, color=C_INK)
    return save(fig, fname)


# ---------------------------------------------------------------------------
# 4. 零件攤平圖（同一比例並排，畫切割外形與雕刻，方便認零件）
# ---------------------------------------------------------------------------
_D_RE = re.compile(r'\bd="([^"]+)"')


def parts_flat(ids, fname, title=None, row_mm=420, gap=10):
    parts = v2_parts()
    rows, row, x = [], [], 0.0
    for pid in ids:
        p = parts[pid]
        b = p.geom.bounds
        w = b[2] - b[0]
        if row and x + w > row_mm:
            rows.append(row)
            row, x = [], 0.0
        row.append((pid, x))
        x += w + gap
    if row:
        rows.append(row)
    heights = [max(parts[pid].geom.bounds[3] - parts[pid].geom.bounds[1] for pid, _ in r) for r in rows]
    total_h = sum(heights) + 18 * len(rows)
    fig, ax = plt.subplots(figsize=(11, max(2.2, 11 * total_h / row_mm)))
    y0 = 0.0
    for r, hh in zip(rows, heights):
        for pid, xo in r:
            p = parts[pid]
            b = p.geom.bounds
            dx, dy = xo - b[0], y0 - b[1]
            draw_geom(ax, affinity.translate(p.geom, dx, dy), C_WOOD, C_WOOD_EDGE, lw=0.7)
            for e in p.engrave:
                m = _D_RE.search(e)
                if not m or not e.lstrip().startswith('<path'):
                    continue
                try:
                    pts = _sample(m.group(1), step=0.4)
                except Exception:
                    continue
                ax.plot(pts[:, 0] + dx, pts[:, 1] + dy, color='#c0392b', lw=0.5, zorder=4)
            ax.text(xo + (b[2] - b[0]) / 2, y0 + (b[3] - b[1]) + 7, pid, ha='center', va='top',
                    fontsize=9, color=C_NEW, fontweight='bold')
        y0 += hh + 18
    ax.set_aspect('equal')
    ax.invert_yaxis()
    ax.autoscale()
    ax.axis('off')
    if title:
        ax.set_title(title, fontsize=11, color=C_INK)
    return save(fig, fname)


# ---------------------------------------------------------------------------
# 5. 照片、規格附圖、接線圖：縮成網頁用尺寸複製到 img/
# ---------------------------------------------------------------------------
REPO = os.path.dirname(V2)
PHOTOS = {   # 原機組裝完成照片（2026-09-21）
    'photo-front.jpg': 'IMG_20260921_151443.jpg',
    'photo-right.jpg': 'IMG_20260921_151448.jpg',
    'photo-back.jpg': 'IMG_20260921_151452.jpg',
    'photo-top.jpg': 'IMG_20260921_151503.jpg',
}
SPEC_FIGS = {   # 三份 v2 規格的附圖（設計審查時畫的；數字以 report.md 為準）
    'spec-crosstrack-front.png': 'crosstrack_final/fig_front.png',
    'spec-crosstrack-section.png': 'crosstrack_final/fig_section.png',
    'spec-crosstrack-parts.png': 'crosstrack_final/fig_parts.png',
    'spec-s1-section.png': 's1wall_final/fig1_section.png',
    'spec-s1-front.png': 's1wall_final/fig2_front.png',
    'spec-s1-parts.png': 's1wall_final/fig3_parts.png',
    'spec-ebox-front.png': 'ebox_final/fig1_front.png',
    'spec-ebox-section.png': 'ebox_final/fig2_section.png',
    'spec-ebox-back.png': 'ebox_final/fig3_back.png',
    'spec-ebox-parts.png': 'ebox_final/fig4_parts.png',
}


def prep_assets(max_w=1600):
    from PIL import Image
    os.makedirs(IMG, exist_ok=True)
    jobs = [(os.path.join(REPO, '01_原始機構', '組裝完成圖', src), dst) for dst, src in PHOTOS.items()]
    jobs += [(os.path.join(V2, 'laser_v2', 'design', src), dst) for dst, src in SPEC_FIGS.items()]
    jobs.append((os.path.join(V2, '接線圖', '分幣機_v2光耦版_ESP32_接線圖.png'), 'wiring.png'))
    for src, dst in jobs:
        im = Image.open(src)
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        out = os.path.join(IMG, dst)
        if dst.endswith('.jpg'):
            im.convert('RGB').save(out, quality=82, optimize=True)
        else:
            im.save(out, optimize=True)
    print('素材', len(jobs), '個')


def main():
    import steps
    prep_assets()
    for st in steps.STEPS:
        sid = st['id']
        if st.get('sheet'):
            sheet_locator(st['sheet'], f'{sid}-sheet.png')
        if st.get('new_asm'):
            assembly_view(st.get('installed', []), st['new_asm'], f'{sid}-asm.png', side=st.get('side', True))
        if st.get('flat'):
            parts_flat(st['flat'], f'{sid}-flat.png', row_mm=st.get('flat_row', 420))
        print('完成', sid)


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    main()

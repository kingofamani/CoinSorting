"""v2 雷切檔輸出：把 layout() 排好的板寫成 SVG（多頁草稿＋分頁）、預覽 PNG、零件清單與報告。

用法
----
    from laser_v2 import export
    res = export.export(sheets, parts, results, out_root)   # out_root 預設 repo 根目錄
    res['draft_svg'], res['out_dir'], res['qa']             # 草稿路徑、分頁資料夾、qa 結果
    export.render_draft(sheets) -> str                      # 只產生草稿 SVG 字串（qa.check(sheets) 用）

輸出
----
* 草稿 SVG：<out_root>/params.OUT_SVG。Inkscape 1.x 多頁格式（照原始檔）：
  sodipodi:namedview 裡每張板一個 inkscape:page（255×355），頁面橫向排、中間留 PAGE_GAP；
  第 1 頁的大小就是 <svg> 的 width/height/viewBox，其他頁在同一個使用者座標裡往右排。
  單位 mm，座標已經套好（零件路徑上沒有 transform）。
* 圖層（inkscape:groupmode="layer"）：「原始零件」「v2 修改」「v2 新增」「註記（不切割）」，
  註記層 style="display:none"。每個零件一個 <g>：inkscape:label＝代號，另有
  data-part（代號）、data-copy（第幾份，0 起算）、data-layer、data-sheet。
  切割路徑一個子路徑一個 <path>，data-kind＝outer（外框）／hole（孔）／line（開放線，如彎曲條鋸縫），
  data-src＝原始元素 id（新零件沒有）。
* 顏色：切割 params.STROKE_CUT（黑 0.2 mm）；雕刻紅 #ff0000（保留原始雕刻元素的樣式，只套座標轉換）；
  註記綠 #008000（只在隱藏的註記層：每個零件的代號與 tags、每張板的標題與利用率）。
  文字一律用 textpath.text_to_d 轉成路徑，整份檔沒有文字元素；textpath 不能用時註記層只放
  小十字記號，並在報告裡警告。
* <out_dir>（預設 <out_root>/laser_v2/out/）：
  - sheet_合板_1.svg …：每張板一個單頁 SVG（同樣 4 個圖層）；
  - sheet_合板_1.png …：預覽圖（matplotlib；切割黑線、雕刻紅線、零件代號藍色小字，字型 params.FONT_PATH）；
  - parts.csv：代號、名稱、材質、每套數量、尺寸、所在板、layer、tags（UTF-8 含 BOM，Excel 直接開）；
  - report.md：張數與利用率、材料與採購（每套／10 套：板材＋各子系統 build() 的 bom＋極小零件切割注意）、
    實量後改哪裡（params 鍵、重跑指令、重切哪塊小樣）、各子系統 notes／warnings／checks、
    跨子系統檢查（integrate.py）、待決事項、qa 結果。
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import polylabel

from . import params, qa
from .catalog import REPO, transform_d, transform_engrave

PAGE_GAP = 30.0            # mm：草稿 SVG 頁與頁之間的間距
LAYERS = (('original', 'layer-orig', '原始零件'),
          ('modified', 'layer-mod', 'v2 修改'),
          ('new', 'layer-new', 'v2 新增'))
NOTE_LAYER = ('layer-note', '註記（不切割）')
NOTE_FILL = f'fill:{params.NOTE_COLOR};stroke:none'
NOTE_LINE = f'fill:none;stroke:{params.NOTE_COLOR};stroke-width:0.2'
ID_SIZE = (1.5, 5.0)       # 註記代號字高範圍（mm，依零件大小）
TAG_SIZE = 1.8             # 註記 tags 字高
TAG_WRAP = 32              # 註記 tags 每行最多幾個字（太長的 tag 折行，免得跨到別的零件或別頁）
TITLE_SIZE = 4.0
PNG_DPI = 120
LABEL_COLOR = '#1f4fbf'    # 預覽圖代號顏色
SUBSYS_NAME = {'crosstrack': 'S5／S10／S50 滑升式感測座（mods_crosstrack）',
               's1': 'S1 卡匣，方案 A（mods_s1）',
               'ebox': '電子盒＋TM1637 正面窗（ebox）'}
LAYER_ZH = {k: z for k, _, z in LAYERS}

# 交接 2026-10-02 第三之一節「仍待使用者決定」：v2 草稿一律照規格預設值產生
PENDING_DEFAULTS = (
    '待決：S1 前臂黏 3 片導流帽 S1-H、PCB 用 1 mm 泡棉膠墊高（照預設：要用，S1-H 已排進板；泡棉膠另購）',
    '待決：模組固定方式（照預設：M3 尼龍螺絲＋講師預黏螺帽）',
    '待決：#13R 右牆牆頂高度 V30 或 V38（照預設：V{S1_WALL_TOP_V:g}，params.S1_WALL_TOP_V）',
    '待決：裝／拆 S50 前要先抽出 10、50 元抽屜（照預設：寫進老師組裝說明）',
    '待決：#5 間隔條只剩 2 支榫（照預設：接受，試切時確認）',
    '待決：電源開關要買哪一款免焊線組（不影響雷切檔）',
    '待決：試切若硬幣卡在模組 PCB 翼上，是否把 S5/S10/S50 改成分離式紅外線對射（照預設：維持槽型光耦）',
)

try:                                   # textpath 由別的模組提供；不能用時降級（報告會警告）
    from .textpath import text_to_d as _text_to_d
    _TEXTPATH_ERR = None
except Exception as _e:                # noqa: BLE001
    _text_to_d = None
    _TEXTPATH_ERR = f'{type(_e).__name__}: {_e}'


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def _attr(s) -> str:
    return escape(str(s), {'"': '&quot;'})


def _sid(s: str) -> str:
    s = str(s).replace('#', 'p')
    s = re.sub(r'[^A-Za-z0-9_.-]', '_', s)
    return s if re.match(r'[A-Za-z_]', s) else '_' + s


def _f(v: float) -> str:
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


MAT_CODE = {'合板': 'ply', '壓克力': 'acr'}


def _sheet_key(sheet) -> str:
    return f'{sheet.material}{sheet.no}'


def _sheet_sid(sheet) -> str:
    return _sid(MAT_CODE.get(sheet.material, sheet.material)) + str(sheet.no)


def _translate(dx, dy=0.0):
    return np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1.0]])


_KIND_CACHE: dict[tuple, list[str]] = {}


def cut_kinds(part) -> list[str]:
    """每個切割子路徑是外框（outer）、孔（hole）還是開放線（line）：封閉線中面積最大的是外框。"""
    closed = list(getattr(part, 'cut_closed', []) or [])
    key = (tuple(part.cut_d), tuple(closed))
    if key in _KIND_CACHE:
        return _KIND_CACHE[key]
    areas = []
    for i, d in enumerate(part.cut_d):
        subs = qa.sample_d(d, step=0.5)
        c = closed[i] if len(closed) == len(part.cut_d) else bool(subs and subs[0][1])
        a = abs(Polygon(subs[0][0]).area) if (c and subs and len(subs[0][0]) >= 4) else -1.0
        areas.append(a)
    k_outer = int(np.argmax(areas)) if areas and max(areas) > 0 else -1
    kinds = ['outer' if i == k_outer else ('hole' if a >= 0 else 'line') for i, a in enumerate(areas)]
    _KIND_CACHE[key] = kinds
    return kinds


_ID_RE = re.compile(r'\sid="[^"]*"')


def _engrave_elem(e: str, M, eid: str) -> str:
    s = transform_engrave(e, M)
    s = _ID_RE.sub('', s)
    return re.sub(r'^(\s*<\w+)', lambda m: f'{m.group(1)} id="{eid}"', s, count=1)


def _cut_style() -> str:
    return params.STROKE_CUT


# ---------------------------------------------------------------------------
# 零件 → SVG 片段
# ---------------------------------------------------------------------------
def _part_group(pl, sheet, dx: float, gid: str) -> str:
    """一個 Placement 的 <g>（座標已套 M 與頁偏移 dx）。"""
    p = pl.part
    M = _translate(dx) @ pl.M
    layer = getattr(p, 'layer', 'original')
    lines = [f'<g id="{gid}" inkscape:label="{_attr(pl.label)}" data-part="{_attr(p.id)}" '
             f'data-copy="{pl.copy}" data-layer="{_attr(layer)}" data-sheet="{_attr(_sheet_key(sheet))}">']
    kinds = cut_kinds(p)
    srcs = list(getattr(p, 'cut_src', []) or [])
    for i, d in enumerate(p.cut_d):
        src = f' data-src="{_attr(srcs[i])}"' if i < len(srcs) and srcs[i] else ''
        lines.append(f'  <path id="{gid}-c{i}" d="{transform_d(d, M)}" style="{_cut_style()}" '
                     f'data-kind="{kinds[i]}"{src}/>')
    for i, e in enumerate(p.engrave):
        lines.append('  ' + _engrave_elem(e, M, f'{gid}-e{i}'))
    lines.append('</g>')
    return '\n'.join(lines)


def _label_point(g):
    """放代號的位置：外形內離邊最遠的點（polylabel）與該距離。"""
    if isinstance(g, MultiPolygon):
        g = max(g.geoms, key=lambda q: q.area)
    try:
        c = polylabel(g, tolerance=0.2)
    except Exception:                                  # noqa: BLE001
        c = g.representative_point()
    return c.x, c.y, g.boundary.distance(c)


def _text_paths(text: str, x: float, y: float, size: float, anchor: str = 'middle') -> str | None:
    if _text_to_d is None or not text.strip():
        return None
    try:
        d = _text_to_d(text, x, y, size, 0.0, anchor)
    except Exception:                                  # noqa: BLE001
        return None
    return d or None


def _wrap(text: str, n: int = TAG_WRAP) -> list[str]:
    """把一行字折成每行 ≤ n 字，盡量在標點或空白後斷行。"""
    out, cur = [], ''
    for ch in text:
        cur += ch
        if len(cur) >= n:
            cut = max(cur.rfind(c) for c in '；，、）) ')
            if cut >= n // 2:
                out.append(cur[:cut + 1].rstrip())
                cur = cur[cut + 1:].lstrip()
            else:
                out.append(cur)
                cur = ''
    if cur.strip():
        out.append(cur)
    return out or [text]


def _note_group(pl, sheet, dx: float, gid: str, warn: list) -> str:
    p = pl.part
    g = pl.geom
    x, y, r = _label_point(g)
    x += dx
    size = max(ID_SIZE[0], min(ID_SIZE[1], 0.9 * r))
    out = [f'<g id="{gid}" inkscape:label="註記 {_attr(pl.label)}" data-part="{_attr(p.id)}" '
           f'data-copy="{pl.copy}" data-sheet="{_attr(_sheet_key(sheet))}">']
    texts = [(pl.label, size)]
    name = getattr(p, 'name', '') or ''
    if name and name != p.id:
        texts.append((name, TAG_SIZE))
    for t in getattr(p, 'tags', []) or []:
        texts.extend((ln, TAG_SIZE) for ln in _wrap(str(t)))
    yy = y + 0.35 * size
    k = 0
    for t, sz in texts:
        d = _text_paths(t, x, yy, sz)
        if d is None:
            if _text_to_d is not None and t.strip():
                warn.append(f'註記文字轉路徑失敗：{t!r}（{p.id}）')
            if k == 0:   # 至少放一個十字記號
                c = 1.5
                out.append(f'  <path id="{gid}-x" d="M {_f(x - c)},{_f(y)} L {_f(x + c)},{_f(y)} '
                           f'M {_f(x)},{_f(y - c)} L {_f(x)},{_f(y + c)}" style="{NOTE_LINE}"/>')
        else:
            out.append(f'  <path id="{gid}-t{k}" d="{d}" style="{NOTE_FILL}"/>')
        yy += sz * 1.25 if k else size * 0.45 + TAG_SIZE * 1.2
        k += 1
    out.append('</g>')
    return '\n'.join(out)


def _sheet_title(sheet, n_same: int) -> str:
    return (f'{sheet.material} 第 {sheet.no}/{n_same} 張　{len(sheet.items)} 件　'
            f'利用率 {sheet.util * 100:.1f}%　{sheet.w:g}×{sheet.h:g} mm')


def _title_group(sheet, n_same: int, dx: float) -> str:
    d = _text_paths(_sheet_title(sheet, n_same), dx + params.SHEET_MARGIN + 1, params.SHEET_MARGIN + TITLE_SIZE,
                    TITLE_SIZE, anchor='start')
    gid = f'note-title-{_sheet_sid(sheet)}'
    body = f'\n  <path id="{gid}-t" d="{d}" style="{NOTE_FILL}"/>' if d else ''
    return f'<g id="{gid}" inkscape:label="註記 {_attr(sheet.title)}" data-sheet="{_attr(_sheet_key(sheet))}">{body}\n</g>'


def _svg_doc(pages, bodies: dict, notes: list[str], comment: str) -> str:
    """pages：[(label, x)]；bodies：layer code → [片段]；notes：註記層片段。"""
    W, H = params.SHEET
    page_xml = '\n'.join(
        f'    <inkscape:page x="{_f(x)}" y="0" width="{_f(W)}" height="{_f(H)}" id="page{k + 1}" '
        f'inkscape:label="{_attr(lbl)}" margin="0" bleed="0" />' for k, (lbl, x) in enumerate(pages)) \
        if len(pages) > 1 else ''
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
           f'<!-- {comment} -->',
           f'<svg width="{_f(W)}mm" height="{_f(H)}mm" viewBox="0 0 {_f(W)} {_f(H)}" version="1.1" id="svg1"',
           '   xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"',
           '   xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"',
           '   xmlns="http://www.w3.org/2000/svg"',
           '   xmlns:svg="http://www.w3.org/2000/svg">',
           '  <sodipodi:namedview id="namedview1" pagecolor="#ffffff" bordercolor="#000000" borderopacity="0.25"',
           '     inkscape:showpageshadow="2" inkscape:pageopacity="0.0" inkscape:pagecheckerboard="0"',
           '     inkscape:deskcolor="#d1d1d1" inkscape:document-units="mm" showgrid="false"',
           '     inkscape:current-layer="layer-orig">']
    if page_xml:
        out.append(page_xml)
    out.append('  </sodipodi:namedview>')
    for code, lid, label in LAYERS:
        out.append(f'  <g inkscape:groupmode="layer" id="{lid}" inkscape:label="{label}">')
        out.extend('    ' + ln for frag in bodies.get(code, []) for ln in frag.split('\n'))
        out.append('  </g>')
    lid, label = NOTE_LAYER
    out.append(f'  <g inkscape:groupmode="layer" id="{lid}" inkscape:label="{label}" style="display:none">')
    out.extend('    ' + ln for frag in notes for ln in frag.split('\n'))
    out.append('  </g>')
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def _render(sheets, page_x: list[float], comment: str, warn: list, count: dict | None = None) -> str:
    bodies: dict[str, list[str]] = {}
    notes: list[str] = []
    if count is None:
        count = {}
        for s in sheets:
            count[s.material] = count.get(s.material, 0) + 1
    for s, dx in zip(sheets, page_x):
        sk = _sheet_sid(s)
        notes.append(_title_group(s, count[s.material], dx))
        for pl in s.items:
            gid = f'{sk}-{_sid(pl.part.id)}-{pl.copy}'
            layer = getattr(pl.part, 'layer', 'original')
            if layer not in LAYER_ZH:
                raise ValueError(f'{pl.part.id} 的 layer={layer!r} 不是 original/modified/new')
            bodies.setdefault(layer, []).append(_part_group(pl, s, dx, gid))
            notes.append(_note_group(pl, s, dx, f'note-{gid}', warn))
    pages = [(s.title, dx) for s, dx in zip(sheets, page_x)]
    return _svg_doc(pages, bodies, notes, comment)


def page_offsets(sheets) -> list[float]:
    W = params.SHEET[0]
    return [k * (W + PAGE_GAP) for k in range(len(sheets))]


COMMENT = ('分幣機 v2 雷切檔（laser_v2.build_v2 產生；改 laser_v2/params.py 後重跑，請勿手改）。'
           '黑 0.2 mm＝切割、紅＝雕刻、綠＝註記（隱藏圖層，不切割）')


def render_draft(sheets, warn: list | None = None) -> str:
    """多頁草稿 SVG 字串。"""
    return _render(sheets, page_offsets(sheets), COMMENT, warn if warn is not None else [])


def render_sheet(sheet, n_same: int | None = None, warn: list | None = None) -> str:
    """單張板的 SVG 字串（座標 0～255、0～355）。n_same：同材質共幾張（標題用）。"""
    return _render([sheet], [0.0], COMMENT + f'　{sheet.title}', warn if warn is not None else [],
                   {sheet.material: n_same or sheet.no})


# ---------------------------------------------------------------------------
# 預覽 PNG
# ---------------------------------------------------------------------------
def preview_png(sheet, path: Path, n_same: int):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.collections import LineCollection
    fp = font_manager.FontProperties(fname=params.FONT_PATH)
    W, H = sheet.w, sheet.h
    fig = plt.figure(figsize=(W / 25.4, (H + 12) / 25.4), dpi=PNG_DPI)
    ax = fig.add_axes([0, 0, 1, H / (H + 12)])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.set_aspect('equal')
    ax.axis('off')
    m = params.SHEET_MARGIN
    ax.add_patch(plt.Rectangle((0, 0), W, H, fill=False, ec='#888888', lw=0.8))
    ax.add_patch(plt.Rectangle((m, m), W - 2 * m, H - 2 * m, fill=False, ec='#cccccc', lw=0.5, ls='--'))
    cut_segs, eng_segs = [], []
    pt_per_mm = 72 / 25.4
    for pl in sheet.items:
        p = pl.part
        A = pl.M
        for d in p.cut_d:
            for pts, _ in qa.sample_d(d, step=0.4):
                cut_segs.append(pts @ A[:2, :2].T + A[:2, 2])
        for e in p.engrave:
            mm = re.search(r'\bd="([^"]*)"', e)
            if not mm:
                continue
            for pts, _ in qa.sample_d(mm.group(1), step=0.4):
                eng_segs.append(pts @ A[:2, :2].T + A[:2, 2])
    ax.add_collection(LineCollection(eng_segs, colors='#ff0000', linewidths=0.35))
    ax.add_collection(LineCollection(cut_segs, colors='#000000', linewidths=0.45))
    for pl in sheet.items:
        x, y, r = _label_point(pl.geom)
        sz = max(1.6, min(3.2, 0.8 * r))
        half = 0.32 * sz * len(pl.label)          # 大約半個字串寬（mm），讓字不要超出板邊
        x = min(max(x, half + 1), W - half - 1)
        ax.text(x, y, pl.label, fontproperties=fp, fontsize=sz * pt_per_mm, color=LABEL_COLOR,
                ha='center', va='center', zorder=5)
    fig.text(0.01, 1 - 6 / (H + 12), _sheet_title(sheet, n_same), fontproperties=fp,
             fontsize=4.2 * pt_per_mm, va='center')
    fig.savefig(path, dpi=PNG_DPI, facecolor='white')
    plt.close(fig)


# ---------------------------------------------------------------------------
# parts.csv
# ---------------------------------------------------------------------------
def _natkey(pid: str):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', pid)]


def _part_order(p):
    layer_rank = {'original': 0, 'modified': 0, 'new': 1}.get(getattr(p, 'layer', 'original'), 2)
    return (layer_rank, _natkey(p.id))


def write_csv(sheets, parts, path: Path):
    where: dict[str, dict[str, int]] = {}
    for s in sheets:
        for pl in s.items:
            w = where.setdefault(pl.part.id, {})
            w[_sheet_key(s)] = w.get(_sheet_key(s), 0) + 1
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(['代號', '名稱', '材質', '每套數量', '尺寸(mm)', '所在板', 'layer', 'tags'])
        for p in sorted(parts, key=_part_order):
            x0, y0, x1, y1 = p.geom.bounds
            w = where.get(p.id, {})
            loc = '、'.join(f'{k}' + (f'×{n}' if n > 1 else '') for k, n in w.items())
            wr.writerow([p.id, getattr(p, 'name', '') or p.id, p.material, int(getattr(p, 'qty', 1) or 1),
                         f'{x1 - x0:.1f}×{y1 - y0:.1f}', loc, getattr(p, 'layer', 'original'),
                         '；'.join(str(t) for t in (getattr(p, 'tags', []) or []))])


# ---------------------------------------------------------------------------
# report.md
# ---------------------------------------------------------------------------
def _md(s) -> str:
    """Markdown 表格內文：跳脫 |、< >（避免「<text>」被當成 HTML 標籤吃掉），換行改空白。"""
    return str(s).replace('|', '\\|').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ')


def _fmt(v) -> str:
    if isinstance(v, float):
        return f'{v:.3f}'.rstrip('0').rstrip('.')
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(_fmt(x) for x in v) + ']'
    if isinstance(v, dict):
        return '{' + ', '.join(f'{k}: {_fmt(x)}' for k, x in v.items()) + '}'
    if v is None:
        return ''
    return str(v)


def _pending(results) -> list[str]:
    out = [s.format(S1_WALL_TOP_V=params.S1_WALL_TOP_V) for s in PENDING_DEFAULTS]
    for key, r in results.items():
        for s in r.get('pending', []) or []:
            out.append(f'[{key}] {s}')
        for s in r.get('notes', []) or []:
            if isinstance(s, str) and s.startswith('待決'):
                out.append(f'[{key}] {s}')
    return out


BOM_SPARE = '備品（不在切割檔）'
BOM_CATS = ('電子', '五金', '耗材')
SETS = 10                  # 研習一場的套數（report 的合計欄）
SMALL_PART = 10.0          # mm：外包兩邊都小於這個的零件列為「極小零件」（一般蜂巢台格 6～10 mm）
TINY_AREA = 20.0           # mm²：淨面積小於這個的幾乎一定會掉進蜂巢


def _qty_txt(q, unit, per=1):
    if q is None:
        return unit
    v = q * per
    v = int(v) if abs(v - round(v)) < 1e-9 else round(v, 1)
    return f'{v} {unit}'


def _material_section(sheets, parts, results) -> list[str]:
    """report.md「三、材料與採購（每套／10 套）」：板材＋各子系統 build() 的 bom（INTERFACE.md）＋極小零件切割注意。"""
    L = [f'## 三、材料與採購（每套／{SETS} 套）\n']
    W, H = params.SHEET
    m, g = params.SHEET_MARGIN, params.PART_GAP
    L.append('板材張數依這份草稿的排版；五金、電子、耗材由各子系統 build() 的 bom 彙整（依目前 params）。'
             '「誰用」：講師預組＝研習前講師做好；老師現場＝研習時老師自己裝。價格不在雷切檔範圍。\n')
    L.append(f'**板材（雷切，{W:g}×{H:g} 可切範圍）**\n')
    L.append(f'| 材料 | 每套 | {SETS} 套 | 說明 |')
    L.append('|---|---|---|---|')
    by = {}
    for s in sheets:
        by.setdefault(s.material, []).append(s)
    for mat, ss in by.items():
        util = '、'.join(f'第 {s.no} 張 {s.util * 100:.0f}%' for s in ss)
        n = len(ss)
        tot = f'{n * SETS} 張'
        note = f'厚 {params.T_ACRYLIC if mat == "壓克力" else params.T_PLY:g} mm；利用率 {util}'
        if n == 1 and ss[0].util < 0.35:          # 用很少的材料：估計 10 套合排
            ex, ey = ss[0].extent
            bw, bh = ex - m, ey - m
            fit = max((int((W - 2 * m + g) // (a + g)) * int((H - 2 * m + g) // (b + g)))
                      for a, b in ((bw, bh), (bh, bw)))
            if fit > 1:
                tot += f'（{SETS} 套合排約 {-(-SETS // fit)} 張，粗估：每套零件 {bw:.0f}×{bh:.0f} 一塊，一張放 {fit} 塊）'
        L.append(f'| {mat} | {n} 張 | {tot} | {_md(note)} |')
    L.append('| 試切小樣 | — | — | 另計，見 trial_report.md（spec 建議 MDF、合板各切一次） |')
    L.append('')
    rows = []
    for key in ('crosstrack', 's1', 'ebox'):
        for r in (results.get(key) or {}).get('bom', []) or []:
            rows.append(dict(r, key=key))
    for k in results:
        if k not in ('crosstrack', 's1', 'ebox'):
            rows += [dict(r, key=k) for r in results[k].get('bom', []) or []]
    if not rows:
        L.append('（這次沒有子系統的採購清單。）\n')
    else:
        L.append('**電子、五金、耗材**\n')
        L.append(f'| 類別 | 品項 | 每套 | {SETS} 套 | 誰用 | 說明 | 出處 |')
        L.append('|---|---|---|---|---|---|---|')
        for cat in BOM_CATS:
            for r in [r for r in rows if r['cat'] == cat]:
                L.append(f'| {cat} | {_md(r["item"])} | {_qty_txt(r.get("qty"), r.get("unit", ""))} | '
                         f'{_md(r.get("per10") or _qty_txt(r.get("qty"), r.get("unit", ""), SETS))} | {_md(r.get("who", ""))} | '
                         f'{_md(r.get("note", ""))} | {_md(r.get("src") or r["key"])} |')
        nmod = sum(r['qty'] for r in rows if r['cat'] == '電子' and '光耦模組' in r['item'] and r.get('qty'))
        if nmod:
            L.append(f'\n槽型光耦模組合計每套 {nmod:g} 個、{SETS} 套 {nmod * SETS:g} 個（另見下表備用）。')
        L.append('')
        sp = [r for r in rows if r['cat'] == BOM_SPARE]
        if sp:
            L.append('**備品（spec 建議；目前都不在切割檔，要不要排進切割檔請使用者決定）**\n')
            L.append(f'| 品項 | 每套 | {SETS} 套 | 說明 | 出處 |')
            L.append('|---|---|---|---|---|')
            for r in sp:
                per = '—' if r.get('qty') is None else _qty_txt(r['qty'], r.get('unit', ''))
                L.append(f'| {_md(r["item"])} | {per} | {_md(r.get("per10") or _qty_txt(r.get("qty"), r.get("unit", ""), SETS))} | '
                         f'{_md(r.get("note", ""))} | {_md(r.get("src") or r["key"])} |')
            L.append('')
    # 極小零件（v2 新零件；原始零件以前就這樣切，只列出來比較）
    small, orig_small = [], []
    for p in parts:
        x0, y0, x1, y1 = p.geom.bounds
        if max(x1 - x0, y1 - y0) < SMALL_PART:
            (small if getattr(p, 'layer', 'original') == 'new' else orig_small).append((p.geom.area, p, x1 - x0, y1 - y0))
    if small:
        small.sort(key=lambda t: t[0])
        orig_small.sort(key=lambda t: t[0])
        L.append('**切割注意：極小零件**\n')
        ref = ''
        if orig_small:
            a0, _, w0, h0 = orig_small[0]
            ref = (f'原始檔最小的切割件是 {"、".join(p.id for a, p, w, h in orig_small if abs(a - a0) < 1)} '
                   f'{w0:.0f}×{h0:.0f}（{a0:.0f} mm²），以前也沒加連接橋；')
        L.append(f'- v2 新零件裡外包兩邊都小於 {SMALL_PART:g} mm 的：' + '、'.join(
            f'{p.id} {w:.1f}×{h:.1f}（{a:.0f} mm²，×{int(getattr(p, "qty", 1) or 1)}）' for a, p, w, h in small)
                 + f'。{ref}一般雷切蜂巢台格子 6～10 mm。')
        tiny = [p.id for a, p, w, h in small if a < TINY_AREA]
        if tiny:
            L.append(f'- {"、".join(tiny)} 小於 {TINY_AREA:g} mm²，切完幾乎一定會掉進蜂巢或集塵盤（3 mm 厚的零件卡在自己的切口裡'
                     '最多只翹約 3°，不會撞噴嘴，主要是會掉、會丟）。')
        L.append('- 切這一張前在板底貼一層紙膠帶，或墊一張犧牲板；切完先清點這幾種的數量，再檢查蜂巢底下與集塵盤。')
        L.append('- 這些都是講師預組時才用（插銷黏 C1、導流帽黏前臂、填塊黏背蓋、防拔鍵選用），掉了可以撿回或重切，'
                 '不影響老師現場組裝；備品見上表。不建議自己加微連接：插銷是 3.0 方塊要壓進 2.9 孔，連接點留下的凸點會影響配合。'
                 '要不要多切備品、要不要做小件框或微連接，請依雷切機台面（蜂巢台或刀條台、格子大小）決定。')
        L.append('- 試切小樣也有同樣的小件（PIN、S1-H、S1-P、TA-PIN、EB-K），處理方式相同。\n')
    return L


def _measure_section() -> list[str]:
    """report.md「四、實量後改哪裡、怎麼重跑」：量什麼 → params.py 的哪個鍵 → 重跑 → 重切哪一塊小樣。"""
    keys = lambda d: '、'.join(d)
    L = ['## 四、實量後改哪裡、怎麼重跑\n',
         '全部只改 `laser_v2/params.py`（各字典的鍵都已列在檔裡，註解寫了意義），不必改各子系統檔。\n',
         '| 量什麼 | 改 params.py 的哪裡 | 單位與注意 | 會變的切割 | 重切哪一塊試切小樣 |',
         '|---|---|---|---|---|',
         f'| 合板實際厚度（游標卡尺量幾處取平均） | `T_PLY`（目前 {params.T_PLY:g}） | mm；所有榫槽、掛勾槽、支架槽跟著變 | '
         '全部新切割 | TA、TB 全部 |',
         f'| 槽型光耦模組（crosstrack spec d-1、s1 spec d-4 的 Go／No-Go 清單） | `MODULE`：{keys(params.MODULE)} | '
         "mm；wing 填 'up'／'down'／'center'（排針朝自己、兩臂朝上時 PCB 長邊在右＝'up'）；comp_h（翼上最高零件）"
         '>2.3 時窄段定位壁會太矮（crosstrack 檢查會不過） | #24／#26 窗與光孔、隔板缺口、P1／C1、#13R 牆槽、#37 卡匣窗、S1 卡匣 | '
         'TA-#24、TA-#26、TA-#5、TA-#6、P1／C1、TB 全部 |',
         f'| TM1637 顯示器 | `TM1637`：{keys(params.TM1637)} | mm；**hole_dx／hole_dy 是半距**（孔中心離 PCB 中心）：'
         '量到孔距 38×20 要填 19、10；沒有固定孔就 use_screws=False（#24 不切 M2 孔，改熱熔膠）；只改 pcb_w／pcb_h 不改孔距時，'
         'ebox 檢查「M2 孔在 TM1637 PCB 上」會不過 | #24 顯示窗與 M2 孔、#26 L 形缺口、#5 前上角 | TA-#24、TA-#26、TA-#5 |',
         f'| ESP32 擴展板＋開發板 | `ESP32_BOARD`：{keys(params.ESP32_BOARD)} | mm；4 個 M3 孔離板邊要相等（hole_inset）；'
         'USB／DC 在 +U 端（右牆那側）是寫死的，實品相反要先問 | EB-B 孔、EB-WR 服務窗、盒底 | 電子盒 EB-* |',
         f'| 9V 電池 | `BATTERY_9V`：{keys(params.BATTERY_9V)} | mm；口袋取 max(實測, 標準 48.5×26.5×17.5)，實品較小不縮 | '
         '電子盒電池帶 | 電子盒 EB-* |',
         '',
         '重跑（在 repo 根目錄）：`.venv/Scripts/python.exe -B -m laser_v2.build_v2`（約 95 秒；草稿、分頁 SVG、本報告、'
         '試切小樣一起更新；只要草稿加 `--no-trial`）。改完先看「六、各子系統」的警告與「七、跨子系統檢查」，'
         '全部通過再切；先切試切小樣照 trial_report.md 驗收，再切整台。\n']
    return L


def _cross_section(cross: dict | None) -> list[str]:
    """report.md「七、跨子系統檢查」：integrate.check()／check_layout() 的結果。"""
    L = ['## 七、跨子系統檢查（laser_v2/integrate.py）\n']
    if not cross or not cross.get('rows'):
        L.append('（這次沒有執行跨子系統檢查。）\n')
        return L
    from .integrate import SEC_TITLE
    rows = cross['rows']
    bad = [r for r in rows if r['ok'] is False]
    n_ok = sum(1 for r in rows if r['ok'] is True)
    n_info = sum(1 for r in rows if r['ok'] is None)
    L.append(f'共 {len(rows)} 項：通過 {n_ok}、未通過 {len(bad)}、資訊 {n_info}。'
             "座標：#24/#26/#37 用組裝座標 (U,V)，間隔條與櫃側板用 (W',V)（frames.py）。\n")
    eb = cross.get('ebox')
    if eb:
        L.append(f'- 電子盒改用 {"、".join(eb.get("others", []))} 的實際結果重跑（ebox.build(cat, others=…)，即 ebox.recheck）：'
                 f'檢查 {eb["n_checks"] - eb["n_fail"]}/{eb["n_checks"]} 通過、警告 {len(eb.get("warnings", []))} 則；'
                 f'edits 和名目 json 版{"相同" if eb.get("same_edits") else "不同（Logo 方案或切割有變）"}，草稿用重跑後的結果。')
    for m in cross.get('engrave_fix') or []:
        L.append(f'- #24 雕刻依 crosstrack spec b-6 用最終切割重算：{_md(m)}')
    iss = cross.get('issues') or []
    L.append('- 兩個子系統在同一零件上的修改區域相交或 < 1.5 mm：' + ('沒有。' if not iss else f'{len(iss)} 處：'))
    L.extend(f'  - {_md(x)}' for x in iss)
    if bad:
        L.append('\n**未通過**\n')
        L.extend(f'- [{r["sec"]}] {_md(r["name"])}：{_md(_fmt(r["value"]))}（期望 {_md(_fmt(r["expected"]))}）'
                 + (f'；{_md(r["note"])}' if r.get('note') else '') for r in bad)
    L.append('')
    secs = []
    for r in rows:
        if r['sec'] not in secs:
            secs.append(r['sec'])
    for sec in secs:
        rs = [r for r in rows if r['sec'] == sec]
        nb = sum(1 for r in rs if r['ok'] is False)
        L.append(f'**{SEC_TITLE.get(sec, sec)}**（{len(rs)} 項' + (f'，未通過 {nb}' if nb else '') + '）\n')
        L.append('| 項目 | 結果 | 值 | 期望 | 說明 |')
        L.append('|---|---|---|---|---|')
        for r in rs:
            flag = 'OK' if r['ok'] else ('資訊' if r['ok'] is None else '**未通過**')
            L.append(f'| {_md(r["name"])} | {flag} | {_md(_fmt(r["value"]))} | {_md(_fmt(r["expected"]))} | {_md(r.get("note", "") or "")} |')
        L.append('')
    return L


def write_report(path: Path, sheets, parts, results, qa_rows, qa_sheet_rows, files, warn, mode: str,
                 cross: dict | None = None):
    L = []
    W, H = params.SHEET
    by = {}
    for s in sheets:
        by[s.material] = by.get(s.material, 0) + 1
    L.append('# 分幣機 v2 雷切草稿：產生報告\n')
    L.append(f'由 `python -m laser_v2.build_v2{" --only-original" if mode == "only-original" else ""}` 產生'
             f'（{"只排原始零件，測試用" if mode == "only-original" else "完整流程"}）。'
             '模組實量後改 `laser_v2/params.py` 重跑即可更新'
             + ('（量什麼、改哪個鍵、重跑指令見第四節；採購與備品見第三節）。\n' if mode != 'only-original' else '。\n'))

    L.append('## 一、輸出檔\n')
    L.append(f'- 草稿（多頁，Inkscape 1.x 開）：`{files["draft_rel"]}`，{len(sheets)} 頁橫向排列、頁距 {PAGE_GAP:g} mm。')
    L.append(f'- 分頁 SVG／預覽 PNG：`{files["out_rel"]}/sheet_<材質>_<n>.svg／.png`；零件清單 `parts.csv`。')
    L.append('- 圖層：「原始零件」「v2 修改」「v2 新增」「註記（不切割）」（註記層預設隱藏）。')
    L.append(f'- 顏色：黑 {qa.CUT_COLOR} {qa.CUT_WIDTH:g} mm＝切割；紅 {qa.ENGRAVE_COLOR}＝雕刻；'
             f'綠 {qa.NOTE_COLOR}＝註記（隱藏，不切割）。全部文字都已轉成路徑。\n')

    L.append('## 二、張數與利用率\n')
    L.append(f'板 {W:g}×{H:g} mm，零件離板邊 ≥ {params.SHEET_MARGIN:g} mm、零件之間 ≥ {params.PART_GAP:g} mm'
             '（真實外形距離）。利用率＝零件淨面積（外框減孔）÷ 板面積。\n')
    L.append('| 板 | 件數 | 利用率 | 外框面積比 | 排到（x, y） | 排法／備註 |')
    L.append('|---|---:|---:|---:|---|---|')
    for s in sheets:
        ex, ey = s.extent
        L.append(f'| {s.title} | {len(s.items)} | {s.util * 100:.1f}% | {s.outer_area / s.area * 100:.1f}% | '
                 f'{ex:.0f}, {ey:.0f} | {_md("；".join(s.notes))} |')
    L.append('\n合計：' + '、'.join(f'{m} {n} 張' for m, n in by.items()) + '（交接估計合板 3～4 張）。')
    L.append('彎曲條（開放鋸縫很多的零件，例如 #27）只轉 0／180 度，保持原始檔的木紋方向。\n')

    if mode != 'only-original':
        L.extend(_material_section(sheets, parts, results))
        L.extend(_measure_section())

    L.append('## 五、零件\n')
    cnt = {}
    n_items = 0
    for p in parts:
        lay = getattr(p, 'layer', 'original')
        q = int(getattr(p, 'qty', 1) or 1)
        cnt[lay] = cnt.get(lay, 0) + q
        n_items += q
    L.append(f'共 {len(parts)} 種、{n_items} 件：' + '、'.join(f'{LAYER_ZH.get(k, k)} {v} 件' for k, v in cnt.items()) + '。\n')
    touched = [p for p in sorted(parts, key=_part_order) if getattr(p, 'layer', 'original') != 'original'
               or (getattr(p, 'tags', None))]
    if touched:
        L.append('| 代號 | 名稱 | 圖層 | 數量 | 尺寸 | tags |')
        L.append('|---|---|---|---:|---|---|')
        for p in touched:
            x0, y0, x1, y1 = p.geom.bounds
            L.append(f'| {_md(p.id)} | {_md(getattr(p, "name", "") or p.id)} | {LAYER_ZH.get(p.layer, p.layer)} | '
                     f'{int(getattr(p, "qty", 1) or 1)} | {x1 - x0:.1f}×{y1 - y0:.1f} | '
                     f'{_md("；".join(str(t) for t in (getattr(p, "tags", []) or [])))} |')
        L.append('')

    L.append('## 六、各子系統\n')
    if not results:
        L.append('（這次沒有執行子系統。）\n')
    keys = [k for k in ('crosstrack', 's1', 'ebox') if k in results] + [k for k in results if k not in SUBSYS_NAME]
    for key in keys:
        r = results[key]
        L.append(f'### {SUBSYS_NAME.get(key, key)}\n')
        L.append(f'edits {len(r.get("edits", []))} 項、新零件 {len(r.get("new_parts", []))} 種'
                 + (f'、改代號 {_fmt(r["renames"])}' if r.get('renames') else '')
                 + (f'、同板群組 {_fmt(r["groups"])}' if r.get('groups') else '') + '。\n')
        if r.get('warnings'):
            L.append('**警告**\n')
            L.extend(f'- {_md(w)}' for w in r['warnings'])
            L.append('')
        if r.get('notes'):
            L.append('**說明**\n')
            L.extend(f'- {_md(n)}' for n in r['notes'])
            L.append('')
        if r.get('checks'):
            ok_n = sum(1 for c in r['checks'] if c.get('ok'))
            bad_c = [c for c in r['checks'] if not c.get('ok')]
            L.append(f'**檢查**：{ok_n}/{len(r["checks"])} 通過' + ('。' if not bad_c else '，未通過：') + '\n')
            for c in bad_c:
                L.append(f'- **未通過** {_md(c.get("name", ""))}：值 {_md(_fmt(c.get("value")))}，'
                         f'期望 {_md(_fmt(c.get("expected")))}' + (f'（{_md(c.get("note"))}）' if c.get('note') else ''))
            if bad_c:
                L.append('')
            L.append(f'<details><summary>全部 {len(r["checks"])} 項檢查</summary>\n')
            L.append('| 項目 | 結果 | 值 | 期望 | 說明 |')
            L.append('|---|---|---|---|---|')
            for c in r['checks']:
                L.append(f'| {_md(c.get("name", ""))} | {"OK" if c.get("ok") else "**未通過**"} | '
                         f'{_md(_fmt(c.get("value")))} | {_md(_fmt(c.get("expected")))} | {_md(c.get("note", "") or "")} |')
            L.append('\n</details>\n')
    cw = [f'{p.id}：{w}' for p in parts for w in (getattr(p, 'warnings', None) or [])]
    if results:
        L.append('### 合成（compose）\n')
        if cw:
            L.append('**警告**\n')
            L.extend(f'- {_md(w)}' for w in cw)
        else:
            L.append('沒有合成警告。')
        L.append('')

    L.extend(_cross_section(cross))

    L.append('## 八、待決事項（這份草稿照預設值產生）\n')
    L.extend(f'- {_md(s)}' for s in _pending(results))
    L.append('')

    L.append('## 九、QA（雷切檔衛生檢查，laser_v2/qa.py）\n')
    bad = qa.failures(qa_rows)
    nt = qa.notices(qa_rows)
    L.append(f'草稿 SVG：{len(qa_rows) - len(bad)}/{len(qa_rows)} 項通過'
             + (f'（其中 {len(nt)} 項是「注意」等級，不算失敗）' if nt else '') + '。\n')
    L.append('| 項目 | 結果 | 說明 |')
    L.append('|---|---|---|')
    for q in qa_rows:
        flag = 'OK' if q['ok'] else ('注意' if q.get('level') == 'warn' else '**未通過**')
        L.append(f'| {_md(q["name"])} | {flag} | {_md(q["detail"])} |')
    L.append('')
    if qa_sheet_rows:
        L.append('分頁 SVG：')
        for name, rows in qa_sheet_rows.items():
            b = qa.failures(rows)
            L.append(f'- `{name}`：{len(rows) - len(b)}/{len(rows)} 項通過' +
                     ('' if not b else '；未通過：' + '；'.join(f'{q["name"]}（{_md(q["detail"])}）' for q in b)))
        L.append('')

    L.append('## 十、其他\n')
    L.append(f'- #26 右側第 1 個齒孔修正（params.FIX_26_TOOTH_HOLE）：{"已套用" if params.FIX_26_TOOTH_HOLE else "未套用"}。')
    try:
        from .catalog import removed_items
        rm = removed_items()
        L.append(f'- 原始檔清理（catalog.removed_items()）共 {len(rm)} 項：' +
                 '；'.join(f'{r["kind"]} {r["id"]}' for r in rm) + '。')
    except Exception as e:                              # noqa: BLE001
        L.append(f'- 讀不到原始檔清理清單：{e}')
    if warn:
        L.append('- 輸出警告：')
        L.extend(f'  - {_md(w)}' for w in warn)
    L.append('')
    path.write_text('\n'.join(L), encoding='utf-8')


# ---------------------------------------------------------------------------
# 主程式
# ---------------------------------------------------------------------------
def export(sheets, parts, results, out_root=REPO, out_dir=None, png: bool = True, run_qa: bool = True,
           cross: dict | None = None) -> dict:
    """寫出草稿 SVG、分頁 SVG、預覽 PNG、parts.csv、report.md，並跑 qa.check。回傳各檔路徑與 qa 結果。
    cross：integrate.check() 的結果（另加 'ebox' 重查資訊），寫進 report.md 第七節。"""
    out_root = Path(out_root)
    out_dir = Path(out_dir) if out_dir else out_root / 'laser_v2' / 'out'
    out_root.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    warn: list[str] = []
    if _TEXTPATH_ERR:
        warn.append(f'textpath.py 不能用（{_TEXTPATH_ERR}）：註記層只放十字記號，沒有代號文字')

    draft = out_root / params.OUT_SVG
    draft.write_text(render_draft(sheets, warn), encoding='utf-8')

    count = {}
    for s in sheets:
        count[s.material] = count.get(s.material, 0) + 1
    sheet_svgs, pngs = [], []
    for s in sheets:
        f = out_dir / f'sheet_{s.material}_{s.no}.svg'
        f.write_text(render_sheet(s, count[s.material], warn=warn), encoding='utf-8')
        sheet_svgs.append(f)
        if png:
            g = out_dir / f'sheet_{s.material}_{s.no}.png'
            preview_png(s, g, count[s.material])
            pngs.append(g)
    csv_path = out_dir / 'parts.csv'
    write_csv(sheets, parts, csv_path)

    qa_rows, qa_sheet = [], {}
    if run_qa:
        qa_rows = qa.check(draft, parts=parts)
        for f in sheet_svgs:
            qa_sheet[f.name] = qa.check(f)
    warn = list(dict.fromkeys(warn))

    def rel(p: Path) -> str:
        try:
            return str(p.resolve().relative_to(REPO)).replace('\\', '/')
        except ValueError:
            return str(p)
    report = out_dir / 'report.md'
    mode = 'full' if results else 'only-original'
    write_report(report, sheets, parts, results, qa_rows, qa_sheet,
                 dict(draft_rel=rel(draft), out_rel=rel(out_dir)), warn, mode, cross=cross)
    all_rows = list(qa_rows)        # 草稿全部項目＋分頁 SVG 的未通過項目（注意等級不重複列）
    for name, rows in qa_sheet.items():
        all_rows += [dict(r, name=f'{name}：{r["name"]}') for r in qa.failures(rows)]
    return dict(draft_svg=draft, out_dir=out_dir, sheet_svgs=sheet_svgs, pngs=pngs, csv=csv_path,
                report=report, qa=all_rows, qa_draft=qa_rows, qa_sheets=qa_sheet, warnings=warn)

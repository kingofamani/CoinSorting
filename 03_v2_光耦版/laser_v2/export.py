"""v2 雷切檔輸出：把 layout() 排好的板寫成 SVG（多頁草稿＋分頁）、預覽 PNG、零件清單與報告。

用法
----
    from laser_v2 import export
    res = export.export(sheets, parts, results, out_root)   # out_root 預設 v2 資料夾（03_v2_光耦版）
    res['draft_svg'], res['out_dir'], res['qa']             # 草稿路徑、分頁資料夾、qa 結果
    export.render_draft(sheets) -> str                      # 只產生草稿 SVG 字串（qa.check(sheets) 用）

輸出
----
* 草稿 SVG：<out_root>/params.OUT_SVG。Inkscape 1.x 多頁格式（照原始檔）：
  sodipodi:namedview 裡每張板一個 inkscape:page（255×355），頁面橫向排、中間留 PAGE_GAP；
  第 1 頁的大小就是 <svg> 的 width/height/viewBox，其他頁在同一個使用者座標裡往右排。
  單位 mm，座標已經套好（零件路徑上沒有 transform）。
* 圖層（inkscape:groupmode="layer"）：「原始零件」「v2 修改」「v2 新增」「註記（不切割）」，
  註記層 style="display:none"。每個零件一個 <g>：inkscape:label＝代號（備品寫「代號（備品…）」），另有
  data-part（代號）、data-copy（第幾份，0 起算；≥ qty 的是備品）、data-spare（1＝備品）、data-layer、data-sheet。
  切割路徑一個子路徑一個 <path>，data-kind＝outer（外框）／hole（孔）／line（開放線，如彎曲條鋸縫），
  data-src＝原始元素 id（新零件沒有）。
* 零件群組內的寫入順序（cut_order）：雕刻 → 孔與開放線（cut_d 原順序）→ 外框最後。幾何不變；
  雷切軟體照檔案順序切時，零件到最後才和板分開。path id 仍用 cut_d／engrave 的原 index（-c<i>／-e<i>）。
* 顏色：切割 params.STROKE_CUT（黑 0.2 mm）；雕刻紅 #ff0000 0.2 mm 線（保留雕刻元素的樣式，只套座標轉換；
  原始檔和 v2 新增的雕刻都是 compose.STYLE_ENGRAVE＝fill:none;stroke:#ff0000;stroke-width:0.2，qa 會檢查）；
  註記綠 #008000（只在草稿的隱藏註記層：每個零件的代號與 tags、每張板的標題與利用率）。
  文字一律用 textpath.text_to_d 轉成路徑，整份檔沒有文字元素；textpath 不能用時註記層只放
  小十字記號，並在報告裡警告。
* <out_dir>（預設 <out_root>/laser_v2/out/）：
  - sheet_合板_1.svg …：每張板一個單頁 SVG，**上雷切機用**：只有「原始零件」「v2 修改」「v2 新增」3 個圖層，
    不含註記層（render_sheet(notes=False)；qa.check(mode='sheet') 檢查）；
  - sheet_合板_1.png …：預覽圖（matplotlib；切割黑線、雕刻紅線、零件代號藍色小字，字型 params.FONT_PATH）；
  - parts.csv：代號、名稱、材質、每套數量、備品、尺寸、所在板、備品所在板、layer、tags（UTF-8 含 BOM，Excel 直接開）；
  - report.md：上雷切機用哪個檔與雷切軟體設定、組裝提醒、張數與利用率、材料與採購（每套／10 套：板材＋
    各子系統 build() 的 bom＋備品已排進切割檔＋極小零件切割注意）、實量後改哪裡（params 鍵、重跑指令、
    重切哪塊小樣）與本次使用的 params、各子系統 notes／warnings／checks、跨子系統檢查（integrate.py）、
    待決事項、qa 結果。
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
def cut_order(part) -> list[int]:
    """零件內切割子路徑的寫入順序（cut_d 的 index）：孔與開放線（彎曲條鋸縫等）照 cut_d 原順序在前，外框最後。
    雷切軟體照檔案順序切時，零件的外框最後才切斷，內部的孔切的時候零件還固定在板上。"""
    kinds = cut_kinds(part)
    return [i for i, k in enumerate(kinds) if k != 'outer'] + [i for i, k in enumerate(kinds) if k == 'outer']


def _part_group(pl, sheet, dx: float, gid: str) -> str:
    """一個 Placement 的 <g>（座標已套 M 與頁偏移 dx）。
    寫入順序：雕刻 → 孔與開放線 → 外框（最後）；幾何和 cut_d 完全相同，只換順序。
    path id 用 cut_d／engrave 原本的 index（c<i>、e<i>），不隨順序改變。"""
    p = pl.part
    M = _translate(dx) @ pl.M
    layer = getattr(p, 'layer', 'original')
    spare = bool(getattr(pl, 'spare', False))
    lines = [f'<g id="{gid}" inkscape:label="{_attr(pl.label)}" data-part="{_attr(p.id)}" '
             f'data-copy="{pl.copy}" data-spare="{int(spare)}" data-layer="{_attr(layer)}" '
             f'data-sheet="{_attr(_sheet_key(sheet))}">']
    for i, e in enumerate(p.engrave):
        lines.append('  ' + _engrave_elem(e, M, f'{gid}-e{i}'))
    kinds = cut_kinds(p)
    srcs = list(getattr(p, 'cut_src', []) or [])
    for i in cut_order(p):
        src = f' data-src="{_attr(srcs[i])}"' if i < len(srcs) and srcs[i] else ''
        lines.append(f'  <path id="{gid}-c{i}" d="{transform_d(p.cut_d[i], M)}" style="{_cut_style()}" '
                     f'data-kind="{kinds[i]}"{src}/>')
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
           f'data-copy="{pl.copy}" data-spare="{int(bool(getattr(pl, "spare", False)))}" '
           f'data-sheet="{_attr(_sheet_key(sheet))}">']
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


def _svg_doc(pages, bodies: dict, notes: list[str] | None, comment: str) -> str:
    """pages：[(label, x)]；bodies：layer code → [片段]；notes：註記層片段（None＝整個註記層都不寫，上雷切機用）。"""
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
    if notes is not None:
        lid, label = NOTE_LAYER
        out.append(f'  <g inkscape:groupmode="layer" id="{lid}" inkscape:label="{label}" style="display:none">')
        out.extend('    ' + ln for frag in notes for ln in frag.split('\n'))
        out.append('  </g>')
    out.append('</svg>')
    return '\n'.join(out) + '\n'


def _render(sheets, page_x: list[float], comment: str, warn: list, count: dict | None = None,
            notes: bool = True) -> str:
    """notes=False：不寫註記層（上雷切機用的分頁檔）。"""
    bodies: dict[str, list[str]] = {}
    note_frags: list[str] | None = [] if notes else None
    if count is None:
        count = {}
        for s in sheets:
            count[s.material] = count.get(s.material, 0) + 1
    for s, dx in zip(sheets, page_x):
        sk = _sheet_sid(s)
        if notes:
            note_frags.append(_title_group(s, count[s.material], dx))
        for pl in s.items:
            gid = f'{sk}-{_sid(pl.part.id)}-{pl.copy}'
            layer = getattr(pl.part, 'layer', 'original')
            if layer not in LAYER_ZH:
                raise ValueError(f'{pl.part.id} 的 layer={layer!r} 不是 original/modified/new')
            bodies.setdefault(layer, []).append(_part_group(pl, s, dx, gid))
            if notes:
                note_frags.append(_note_group(pl, s, dx, f'note-{gid}', warn))
    pages = [(s.title, dx) for s, dx in zip(sheets, page_x)]
    return _svg_doc(pages, bodies, note_frags, comment)


def page_offsets(sheets) -> list[float]:
    W = params.SHEET[0]
    return [k * (W + PAGE_GAP) for k in range(len(sheets))]


COMMENT = ('分幣機 v2 雷切草稿（laser_v2.build_v2 產生；改 laser_v2/params.py 後重跑，請勿手改）。'
           '黑 0.2 mm＝切割、紅 0.2 mm 線＝雕刻（雷切軟體設線／向量雕刻，不要填色／掃描）、'
           '綠＝註記（隱藏圖層，不切割）。上雷切機請用 laser_v2/out/sheet_*.svg（不含註記）')
# 雷切軟體多半照圖層（顏色）順序跑、不照檔案順序：紅（雕刻）要排在黑（切割）前面，不然整張先切穿、小零件來不及雕刻
LAYER_ORDER_TIP = ('雷切軟體多半照圖層（顏色）順序跑、不照檔案順序：圖層清單裡把紅色（雕刻）排在黑色（切割）前面，'
                   '黑色圖層再開「先切內部（inner first）」；不然整張先切穿，小零件來不及雕刻就掉了或移位')
# 小字用 0.2 mm 線雕刻：筆畫間隙、字腔比線寬還窄的地方會燒成一團（verify2 量過「感測器線」「左牆」最明顯）
SMALL_TEXT_TIP = ('小字（em 2～3 的代號字、#37「感測器線」、EB-WL「左牆」等）用 0.2 mm 線雕刻，筆畫間隙比線寬還窄的地方會燒糊：'
                  '先切試切小樣，調紅色圖層的功率／速度，確認 C1-S10 的「S10」（em 2.1）和 TB-#37 的「感測器線」刻得清楚再切整台')
GENERATOR_MARKS = ('laser_v2.build_v2 產生', 'laser_v2.trial 產生')   # 分頁 SVG 檔頭註解；清舊檔時用來認產生器寫的檔
COMMENT_SHEET = ('分幣機 v2 雷切檔，上雷切機用（laser_v2.build_v2 產生；改 laser_v2/params.py 後重跑，請勿手改）。'
                 '黑 0.2 mm＝切割；紅 0.2 mm 線＝雕刻，紅色圖層設「線／向量雕刻（低功率切割）」，不要用填色／掃描。'
                 '不含註記。每個零件先雕刻、切孔與內部線，外框最後切。' + LAYER_ORDER_TIP)
NOTE_LAYER_RULE = '草稿含隱藏註記層；分頁 SVG（上雷切機用）不含註記層'


def render_draft(sheets, warn: list | None = None) -> str:
    """多頁草稿 SVG 字串（含隱藏的註記層）。"""
    return _render(sheets, page_offsets(sheets), COMMENT, warn if warn is not None else [])


def render_sheet(sheet, n_same: int | None = None, warn: list | None = None, notes: bool = False,
                 comment: str = COMMENT_SHEET) -> str:
    """單張板的 SVG 字串（座標 0～255、0～355）。n_same：同材質共幾張（標題用）。
    預設 notes=False：上雷切機用，不寫註記層（qa.check(..., mode='sheet') 檢查）。"""
    return _render([sheet], [0.0], comment + f'　{sheet.title}', warn if warn is not None else [],
                   {sheet.material: n_same or sheet.no}, notes=notes)


# ---------------------------------------------------------------------------
# 預覽 PNG
# ---------------------------------------------------------------------------
LABEL_GAP = 0.35           # 預覽代號字框離雕刻、切割線、其他代號的距離（mm）
LABEL_MIN = 1.6            # 零件裡放代號的最小字高（再小就改放在零件外、拉引線；和舊做法的下限相同）
LABEL_OUT_MIN = 1.3        # 零件外（引線）放不下時再試的字高


def _label_wh(text: str, sz: float) -> tuple[float, float]:
    """預覽代號字框的大約寬高（mm；微軟正黑體：全形字約 1 em、半形約 0.58 em）。"""
    w = sum(1.0 if ord(ch) > 0x2000 else 0.58 for ch in text) * sz
    return w + 0.3, 1.2 * sz


def _place_labels(sheet, eng_segs, cut_segs) -> list[tuple]:
    """預覽 PNG 的代號位置：回傳和 sheet.items 同順序的 (x, y, 字高, 引線 ((x0, y0), (x1, y1)) 或 None)。
    先放大零件。零件裡找不壓雕刻（紅字）、切割線、其他代號的位置（字可以縮到 LABEL_MIN）；放不下的（極小零件、
    備品）改放在旁邊沒有零件的空白處，拉一條引線。都找不到才退回舊做法（外形內離邊最遠的點）。只影響預覽圖。"""
    import shapely
    from shapely.geometry import LineString as _LS, box as _box
    from shapely.strtree import STRtree
    W, H = sheet.w, sheet.h
    ink = [_LS(s) for s in eng_segs if len(s) >= 2]
    cut = [_LS(s) for s in cut_segs if len(s) >= 2]
    ink_tree = STRtree(ink) if ink else None
    cut_tree = STRtree(cut) if cut else None
    def filled(g):      # 外形補滿孔：零件外的代號不放進別的零件的孔裡（看起來會像在標那個孔）
        polys = g.geoms if isinstance(g, MultiPolygon) else [g]
        return shapely.union_all([Polygon(p.exterior) for p in polys])
    part_tree = STRtree([filled(pl.geom) for pl in sheet.items])
    placed: list = []
    out: list = [None] * len(sheet.items)

    def free(boxes, inside=None):
        """boxes（shapely 陣列）裡可以用的：在板內、不壓雕刻／切割線／已放的代號；inside＝要整個在這個外形內，
        None＝要在所有零件外面。"""
        ok = shapely.contains(_box(0.5, 0.5, W - 0.5, H - 0.5), boxes)
        if inside is not None:
            shapely.prepare(inside)
            ok &= shapely.contains(inside, boxes)
        grown = shapely.buffer(boxes, LABEL_GAP, join_style='mitre')
        trees = [t for t in (ink_tree, cut_tree) if t is not None]
        if inside is None:
            trees.append(part_tree)
        for t in trees:
            hit = t.query(grown, predicate='intersects')
            if hit.size:
                ok[np.unique(hit[0])] = False
        for b in placed:
            ok &= ~shapely.intersects(grown, b)
        return ok

    order = sorted(range(len(sheet.items)), key=lambda i: -sheet.items[i].geom.area)
    for i in order:
        pl = sheet.items[i]
        g = pl.geom
        x0, y0, r = _label_point(g)
        sz0 = max(1.6, min(3.2, 0.8 * r))
        gx0, gy0, gx1, gy1 = g.bounds
        res = None
        inner = g.buffer(-0.3)
        if not inner.is_empty:                      # 1) 零件裡面（字由大到小）
            step = max(0.8, min(gx1 - gx0, gy1 - gy0) / 12, (g.area / 400) ** 0.5)
            xs, ys = np.meshgrid(np.arange(gx0, gx1 + step, step), np.arange(gy0, gy1 + step, step))
            cx, cy = np.append(x0, xs.ravel()), np.append(y0, ys.ravel())
            pref = np.hypot(cx - x0, cy - y0)       # 越靠近原本的點（離邊最遠）越好
            sz = sz0
            while res is None and sz >= LABEL_MIN - 1e-9:
                w, h = _label_wh(pl.label, sz)
                boxes = shapely.box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
                ok = free(boxes, inner)
                if ok.any():
                    k = int(np.argmin(np.where(ok, pref, np.inf)))
                    res = (float(cx[k]), float(cy[k]), sz, None)
                sz = round(sz * 0.8, 3)
        for sz in (max(LABEL_MIN, min(sz0, 2.2)), LABEL_OUT_MIN):   # 2) 零件外面的空白處，拉引線
            if res is not None:
                break
            w, h = _label_wh(pl.label, sz)
            cands = []
            for d in (0.8, 2.0, 3.5, 5.5, 8.0, 12.0, 18.0, 26.0, 36.0):
                for fx in np.linspace(-1.0, 1.0, 9):
                    cx = (gx0 + gx1) / 2 + fx * (w + gx1 - gx0) / 2
                    cands += [(cx, gy0 - d - h / 2), (cx, gy1 + d + h / 2)]
                for fy in np.linspace(-1.0, 1.0, 5):
                    cy = (gy0 + gy1) / 2 + fy * (h + gy1 - gy0) / 2
                    cands += [(gx0 - d - w / 2, cy), (gx1 + d + w / 2, cy)]
            c = np.array(cands)
            boxes = shapely.box(c[:, 0] - w / 2, c[:, 1] - h / 2, c[:, 0] + w / 2, c[:, 1] + h / 2)
            ok = free(boxes)
            if ok.any():
                idx = np.flatnonzero(ok)
                leads = shapely.shortest_line(boxes[idx], g)
                cost = shapely.length(leads)
                hit = part_tree.query(leads, predicate='intersects')    # 引線穿過別的零件要扣分
                for a_, b_ in zip(*hit):
                    if b_ != i:
                        cost[a_] += 50.0
                for b in placed:                                         # 引線壓到別的代號也扣分
                    cost += 20.0 * shapely.intersects(leads, b)
                k = int(np.argmin(cost))
                (ax, ay), (bx, by) = shapely.get_coordinates(leads[k])
                res = (float(c[idx[k], 0]), float(c[idx[k], 1]), sz, ((ax, ay), (bx, by)))
        if res is None:                             # 3) 退回舊做法
            half = 0.32 * sz0 * len(pl.label)
            res = (min(max(x0, half + 1), W - half - 1), y0, sz0, None)
        x, y, sz, _ = res
        w, h = _label_wh(pl.label, sz)
        placed.append(_box(x - w / 2, y - h / 2, x + w / 2, y + h / 2))
        out[i] = res
    return out


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
    for pl, (x, y, sz, lead) in zip(sheet.items, _place_labels(sheet, eng_segs, cut_segs)):
        if lead is not None:                      # 零件裡放不下：字放在旁邊空白處，拉一條細線到零件
            ax.plot([lead[0][0], lead[1][0]], [lead[0][1], lead[1][1]], color=LABEL_COLOR, lw=0.3, zorder=5)
        ax.text(x, y, pl.label, fontproperties=fp, fontsize=sz * pt_per_mm, color=LABEL_COLOR,
                ha='center', va='center', zorder=6)
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


CSV_HEADER = ['代號', '名稱', '材質', '每套數量', '備品', '尺寸(mm)', '所在板', '備品所在板', 'layer', 'tags']


def _where(sheets) -> dict[tuple[str, bool], dict[str, int]]:
    """(代號, 是否備品) → {板: 份數}。"""
    where: dict[tuple[str, bool], dict[str, int]] = {}
    for s in sheets:
        for pl in s.items:
            w = where.setdefault((pl.part.id, bool(getattr(pl, 'spare', False))), {})
            w[_sheet_key(s)] = w.get(_sheet_key(s), 0) + 1
    return where


def _loc(w: dict) -> str:
    return '、'.join(f'{k}' + (f'×{n}' if n > 1 else '') for k, n in w.items())


def write_csv(sheets, parts, path: Path):
    """parts.csv：每種零件一列。「每套數量」是正式件；「備品」是每套多排進切割檔的份數（實際排到的），
    「備品所在板」另列。"""
    where = _where(sheets)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        wr = csv.writer(f)
        wr.writerow(CSV_HEADER)
        for p in sorted(parts, key=_part_order):
            x0, y0, x1, y1 = p.geom.bounds
            w = where.get((p.id, False), {})
            ws = where.get((p.id, True), {})
            wr.writerow([p.id, getattr(p, 'name', '') or p.id, p.material, int(getattr(p, 'qty', 1) or 1),
                         sum(ws.values()), f'{x1 - x0:.1f}×{y1 - y0:.1f}', _loc(w), _loc(ws),
                         getattr(p, 'layer', 'original'),
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


def _sensor_pins() -> dict | None:
    """感測器線盒端插哪一欄（ebox.SENSOR_PINS）；讀不到時回傳 None（報告只寫「要插的欄位」）。"""
    try:
        from .ebox import SENSOR_PINS
        return dict(SENSOR_PINS)
    except Exception:                                  # noqa: BLE001
        return None


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
    L.extend(_spare_section(sheets, parts))
    if rows:
        sp = [r for r in rows if r['cat'] == BOM_SPARE]
        if sp:
            L.append('**其他備品（spec 建議；不在切割檔，要不要另外準備請使用者決定）**\n')
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
            f'{p.id} {w:.1f}×{h:.1f}（{a:.0f} mm²，×{int(getattr(p, "qty", 1) or 1)}'
            + (f'＋備品 {int(getattr(p, "spare", 0) or 0)}' if int(getattr(p, 'spare', 0) or 0) else '') + '）'
            for a, p, w, h in small)
                 + f'。{ref}一般雷切蜂巢台格子 6～10 mm。')
        tiny = [p.id for a, p, w, h in small if a < TINY_AREA]
        if tiny:
            L.append(f'- {"、".join(tiny)} 小於 {TINY_AREA:g} mm²，切完幾乎一定會掉進蜂巢或集塵盤（3 mm 厚的零件卡在自己的切口裡'
                     '最多只翹約 3°，不會撞噴嘴，主要是會掉、會丟）。')
        sm_ids = {p.id for _, p, _, _ in small}
        sm_sheets = [s for s in sheets if any(pl.part.id in sm_ids for pl in s.items)]
        which = '、'.join(f'{s.material}第 {s.no} 張' for s in sm_sheets) or '有極小零件的板'
        L.append(f'- 切{which}（' + ('極小零件和備品都在這張' if len(sm_sheets) == 1 else '極小零件和備品在這幾張')
                 + '）前，在板底貼一層紙膠帶，或墊一張犧牲板；切完先清點這幾種的數量（正式件＋備品），再檢查蜂巢底下與集塵盤。')
        has_sp = {p.id for s in sheets for pl in s.items if getattr(pl, 'spare', False) for p in [pl.part]}
        sp_txt = ('每套已經多排一整份備品進切割檔（見上面「備品已排進切割檔」），掉了一片直接用備品；'
                  if has_sp & {p.id for _, p, _, _ in small} else '目前沒有排備品；')
        L.append('- 這些都是講師預組時才用（插銷黏 C1、導流帽黏前臂、填塊黏背蓋、防拔鍵選用），掉了可以撿回或重切，'
                 f'不影響老師現場組裝。{sp_txt}不建議自己加微連接：插銷是 3.0 方塊要壓進 2.9 孔，連接點留下的凸點會影響配合。'
                 '要不要做小件框或微連接，請依雷切機台面（蜂巢台或刀條台、格子大小）決定。')
        L.append('- 試切小樣也有同樣的小件（PIN、S1-H、S1-P、EB-K，也一樣多排一份備品），處理方式相同。\n')
    return L


def _spare_section(sheets, parts) -> list[str]:
    """report.md 第三節「備品已排進切割檔」：每套多切的份數與所在板；放不下的另列（layout 不為備品加張數）。"""
    from .layout import unplaced_spares
    where = _where(sheets)
    want = [p for p in sorted(parts, key=_part_order) if int(getattr(p, 'spare', 0) or 0) > 0]
    un = unplaced_spares(sheets)
    if not want and not un:
        return []
    L = ['**備品已排進切割檔（使用者 2026-10-08：外包兩邊都 <10 mm 的極小零件，每套多切一整份；不增加張數）**\n',
         '| 代號 | 名稱 | 每套正式 | 每套備品（排進切割檔） | 備品所在板 |',
         '|---|---|---:|---:|---|']
    for p in want:
        ws = where.get((p.id, True), {})
        n = sum(ws.values())
        need = int(getattr(p, 'spare', 0) or 0)
        L.append(f'| {_md(p.id)} | {_md(getattr(p, "name", "") or p.id)} | {int(getattr(p, "qty", 1) or 1)} | '
                 f'{n}' + ('' if n == need else f'（應 {need}）') + f' | {_md(_loc(ws)) or "—"} |')
    L.append('')
    L.append('備品和正式件形狀完全相同，在 SVG 裡的群組標 `data-spare="1"`、代號標籤寫「（備品）」；'
             '切完和正式件分開收，講師預組時掉了或壞了直接換。')
    if un:
        L.append(f'\n**放不下的備品（沒有排；不為備品加張數，請使用者決定）**：{len(un)} 件：' + '、'.join(_md(u) for u in un))
    L.append('')
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
         f'| S1 模組前臂（靠 #26 那臂）PCB 背面焊腳的**位置**與高度（S1 卡匣用的那個模組；組裝座標 V、W\'） | '
         f'高度：`MODULE[\'back_h\']`（目前 {params.MODULE.get("back_h")}）；**位置不是 params**，量完先回報 | '
         'mm；PCB 用 1 mm 泡棉膠墊高，所以凸出 >1.0 mm 的焊點只能落在 S1-B 讓位孔內（V≤74.7）或 W\'>29，'
         '否則會頂到 S1-B 下料條或 #13R 牆、把 PCB 頂高（光束跟著偏），要改 S1-B 讓位孔／牆槽（mods_s1，改前先問）；'
         '見 laser_v2/驗證筆記/S1規格核對_2026-10-07.md 觀察 1、整機組裝核對_2026-10-07.txt | S1-B 讓位孔、S1-F、#37 卡匣窗焊點段 | '
         'TB-#37、S1-*（TB 全部） |',
         '',
         '重跑（先進到 03_v2_光耦版 資料夾）：`../.venv/Scripts/python.exe -B -m laser_v2.build_v2`（約 95 秒；草稿、分頁 SVG、本報告、'
         '試切小樣一起更新；只要草稿加 `--no-trial`）。改完先看「六、各子系統」的警告與「七、跨子系統檢查」，'
         '全部通過再切；先切試切小樣照 trial_report.md 驗收，再切整台。\n']
    L.extend(params_used_section())
    return L


PARAMS_SHOWN = ('MODULE', 'TM1637', 'ESP32_BOARD', 'BATTERY_9V', 'BEAM_H', 'LOGO_PLAN', 'S1_WALL_TOP_V', 'T_PLY',
                'C_TAB', 'C_SENSOR', 'C_HOOK')


def params_used_section(title: str = '**本次使用的參數（laser_v2/params.py，產生這份檔案時的值）**') -> list[str]:
    """report.md／trial_report.md：這次產生用的 params（實量後對照用）。"""
    L = [f'{title}\n', '| 鍵 | 值 |', '|---|---|']
    for k in PARAMS_SHOWN:
        if not hasattr(params, k):
            continue
        v = getattr(params, k)
        if isinstance(v, dict):
            txt = '、'.join(f'{kk}={_fmt(vv) if not isinstance(vv, str) else repr(vv)}' for kk, vv in v.items())
        else:
            txt = repr(v) if isinstance(v, str) else _fmt(v)
        L.append(f'| `{k}` | {_md(txt)} |')
    L.append('')
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
    sheet_names = '、'.join(f'`sheet_{s.material}_{s.no}.svg`' for s in sheets)
    L.append('# 分幣機 v2 雷切草稿：產生報告\n')
    L.append(f'由 `python -m laser_v2.build_v2{" --only-original" if mode == "only-original" else ""}` 產生'
             f'（{"只排原始零件，測試用" if mode == "only-original" else "完整流程"}）。'
             '模組實量後改 `laser_v2/params.py` 重跑即可更新'
             + ('（量什麼、改哪個鍵、重跑指令見第四節；採購與備品見第三節）。\n' if mode != 'only-original' else '。\n'))
    L.append(f'> **上雷切機用 `{files["out_rel"]}/sheet_*.svg`**（每張板一個檔：{sheet_names}；不含註記）。'
             f'黑＝切割、紅＝雕刻（全部是 {qa.CUT_WIDTH:g} mm 線，和原始檔一樣）：紅色圖層在雷切軟體設'
             '「線／向量雕刻（低功率切割）」，**不要用填色／掃描**。多頁草稿 SVG 含隱藏的註記層，是給人看的，不要直接上機。\n')

    L.append('## 一、輸出檔與上雷切機設定\n')
    L.append(f'- **上雷切機**：`{files["out_rel"]}/sheet_<材質>_<n>.svg`，每檔一張 {W:g}×{H:g} 板（{sheet_names}）。'
             '只有 3 個圖層「原始零件」「v2 修改」「v2 新增」，沒有註記層。')
    L.append(f'- 草稿（多頁，Inkscape 1.x 開，給人看）：`{files["draft_rel"]}`，{len(sheets)} 頁橫向排列、頁距 {PAGE_GAP:g} mm；'
             '圖層多一個「註記（不切割）」（預設隱藏：零件代號、修改說明、每張板標題），不要直接上機。')
    L.append(f'- 預覽 PNG：`{files["out_rel"]}/sheet_<材質>_<n>.png`；零件清單 `parts.csv`（含「備品」「備品所在板」欄）。')
    L.append('')
    L.append('| 顏色 | 是什麼 | 雷切軟體設定 |')
    L.append('|---|---|---|')
    L.append(f'| 黑 {qa.CUT_COLOR}，{qa.CUT_WIDTH:g} mm 線 | 切割（外框、孔、彎曲條鋸縫） | 切割（cut） |')
    L.append(f'| 紅 {qa.ENGRAVE_COLOR}，{qa.CUT_WIDTH:g} mm 線 | 雕刻：原始檔的字與圖案、v2 新增的代號字（外框線字）、'
             '定位框線、▲ 記號 | **線／向量雕刻（低功率切割，line）**；不要用填色／掃描（fill／scan）：'
             '開放的定位框線、▲ 是線，用填色會漏掉或亂填 |')
    L.append(f'| 綠 {qa.NOTE_COLOR} | 註記（只在草稿的隱藏圖層） | 分頁檔沒有；草稿不要上機 |')
    L.append('')
    L.append('- 零件內的順序：每個零件先寫雕刻，再寫孔與內部線（含彎曲條鋸縫），外框寫在最後。雷切軟體照檔案順序切時，'
             '零件要到最後才和板分開，不會切到一半掉下去；軟體會自己排序的話，開「先切內部（inner first）」。')
    L.append(f'- {LAYER_ORDER_TIP}。')
    L.append('- 全部文字都已轉成路徑（外框線字），檔案裡沒有文字元素。')
    if mode != 'only-original':
        L.append(f'- {SMALL_TEXT_TIP}。')
    L.append(f'- 重跑時，`{files["out_rel"]}` 裡**產生器命名**的分頁檔（`sheet_<材質>_<n>.svg`／`.png`）會被覆寫，'
             '這次沒有的那幾張會被移除（SVG 還要檔頭有產生器註解才刪）；自己手改的檔請改名（例如加「_手改」）或存到別處。')
    if mode != 'only-original':
        L.append('')
        L.append('**組裝提醒**\n')
        pins = _sensor_pins()
        L.append('- 每條感測器排線兩端貼標籤：模組端寫站名（S5／S10／S50／S1），盒端寫要插的欄位'
                 + (f'（{"、".join(f"{k}→{v}" for k, v in pins.items())}）' if pins else '')
                 + '；老師依標籤裝站、插線（#24 正面不刻站名）。採購數量見第三節。')
        guide = (results.get('crosstrack') or {}).get('station_guide')
        if guide:
            L.append(f'- {_md(guide)}。')
        L.append('- 極小零件每套多排一份備品（見第三節「備品已排進切割檔」），切完和正式件分開收。')
    L.append('')

    L.append('## 二、張數與利用率\n')
    L.append(f'板 {W:g}×{H:g} mm，零件離板邊 ≥ {params.SHEET_MARGIN:g} mm、零件之間 ≥ {params.PART_GAP:g} mm'
             '（真實外形距離）。利用率＝零件淨面積（外框減孔）÷ 板面積（含備品）。\n')
    L.append('| 板 | 件數 | 其中備品 | 利用率 | 外框面積比 | 排到（x, y） | 排法／備註 |')
    L.append('|---|---:|---:|---:|---:|---|---|')
    for s in sheets:
        ex, ey = s.extent
        L.append(f'| {s.title} | {len(s.items)} | {getattr(s, "n_spare", 0)} | {s.util * 100:.1f}% | '
                 f'{s.outer_area / s.area * 100:.1f}% | {ex:.0f}, {ey:.0f} | {_md("；".join(s.notes))} |')
    L.append('\n合計：' + '、'.join(f'{m} {n} 張' for m, n in by.items())
             + '（目標合板 3 張、壓克力 1 張；備品只塞進已經開的板，不另開板）。')
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
    n_sp = sum(int(getattr(p, 'spare', 0) or 0) for p in parts)
    L.append(f'共 {len(parts)} 種、{n_items} 件：' + '、'.join(f'{LAYER_ZH.get(k, k)} {v} 件' for k, v in cnt.items())
             + (f'；另備品 {n_sp} 件（第三節）' if n_sp else '') + '。\n')
    touched = [p for p in sorted(parts, key=_part_order) if getattr(p, 'layer', 'original') != 'original'
               or (getattr(p, 'tags', None))]
    if touched:
        L.append('| 代號 | 名稱 | 圖層 | 數量（＋備品） | 尺寸 | tags |')
        L.append('|---|---|---|---:|---|---|')
        for p in touched:
            x0, y0, x1, y1 = p.geom.bounds
            L.append(f'| {_md(p.id)} | {_md(getattr(p, "name", "") or p.id)} | {LAYER_ZH.get(p.layer, p.layer)} | '
                     f'{int(getattr(p, "qty", 1) or 1)}' + (f'＋{int(p.spare)}' if int(getattr(p, 'spare', 0) or 0) else '')
                     + f' | {x1 - x0:.1f}×{y1 - y0:.1f} | '
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
        L.append('分頁 SVG（上雷切機用；用分頁檔規則檢查：只有 3 個圖層、沒有註記層、沒有綠色）：')
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
# 清上一次的舊分頁檔（只刪產生器自己的命名）
# ---------------------------------------------------------------------------
MATERIALS = tuple(MAT_CODE)          # 產生器會用到的材質名（檔名裡的 <材質>）


def generated_name(name: str, prefix: str, materials=()) -> bool:
    """name 是不是產生器自己的分頁檔命名：<prefix>_<材質>_<n>.svg／.png（材質＝MATERIALS＋materials）。
    「sheet_合板_1 - 複製.svg」「sheet_合板_1_手改.svg」「sheet_backup.png」這類都不算。"""
    mats = sorted({*MATERIALS, *materials}, key=len, reverse=True)
    pat = rf'{re.escape(prefix)}_(?:{"|".join(re.escape(m) for m in mats)})_[1-9]\d*\.(?:svg|png)'
    return re.fullmatch(pat, name) is not None


def has_generator_mark(path: Path) -> bool:
    """SVG 檔頭（前 2 KB）有產生器註解（GENERATOR_MARKS）。"""
    try:
        with open(path, 'rb') as f:
            head = f.read(2048).decode('utf-8', errors='ignore')
    except OSError:
        return False
    return any(m in head for m in GENERATOR_MARKS)


def remove_stale_outputs(out_dir: Path, prefix: str, keep, materials=()) -> tuple[list[Path], list[Path]]:
    """移除 out_dir 裡上一次留下、這次沒有重寫的 <prefix>_<材質>_<n>.svg／.png。
    只刪產生器命名的檔；SVG 另外要檔頭有產生器註解（手改另存、被 Inkscape 改寫過的不刪）。
    回傳 (刪掉的, 檔名符合但沒有產生器註解而保留的)。使用者自己取名的複本（「- 複製」「_手改」…）完全不碰。"""
    keep = {Path(f).resolve() for f in keep}
    removed, kept = [], []
    for f in sorted(Path(out_dir).glob(f'{prefix}_*')):
        if not f.is_file() or f.resolve() in keep or not generated_name(f.name, prefix, materials):
            continue
        if f.suffix.lower() == '.svg' and not has_generator_mark(f):
            kept.append(f)
            continue
        f.unlink()
        removed.append(f)
    return removed, kept


# ---------------------------------------------------------------------------
# 主程式
# ---------------------------------------------------------------------------
def export(sheets, parts, results, out_root=REPO, out_dir=None, png: bool = True, run_qa: bool = True,
           cross: dict | None = None, notices: list[str] | None = None) -> dict:
    """寫出草稿 SVG、分頁 SVG、預覽 PNG、parts.csv、report.md，並跑 qa.check。回傳各檔路徑與 qa 結果。
    cross：integrate.check() 的結果（另加 'ebox' 重查資訊），寫進 report.md 第七節。
    notices：呼叫端要寫進 report.md「輸出警告」的提醒（例如 --no-trial 時舊試切檔還在）。"""
    out_root = Path(out_root)
    out_dir = Path(out_dir) if out_dir else out_root / 'laser_v2' / 'out'
    out_root.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    warn: list[str] = list(notices or [])
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
    # 上一次多出來的板（張數變少或 --no-png）：留著會被誤拿去切。只刪產生器自己的命名（使用者的複本、手改檔不動）
    removed, kept = remove_stale_outputs(out_dir, 'sheet', sheet_svgs + pngs, {s.material for s in sheets})
    warn += [f'移除上一次留下、這次沒有的分頁檔：{f.name}' for f in removed]
    warn += [f'{f.name} 的檔名像上一次的分頁檔，但檔頭沒有產生器註解（可能是手改過的），沒有刪；這次沒有這張板，'
             '不要拿它去切' for f in kept]
    csv_path = out_dir / 'parts.csv'
    write_csv(sheets, parts, csv_path)

    qa_rows, qa_sheet = [], {}
    if run_qa:
        qa_rows = qa.check(draft, parts=parts, mode='draft')
        for f in sheet_svgs:
            qa_sheet[f.name] = qa.check(f, mode='sheet')
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

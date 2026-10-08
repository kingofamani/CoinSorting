"""v2 雷切檔衛生檢查（QA）：直接讀輸出的 SVG 檢查，不信任產生器內部的資料。

用法
----
    from laser_v2 import qa
    rows = qa.check('分幣機雷切_光耦版_v2_草稿.svg', parts=parts)   # 或 qa.check(sheets)
    bad = qa.failures(rows)                      # 每列 dict(name, ok, detail[, level])；level='warn' 不算失敗
    python -m laser_v2.qa <svg 檔> [...]          # 命令列：印出結果，有未通過項目時 exit 1

check(src, parts=None)
    src：SVG 檔路徑（str／Path），或 layout() 的 list[Sheet]（先在記憶體裡輸出成草稿 SVG 再檢查）。
    parts：V2Part 清單（可省略）；有給就再核對「每個零件 × qty 都在、圖層對、沒有多出來的」。

檢查項目（name）
----------------
* XML 解析：檔案是合法 XML、根元素是 <svg>。
* 頁面：每頁都是 params.SHEET（255×355），多頁時用 sodipodi:namedview 裡的 inkscape:page。
* 圖層名稱：最上層剛好是 LAYERS 這 4 個 inkscape 圖層、順序相同；註記層 style="display:none"、其他層看得見；
  圖層外面沒有任何圖形。
* 沒有 <text>：整份檔沒有 text／tspan／flowRoot／textPath（文字都要先轉成路徑）。
* 顏色：切割層只有黑 #000000（線寬 0.2）＝切割、紅 #ff0000＝雕刻；註記層只有綠 #008000；
  只用 <path>（不用 rect／circle／use／image 等）。
* 零件代號：每個零件群組都有 data-part 與 inkscape:label；註記層有對應的群組；(代號, 份) 不重複；
  所有切割／雕刻路徑都在某個零件群組裡；有給 parts 時核對數量與圖層。
* 外框閉合：每個零件有一個封閉外框；其他封閉子路徑（孔）都在外框內；開放線（彎曲條鋸縫等）在外框內；
  外框與孔組成的外形是合法多邊形（不自交）。
* 雕刻在零件內：雕刻線都在所屬零件的材料上（外框內、不在孔裡）。
* 雕刻不壓切割線（注意等級 level='warn'，不算失敗）：雕刻線和同零件切割線重合 > ENGRAVE_ON_CUT 時列出。
* 無重疊重複切割線：同一條路徑不來回重切；同一零件內、不同零件之間，兩條切割線重疊長度 ≤ OVERLAP_LEN。
* 零件不超出板：每個零件完整落在一頁內，離頁邊 ≥ SHEET_MARGIN。
* 零件間距：同一頁任兩個零件（含孔，真實外形）距離 ≥ PART_GAP。

曲線用 0.2 mm 弦長取樣後用 shapely 計算（取樣誤差遠小於容許值 TOL）。
"""
from __future__ import annotations

import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union
from svgpathtools import Arc, CubicBezier, Line, QuadraticBezier, parse_path

from . import params
from .catalog import INK_NS, SODI_NS, parse_transform, transform_d

LAYERS = ('原始零件', 'v2 修改', 'v2 新增', '註記（不切割）')
LAYER_OF = {'original': '原始零件', 'modified': 'v2 修改', 'new': 'v2 新增'}
NOTE_LAYER = LAYERS[3]
CUT_COLOR = '#000000'
ENGRAVE_COLOR = params.STROKE_ENGRAVE_COLOR.lower()
NOTE_COLOR = params.NOTE_COLOR.lower()
CUT_WIDTH = 0.2
STEP = 0.2            # mm：曲線取樣弦長
TOL = 0.01            # mm：距離容許誤差
CLOSE_TOL = 1e-3      # mm：起終點距離小於此值視為封閉
OVERLAP_BUF = 0.02    # mm：兩條線距離在這以內算「疊在一起」
OVERLAP_LEN = 0.2     # mm：疊在一起超過這個長度＝重複切割
AREA_TOL = 0.05       # mm²：外形 buffer(0) 修正前後面積差在這以內＝只是微小折返（不算自交）
ENGRAVE_ON_CUT = 0.5  # mm：雕刻線和切割線重合超過這個長度 → 「注意」
TEXT_TAGS = {'text', 'tspan', 'flowRoot', 'flowPara', 'flowRegion', 'textPath'}
SHAPE_TAGS = {'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'use', 'image'}
NAMED = {'black': '#000000', 'red': '#ff0000', 'green': '#008000', '#000': '#000000', '#f00': '#ff0000'}
MAX_LIST = 8          # detail 最多列幾筆


# ---------------------------------------------------------------------------
# 取樣（export.py 的預覽圖也用這裡）
# ---------------------------------------------------------------------------
def _cubic_pts(seg, n):
    t = np.linspace(0, 1, n + 1)[:, None]
    P = np.array([[z.real, z.imag] for z in seg.bpoints()])
    return ((1 - t) ** 3) * P[0] + 3 * ((1 - t) ** 2) * t * P[1] + 3 * (1 - t) * t ** 2 * P[2] + t ** 3 * P[3]


def _quad_pts(seg, n):
    t = np.linspace(0, 1, n + 1)[:, None]
    P = np.array([[z.real, z.imag] for z in seg.bpoints()])
    return ((1 - t) ** 2) * P[0] + 2 * (1 - t) * t * P[1] + t ** 2 * P[2]


def _seg_pts(seg, step: float) -> np.ndarray:
    P = _seg_pts_raw(seg, step)
    P[0] = (seg.start.real, seg.start.imag)          # 端點用精確值（避免 Arc.point(1) 的浮點誤差）
    P[-1] = (seg.end.real, seg.end.imag)
    return P


def _seg_pts_raw(seg, step: float) -> np.ndarray:
    if isinstance(seg, Line):
        return np.array([[seg.start.real, seg.start.imag], [seg.end.real, seg.end.imag]])
    if isinstance(seg, CubicBezier):
        b = seg.bpoints()
        L = sum(abs(b[k + 1] - b[k]) for k in range(3))
        return _cubic_pts(seg, max(4, int(math.ceil(L / step))))
    if isinstance(seg, QuadraticBezier):
        b = seg.bpoints()
        L = abs(b[1] - b[0]) + abs(b[2] - b[1])
        return _quad_pts(seg, max(4, int(math.ceil(L / step))))
    if isinstance(seg, Arc):
        L = max(seg.radius.real, seg.radius.imag) * abs(math.radians(seg.delta))
        n = max(8, int(math.ceil(L / step)))
        return np.array([[z.real, z.imag] for z in (seg.point(t) for t in np.linspace(0, 1, n + 1))])
    raise TypeError(type(seg))


def sample_d(d: str, step: float = STEP) -> list[tuple[np.ndarray, bool]]:
    """SVG path d → [(取樣點 (N,2), 是否封閉)]，每個連續子路徑一筆。"""
    out = []
    p = parse_path(d)
    for sp in p.continuous_subpaths():
        segs = list(sp)
        if not segs:
            continue
        chunks = [_seg_pts(segs[0], step)]
        for s in segs[1:]:
            chunks.append(_seg_pts(s, step)[1:])
        pts = np.vstack(chunks)
        closed = abs(sp.end - sp.start) < CLOSE_TOL
        out.append((pts, closed))
    return out


# ---------------------------------------------------------------------------
# 讀 SVG
# ---------------------------------------------------------------------------
def _style(e) -> dict:
    d = {}
    for kv in (e.get('style') or '').split(';'):
        if ':' in kv:
            k, v = kv.split(':', 1)
            d[k.strip()] = v.strip()
    for k in ('stroke', 'fill', 'display', 'stroke-width', 'visibility'):
        if e.get(k) is not None and k not in d:
            d[k] = e.get(k)
    return d


def _color(v):
    if v is None:
        return None
    v = v.strip().lower()
    return NAMED.get(v, v)


@dataclass
class _Elem:
    tag: str
    layer: str | None        # 所在最上層圖層名稱（None＝不在圖層裡）
    part: tuple | None       # (data-part, data-copy, label, data-kind of group) 最近的零件群組
    stroke: str | None
    fill: str | None
    width: float | None
    d: str | None            # 已套上累積 transform 的 d（只有 path）
    kind: str | None         # data-kind（outer/hole/line）
    eid: str | None


@dataclass
class _Doc:
    pages: list = field(default_factory=list)       # [(x, y, w, h)]
    layers: list = field(default_factory=list)      # [(label, style dict)]
    elems: list = field(default_factory=list)       # list[_Elem]
    groups: list = field(default_factory=list)      # [(layer, data-part, data-copy, label, data-layer)]
    stray: list = field(default_factory=list)       # 圖層外的圖形 tag


def _local(tag: str) -> str:
    return tag.split('}')[-1]


def _parse(root) -> _Doc:
    doc = _Doc()
    if _local(root.tag) != 'svg':
        raise ValueError(f'根元素是 {root.tag}，不是 svg')
    for e in root.iter(f'{{{INK_NS}}}page'):
        doc.pages.append(tuple(float(e.get(k)) for k in ('x', 'y', 'width', 'height')))
    if not doc.pages:
        vb = root.get('viewBox')
        if vb:
            x, y, w, h = (float(v) for v in re.split(r'[\s,]+', vb.strip()))
        else:
            x, y = 0.0, 0.0
            w = float(re.sub(r'[a-z]+$', '', root.get('width', '0')))
            h = float(re.sub(r'[a-z]+$', '', root.get('height', '0')))
        doc.pages.append((x, y, w, h))
    doc.pages.sort()

    def walk(e, M, st, layer, part):
        tag = _local(e.tag)
        if tag in ('defs', 'namedview', 'metadata', 'title', 'desc') or e.tag.startswith(f'{{{SODI_NS}}}'):
            return
        if e.tag.startswith(f'{{{INK_NS}}}'):
            return
        M = M @ parse_transform(e.get('transform'))
        own = _style(e)
        st = dict(st)
        st.update({k: v for k, v in own.items() if k in ('stroke', 'fill', 'stroke-width')})
        if tag == 'g':
            if e.get(f'{{{INK_NS}}}groupmode') == 'layer' and layer is None:
                layer = e.get(f'{{{INK_NS}}}label')
                doc.layers.append((layer, own))
            if e.get('data-part') is not None:
                part = (e.get('data-part'), e.get('data-copy', '0'), e.get(f'{{{INK_NS}}}label') or '')
                doc.groups.append((layer, part[0], part[1], part[2], e.get('data-layer')))
            for c in e:
                walk(c, M, st, layer, part)
            return
        if tag in TEXT_TAGS or tag in SHAPE_TAGS or tag == 'path':
            if layer is None:
                doc.stray.append(tag)
            d = e.get('d') if tag == 'path' else None
            if d is not None and not np.allclose(M, np.eye(3)):
                d = transform_d(d, M)
            w = st.get('stroke-width')
            try:
                w = float(re.sub(r'[a-z]+$', '', w)) * math.sqrt(abs(np.linalg.det(M[:2, :2]))) if w else None
            except ValueError:
                w = None
            doc.elems.append(_Elem(tag, layer, part, _color(st.get('stroke')), _color(st.get('fill')), w,
                                   d, e.get('data-kind'), e.get('id')))
            return
        for c in e:
            walk(c, M, st, layer, part)

    for c in root:
        walk(c, np.eye(3), {}, None, None)
    return doc


# ---------------------------------------------------------------------------
# 各項檢查
# ---------------------------------------------------------------------------
def _row(name, ok, detail):
    return dict(name=name, ok=bool(ok), detail=detail)


def _lst(items) -> str:
    items = list(items)
    s = '；'.join(str(x) for x in items[:MAX_LIST])
    return s + (f'；…共 {len(items)} 筆' if len(items) > MAX_LIST else '')


def _is_cut(e: _Elem) -> bool:
    return e.stroke == CUT_COLOR


def _is_engrave(e: _Elem) -> bool:
    return e.stroke == ENGRAVE_COLOR or e.fill == ENGRAVE_COLOR


def _pkey(e: _Elem):
    return (e.layer, e.part[0], e.part[1]) if e.part else None


def _check_pages(doc: _Doc):
    W, H = params.SHEET
    bad = [f'第 {k + 1} 頁 {w:g}×{h:g}' for k, (x, y, w, h) in enumerate(doc.pages)
           if abs(w - W) > 1e-6 or abs(h - H) > 1e-6]
    over = []
    P = sorted(doc.pages)
    for a, b in zip(P, P[1:]):
        if a[0] + a[2] > b[0] - 1e-6 and not (a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]):
            over.append(f'頁 x{a[0]:g} 與 x{b[0]:g} 重疊')
    return [_row('頁面', not bad and not over,
                 f'{len(doc.pages)} 頁，每頁 {W:g}×{H:g}' if not bad and not over else _lst(bad + over))]


def _check_layers(doc: _Doc):
    labels = [l for l, _ in doc.layers]
    errs = []
    if tuple(labels) != LAYERS:
        errs.append(f'圖層是 {labels}，應為 {list(LAYERS)}')
    for l, st in doc.layers:
        hidden = st.get('display') == 'none'
        if l == NOTE_LAYER and not hidden:
            errs.append(f'「{l}」應隱藏（style="display:none"）')
        if l != NOTE_LAYER and hidden:
            errs.append(f'「{l}」被隱藏了')
    if doc.stray:
        errs.append(f'圖層外有 {len(doc.stray)} 個圖形（{_lst(Counter(doc.stray).items())}）')
    return [_row('圖層名稱', not errs, '4 個圖層名稱與順序正確，註記層隱藏' if not errs else _lst(errs))]


def _check_text(doc: _Doc, raw: str):
    n = sum(1 for e in doc.elems if e.tag in TEXT_TAGS)
    n_raw = len(re.findall(r'<(?:\w+:)?(?:text|tspan|flowRoot|textPath)\b', raw))
    return [_row('沒有 <text>', n == 0 and n_raw == 0, '沒有任何文字元素' if n == 0 and n_raw == 0
                 else f'有 {max(n, n_raw)} 個文字元素（文字要先轉成路徑）')]


def _check_colors(doc: _Doc):
    errs = []
    for e in doc.elems:
        where = f'{e.layer}/{e.part[0] if e.part else "-"}/{e.eid or e.tag}'
        if e.tag != 'path':
            if e.tag not in TEXT_TAGS:
                errs.append(f'{where}：用了 <{e.tag}>（只能用 <path>）')
            continue
        cols = {c for c in (e.stroke, e.fill) if c not in (None, 'none')}
        if e.layer == NOTE_LAYER:
            if cols - {NOTE_COLOR}:
                errs.append(f'{where}：註記層出現 {sorted(cols)}')
            continue
        if NOTE_COLOR in cols or cols - {CUT_COLOR, ENGRAVE_COLOR}:
            errs.append(f'{where}：顏色 {sorted(cols)}')
        if e.fill not in (None, 'none', ENGRAVE_COLOR):
            errs.append(f'{where}：填色 {e.fill}（切割線不可填色）')
        if e.stroke == CUT_COLOR and (e.width is None or abs(e.width - CUT_WIDTH) > 1e-6):
            errs.append(f'{where}：切割線寬 {e.width}（應為 {CUT_WIDTH}）')
        if not cols:
            errs.append(f'{where}：沒有顏色（看不見的線）')
    return [_row('顏色', not errs, f'只有切割 {CUT_COLOR}（{CUT_WIDTH} mm）、雕刻 {ENGRAVE_COLOR}、註記 {NOTE_COLOR}'
                 if not errs else _lst(errs))]


def _check_ids(doc: _Doc, parts):
    errs = []
    cut_groups = [g for g in doc.groups if g[0] != NOTE_LAYER]
    note_groups = [g for g in doc.groups if g[0] == NOTE_LAYER]
    for layer, pid, cp, label, dl in cut_groups:
        if not pid:
            errs.append(f'{layer}：有零件群組沒有 data-part')
        elif not label.startswith(pid):
            errs.append(f'{pid}：inkscape:label「{label}」不是以代號開頭')
        if dl is not None and LAYER_OF.get(dl) != layer:
            errs.append(f'{pid}：data-layer={dl} 卻放在「{layer}」')
    keys = Counter((pid, cp) for _, pid, cp, _, _ in cut_groups)
    dup = [f'{k[0]}#{k[1]}×{n}' for k, n in keys.items() if n > 1]
    if dup:
        errs.append('代號重複：' + _lst(dup))
    nkeys = Counter((pid, cp) for _, pid, cp, _, _ in note_groups)
    miss = [f'{k[0]}（第 {int(k[1]) + 1} 份）' for k in keys if k not in nkeys]
    extra = [f'{k[0]}' for k in nkeys if k not in keys]
    if miss:
        errs.append('註記層缺代號：' + _lst(miss))
    if extra:
        errs.append('註記層多出：' + _lst(extra))
    loose = [e.eid or e.tag for e in doc.elems if e.layer != NOTE_LAYER and e.part is None]
    if loose:
        errs.append(f'有 {len(loose)} 條線不屬於任何零件群組：' + _lst(loose))
    n_parts = len(keys)
    if parts is not None:
        want = Counter()
        layer_want = {}
        for p in parts:
            q = int(getattr(p, 'qty', 1) or 1)
            for c in range(q):
                want[(p.id, str(c))] += 1
            layer_want[p.id] = LAYER_OF.get(getattr(p, 'layer', 'original'))
        got = Counter(keys)
        lack = [f'{k[0]}（第 {int(k[1]) + 1} 份）' for k in want if k not in got]
        more = [f'{k[0]}（第 {int(k[1]) + 1} 份）' for k in got if k not in want]
        if lack:
            errs.append('少了零件：' + _lst(lack))
        if more:
            errs.append('多出零件：' + _lst(more))
        wrong = [f'{pid} 在「{layer}」應在「{layer_want[pid]}」' for layer, pid, _, _, _ in cut_groups
                 if pid in layer_want and layer_want[pid] != layer]
        if wrong:
            errs.append('圖層不對：' + _lst(wrong))
    by_layer = Counter(g[0] for g in cut_groups)
    det = f'{n_parts} 件（' + '、'.join(f'{l} {by_layer.get(l, 0)}' for l in LAYERS[:3]) + '），每件都有代號與註記'
    return [_row('零件代號', not errs, det if not errs else _lst(errs))], n_parts


@dataclass
class _PartGeom:
    key: tuple
    name: str
    outer: np.ndarray | None = None
    holes: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    engrave: list = field(default_factory=list)
    poly: object = None
    bbox: tuple | None = None
    subs: list = field(default_factory=list)       # [(eid, idx, pts, closed, kind)]


def _collect(doc: _Doc):
    parts: dict[tuple, _PartGeom] = {}
    for e in doc.elems:
        if e.tag != 'path' or not e.d or e.layer == NOTE_LAYER or e.part is None:
            continue
        k = _pkey(e)
        pg = parts.setdefault(k, _PartGeom(k, e.part[2] or e.part[0]))
        if _is_cut(e):
            for i, (pts, closed) in enumerate(sample_d(e.d)):
                pg.subs.append((e.eid, i, pts, closed, e.kind))
        elif _is_engrave(e):
            for pts, closed in sample_d(e.d):
                pg.engrave.append(pts)
    return parts


def _build_geoms(parts: dict):
    """每個零件：找外框（面積最大的封閉子路徑）、孔、開放線，組成 shapely 外形。回傳錯誤清單。"""
    errs, micro = [], []
    for k, pg in parts.items():
        closed = [(s, Polygon(s[2])) for s in pg.subs if s[3] and len(s[2]) >= 4]
        if not closed:
            errs.append(f'{pg.name}：沒有封閉外框')
            continue
        (outer_s, outer_p) = max(closed, key=lambda c: abs(c[1].area))
        pg.outer = outer_s[2]
        if outer_s[4] not in (None, 'outer'):
            errs.append(f'{pg.name}：面積最大的封閉線標成 {outer_s[4]}')
        shell = Polygon(outer_p.exterior)
        n_micro = len(micro)
        if not shell.is_valid:
            fixed = shell.buffer(0)
            if isinstance(fixed, MultiPolygon) or abs(fixed.area - shell.area) > AREA_TOL:
                errs.append(f'{pg.name}：外框自交（{shapely.is_valid_reason(shell)}）')
            else:
                micro.append(f'{pg.name}（{shapely.is_valid_reason(shell)}）')
            shell = fixed if isinstance(fixed, Polygon) else shell
        sh_buf = shell.buffer(0.05)
        for s, p in closed:
            if s is outer_s:
                continue
            if s[4] == 'outer':
                errs.append(f'{pg.name}：有兩條標成 outer 的封閉線')
            if not sh_buf.contains(p):
                errs.append(f'{pg.name}：封閉線 {s[0]} 不在外框內')
            pg.holes.append(s[2])
        for s in pg.subs:
            if s[3]:
                continue
            if s[4] in ('outer', 'hole'):
                errs.append(f'{pg.name}：{s[0]} 標成 {s[4]} 但沒有封閉（起終點差 '
                            f'{float(np.hypot(*(s[2][0] - s[2][-1]))):.4f} mm）')
            if len(s[2]) >= 2 and not sh_buf.contains(LineString(s[2])):
                errs.append(f'{pg.name}：開放線 {s[0]} 超出外框')
            pg.lines.append(s[2])
        poly = Polygon(outer_p.exterior, [Polygon(h).exterior for h in pg.holes])
        if not poly.is_valid:
            fixed = poly.buffer(0)
            reason = shapely.is_valid_reason(poly)
            if isinstance(fixed, MultiPolygon) or abs(fixed.area - poly.area) > AREA_TOL:
                errs.append(f'{pg.name}：外框與孔組成的外形不合法（{reason}）')
            elif len(micro) == n_micro:
                micro.append(f'{pg.name}（{reason}）')
            poly = fixed
        pg.poly = poly
        pg.bbox = shell.bounds
    return errs, micro


def _check_closed(parts: dict, errs_geom: list, micro: list):
    n_open = sum(len(pg.lines) for pg in parts.values())
    n_hole = sum(len(pg.holes) for pg in parts.values())
    ok = not errs_geom
    det = (f'{len(parts)} 個零件外框都封閉、不自交；孔 {n_hole} 個都在外框內；開放線（鋸縫等）{n_open} 條都在外框內'
           if ok else _lst(errs_geom))
    if micro:
        det += (f'。另有 {len(micro)} 處面積差 < {AREA_TOL} mm² 的微小折返（起點的次微米來回、座標四捨五入），'
                f'不影響切割：{_lst(micro)}')
    return [_row('外框閉合', ok, det)]


def _check_engrave(parts: dict):
    """雕刻要落在零件的材料上（外框內、不在孔裡）；雕刻線和切割線重合的長度另列為「注意」。"""
    errs, warn = [], []
    n = 0
    for pg in parts.values():
        if pg.poly is None:
            continue
        mat = pg.poly.buffer(0.05)
        cuts = [LineString(s[2]) for s in pg.subs if len(s[2]) >= 2]
        cut_zone = unary_union([c.buffer(OVERLAP_BUF, quad_segs=4) for c in cuts]) if cuts else None
        for pts in pg.engrave:
            n += 1
            g = LineString(pts) if len(pts) >= 2 else Point(pts[0])
            if not mat.contains(g):
                errs.append(f'{pg.name}：雕刻有 {g.difference(mat).length:.2f} mm 不在材料上（超出外框或在孔裡）')
            elif cut_zone is not None and isinstance(g, LineString):
                ov = g.intersection(cut_zone).length
                if ov > ENGRAVE_ON_CUT:
                    warn.append(f'{pg.name}：雕刻線有 {ov:.2f} mm 和切割線重合')
    rows = [_row('雕刻在零件內', not errs, f'{n} 條雕刻線都在所屬零件的材料上（外框內、不在孔裡）'
                 if not errs else _lst(errs))]
    r = _row('雕刻不壓切割線', not warn, '雕刻線沒有和切割線重合' if not warn else
             _lst(warn) + '（雷切時同一條線先雕再切，不影響成品；注意等級，不算失敗）')
    r['level'] = 'warn'
    rows.append(r)
    return rows


def _check_overlap(parts: dict):
    errs = []
    lines, owner = [], []
    for pg in parts.values():
        for eid, i, pts, closed, kind in pg.subs:
            if len(pts) < 2:
                continue
            ls = LineString(pts)
            u = unary_union(ls)
            if ls.length - u.length > OVERLAP_LEN:
                errs.append(f'{pg.name}/{eid}：同一條線來回重切 {ls.length - u.length:.2f} mm')
            lines.append(ls)
            owner.append((pg.name, eid, i))
    if lines:
        tree = shapely.STRtree(lines)
        a_idx, b_idx = tree.query(lines, predicate='dwithin', distance=OVERLAP_BUF)
        for a, b in zip(a_idx, b_idx):
            a, b = int(a), int(b)
            if b <= a:
                continue
            ov = lines[a].intersection(lines[b].buffer(OVERLAP_BUF, quad_segs=4)).length
            if ov > OVERLAP_LEN:
                same = owner[a][0] == owner[b][0]
                errs.append(f'{"同一零件" if same else "不同零件"} {owner[a][0]}/{owner[a][1]} 與 '
                            f'{owner[b][0]}/{owner[b][1]} 重疊 {ov:.2f} mm')
    return [_row('無重疊重複切割線', not errs, f'{len(lines)} 條切割線，沒有重切或兩條疊在一起'
                 if not errs else _lst(errs))]


def _page_of(bbox, pages):
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    for k, (x, y, w, h) in enumerate(pages):
        if x <= cx <= x + w and y <= cy <= y + h:
            return k
    return None


def _check_bounds(parts: dict, pages):
    m = params.SHEET_MARGIN
    errs = []
    page_of = {}
    for k, pg in parts.items():
        if pg.bbox is None:
            continue
        allpts = np.vstack([s[2] for s in pg.subs] + pg.engrave) if pg.subs else None
        x0, y0 = allpts.min(axis=0)
        x1, y1 = allpts.max(axis=0)
        pi = _page_of((x0, y0, x1, y1), pages)
        if pi is None:
            errs.append(f'{pg.name}：不在任何一頁裡')
            continue
        page_of[k] = pi
        px, py, pw, ph = pages[pi]
        d = min(x0 - px, y0 - py, px + pw - x1, py + ph - y1)
        if d < m - TOL:
            errs.append(f'{pg.name}：第 {pi + 1} 頁，離頁邊 {d:.3f} mm（應 ≥ {m}）')
    return [_row('零件不超出板', not errs, f'每個零件都在頁內、離頁邊 ≥ {m} mm' if not errs else _lst(errs))], page_of


def _check_gap(parts: dict, page_of: dict):
    gap = params.PART_GAP
    errs = []
    keys = [k for k in parts if parts[k].poly is not None]
    geoms = [parts[k].poly for k in keys]
    dmin = math.inf
    if geoms:
        tree = shapely.STRtree(geoms)
        a_idx, b_idx = tree.query(geoms, predicate='dwithin', distance=gap + 1.0)
        for a, b in zip(a_idx, b_idx):
            a, b = int(a), int(b)
            if b <= a:
                continue
            d = geoms[a].distance(geoms[b])
            dmin = min(dmin, d)
            if d < gap - TOL:
                errs.append(f'{parts[keys[a]].name} 與 {parts[keys[b]].name} 距離 {d:.3f} mm')
    det = (f'任兩零件距離 ≥ {gap} mm' + (f'（最近 {dmin:.2f} mm）' if dmin < math.inf else '')
           if not errs else _lst(errs))
    return [_row('零件間距', not errs, det)]


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------
def check(src, parts=None) -> list[dict]:
    """檢查一份 v2 雷切 SVG（檔案路徑），或 layout() 的 list[Sheet]（先輸出成記憶體中的草稿 SVG）。"""
    if isinstance(src, (str, Path)):
        raw = Path(src).read_text(encoding='utf-8')
    elif isinstance(src, list):
        from . import export as _export          # 延後匯入，避免 export ↔ qa 循環
        raw = _export.render_draft(src)
    else:
        raise TypeError(f'qa.check 不支援 {type(src).__name__}')
    try:
        root = ET.fromstring(raw.encode('utf-8'))
        doc = _parse(root)
    except Exception as e:                       # noqa: BLE001
        return [_row('XML 解析', False, f'{type(e).__name__}: {e}')]
    rows = [_row('XML 解析', True, f'{len(doc.elems)} 個圖形元素')]
    rows += _check_pages(doc)
    rows += _check_layers(doc)
    rows += _check_text(doc, raw)
    rows += _check_colors(doc)
    r, _ = _check_ids(doc, parts)
    rows += r
    pgs = _collect(doc)
    errs, micro = _build_geoms(pgs)
    rows += _check_closed(pgs, errs, micro)
    rows += _check_engrave(pgs)
    rows += _check_overlap(pgs)
    r, page_of = _check_bounds(pgs, doc.pages)
    rows += r
    rows += _check_gap(pgs, page_of)
    return rows


def failures(rows) -> list[dict]:
    """真正的失敗（不含 level='warn' 的注意項目）。"""
    return [r for r in rows if not r['ok'] and r.get('level') != 'warn']


def notices(rows) -> list[dict]:
    """注意項目（level='warn' 且未通過）。"""
    return [r for r in rows if not r['ok'] and r.get('level') == 'warn']


def _flag(r) -> str:
    return 'OK' if r['ok'] else ('注意' if r.get('level') == 'warn' else '未通過')


def report(rows) -> str:
    return '\n'.join(f'{_flag(r)}　{r["name"]}：{r["detail"]}' for r in rows)


if __name__ == '__main__':
    bad_any = False
    for f in sys.argv[1:]:
        rows = check(f)
        print(f'== {f}')
        print(report(rows))
        bad_any |= bool(failures(rows))
    sys.exit(1 if bad_any else 0)

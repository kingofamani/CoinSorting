"""跨子系統整合檢查：三個子系統（crosstrack／s1／ebox）與 #26 齒孔修正合成後，檢查彼此有沒有打架。

build_v2 的流程
---------------
1. 三個子系統各自 build(cat)。
2. ebox_integrated()：ebox 改用 mods_s1、mods_crosstrack 的「實際結果」重跑
   （ebox.build(cat, others=…)，等於 ebox 要求的 recheck），取代名目 json 的結果。
3. compose → check(cat, results, parts) → layout → check_layout(sheets, parts)。
4. 結果（rows）寫進 report.md「跨子系統檢查」一節；未通過的項目 build_v2 會印出來。

檢查項目（交接 2026-10-02 第二節第 3 點＋整合任務）
-------------------------------------------------
A. #37：S1（卡匣窗、B1 槽、M3 孔、背蓋 S1-F）與電子盒（掛勾槽、頂邊缺口、感測器線孔）的開孔
   彼此距離；感測器線孔不壓 S1 背蓋／B1 槽／S1 禁區／掛勾槽；#37 單一連通；新切割附近沒有細料。
B. 電子盒 S1 禁區：用 mods_s1 的實際 keepout 重跑 ebox，列出禁區來源與相關檢查。
C. #5：crosstrack 缺口＋電子盒前上角合成後仍 1 塊、剩下的榫、最小料寬。
D. #26：三個子系統＋齒孔修正；四個分幣開口逐字不變、新切割離開口的距離、單一連通。
E. #24：雕刻「1」「5」、Logo 移位後離最終所有切割 ≥1.5、彼此不重疊；不符合時列出（搬移規則見
   crosstrack spec b-6：最小平移搜尋，成本 |ΔV|+3|ΔU|）。
F. 任兩個子系統（含原始檔修正）在同一零件上的修改區域相交或 < 1.5 mm：全部列出並註明處理。
G. 原始子路徑：沒被修改的零件 cut_d／engrave 和原始檔逐字相同；被修改零件裡沒被碰到的子路徑也逐字相同；
   被重生、刪掉或消失的子路徑都要有對應的 edit（離 edit < 0.05 mm）。
H. #26 分幣開口、#24 斜槽（軌道）和原始檔逐點相同（≤0.001 mm）。
K. 榫槽配對：間隔條 #5/#6/#7、櫃側板 #13R/#21 在 #24、#26、#37 板厚內的截面都落在孔或缺口裡
   （干涉不比原始檔大），新切出的槽都有榫（沒有空槽）。
W. 新切割造成的細料：每個新／重生的切割環到同零件其他環的距離 ≥ MIN_WEB（比原始檔近才算），
   以及形態學 opening 找出 edit 附近寬度 < MIN_WEB 的料。
L. 排版：S1-B 與 #13R 同一張、ebox 群組同一張、張數在交接估計內、備品（V2Part.spare）都排進現有的板。
S. S1 最前實體到 S5 實際最深 W'（mods_s1 的 s5_gap 用規格常數 10.0，這裡改用 mods_crosstrack 實際值）。

每一筆檢查是 dict(sec, name, ok, value, expected, note)；ok=None 表示「資訊」（不算通過或失敗）。
座標：#24/#26/#37 用組裝座標 (U,V)，間隔條與櫃側板用 (W',V)（見 frames.py）。
"""
from __future__ import annotations

import copy
import math
import re

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box
from shapely.ops import nearest_points, unary_union

from . import catalog as _cat
from . import frames as F
from . import params
from . import qa
from . import textpath

MIN_WEB = 2.0          # mm：新切割留下的料寬下限（三份 spec 的 min_web）
SENSOR_WEB = 2.5       # mm：#37 感測器線孔到其他切割（ebox spec e：≥2.5）
NEAR = 1.5             # mm：兩個子系統的修改區域比這個近就要列出
ENGRAVE_CLEAR = 1.5    # mm：#24 雕刻離切割（crosstrack spec b-6）
LOGO_CLEAR = 3.0       # mm：Logo 離其他切割／雕刻（ebox spec 規則 4）
LOGO_HOLE_CLEAR = 2.0  # mm：Logo 菱形孔離其他孔
POINT_TOL = 0.001      # mm：分幣開口、軌道逐點比對容許
TOUCH = 0.05           # mm：「碰到」（同 compose.TOUCH）
TENON_TOL = 0.05       # mm：榫槽干涉比原始檔多這麼多才算變差
STEP = 0.1             # mm：取樣弦長
STUB_AREA = 3.0        # mm²：opening 找到的細料若只有一邊接本體且比這小，算「小凸齒」（只記錄，不算細料）

COIN_OPENINGS = {'path131[4]': '1 元開口', 'path131[8]': '5 元開口', 'path131[10]': '10 元開口',
                 'path131[13]': '50 元開口'}
RAIL_SRC = {'#24': {'rect2[1]': '#24 斜槽（軌道）'}}
ENG_NAMES = {'text16-7-2': '「1」', 'text11-4-1': '「5」', 'path1-5-9': 'Logo',
             'text1-6-4': '「10」', 'text2-1-3': '「50」'}
LOGO_HOLES = ('path10[0]', 'path11[0]', 'path12[0]', 'path15[0]', 'path16[0]', 'path17[0]',
              'path4[0]', 'path5[0]', 'path8[0]')
SYS_ZH = {'crosstrack': 'crosstrack', 's1': 's1', 'ebox': 'ebox', 'fix26': '原始檔修正'}
PLATES = {'#24': F.W24, '#26': F.W26, '#37': (F.W37_IN, F.W37_IN + F.T_BOARD)}
U_PLANE_PARTS = ('#5', '#6', '#7', '#13', '#21')   # 板面平行 (W',V) 的零件（frame 用原代號）


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def _row(sec, name, ok, value='', expected='', note=''):
    if isinstance(value, (float, np.floating)):
        value = round(float(value), 3)
    return dict(sec=sec, name=name, ok=None if ok is None else bool(ok), value=value, expected=expected, note=note)


def _r(v, n=2):
    return None if v is None else round(float(v), n)


def _polys(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g] if g.area > 0 else []
    out = []
    for h in getattr(g, 'geoms', []):
        out.extend(_polys(h))
    return out


def _ring_lines(d: str, step: float = STEP) -> list[LineString]:
    return [LineString(np.vstack([p, p[:1]]) if c else p) for p, c in qa.sample_d(d, step) if len(p) >= 2]


def _ring_poly(d: str, step: float = STEP) -> Polygon:
    subs = qa.sample_d(d, step)
    g = Polygon(subs[0][0])
    return g if g.is_valid else g.buffer(0)


def _elem_d(elem: str) -> str | None:
    m = re.search(r'\bd="([^"]*)"', elem)
    return m.group(1) if m else None


def _engrave_region(elem: str):
    """雕刻元素的範圍：線雕＝線往外 0.1（線寬一半）；填色文字＝字形區域。"""
    d = _elem_d(elem)
    if not d:
        return Polygon()
    if re.search(r'fill:\s*#ff0000', elem, re.I) and 'stroke:none' in elem.replace(' ', ''):
        pieces = [Polygon(p) for p, c in qa.sample_d(d, 0.05) if len(p) >= 3]
        return unary_union([q if q.is_valid else q.buffer(0) for q in pieces])
    return unary_union(_ring_lines(d, 0.1)).buffer(0.1)


def _plane_axes(pid: str):
    """零件板面平行的兩個組裝軸。"""
    ax = F.frame(pid).plane()[0]
    return {'W': ('U', 'V'), 'U': ('W', 'V'), 'V': ('U', 'W')}[ax]


def _to_asm(pid: str, g, axes=None):
    """頁座標幾何 → 組裝座標兩軸（板面上面 z=0）。"""
    axes = axes or _plane_axes(pid)
    return F.frame(pid).geom_asm(g, 0.0, axes)


def _fmt_box(g, axes=('U', 'V')) -> str:
    b = g.bounds
    a0 = "W'" if axes[0] == 'W' else axes[0]
    a1 = "W'" if axes[1] == 'W' else axes[1]
    return f'{a0}{b[0]:.1f}～{b[2]:.1f}×{a1}{b[1]:.1f}～{b[3]:.1f}'


def _where(pid: str, a, b) -> str:
    """兩個幾何最近點的組裝座標（報告用）。"""
    p, q = nearest_points(a, b)
    axes = _plane_axes(pid)
    x = F.frame(pid).to_asm((p.x + q.x) / 2, (p.y + q.y) / 2, 0.0)
    return ' '.join(f"{'W' + chr(39) if k == 'W' else k}{x[F.AX[k]]:.1f}" for k in axes)


def _opening(G, r: float):
    return G.buffer(-r, join_style=2, mitre_limit=10).buffer(r, join_style=2, mitre_limit=10)


def _orig_id(p) -> str:
    return getattr(p, 'orig_id', None) or p.id


def _by_orig(parts) -> dict:
    return {_orig_id(p): p for p in parts if getattr(p, 'layer', 'original') != 'new'}


# ---------------------------------------------------------------------------
# ebox 用實際結果重查（ebox 的 request）
# ---------------------------------------------------------------------------
def _edit_sig(r: dict) -> list:
    return [(e['op'], e['part'], e.get('src'), round(float(e.get('dx', 0) or 0), 6), round(float(e.get('dy', 0) or 0), 6),
             e['geom'].wkt if 'geom' in e else e.get('d', e.get('text'))) for e in r['edits']]


def ebox_integrated(cat: dict, results: dict) -> tuple[dict, dict]:
    """ebox 改用 mods_s1、mods_crosstrack 的實際結果（S1 keepout、#37／#26／#24 新切割、雕刻搬移、
    隔板 v2 外形）重跑。回傳 (新的 ebox 結果, 資訊 dict(same_edits, n_checks, n_fail, warnings))。

    same_edits=False 表示 Logo 方案等因其他子系統的實際結果而改變，build_v2 一律改用新的結果。"""
    from . import ebox
    others = {k: results[k] for k in ('s1', 'crosstrack') if k in results}
    r2 = ebox.build(copy.deepcopy(cat), others=others)
    old = results.get('ebox')
    same = old is not None and _edit_sig(r2) == _edit_sig(old)
    bad = [c for c in r2.get('checks', []) if not c.get('ok')]
    info = dict(same_edits=same, n_checks=len(r2.get('checks', [])), n_fail=len(bad),
                warnings=list(r2.get('warnings', [])), others=sorted(others))
    return r2, info


# ---------------------------------------------------------------------------
# edit 區域（頁座標）
# ---------------------------------------------------------------------------
def edit_regions(cat0: dict, cat: dict, results: dict) -> list[dict]:
    """每個 edit 實際改到的區域（頁座標）。kind：'cut'（挖／新孔）、'add'（加料）、'fill'（刪孔補實）、
    'engrave'（雕刻新位置）。#26 齒孔修正以 sys='fix26' 列入。"""
    rev = {}
    for r in results.values():
        for old, new in (r.get('renames') or {}).items():
            rev[new] = old
    out = []
    for sysn, r in results.items():
        for e in r['edits']:
            pid = rev.get(e['part'], e['part'])
            p = cat[pid]
            outer = Polygon(p.geom.exterior)
            op = e['op']
            tag = e.get('tag') or op
            if op == 'subtract':
                g, kind = e['geom'].intersection(outer.buffer(0.01)), 'cut'
            elif op == 'union':
                g, kind = e['geom'], 'add'
            elif op == 'delete_cut':
                g, kind = _ring_poly(p.cut_d[p.cut_src.index(e['src'])]), 'fill'
            elif op == 'translate_cut':
                g0 = _ring_poly(p.cut_d[p.cut_src.index(e['src'])])
                g, kind = affinity.translate(g0, e['dx'], e['dy']), 'cut'
            elif op == 'move_engrave':
                el = p.engrave[p.engrave_src.index(e['src'])]
                g, kind = affinity.translate(_engrave_region(el), e['dx'], e['dy']), 'engrave'
            elif op == 'add_engrave':
                g, kind = unary_union(_ring_lines(e['d'], 0.1)).buffer(0.1), 'engrave'
            elif op == 'add_engrave_text':
                d = textpath.text_to_d(str(e['text']), float(e['x']), float(e['y']), float(e['size']),
                                       float(e.get('angle', 0) or 0), e.get('anchor', 'start') or 'start')
                g, kind = _engrave_region(f'<path d="{d}" style="fill:#ff0000;stroke:none"/>'), 'engrave'
            elif op == 'delete_engrave':
                continue
            else:
                raise ValueError(f'未知 op {op}')
            out.append(dict(sys=sysn, part=pid, op=op, tag=tag, kind=kind, geom=g, src=e.get('src')))
    if params.FIX_26_TOOTH_HOLE:
        i = cat0['#26'].cut_src.index('path131[19]')
        old = _ring_poly(cat0['#26'].cut_d[i])
        new = _ring_poly(cat['#26'].cut_d[i])
        out.append(dict(sys='fix26', part='#26', op='translate_cut', tag='#26 齒孔修正', kind='cut',
                        geom=unary_union([old, new]), src='path131[19]'))
    return out


# ---------------------------------------------------------------------------
# 主檢查
# ---------------------------------------------------------------------------
def check(cat: dict, results: dict, parts: list, cat0: dict | None = None) -> dict:
    """跨子系統檢查。cat＝build_v2 傳給子系統的零件（已修 #26 齒孔）；cat0＝原始檔（None 時重新載入）。
    回傳 dict(rows=[...], issues=[...]）：issues 是 F 節列出的相交／太近項目（含處理說明）。"""
    cat0 = cat0 if cat0 is not None else _cat.load_catalog()
    _CT_CACHE.clear()                      # params 可能改過：crosstrack 模型每次 check 重算一次
    regs = edit_regions(cat0, cat, results)
    P = _by_orig(parts)
    rows: list[dict] = []
    issues: list[str] = []
    rows += _sec_A(cat0, cat, results, P, regs)
    rows += _sec_B(results)
    rows += _sec_C(cat0, P, regs)
    rows += _sec_D(cat0, P, regs)
    covers = front_covers(cat)
    rows += _sec_E(cat0, P, covers)
    rf, issues = _sec_F(regs, P)
    rows += rf
    rows += _sec_G(cat0, cat, P, regs, parts)
    rows += _sec_H(cat0, P)
    rows += _sec_K(cat0, P)
    rows += _sec_W(cat0, P, regs)
    rows += _sec_S(cat, results)
    return dict(rows=rows, issues=issues)


# ---- A. #37 ---------------------------------------------------------------
def _sec_A(cat0, cat, results, P, regs) -> list[dict]:
    rows = []
    p37 = P['#37']
    feats = [(r['sys'], r['tag'], _to_asm('#37', r['geom'])) for r in regs if r['part'] == '#37' and r['kind'] == 'cut']
    sensor = [f for f in feats if '感測器線孔' in f[1]]
    rows.append(_row('A', '#37 單一連通', p37.geom.geom_type == 'Polygon', p37.geom.geom_type, 'Polygon'))
    if len(sensor) != 1:
        rows.append(_row('A', '#37 感測器線孔', False, f'找到 {len(sensor)} 個', '恰 1 個（由 ebox 開）'))
        return rows
    sh = sensor[0][2]
    rows.append(_row('A', '#37 感測器線孔位置', None, _fmt_box(sh), 'U88～100×V40～46（交接定案）'))
    # S1 背蓋 S1-F、S1 禁區
    try:
        from . import mods_s1
        g = mods_s1.geometry(copy.deepcopy(cat), mods_s1.module_params(), mods_s1.design_params())
        s1f = g['S1F_UV']
        d = sh.distance(s1f)
        rows.append(_row('A', '感測器線孔 ↔ S1 背蓋 S1-F（貼 #37 外面）', d >= MIN_WEB, d, f'≥{MIN_WEB:g}（不被背蓋蓋住）',
                         f'背蓋 {_fmt_box(s1f)}'))
    except Exception as e:                      # noqa: BLE001
        rows.append(_row('A', '感測器線孔 ↔ S1 背蓋 S1-F', False, f'算不出來：{e}', ''))
    k = (results.get('s1') or {}).get('keepout')
    if k:
        kz = box(k['U'][0], k['V'][0], k['U'][1], k['V'][1])
        d = sh.distance(kz)
        rows.append(_row('A', '感測器線孔 ↔ S1 禁區（mods_s1 keepout 的 U×V 投影）', d > 0, d, '>0（不在禁區內）',
                         f"禁區 U{k['U'][0]}～{k['U'][1]}×V{k['V'][0]}～{k['V'][1]}×W'{k['W'][0]}～{k['W'][1]}"))
    # 和 #37 上其他所有新切割、原始孔、外框的距離
    for sysn, tag, gg in feats:
        if gg is sh:
            continue
        d = sh.distance(gg)
        rows.append(_row('A', f'感測器線孔 ↔ {SYS_ZH[sysn]}「{tag}」', d >= SENSOR_WEB, d, f'≥{SENSOR_WEB:g}（ebox spec）'))
    holes0 = [(_s, _to_asm('#37', _ring_poly(d))) for d, _s in zip(cat0['#37'].cut_d[1:], cat0['#37'].cut_src[1:])]
    dh = min((sh.distance(h), s) for s, h in holes0)
    rows.append(_row('A', f'感測器線孔 ↔ 最近的原始孔 {dh[1]}', dh[0] >= SENSOR_WEB, dh[0], f'≥{SENSOR_WEB:g}'))
    outer0 = _to_asm('#37', Polygon(cat0['#37'].geom.exterior))
    d = sh.distance(outer0.exterior)
    rows.append(_row('A', '感測器線孔 ↔ #37 外框', d >= SENSOR_WEB, d, f'≥{SENSOR_WEB:g}'))
    # 不同子系統的 #37 新切割兩兩距離
    best = None
    for i, (sa, ta, ga) in enumerate(feats):
        for sb, tb, gb in feats[i + 1:]:
            if sa == sb:
                continue
            d = ga.distance(gb)
            if best is None or d < best[0]:
                best = (d, f'{SYS_ZH[sa]}「{ta}」↔ {SYS_ZH[sb]}「{tb}」')
    if best:
        rows.append(_row('A', f'#37 上 S1 與電子盒新切割的最近距離（{best[1]}）', best[0] >= MIN_WEB, best[0], f'≥{MIN_WEB:g}'))
    # 所有新切割（不分子系統）兩兩、以及對原始孔／外框（缺口除外）的最近距離＝最細的料
    best = None
    for i, (sa, ta, ga) in enumerate(feats):
        for sb, tb, gb in feats[i + 1:]:
            d = ga.distance(gb)
            if best is None or d < best[0]:
                best = (d, f'{SYS_ZH[sa]}「{ta}」↔ {SYS_ZH[sb]}「{tb}」')
        for s0, h in holes0:
            d = ga.distance(h)
            if best is None or d < best[0]:
                best = (d, f'{SYS_ZH[sa]}「{ta}」↔ 原始孔 {s0}')
        if ga.distance(outer0.exterior) > 1e-6:          # 缺口本來就碰外框，不算
            d = ga.distance(outer0.exterior)
            if best is None or d < best[0]:
                best = (d, f'{SYS_ZH[sa]}「{ta}」↔ #37 外框')
    if best:
        rows.append(_row('A', f'#37 所有新切割之間、對原始孔與外框的最細料（{best[1]}）', best[0] >= MIN_WEB, best[0],
                         f'≥{MIN_WEB:g}'))
    # 電子盒盒體 ↔ S1 背蓋（#37 外面，(U,V) 投影）
    eb = results.get('ebox') or {}
    m = re.search(r'電子盒掛在 #37 背面 U([\d.]+)～([\d.]+)、V([\d.]+)～([\d.]+)', ' '.join(eb.get('notes', [])))
    if m and k:
        bx = box(float(m.group(1)), float(m.group(3)), float(m.group(2)), float(m.group(4)))
        d = bx.distance(box(k['U'][0], k['V'][0], k['U'][1], k['V'][1]))
        rows.append(_row('A', '電子盒盒體 ↔ S1 禁區（U×V 投影）', d >= 1.0, d, '≥1（ebox 左牆下限＝禁區右界＋1）',
                         f'盒 U{m.group(1)}～{m.group(2)}×V{m.group(3)}～{m.group(4)}'))
    return rows


# ---- B. 電子盒 S1 禁區 -----------------------------------------------------
def _sec_B(results) -> list[dict]:
    rows = []
    eb = results.get('ebox') or {}
    s1 = results.get('s1') or {}
    k = s1.get('keepout')
    src = [n for n in eb.get('notes', []) if 'S1 禁區' in n]
    used = re.search(r'U([\d.]+)～([\d.]+) × V([\d.]+)～([\d.]+) × W\'([\d.]+)～([\d.]+)', src[0]) if src else None
    if k and used:
        got = tuple(float(x) for x in used.groups())
        want = (k['U'][0], k['U'][1], k['V'][0], k['V'][1], k['W'][0], k['W'][1])
        same = all(abs(a - b) < 0.011 for a, b in zip(got, want))
        rows.append(_row('B', 'ebox 用的 S1 禁區＝mods_s1 實際 keepout', same,
                         'U{}～{}×V{}～{}×W\'{}～{}'.format(*got), 'U{}～{}×V{}～{}×W\'{}～{}'.format(*want),
                         '資料來源：' + ('mods_s1.build() 實際結果' if 'mods_s1.build() 實際結果' in src[0] else '名目 json')))
    else:
        rows.append(_row('B', 'ebox 用的 S1 禁區', False, '找不到', 'mods_s1 keepout'))
    for c in eb.get('checks', []):
        nm = str(c.get('name', ''))
        if (re.search(r'S1(?![0-9])', nm) and ('禁區' in nm or '#37' in nm or 'S1 在' in nm)) or '禁區' in nm:
            rows.append(_row('B', f'ebox 檢查：{nm}', c.get('ok'), c.get('value'), c.get('expected'), c.get('note', '') or ''))
    n = len(eb.get('checks', []))
    bad = sum(1 for c in eb.get('checks', []) if not c.get('ok'))
    rows.append(_row('B', 'ebox 全部檢查（用實際結果重算）', bad == 0, f'{n - bad}/{n}', '全過'))
    return rows


# ---- C. #5 ----------------------------------------------------------------
def _sections(gWV, W) -> list[tuple[float, float]]:
    return F._section_V(gWV, W)


def _sec_C(cat0, P, regs) -> list[dict]:
    from .ebox import min_web
    rows = []
    p5 = P['#5']
    rows.append(_row('C', '#5 單一連通', p5.geom.geom_type == 'Polygon', p5.geom.geom_type, 'Polygon'))
    sysn = sorted({r['sys'] for r in regs if r['part'] == '#5' and r['kind'] in ('cut', 'add', 'fill')})
    rows.append(_row('C', '#5 套用的子系統', set(sysn) >= {'crosstrack', 'ebox'}, '、'.join(sysn), 'crosstrack、ebox'))
    g = _to_asm('#5', p5.geom, ('W', 'V'))
    g0 = _to_asm('#5', cat0['#5'].geom, ('W', 'V'))
    front26 = _sections(g, sum(F.W26) / 2)
    front24 = _sections(g, sum(F.W24) / 2)
    rear = _sections(g, F.W37_IN + 1.5)
    f26_0 = _sections(g0, sum(F.W26) / 2)
    rows.append(_row('C', '#5 前榫（穿 #26，W\'−1.5 截面 V 範圍）', len(front26) >= 1,
                     '；'.join(f'V{a:.2f}～{b:.2f}' for a, b in front26) or '無',
                     '≥1 支（spec：只剩第二小榫）', '原始：' + '；'.join(f'V{a:.2f}～{b:.2f}' for a, b in f26_0)))
    rows.append(_row('C', '#5 長榫（穿到 #24）已刪', len(front24) == 0, len(front24), '0（S50 開底缺口）'))
    rows.append(_row('C', '#5 後榫（插 #37）', len(rear) == 1, '；'.join(f'V{a:.2f}～{b:.2f}' for a, b in rear) or '無', '1 支'))
    w = min_web(p5.geom)
    w0 = min_web(cat0['#5'].geom)
    rows.append(_row('C', '#5 最小料寬（負緩衝切斷寬度）', w >= MIN_WEB, w, f'≥{MIN_WEB:g}', f'原始 #5：{w0}'))
    ct = [r['geom'] for r in regs if r['part'] == '#5' and r['sys'] == 'crosstrack' and r['kind'] == 'cut']
    eb = [r['geom'] for r in regs if r['part'] == '#5' and r['sys'] == 'ebox' and r['kind'] == 'cut']
    if ct and eb:
        a, b = unary_union(ct), unary_union(eb)
        d = a.distance(b)
        # 兩個缺口之間的料（在 #5 外框內）最窄處
        rest = p5.geom
        rows.append(_row('C', '#5 crosstrack 缺口 ↔ 電子盒前上角', d >= MIN_WEB, d, f'≥{MIN_WEB:g}',
                         f'crosstrack {_fmt_box(_to_asm("#5", a, ("W", "V")), ("W", "V"))}；'
                         f'ebox {_fmt_box(_to_asm("#5", b, ("W", "V")), ("W", "V"))}；剩餘面積 {rest.area:.0f}／原 {cat0["#5"].geom.area:.0f} mm²'))
    return rows


# ---- D. #26 ---------------------------------------------------------------
def _sec_D(cat0, P, regs) -> list[dict]:
    rows = []
    p = P['#26']
    rows.append(_row('D', '#26 單一連通', p.geom.geom_type == 'Polygon', p.geom.geom_type, 'Polygon'))
    sysn = sorted({r['sys'] for r in regs if r['part'] == '#26'})
    rows.append(_row('D', '#26 套用的修改來源', set(sysn) >= {'crosstrack', 's1', 'ebox', 'fix26'},
                     '、'.join(SYS_ZH[s] for s in sysn), 'crosstrack、s1、ebox、原始檔修正'))
    # 齒孔修正
    from .frames import fix_26_tooth_hole
    ref = fix_26_tooth_hole(cat0['#26'])
    i = ref.cut_src.index('path131[19]')
    ok = 'path131[19]' in p.cut_src and p.cut_d[p.cut_src.index('path131[19]')] == ref.cut_d[i]
    rows.append(_row('D', '#26 齒孔 path131[19] ＝ frames.fix_26_tooth_hole() 結果（逐字）', ok, ok, True))
    # 新切割離四個分幣開口
    cuts = [(r['sys'], r['tag'], r['geom']) for r in regs if r['part'] == '#26' and r['kind'] == 'cut']
    for src, nm in COIN_OPENINGS.items():
        op = _ring_poly(cat0['#26'].cut_d[cat0['#26'].cut_src.index(src)])
        dd = min((op.distance(g), s, t) for s, t, g in cuts)
        rows.append(_row('D', f'#26 {nm}（{src}）↔ 最近的新切割 {SYS_ZH[dd[1]]}「{dd[2]}」', dd[0] >= MIN_WEB, dd[0],
                         f'≥{MIN_WEB:g}'))
    # 消失的原始孔：要有理由
    van = (p.stats or {}).get('vanished', []) if hasattr(p, 'stats') else []
    for s in van:
        why = ''
        if s == 'path131[1]':
            g5 = _to_asm('#5', P['#5'].geom, ('W', 'V'))
            up = [iv for iv in _sections(g5, sum(F.W26) / 2) if iv[0] < 30]
            ok = not up
            why = '#5 上小榫槽（V17～27）被電子盒 L 形缺口吃掉；#5 上小榫已由電子盒刪除' if ok else '#5 仍有上小榫，槽卻不見了'
        else:
            ok = False
            why = '沒有預期這個孔消失'
        rows.append(_row('D', f'#26 原始孔 {s} 消失', ok, why, '有對應的榫被刪'))
    return rows


# ---- E. #24 雕刻 ------------------------------------------------------------
def _centerline_pts(elem: str):
    """雕刻元素的中心線取樣點（MultiPoint）：bbox／凸包用。"""
    from shapely.geometry import MultiPoint
    d = _elem_d(elem)
    return MultiPoint(np.vstack([p for p, _ in qa.sample_d(d, 0.05)])) if d else MultiPoint()


def _ct_model(cat):
    """mods_crosstrack 的內部模型（同一份 cat 只算一次）。"""
    key = id(cat)
    if _CT_CACHE.get('key') != key:
        from . import mods_crosstrack as CT
        _CT_CACHE.update(key=key, M=CT.model(copy.deepcopy(cat)))
    return _CT_CACHE['M']


_CT_CACHE: dict = {}


def front_covers(cat) -> 'Polygon':
    """裝在 #24 前方、會蓋住雕刻的東西（組裝 U,V）：crosstrack 三站的蓋板 C1（P1、插銷都在 C1 範圍內）。"""
    try:
        M = _ct_model(cat)
        return unary_union([R['c1'] for R in M['S'].values()])
    except Exception:                       # noqa: BLE001
        return None


def _sec_E(cat0, P, covers=None) -> list[dict]:
    """量法：「1」「5」照 crosstrack spec b-6（export.py 的搜尋）用雕刻中心線的外框（bbox）到切割的距離；
    Logo 照 ebox 規則 4 用凸包（雕刻＋9 個菱形孔）；雕刻彼此用凸包距離。另列字墨（含 0.2 線寬）到切割的距離。
    covers：#24 前方會蓋住雕刻的零件（front_covers），雕刻也要離它 ≥1.5（同 crosstrack 的搜尋條件）。"""
    rows = []
    p = P['#24']
    lines = []
    for d, s in zip(p.cut_d, p.cut_src):
        if s not in LOGO_HOLES:
            lines.extend(_ring_lines(d, 0.02))
    cut_all = MultiLineString(lines)
    holes_logo = unary_union([_ring_poly(d) for d, s in zip(p.cut_d, p.cut_src) if s in LOGO_HOLES])
    cen = {s: _centerline_pts(e) for e, s in zip(p.engrave, p.engrave_src)}
    ink = {s: _engrave_region(e) for e, s in zip(p.engrave, p.engrave_src)}
    hull = {s: g.convex_hull for s, g in cen.items()}
    if 'path1-5-9' in hull:
        hull['path1-5-9'] = unary_union([hull['path1-5-9'], holes_logo]).convex_hull
    for src in ('text16-7-2', 'text11-4-1'):
        if src not in cen:
            rows.append(_row('E', f'#24 雕刻{ENG_NAMES[src]}', False, '不見了', '存在'))
            continue
        bb = cen[src].envelope
        d_box = min(bb.distance(cut_all), bb.distance(holes_logo))
        d_ink = min(ink[src].distance(cut_all), ink[src].distance(holes_logo))
        rows.append(_row('E', f'#24 雕刻{ENG_NAMES[src]}外框離最終所有切割（spec b-6 量法）', d_box >= ENGRAVE_CLEAR - 1e-3,
                         round(d_box, 3), f'≥{ENGRAVE_CLEAR:g}',
                         f'位置 {_fmt_box(_to_asm("#24", bb))}；字墨（含線寬）到切割 {d_ink:.2f}；'
                         f'最近處 {_where("#24", bb, cut_all)}'))
        if covers is not None and not covers.is_empty:
            dc = _to_asm('#24', bb).distance(covers)
            rows.append(_row('E', f'#24 雕刻{ENG_NAMES[src]}外框離 #24 前方的蓋板 C1（不被蓋住）', dc >= ENGRAVE_CLEAR - 1e-3,
                             round(dc, 3), f'≥{ENGRAVE_CLEAR:g}', 'C1＝mods_crosstrack 實際位置'))
    if 'path1-5-9' in cen:
        lg = hull['path1-5-9']
        d = lg.distance(cut_all)
        rows.append(_row('E', '#24 Logo（雕刻＋9 個菱形孔的凸包）離其他切割', d >= LOGO_CLEAR, d, f'≥{LOGO_CLEAR:g}（ebox 規則 4）',
                         f'位置 {_fmt_box(_to_asm("#24", lg.envelope))}；最近處 {_where("#24", lg, cut_all)}'))
        dh = holes_logo.distance(cut_all)
        rows.append(_row('E', '#24 Logo 菱形孔離其他孔／外框', dh >= LOGO_HOLE_CLEAR, dh, f'≥{LOGO_HOLE_CLEAR:g}'))
        moved = [h for h in LOGO_HOLES if h in p.cut_src]
        ok = len(moved) == 9 and all(h in (p.stats or {}).get('moved', []) for h in moved)
        rows.append(_row('E', '#24 Logo 9 個菱形孔只平移（曲線不變）', ok,
                         f'{len(moved)} 個、moved {len((p.stats or {}).get("moved", []))}', '9'))
    keys = [s for s in ('text16-7-2', 'text11-4-1', 'path1-5-9', 'text1-6-4', 'text2-1-3') if s in hull]
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            d = hull[a].distance(hull[b])
            need = LOGO_CLEAR if 'path1-5-9' in (a, b) else ENGRAVE_CLEAR
            if d < 10:
                rows.append(_row('E', f'#24 雕刻 {ENG_NAMES[a]}↔{ENG_NAMES[b]}（凸包）', d >= need, d, f'≥{need:g}（不重疊）'))
    far = [f'{ENG_NAMES[a]}↔{ENG_NAMES[b]}' for i, a in enumerate(keys) for b in keys[i + 1:] if hull[a].distance(hull[b]) >= 10]
    rows.append(_row('E', '#24 其他雕刻配對都 ≥10 mm', True, f'{len(far)} 組', '≥10'))
    return rows


def engrave_failures(rows) -> list[str]:
    """E 節裡「1」「5」不合格的雕刻 src（給 recompute_engrave_moves 用）。"""
    out = []
    for r in rows:
        if r['sec'] == 'E' and r['ok'] is False:
            for src in ('text16-7-2', 'text11-4-1'):
                if ENG_NAMES[src] in r['name'] and src not in out:
                    out.append(src)
    return out


def recompute_engrave_moves(cat: dict, results: dict, parts: list, srcs: list[str]) -> list[str]:
    """E 節不合格時，依 crosstrack spec b-6 的規則用「最終所有切割」重算 #24「1」「5」的新位置：
    從原位置做最小平移搜尋（成本 |ΔV|+3|ΔU|，範圍與步距照 mods_crosstrack.DESIGN），新位置的外框要在
    #24 外框內縮 engrave_clear、V ≤ v_drawer−1，且離最終所有孔／窗、轉盤圍邊、其他雕刻 ≥ engrave_clear。
    直接改 results['crosstrack'] 裡對應 move_engrave 的 dx、dy、tag（呼叫端要重新 compose）。回傳說明。"""
    from . import mods_crosstrack as CT
    Pd = CT.DESIGN
    clear, vmax = Pd['engrave_clear'], Pd['v_drawer'] - 1.0
    (du0, du1), (dv0, dv1), stp = Pd['engrave_search']
    P = _by_orig(parts)
    p = P['#24']
    g = _to_asm('#24', p.geom)
    region = Polygon(g.exterior).buffer(-clear).intersection(box(0, 0, 246, vmax))
    holes = unary_union([Polygon(h) for h in g.interiors])
    ring = Point(CT.TURN_C).buffer(CT.TURN_R_RING + 1.0, 128)
    covers = front_covers(cat)
    if covers is not None:
        holes = unary_union([holes, covers])          # 蓋板 C1 會蓋住雕刻（crosstrack 搜尋也把它當障礙）
    cen = {s: _to_asm('#24', _centerline_pts(e)) for e, s in zip(p.engrave, p.engrave_src)}
    orig = {s: _to_asm('#24', _centerline_pts(e)).envelope for e, s in zip(cat['#24'].engrave, cat['#24'].engrave_src)}
    cands = sorted((abs(dV) + 3 * abs(dU), dU, dV) for dU in np.arange(du0, du1 + 1e-9, stp)
                   for dV in np.arange(dv0, dv1 + 1e-9, stp))
    msgs = []
    edits = results['crosstrack']['edits']
    for src in srcs:
        others = unary_union([m.convex_hull for s, m in cen.items() if s != src])   # Logo 菱形孔已在 holes 裡
        blk = unary_union([holes, ring, others])
        import shapely
        shapely.prepare(blk)
        best = None
        for cost, dU, dV in cands:
            b = affinity.translate(orig[src], dU, dV)
            if region.contains(b) and not b.buffer(clear).intersects(blk):
                best = (float(dU), float(dV))
                break
        e = next((x for x in edits if x['op'] == 'move_engrave' and x.get('src') == src), None)
        if best is None:
            msgs.append(f'雕刻{ENG_NAMES[src]}：用最終切割重算也找不到 ≥{clear:g} 的位置，維持原搬移（要人工處理）')
            continue
        dx, dy = CT._page_delta('#24', best[0], best[1])
        if e is None:
            e = dict(op='move_engrave', part='#24', src=src)
            edits.append(e)
        old = (e.get('dx'), e.get('dy'))
        e['dx'], e['dy'] = round(float(dx), 4), round(float(dy), 4)
        e['tag'] = f'雕刻{ENG_NAMES[src]}搬移 ΔU{best[0]:+g} ΔV{best[1]:+g}（整合時用最終切割重算）'
        msgs.append(f'雕刻{ENG_NAMES[src]}：用最終切割重算，頁座標平移 {old} → ({e["dx"]}, {e["dy"]})，'
                    f'ΔU{best[0]:+g} ΔV{best[1]:+g}')
    return msgs


# ---- F. 不同子系統的修改區域 ---------------------------------------------
_EXPECTED = {
    # (零件, 子系統 a, tag 關鍵字 a, 子系統 b, tag 關鍵字 b) → 說明（相交／太近是設計上預期的）
}


def _sec_F(regs, P) -> tuple[list[dict], list[str]]:
    rows, issues = [], []
    by_part: dict[str, list[dict]] = {}
    for r in regs:
        by_part.setdefault(r['part'], []).append(r)
    for pid, lst in sorted(by_part.items()):
        sysset = sorted({r['sys'] for r in lst})
        if len(sysset) < 2:
            continue
        best = None
        n_near = 0
        axes = _plane_axes(pid)
        for i, a in enumerate(lst):
            for b in lst[i + 1:]:
                if a['sys'] == b['sys']:
                    continue
                d = a['geom'].distance(b['geom'])
                if best is None or d < best[0]:
                    best = (d, a, b)
                if d < NEAR:
                    n_near += 1
                    how = _judge(pid, a, b, d)
                    issues.append(f"{pid}：{SYS_ZH[a['sys']]}「{a['tag']}」↔ {SYS_ZH[b['sys']]}「{b['tag']}」"
                                  f"{'相交' if d < 1e-6 else f'相距 {d:.2f} mm'}（{_where(pid, a['geom'], b['geom'])}）→ {how[1]}")
                    rows.append(_row('F', f"{pid} {SYS_ZH[a['sys']]}「{a['tag']}」↔ {SYS_ZH[b['sys']]}「{b['tag']}」",
                                     how[0], round(d, 2), f'≥{NEAR:g} 或已處理', how[1]))
        if best:
            d, a, b = best
            rows.append(_row('F', f'{pid}：{"／".join(SYS_ZH[s] for s in sysset)} 修改區域最近距離', None, round(d, 2),
                             f'≥{NEAR:g}', f"{SYS_ZH[a['sys']]}「{a['tag']}」↔ {SYS_ZH[b['sys']]}「{b['tag']}」；"
                                         f'< {NEAR:g} 的共 {n_near} 組'))
    return rows, issues


def _judge(pid, a, b, d) -> tuple[bool, str]:
    """兩個子系統的修改區域太近時，判斷是否可接受並說明處理方式。"""
    kinds = {a['kind'], b['kind']}
    if kinds == {'engrave'}:
        return (d > 0.3, '兩個雕刻：外框不重疊即可（雕刻不影響強度）' if d > 0.3 else '雕刻重疊，要搬開')
    if 'engrave' in kinds:
        e, c = (a, b) if a['kind'] == 'engrave' else (b, a)
        if c['kind'] == 'fill':
            return (True, f"雕刻落在{SYS_ZH[c['sys']]}刪孔補實的區域旁，補實後是實料，可接受")
        return (d >= 1.0, '雕刻離切割 ≥1.0（E 節另以 1.5 規則檢查 #24 的「1」「5」）' if d >= 1.0 else '雕刻離切割太近，要搬開')
    if 'fill' in kinds:
        f, c = (a, b) if a['kind'] == 'fill' else (b, a)
        return (True, f"一邊是刪孔補實（{f['tag']}），另一邊的切割照常切；合成後不會留下細料（W 節另查細料）")
    return (d >= MIN_WEB, f'兩個切割之間的料 {d:.2f} mm' + ('' if d >= MIN_WEB else f'，小於 {MIN_WEB:g}，要改'))


# ---- G. 原始子路徑逐字保留 -------------------------------------------------
def _sec_G(cat0, cat, P, regs, parts) -> list[dict]:
    rows = []
    n_orig_ok, bad_orig = 0, []
    for v in parts:
        if v.layer != 'original':
            continue
        o = cat0[v.id]
        same = v.cut_d == o.cut_d and v.engrave == o.engrave and v.cut_src == o.cut_src
        if same:
            n_orig_ok += 1
        else:
            bad_orig.append(v.id)
    n_orig = sum(1 for v in parts if v.layer == 'original')
    rows.append(_row('G', '沒被修改的原始零件：cut_d／engrave 和原始檔逐字相同', not bad_orig, f'{n_orig_ok}/{n_orig}',
                     '全部', '不同：' + '、'.join(bad_orig) if bad_orig else ''))
    by_part: dict[str, list[dict]] = {}
    for r in regs:
        by_part.setdefault(r['part'], []).append(r)
    for v in parts:
        if v.layer != 'modified':
            continue
        pid = _orig_id(v)
        o = cat0[pid]
        fin = dict(zip(v.cut_src, v.cut_d))
        moved = set((v.stats or {}).get('moved', []))
        kept = changed = 0
        unexplained = []
        regen = []
        for d0, s in zip(o.cut_d, o.cut_src):
            if s in fin and s not in moved:
                if fin[s] == d0:
                    kept += 1
                    continue
                if pid == '#26' and s == 'path131[19]':
                    changed += 1          # 齒孔修正（D 節逐字比對 frames 的結果）
                    continue
                unexplained.append(f'{s}（d 不同）')
                continue
            if s in moved:
                changed += 1
                continue
            # 重生、刪除或消失：要有 edit 碰到它
            ring = _ring_poly(d0) if o.cut_closed[o.cut_src.index(s)] else LineString(qa.sample_d(d0)[0][0])
            near = [r for r in by_part.get(pid, []) if r['kind'] in ('cut', 'add', 'fill')
                    and (r.get('src') == s or r['geom'].distance(ring if s != o.cut_src[0] else ring.exterior) < TOUCH)]
            if near:
                changed += 1
                regen.append(f"{s}←{'／'.join(sorted({SYS_ZH[r['sys']] for r in near}))}")
            else:
                unexplained.append(s)
        # 雕刻
        efin = dict(zip(v.engrave_src, v.engrave))
        e_kept = e_changed = 0
        e_bad = []
        mv = {r['src'] for r in by_part.get(pid, []) if r['op'] == 'move_engrave'}
        for e0, s in zip(o.engrave, o.engrave_src):
            if s in mv:
                e_changed += 1
            elif efin.get(s) == e0:
                e_kept += 1
            else:
                e_bad.append(s)
        ok = not unexplained and not e_bad
        rows.append(_row('G', f'{v.id} 沒被碰到的子路徑逐字相同', ok,
                         f'切割 保留 {kept}／改 {changed}；雕刻 保留 {e_kept}／移 {e_changed}', '沒有不明的改變',
                         ('重生或刪除（都有 edit 碰到）：' + '、'.join(regen) if regen else '')
                         + ('；不明的改變：' + '、'.join(unexplained + e_bad) if not ok else '')))
    return rows


# ---- H. 分幣開口與軌道逐點 -------------------------------------------------
def _point_dev(d0: str, d1_list: list[str]) -> float:
    """原始子路徑取樣點到最終切割線（同零件所有子路徑）的最大距離。"""
    pts = np.vstack([p for p, _ in qa.sample_d(d0, 0.05)])
    lines = MultiLineString([L for d in d1_list for L in _ring_lines(d, 0.02)])
    import shapely
    return float(shapely.distance(shapely.points(pts), lines).max())


def _sec_H(cat0, P) -> list[dict]:
    rows = []
    items = [('#26', s, n) for s, n in COIN_OPENINGS.items()] + [(pid, s, n) for pid, m in RAIL_SRC.items() for s, n in m.items()]
    for pid, src, nm in items:
        o = cat0[pid]
        d0 = o.cut_d[o.cut_src.index(src)]
        v = P[pid]
        verb = src in v.cut_src and v.cut_d[v.cut_src.index(src)] == d0
        dev = 0.0 if verb else _point_dev(d0, v.cut_d)
        rows.append(_row('H', f'{pid} {nm}（{src}）和原始檔逐點相同', verb or dev <= POINT_TOL,
                         '逐字相同（偏差 0）' if verb else f'偏差 {dev:.4f}', f'≤{POINT_TOL:g} mm'))
    return rows


# ---- K. 榫槽配對 ----------------------------------------------------------
def _tenon_report(pid_part: str, g_part_page, plates: dict) -> list[tuple]:
    """U 平面零件在 #24/#26/#37 板厚中央的截面（V 區間），和板子（UV）在同一 U 範圍內的實料干涉。
    回傳 [(板, V 區間, 干涉長度 V)]；干涉長度＝截面區間內、板子實料佔的 V 長度（窄 U 欄位內）。"""
    fr = F.frame(pid_part)
    g = fr.geom_asm(g_part_page, 0.0, ('W', 'V'))
    u0, u1 = fr.plane()[1:]
    uc = (u0 + u1) / 2
    out = []
    for plate, (w0, w1) in PLATES.items():
        for lo, hi in _sections(g, (w0 + w1) / 2):
            mat = plates[plate]
            col = box(uc - 1.0, lo, uc + 1.0, hi)
            inter = mat.intersection(col)
            L = sum(q.bounds[3] - q.bounds[1] for q in _polys(inter)) if not inter.is_empty else 0.0
            out.append((plate, (lo, hi), L))
    return out


def _empty_slots(pid_part, g_part_page, plates, plates0) -> list[str]:
    """板子上新切出、落在這片 U 欄位內的槽（不是原始孔），有沒有榫穿過。"""
    fr = F.frame(pid_part)
    g = fr.geom_asm(g_part_page, 0.0, ('W', 'V'))
    u0, u1 = fr.plane()[1:]
    out = []
    for plate, (w0, w1) in PLATES.items():
        secs = _sections(g, (w0 + w1) / 2)
        holes = [Polygon(h) for h in plates[plate].interiors]
        holes0 = [Polygon(h) for h in plates0[plate].interiors]
        for h in holes:
            b = h.bounds
            if (b[0] > u0 - 0.3 and b[2] < u1 + 0.3 and 2.5 < (b[2] - b[0]) < 3.6
                    and (b[3] - b[1]) >= 4.0):      # 槽寬 ≈ 板厚、在這片的 U 欄位（光孔 1.8 寬不算）
                if any(h.symmetric_difference(h0).area < 0.05 for h0 in holes0):
                    continue                                                    # 原始孔（另外比對）
                hit = any(lo < b[3] and hi > b[1] for lo, hi in secs)
                if not hit:
                    out.append(f'{plate} 新槽 V{b[1]:.1f}～{b[3]:.1f}')
    return out


def _sec_K(cat0, P) -> list[dict]:
    rows = []
    plates = {pid: _to_asm(pid, P[pid].geom, ('U', 'V')) for pid in PLATES}
    plates0 = {pid: _to_asm(pid, cat0[pid].geom, ('U', 'V')) for pid in PLATES}
    for pid in U_PLANE_PARTS:
        v = P[pid]
        rep = _tenon_report(pid, v.geom, plates)
        rep0 = _tenon_report(pid, cat0[pid].geom, plates0)
        worst = max((L for _, _, L in rep), default=0.0)
        worst0 = max((L for _, _, L in rep0), default=0.0)
        bad = [(pl, iv, L) for pl, iv, L in rep if L > max(worst0, 0.35) + TENON_TOL]
        txt = '；'.join(f'{pl} V{iv[0]:.1f}～{iv[1]:.1f}' + (f'（干涉 {L:.2f}）' if L > 0.005 else '') for pl, iv, L in rep)
        rows.append(_row('K', f'{v.id} 穿板截面都在孔／缺口裡（{len(rep)} 段）', not bad, round(worst, 3),
                         f'干涉 ≤ 原始 {worst0:.3f}（或 ≤0.35）＋{TENON_TOL:g}', txt))
        empty = _empty_slots(pid, v.geom, plates, plates0)
        rows.append(_row('K', f'{v.id} 欄位內的新槽都有榫', not empty, '、'.join(empty) or '無空槽', '無空槽'))
    # 原始槽（#24/#26/#37）在 v2 變成空槽：列出（資訊；被刪的榫對應的孔應該已刪）
    return rows


# ---- W. 細料 ------------------------------------------------------------------
def _sec_W(cat0, P, regs) -> list[dict]:
    rows = []
    for pid in sorted({r['part'] for r in regs if r['kind'] in ('cut', 'add', 'fill')}):
        v = P[pid]
        o = cat0[pid]
        rings0 = {s: unary_union(_ring_lines(d)) for d, s in zip(o.cut_d, o.cut_src)}
        rings = [(s, unary_union(_ring_lines(d))) for d, s in zip(v.cut_d, v.cut_src)]
        moved = set((v.stats or {}).get('moved', []))
        worst = None
        for i, (sa, ga) in enumerate(rings):
            newa = sa.endswith('*') or sa in moved
            for sb, gb in rings[i + 1:]:
                newb = sb.endswith('*') or sb in moved
                if not (newa or newb):
                    continue
                d = ga.distance(gb)
                if d >= MIN_WEB:
                    continue
                ca = [x for x in re.split(r'[+*~]', sa) if x in rings0]
                cb = [x for x in re.split(r'[+*~]', sb) if x in rings0]
                d0 = min((rings0[x].distance(rings0[y]) for x in ca for y in cb), default=math.inf)
                if d < d0 - 0.01:
                    if worst is None or d < worst[0]:
                        worst = (d, sa, sb, _where(pid, ga, gb), d0)
        ok = worst is None
        rows.append(_row('W', f'{v.id} 新／重生切割環到其他環 ≥{MIN_WEB:g}（比原始檔近的才算）', ok,
                         'OK' if ok else round(worst[0], 3), f'≥{MIN_WEB:g}',
                         '' if ok else f'{worst[1]} ↔ {worst[2]} 在 {worst[3]}（原始 {worst[4]:.2f}）'))
        # opening：edit 附近、寬度 < MIN_WEB、原本沒有的細料
        near = unary_union([r['geom'] for r in regs if r['part'] == pid and r['kind'] in ('cut', 'add')]).buffer(MIN_WEB)
        if near.is_empty:
            continue
        M, M0 = v.geom, o.geom
        r_ = MIN_WEB / 2
        neck = M.difference(_opening(M, r_)).intersection(near)
        neck0 = M0.difference(_opening(M0, r_))
        tr = [r for r in regs if r['part'] == pid and r['op'] == 'translate_cut' and r['sys'] != 'fix26']
        if tr:      # 平移的孔（Logo 菱形孔）：孔與孔之間原本就細，跟著平移後的位置也算「原本就有」
            M0t = o.geom
            for r in tr:
                M0t = M0t.difference(r['geom'])
            neck0 = unary_union([neck0, M0t.difference(_opening(M0t, r_))])
        neck0 = neck0.buffer(0.05)
        pcs = [q for q in _polys(neck.difference(neck0)) if q.area > 0.3]
        # 分兩種：頸部（拿掉會把零件切成兩塊＝真的細料）、小凸齒（只有一邊接本體，斷了也不影響）
        necks, stubs = [], []
        for q in pcs:
            rest = [x for x in _polys(M.difference(q.buffer(0.02))) if x.area > 0.5]
            (necks if len(rest) > 1 or q.area >= STUB_AREA else stubs).append(q)
        where = lambda L: '；'.join(_fmt_box(_to_asm(pid, q), _plane_axes(pid)) for q in L[:4])
        big = max(necks, key=lambda q: q.area) if necks else None
        rows.append(_row('W', f'{v.id} edit 附近沒有新的 <{MIN_WEB:g} mm 細料（opening 法）', not necks,
                         'OK' if not necks else f'{len(necks)} 塊，最大 {big.area:.2f} mm²', '無',
                         ('' if not necks else '在 ' + where(necks))
                         + ('' if not stubs else f'；另有 {len(stubs)} 個 <{STUB_AREA:g} mm² 的單邊小凸齒（不影響強度）：' + where(stubs))))
    return rows


# ---- S. S1 ↔ S5 實際深度 --------------------------------------------------
def _sec_S(cat, results) -> list[dict]:
    rows = []
    s1 = results.get('s1') or {}
    ck = {c.get('key'): c for c in s1.get('checks', []) if c.get('key')}
    if 's5_gap' not in ck:
        return [_row('S', 'S1 ↔ S5 間隙', None, 'mods_s1 沒有 s5_gap 檢查', '')]
    M = _ct_model(cat)
    st = M['S']['S5']
    wmax = max(b[6] for key in ('mod_final', 'mod_low') for b in st.get(key, []) if b[0] != '排針＋杜邦頭')
    front_W = float(ck['s5_gap']['value']) + 10.0          # mods_s1：value＝front_W − S5_W_MAX(10.0)
    gap = front_W - wmax
    rows.append(_row('S', "S1 最前實體 W' 到 S5 實際最深 W'（最終位置與低位）", gap >= 1.5, gap, '≥1.5',
                     f"S1 最前 W'{front_W:.2f}；S5 最深 W'{wmax:.2f}（mods_crosstrack 實際；mods_s1 用規格常數 10.0）"))
    return rows


# ---------------------------------------------------------------------------
# 排版
# ---------------------------------------------------------------------------
def check_layout(sheets, parts) -> list[dict]:
    rows = []
    where: dict[str, set] = {}
    for s in sheets:
        for pl in s.items:
            if getattr(pl, 'spare', False):      # 備品不受 group 限制（layout 只塞進已經開的板），下面另外檢查
                continue
            where.setdefault(pl.part.id, set()).add((s.material, s.no))
    groups: dict[str, list[str]] = {}
    for p in parts:
        if getattr(p, 'group', None):
            groups.setdefault(p.group, []).append(p.id)
    for gname, ids in sorted(groups.items()):
        sh = set().union(*[where.get(i, set()) for i in ids])
        rows.append(_row('L', f'同板群組 {gname}（{"、".join(ids)}）排在同一張', len(sh) == 1,
                         '、'.join(f'{m} 第 {n} 張' for m, n in sorted(sh)), '1 張'))
    ok = 'S1-B' in where and '#13R' in where and where['S1-B'] == where['#13R']
    rows.append(_row('L', 'S1-B 與 #13R 同一張', ok, '、'.join(f'{m} 第 {n} 張' for m, n in sorted(where.get('S1-B', set()))), '同一張'))
    by = {}
    for s in sheets:
        by[s.material] = by.get(s.material, 0) + 1
    ply, acr = by.get('合板', 0), by.get('壓克力', 0)
    rows.append(_row('L', '合板張數（交接估 3～4 張）', 3 <= ply <= 4, ply, '3～4'))
    rows.append(_row('L', '壓克力張數', acr >= 1, acr, '≥1（另排）'))
    missing = [p.id for p in parts if p.id not in where]
    rows.append(_row('L', '每個零件都有排', not missing, '、'.join(missing) or '全部', '全部'))
    # 備品（使用者 2026-10-08：極小零件每套多一整份；layout 只塞進已經開的板，不加張數）
    from .layout import unplaced_spares
    want = {p.id: int(getattr(p, 'spare', 0) or 0) for p in parts if int(getattr(p, 'spare', 0) or 0)}
    got: dict[str, int] = {}
    for s in sheets:
        for pl in s.items:
            if getattr(pl, 'spare', False):
                got[pl.part.id] = got.get(pl.part.id, 0) + 1
    un = unplaced_spares(sheets)
    if want or un:
        rows.append(_row('L', '備品都排進現有的板（不增加張數）', not un and got == want,
                         f'{sum(got.values())}/{sum(want.values())} 件', '全部',
                         ('放不下：' + '、'.join(un)) if un else '、'.join(f'{k}×{v}' for k, v in want.items())))
    return rows


# ---------------------------------------------------------------------------
# 報告
# ---------------------------------------------------------------------------
SEC_TITLE = {
    'A': 'A. #37 開孔（S1 ↔ 電子盒 ↔ 感測器線孔）',
    'B': 'B. 電子盒 S1 禁區改用 mods_s1 實際結果重查',
    'C': 'C. #5（crosstrack ＋ 電子盒）',
    'D': 'D. #26（三個子系統＋齒孔修正）',
    'E': 'E. #24 雕刻「1」「5」與 Logo',
    'F': 'F. 兩個子系統在同一零件上的修改區域（< 1.5 mm 列出）',
    'G': 'G. 原始子路徑逐字保留',
    'H': 'H. 分幣開口與軌道逐點比對',
    'K': 'K. 榫槽配對（間隔條、櫃側板穿過 #24／#26／#37）',
    'W': 'W. 新切割造成的細料',
    'S': 'S. S1 ↔ S5 實際間隙',
    'L': 'L. 排版',
}


def failures(rows) -> list[dict]:
    return [r for r in rows if r['ok'] is False]


def summary_lines(rows) -> list[str]:
    out = []
    for r in rows:
        flag = 'OK ' if r['ok'] else ('資訊' if r['ok'] is None else '!! ')
        out.append(f"{flag}[{r['sec']}] {r['name']}：{r['value']}（期望 {r['expected']}）" + (f"  {r['note']}" if r['note'] else ''))
    return out


# ---------------------------------------------------------------------------
# 單獨執行：python -m laser_v2.integrate（跑三個子系統＋ebox 重查＋compose，印出跨子系統檢查；不排版、不輸出）
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import sys
    from . import compose
    from .build_v2 import load_parts, run_subsystems
    _cat0 = _cat.load_catalog()
    _c = load_parts()
    _res = run_subsystems(_c)
    _res['ebox'], _info = ebox_integrated(_c, _res)
    print(f"ebox 重查：{_info['n_checks'] - _info['n_fail']}/{_info['n_checks']} 通過、edits 相同={_info['same_edits']}")
    _parts = compose.compose(_c, _res)
    _out = check(_c, _res, _parts, _cat0)
    print('\n'.join(summary_lines(_out['rows'])))
    for _s in _out['issues']:
        print('相交／太近：' + _s)
    _bad = failures(_out['rows'])
    print(f"\n共 {len(_out['rows'])} 項，未通過 {len(_bad)}")
    sys.exit(1 if _bad else 0)

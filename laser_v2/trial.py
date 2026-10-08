"""試切小樣：從 v2 最終零件裁出測試用的局部，排進 255×355 的板，輸出試切檔與試切說明。

用法
----
    python -m laser_v2.trial            # 自己跑完產生流程（子系統 → ebox 重查 → compose → #24 雕刻檢查），再輸出試切小樣
    python -m laser_v2.trial --no-png   # 不畫預覽圖
    from laser_v2 import trial
    res = trial.run(parts, results, cat)   # build_v2 最後呼叫：parts＝compose 的最終零件（含所有 v2 修改）

輸出
----
* 分幣機雷切_光耦版_v2_試切小樣.svg（repo 根目錄）：格式同 v2 草稿（export.py：Inkscape 多頁、255×355、
  4 個圖層「原始零件」「v2 修改」「v2 新增」「註記（不切割）」、文字全部轉成路徑），並跑 qa.check。
  裁出來的局部放「v2 修改」層，v2 新零件與試切輔助件放「v2 新增」層。
* laser_v2/out/trial_<材質>_<n>.png：預覽圖。
* laser_v2/out/trial_report.md：每片是什麼、要測什麼（對應三份 spec 的 T 編號）、怎麼判定過關、
  不過關時改哪個參數，以及本模組的檢查結果。

小樣組成（依 crosstrack／s1wall／ebox 三份 spec 的 (g) g-2 試切章節）
--------------------------------------------------------------------
TA 組＝機身左段（S10、S50 感測座＋TM1637 顯示器＋電子盒），可以組成一段真的能滾硬幣的機身：
* TA-#24：#24 的 U142～246 × V4～98（左下腳 V98 以下切掉）。含 S10 窗、S50 開底缺口與兩個插銷孔、
  斜槽軌道 U146～234、顯示窗＋4 個 M2 孔、移位後的 Logo、「5」「10」「50」雕刻、#21 的兩個齒孔。
  右端 U142～146 把斜槽補成 4 mm 連接條（試切專用，實機沒有）：斜槽一切開，軌道下方那條就只靠
  S50 開底缺口上的 2.3 mm 保留條懸臂掛著，補了才和實機一樣兩端都有支撐。
* TA-#26：#26 的 U142～243 × V14～98。含 S10/S50 窗與光孔、10 元／50 元開口（5 元開口被切到一部分）、
  #6 兩個小榫槽、#5 第二小榫槽、L 形缺口、#21 齒孔。
* TA-#37：#37 的 U141～246 × V4～78。含 4 個掛勾槽、頂邊顯示器線缺口、#6/#5 後榫槽；電子盒前緣（到 V76.25）
  整片靠得到 #37。
* TA-#5、TA-#6：#5 v2、#6 v2 整片（S50／S10 擋面與缺口、#5 前上角讓位）。把 TA-#26 和 TA-#37 撐在一起。
* P1-S10、C1-S10、P1-S50、C1-S50、PIN-S50×2：v2 鎖塊、蓋板、插銷（和正式件相同，試切過了可直接用）。
* EB-WL、EB-WR、EB-B、EB-T、EB-S、EB-F、EB-E、EB-K×2：電子盒全部（和正式件相同）。
* TA-ST×2（試切支架，新設計）：(W',V) 平面的板，前槽夾 #24＋#26 下緣、後槽托 TA-#37 下緣，底邊水平，
  讓 TA 組照實機角度（面板後仰 30°）站著；放在 U142～145 與 U241～244（電子盒兩側）。
* TA-PIN×2（定位銷，新設計）：穿過 TA-#24、TA-#26 左下兩個 #21 齒孔，讓兩片的窗對齊。
TB 組＝S1 卡匣：
* TB-#13R：#13R 上段（加高牆、牆槽、前榫 F1/F2、後榫 B1，往下留到 V83.5，不含齒）。
* TB-#26：#26 的 U92～112 × V48～80（槽 F1、F2、C）。
* TB-#37：#37 的 U85.5～127 × V32～86（卡匣窗、槽 B1、2 個 M3 孔、感測器線孔）。
* S1-B、S1-C、S1-F、S1-P、S1-H×3：卡匣全部（和正式件相同）。

和 spec 建議範圍不同的地方（理由寫進報告）
* crosstrack T1 建議 #24/#26 切 U165～215 × V40～98：U165 會切過 S10 窗（窗在 U144～169），而且斜槽會把
  那塊切成上下兩半，所以改成 U142 起、往左包到 #24 左端。
* ebox 建議 #37 切 V0～45：#5、#6 的後榫槽在 V40～56，改到 V78 讓隔板插得上、電子盒前緣整片靠得到。
* s1 建議 #26／#37 切 U90～130 × V30～85：#26 往左會切過 1 元開口與 S5 窗、留下細條，所以只切槽附近
  （U92～112 × V48～80）；#37 往下到 V86（窗下緣到 #37 底邊只有 3.2 mm，V85 會留下細條）。

裁切方法
--------
* 裁切範圍用組裝座標 (U,V) 或 (W',V) 寫，經 frames 換到各零件的頁座標；邊都是直線。
* 用 compose 的合成程式（_apply_part）對最終零件做一次 subtract（範圍外全部去掉），所以沒有被裁到的
  孔、窗、開口原樣保留原始 d（曲線不變），被裁到的子路徑才重新產生；結果一定是單一連通零件。
* 部分在範圍外的雕刻整個刪掉（列在報告）；每片雕小代號（TA-#24…），用 textpath 轉成路徑，
  位置自動找（離切割與其他雕刻 ≥1 mm）。
* 裁切線若有設定搜尋範圍（TA 的右緣），會在範圍內找「不新增 <2 mm 細料」的位置；模組實量後窗變大時
  會自動讓開，真的找不到就在檢查裡列為未通過。

檢查（寫進 trial_report.md）
---------------------------
每片：單一連通、外形＝最終零件∩裁切範圍（TA-#24 另加連接條）、裁切邊不新增 <2 mm 細料、
範圍內的原始／v2 切割逐字保留、必要特徵都在（依各子系統 edit 的 tag 與原始 src 對照）；
TA-#24 軌道（斜槽下緣）逐點相同；支架角度、支架離電子盒牆與感測座的距離、掛上電子盒時的重心（粗估）；
同板群組；張數；
qa.check（雷切檔衛生）。
"""
from __future__ import annotations

import argparse
import dataclasses
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from svgpathtools import parse_path

from . import compose as C
from . import export as X
from . import frames as F
from . import layout as L
from . import params, qa, textpath
from .catalog import REPO

TRIAL_SVG = '分幣機雷切_光耦版_v2_試切小樣.svg'
REPORT_NAME = 'trial_report.md'
SYS = '試切小樣'
MIN_WEB = 2.0          # mm：裁切邊不可新增比這個窄的料（三份 spec 的 min_web）
LABEL_CLEAR = 1.0      # mm：代號雕刻離切割、其他雕刻
ENG_KEEP_MARGIN = 0.2  # mm：雕刻外框要在裁切範圍內縮這麼多才保留
SNAP = 0.002           # mm：裁切範圍頂點離零件頂點座標這麼近就對齊（避免共線邊產生細縫）
POINT_TOL = 0.001      # mm：軌道逐點比對
MAX_SHEETS = 2         # 試切目標 1 張，最多 2 張

# 支架 TA-ST（試切輔助件）
ST_FIT = params.C_TAB  # 槽每邊餘隙（一般榫槽 0.1）；槽寬用 params.T_PLY（實際板厚）
ST_SLOT = 5.0          # 槽深
ST_LIP = 3.0           # 槽前後唇厚
ST_BASE_GAP = 3.0      # 槽底到底邊的最小料
ST_BEAM = 8.0          # 前後兩槽之間的橫樑高（V 方向）
ST_TAIL_W = 65.0       # 底邊往後延伸到 W'（要過電子盒重心，掛上電子盒才不會往後倒）
ST_TAIL_H = 9.0        # 尾段高（V 方向，≈7.8 mm 垂直高）
ST_U_LEFT = 241.0      # 左支架 U 起點（電子盒右牆 U237～240 外側）；右支架從 TA 右緣（自動找的裁切線）起
PIN_LEN = 10.0         # 定位銷長（#24＋#26＝6，前面露 1、後面露 3）

GROUP_ZH = {'TA': 'TA 組：機身左段（S10／S50 感測座＋TM1637 顯示器＋電子盒）',
            'TB': 'TB 組：S1 卡匣'}

# ---------------------------------------------------------------------------
# 裁切件定義（組裝座標）
#   axes：範圍用的兩個組裝軸；rect：(a0, a1, b0, b1)；search：{'a0': (lo, hi)} 在範圍內找裁切線；
#   link：和哪一片共用搜尋結果；minus：再去掉的矩形；poly：非矩形時的頂點；bridge：補連接條寬（a0 起）；
#   need_tags：必須完整包含的 edit（tag 關鍵字）；need_src：必須逐字保留的原始子路徑；
#   label：代號雕刻 (字高, 偏好位置 (a,b), 角度候選)
# ---------------------------------------------------------------------------
CROPS = [
    dict(id='TA-#24', src='#24', grp='TA', axes=('U', 'V'), rect=(142.0, 250.0, -5.0, 105.0),
         search={'a0': (140.5, 146.0)}, minus=[(235.5, 260.0, 98.0, 130.0)], bridge=4.0,
         need_tags=('S10 階梯窗', 'S50 開底缺口', 'S50 插銷孔', 'TM1637 顯示窗', 'TM1637 M2'),
         need_src=('rect2[12]', 'rect2[14]', 'path4[0]', 'path5[0]', 'path8[0]', 'path10[0]', 'path11[0]',
                   'path12[0]', 'path15[0]', 'path16[0]', 'path17[0]'),
         need_eng=('path1-5-9', 'text1-6-4', 'text2-1-3', 'text11-4-1'),
         label=(4.0, (172.0, 12.0), (-90.0, 0.0)),
         name='#24 前面板左段（S10／S50 感測窗、顯示窗、Logo）'),
    dict(id='TA-#26', src='#26', grp='TA', axes=('U', 'V'), rect=(142.0, 250.0, -5.0, 101.0), link='TA-#24',
         need_tags=('S10 階梯窗', 'S10 光孔', 'S50 開底缺口', 'S50 光孔', '#6 新小榫槽', 'L 形缺口'),
         need_src=('path131[2]', 'path131[5]', 'path131[10]', 'path131[13]', 'path131[18]', 'path131[25]'),
         label=(4.0, (152.0, 27.0), (-90.0, 0.0)),
         name='#26 內牆左段（10／50 元開口、S10／S50 窗與光孔、L 形缺口）'),
    dict(id='TA-#37', src='#37', grp='TA', axes=('U', 'V'), rect=(141.0, 250.0, -5.0, 78.0),
         need_tags=('掛勾槽', '頂邊 U 形缺口'),
         need_src=('path509-6[6]', 'path509-6[7]'),
         label=(4.0, (217.0, 46.0), (90.0, 0.0)),
         name='#37 後面板左上段（掛勾槽、顯示器線缺口、#5／#6 後榫槽）'),
    dict(id='TB-#13R', src='#13R', frame='#13', grp='TB', axes=('W', 'V'),
         poly=[(-10.0, 25.0), (40.0, 25.0), (40.0, 79.4), (29.5, 79.4), (29.5, 83.5), (-10.0, 83.5)],
         need_tags=('牆槽',), need_src=(),
         label=(3.0, (15.0, 52.5), (-60.0, 0.0)),
         name='#13R 上段（加高牆、牆槽、前榫 F1／F2、後榫 B1）', group='S1-wall'),
    dict(id='TB-#26', src='#26', grp='TB', axes=('U', 'V'), rect=(92.0, 112.0, 48.0, 80.0),
         need_tags=('槽 F1', '槽 F2', '槽 C'), need_src=(),
         label=(2.5, (96.8, 64.0), (0.0, -90.0)),
         name='#26 局部（S1 槽 F1、F2、C）'),
    dict(id='TB-#37', src='#37', grp='TB', axes=('U', 'V'), rect=(85.5, 127.0, 32.0, 86.0),
         need_tags=('卡匣窗', '槽 B1', 'M3 孔', '感測器線孔'), need_src=(),
         label=(3.0, (118.0, 38.5), (90.0, 0.0)),
         name='#37 局部（S1 卡匣窗、槽 B1、M3 孔）'),
]
FULL = [   # 整片沿用 v2 零件、只加代號
    dict(id='TA-#5', src='#5', grp='TA', label=(3.0, (20.0, 33.0), (0.0, 90.0)), name='#5 v2 間隔條（10|50）整片（只多雕代號，試切過可以裝到整台）'),
    dict(id='TA-#6', src='#6', grp='TA', label=(3.0, (20.0, 33.0), (0.0, 90.0)), name='#6 v2 間隔條（5|10）整片（只多雕代號，試切過可以裝到整台）'),
]
NEW_KEEP = {   # v2 新零件，原樣放進小樣
    'TA': ('P1-S10', 'C1-S10', 'P1-S50', 'C1-S50', 'PIN-S50',
           'EB-WL', 'EB-WR', 'EB-B', 'EB-T', 'EB-S', 'EB-F', 'EB-E', 'EB-K'),
    'TB': ('S1-B', 'S1-C', 'S1-H', 'S1-F', 'S1-P'),
}


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------
def _row(name, ok, value='', expected='', note='', piece=''):
    if isinstance(value, (float, np.floating)):
        value = round(float(value), 3)
    return dict(piece=piece, name=name, ok=None if ok is None else bool(ok), value=value, expected=expected, note=note)


def _polys(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g] if g.area > 0 else []
    out = []
    for h in getattr(g, 'geoms', []):
        out.extend(_polys(h))
    return out


def _orig(p) -> str:
    return getattr(p, 'orig_id', None) or p.id


def _elem_d(elem: str) -> str | None:
    m = re.search(r'\bd="([^"]*)"', elem)
    return m.group(1) if m else None


def _d_bbox(d: str):
    x0, x1, y0, y1 = parse_path(d).bbox()
    return (x0, y0, x1, y1)


def _opening(G, r: float):
    return G.buffer(-r, join_style=2, mitre_limit=10).buffer(r, join_style=2, mitre_limit=10)


def _plane(frame_id: str):
    """零件板面：(擠出軸 index, 板面 z=0 那面的座標)。"""
    fr = F.frame(frame_id)
    k = int(np.argmax(np.abs(fr.T[:3, 2])))
    return k, float(fr.to_asm(0.0, 0.0, 0.0)[k])


def asm_to_page_geom(frame_id: str, axes, g):
    """組裝座標兩軸上的多邊形 → 零件頁座標多邊形（板面 z=0 處；只用在板面平行兩軸的零件）。"""
    fr = F.frame(frame_id)
    k, w = _plane(frame_id)
    i, j = F.AX[axes[0]], F.AX[axes[1]]
    if {i, j, k} != {0, 1, 2}:
        raise ValueError(f'{frame_id} 的板面不平行 {axes}')

    def ring(coords):
        C_ = np.array(coords)
        A = np.zeros((len(C_), 3))
        A[:, i], A[:, j], A[:, k] = C_[:, 0], C_[:, 1], w
        P = fr.to_page(A[:, 0], A[:, 1], A[:, 2])
        return P[:, :2]
    out = []
    for p in _polys(g):
        out.append(Polygon(ring(p.exterior.coords), [ring(r.coords) for r in p.interiors]))
    return out[0] if len(out) == 1 else unary_union(out)


def page_to_asm_geom(frame_id: str, axes, g):
    return F.frame(frame_id).geom_asm(g, 0.0, axes)


def _vertex_coords(part) -> tuple[np.ndarray, np.ndarray]:
    xs, ys = [], []
    for d in part.cut_d:
        for s in parse_path(d):
            for z in (s.start, s.end):
                xs.append(z.real)
                ys.append(z.imag)
    return np.unique(np.round(xs, 6)), np.unique(np.round(ys, 6))


def _snap(g, xs, ys, tol=SNAP):
    """多邊形頂點座標離零件頂點座標 < tol 就對齊（讓裁切線和零件原有邊精確共線，不留細縫）。"""
    def f(v, arr):
        k = np.searchsorted(arr, v)
        best = v
        for q in (k - 1, k):
            if 0 <= q < len(arr) and abs(arr[q] - v) < tol and abs(arr[q] - v) < abs(best - v) + tol:
                best = float(arr[q])
        return best

    def ring(coords):
        return [(f(x, xs), f(y, ys)) for x, y in coords]
    return Polygon(ring(g.exterior.coords), [ring(r.coords) for r in g.interiors])


# ---------------------------------------------------------------------------
# 代號雕刻：自動找位置
# ---------------------------------------------------------------------------
def _text_box0(text, size, angle):
    d = textpath.text_to_d(text, 0.0, 0.0, size, angle, 'middle')
    return _d_bbox(d)


def place_label(geom, eng_boxes, text, size, prefer_xy, angles, clear=LABEL_CLEAR, step=0.5, sizes=None):
    """在零件材料上找放得下代號的位置 → dict(x, y, size, angle)；找不到回傳 None。
    條件：文字外框外擴 clear 後完全在材料內（不壓孔），且離其他雕刻外框 ≥ clear；偏好位置最近者優先。"""
    sizes = sizes or [size, size * 0.85, size * 0.7, max(1.8, size * 0.55)]
    inner = geom.buffer(-clear, join_style=2)
    if inner.is_empty:
        return None
    obst = unary_union([box(*b).buffer(clear, join_style=2) for b in eng_boxes]) if eng_boxes else None
    shapely.prepare(inner)
    if obst is not None:
        shapely.prepare(obst)
    x0, y0, x1, y1 = geom.bounds
    xs = np.arange(x0, x1 + step, step)
    ys = np.arange(y0, y1 + step, step)
    X_, Y_ = np.meshgrid(xs, ys)
    X_, Y_ = X_.ravel(), Y_.ravel()
    px, py = prefer_xy
    order = np.argsort((X_ - px) ** 2 + (Y_ - py) ** 2, kind='stable')
    X_, Y_ = X_[order], Y_[order]
    for sz in sizes:
        for ang in angles:
            bx0, by0, bx1, by1 = _text_box0(text, sz, ang)
            boxes = shapely.box(X_ + bx0, Y_ + by0, X_ + bx1, Y_ + by1)
            ok = shapely.contains(inner, boxes)
            if obst is not None:
                ok &= ~shapely.intersects(obst, boxes)
            hit = np.nonzero(ok)[0]
            if len(hit):
                k = int(hit[0])
                return dict(x=float(X_[k]), y=float(Y_[k]), size=float(sz), angle=float(ang))
    return None


def _eng_boxes(part) -> list[tuple]:
    out = []
    for e in part.engrave:
        d = _elem_d(e)
        if d:
            out.append(_d_bbox(d))
    return out


def _label_edit(part, text, lab, frame_id=None, axes=None) -> dict:
    size, prefer, angles = lab
    if frame_id is not None:
        pg = asm_to_page_geom(frame_id, axes, Point(prefer).buffer(0.01))
        prefer_xy = (pg.centroid.x, pg.centroid.y)
    else:
        prefer_xy = prefer
    pos = place_label(part.geom, _eng_boxes(part), text, size, prefer_xy, angles)
    if pos is None:
        raise RuntimeError(f'{text}：零件上找不到放代號的位置')
    return dict(op='add_engrave_text', part=part.id, text=text, x=pos['x'], y=pos['y'], size=pos['size'],
                angle=pos['angle'], anchor='middle', tag=f'試切代號「{text}」', _sys=SYS, _k=99)


# ---------------------------------------------------------------------------
# 裁切
# ---------------------------------------------------------------------------
def _region_asm(spec: dict, a0: float | None = None):
    if spec.get('poly'):
        reg = Polygon(spec['poly'])
    else:
        r0, r1, b0, b1 = spec['rect']
        if a0 is not None:
            r0 = a0
        reg = box(r0, b0, r1, b1)
    for m in spec.get('minus', ()):
        reg = reg.difference(box(m[0], m[2], m[1], m[3]))
    return reg


class TrialInfeasible(RuntimeError):
    """目前參數下排不出試切小樣（例如感測座窗移到 TA 右緣的搜尋範圍裡）。build_trial／run 會把它記成檢查未通過。"""


def _bridge_asm(spec: dict, part_uv, a0: float):
    """TA-#24 連接條：把 a0～a0+w 之間的斜槽補實（只補斜槽那一段，不碰別的孔）。
    斜槽＝零件最大的孔，要橫跨整條連接條，否則丟 RuntimeError（_search_a0 會把這個位置當成不可行，換下一個）。
    連接條矩形碰到別的孔（例如翼朝下游時移過來的 S5 窗）就把那些孔扣掉，孔保持原樣。"""
    w = spec.get('bridge')
    if not w:
        return None
    band = box(a0 - 1.0, -50.0, a0 + w, 200.0)
    holes = [Polygon(r) for r in part_uv.interiors]
    if not holes:
        raise RuntimeError(f'{spec["id"]}：零件沒有孔，找不到斜槽')
    slot = max(holes, key=lambda h: h.area)
    if not (slot.intersects(band) and slot.bounds[0] < a0 and slot.bounds[2] > a0 + w):
        raise RuntimeError(f'{spec["id"]}：連接條位置 U{a0:.1f}～{a0 + w:.1f} 沒有整段落在斜槽上')
    hb = slot.intersection(band).bounds
    br = box(a0 - 1.0, hb[1] - 2.0, a0 + w, hb[3] + 2.0)
    other = [h for h in holes if h is not slot and h.intersects(br)]
    if other:
        br = br.difference(unary_union(other))
        if br.geom_type != 'Polygon':
            br = max(_polys(br), key=lambda q: q.area)
    return br


def _new_narrow(geom0, geom1, near, r: float) -> float:
    """geom1（裁切後）在 near 附近、比 2r 窄、而且 geom0（裁切前）原本不窄的料面積。
    先裁到 near 外擴 2r+2 的範圍再算（快很多；裁出來的假邊離 near ≥2r+2，不影響結果）。"""
    clip = near.buffer(2 * r + 2.0)
    g1, g0 = geom1.intersection(clip), geom0.intersection(clip)
    n1 = g1.difference(_opening(g1, r)).intersection(near)
    n0 = g0.difference(_opening(g0, r)).buffer(0.05)
    return sum(p.area for p in _polys(n1.difference(n0)))


def _crop_web(geom0_pg, region_pg, edge_near, r=MIN_WEB / 2) -> float:
    piece = geom0_pg.intersection(region_pg)
    piece = max(_polys(piece), key=lambda q: q.area) if _polys(piece) else Polygon()
    return _new_narrow(geom0_pg, piece, edge_near, r), piece


def _min_width_near(piece, geom0, near, lo=0.2, hi=6.0) -> float:
    """裁切邊附近新增料的最小寬度（opening 二分搜尋，0.05 mm）。"""
    if _new_narrow(geom0, piece, near, lo / 2) > 0.01:
        return lo
    if _new_narrow(geom0, piece, near, hi / 2) <= 0.01:
        return hi
    a, b = lo, hi
    while b - a > 0.05:
        m = (a + b) / 2
        if _new_narrow(geom0, piece, near, m / 2) > 0.01:
            b = m
        else:
            a = m
    return round(a, 2)


def _search_a0(specs, parts_by, frame_of) -> tuple[float | None, str]:
    """在 search 範圍內（0.1 mm 一步）找裁切線：所有共用的零件都不新增 <MIN_WEB 細料、連接條只補斜槽；
    有多個就取最靠近預設值。回傳 (a0, '')；全部不可行時回傳 (None, 原因)，不丟例外（由呼叫端記成檢查未通過）。"""
    lead = specs[0]
    lo, hi = lead['search']['a0']
    pref = lead['rect'][0]
    cands = sorted(np.round(np.arange(lo, hi + 1e-9, 0.1), 2), key=lambda v: (abs(v - pref), v))
    why = {}
    for a0 in cands:
        ok = True
        for s in specs:
            p = parts_by[s['src']]
            fid = frame_of(s)
            reg = asm_to_page_geom(fid, s['axes'], _region_asm(s, a0))
            line = asm_to_page_geom(fid, s['axes'], box(a0 - 0.01, -50, a0 + 0.01, 200))
            try:
                br = _bridge_asm(s, page_to_asm_geom(fid, s['axes'], p.geom), a0) if s.get('bridge') else None
            except RuntimeError as e:          # 這個位置補不了連接條 → 換下一個
                why.setdefault('連接條', (a0, str(e)))
                ok = False
                break
            g0 = p.geom.union(asm_to_page_geom(fid, s['axes'], br)) if br is not None else p.geom
            area, _ = _crop_web(g0, reg, line.buffer(MIN_WEB + 1.0))
            if area > 0.01:
                why.setdefault(f'{s["id"]} 細料', (a0, f'{s["id"]} 在 U{a0:g} 裁切會留下 <{MIN_WEB:g} mm 細料 {area:.2f} mm²'))
                ok = False
                break
        if ok:
            return float(a0), ''
    detail = '；'.join(f'例：{v[1]}' for v in why.values())
    return None, (f'{lead["id"]}：U{lo:g}～{hi:g} 之間找不到可行的右緣裁切線（不留 <{MIN_WEB:g} mm 細料、連接條只補斜槽）'
                  f'；{detail}。感測座窗可能移進了這個範圍（例如 params.MODULE 的 wing 或模組尺寸改了），'
                  '要調整 trial.CROPS 的 rect／search')


def crop_piece(spec: dict, part, a0: float | None = None):
    """依裁切件定義從最終零件裁出一片 → (V2Part, info dict)。"""
    fid = spec.get('frame', spec['src'])
    axes = spec['axes']
    reg_asm = _region_asm(spec, a0)
    reg = asm_to_page_geom(fid, axes, reg_asm)
    xs, ys = _vertex_coords(part)
    reg = _snap(reg, xs, ys)
    big = box(*part.geom.bounds).buffer(10.0)
    edits = [dict(op='subtract', part=part.id, geom=big.difference(reg), tag='試切裁切（範圍外去掉）', _sys=SYS, _k=0)]
    bridge_pg = None
    if spec.get('bridge'):
        br = _bridge_asm(spec, page_to_asm_geom(fid, axes, part.geom), a0 if a0 is not None else spec['rect'][0])
        bridge_pg = asm_to_page_geom(fid, axes, br)
        edits.insert(0, dict(op='union', part=part.id, geom=bridge_pg, tag='試切連接條（補斜槽右端，實機沒有）',
                             _sys=SYS, _k=1))
    dropped = []
    keep_reg = reg.buffer(-ENG_KEEP_MARGIN)
    for e, s in zip(part.engrave, part.engrave_src):
        d = _elem_d(e)
        if d is None:
            continue
        if not box(*_d_bbox(d)).within(keep_reg):
            inside = box(*_d_bbox(d)).intersects(reg)
            edits.append(dict(op='delete_engrave', part=part.id, src=s, tag='試切：刪掉範圍外的雕刻', _sys=SYS, _k=2))
            if inside:
                dropped.append(s)
    v1 = C._apply_part(part, edits, spec['name'])
    lab = _label_edit(v1, spec['id'], spec['label'], fid, axes)
    v = C._apply_part(v1, [lab], spec['name'])
    v.warnings = list(v1.warnings) + list(v.warnings)
    v.applied = list(v1.applied) + list(v.applied)
    v.cut_src = [re.sub(r'\*{2,}', '*', q) for q in v.cut_src]   # 已重生過的子路徑再重生：src 結尾只留一個 *
    g0 = part.geom.union(bridge_pg) if bridge_pg is not None else part.geom
    v = dataclasses.replace(v, id=spec['id'], name=spec['name'], layer='modified', qty=1, group=spec.get('group'),
                            tags=[f'試切小樣：{part.id} 裁切'] + ([f'右端補 {spec["bridge"]:g} mm 連接條'] if bridge_pg else []),
                            orig_id=_orig(part))
    info = dict(spec=spec, src_part=part, region_pg=reg, region_asm=reg_asm, bridge_pg=bridge_pg, g0=g0,
                dropped=dropped, a0=a0, frame=fid, label=lab)
    return v, info


def full_piece(spec: dict, part):
    fid = spec['src']
    lab = _label_edit(part, spec['id'], spec['label'], fid, ('W', 'V'))
    v = C._apply_part(part, [lab], spec['name'])
    v = dataclasses.replace(v, id=spec['id'], name=spec['name'], layer='modified', qty=1,
                            tags=[f'試切小樣：{part.id} 整片'], orig_id=_orig(part))
    return v, dict(spec=spec, src_part=part, label=lab, frame=fid)


# ---------------------------------------------------------------------------
# 試切輔助件
# ---------------------------------------------------------------------------
def _bottom_V(piece_info, U: float) -> float:
    """TA 裁切件在某個 U 的下緣 V（組裝座標）。"""
    g = page_to_asm_geom(piece_info['frame'], ('U', 'V'), piece_info['piece'].geom)
    ln = LineString([(U, -50), (U, 200)]).intersection(g)
    return float(ln.bounds[3])


def stand_geom(v_front: float, v37: float) -> Polygon:
    """支架 TA-ST 在 (W',V) 平面的外形。底邊水平（V＋tan30°·W'＝常數；frames：機身後仰 30°）。"""
    k = math.tan(math.radians(30.0))
    f = ST_FIT
    t = params.T_PLY
    w0, w1 = F.W24[0] - f, F.W24[0] + 2 * t + f              # 前槽：#24 前面～#26 背面（兩片板厚）
    a0, a1 = F.W37_IN - f, F.W37_IN + t + f                  # 後槽：#37
    vt = v_front - ST_SLOT                                   # 前槽口
    vt37 = v37 - ST_SLOT                                     # 後槽口
    K = max(v_front + ST_BASE_GAP + k * w1, v37 + ST_BASE_GAP + k * a1)   # 底邊
    base = lambda w: K - k * w
    beam = lambda w: base(w) - ST_BEAM
    w_post = a0 - 8.9                                         # 橫樑接到後柱的位置
    pts = [(w0 - ST_LIP, vt), (w0, vt), (w0, v_front), (w1, v_front), (w1, min(vt, beam(w1))),
           (w_post, beam(w_post)), (a0, vt37), (a0, v37), (a1, v37), (a1, vt37), (a1 + ST_LIP, vt37),
           (a1 + ST_LIP, base(a1 + ST_LIP) - ST_TAIL_H), (ST_TAIL_W, base(ST_TAIL_W) - ST_TAIL_H),
           (ST_TAIL_W, base(ST_TAIL_W)), (w0 - ST_LIP, base(w0 - ST_LIP))]
    g = Polygon(pts)
    if not g.is_valid:
        raise RuntimeError(f'支架外形不合法：{shapely.is_valid_reason(g)}')
    return g


def aux_parts(info_by: dict, a0: float) -> tuple[list, dict]:
    """支架 TA-ST×2、定位銷 TA-PIN×2 → (V2Part list, 說明 dict)。"""
    U_r = a0
    U_l = ST_U_LEFT
    vf = {}
    for side, U in (('右', U_r + 1.5), ('左', U_l + 1.0)):
        v24 = _bottom_V(info_by['TA-#24'], U)
        v26 = _bottom_V(info_by['TA-#26'], U)
        vf[side] = (v24, v26)
    v_all = [v for pair in vf.values() for v in pair]
    if max(v_all) - min(v_all) > 0.05:
        raise RuntimeError(f'支架位置 #24／#26 下緣不齊：{vf}')
    v_front = float(np.mean(v_all))
    v37 = float(CROPS[[c['id'] for c in CROPS].index('TA-#37')]['rect'][3])
    g = stand_geom(v_front, v37)
    x0, y0 = g.bounds[0], g.bounds[1]
    loc = affinity.translate(g, -x0, -y0)
    spec = dict(id='TA-ST', name='試切支架（夾 #24＋#26 下緣、托 TA-#37 下緣；面板照實機後仰 30°）', material='合板',
                qty=2, geom=loc, tag='試切輔助件（實機沒有）')
    st = C._new_part(spec, SYS)
    c = loc.centroid
    lab = _label_edit(st, 'TA-ST', (3.0, (c.x, c.y), (0.0, -30.0, 90.0)))
    lab['part'] = st.id
    st = C._apply_part(st, [lab], spec['name'])
    st = dataclasses.replace(st, id='TA-ST', name=spec['name'], layer='new', qty=2, tags=[spec['tag']],
                             orig_id=None, group=None)
    # 定位銷：#21 齒孔（TA-#24 rect2[12]）的 V 高 − 0.1
    p24 = info_by['TA-#24']['src_part']
    hole = p24.cut_d[p24.cut_src.index('rect2[12]')]
    hb = page_to_asm_geom('#24', ('U', 'V'), box(*_d_bbox(hole))).bounds
    pin_w = round(hb[3] - hb[1] - 0.1, 2)
    pin = C._new_part(dict(id='TA-PIN', name='試切定位銷（穿 TA-#24、TA-#26 左下 #21 齒孔）', material='合板', qty=2,
                           geom=box(0, 0, PIN_LEN, pin_w), tag='試切輔助件（實機沒有）'), SYS)
    pin = dataclasses.replace(pin, layer='new', tags=['試切輔助件（實機沒有）'])
    info = dict(U=dict(右=(U_r, U_r + F.T_BOARD), 左=(U_l, U_l + F.T_BOARD)), v_front=v_front, v37=v37,
                stand_asm=g, pin=(PIN_LEN, pin_w), hole_uv=hb, K=None)
    return [st, pin], info


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def build_trial(parts: list, results: dict) -> tuple[list, dict]:
    """最終零件 → 試切件（list[V2Part]）與各片資訊。"""
    by_orig = {_orig(p): p for p in parts if getattr(p, 'layer', 'original') != 'new'}
    by_id = {p.id: p for p in parts}
    parts_by = {}
    for s in CROPS + FULL:
        p = by_id.get(s['src']) or by_orig.get(s['src'])
        if p is None:
            raise KeyError(f'最終零件裡找不到 {s["src"]}')
        parts_by[s['src']] = p
    frame_of = lambda s: s.get('frame', s['src'])
    # 搜尋 TA 右緣（TA-#24、TA-#26 共用）
    a0 = None
    lead = [s for s in CROPS if s.get('search')]
    a0s = {}
    for s in lead:
        grp = [s] + [t for t in CROPS if t.get('link') == s['id']]
        a0, why = _search_a0(grp, parts_by, frame_of)
        if a0 is None:
            raise TrialInfeasible(why)
        a0s[s['id']] = a0
        for t in grp[1:]:
            a0s[t['id']] = a0s[s['id']]
    out, info_by = [], {}
    for s in CROPS:
        a0 = a0s.get(s['id'])
        v, info = crop_piece(s, parts_by[s['src']], a0)
        info['piece'] = v
        info_by[s['id']] = info
        out.append(v)
    for s in FULL:
        v, info = full_piece(s, parts_by[s['src']])
        info['piece'] = v
        info_by[s['id']] = info
        out.append(v)
    for grp, ids in NEW_KEEP.items():
        for pid in ids:
            p = by_id.get(pid)
            if p is None:
                raise KeyError(f'最終零件裡找不到新零件 {pid}')
            q = dataclasses.replace(p, cut_d=list(p.cut_d), engrave=list(p.engrave), tags=list(p.tags))
            if pid == 'S1-B':
                q.group = 'S1-wall'          # 和 TB-#13R 同板（牆面齊平）
            out.append(q)
            info_by[pid] = dict(piece=q, grp=grp)
    a0_ta = a0s.get('TA-#24', CROPS[0]['rect'][0])
    aux, ainfo = aux_parts(info_by, a0_ta)
    out.extend(aux)
    for q in aux:
        info_by[q.id] = dict(piece=q, grp='TA')
    return out, dict(info=info_by, a0=a0s, aux=ainfo)


# ---------------------------------------------------------------------------
# 檢查
# ---------------------------------------------------------------------------
def _edit_regions(results: dict, src_part_id: str, orig_part) -> list[tuple[str, object]]:
    """各子系統對某零件的 subtract 區域（頁座標，edit 原樣）與 tag；translate_cut 的區域是 None。"""
    rev = {}
    for r in results.values():
        for old, new in (r.get('renames') or {}).items():
            rev[new] = old
    out = []
    for r in results.values():
        for e in r.get('edits', []):
            pid = rev.get(e['part'], e['part'])
            if pid != src_part_id:
                continue
            if e['op'] == 'subtract':
                out.append((e.get('tag') or '', e['geom']))
            elif e['op'] == 'translate_cut':
                out.append((e.get('tag') or '', None))
    return out


def check_pieces(tinfo: dict, results: dict) -> list[dict]:
    rows = []
    info_by = tinfo['info']
    for s in CROPS:
        I = info_by[s['id']]
        v, p, reg = I['piece'], I['src_part'], I['region_pg']
        pid = s['id']
        n = len([q for q in _polys(v.geom) if q.area >= 0.01])
        rows.append(_row('單一連通', n == 1, n, 1, piece=pid))
        ref = I['g0'].intersection(reg)
        sd = v.geom.symmetric_difference(ref).area
        rows.append(_row('外形＝最終零件∩裁切範圍' + ('＋連接條' if I['bridge_pg'] is not None else ''),
                         sd < 0.01, round(sd, 4), '<0.01 mm²', piece=pid))
        # 裁切邊細料
        edge = reg.exterior.intersection(Polygon(p.geom.exterior).buffer(0.01))
        near = edge.buffer(MIN_WEB + 1.0)
        if I['bridge_pg'] is not None:
            near = near.union(I['bridge_pg'].buffer(MIN_WEB + 1.0))
        area = _new_narrow(I['g0'], v.geom, near, MIN_WEB / 2)
        w = _min_width_near(v.geom, I['g0'], near)
        rows.append(_row('裁切邊不新增細料', area <= 0.01, f'裁切邊附近新增料最窄約 {w:g} mm', f'≥{MIN_WEB:g} mm',
                         note='' if area <= 0.01 else f'比 {MIN_WEB:g} mm 窄的料 {area:.2f} mm²', piece=pid))
        # 範圍內的切割逐字保留
        kept, regen = 0, []
        vset = set(v.cut_d)
        inner = reg.buffer(-0.05)
        for d, src in zip(p.cut_d[1:], p.cut_src[1:]):
            gb = box(*_d_bbox(d))
            if gb.within(inner) and not (I['bridge_pg'] is not None and gb.intersects(I['bridge_pg'])):
                if d in vset:
                    kept += 1
                else:
                    regen.append(src)
        rows.append(_row('範圍內的孔／窗逐字保留', not regen, f'{kept} 個', '全部',
                         note=('重生：' + '、'.join(regen)) if regen else '', piece=pid))
        # 必要特徵：各子系統對這片的 edit（依 tag 找），連同周圍 1 mm 的料都和最終零件相同
        regs = _edit_regions(results, _orig(p), p)
        missing = []
        for key in s.get('need_tags', ()):
            hits = [g for t, g in regs if key in t and g is not None and not g.is_empty]
            if not hits:
                missing.append(f'{key}（找不到這個 edit）')
                continue
            for g in hits:
                zone = g.buffer(1.0)
                sd = I['g0'].intersection(zone).symmetric_difference(v.geom.intersection(zone)).area
                if sd > 0.01:
                    missing.append(f'{key}（被裁到，差 {sd:.2f} mm²）')
                    break
        for src in s.get('need_src', ()):
            if src not in p.cut_src:
                missing.append(f'{src}（最終零件沒有）')
                continue
            if p.cut_d[p.cut_src.index(src)] not in vset:
                missing.append(f'{src}（被裁到或不在範圍內）')
        for src in s.get('need_eng', ()):
            if src not in v.engrave_src:
                missing.append(f'雕刻 {src}（被刪掉）')
        need = list(s.get('need_tags', ())) + list(s.get('need_src', ())) + list(s.get('need_eng', ()))
        rows.append(_row('必要特徵完整', not missing, f'{len(need) - len(missing)}/{len(need)}', '全部',
                         note='；'.join(missing) if missing else '、'.join(need), piece=pid))
        if I['dropped']:
            rows.append(_row('刪掉的雕刻（部分在範圍外）', None, '、'.join(I['dropped']), '', piece=pid))
        if v.warnings:
            rows.append(_row('合成警告', None, len(v.warnings), '', note='；'.join(v.warnings), piece=pid))
    # TA-#24 軌道逐點
    I = info_by['TA-#24']
    p = I['src_part']
    src_slot = [k for k in p.cut_src if k.startswith('rect2[1]')]
    if src_slot:
        d = p.cut_d[p.cut_src.index(src_slot[0])]
        pts = np.array([[z.real, z.imag] for seg in parse_path(d) for z in
                        (seg.point(t) for t in np.linspace(0, 1, 60))])
        uv = F.frame('#24').to_asm(pts[:, 0], pts[:, 1], 0.0)
        a0 = tinfo['a0'].get('TA-#24')
        sel = (uv[:, 0] > a0 + CROPS[0]['bridge'] + 1.0) & (uv[:, 0] < 233.0) & (uv[:, 1] > F.rail_V(uv[:, 0]) - 1.5)
        bd = I['piece'].geom.boundary
        dev = max((bd.distance(Point(q)) for q in pts[sel]), default=float('nan'))
        rows.append(_row('斜槽軌道（下緣）逐點相同', dev <= POINT_TOL, f'{dev:.4f} mm（{int(sel.sum())} 點）',
                         f'≤{POINT_TOL}', note=f'U{a0 + CROPS[0]["bridge"]:.1f}～234，硬幣可以滾過 S10、S50 兩站',
                         piece='TA-#24'))
    # 支架
    A = tinfo['aux']
    k = math.tan(math.radians(30.0))
    g = A['stand_asm']
    C_ = np.array(g.exterior.coords)
    base_pts = C_[np.argsort(C_[:, 1] + k * C_[:, 0])[-2:]]
    tilt = math.degrees(math.atan2(base_pts[1, 1] - base_pts[0, 1], base_pts[1, 0] - base_pts[0, 0]))
    rows.append(_row('支架底邊水平（面板後仰 30°）', abs(abs(tilt) % 180 - 30.0) < 0.05 or abs(abs(tilt) % 180 - 150.0) < 0.05,
                     f'底邊在 (W\',V) 的斜率角 {tilt:.2f}°', '±30°（V＋tan30°·W\'＝常數）', piece='TA-ST'))
    hooks = []
    for t, gg in _edit_regions(results, '#37', info_by['TA-#37']['src_part']):
        if '掛勾槽' in t and gg is not None:
            hooks.append(page_to_asm_geom('#37', ('U', 'V'), gg).bounds)
    # 感測座：模組在窗的 (U,V) 範圍內上下滑（W' 在 PCB 前後緣之間），蓋板 C1 在 #24 前方、比窗大 cap_m
    M = tinfo.get('ct_model')
    zones = []
    if M is not None:
        Wp = M['D']['W_pcb']
        cap = M['P']['cap_m'] + M['P']['fit']
        for k, R in M['S'].items():
            zones.append((f'{k} 模組', R['win'], (Wp[0] - 0.5, Wp[1] + M['P']['c_stop'])))
            zones.append((f'{k} 蓋板 C1', R['win'].buffer(cap, join_style=2), (F.W24[0] - F.T_BOARD, F.W24[0])))
    for side, (u0, u1) in A['U'].items():
        dh = min((max(h[0] - u1, u0 - h[2]) for h in hooks), default=float('nan'))
        rows.append(_row(f'{side}支架 U{u0:g}～{u1:g} 離電子盒掛勾槽（牆）', dh >= 0.5, round(dh, 2), '≥0.5',
                         note='電子盒牆在掛勾槽內，支架在盒子外側', piece='TA-ST'))
        if not zones:
            rows.append(_row(f'{side}支架離感測座', None, '沒有 crosstrack 模型，略過', '', piece='TA-ST'))
            continue
        best = None
        for name, uv, (wa, wb) in zones:
            sec = A['stand_asm'].intersection(box(wa, -500, wb, 500))
            if sec.is_empty:
                continue
            vb = sec.bounds
            foot = box(u0, vb[1], u1, vb[3])           # 支架在這段 W' 內的 (U,V) 投影（保守取外包）
            dd = foot.distance(uv)
            if best is None or dd < best[0]:
                best = (dd, name)
        rows.append(_row(f'{side}支架離感測座（模組上下滑的範圍、蓋板）', best[0] >= 0.5, round(best[0], 2), '≥0.5',
                         note=f"最近：{best[1]}（同一段 W' 內比 (U,V) 距離）", piece='TA-ST'))
    rows += _stability_rows(tinfo)
    rows.append(_row('支架前槽／後槽', None, f'#24＋#26 下緣 V{A["v_front"]:.2f}、TA-#37 下緣 V{A["v37"]:g}',
                     '', note=f'槽寬 {params.T_PLY * 2 + 2 * ST_FIT:g}／{params.T_PLY + 2 * ST_FIT:g}（params.T_PLY、C_TAB）、'
                               f'深 {ST_SLOT:g}', piece='TA-ST'))
    ub = A['hole_uv']
    rows.append(_row('定位銷對 #21 齒孔', A['pin'][1] < ub[3] - ub[1], f'銷寬 {A["pin"][1]:g}（板厚 {params.T_PLY:g}）',
                     f'孔 {ub[2] - ub[0]:.2f}×{ub[3] - ub[1]:.2f}', piece='TA-PIN'))
    return rows


RHO = {'椴木合板': 0.55, 'MDF': 0.75}   # g/cm³（粗估）
STAB_MARGIN = 5.0                      # mm：重心離支架底邊兩端至少這麼多


def _stability_rows(tinfo) -> list[dict]:
    """TA 組站在支架上會不會倒（粗估）：重心的世界前後位置 Z＝−0.5V＋0.866W'（frames：機身後仰 30°）
    要落在支架底邊兩端之間。板件用面積×板厚×密度；電池、擴展板位置照 ebox spec c-5，模組、TM1637 估計。"""
    from . import ebox
    info_by = tinfo['info']
    k = math.tan(math.radians(30.0))
    g = tinfo['aux']['stand_asm']
    C_ = np.array(g.exterior.coords)[:-1]
    on_base = C_[np.abs((C_[:, 1] + k * C_[:, 0]) - (C_[:, 1] + k * C_[:, 0]).max()) < 1e-6]
    Zs = -0.5 * on_base[:, 1] + 0.866 * on_base[:, 0]
    zf, zb = float(Zs.min()), float(Zs.max())
    plates = []
    for pid in ('TA-#24', 'TA-#26', 'TA-#37', 'TA-#5', 'TA-#6'):
        I = info_by[pid]
        c = I['piece'].geom.centroid
        U, V, W = F.frame(I['frame']).to_asm(c.x, c.y, F.T_BOARD / 2)
        plates.append((I['piece'].geom.area * F.T_BOARD / 1000.0, (U, V, W)))
    eb_area = sum(info_by[q]['piece'].geom.area * int(info_by[q]['piece'].qty or 1)
                  for q in info_by if q.startswith('EB-'))
    B = ebox.BOX
    hw = info_by['EB-WL']['piece'].geom.bounds
    box_c = ((B['U_WL'] + B['U_WR'] + F.T_BOARD) / 2, B['V_top'] + (hw[3] - hw[1]) / 2, (B['W_front'] + B['W_back']) / 2)
    extras = [('9V 電池', 46.0, (212.5, 8.75, 45.5)), ('擴展板＋開發板', 35.0, (197.5, 48.5, 50.0))]
    M = tinfo.get('ct_model')
    front = [('TM1637', 8.0, (214.5, 17.5, -2.2))]
    if M is not None:
        for kk in ('S10', 'S50'):
            if kk in M['S']:
                bu = M['S'][kk]['beam_UV']
                front.append((f'{kk} 模組＋鎖塊', 6.0, (float(bu[0]), float(bu[1]) + 5.0, -6.0)))
    rows = []
    for label, with_box in (('不掛電子盒', False), ('掛上電子盒（含電池、擴展板）', True)):
        worst = None
        for mat, rho in RHO.items():
            ms = [(v * rho, p) for v, p in plates] + [(m, p) for _, m, p in front]
            if with_box:
                ms += [(eb_area * F.T_BOARD / 1000.0 * rho, box_c)] + [(m, p) for _, m, p in extras]
            mt = sum(m for m, _ in ms)
            Z = sum(m * (-0.5 * p[1] + 0.866 * p[2]) for m, p in ms) / mt
            margin = min(Z - zf, zb - Z)
            if worst is None or margin < worst[0]:
                worst = (margin, mat, Z, mt)
        rows.append(_row(f'TA 組站在支架上：{label}', worst[0] >= STAB_MARGIN,
                         f'重心 Z{worst[2]:.1f}，離支架底邊兩端（Z{zf:.1f}～{zb:.1f}）最少 {worst[0]:.1f} mm',
                         f'≥{STAB_MARGIN:g} mm', note=f'粗估：總重約 {worst[3]:.0f} g（{worst[1]}最不利）；'
                                                    "Z＝−0.5V＋0.866W'，往後為正", piece='TA-ST'))
    return rows


def check_layout(sheets, tparts) -> list[dict]:
    rows = []
    n = len(sheets)
    rows.append(_row('張數', n <= MAX_SHEETS, f'{n} 張', f'目標 1 張、最多 {MAX_SHEETS} 張'))
    where = {}
    for s in sheets:
        for pl in s.items:
            where.setdefault(pl.part.id, set()).add(s.no)
    groups = {}
    for p in tparts:
        if p.group:
            groups.setdefault(p.group, []).append(p.id)
    for gname, ids in groups.items():
        sh = set().union(*[where.get(i, set()) for i in ids])
        rows.append(_row(f'同板群組 {gname}', len(sh) == 1, '、'.join(f'第 {k} 張' for k in sorted(sh)), '同一張',
                         note='、'.join(ids)))
    return rows


# ---------------------------------------------------------------------------
# 輸出
# ---------------------------------------------------------------------------
COMMENT = ('分幣機 v2 試切小樣（laser_v2.trial 產生；改 laser_v2/params.py 後重跑 build_v2，請勿手改）。'
           '黑 0.2 mm＝切割、紅＝雕刻、綠＝註記（隱藏圖層，不切割）')


def write_outputs(sheets, tparts, out_root: Path, out_dir: Path, png: bool = True) -> dict:
    warn: list[str] = []
    svg = out_root / TRIAL_SVG
    svg.write_text(X._render(sheets, X.page_offsets(sheets), COMMENT, warn), encoding='utf-8')
    pngs = []
    if png:
        count = {}
        for s in sheets:
            count[s.material] = count.get(s.material, 0) + 1
        for s in sheets:
            f = out_dir / f'trial_{s.material}_{s.no}.png'
            X.preview_png(s, f, count[s.material])
            pngs.append(f)
    rows = qa.check(svg, parts=tparts)
    return dict(svg=svg, pngs=pngs, qa=rows, warnings=list(dict.fromkeys(warn)))


# ---------------------------------------------------------------------------
# 報告
# ---------------------------------------------------------------------------
def _md(s) -> str:
    return str(s).replace('|', '\\|').replace('<', '&lt;').replace('>', '&gt;').replace('\n', ' ')


def _extent(I) -> str:
    """裁切件實際範圍（組裝座標）。"""
    spec = I['spec']
    ax = {'U': 'U', 'V': 'V', 'W': "W'"}
    b = page_to_asm_geom(I['frame'], spec['axes'], I['piece'].geom).bounds
    return f"{ax[spec['axes'][0]]}{b[0]:.1f}～{b[2]:.1f} × {ax[spec['axes'][1]]}{b[1]:.1f}～{b[3]:.1f}"


def _rng(spec, a0) -> str:
    ax = {'U': 'U', 'V': 'V', 'W': "W'"}
    if spec.get('poly'):
        P = np.array(spec['poly'])
        return (f"{ax[spec['axes'][0]]}{P[:, 0].min():g}～{P[:, 0].max():g} × {ax[spec['axes'][1]]}"
                f"{P[:, 1].min():g}～{P[:, 1].max():g}（多邊形，避開 #37 板厚內的後上角）")
    r0, r1, b0, b1 = spec['rect']
    if a0 is not None:
        r0 = a0
    return f"{ax[spec['axes'][0]]}{r0:g}～{r1:g} × {ax[spec['axes'][1]]}{b0:g}～{b1:g}"


# 每片的測試說明：(要測什麼, 對應 spec T, 過關標準, 不過關改哪裡)
GUIDE = {
    'TA-#24': ('切縫；S10 保留條 2.3／肩部 3.2、S50 保留條有沒有燒斷或翹；S50 插銷孔；模組裝拆；TM1637 裝窗；'
               '之後當講師黏插銷的治具',
               'crosstrack T1、T2、T7、T8；ebox T1',
               '保留條完整、直尺貼上縫 ≤0.2；插銷 3×3 壓得進 2.9 孔、不鬆；模組「低位推入→上滑→塞鎖塊→放手」順'
               '（塞鎖塊＝P1 背面貼 #24 正面、在窗下方往上抬到凸塊碰 PCB 下面，再往後推 3 mm；用這個手法驗收），'
               '量 C1 頂到前臂底下焊點的實際餘隙（名目 0.3～0.5）；'
               '拔鎖塊（先往前拉 3 mm 再往下）後模組自己落回低位；LED 塊塞得進不晃、凸出約 4 mm、4 支 M2 鎖得上、'
               '螺絲頭不壓「10」；手指按 S10 保留條中央不斷',
               '保留條斷／翹：先 MDF、合板各切一次比較；仍斷→降 params.BEAM_H（定案 2.5，改前要問使用者）或 '
               'mods_crosstrack.DESIGN["g_strip"]。模組卡住→實量後改 params.MODULE（spec d-2 表：槽底頂保留條看 '
               'slot_d／arm_top／pcb_t，本體進不了窄段看 arm_w，PCB 碰窗看 pcb_W／body_e，零件頂到肩部看 comp_h）。'
               '塞鎖塊時 P1 凸塊撞到前臂底下的焊腳→是塞法不對（不可從模組前方直接水平推入，要照上面先抬再推），'
               '不是改參數；P1 推到位後焊點仍壓到 P1 其餘頂面→看 params.MODULE 的 back_h（P1 讓位深度跟著變）。'
               '顯示器→params.TM1637（hole_dx／hole_dy 是半距：孔中心離 PCB 中心，實量孔距要除以 2）'),
    'TA-#26': ('光孔兩側肉（S10 2.12、S50 2.30）、窗到開口唇 3.6／4.5 完整；L 形缺口放 TM1637 PCB、M2 螺帽、彎針、'
               '杜邦頭、上升線；放硬幣預演落幣（5 元落在 S10 翼上方、10 元落在 S50 翼上方）',
               'crosstrack T1、T2、T3 預演（R1、R3）；ebox T2',
               '光孔兩側沒有燒斷；顯示器的 PCB、杜邦頭、線放進缺口不被夾；硬幣滾過與落下不卡在翼或後臂上',
               '光孔肉斷→mods_crosstrack.DESIGN["lh_u"]、["delta_u"]；硬幣被後臂頂住→DESIGN["delta_u"] 改 −0.5'
               '（spec d-5）；卡在翼上→spec 備案（改分離式對射，待使用者決定）；缺口太緊→ebox.C_NOTCH、params.TM1637'),
    'TA-#37': ('電子盒兩層掛勾「抬、推、放」；顯示器線頂邊缺口；撐住 #5／#6 後榫',
               'ebox T3（T7 線路預演）',
               '抬 6.4、推、放順手，滑到底不晃；裝 EB-K（從機身內側塞，頭長出來的那端朝上）後抬不起來；'
               '勾唇到 #37 內面間隙約 0.15（塞得進 0.1 塞規、'
               '塞不進 0.3）',
               'params.C_HOOK（掛勾槽單邊餘隙 0.2）、params.T_PLY（實際板厚）；勾唇位置 ebox.HOOK'),
    'TA-#5': ('S50 缺口擋面（W\'7.8）＋2 mm 導角；前上角讓 TM1637 背面零件；只剩 2 支榫會不會晃',
              'crosstrack T2；ebox T2、T5（只剩 2 支榫）',
              '模組後臂外面貼得到擋面、上滑時導角把模組往前帶；TM1637 背面零件不碰 #5；用手指推隔板頂晃動 ≤0.5 mm',
              '擋面→params.MODULE（arm_t、slot_w、pcb_L，spec d-2）；碰背面零件→ebox.C_DIV 或 params.TM1637；'
              '晃→講師預組時點白膠（spec ebox g-1 第 2 點）'),
    'TA-#6': ('S10 缺口擋面＋導角；#6 v2 新上方小榫插 #26 新槽',
              'crosstrack T2',
              '新小榫插得進 TA-#26 的新槽（2.9×6.9）；模組後臂貼擋面', '同 TA-#5；槽太緊→mods_crosstrack.DESIGN["slot_shrink"]'),
    'P1-S10': ('S10 鎖塊（黏在 C1 雕刻外框內，頂住凸塊對齊 C1 下緣的 ▲）', 'crosstrack T2',
               'P1 貼 #24 正面往上抬、再往後推 3 mm 塞得進 #24 窗，凸塊頂住 PCB 下面；放手後模組不掉',
               'P1 頂面磨低（槽底頂到保留條時，spec d-2）；改 params.MODULE 後重產生'),
    'C1-S10': ('S10 蓋板', 'crosstrack T2、T7', '蓋板貼 #24 正面；裝一站 ≤2 分鐘、拆換 ≤1 分鐘', '同 P1-S10'),
    'P1-S50': ('S50 鎖塊', 'crosstrack T2', '同 P1-S10', '同 P1-S10'),
    'C1-S50': ('S50 蓋板（兩側插銷）', 'crosstrack T1、T2', '插銷插得進 TA-#24 兩個方孔，鎖塊不轉', '同 P1-S10'),
    'PIN-S50': ('S50 插銷 ×2', 'crosstrack T1（a-2 第 5 步：先插進 TA-#24 孔再壓 C1 上去黏）', '壓得進 2.9 孔、不鬆',
                'mods_crosstrack.DESIGN["slot_shrink"]（孔每邊少 0.05）、DESIGN["pin"]'),
    'EB-*': ('電子盒 7 片＋防拔鍵 ×2（盒體全組，裝實品擴展板、電池、線組）', 'ebox T3、T4',
             '電池往上拿出、放回各 10 次（每次 ≤20 秒）；USB、DC 從服務窗插拔順；EN／BOOT 按得到；GVS 杜邦頭插上後'
             '線收得進 W\'70；掛上 TA-#37 不晃',
             'params.ESP32_BOARD（孔位、USB／DC 位置的鍵都列在裡面）、params.BATTERY_9V、params.C_TAB、'
             'params.T_PLY；盒子尺寸 ebox.BOX'),
    'TA-ST': ('試切支架 ×2（新設計，實機沒有）：TA 組照實機角度站著，滾硬幣用', '—',
              '#24＋#26 下緣卡進前槽、TA-#37 下緣卡進後槽，整組站得穩（掛上電子盒也不會往後倒）', '只是治具，不影響 v2'),
    'TA-PIN': ('定位銷 ×2（新設計，實機沒有）：穿過 TA-#24、TA-#26 左下兩個 #21 齒孔，讓兩片的窗對齊', '—',
               '兩片疊好後 S10／S50 窗邊對齊（錯位 ≤0.2）', '只是治具'),
    'TB-#13R': ('牆槽讓 S1-B 滑進去；前榫 F1、F2 插 #26，後榫 B1 插 #37；前榫 2.6 不穿出 #26 前面', 's1 T1',
                'S1-B 在牆槽內滑順、不晃；F1／F2／B1 插得進',
                'mods_s1.DES["c_tab"]（S1 木榫單邊餘隙 0.15）；板厚 <2.7 時前榫改 2.4（mods_s1.DES，spec R7）'),
    'TB-#26': ('槽 F1、F2（#13R 前榫）、槽 C（S1-C 尖榫）', 's1 T1', 'S1-C 尖榫自己找到槽 C', 'mods_s1.DES["c_tab"]'),
    'TB-#37': ('卡匣窗、槽 B1、M3 孔；裝實品模組量光束', 's1 T1、T2、T3（靜態）、T7（插卡匣時間）',
               '背蓋貼平時後臂內面比 #37 內面低 0～0.5；光束中心 ≥U118.0（Ø1 鑽頭尾端從 U112 推到 U125）；'
               '1 元貼 #37 由上往下推過，靠左、靠右燈都會亮；插卡匣＋鎖 2 支螺絲 ≤1 分鐘',
               '後臂位置→params.T_PLY、mods_s1.DES["wb_recess"]；光束 <118→mods_s1.DES["s_pcb"]（泡棉加厚，最多 1.6）'
               '或實量後改 params.MODULE（arm_top、slot_d、beam_sb、pcb_t）；窗太緊→params.C_SENSOR'),
    'S1-*': ('卡匣：S1-B 座塊、S1-C 座板、S1-F 背蓋、S1-P 填塊、S1-H 導流帽 ×3', 's1 T1、T2、T7（T8 耐久要整台）',
             'S1-B 黏 S1-C 後插進牆槽順；背蓋 2 支 M3 尼龍螺絲鎖上後整面貼 #37；後臂內面→背蓋前面 2.7±0.2',
             '同 TB-#37；導流帽鬆→改瞬間膠（spec R1）'),
}

GUIDE_ORDER = {
    'TA': ('TA-#24', 'TA-#26', 'TA-#37', 'TA-#5', 'TA-#6', 'P1-S10', 'C1-S10', 'P1-S50', 'C1-S50', 'PIN-S50',
           'EB-*', 'TA-ST', 'TA-PIN'),
    'TB': ('TB-#13R', 'TB-#26', 'TB-#37', 'S1-*'),
}

NOT_HERE = [
    'crosstrack T3（每格 100 枚落幣錄影）、T4（計數）、T5（分級和原機比）、T6（抽屜）：要整台 v2。',
    's1 T4（200 枚落幣）、T5（混合）、T6（邊界、日光燈）、T8（500 枚耐久）：要整台。',
    'ebox T5（整台翻倒力）、T6（跑硬幣看 WL 勾唇）、T7（四條感測器線實際走線）、T8（教室可視）：要整台。',
    's1 T0、crosstrack d-1：拿到模組先實量（Go／No-Go），改 params.MODULE 後重跑 build_v2，再切小樣。',
]


def write_report(path: Path, tparts, tinfo, sheets, rows, qa_rows, files: dict, elapsed: float):
    Lr = []
    info_by = tinfo['info']
    a0 = tinfo['a0'].get('TA-#24')
    Lr.append('# 分幣機 v2 試切小樣：說明與檢查\n')
    Lr.append('由 `python -m laser_v2.trial`（或 `python -m laser_v2.build_v2` 最後一步）產生。'
              '小樣直接從 v2 最終零件（含 crosstrack、S1、電子盒全部修改與 #26 齒孔修正）裁出來，'
              '模組實量後改 `laser_v2/params.py` 重跑，小樣會跟著更新。\n')
    Lr.append('## 一、檔案\n')
    Lr.append(f'- 試切檔：`{files["svg"]}`（{len(sheets)} 頁，255×355；圖層同 v2 草稿：裁出來的局部在「v2 修改」，'
              'v2 新零件與試切輔助件在「v2 新增」；註記層預設隱藏）。')
    if files.get('pngs'):
        Lr.append('- 預覽圖：' + '、'.join(f'`{p}`' for p in files['pngs']))
    Lr.append('- 顏色：黑 0.2 mm＝切割、紅＝雕刻（代號 TA-#24 等）、綠＝註記（不切割）。\n')
    Lr.append('## 二、用板\n')
    for s in sheets:
        ex, ey = s.extent
        Lr.append(f'- {s.title}：{len(s.items)} 件，利用率 {s.util * 100:.1f}%（外框 {s.outer_area / s.area * 100:.1f}%），'
                  f'排到 x≤{ex:.0f}、y≤{ey:.0f}（板邊留 {params.SHEET_MARGIN:g} mm，'
                  f'用 {s.w:g}×{math.ceil(ey + params.SHEET_MARGIN):g} 的板也切得下）。')
    n_items = sum(int(getattr(p, 'qty', 1) or 1) for p in tparts)
    Lr.append(f'\n共 {len(tparts)} 種、{n_items} 件。spec 建議 MDF 和合板各切一次（保留條 2.3 會不會燒斷），'
              '每種板材各切 1 份。\n')

    Lr.append('## 三、每一片\n')
    Lr.append('代號雕在零件上：TA／TB 是小樣的組別（不是 spec 的 T 編號）。裁切範圍用組裝座標（frames.py：U 往左、'
              "V 沿面板往下、W' 往後）。v2 新零件和正式件完全相同，試切過了可以留著用。\n")
    by_id = {p.id: p for p in tparts}
    for grp, keys in GUIDE_ORDER.items():
        Lr.append(f'### {GROUP_ZH[grp]}\n')
        Lr.append('| 片 | 是什麼（裁切範圍） | 要測什麼 | 對應 spec | 過關標準 | 不過關時改哪裡 |')
        Lr.append('|---|---|---|---|---|---|')
        for key in keys:
            if key.endswith('*'):
                ids = [q.id + (f'×{q.qty}' if q.qty > 1 else '') for q in tparts if q.id.startswith(key[:-1])]
                what = '、'.join(ids)
            else:
                p = by_id[key]
                I = info_by.get(key, {})
                spec = I.get('spec')
                what = p.name if spec is None or 'rect' not in spec and 'poly' not in spec \
                    else f'{p.name}；實際 {_extent(I)}'
                if p.qty > 1:
                    what += f'（×{p.qty}）'
            t, ref, ok, fix = GUIDE[key]
            Lr.append(f'| {_md(key)} | {_md(what)} | {_md(t)} | {_md(ref)} | {_md(ok)} | {_md(fix)} |')
        Lr.append('')

    Lr.append('## 四、怎麼組、怎麼測\n')
    Lr.append('**TA 組（機身左段）**')
    Lr.append(f'1. TA-#24 疊在 TA-#26 前面（雕刻面朝前），左下兩個 #21 齒孔插 TA-PIN（前露 1、後露 3）。')
    Lr.append('2. TA-#6、TA-#5（雕刻面朝右，也就是 U 小、轉盤那一側）的前小榫插 TA-#26（#6 兩支、#5 一支），'
              '後榫插 TA-#37（雕刻面朝後）。')
    Lr.append(f'3. 兩片 TA-ST 立在桌上，間距照 U{tinfo["aux"]["U"]["右"][0]:g} 與 U{tinfo["aux"]["U"]["左"][0]:g}'
              f'（各在電子盒外側）：#24＋#26 下緣放進前槽（寬 {2 * params.T_PLY + 2 * ST_FIT:g}），TA-#37 下緣放進後槽'
              f'（寬 {params.T_PLY + 2 * ST_FIT:g}）。面板就是實機的後仰 30°，'
              f'軌道（斜槽下緣）對桌面約 17°。')
    Lr.append('4. 感測座：照 crosstrack a-3 裝 S10、S50（先黏 P1 到 C1，S10 的凸塊對齊 C1 下緣的 ▲；S50 插銷先插 TA-#24 孔'
              '再黏 C1）。塞鎖塊用新塞法：P1 背面貼 TA-#24 正面、從窗下方往上抬到凸塊碰 PCB 下面，再往後推 3 mm'
              '（不可從模組前方直接水平推入，凸塊會撞前臂底下的焊腳；見 report.md crosstrack 說明）。')
    Lr.append(f'5. 滾硬幣：硬幣從斜槽右端（U{a0 + CROPS[0]["bridge"]:g} 以左）放進去靠著 TA-#26 往下滾。'
              '10 元經過 S10 光束後掉進 10 元開口；50 元經過 S10、S50 兩道光束後掉進 50 元開口（兩個開口都完整）。'
              '5 元放在右端會直接掉進 5 元開口（右緣被裁掉約 1.4 mm）、落在 S10 翼上方；10 元落進 10 元開口時在 S50 翼上方，'
              '可以看翼會不會卡幣（R1）。')
    Lr.append('6. TM1637 從 TA-#24 背面裝窗，PCB 進 TA-#26 的 L 形缺口；電子盒照 ebox a-2 組好，掛上 TA-#37'
              '（抬、推、放）。支架尾巴延伸到 W\'65，掛上電子盒也不會往後倒。')
    Lr.append('\n**TB 組（S1 卡匣）**')
    Lr.append('1. TB-#13R 前榫 F1、F2 插 TB-#26，後榫 B1 插 TB-#37（雕刻面朝空腔、朝 U 小的一側）。')
    Lr.append('2. 卡匣照 s1 a-2 預組（S1-B 黏 S1-C、後榫插 S1-F、S1-P 黏背蓋前面、導流帽黏前臂、模組貼 1 mm 泡棉膠），'
              '從 TB-#37 背面推進牆槽，鎖 2 支 M3。')
    Lr.append('3. 量後臂內面位置、光束 U（s1 T2）、手推 1 元（s1 T3）。\n')
    Lr.append('**這份小樣做不到、要切整台才能測的項目**\n')
    Lr.extend(f'- {s}' for s in NOT_HERE)
    Lr.append('')

    Lr.append('## 五、和 spec 建議範圍不同的地方\n')
    ext = {k: _extent(info_by[k]) for k in ('TA-#24', 'TA-#26', 'TA-#37', 'TB-#13R', 'TB-#26', 'TB-#37')}
    br = CROPS[0]['bridge']
    Lr.append(f'- crosstrack g-2 T1 建議 #24、#26 切 U165～215 × V40～98：S10 窗在 U144～169，U165 會把窗切開；斜槽也會把'
              f'那塊切成上下兩半。改成從 U{a0:g} 起（S10 窗右下角外留 ≥{MIN_WEB:g} mm，在 U'
              f'{CROPS[0]["search"]["a0"][0]:g}～{CROPS[0]["search"]["a0"][1]:g} 自動找），往左包到 #24 左端，'
              f'和 ebox 要的 #24 左上（顯示窗）合成一片：TA-#24 {ext["TA-#24"]}、TA-#26 {ext["TA-#26"]}。')
    Lr.append(f'- TA-#24 右端 U{a0:g}～{a0 + br:g} 把斜槽補成 {br:g} mm 連接條（試切專用）：不補的話，斜槽下方那條'
              '（S10 窗那段）只靠 S50 開底缺口上的 2.3 mm 保留條懸臂掛著，搬動就可能斷，也測不出實機「保留條兩端固定」的強度。'
              '硬幣從連接條左邊放進斜槽。')
    Lr.append('- TA-#24 左下腳（V98 以下）切掉，讓 #24、#26 下緣齊平，支架才夾得住。')
    Lr.append(f'- ebox g-2 建議 #37 切 U140～246 × V0～45：#5、#6 的後榫槽在 V40～56，所以往下切到 TA-#37 {ext["TA-#37"]}，'
              '讓隔板把 #26、#37 撐在一起，電子盒前緣（到 V76.25）也整片靠得到 #37；右緣避開 #7 後榫槽（U135.9～138.8），'
              '下緣避開 #37 左端榫（V79.95 起）。')
    Lr.append(f'- s1 g-2 建議 #26、#37 切 U90～130 × V30～85：#26 往左會切過 1 元開口與 S5 窗、留下細條，所以只切槽附近'
              f'（TB-#26 {ext["TB-#26"]}）；#37 改成 TB-#37 {ext["TB-#37"]}（卡匣窗下緣 V78.8 到 #37 底邊 V82 只有 3.2 mm，'
              '切在 V82 以上會留細條；左邊包住感測器線孔）。')
    Lr.append(f'- s1 建議的「#13R 上段」：TB-#13R {ext["TB-#13R"]}，往下留到牆槽下方 6.6 mm，#37 板厚內的後上角讓開，不含齒。')
    Lr.append('- 新增試切輔助件：TA-ST×2（支架）、TA-PIN×2（定位銷）。\n')

    Lr.append('## 六、檢查結果\n')
    bad = [r for r in rows if r['ok'] is False]
    n_ok = sum(1 for r in rows if r['ok'] is True)
    Lr.append(f'本模組檢查 {len(rows)} 項：通過 {n_ok}、未通過 {len(bad)}、資訊 {len(rows) - n_ok - len(bad)}。\n')
    Lr.append('| 片 | 項目 | 結果 | 值 | 期望 | 說明 |')
    Lr.append('|---|---|---|---|---|---|')
    for r in rows:
        flag = 'OK' if r['ok'] else ('資訊' if r['ok'] is None else '**未通過**')
        Lr.append(f'| {_md(r["piece"])} | {_md(r["name"])} | {flag} | {_md(r["value"])} | {_md(r["expected"])} | '
                  f'{_md(r["note"])} |')
    Lr.append('')
    qb = qa.failures(qa_rows)
    Lr.append(f'**qa.check（雷切檔衛生）**：{len(qa_rows) - len(qb)}/{len(qa_rows)} 項通過。\n')
    Lr.append('| 項目 | 結果 | 說明 |')
    Lr.append('|---|---|---|')
    for q in qa_rows:
        flag = 'OK' if q['ok'] else ('注意' if q.get('level') == 'warn' else '**未通過**')
        Lr.append(f'| {_md(q["name"])} | {flag} | {_md(q["detail"])} |')
    Lr.append('')
    Lr.append('## 七、待決（照預設產生）\n')
    Lr.append('- 待決：試切板材（照預設：spec 建議 MDF 與合板各切一次，比較保留條 2.3）。')
    Lr.append('- 待決：模組、TM1637、擴展板都還沒實量（照預設：params.py 暫定值；實量後重跑再切）。')
    Lr.append('- 待決：支架、定位銷、TA-#24 連接條是試切專用設計（照預設：放進小樣，實機不用）。')
    Lr.append(f'\n產生耗時 {elapsed:.1f} s。')
    path.write_text('\n'.join(Lr) + '\n', encoding='utf-8')


def remove_stale(out_root, out_dir) -> list[Path]:
    """移除上一次產生的試切檔（試切 SVG、trial_*.png、trial_report.md），回傳移除的檔案。
    本次排不出小樣或產生途中出錯時用：舊檔留著會和新草稿對不上。"""
    out_root = Path(out_root) if out_root else REPO
    out_dir = Path(out_dir) if out_dir else REPO / 'laser_v2' / 'out'
    removed = []
    for f in [out_root / TRIAL_SVG, out_dir / REPORT_NAME] + sorted(out_dir.glob('trial_*.png')):
        if f.is_file():
            f.unlink()
            removed.append(f)
    return removed


def write_fail_report(path: Path, reason: str, removed: list, elapsed: float):
    """排不出試切小樣時的 trial_report.md：寫明原因、舊檔已移除、怎麼處理。"""
    Lr = ['# 分幣機 v2 試切小樣：本次參數排不出來\n',
          '由 `python -m laser_v2.build_v2`（或 `python -m laser_v2.trial`）產生。**這次沒有產生試切小樣**；'
          'v2 草稿（分幣機雷切_光耦版_v2_草稿.svg、laser_v2/out/）已照目前 params 更新。\n',
          '## 原因\n', f'- {_md(reason)}\n',
          '## 上一次的試切檔\n',
          '已移除（避免和新草稿對不上）：' + ('、'.join(f'`{Path(p).name}`' for p in removed) if removed else '沒有舊檔。') + '\n',
          '## 怎麼處理\n',
          '- 先看 report.md 的 crosstrack 檢查與警告：多半是 params.MODULE（wing、模組尺寸）改了，感測座窗移到 '
          'TA 右緣附近（TA-#24 右緣在 U{:g}～{:g} 之間自動找，連接條要只補斜槽）。'.format(*CROPS[0]['search']['a0']),
          '- 窗的位置確定後，調整 laser_v2/trial.py 的 CROPS（TA-#24 的 rect／search）與右支架位置（右支架在 TA 右緣、'
          '電子盒左牆外側，不可壓到電子盒掛勾槽），再重跑。',
          '- 只要草稿、不要小樣時，可以用 `python -m laser_v2.build_v2 --no-trial`。',
          f'\n產生耗時 {elapsed:.1f} s。']
    path.write_text('\n'.join(Lr) + '\n', encoding='utf-8')


# ---------------------------------------------------------------------------
# 對外
# ---------------------------------------------------------------------------
def run(parts: list, results: dict, cat: dict | None = None, out_root=None, out_dir=None, png: bool = True,
        verbose: bool = True) -> dict:
    """最終零件 → 試切小樣（SVG、預覽、報告）。回傳 dict(svg, report, pngs, sheets, parts, rows, qa, failures)。
    cat：傳給子系統的零件（build_v2.load_parts()）；用來算 crosstrack 模型（支架對感測座的檢查），None 時重新載入。"""
    t0 = time.time()
    out_root = Path(out_root) if out_root else REPO
    out_dir = Path(out_dir) if out_dir else REPO / 'laser_v2' / 'out'
    out_root.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        tparts, tinfo = build_trial(parts, results)
    except TrialInfeasible as e:     # 排不出小樣：移除上一次的舊檔（不然會和新草稿對不上），報告寫明原因
        removed = remove_stale(out_root, out_dir)
        report = out_dir / REPORT_NAME
        row = _row('排得出試切小樣', False, '找不到可行的 TA 右緣裁切線', '找得到', note=str(e), piece='TA-#24')
        write_fail_report(report, str(e), removed, time.time() - t0)
        if verbose:
            print(f'[trial] 未通過：本次參數排不出試切小樣：{e}')
            print('[trial] 草稿已更新；試切小樣沒有產生，上一次的舊檔已移除：'
                  + ('、'.join(str(p) for p in removed) if removed else '（沒有舊檔）'))
            print(f'      {report}（寫明原因）')
        return dict(svg=None, report=report, pngs=[], sheets=[], parts=[], rows=[row], qa=[], failures=[row],
                    qa_failures=[], info=None, removed=removed)
    try:
        from . import mods_crosstrack
        if cat is None:
            from .build_v2 import load_parts
            cat = load_parts()
        tinfo['ct_model'] = mods_crosstrack.model(cat)
    except Exception as e:                       # noqa: BLE001 —— 只影響支架對感測座的檢查
        tinfo['ct_model'] = None
        print(f'[trial] 讀不到 crosstrack 模型（{type(e).__name__}: {e}），略過支架對感測座的檢查', file=sys.stderr)
    rows = check_pieces(tinfo, results)
    sheets = L.layout(tparts, verbose=False)
    rows += check_layout(sheets, tparts)
    res = write_outputs(sheets, tparts, out_root, out_dir, png=png)
    keep = {Path(f).resolve() for f in res['pngs']}
    for f in sorted(out_dir.glob('trial_*.png')):     # 這次沒有重畫的舊預覽圖（張數變少或 --no-png）會和小樣對不上
        if f.resolve() not in keep:
            f.unlink()

    def rel(p: Path) -> str:
        try:
            return str(Path(p).resolve().relative_to(REPO)).replace('\\', '/')
        except ValueError:
            return str(p)
    report = out_dir / REPORT_NAME
    write_report(report, tparts, tinfo, sheets, rows, res['qa'],
                 dict(svg=rel(res['svg']), pngs=[rel(p) for p in res['pngs']]), time.time() - t0)
    fails = [r for r in rows if r['ok'] is False]
    qfails = qa.failures(res['qa'])
    if verbose:
        n_items = sum(int(getattr(p, 'qty', 1) or 1) for p in tparts)
        print(f'試切小樣：{len(tparts)} 種、{n_items} 件；' + '、'.join(
            f'{s.title} 利用率 {s.util * 100:.1f}%' for s in sheets))
        for r in fails:
            print(f'[trial] 未通過 [{r["piece"]}] {r["name"]}：{r["value"]}（期望 {r["expected"]}）'
                  + (f'；{r["note"]}' if r['note'] else ''))
        for q in qfails:
            print(f'[trial] QA 未通過：{q["name"]}：{q["detail"]}')
        print(f'試切檢查 {len(rows)} 項（未通過 {len(fails)}）；QA {len(res["qa"]) - len(qfails)}/{len(res["qa"])}')
        print(f'輸出：{res["svg"]}')
        print(f'      {report}')
    return dict(svg=res['svg'], report=report, pngs=res['pngs'], sheets=sheets, parts=tparts, rows=rows,
                qa=res['qa'], failures=fails, qa_failures=qfails, info=tinfo)


def final_parts():
    """自己跑一次產生流程，回傳 (cat, results, parts)：和 build_v2 相同（子系統 → ebox 重查 → compose →
    #24「1」「5」離切割不足時依 spec b-6 重算再合成）。"""
    from . import build_v2, compose, integrate
    cat = build_v2.load_parts()
    results = build_v2.run_subsystems(cat)
    results['ebox'], _ = integrate.ebox_integrated(cat, results)
    parts = compose.compose(cat, results)
    cross = integrate.check(cat, results, parts)
    bad = integrate.engrave_failures(cross['rows'])
    if bad:
        for m in integrate.recompute_engrave_moves(cat, results, parts, bad):
            print(f'[integrate] {m}')
        parts = compose.compose(cat, results)
    return cat, results, parts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='python -m laser_v2.trial', description='分幣機 v2 試切小樣')
    ap.add_argument('--out-root', default=None, help='試切 SVG 輸出資料夾（預設 repo 根目錄）')
    ap.add_argument('--out-dir', default=None, help='預覽圖與 trial_report.md 的資料夾（預設 laser_v2/out）')
    ap.add_argument('--no-png', action='store_true', help='不畫預覽圖')
    a = ap.parse_args(argv)
    t0 = time.time()
    cat, results, parts = final_parts()
    res = run(parts, results, cat, out_root=a.out_root, out_dir=a.out_dir, png=not a.no_png)
    print(f'耗時 {time.time() - t0:.1f} s')
    if res['qa_failures']:
        return 1
    return 2 if res['failures'] else 0


if __name__ == '__main__':
    sys.exit(main())

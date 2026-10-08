"""v2 雷切檔產生器主程式：讀原始檔 → 修 #26 齒孔 → 三個子系統 → 合併 → 跨子系統檢查 → 排版 → 輸出 → 檢查。

用法
----
    python -m laser_v2.build_v2                    # 完整流程，輸出到 repo 根目錄與 laser_v2/out/
    python -m laser_v2.build_v2 --only-original    # 只排原始 60 個零件（測試排版／輸出用），
                                                   # 預設輸出到 laser_v2/_work/layout_export/only_original/
    選項：--out-root DIR（草稿 SVG 放這裡）、--out-dir DIR（分頁 SVG／PNG／csv／report 放這裡）、--no-png、
          --no-trial（不產生試切小樣）

流程
----
0. check_params()：params.py 的必要鍵都在、數值型別、正值、在合理範圍（例如 MODULE['slot_w'] 6～15）、
   wing∈{up,down,center}、LOGO_PLAN∈{L1,L2}、字典裡不認得的鍵（打錯字）、切割／雕刻樣式是固定值…；
   填錯就用中文印出哪個鍵、現在的值、合理範圍，結束碼 3，不往下跑（範圍表在本檔 PARAM_RULES）。
   1～8 步丟例外時印中文說明（多半是 params 超出設計能處理的範圍），結束碼 1。
1. catalog.load_catalog()：原始檔拆成 60 個零件。
2. params.FIX_26_TOOTH_HOLE 為 True 時，用 frames.fix_26_tooth_hole() 修 #26 右側第 1 個齒孔
   （子系統看到的就是修正後的 #26；compose 會偵測已修過，不會重複平移）。
3. mods_crosstrack.build、mods_s1.build、ebox.build（各拿一份獨立的零件副本，互不影響）。
   任何一個匯入或執行失敗就直接報錯，不會跳過。
4. 電子盒重查：ebox 改用 mods_s1、mods_crosstrack 的實際結果重跑（integrate.ebox_integrated，
   等於 ebox.recheck；S1 禁區用 mods_s1 的 keepout），草稿一律用重跑後的結果。
5. compose.compose(cat, results) → list[V2Part]。
6. integrate.check()：跨子系統檢查（#37 開孔、S1 禁區、#5、#26、#24 雕刻、修改區域相交、
   原始子路徑逐字保留、分幣開口與軌道逐點、榫槽配對、細料、S1↔S5 間隙）。
7. layout.layout(parts) → list[Sheet]（正式件排完再把備品 V2Part.spare 塞進已經開的板，不加張數）；
   integrate.check_layout()（同板群組、張數、備品都排進去）。
8. export.export(...)：草稿 SVG（含隱藏註記層）、分頁 SVG（上雷切機用，不含註記層）、預覽 PNG、parts.csv、
   report.md（含跨子系統檢查），並跑 qa.check（草稿用 mode='draft'、分頁檔用 mode='sheet'）。
9. 印出摘要（各子系統 warnings、未通過的子系統 checks、跨子系統檢查、qa 未通過項目、張數、備品）。
10. trial.run(...)：從最終零件裁出試切小樣 → <out-root>/分幣機雷切_光耦版_v2_試切小樣.svg（含隱藏註記層）、
    <out-dir>/trial_<材質>_<n>.svg（上雷切機用，不含註記層）、trial_report.md、trial_<材質>_<n>.png
    （--only-original、--no-trial 時不做；--no-trial 時上一次的試切檔不動，但 report.md 與摘要會提醒它們是舊 params 的）。

結束碼：0＝全部通過；
        1＝qa（草稿、分頁 SVG 或試切小樣）有未通過項目，或流程出錯（例外；會印中文說明，多半是 params 超出設計能處理的範圍）；
        2＝qa 通過但子系統 checks、跨子系統檢查或試切小樣檢查有未通過項目；
        3＝params.py 填錯（check_params，什麼都沒有產生）。
"""
from __future__ import annotations

import argparse
import copy
import difflib
import sys
import time
from dataclasses import dataclass, field, fields
from pathlib import Path

from . import params
from .catalog import REPO, Part, load_catalog
from .frames import fix_26_tooth_hole

SUBSYSTEMS = (('crosstrack', 'mods_crosstrack'), ('s1', 'mods_s1'), ('ebox', 'ebox'))
TAG_FIX26 = '修正 #26 右側第 1 個齒孔（原始檔偏 ΔV+1.000、ΔU+0.134；frames.fix_26_tooth_hole）'
EXIT_OK, EXIT_QA, EXIT_CHECKS, EXIT_PARAMS = 0, 1, 2, 3

# ---------------------------------------------------------------------------
# params 檢查（流程第 0 步）：(鍵, 下限, 上限, 說明)；下限 > 0 的就是「要正值」。
# 範圍是「合理」範圍（擋打錯字、單位錯，例如 cm 填成 mm），不是設計容許範圍；設計上合不合由各子系統的 checks 判斷。
# 標 opt 的鍵可以不填（子系統有預設值）。
# ---------------------------------------------------------------------------
PARAM_RULES = {
    'T_PLY': (2.0, 5.0, '合板厚；超過 5 mm 電子盒右牆 EB-WR 會斷開，產生器做不出來'),
    'T_ACRYLIC': (2.0, 6.0, '壓克力厚'),
    'SHEET_MARGIN': (0.0, 20.0, '零件離板邊'),
    'PART_GAP': (0.5, 20.0, '零件之間'),
    'C_TAB': (0.0, 0.5, '一般榫槽單邊餘隙'),
    'C_SENSOR': (0.0, 1.5, '光耦相關開孔單邊餘隙'),
    'C_HOOK': (0.0, 0.6, '電子盒掛勾槽單邊餘隙'),
    'BEAM_H': (1.5, 4.5, '跨軌光束離軌道面（定案 2.5）'),
    'S1_WALL_TOP_V': (30.0, 38.0, '#13R 右牆牆頂 V（V30 或 V38）'),
}
DICT_RULES = {
    'MODULE': {
        'slot_w': (6.0, 15.0, '槽寬：兩臂內面距'), 'slot_d': (5.0, 15.0, '槽深：臂頂到槽底'),
        'beam_sb': (2.0, 10.0, '光束中心離槽底'), 'arm_t': (3.0, 12.0, '單臂沿光束厚'),
        'arm_w': (3.0, 12.0, '臂寬'), 'arm_top': (6.0, 20.0, '臂頂離 PCB 元件面'),
        'pcb_L': (15.0, 45.0, 'PCB 沿光束長'), 'pcb_W': (10.0, 35.0, 'PCB 寬'), 'pcb_t': (0.8, 2.4, 'PCB 厚'),
        'body_e': (0.0, 10.0, '光耦本體側邊到 PCB 長邊'), 'comp_h': (0.0, 6.0, 'PCB 元件面最高零件'),
        'back_h': (0.0, 4.0, 'PCB 背面焊點凸出'), 'hdr_up': (5.0, 25.0, '直立排針＋杜邦頭高度'),
        'hdr_len': (2.0, 20.0, '排針＋杜邦頭沿光束方向長', 'opt'), 'pcb_ovf': (0.0, 10.0, 'PCB 前端超出前臂外面', 'opt'),
        'aperture': (0.2, 3.0, '光耦光窗寬', 'opt'),
    },
    'TM1637': {
        'pcb_w': (20.0, 60.0, 'PCB 寬'), 'pcb_h': (12.0, 40.0, 'PCB 高'), 'pcb_t': (0.8, 2.4, 'PCB 厚'),
        'hole_d': (1.5, 3.5, '固定孔徑'),
        'body_w': (15.0, 55.0, 'LED 塊寬', 'opt'), 'body_h': (8.0, 30.0, 'LED 塊高', 'opt'),
        'body_H': (3.0, 15.0, 'LED 塊厚（往前凸出）', 'opt'),
        'body_dx': (-15.0, 15.0, 'LED 塊中心相對 PCB 中心（U）', 'opt'),
        'body_dy': (-15.0, 15.0, 'LED 塊中心相對 PCB 中心（V）', 'opt'),
        'back_h': (0.0, 8.0, 'PCB 背面零件最高', 'opt'),
        'hole_dx': (5.0, 30.0, '固定孔半距（孔中心離 PCB 中心，U；實量孔距要除以 2）', 'opt'),
        'hole_dy': (3.0, 20.0, '固定孔半距（V；實量孔距要除以 2）', 'opt'),
        'dup_len': (8.0, 20.0, '杜邦頭長', 'opt'), 'dup_gap': (0.0, 5.0, '排針到杜邦頭間隙', 'opt'),
        'wire_bend': (0.0, 15.0, '線折彎預留', 'opt'),
    },
    'ESP32_BOARD': {
        'L': (50.0, 110.0, '擴展板長'), 'W': (30.0, 75.0, '擴展板寬'),
        't': (0.8, 2.4, '擴展板厚', 'opt'), 'standoff': (0.0, 15.0, '墊高', 'opt'),
        'hole_inset': (1.5, 8.0, 'M3 孔中心離板邊', 'opt'), 'hole_d': (2.0, 4.0, 'M3 孔徑', 'opt'),
        'hdr_h': (4.0, 15.0, '擴展板母座高', 'opt'), 'dev_len': (40.0, 70.0, '開發板長', 'opt'),
        'dev_w': (20.0, 35.0, '開發板寬', 'opt'), 'usb_inset': (0.0, 15.0, 'USB 座離板右端', 'opt'),
        'usb_V_off': (0.0, 75.0, 'USB 座離擴展板上緣', 'opt'), 'btn_dv': (0.0, 25.0, 'EN/BOOT 鍵離 USB 中心', 'opt'),
        'dc_V_off': (0.0, 75.0, 'DC 座離擴展板上緣', 'opt'),
    },
    'BATTERY_9V': {'L': (40.0, 55.0, '9V 電池長'), 'W': (20.0, 30.0, '9V 電池寬'), 'T': (12.0, 22.0, '9V 電池厚')},
}
CHOICES = {   # (鍵, 子鍵或 None) → 允許的值
    ('MODULE', 'wing'): ('up', 'down', 'center'),
    ('TM1637', 'hdr_mode'): ('RA', 'STRAIGHT'),
}
FLAG_KEYS = {'TM1637': {'use_screws'}}   # True／False 的鍵（另外檢查）
# 切割／雕刻樣式不是實量參數：qa 與原始檔只認得這幾個值，改了一定 qa 失敗，所以 check_params 要求固定值
FIXED_STYLE = {'STROKE_CUT': 'fill:none;stroke:#000000;stroke-width:0.2', 'STROKE_ENGRAVE_COLOR': '#ff0000'}


def _subsystem_keys() -> dict[str, set]:
    """params 字典裡「進階」也認得的鍵：子系統預設值字典的同名鍵可以由 params 覆蓋
    （ebox：TM1637→DISP_DEFAULT、ESP32_BOARD→BOARD_DEFAULT、BATTERY_9V→BATT_DEFAULT；mods_s1：MODULE→MODULE_EXTRA）。
    讀不到子系統時回傳空的（只認 DICT_RULES 的鍵）。"""
    out: dict[str, set] = {}
    try:
        from . import ebox
        out['TM1637'] = set(ebox.DISP_DEFAULT)
        out['ESP32_BOARD'] = set(ebox.BOARD_DEFAULT)
        out['BATTERY_9V'] = set(ebox.BATT_DEFAULT) - {'Tk'}      # 電池厚填 T（ebox 換成 Tk）
    except Exception:                                            # noqa: BLE001
        pass
    try:
        from . import mods_s1
        out['MODULE'] = set(mods_s1.MODULE_EXTRA)
    except Exception:                                            # noqa: BLE001
        pass
    return out


def _is_num(v) -> bool:
    import math
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _rng(lo, hi, unit='mm') -> str:
    return f'{lo:g}～{hi:g}' + (f' {unit}' if unit else '')


def check_params(P=params) -> list[str]:
    """params.py 的必要鍵、型別、正值、合理範圍。回傳中文錯誤說明（空＝沒問題）。"""
    errs = []

    def num(where, v, lo, hi, desc, unit='mm'):
        if not _is_num(v):
            errs.append(f'{where} 現在是 {v!r}（{type(v).__name__}），要填數字；{desc}，合理範圍 {_rng(lo, hi, unit)}')
        elif not lo <= v <= hi:
            pos = '（要正值）' if lo > 0 and v <= 0 else ''
            errs.append(f'{where} 現在是 {v!r}{pos}，合理範圍 {_rng(lo, hi, unit)}（{desc}）')

    for k, (lo, hi, desc) in PARAM_RULES.items():
        if not hasattr(P, k):
            errs.append(f'params.{k} 不見了（{desc}，合理範圍 {_rng(lo, hi)}）')
            continue
        num(f'params.{k}', getattr(P, k), lo, hi, desc, '' if k == 'S1_WALL_TOP_V' else 'mm')
    if not hasattr(P, 'SHEET'):
        errs.append('params.SHEET 不見了（每張板可切範圍 (寬, 高) mm，例如 (255.0, 355.0)）')
    else:
        sh = P.SHEET
        if not (isinstance(sh, (tuple, list)) and len(sh) == 2):
            errs.append(f'params.SHEET 現在是 {sh!r}，要填 (寬, 高) 兩個數字，例如 (255.0, 355.0)')
        else:
            for nm, v in zip(('寬', '高'), sh):
                num(f'params.SHEET 的{nm}', v, 150.0, 1000.0, '每張板可切範圍')
    if hasattr(P, 'KERF_COMP') and (not _is_num(P.KERF_COMP) or P.KERF_COMP != 0):
        errs.append(f'params.KERF_COMP 現在是 {P.KERF_COMP!r}，只能是 0（產生器不做切縫補償，填別的值不會有作用；'
                    '分幣開口餘量只有 0.14 mm，原始檔也沒有補償）')
    for name, rules in DICT_RULES.items():
        d = getattr(P, name, None)
        if not isinstance(d, dict):
            errs.append(f'params.{name} 不見了或不是 dict（現在是 {d!r}）')
            continue
        for k, rule in rules.items():
            lo, hi, desc = rule[:3]
            opt = len(rule) > 3 and rule[3] == 'opt'
            where = f"params.{name}['{k}']"
            if k not in d:
                if not opt:
                    errs.append(f'{where} 不見了（{desc}，合理範圍 {_rng(lo, hi)}）')
                continue
            num(where, d[k], lo, hi, desc)
    extra = _subsystem_keys()
    for name, rules in DICT_RULES.items():     # 不認得的鍵（多半是打錯字：子系統會默默改用預設值，實量值不會生效）
        d = getattr(P, name, None)
        if not isinstance(d, dict):
            continue
        basic = set(rules) | {k for (n, k) in CHOICES if n == name} | FLAG_KEYS.get(name, set())
        adv = extra.get(name, set()) - basic
        for k in d:
            if k in basic or k in adv:
                continue
            close = difflib.get_close_matches(str(k), sorted(basic | adv), n=1, cutoff=0.6)
            errs.append(f"params.{name}['{k}'] 不認得這個鍵（是不是打錯字？"
                        + (f"最像的是 '{close[0]}'。" if close else '')
                        + f"可用的鍵：{'、'.join(sorted(basic))}"
                        + (f"；進階（覆蓋子系統預設值）：{'、'.join(sorted(adv))}" if adv else '')
                        + '）。打錯的鍵子系統不會讀，會默默改用預設值')
    for (name, k), allowed in CHOICES.items():
        d = getattr(P, name, None)
        if isinstance(d, dict):
            if k not in d:
                if (name, k) == ('MODULE', 'wing'):
                    errs.append(f"params.MODULE['wing'] 不見了（只能是 {'／'.join(repr(a) for a in allowed)}）")
            elif d[k] not in allowed:
                errs.append(f"params.{name}['{k}'] 現在是 {d[k]!r}，只能是 {'／'.join(repr(a) for a in allowed)}")
    tm = getattr(P, 'TM1637', None)
    if isinstance(tm, dict) and 'use_screws' in tm and not isinstance(tm['use_screws'], bool):
        errs.append(f"params.TM1637['use_screws'] 現在是 {tm['use_screws']!r}，只能是 True（4 支 M2 螺絲）或 False（熱熔膠）")
    m = getattr(P, 'MODULE', None)
    if isinstance(m, dict) and _is_num(m.get('beam_sb')) and _is_num(m.get('slot_d')) and m['beam_sb'] >= m['slot_d']:
        errs.append(f"params.MODULE['beam_sb']（{m['beam_sb']!r}）要比 slot_d（{m['slot_d']!r}）小：光束中心在槽裡面")
    lp = getattr(P, 'LOGO_PLAN', None)
    if not (lp in ('L1', 'L2') or (isinstance(lp, (tuple, list)) and len(lp) == 2 and all(_is_num(x) for x in lp))):
        errs.append(f"params.LOGO_PLAN 現在是 {lp!r}，只能是 'L1'（「10」右邊）或 'L2'（顯示窗正下方）"
                    '（進階：(ΔU, ΔV) 兩個數字）')
    for k in ('FIX_26_TOOTH_HOLE',):
        if not isinstance(getattr(P, k, None), bool):
            errs.append(f'params.{k} 現在是 {getattr(P, k, None)!r}，只能是 True 或 False')
    fp = getattr(P, 'FONT_PATH', None)
    if not isinstance(fp, str) or not Path(fp).is_file():
        errs.append(f'params.FONT_PATH 現在是 {fp!r}，找不到這個字型檔（雕刻文字轉路徑要用，預設微軟正黑體 '
                    r"r'C:\Windows\Fonts\msjh.ttc'）")
    of = getattr(P, 'OUT_SVG', None)
    if not isinstance(of, str) or not of.lower().endswith('.svg'):
        errs.append(f'params.OUT_SVG 現在是 {of!r}，要是 .svg 檔名')
    import re as _re
    for k, want in FIXED_STYLE.items():         # 不是實量參數：qa 寫死黑 0.2 切割、原始檔雕刻一律 #ff0000
        v = getattr(P, k, None)
        norm = _re.sub(r'\s+', '', v).lower().rstrip(';') if isinstance(v, str) else v
        if norm != want:
            errs.append(f'params.{k} 現在是 {v!r}，只能是 {want!r}（不是實量參數：qa 和原始檔只認得這個值，'
                        '改了 qa 一定不過；雷切軟體的切割／雕刻設定請在軟體裡依顏色設）')
    v = getattr(P, 'NOTE_COLOR', None)
    if not isinstance(v, str) or not _re.fullmatch(r'#[0-9a-fA-F]{6}', v):
        errs.append(f'params.NOTE_COLOR 現在是 {v!r}，要填 #rrggbb 顏色（預設 #008000）')
    elif v.lower() in ('#000000', '#ff0000'):
        errs.append(f'params.NOTE_COLOR 現在是 {v!r}，不可和切割（#000000）或雕刻（#ff0000）同色（預設 #008000）')
    return errs


@dataclass
class _V2PartLite(Part):
    """只排原始零件（--only-original）且 compose.py 還不能用時的簡易 V2Part。"""
    layer: str = 'original'
    name: str = ''
    qty: int = 1
    tags: list = field(default_factory=list)
    group: str | None = None
    spare: int = 0


def load_parts() -> dict:
    """原始零件＋（依 params）#26 齒孔修正。"""
    cat = load_catalog()
    if params.FIX_26_TOOTH_HOLE:
        cat['#26'] = fix_26_tooth_hole(cat['#26'])
    return cat


def wrap_originals(cat: dict) -> list:
    """把 catalog 的 Part 包成 layer='original' 的 V2Part（--only-original 與測試用）。
    compose.V2Part 能用就用它，否則用本檔的 _V2PartLite（會印出提醒）。"""
    cls = None
    try:
        from .compose import V2Part as cls          # noqa: N813
    except Exception as e:                           # 只在 --only-original 測試時降級
        print(f'（提醒）compose.V2Part 無法使用（{type(e).__name__}: {e}），改用簡易包裝', file=sys.stderr)
    base = {f.name for f in fields(Part)}
    out = []
    for k in sorted(cat, key=lambda k: (cat[k].num, k)):
        p = cat[k]
        kw = {n: getattr(p, n) for n in base}
        extra = dict(layer='original', name=p.id, qty=1, group=None,
                     tags=[TAG_FIX26] if (p.id == '#26' and params.FIX_26_TOOTH_HOLE) else [])
        obj = None
        if cls is not None:
            try:
                obj = cls(**kw, **extra)
            except TypeError:
                obj = None
        if obj is None:
            obj = _V2PartLite(**kw, **extra)
        out.append(obj)
    return out


def run_subsystems(cat: dict) -> dict:
    """匯入並執行三個子系統（失敗直接丟例外）。"""
    import importlib
    results = {}
    for key, mod in SUBSYSTEMS:
        m = importlib.import_module(f'.{mod}', __package__)
        t = time.time()
        r = m.build(copy.deepcopy(cat))
        if not isinstance(r, dict):
            raise TypeError(f'{mod}.build() 應回傳 dict，實際是 {type(r).__name__}')
        for need in ('edits', 'new_parts', 'notes', 'warnings'):
            if need not in r:
                raise KeyError(f'{mod}.build() 回傳缺少 {need!r}')
        print(f'{mod}.build：edits {len(r["edits"])}、新零件 {len(r["new_parts"])}、'
              f'warnings {len(r["warnings"])}、checks {len(r.get("checks", []))}（{time.time() - t:.1f} s）')
        results[key] = r
    return results


def _check_failures(results: dict) -> list[str]:
    out = []
    for key, r in results.items():
        for c in r.get('checks', []) or []:
            if not c.get('ok', False):
                out.append(f'[{key}] {c.get("name")}：值 {c.get("value")}，期望 {c.get("expected")}'
                           + (f'（{c.get("note")}）' if c.get('note') else ''))
    return out


def _stale_trial_notice(a, out_root: Path, out_dir) -> list[str]:
    """--no-trial 時，上一次的試切檔（標成上雷切機用）還留著：列出來提醒（不刪，params 沒改的話它們仍然可用）。"""
    if a.only_original or not a.no_trial:
        return []
    from . import export, trial
    od = Path(out_dir) if out_dir else Path(out_root) / 'laser_v2' / 'out'
    old = [f for f in (Path(out_root) / trial.TRIAL_SVG, od / trial.REPORT_NAME) if f.is_file()]
    old += [f for f in sorted(od.glob('trial_*')) if f.is_file() and export.generated_name(f.name, 'trial')]
    if not old:
        return []
    return ['這次加了 --no-trial，試切小樣沒有更新：' + '、'.join(f.name for f in old)
            + ' 是上一次的 params 產生的。params 改過的話不要拿它們去切，先重跑完整流程（不加 --no-trial）']


def _pipeline(a, export, layout):
    """讀原始檔 → 子系統 → 合成 → 跨子系統檢查 → 排版 → 輸出（流程 1～8）。
    回傳 (cat, results, parts, cross, sheets, res, out_root)。"""
    cat = load_parts()
    print(f'原始零件 {len(cat)} 個' + ('（已修 #26 齒孔）' if params.FIX_26_TOOTH_HOLE else ''))
    cross = None
    if a.only_original:
        results = {}
        parts = wrap_originals(cat)
        out_root = Path(a.out_root) if a.out_root else REPO / 'laser_v2' / '_work' / 'layout_export' / 'only_original'
        out_dir = Path(a.out_dir) if a.out_dir else out_root / 'out'
    else:
        from . import compose, integrate     # 匯入失敗直接報錯
        results = run_subsystems(cat)
        t = time.time()
        results['ebox'], ebinfo = integrate.ebox_integrated(cat, results)
        print(f'ebox 重查（改用 {"、".join(ebinfo["others"])} 的實際結果）：檢查 '
              f'{ebinfo["n_checks"] - ebinfo["n_fail"]}/{ebinfo["n_checks"]} 通過、警告 {len(ebinfo["warnings"])} 則、'
              f'edits 和名目版{"相同" if ebinfo["same_edits"] else "不同（改用重查結果）"}（{time.time() - t:.1f} s）')
        parts = compose.compose(cat, results)
        t = time.time()
        cross = integrate.check(cat, results, parts)
        bad_eng = integrate.engrave_failures(cross['rows'])
        if bad_eng:     # #24「1」「5」離最終切割不足 1.5：照 crosstrack spec b-6 用最終切割重算，再合成一次
            msgs = integrate.recompute_engrave_moves(cat, results, parts, bad_eng)
            for m in msgs:
                print(f'[integrate] {m}')
            parts = compose.compose(cat, results)
            cross = integrate.check(cat, results, parts)
            cross['engrave_fix'] = msgs
        cross['ebox'] = ebinfo
        print(f'跨子系統檢查：{len(cross["rows"])} 項，未通過 {len(integrate.failures(cross["rows"]))}'
              f'（{time.time() - t:.1f} s）')
        out_root = Path(a.out_root) if a.out_root else REPO
        out_dir = Path(a.out_dir) if a.out_dir else None
    n_items = sum(int(getattr(p, 'qty', 1) or 1) for p in parts)
    n_spare = sum(int(getattr(p, 'spare', 0) or 0) for p in parts)
    print(f'零件 {len(parts)} 種、{n_items} 件' + (f'＋備品 {n_spare} 件（只塞進已經開的板）' if n_spare else ''))

    sheets = layout.layout(parts)
    if cross is not None:
        from . import integrate
        cross['rows'] += integrate.check_layout(sheets, parts)
    res = export.export(sheets, parts, results, out_root, out_dir=out_dir, png=not a.no_png, cross=cross,
                        notices=_stale_trial_notice(a, out_root, out_dir))
    return cat, results, parts, cross, sheets, res, out_root


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='python -m laser_v2.build_v2', description='分幣機 v2 雷切檔產生器')
    ap.add_argument('--only-original', action='store_true', help='只排原始 60 個零件（不跑子系統與 compose）')
    ap.add_argument('--out-root', default=None, help='草稿 SVG 輸出資料夾（預設 repo 根目錄）')
    ap.add_argument('--out-dir', default=None, help='分頁 SVG／PNG／csv／report 的資料夾（預設 <out-root>/laser_v2/out）')
    ap.add_argument('--no-png', action='store_true', help='不畫預覽 PNG')
    ap.add_argument('--no-trial', action='store_true', help='不產生試切小樣（laser_v2/trial.py）')
    a = ap.parse_args(argv)

    perr = check_params()
    if perr:
        print(f'params.py 有 {len(perr)} 個地方要改（這次什麼都沒有產生，舊的輸出檔沒有動）：', file=sys.stderr)
        for s in perr:
            print(f'  - {s}', file=sys.stderr)
        print('改 laser_v2/params.py 後重跑（結束碼 3）。', file=sys.stderr)
        return EXIT_PARAMS

    from . import export, layout   # noqa: E401

    t0 = time.time()
    try:
        cat, results, parts, cross, sheets, res, out_root = _pipeline(a, export, layout)
    except Exception as e:                  # noqa: BLE001 —— 例外多半是 params 超出設計能處理的範圍，給中文說明
        import traceback
        traceback.print_exc()
        print(f'\n產生草稿時出錯（{type(e).__name__}: {e}）。\n'
              '最常見的原因是 laser_v2/params.py 的值超出設計能處理的範圍（例如板厚、模組或顯示器尺寸和暫定值差很多），'
              'check_params 的「合理範圍」只擋打錯字，擋不住這種情況：先把最近改的值改回去重跑確認；'
              '如果值是實量的、確定沒填錯，把上面的錯誤訊息回報。\n'
              '這次的輸出沒有完成（草稿、分頁檔、report.md 可能還是上一次的，或只寫了一半），不要拿去切。'
              f'（結束碼 {EXIT_QA}）', file=sys.stderr)
        print(f'耗時 {time.time() - t0:.1f} s')
        return EXIT_QA
    n_spare = sum(int(getattr(p, 'spare', 0) or 0) for p in parts)

    # ---- 摘要 ----
    print('\n===== 摘要 =====')
    for key, r in results.items():
        for w in r.get('warnings', []) or []:
            print(f'[{key}] 警告：{w}')
    cf = _check_failures(results)
    for s in cf:
        print('子系統檢查未通過 ' + s)
    cw = [f'{p.id}：{w}' for p in parts for w in (getattr(p, 'warnings', None) or [])]
    for w in cw:
        print(f'[compose] 警告：{w}')
    xf = []
    if cross is not None:
        from .integrate import failures as xfailures
        xf = xfailures(cross['rows'])
        for s in cross.get('issues', []):
            print(f'[integrate] 修改區域相交／太近：{s}')
        for r in xf:
            print(f'[integrate] 未通過 [{r["sec"]}] {r["name"]}：{r["value"]}（期望 {r["expected"]}）'
                  + (f'；{r["note"]}' if r.get('note') else ''))
        n_ok = sum(1 for r in cross['rows'] if r['ok'] is True)
        print(f'跨子系統檢查：{n_ok} 通過、{len(xf)} 未通過、'
              f'{sum(1 for r in cross["rows"] if r["ok"] is None)} 資訊（詳見 report.md 第七節）')
    for w in res.get('warnings', []):
        print(f'[export] 警告：{w}')
    from .qa import failures, notices
    bad = failures(res['qa'])                 # 草稿＋分頁 SVG 的失敗項目（注意等級不算）
    for q in notices(res['qa_draft']):
        print(f'QA 注意：{q["name"]}：{q["detail"]}')
    for q in bad:
        print(f'QA 未通過：{q["name"]}：{q["detail"]}')
    rows = res['qa_draft']
    n_ok = sum(1 for q in rows if q['ok'] or q.get('level') == 'warn')
    print(f'QA（草稿）：{n_ok}/{len(rows)} 項通過（注意 {len(notices(rows))} 項）'
          + (f'；含分頁 SVG 共 {len(bad)} 項未通過' if bad else ''))
    by = {}
    for s in sheets:
        by[s.material] = by.get(s.material, 0) + 1
    print('張數：' + '、'.join(f'{m} {n} 張' for m, n in by.items()))
    n_sp = sum(1 for s in sheets for pl in s.items if getattr(pl, 'spare', False))
    if n_spare or n_sp:
        print(f'備品：排進 {n_sp}/{n_spare} 件')
    for u in layout.unplaced_spares(sheets):
        print(f'[layout] 備品放不下（沒有排，不加張數）：{u}')
    print(f'輸出：{res["draft_svg"]}（草稿，含隱藏註記層；不要直接上機）')
    print(f'      {res["out_dir"]}（上雷切機用 sheet_*.svg〔不含註記〕、預覽 PNG、parts.csv、report.md）')
    tf = []
    if not a.only_original and not a.no_trial:
        from . import trial                 # 匯入失敗直接報錯
        print('\n===== 試切小樣 =====')
        try:
            tr = trial.run(parts, results, cat, out_root=out_root, out_dir=res['out_dir'], png=not a.no_png)
        except Exception as e:              # noqa: BLE001 —— 草稿已寫好；舊的試切檔要移除，不然會和新草稿對不上
            import traceback
            traceback.print_exc()
            removed = trial.remove_stale(out_root, res['out_dir'])
            print(f'\n[trial] 產生試切小樣時出錯（{type(e).__name__}: {e}）。草稿已照目前 params 更新；'
                  '試切小樣沒有更新，上一次的舊檔已移除：' + ('、'.join(str(p) for p in removed) if removed else '（沒有舊檔）')
                  + '。只要草稿時可以加 --no-trial。', file=sys.stderr)
            print(f'耗時 {time.time() - t0:.1f} s')
            return EXIT_QA
        bad = list(bad) + tr['qa_failures']
        tf = tr['failures']
    print(f'耗時 {time.time() - t0:.1f} s')
    if bad:
        return EXIT_QA
    if cf or xf or tf:
        return EXIT_CHECKS
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())

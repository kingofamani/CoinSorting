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
7. layout.layout(parts) → list[Sheet]；integrate.check_layout()（同板群組、張數）。
8. export.export(...)：草稿 SVG、分頁 SVG、預覽 PNG、parts.csv、report.md（含跨子系統檢查），並跑 qa.check。
9. 印出摘要（各子系統 warnings、未通過的子系統 checks、跨子系統檢查、qa 未通過項目、張數）。
10. trial.run(...)：從最終零件裁出試切小樣 → <out-root>/分幣機雷切_光耦版_v2_試切小樣.svg、
    <out-dir>/trial_report.md、trial_<材質>_<n>.png（--only-original、--no-trial 時不做）。

結束碼：0＝全部通過；1＝qa（草稿或試切小樣）有未通過項目（或流程出錯）；
        2＝qa 通過但子系統 checks、跨子系統檢查或試切小樣檢查有未通過項目。
"""
from __future__ import annotations

import argparse
import copy
import sys
import time
from dataclasses import dataclass, field, fields
from pathlib import Path

from . import params
from .catalog import REPO, Part, load_catalog
from .frames import fix_26_tooth_hole

SUBSYSTEMS = (('crosstrack', 'mods_crosstrack'), ('s1', 'mods_s1'), ('ebox', 'ebox'))
TAG_FIX26 = '修正 #26 右側第 1 個齒孔（原始檔偏 ΔV+1.000、ΔU+0.134；frames.fix_26_tooth_hole）'


@dataclass
class _V2PartLite(Part):
    """只排原始零件（--only-original）且 compose.py 還不能用時的簡易 V2Part。"""
    layer: str = 'original'
    name: str = ''
    qty: int = 1
    tags: list = field(default_factory=list)
    group: str | None = None


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='python -m laser_v2.build_v2', description='分幣機 v2 雷切檔產生器')
    ap.add_argument('--only-original', action='store_true', help='只排原始 60 個零件（不跑子系統與 compose）')
    ap.add_argument('--out-root', default=None, help='草稿 SVG 輸出資料夾（預設 repo 根目錄）')
    ap.add_argument('--out-dir', default=None, help='分頁 SVG／PNG／csv／report 的資料夾（預設 <out-root>/laser_v2/out）')
    ap.add_argument('--no-png', action='store_true', help='不畫預覽 PNG')
    ap.add_argument('--no-trial', action='store_true', help='不產生試切小樣（laser_v2/trial.py）')
    a = ap.parse_args(argv)

    from . import export, layout   # noqa: E401

    t0 = time.time()
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
    print(f'零件 {len(parts)} 種、{n_items} 件')

    sheets = layout.layout(parts)
    if cross is not None:
        from . import integrate
        cross['rows'] += integrate.check_layout(sheets, parts)
    res = export.export(sheets, parts, results, out_root, out_dir=out_dir, png=not a.no_png, cross=cross)

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
    print(f'輸出：{res["draft_svg"]}')
    print(f'      {res["out_dir"]}（report.md、parts.csv、分頁 SVG／PNG）')
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
            return 1
        bad = list(bad) + tr['qa_failures']
        tf = tr['failures']
    print(f'耗時 {time.time() - t0:.1f} s')
    if bad:
        return 1
    if cf or xf or tf:
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())

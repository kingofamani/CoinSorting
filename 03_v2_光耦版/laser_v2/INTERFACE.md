# laser_v2 產生器架構與介面

執行（Windows，先進到 `03_v2_光耦版` 資料夾；`.venv` 在上一層 repo 根目錄）：`../.venv/Scripts/python.exe -B -m laser_v2.build_v2`
原始雷切檔在 `../01_原始機構/分幣機雷切原始檔.svg`（catalog.SRC_SVG）。
→ 檢查 params → 讀原始檔 → 三個子系統 → 合併 → 跨子系統檢查 → 排版 → 輸出 → qa → 試切小樣（約 65～95 秒）。
選項：`--only-original`（只排原始 60 個零件，測排版／輸出）、`--out-root DIR`、`--out-dir DIR`、`--no-png`、`--no-trial`。

## 結束碼（build_v2）

| 碼 | 意思 |
|---|---|
| 0 | 全部通過 |
| 1 | qa（草稿、分頁 SVG 或試切小樣）有未通過項目，或流程出錯（例外） |
| 2 | qa 通過，但子系統 checks、跨子系統檢查（integrate）或試切小樣檢查有未通過項目 |
| 3 | params.py 填錯（`build_v2.check_params()`；印出中文說明，什麼都沒有產生、舊輸出不動） |

## 流程（build_v2.main）

0. `check_params()`：params.py 必要鍵都在、數值型別（不收 bool／字串）、正值、合理範圍（`build_v2.PARAM_RULES`／
   `DICT_RULES`，例如 `MODULE['slot_w']` 6～15）、`MODULE['wing']`∈{up, down, center}、`LOGO_PLAN`∈{L1, L2}
   （進階：(ΔU, ΔV)）、`TM1637['hdr_mode']`∈{RA, STRAIGHT}、`use_screws` 是 bool、`KERF_COMP`＝0、字型檔存在、
   字典裡**不認得的鍵**（打錯字；ebox／mods_s1 預設值字典的同名鍵算「進階」可以用）、`STROKE_CUT`／
   `STROKE_ENGRAVE_COLOR` 是固定值（qa 與原始檔只認得黑 0.2 切割、#ff0000 雕刻）、`NOTE_COLOR` 不和它們同色…
   錯誤訊息寫出哪個鍵、現在的值、合理範圍 → 結束碼 3。合理範圍只擋打錯字／單位錯，設計合不合由子系統 checks 判斷；
   之後的流程丟例外時（多半是 params 超出設計能處理的範圍）印中文說明、結束碼 1。
1. `load_parts()`：`catalog.load_catalog()` 拆原始檔成 60 個零件；`params.FIX_26_TOOTH_HOLE` 時
   `frames.fix_26_tooth_hole()` 修 #26 齒孔（子系統看到的是修過的 #26）。
2. 三個子系統各自 `build(copy.deepcopy(cat))`：`mods_crosstrack`、`mods_s1`、`ebox`。匯入或執行失敗直接報錯。
3. ebox 重查：`integrate.ebox_integrated(cat, results)`＝`ebox.build(cat, others=…)`，改用 mods_s1（keepout、
   #37／#26 切割）與 mods_crosstrack（#24／#26 切割、雕刻搬移、隔板外形）的實際結果，取代名目版。
4. `compose.compose(cat, results)` → `list[V2Part]`。
5. `integrate.check(cat, results, parts)`；#24「1」「5」離最終切割不足時 `integrate.recompute_engrave_moves()`
   依 crosstrack spec b-6 重算搬移，再 compose、再 check 一次。
6. `layout.layout(parts)` → `list[Sheet]`（正式件排完後，備品只塞進已經開的板）；`integrate.check_layout()`。
7. `export.export(...)`：草稿、分頁 SVG、預覽 PNG、parts.csv、report.md，並跑 qa（草稿 `mode='draft'`、
   分頁檔 `mode='sheet'`）。
8. 印摘要（警告、未通過的檢查、qa、張數、備品）。
9. `trial.run(...)`：試切小樣（`--only-original`、`--no-trial` 時不做）。

## 模組

| 檔案 | 內容 |
|---|---|
| `params.py` | 共用參數（板材、頁面、模組尺寸、設計選擇、字型）。實品量完只改這裡。 |
| `catalog.py` | 原始 SVG 拆成 60 個編號零件（`load_catalog()`），含清理（刪雜線、註記、#24 退化切線）。 |
| `frames.py` | 組裝座標 (U,V,W') ↔ 各零件原始頁座標。`fix_26_tooth_hole()` 修 #26 齒孔。 |
| `mods_crosstrack.py` | S5／S10／S50 滑升式感測座：#24/#26 階梯窗、光孔、隔板 #5/#6/#7 缺口、P1/C1/插銷。 |
| `mods_s1.py` | S1 卡匣（方案 A）：#13→#13R 加高右牆、#26/#37 新槽與窗、S1-B/C/H/F/P/(K)。 |
| `ebox.py` | 電子盒（#37 背面兩層掛勾盒）＋TM1637 正面窗：#24 窗與 Logo 移位、#26 L 形缺口、#5 前上角、#37 掛勾槽與線孔、EB-* 新零件。 |
| `compose.py` | 收集所有修改、套用到零件，保留未受影響子路徑的原始曲線；`STYLE_ENGRAVE`。 |
| `textpath.py` | 文字 → SVG path（外框線字），字型 `params.FONT_PATH`。 |
| `integrate.py` | 跨子系統檢查（A～W 節）、ebox 重查、排版檢查（L 節）。 |
| `layout.py` | 把零件排進 255×355 的板（合板、壓克力分開），備品塞進已開的板。 |
| `export.py` | 輸出草稿 SVG、分頁 SVG（上雷切機用）、預覽 PNG、parts.csv、report.md。 |
| `qa.py` | 雷切檔衛生檢查（直接讀輸出的 SVG）。 |
| `trial.py` | 試切小樣：從最終零件裁局部、排一張板、輸出與 trial_report.md。 |
| `build_v2.py` | 串起全部流程（含 params 檢查），印出檢查結果與警告，回傳結束碼。 |

## 子系統模組介面

每個子系統模組提供：

```python
def build(cat: dict[str, Part]) -> dict:
    return dict(
        edits=[...],       # 對原始零件的修改（見下）
        new_parts=[...],   # v2 新增零件（見下）
        notes=[...],       # 文字說明（寫進報告與註記圖層）
        warnings=[...],    # 依目前 params 算出的 Go/No-Go 警告（例如模組尺寸超出容許範圍）
        # 以下選用
        renames={...}, groups={...}, checks=[...], pending=[...], bom=[...], keepout={...}, station_guide='...',
    )
```

模組尺寸一律從 `params.MODULE`（以及 `TM1637`、`ESP32_BOARD`、`BATTERY_9V`）讀，不可寫死；
子系統自己的設計參數放在模組檔案開頭。

### build() 回傳的選用欄位

| key | 格式 | 說明 |
|---|---|---|
| `renames` | `{'#13': '#13R'}` | 修改後的零件換新代號（雕刻代號、報告、零件清單都用新代號；V2Part.orig_id 留舊代號） |
| `groups` | `{'#13R': 'S1-wall'}` | 原始零件（新或舊代號）或新零件加入同板群組；new_parts 也可以自己帶 `group` |
| `checks` | `[dict(name, ok: bool, value, expected, note)]` | 子系統依目前 params 算出的檢查；未通過 → build_v2 結束碼 2 |
| `pending` | `[str, ...]` | 照預設值產生、仍待使用者決定的項目（寫進 report.md 待決事項） |
| `bom` | `[dict(cat, item, qty, unit, who, note, src, per10)]` | 要另外買或要備的東西。`cat`：`'電子'`／`'五金'`／`'耗材'`／`'備品（不在切割檔）'`；`qty` 每套數量（`None`＝少量，`unit` 寫「少量」）；`per10` 選填（10 套不是 qty×10 時填文字）；`who`：「講師預組」／「老師現場」／「講師」；`src` 規格出處 |
| `keepout` | `dict(name, U=(u0, u1), V=(v0, v1), W=(w0, w1))` | 只有 mods_s1：#37 背面 S1 禁區（組裝座標 mm），ebox 重查用、integrate A／B 節檢查 |
| `station_guide` | `str` | 只有 mods_crosstrack：老師認站說明（#24 不刻站名後，沿滑道第幾個窗裝哪一站），export 寫進 report.md「組裝提醒」 |

### edits（座標一律是該零件的「原始頁座標」，mm）

| op | 欄位 | 說明 |
|---|---|---|
| `subtract` | `part`, `geom`（shapely Polygon/MultiPolygon） | 挖孔、開窗、缺口（碰到外框就變成缺口） |
| `union` | `part`, `geom` | 加料（加高、加榫） |
| `delete_cut` | `part`, `src`（例如 `'rect2[13]'`，對應 `Part.cut_src`） | 刪掉原始的某個孔（該處補成實心） |
| `translate_cut` | `part`, `src`, `dx`, `dy` | 平移原始的某個孔（例如 Logo 的菱形孔）；沒被別的 edit 碰到時保留原 src |
| `move_engrave` | `part`, `src`（`Part.engrave_src` 的元素 id）, `dx`, `dy` | 平移雕刻 |
| `add_engrave` | `part`, `d`（SVG path d，頁座標） | 新增雕刻（一律 `STYLE_ENGRAVE`；帶別的 style 會被忽略並警告） |
| `delete_engrave` | `part`, `src` | 刪除雕刻 |
| `add_engrave_text` | `part`, `text`, `x`, `y`, `size`（字高 mm）, `angle`（度）, `anchor`（`'start'/'middle'/'end'`） | 新增雕刻文字；compose 用 `textpath.py`（微軟正黑體，`params.FONT_PATH`）轉成外框線字路徑 |

每個 edit 另可帶 `tag`（中文說明，例如 `'S50 階梯窗'`），會寫進報告。

### new_parts

```python
dict(
    id='P1-S50',          # 唯一代號（雕刻在零件上的標籤也用它）
    name='S50 鎖塊',
    material='合板',      # 或 '壓克力'
    qty=1,                # 每套數量
    spare=0,              # 選用：每套另外多切的備品數（整數 ≥0，預設 0）。使用者 2026-10-08：外包兩邊都 <10 mm 的極小零件 spare＝qty
    group=None,           # 選用：同板群組（同 group 的零件排同一張板）
    geom=Polygon,         # 零件外形（區域座標，任意原點），含孔
    engrave=[d, ...],     # 雕刻路徑（同一區域座標）
    texts=[dict(text='S1-C', x=..., y=..., size=3, angle=0, anchor='middle')],  # 雕刻文字（同一區域座標）
)
```

零件上要不要雕代號由子系統自己決定，放在 `texts`。雕刻面方向有規定時，在 `name` 或 `notes` 寫清楚，例如「雕刻面朝牆」。
（使用者 2026-10-08 決定 4：#24 正面不刻 S5／S10／S50，站別改成在排線上貼標籤。）

## compose.py

```python
compose(cat: dict[str, Part], results: dict[str, dict] | None, *, fix_defects: bool | None = None) -> list[V2Part]
# results 的 key：'crosstrack'、's1'、'ebox'（各子系統 build() 的回傳）
STYLE_ENGRAVE = 'fill:none;stroke:#ff0000;stroke-width:0.2'   # 所有 v2 新增雕刻的樣式；qa 以它為準
```

* `fix_defects`：None＝照 `params.FIX_26_TOOTH_HOLE`；True／False 強制開關 #26 齒孔修正（compose 加一個
  translate_cut；傳進來的 #26 已經修過就不重複平移，只標 modified 加 tag）。
* 套用順序（同一零件的所有子系統 edits 合併後）：`delete_cut` → `translate_cut` → `union` → `subtract` →
  雕刻（`move_engrave` → `delete_engrave` → `add_engrave` → `add_engrave_text`）。
  材料＝((外框 − 各孔) ∪ 所有 union) − 所有 subtract。結果必須是單一連通零件，否則 raise ComposeError。
* 輸出：沒被 edit 碰到的原始子路徑保留原始 d（曲線不變）；被碰到的由 shapely 結果重新產生（遠離 edit 的線段保留
  原曲線，其餘折線，弦高誤差 ≤0.005 mm）；重生與新產生的子路徑刪掉長度 < 0.001 mm 的線段
  （`stats['short_dropped']`）。cut_d 的順序：外框、孔、開放線（輸出 SVG 時 export 會改成外框最後寫，見下）。
* `cut_src` 規則：
  - 保留的子路徑用原始 src（例如 `'rect2[5]'`）。
  - `translate_cut` 只平移、沒被別的 edit 碰到的孔也**保留原 src**（d 是平移後的原始曲線，列在 `stats['moved']`）。
  - 重生的環：參與的原始 src 用 `+` 連接再加 `*`（`'rect2[0]*'`、`'path131[1]+path131[2]*'`）；
    全新的孔 `'new1*'`、`'new2*'`…；裁過的開放線 `'path14[5]*'`（裁成多段 `'~1*'`、`'~2*'`）。
  - **src 結尾有 `*` ＝重生或新增；沒有 `*` ＝原始曲線**（integrate G 節據此檢查逐字保留）。
* 雕刻：全部是 `STYLE_ENGRAVE`（和原始檔一樣的 0.2 mm 紅線）；文字是外框線字（每個輪廓封閉，中空字的外框與
  字腔都刻），沒有 `<text>`、沒有填色。新增雕刻的 src：`'new-engrave-k'`／`'text:文字'`。
  字墨離最終切割 < 1.0、離其他雕刻 < 0.4 → 警告（`stats['texts']`）。

### V2Part（`catalog.Part` 的子類別，dataclass）

`catalog.Part` 的欄位（id、num、page、material、cut_d、engrave、geom、bbox、cut_src、cut_closed、engrave_src）之外：

| 欄位 | 預設 | 說明 |
|---|---|---|
| `layer` | `'original'` | `'original'`（沒被 edit 碰到）／`'modified'`／`'new'` |
| `name` | `''` | 中文名稱（原始零件用 frames 的說明，沒有的用代號） |
| `qty` | 1 | 每套數量 |
| `tags` | `[]` | 套用到這個零件的 edit 說明 |
| `group` | None | 同板群組代號 |
| `orig_id` | None | 改代號前的原始代號（新零件 None） |
| `applied` | `[]` | 套用紀錄（報告用） |
| `n_regen` | 0 | 重新產生的切割子路徑數（含全新的孔與裁過的開放線） |
| `n_kept` | 0 | 原樣保留的切割子路徑數（含只平移的孔） |
| `warnings` | `[]` | 合成警告 |
| `stats` | `{}` | 細節：kept_segments、poly_lines、vanished、filled、regen_src、new_src、touched、moved、short_dropped、texts… |
| `spare` | 0 | 每套另外多切的備品數（new_parts 的 `spare`；原始零件 0） |

座標：原始與修改零件維持「原始頁座標」；新零件用自己的區域座標（`num`＝0、`page`＝0）。

## textpath.py

```python
text_to_d(text, x, y, size, angle=0.0, anchor='start') -> str   # SVG path d，mm
```

字型讀 `params.FONT_PATH`（微軟正黑體 msjh.ttc，用第 0 個字型）。`size` 是 em 高（mm）。輸出每個輪廓封閉，
compose 用 `STYLE_ENGRAVE` 畫成外框線字。

排字工具（子系統放代號字用；2026-10-08 起字墨離切割 ≥ `TEXT_CLEAR`＝1.0、離其他雕刻線 ≥ `ENGRAVE_GAP`＝0.4）：

```python
ink_bounds(text, size, angle=0.0, anchor='start', x=0.0, y=0.0) -> (x0, y0, x1, y1)   # 字墨精確外包
ink_box(text, x, y, size, angle=0.0, anchor='start') -> Polygon                       # 字墨外框（轉 angle，保守）
fit_text(region, text, sizes, *, clear=TEXT_CLEAR, avoid=None, avoid_clear=ENGRAVE_GAP,
         angles=(0.0,), anchor='middle', prefer=None, angle_penalty=0.3) -> dict | None
# 依序試 sizes（先大字），Minkowski 精確求可放位置；有 prefer 取最近、否則取 slack 最大；放不下 None
text_spec(fit) -> dict          # fit_text 結果 → add_engrave_text／texts 用的 text/x/y/size/angle/anchor
outline_problems(text) -> tuple # 線雕檢查：輪廓封閉、不自交、彼此不交叉（空＝沒問題）
```

## 子系統自我測試（和 design/*_final 的 json 比對）

| 指令 | 內容 |
|---|---|
| `python -B -m laser_v2.mods_crosstrack` | `spec_module(wing)`：crosstrack 規格名目（bump_h＝1.5）三種翼向和 json 比對；`selftest_params()`：params 實值（back_h 2.0）跑 checks，列出和規格名目相比的幾何變化 |
| `python -B -m laser_v2.mods_s1 --selftest` | `ref_module()`：geometry_s1_final.json 的 MOD 和 params 不同的鍵（back_h＝2.0 後是空 dict，直接用 params 和 json 比對） |
| `python -B -m laser_v2.ebox --selftest` | ebox 幾何與 checks.json 比對 |
| `python -B -m laser_v2.compose`、`python -B -m laser_v2.textpath` | 模組自我測試 |

## layout.py

```python
layout(parts: list[V2Part], verbose=True) -> list[Sheet]
unplaced_spares(sheets) -> list[str]          # 放不進現有板的備品（空＝全部排進去）
```

* `Sheet`：`material`、`no`（同材質內從 1 起算）、`w`、`h`、`items: list[Placement]`、`notes`、
  `unplaced`（放不下的備品，只記在該材質最後一張）、`n_spare`、`util`、`extent`、`title`。
* `Placement`：`part`（V2Part）、`copy`（第幾份，0 起算）、`M`（3×3，零件座標 → 板座標）、`rot`、
  `spare`（bool：`copy ≥ qty` 的是備品）、`geom`、`label`（正式 `'PIN-S50（1/2）'`、備品 `'PIN-S50（備品 1/2）'`，
  只有 1 份備品時 `'S1-P（備品）'`）。
* 規則：零件可轉 0／90／180／270 度（彎曲條只轉 0／180），不鏡像；合板與壓克力分開排；同 group 排同一張板；
  零件離板邊 ≥ SHEET_MARGIN、彼此 ≥ PART_GAP（真實外形距離）。
* 備品：正式的 qty 份排完、張數定了以後，備品（copy＝qty … qty+spare−1）才逐件塞進**已經開的板**
  （先試同零件正式份所在的板，再依板序），**不會為備品開新板**；放不下的不排、記在 `Sheet.unplaced`，
  integrate L 節與 trial 檢查列為未通過。備品不受 group 限制。

## export.py

```python
export(sheets, parts, results, out_root=REPO, out_dir=None, png=True, run_qa=True, cross=None, notices=None) -> dict
# notices：呼叫端要寫進 report.md「輸出警告」的提醒（build_v2 --no-trial 時列出還留著的舊試切檔）
# 回傳 draft_svg、out_dir、sheet_svgs、pngs、csv、report、qa（草稿全部＋分頁檔失敗項）、qa_draft、qa_sheets、warnings
render_draft(sheets) -> str                     # 多頁草稿（含隱藏註記層）
render_sheet(sheet, n_same, notes=False) -> str # 單張板；預設不含註記層（上雷切機用）
cut_order(part) -> list[int]                    # 零件內切割子路徑的寫入順序
params_used_section(title) -> list[str]         # report／trial_report 的「本次使用的參數」表
```

* SVG 結構：圖層 → 零件 `<g>` → `<path>`。零件 `<g>` 有 `inkscape:label`（＝Placement.label）、`data-part`、
  `data-copy`、`data-spare`（0／1）、`data-layer`、`data-sheet`；切割 path 一個子路徑一個，`data-kind`＝
  outer／hole／line、`data-src`＝cut_src。沒有 transform（座標已套好）、沒有 `<text>`。
* **零件內寫入順序**：雕刻 → 孔與開放線（cut_d 原順序）→ **外框最後**。幾何不變；雷切軟體照檔案順序切時，
  零件要到最後才和板分開。path id 仍用原 index（`-c<i>`、`-e<i>`）。
* 顏色：黑 #000000 0.2 mm＝切割；紅 #ff0000 0.2 mm 線＝雕刻（全部 `STYLE_ENGRAVE`，紅色圖層在雷切軟體設
  「線／向量雕刻（低功率切割）」，不要用填色／掃描）；綠 #008000＝註記（只在草稿的隱藏註記層）。

## qa.py

```python
check(src, parts=None, mode=None) -> list[dict]   # dict(name, ok, detail[, level='warn'])
failures(rows) / notices(rows) / report(rows) / guess_mode(path)
python -m laser_v2.qa <svg> [...]
```

* `src`：SVG 路徑或 `list[Sheet]`。`mode`：`'draft'`（4 個圖層、註記層隱藏）／`'sheet'`（上雷切機用：剛好 3 個圖層
  「原始零件」「v2 修改」「v2 新增」，不可以有註記層、註記群組或綠色）；None＝依檔名（`sheet_*.svg`、`trial_*.svg`
  → sheet，其他 → draft）。
* 檢查項目：XML 解析、頁面、圖層名稱、沒有 `<text>`、顏色、雕刻樣式（每個雕刻元素都是 `compose.STYLE_ENGRAVE`，
  不可填色）、零件代號（含 data-spare 與標籤一致；給 parts 時核對每份正式件都在、備品份數不超過 qty＋spare、
  圖層對）、外框閉合、**零件內切割順序**（外框是群組裡最後一個元素）、雕刻在零件內、雕刻不壓切割線（注意等級）、
  無重疊重複切割線、零件不超出板、零件間距。

## integrate.py

```python
ebox_integrated(cat, results) -> (results_ebox, info)
check(cat, results, parts, cat0=None) -> dict(rows=[...], issues=[...])
engrave_failures(rows) / recompute_engrave_moves(cat, results, parts, srcs)
check_layout(sheets, parts) -> list[dict]   # L 節：同板群組、S1-B 與 #13R 同張、張數、每個零件都有排、備品都排進現有的板
failures(rows) / summary_lines(rows) / SEC_TITLE
```

每列 `dict(sec, name, ok, value, expected, note)`；`ok=None`＝資訊。

## trial.py

```python
run(parts, results, cat=None, out_root=None, out_dir=None, png=True) -> dict
# svg、sheet_svgs、report、pngs、sheets、parts、rows、qa、qa_sheets、failures、qa_failures、info
```

極小零件（外包兩邊都 <10 mm）照正式檔規則每套多一份備品（V2Part.spare 已有就照它，否則 spare＝qty），仍 1 張板。

## 輸出檔

| 檔 | 用途 |
|---|---|
| `laser_v2/out/sheet_<材質>_<n>.svg` | **上雷切機用**：每張板一個，255×355，3 個圖層，**不含註記層** |
| `laser_v2/out/sheet_<材質>_<n>.png` | 預覽圖（黑切割、紅雕刻、藍代號） |
| `laser_v2/out/parts.csv` | 零件清單（UTF-8 含 BOM）：代號、名稱、材質、每套數量、備品、尺寸(mm)、所在板、備品所在板、layer、tags |
| `laser_v2/out/report.md` | 上雷切機用哪個檔與雷切設定、組裝提醒、張數與利用率、材料與採購（含備品已排進切割檔）、實量後改哪裡與本次 params、各子系統、跨子系統檢查、待決、qa |
| `分幣機雷切_光耦版_v2_草稿.svg`（03_v2_光耦版 資料夾） | 多頁草稿（Inkscape 1.x 多頁），4 個圖層，含隱藏的「註記（不切割）」層；給人看，不要直接上機 |
| `laser_v2/out/trial_<材質>_<n>.svg` | 試切小樣，**上雷切機用**（同分頁檔規則，不含註記） |
| `laser_v2/out/trial_<材質>_<n>.png`、`trial_report.md` | 試切小樣預覽與說明（每片要測什麼、過關標準、不過關改哪裡、本次 params） |
| `分幣機雷切_光耦版_v2_試切小樣.svg`（03_v2_光耦版 資料夾） | 試切小樣多頁檔，含隱藏註記層；給人看 |

**重跑時 out/ 裡哪些檔會被動到**：`sheet_<材質>_<n>.svg／.png`、`trial_<材質>_<n>.svg／.png`（材質＝合板／壓克力，
n 是數字）每次重跑會被覆寫；這次沒有的那幾張會被移除（`export.remove_stale_outputs`：只認這種命名，SVG 還要檔頭有
產生器註解「laser_v2.build_v2 產生」或「laser_v2.trial 產生」才刪）。「sheet_合板_1 - 複製.svg」「sheet_合板_1_手改.svg」
這類自己取名的檔不會被碰；手改的檔請改名或存到別處。`--no-trial` 不刪舊試切檔，只在 report.md「輸出警告」與摘要提醒。

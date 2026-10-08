# laser_v2 產生器架構與介面

執行：`python3 -m laser_v2.build_v2` → 讀原始檔、套用各子系統修改、排版、輸出 v2 雷切檔。
（這台 Windows 上在 repo 根目錄用 `.venv/Scripts/python.exe -B -m laser_v2.build_v2`，約 95 秒，連試切小樣一起產生。）

## 模組

| 檔案 | 內容 |
|---|---|
| `params.py` | 共用參數（板材、頁面、模組尺寸、設計選擇）。實品量完只改這裡。 |
| `catalog.py` | 原始 SVG 拆成 60 個編號零件（`load_catalog()`），含清理（刪雜線、註記、#24 退化切線）。 |
| `frames.py` | 組裝座標 (U,V,W') ↔ 各零件原始頁座標。`fix_26_tooth_hole()` 修 #26 齒孔。 |
| `mods_crosstrack.py` | S5／S10／S50 滑升式感測座：#24/#26 階梯窗、光孔、隔板 #5/#6/#7 缺口、P1/C1/插銷。 |
| `mods_s1.py` | S1 卡匣（方案 A）：#13→#13R 加高右牆、#26/#37 新槽與窗、S1-B/C/H/F/P/(K)。 |
| `ebox.py` | 電子盒（#37 背面兩層掛勾盒）＋TM1637 正面窗：#24 窗與 Logo 移位、#26 L 形缺口、#5 前上角、#37 掛勾槽與線孔、EB-* 新零件。 |
| `compose.py` | 收集所有修改、套用到零件，保留未受影響子路徑的原始曲線。 |
| `layout.py` | 把合板零件排進 255×355 的頁、壓克力另排。 |
| `export.py` | 輸出多頁 SVG（Inkscape 可開）、分頁 SVG、預覽 PNG、零件清單。 |
| `build_v2.py` | 串起全部流程，印出檢查結果與警告。 |

## 子系統模組介面

每個子系統模組提供：

```python
def build(cat: dict[str, Part]) -> dict:
    return dict(
        edits=[...],       # 對原始零件的修改（見下）
        new_parts=[...],   # v2 新增零件（見下）
        notes=[...],       # 文字說明（寫進報告與註記圖層）
        warnings=[...],    # 依目前 params 算出的 Go/No-Go 警告（例如模組尺寸超出容許範圍）
    )
```

模組尺寸一律從 `params.MODULE` 讀，不可寫死；子系統自己的設計參數放在模組檔案開頭。

### edits（座標一律是該零件的「原始頁座標」，mm）

| op | 欄位 | 說明 |
|---|---|---|
| `subtract` | `part`, `geom`（shapely Polygon/MultiPolygon） | 挖孔、開窗、缺口（碰到外框就變成缺口） |
| `union` | `part`, `geom` | 加料（加高、加榫） |
| `delete_cut` | `part`, `src`（例如 `'rect2[13]'`，對應 `Part.cut_src`） | 刪掉原始的某個孔（該處補成實心） |
| `translate_cut` | `part`, `src`, `dx`, `dy` | 平移原始的某個孔（例如 Logo 的菱形孔） |
| `move_engrave` | `part`, `src`（`Part.engrave_src` 的元素 id）, `dx`, `dy` | 平移雕刻 |
| `add_engrave` | `part`, `d`（SVG path d，頁座標） | 新增雕刻（文字請先轉成路徑） |
| `delete_engrave` | `part`, `src` | 刪除雕刻 |
| `add_engrave_text` | `part`, `text`, `x`, `y`, `size`（字高 mm）, `angle`（度）, `anchor`（`'start'/'middle'/'end'`） | 新增雕刻文字；`compose.py` 用 `textpath.py`（文泉驛正黑）轉成路徑 |

每個 edit 另可帶 `tag`（中文說明，例如 `'S50 階梯窗'`），會寫進報告。

`compose.py` 套用順序（同一零件的所有子系統 edits 合併後）：
`delete_cut` → `translate_cut` → `union` → `subtract` → 雕刻操作。
結果必須仍是單一連通零件；輸出時，沒有被任何 edit 碰到的原始子路徑保留原始 d（曲線不變），
被碰到的子路徑才由 shapely 結果重新產生（折線，誤差 ≤0.02 mm）。

### new_parts

```python
dict(
    id='P1-S50',          # 唯一代號（雕刻在零件上的標籤也用它）
    name='S50 鎖塊',
    material='合板',      # 或 '壓克力'
    qty=1,                # 每套數量
    geom=Polygon,         # 零件外形（區域座標，任意原點），含孔
    engrave=[d, ...],     # 雕刻路徑（同一區域座標）
    texts=[dict(text='S1-C', x=..., y=..., size=3, angle=0, anchor='middle')],  # 雕刻文字（同一區域座標）
)
```

（零件上要不要雕代號由子系統自己決定，放在 `texts`。雕刻面方向有規定時，
在 `name` 或 `notes` 寫清楚，例如「雕刻面朝牆」。）

## 輸出

- `分幣機雷切_光耦版_v2_草稿.svg`（repo 根目錄）：多頁，每頁 255×355；圖層「原始零件」「v2 修改」「v2 新增」「註記（不切割，預設隱藏）」。
- `laser_v2/out/`：每張板一個 SVG、預覽 PNG、零件清單與檢查報告。
- 顏色：黑 #000000 0.2 mm＝切割；紅 #ff0000＝雕刻；綠 #008000＝註記（隱藏圖層）。

## 模組之間的資料格式（2026-10-07 補）

### build() 回傳的選用欄位

除了 `edits`／`new_parts`／`notes`／`warnings`，子系統可以再回傳：

- `renames`：`{'#13': '#13R'}`，修改後的零件換新代號（雕刻代號、報告、零件清單都用新代號）。
- `checks`：`[dict(name=..., ok=bool, value=..., expected=..., note=...)]`，子系統依目前 params 算出的檢查。
- `pending`：`[str, ...]`，照預設值產生、仍待使用者決定的項目（寫進 report.md 待決事項）。
- `bom`（2026-10-07 補）：`[dict(cat=..., item=..., qty=..., unit=..., who=..., note=..., src=..., per10=...)]`，
  這個子系統要另外買或要備的東西（依目前 params）。`cat` 是 `'電子'`／`'五金'`／`'耗材'`／`'備品（不在切割檔）'`；
  `qty` 是每套數量（數字，`None`＝少量／不定量，這時 `unit` 寫「少量」）；`per10` 選填，10 套的數量不是 qty×10 時填文字
  （例如備品「各 2 片」）；`who` 是「講師預組」／「老師現場」／「講師」；`src` 是規格出處。
  export.py 把三個子系統的 bom 合成 report.md「三、材料與採購（每套／10 套）」，另加板材張數與極小零件的切割注意。

`new_parts` 的 dict 可另加 `group='S1-wall'`：同一 group 的零件（含原始零件）要排在同一張板。
原始零件要加入 group，用 `groups={'#13R': 'S1-wall'}` 放在 build() 回傳裡。

### compose.py

```python
compose(cat: dict[str, Part], results: dict[str, dict]) -> list[V2Part]
# results 的 key：'crosstrack'、's1'、'ebox'（各子系統 build() 的回傳）
```

`V2Part` 是 `catalog.Part` 的子類別（dataclass），多這些欄位：

| 欄位 | 說明 |
|---|---|
| `layer` | `'original'`（沒被任何 edit 碰到）／`'modified'`／`'new'` |
| `name` | 中文名稱（原始零件沒有名稱時用代號） |
| `qty` | 每套數量（原始零件 1） |
| `tags` | 套用到這個零件的 edit 說明（list[str]） |
| `group` | 同板群組代號或 None |

座標：原始與修改零件維持「原始頁座標」；新零件用自己的區域座標。
`add_engrave_text` 與 `new_parts.texts` 在 compose 階段就用 `textpath.py` 轉成 `<path>`，之後不再出現 `<text>`。
新零件的 `num` 設 0、`page` 設 0。

### textpath.py

```python
text_to_d(text, x, y, size, angle=0.0, anchor='start') -> str   # SVG path d，mm
```

字型讀 `params.FONT_PATH`（微軟正黑體 msjh.ttc，用第 0 個字型）。`size` 是 em 高（mm）。

### layout.py

```python
layout(parts: list[V2Part]) -> list[Sheet]
```

`Sheet`：`material`、`no`（同材質內從 1 起算）、`w`、`h`、`items: list[Placement]`。
`Placement`：`part`（V2Part）、`copy`（第幾份，0 起算；qty>1 時每份各一個 Placement）、`M`（3×3，零件座標 → 板座標）。
零件可轉 0／90／180／270 度；合板與壓克力分開排；同 group 排同一張板。

### export.py ／ qa.py ／ build_v2.py

- `export.export(sheets, parts, results, out_root) -> dict`：寫出草稿 SVG、`laser_v2/out/` 下的分頁 SVG、預覽 PNG、`parts.csv`、`report.md`。
- `qa.py`：雷切檔衛生檢查（外框閉合、無重疊重複線、零件不超出板、零件之間距離 ≥ PART_GAP、沒有 `<text>`、顏色與圖層正確）。
- `build_v2.py`：`python -m laser_v2.build_v2` 串起全部流程；任何子系統匯入失敗就直接報錯，不可靜默略過。

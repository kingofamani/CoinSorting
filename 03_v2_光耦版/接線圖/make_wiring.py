"""分幣機 v2（光耦版）ESP32 接線圖產生器。

輸出同資料夾的 分幣機_v2光耦版_ESP32_接線圖.svg（版面沿用 02_v1_紅外線版/ESP32版/分幣機_ESP32_接線圖.svg）。
接線依 03_v2_光耦版/coin_sorter_opto_esp32（S1→G27、S5→G26、S10→G25、S50→G33；TM1637 CLK→G14、DIO→G13）
與 laser_v2/out/report.md 的材料表（3P 線 20／40 cm、4P 連排線 30 cm、9V 電池扣＋線上開關＋DC 插頭）。

執行（repo 根目錄）：.venv/Scripts/python.exe -B 03_v2_光耦版/接線圖/make_wiring.py

PNG（3320×2320，和 v1 同尺寸）：這台沒有 SVG 轉 PNG 的工具，改用瀏覽器畫。
  1. 執行 轉PNG/serve.py（本機 http://127.0.0.1:8765，提供這個資料夾的檔案，並接收 PNG 存回這裡）
  2. 用瀏覽器開 http://localhost:8765/轉PNG/render.html：頁面把 SVG 以 2 倍畫到畫布，自動存成同名 .png
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_SVG = os.path.join(HERE, '分幣機_v2光耦版_ESP32_接線圖.svg')
W, H = 1660, 1160
FONT = "'Microsoft JhengHei','Noto Sans CJK TC','PingFang TC',sans-serif"

RED, BLACK, YEL, YEL_EDGE = '#D7263D', '#222222', '#E0A800', '#8a6a00'
out = []


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def text(x, y, s, size=13, anchor='start', bold=False, fill='#222'):
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
               f'font-weight="{"bold" if bold else "normal"}" fill="{fill}">{esc(s)}</text>')


def rect(x, y, w, h, fill, stroke='#333', sw=2, rx=0, extra=''):
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
               f'stroke="{stroke}" stroke-width="{sw}"{extra}/>')


def circle(cx, cy, r, fill, stroke='#000', sw=1):
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def wire(pts, color, width=4, dots=True):
    p = ' '.join(f'{x},{y}' for x, y in pts)
    if color == YEL:   # 黃線加深色外框，白底上才看得清楚
        out.append(f'<polyline points="{p}" fill="none" stroke="{YEL_EDGE}" stroke-width="{width + 2}" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
    out.append(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{width}" '
               f'stroke-linejoin="round" stroke-linecap="round"/>')
    if dots:
        for x, y in (pts[0], pts[-1]):
            circle(x, y, 4.5, color)


# ---------------------------------------------------------------------------
# 標題
# ---------------------------------------------------------------------------
def draw_title():
    rect(0, 0, W, H, '#ffffff', stroke='none', sw=0)
    text(W / 2, 42, '智能分幣機 v2　接線圖（ESP32＋槽型光耦）', 30, 'middle', True)
    text(W / 2, 70, 'ESP32（WROOM-32）＋ 38P 擴展板 ＋ 4 個槽型光耦模組（LM393，槽寬 10 mm）＋ 4 位數七段顯示器（TM1637）'
         '｜電源：9V（經開關）＋原 18650（馬達）', 15, 'middle', fill='#555')


# ---------------------------------------------------------------------------
# 擴展板（位置與 v1 相同）
# ---------------------------------------------------------------------------
COLS = ['SD3', 'SD2', 'G13', 'G12', 'G14', 'G27', 'G26', 'G25', 'G33', 'G32', 'G35', 'G34']
COL_X = {name: 600 + 55 * i for i, name in enumerate(COLS)}   # 排針中心 x
Y_S, Y_V, Y_G = 420, 445, 470                                   # S／V／G 排針中心 y


def draw_board():
    rect(520, 380, 770, 430, '#7a1f86', rx=10)
    text(1276, 794, 'ESP32 38P 擴展板', 18, 'end', True, '#fff')
    text(540, 402, '上方排針', 12, bold=True, fill='#f3d9f7')
    for lab, y in (('S', 426), ('V', 451), ('G', 476)):
        text(536, y, lab, 15, 'middle', True, '#fff')
    for name in COLS:
        x = COL_X[name]
        for y, c in ((Y_S, '#3d7be0'), (Y_V, '#e03c3c'), (Y_G, '#111')):
            rect(x - 6, y - 6, 12, 12, c, stroke='#000', sw=1)
        text(x, 500, name, 13, 'middle', fill='#fff')
    text(905, 540, '由上而下：藍 S（訊號）／紅 V（電源）／黑 G（地）；腳位名稱與順序以板上印字為準', 13, 'middle', fill='#f3d9f7')
    text(905, 560, '同一種 V（或 G）全部相通；G12 會影響開機，本方案不接', 13, 'middle', fill='#f3d9f7')
    # 黃色跳帽
    rect(548, 580, 150, 58, '#fff3b0', stroke='#b8860b', rx=6)
    text(623, 603, '黃色跳帽 → 3.3V', 15, 'middle', True, '#7a4d00')
    text(623, 625, '（不可設 5V！）', 13, 'middle', True, '#b00')
    # ESP32 開發板
    rect(740, 590, 440, 140, '#111', rx=6)
    rect(708, 638, 38, 36, '#bbb', rx=4)
    text(727, 694, 'Micro', 11, 'middle', True, '#fff')
    text(727, 708, 'USB', 11, 'middle', True, '#fff')
    rect(1070, 606, 96, 108, '#c9c9c9', stroke='#888', rx=3)
    text(1118, 664, 'WROOM-32', 12, 'middle', True, '#333')
    text(900, 632, 'ESP32 開發板（插在擴展板上）', 18, 'middle', True, '#fff')
    text(900, 656, 'BOOT 鍵＝金額歸零（不重開機）', 14, 'middle', True, '#9ff0a0')
    text(900, 676, 'RST 鍵＝重開機（重新判定擋住電位）', 13, 'middle', fill='#ddd')
    text(900, 698, '燒錄卡在 Connecting… → 按住 BOOT 鍵', 13, 'middle', fill='#ffd27a')
    text(900, 718, '（或 EN–GND 加 10µF 電容，長腳接 EN）', 12, 'middle', fill='#ffd27a')
    rect(760, 752, 420, 22, 'none', stroke='#d9a7e0', rx=4, extra=' stroke-dasharray="5,4"')
    text(970, 768, '下方排針：本方案不使用', 12, 'middle', fill='#f3d9f7')
    # DC 座
    rect(488, 745, 40, 46, '#111', rx=4)
    circle(500, 768, 7, '#777', stroke='none', sw=0)
    text(540, 800, 'DC 座（6.5–16V）', 13, bold=True, fill='#fff')


# ---------------------------------------------------------------------------
# TM1637 顯示器（位置與 v1 相同）
# ---------------------------------------------------------------------------
def draw_display():
    rect(70, 130, 330, 150, '#1b3d8f', rx=8)
    rect(92, 150, 240, 80, '#000', stroke='#555', rx=4)
    text(212, 210, '88:88', 56, 'middle', True, '#ff3b3b')
    text(212, 262, '4 位數七段顯示器（TM1637）', 14, 'middle', fill='#ddd')
    for lab, y in (('CLK', 160), ('DIO', 190), ('VCC', 220), ('GND', 250)):
        rect(394, y - 6, 12, 12, '#ddd', stroke='#000', sw=1)
        text(388, y + 5, lab, 12, 'end', True, '#fff')
    wire([(400, 160), (COL_X['G14'], 160), (COL_X['G14'], Y_S)], YEL)
    wire([(400, 190), (COL_X['G13'], 190), (COL_X['G13'], Y_S)], YEL)
    wire([(400, 220), (630, 220), (630, Y_V), (COL_X['SD2'], Y_V)], RED)
    wire([(400, 250), (575, 250), (575, Y_G), (COL_X['SD3'], Y_G)], BLACK)
    text(70, 312, 'CLK→G14 的 S、DIO→G13 的 S', 15, bold=True, fill='#6b5200')
    text(70, 334, 'VCC→任一 V、GND→任一 G', 15, bold=True, fill='#6b5200')
    text(70, 354, '4P 母對母連排線 30 cm（顯示器裝在正面 #24 左上）', 13, fill='#555')


# ---------------------------------------------------------------------------
# 4 個槽型光耦模組（右上）＋ 3P 排線（每條插擴展板一整欄）
# ---------------------------------------------------------------------------
MODULES = [   # 站名、位置、接到哪一欄、排線
    ('S1', '1 元滑道內', 'G27', '3P 20 cm'),
    ('S5', '1|5 間隔條', 'G26', '3P 40 cm'),
    ('S10', '5|10 間隔條', 'G25', '3P 40 cm'),
    ('S50', '10|50 間隔條', 'G33', '3P 40～50 cm'),
]


def draw_slot_sensor(cx, top, arm_h=30, gap=32, arm_w=18):
    """槽型光耦本體：兩支臂（中間是槽）＋紅色虛線光束。"""
    rect(cx - gap / 2 - arm_w, top, arm_w, arm_h, '#222', sw=1, rx=2)
    rect(cx + gap / 2, top, arm_w, arm_h, '#222', sw=1, rx=2)
    rect(cx - gap / 2 - arm_w, top + arm_h - 8, gap + 2 * arm_w, 8, '#222', sw=1)
    out.append(f'<line x1="{cx - gap / 2}" y1="{top + 10}" x2="{cx + gap / 2}" y2="{top + 10}" '
               f'stroke="#ff4040" stroke-width="2" stroke-dasharray="4,3"/>')


def draw_modules():
    y0 = 210                              # 排線從模組端杜邦頭出來的 y
    for k, (name, loc, col, cable) in enumerate(MODULES):
        mx = 1120 + 125 * k
        xc = COL_X[col]
        text(mx, 96, name, 18, 'middle', True)
        text(mx, 113, loc, 12, 'middle', fill='#555')
        draw_slot_sensor(mx, 120)
        rect(mx - 48, 150, 96, 46, '#1f5f8b', rx=4)
        text(mx, 168, '槽型光耦 LM393', 10, 'middle', fill='#dbeafe')
        for lab, dx in (('VCC', -26), ('GND', 0), ('OUT', 26)):
            text(mx + dx, 190, lab, 9, 'middle', True, '#fff')
        rect(mx - 34, 196, 68, 14, '#444', sw=1, rx=2)          # 模組端杜邦頭
        # 3P 排線：紅 VCC→V、黑 GND→G、黃 OUT→S；越右邊的模組橫線越低，線不交叉
        yk = 262 + 28 * k
        for color, d in ((RED, -6), (BLACK, 0), (YEL, 6)):
            wire([(mx + d, y0), (mx + d, yk + d), (xc + d, yk + d), (xc + d, 404)], color, 3, dots=False)
        text(mx + 12, 228, cable, 11, fill='#555')
        # 盒端 1×3 杜邦頭蓋住整欄 S／V／G
        rect(xc - 11, 404, 22, 78, '#333', stroke='#000', sw=1.5, rx=2)
        for lab, y in (('S', Y_S), ('V', Y_V), ('G', Y_G)):
            text(xc, y + 4, lab, 10, 'middle', True, '#fff')
        text(xc, 516, name, 12, 'middle', True, '#ffe08a')
    text(1645, 428, 'S1→G27、S5→G26、S10→G25、S50→G33', 14, 'end', True, '#6b5200')
    text(1645, 448, '每條 3P 線插擴展板一整欄（S／V／G）', 13, 'end', fill='#6b5200')
    text(1645, 468, '兩端貼標籤：模組端寫站名、盒端寫欄位', 13, 'end', fill='#6b5200')


# ---------------------------------------------------------------------------
# 左側說明框：一個模組怎麼接
# ---------------------------------------------------------------------------
def draw_inset():
    rect(60, 366, 420, 254, '#f7f7f7', stroke='#999', rx=8, extra=' stroke-dasharray="6,4"')
    text(75, 390, '一個光耦模組的接法（4 個都一樣）', 15, bold=True)
    draw_slot_sensor(135, 400, arm_h=32, gap=40, arm_w=20)
    rect(80, 430, 110, 54, '#1f5f8b', rx=4)
    for lab, x in (('VCC', 105), ('GND', 135), ('OUT', 165)):
        text(x, 476, lab, 10, 'middle', True, '#fff')
        rect(x - 4, 484, 8, 8, '#ccc', sw=1)
    wire([(165, 492), (165, 512), (290, 512), (290, 447), (320, 447)], YEL)
    wire([(105, 492), (105, 530), (300, 530), (300, 477), (320, 477)], RED)
    wire([(135, 492), (135, 548), (310, 548), (310, 507), (320, 507)], BLACK)
    rect(316, 432, 30, 90, 'none', stroke='#333', sw=1.5, rx=3)
    for lab, y, c, note in (('S', 447, '#3d7be0', 'S（訊號）'), ('V', 477, '#e03c3c', 'V（3.3V）'), ('G', 507, '#111', 'G（地）')):
        rect(320, y - 11, 22, 22, c, stroke='#000', sw=1)
        text(331, y + 5, lab, 12, 'middle', True, '#fff')
        text(352, y + 5, note, 12)
    text(318, 426, '盒端 1×3 杜邦頭', 11, fill='#555')
    text(75, 574, 'VCC→V（紅）、GND→G（黑）、OUT（或 DO）→S（黃）', 13, bold=True, fill='#6b5200')
    text(75, 593, '模組腳位順序以實品印字為準（有 AO 腳的不接）', 12, fill='#555')
    text(75, 610, '光耦 VCC 一定接 V（3.3V），不要接 5V 排針', 12, bold=True, fill='#b00')


# ---------------------------------------------------------------------------
# 電源（9V 電池扣＋線上開關＋DC 插頭）、馬達電路
# ---------------------------------------------------------------------------
def draw_power():
    rect(170, 690, 120, 150, '#444', rx=8)
    rect(195, 676, 22, 16, '#bbb', rx=2)
    rect(245, 676, 22, 16, '#bbb', rx=2)
    text(230, 765, '9V', 34, 'middle', True, '#fff')
    text(230, 792, '方形鹼性', 13, 'middle', fill='#eee')
    text(230, 865, '電子部分電源', 15, 'middle', True)
    text(230, 885, '（電池扣＋線上開關＋DC 插頭，免焊線組）', 12, 'middle', fill='#555')
    wire([(206, 676), (206, 640), (400, 640), (400, 662)], RED)
    rect(388, 662, 24, 36, '#ddd', rx=4)
    out.append('<line x1="394" y1="690" x2="406" y2="670" stroke="#333" stroke-width="2"/>')
    wire([(400, 698), (400, 760), (430, 760)], RED)
    text(418, 680, '電源開關', 13, bold=True)
    text(418, 697, '（電子盒頂板）', 11, fill='#555')
    wire([(256, 676), (256, 655), (372, 655), (372, 776), (430, 776)], BLACK)
    rect(430, 749, 58, 38, '#555', rx=6)
    text(459, 810, 'DC 插頭', 13, 'middle', True)
    text(459, 830, '中心＝正極（先用電表確認）', 12, 'middle', fill='#b00')


def draw_motor():
    rect(1330, 500, 300, 300, '#fafafa', stroke='#888', rx=10, extra=' stroke-dasharray="8,6"')
    text(1480, 528, '馬達電路（獨立，不接 ESP32）', 16, 'middle', True)
    rect(1355, 560, 110, 44, '#3b7dd8', rx=8)
    text(1410, 588, '18650 ×1', 15, 'middle', True, '#fff')
    text(1410, 624, '原本的電池盒', 12, 'middle', fill='#555')
    rect(1515, 562, 50, 40, '#ddd', rx=6)
    text(1540, 588, '開關', 13, 'middle', True)
    circle(1480, 715, 38, '#f4d03f', stroke='#333', sw=2)
    text(1480, 712, 'TT', 16, 'middle', True)
    text(1480, 730, '馬達', 13, 'middle')
    wire([(1465, 574), (1515, 574)], RED)
    wire([(1565, 582), (1595, 582), (1595, 715), (1518, 715)], RED)
    wire([(1355, 592), (1342, 592), (1342, 715), (1442, 715)], BLACK)
    text(1480, 782, '維持原機構，不用改', 12, 'middle', fill='#555')


# ---------------------------------------------------------------------------
# 底部：線色、使用順序
# ---------------------------------------------------------------------------
def draw_footer():
    out.append('<line x1="40" y1="916" x2="1620" y2="916" stroke="#ccc" stroke-width="1"/>')
    text(60, 948, '線色', 18, bold=True)
    for y, c, s in ((980, RED, '紅＝V / VCC（3.3V）'), (1010, BLACK, '黑＝G / GND（地）'),
                    (1040, YEL, '黃＝S / 訊號（OUT、CLK、DIO）')):
        wire([(70, y), (120, y)], c)
        text(135, y + 5, s, 15)
    text(560, 948, '使用順序', 18, bold=True)
    lines = ['① 確認跳帽在 3.3V → 依圖插線（4 條 3P 感測器線照兩端標籤插；顯示器用 4P 連排線）',
             '② 4 個感測器槽裡清空 → 打開電源開關 → 顯示「1234」約 1.5 秒（自動判定擋住電位）→ 變成「0」',
             '③ 再打開馬達開關，倒入硬幣（每枚離開感測器時才加）；冒號亮＝C5≥C10≥C50 不成立，看序列埠',
             '④ 歸零：先停馬達、等軌道上沒有硬幣，再按 BOOT 鍵　⑤ 用完：關馬達開關、關電源開關']
    for i, s in enumerate(lines):
        text(560, 980 + 26 * i, s, 15)
    text(560, 1090, '注意：Micro-USB 燒錄時先關電源開關｜光耦 VCC 接 V（3.3V），不接 5V｜馬達不可從擴展板取電｜'
         '不接 G0、G2、G5、G12、G15（板上 BOOT 鍵可以按）', 14, bold=True, fill='#b00')
    text(560, 1118, '程式：03_v2_光耦版/coin_sorter_opto_esp32（序列埠 115200；v＝即時狀態、r＝歸零、a＝重新判定、?＝說明）',
         12, fill='#777')


def main():
    draw_title()
    draw_board()
    draw_display()
    draw_modules()
    draw_inset()
    draw_power()
    draw_motor()
    draw_footer()
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="{FONT}">\n' + '\n'.join(out) + '\n</svg>\n')
    with open(OUT_SVG, 'w', encoding='utf-8', newline='\n') as f:
        f.write(svg)
    print('輸出', OUT_SVG, f'（{len(out)} 個元素）')


if __name__ == '__main__':
    main()

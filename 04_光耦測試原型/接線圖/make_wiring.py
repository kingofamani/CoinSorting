"""光耦簡易測試原型 ESP32 接線圖產生器。

輸出同資料夾的 光耦測試原型_ESP32_接線圖.svg（版面沿用 03_v2_光耦版/接線圖/make_wiring.py，只讀不改它）。
接線依 04_光耦測試原型/opto_test_esp32（光耦 OUT→G27 的 S、VCC→V、GND→G；TM1637 可不接，CLK→G14、DIO→G13）
與 組裝與測試說明.md 第 5 節（電腦 USB 供電、母母杜邦線 3 條）。

執行（repo 根目錄）：.venv/Scripts/python.exe -B 04_光耦測試原型/接線圖/make_wiring.py

PNG（2 倍）：這台沒有 SVG 轉 PNG 的工具，改用瀏覽器畫。
  1. 執行 轉PNG/serve.py（本機 http://127.0.0.1:8768，提供這個資料夾的檔案，並接收 PNG 存回這裡）
  2. 用瀏覽器開 http://localhost:8768/轉PNG/render.html：頁面把 SVG 以 2 倍畫到畫布，自動存成同名 .png
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_SVG = os.path.join(HERE, '光耦測試原型_ESP32_接線圖.svg')
W, H = 1660, 1080
FONT = "'Microsoft JhengHei','Noto Sans CJK TC','PingFang TC',sans-serif"

RED, BLACK, YEL, YEL_EDGE, GREY = '#D7263D', '#222222', '#E0A800', '#8a6a00', '#6b6b6b'
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


def draw_title():
    rect(0, 0, W, H, '#ffffff', stroke='none', sw=0)
    text(W / 2, 42, '光耦簡易測試原型　接線圖（ESP32＋1 個槽型光耦）', 30, 'middle', True)
    text(W / 2, 70, 'ESP32（WROOM-32）＋ 38P 擴展板 ＋ 槽型光耦模組 ×1（LM393，槽寬 10 mm）＋（選用）4 位數七段顯示器 TM1637'
         '｜電源：電腦 USB（不用 9V）', 15, 'middle', fill='#555')


# ---------------------------------------------------------------------------
# 擴展板（位置與 v2 接線圖相同）
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
    text(905, 560, '同一種 V（或 G）全部相通；這台只用 G27 那一欄（顯示器另用 G14、G13）', 13, 'middle', fill='#f3d9f7')
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
    text(900, 656, '上傳卡在 Connecting… → 按住 BOOT 鍵', 14, 'middle', True, '#ffd27a')
    text(900, 678, 'EN（RST）鍵＝重開機、自動判定擋住電位', 13, 'middle', fill='#9ff0a0')
    text(900, 698, '（開機約 1 秒，槽裡不能有東西）', 13, 'middle', fill='#9ff0a0')
    rect(760, 752, 420, 22, 'none', stroke='#d9a7e0', rx=4, extra=' stroke-dasharray="5,4"')
    text(970, 768, '下方排針：不使用', 12, 'middle', fill='#f3d9f7')
    rect(488, 745, 40, 46, '#111', rx=4)
    circle(500, 768, 7, '#777', stroke='none', sw=0)
    text(540, 800, 'DC 座：這台不用', 13, bold=True, fill='#fff')


# ---------------------------------------------------------------------------
# TM1637 顯示器（選用；位置與 v2 接線圖相同）
# ---------------------------------------------------------------------------
def draw_display():
    rect(56, 118, 358, 248, 'none', stroke='#999', sw=1.5, rx=10, extra=' stroke-dasharray="7,5"')
    text(70, 112, '選用：可不接（接了會顯示目前枚數）', 13, bold=True, fill='#777')
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
    text(70, 354, '母母杜邦線 4 條', 13, fill='#555')


# ---------------------------------------------------------------------------
# 槽型光耦模組（右上）→ G27 那一欄
# ---------------------------------------------------------------------------
def draw_slot_sensor(cx, top, arm_h=34, gap=36, arm_w=20):
    """槽型光耦本體：兩支臂（中間是槽）＋紅色虛線光束。"""
    rect(cx - gap / 2 - arm_w, top, arm_w, arm_h, '#222', sw=1, rx=2)
    rect(cx + gap / 2, top, arm_w, arm_h, '#222', sw=1, rx=2)
    rect(cx - gap / 2 - arm_w, top + arm_h - 8, gap + 2 * arm_w, 8, '#222', sw=1)
    out.append(f'<line x1="{cx - gap / 2}" y1="{top + 11}" x2="{cx + gap / 2}" y2="{top + 11}" '
               f'stroke="#ff4040" stroke-width="2" stroke-dasharray="4,3"/>')


def draw_module():
    mx = 1180
    xc = COL_X['G27']
    text(mx, 96, '槽型光耦模組（LM393，槽寬 10 mm）', 17, 'middle', True)
    text(mx, 116, '裝在背牆 B 的窗上；排針朝背後', 13, 'middle', fill='#555')
    draw_slot_sensor(mx, 126)
    rect(mx - 70, 160, 140, 52, '#1f5f8b', rx=4)
    text(mx, 180, '槽型光耦 LM393', 11, 'middle', fill='#dbeafe')
    pins = (('VCC', -39, RED), ('GND', -13, BLACK), ('OUT', 13, YEL), ('AO', 39, None))
    for lab, dx, _ in pins:
        text(mx + dx, 204, lab, 10, 'middle', True, '#fff')
        rect(mx + dx - 4, 212, 8, 10, '#ccc', sw=1)
    # AO 不接
    text(mx + 39, 246, '✕ 不接', 12, 'middle', True, '#b00')
    text(mx + 64, 160 - 6, '（有的寫 DO；3 腳模組沒有 AO）', 11, 'start', fill='#555')
    # 3 條母母杜邦線：OUT→S、VCC→V、GND→G；每條各插一支針
    ys = {'VCC': 300, 'GND': 318, 'OUT': 282}
    for lab, dx, color in pins:
        if color is None:
            continue
        d = {'VCC': 0, 'GND': 6, 'OUT': -6}[lab]
        wire([(mx + dx, 222), (mx + dx, ys[lab]), (xc + d, ys[lab]), (xc + d, 404)], color, 3, dots=False)
    rect(xc - 11, 404, 22, 78, '#333', stroke='#000', sw=1.5, rx=2)
    for lab, y in (('S', Y_S), ('V', Y_V), ('G', Y_G)):
        text(xc, y + 4, lab, 10, 'middle', True, '#fff')
    text(1645, 270, 'OUT（DO）→G27 的 S', 16, 'end', True, '#6b5200')
    text(1645, 292, 'VCC→同一欄的 V、GND→同一欄的 G', 15, 'end', True, '#6b5200')
    text(1645, 312, '母母杜邦線 3 條（模組腳位順序以實品印字為準）', 13, 'end', fill='#555')


# ---------------------------------------------------------------------------
# 右側說明：線怎麼走
# ---------------------------------------------------------------------------
def draw_route_note():
    rect(1310, 390, 330, 230, '#f7f7f7', stroke='#999', rx=8, extra=' stroke-dasharray="6,4"')
    text(1325, 416, '裝在原型上時', 15, bold=True)
    lines = ['① 杜邦線先插在模組排針上，再裝模組',
             '　（裝好後排針在背牆後下方，事後難插）',
             '② 線往下走，用紙膠帶固定在底板 A，',
             '　留一點鬆度',
             '③ 不要往背後拉緊：會把模組拉歪，',
             '　光束就對不到光孔',
             '④ 底板要固定在桌上（壓重物或貼膠帶），',
             '　線拉一下整台就可能往後翻']
    for i, s in enumerate(lines):
        text(1325, 444 + 22 * i, s, 13)


# ---------------------------------------------------------------------------
# 電腦 USB（供電＋上傳＋序列埠）
# ---------------------------------------------------------------------------
def draw_usb():
    rect(110, 600, 220, 140, '#2f3640', rx=8)
    rect(124, 614, 192, 112, '#cfe3f7', stroke='none', sw=0, rx=3)
    text(220, 655, 'Arduino IDE', 16, 'middle', True, '#1f3b5c')
    text(220, 680, '序列埠 115200', 14, 'middle', fill='#1f3b5c')
    text(220, 702, 'c20 / e / v / ?', 13, 'middle', fill='#1f3b5c')
    out.append('<path d="M 90 740 L 350 740 L 370 762 L 70 762 Z" fill="#596275" stroke="#333" stroke-width="2"/>')
    text(220, 784, '電腦', 15, 'middle', True)
    wire([(350, 690), (470, 690), (470, 656), (708, 656)], GREY, 7, dots=False)
    text(360, 680, 'USB 線', 14, bold=True)
    text(220, 804, 'USB 線要能傳資料（不是只能充電的那種）', 12, 'middle', fill='#555')
    text(220, 822, '供電、上傳程式、看序列埠都靠這條', 12, 'middle', fill='#555')


# ---------------------------------------------------------------------------
# 底部：線色、使用順序
# ---------------------------------------------------------------------------
def draw_footer():
    out.append('<line x1="40" y1="836" x2="1620" y2="836" stroke="#ccc" stroke-width="1"/>')
    text(60, 868, '線色', 18, bold=True)
    for y, c, s in ((900, RED, '紅＝V / VCC（3.3V）'), (930, BLACK, '黑＝G / GND（地）'),
                    (960, YEL, '黃＝S / 訊號（OUT、CLK、DIO）')):
        wire([(70, y), (120, y)], c)
        text(135, y + 5, s, 15)
    text(135, 990, '（杜邦線顏色不限，照腳位插就好）', 12, fill='#777')
    text(560, 868, '使用順序', 18, bold=True)
    lines = ['① 跳帽設 3.3V → 杜邦線先插在模組排針上：OUT→G27 的 S、VCC→V、GND→G（AO 不接）',
             '② USB 接電腦 → Arduino IDE 開 opto_test_esp32.ino、開發板選 ESP32 Dev Module → 上傳（Connecting… 時按住 BOOT）',
             '③ 序列埠 115200 → 按 EN 重開：開機約 1 秒自動判定擋住電位，槽裡不能有東西',
             '④ 紙片擋住光束約 1 秒再拿開，確認判定沒反 → 輸入 v 看「■ 擋住／· 沒擋」→ 照《組裝與測試說明》第 7 節做 T1～T7']
    for i, s in enumerate(lines):
        text(560, 900 + 26 * i, s, 15)
    text(560, 1010, '注意：光耦 VCC 接 V（3.3V），不接 5V｜AO 不接｜這台不用 9V 和 DC 座｜'
         '不接 G0、G2、G5、G12、G15（板上 BOOT 鍵可以按）', 14, bold=True, fill='#b00')
    text(560, 1038, '程式：04_光耦測試原型/opto_test_esp32（c20＝丟 20 枚、e＝報告、v＝即時電位、p＝看抖動、?＝說明）',
         12, fill='#777')


def main():
    draw_title()
    draw_board()
    draw_display()
    draw_module()
    draw_route_note()
    draw_usb()
    draw_footer()
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="{FONT}">\n' + '\n'.join(out) + '\n</svg>\n')
    with open(OUT_SVG, 'w', encoding='utf-8', newline='\n') as f:
        f.write(svg)
    print('輸出', OUT_SVG, f'（{len(out)} 個元素）')


if __name__ == '__main__':
    main()

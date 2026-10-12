"""組裝教學網頁每一步要畫的圖（make_figures.py 讀這個檔）。

欄位：
  id        圖檔前綴（img/{id}-sheet.png、{id}-asm.png、{id}-flat.png）
  sheet     零件位置圖：這些零件在 4 張板上塗色標出
  installed 組裝示意圖：已經裝好的零件（木色）
  new_asm   組裝示意圖：這一步新加的零件（青色）。只有機身 11 片有組裝座標
  side      組裝示意圖要不要畫側視（預設要）
  flat      零件攤平圖：同一比例並排、畫雕刻
  flat_row  攤平圖每列寬（mm），越小零件畫得越大
"""

BODY = ['#24', '#26']
SPACERS = ['#7', '#6', '#5']
CABINET = ['#12', '#13R', '#21']
V2_CHANGED = ['#24', '#26', '#37', '#13R', '#21', '#7', '#6', '#5']

STEPS = [
    # ---- 開始前 ----
    dict(id='s-v2', sheet=V2_CHANGED, flat=V2_CHANGED, flat_row=470),

    # ---- 講師預組 ----
    dict(id='a-lock', sheet=['P1-S5', 'C1-S5', 'P1-S10', 'C1-S10', 'P1-S50', 'C1-S50', 'PIN-S50'],
         flat=['C1-S5', 'P1-S5', 'C1-S10', 'P1-S10', 'C1-S50', 'P1-S50', 'PIN-S50'], flat_row=150),
    dict(id='a-s1', flat=['S1-C', 'S1-B', 'S1-F', 'S1-P', 'S1-H'], flat_row=150),
    dict(id='a-ebox', flat=['EB-E', 'EB-F', 'EB-S', 'EB-T', 'EB-K', 'EB-WL', 'EB-WR', 'EB-B'], flat_row=300),

    # ---- 老師組裝 ----
    dict(id='b-small', flat=['#9', '#10', '#11', '#15', '#19', '#25', '#52', '#53', '#54', '#55', '#56', '#57',
                             '#16', '#17', '#20', '#23', '#14', '#58', '#18', '#59', '#22'], flat_row=150),
    dict(id='b-drawer', flat=['#32', '#39', '#41', '#49', '#45', '#52'], flat_row=250),
    dict(id='b-cab', new_asm=CABINET, flat=CABINET, flat_row=300),
    dict(id='b-front', new_asm=BODY),
    dict(id='b-spacer', installed=BODY, new_asm=SPACERS, flat=SPACERS, flat_row=200),
    dict(id='b-cabin', installed=BODY + SPACERS, new_asm=CABINET),
    dict(id='b-motor', flat=['#1', '#2', '#3', '#4'], flat_row=160),
    dict(id='b-back', installed=BODY + SPACERS + CABINET, new_asm=['#37']),
    dict(id='b-ends', installed=BODY + SPACERS + CABINET + ['#37'], new_asm=['#31', '#36']),
    dict(id='b-rotor', flat=['#18', '#62', '#14', '#16', '#17'], flat_row=210),
    dict(id='b-ring', flat=['#63', '#27'], flat_row=260),
]

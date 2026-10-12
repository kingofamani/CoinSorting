"""ebox_final 參數（裁判合併版）。單位 mm。
組裝座標 (U, V, W')：U 0＝右端轉盤側→246 左端；V 0＝面板頂→114 底（沿 60° 斜面往下）；
W' 0＝#26 背面，往後為正；#24 在 -6~-3、#26 在 -3~0、#37 在 29~32。
改這裡 → python3 -B run_all.py（model → checks → sens → export → fig）。"""

T = 3.0            # 合板厚（實測後改）
C_TAB = 0.1        # 一般榫槽單邊餘隙（槽寬 = T + 2*C_TAB = 3.2）
C_HOOK = 0.2       # #37 掛勾槽單邊餘隙
MIN_WEB = 2.0      # 新切割留下的料寬下限

# ---------------------------------------------------------------- TM1637（暫定，實品量到後改）
DISP = dict(
    pcb_w=42.0, pcb_h=24.0, pcb_t=1.6,
    body_w=30.0, body_h=14.0, body_H=7.2,      # 0.36 吋四位 LED 塊
    body_dx=0.0, body_dy=0.0,                  # LED 塊中心相對 PCB 中心（+dx 往觀看者右手 −U；+dy 往下 +V）
    back_h=2.6, back_inset=1.0,                # 背面零件最高、零件區離 PCB 邊
    hole_d=2.2, hole_dx=19.0, hole_dy=10.0,    # 固定孔（沒有孔就 use_screws=False）
    use_screws=True,
    hdr_mode='RA',                             # 'RA' 彎針朝觀看者右手（−U）；'STRAIGHT' 直針朝後
    hdr_pins=4, hdr_pitch=2.54, hdr_dy=0.0, hdr_body=2.5, pin_h=1.27,
    dup_len=14.0, dup_sq=2.54, dup_gap=1.0, wire_bend=5.5,
)
DISP_UR = 193.5    # PCB 右緣（觀看者右手，U 小側）
DISP_VP = None     # PCB 上緣 V；None＝自動：上排 M2 孔到 #24 頂邊料寬 ≥2.0 且 ≥V5（名目算出 5.5；D2 用 5.0 只有 1.8）
C_WIN = 0.3        # #24 LED 窗單邊餘隙
C_SCREW = 0.1      # M2 孔 Ø(hole_d + 2*C_SCREW) = Ø2.4
C_NOTCH = 0.5      # #26 缺口對 PCB／杜邦頭／螺帽
C_DIV = 0.8        # #5 前上角對 PCB 背面零件的讓位
NUT_M2 = dict(d_circ=4.62, t=1.6)
SCREW_M2 = dict(L=8.0, head_d=3.8, head_h=1.3)
WIRE_D = 1.4

# 顯示器線越過機頂的位置（#37 頂邊 U 形缺口中心）。D2 原在 U175.8；本版移到 U168，
# 讓出 U≥173 給電池帶（線在 #24 背面 V5.5~9 先往 −U 走約 8 mm 再越頂）。
CABLE_U = 168.0
CABLE_NOTCH_37 = dict(w=6.5, depth=4.5)        # 寬（U）× 深（V，從頂邊 V4 往下）
CABLE_RUN_V = (5.5, 9.5)                        # 線在 #24 背面水平段的 V 範圍（熱熔膠固定）

# Logo（#24 雕刻 path1-5-9 ＋ 9 個菱形切穿孔）整組平移 (ΔU, ΔV)；model.py 會重新搜尋並驗證
LOGO_SHIFT = (-13.5, 17.0)                      # 方案 L2：移到顯示窗正下方、「10」與「50」之間（搜尋最佳 3.38）
LOGO_SHIFT_ALT = (-50.5, 7.0)                   # 方案 L1：移到「5」(新位置) 與「10」之間（搜尋最佳 3.50）

# ---------------------------------------------------------------- 電子盒（掛 #37 背面）
BOX = dict(
    U_WL=146.0,        # 左牆 EB-WL 的 −U 面（從背面看在左；離 S1 禁區 U133 有 13）
    U_WR=237.0,        # 右牆 EB-WR 的 −U 面（內面）；外面 240，#37 掛勾槽到 #37 左緣 U243 料寬 2.8
    V_top=4.0,         # 頂板 EB-T 上面（＝#37 頂邊 V4）
    W_front=32.25,     # 牆前緣（#37 外面 32.0 + 0.25）
    W_back=70.0,       # 牆後緣
    gap=3.0,           # #37 外面到底板 EB-B 前面
    top_W0=50.0,       # 頂板開關區前緣 W'（前面留給顯示器線、電池扣線）
    wl_notch=(32.25, 42.0, 41.0, 53.0),   # 左牆前緣排線口 W'0,W'1,V0,V1（感測器線進盒）
)
HOOK = dict(lip_W0=25.0, lip_back=28.85, neck_h=6.0, lip_len=6.0, levels=(13.5, 29.0), chamfer=1.0)   # 下層 31→29：勾唇離 5 元翻倒弧 ≥8
BOARD = dict(L=78.0, W=53.5, t=1.6, standoff=4.8, hole_inset=3.0, hole_d=3.4,
             c_end=0.5,          # 板端到右牆內面
             c_top=1.0, c_bot=1.0,   # 板上緣到電池架、板下緣到底板下緣（讓 M3 孔四周料寬 ≥2）
             hdr_h=8.5, dev_t=1.6, dev_comp=3.0, dev_len=55.0, dev_w=28.0, usb_inset=2.0,
             gvs_V_off=6.0, male_h=2.5, dup_len=14.0, bend=5.5,
             usb_V_off=26.75, btn_dv=8.5, usb_w=8.0, usb_h=2.6, usb_plug=(11.0, 8.0),     # 插頭外殼 (V, W')
             dc_V_off=6.5, dc_d=9.0, dc_h=11.0, dc_len=14.0, dc_plug_d=10.0,
             en_V_off=(11.7, 25.7),
             pin1_from_antenna=5.0, pitch=2.54)
# 9V 電池「電池帶」：躺在盒頂、長邊沿 U，頂面凸出盒頂 bat_proud，往上（−V）直接拔出
BATT = dict(L=48.5, W=26.5, Tk=17.5, c=0.25, clip=12.5, proud=4.0)   # L 沿 U、Tk 沿 V、W 沿 W'
SWITCH = dict(cut_a=9.0, cut_b=13.5, body_depth=14.0, U0=152.0, W0=53.0)   # 同原機馬達開關 13.5×9，轉 90°：U 9 × W' 13.5
SERVICE_WIN_C = 1.0          # USB/DC 服務窗：插頭外殼外加 1.0
SENSOR_HOLE_37 = (88.0, 100.0, 40.0, 46.0)   # 感測器線過 #37 的孔 U0,U1,V0,V1（右側空腔→背面）

# ---------------------------------------------------------------- 外部禁區（其他子系統）
S1_ZONE = dict(U=(94.0, 133.0), V=(50.7, 79.0), W=(32.0, 40.0))   # s1wall_d1 背蓋＋排針 ∪ s1wall_d2 排針區（保守聯集）
MOTOR_SW = (40.25, 53.75, 1.0, 19.23)                          # #37 原馬達開關孔
# 質量（重心計算）
RHO = {'椴木合板 0.55': 0.55e-3, 'MDF 0.75': 0.75e-3}
M_ITEMS = dict(batt=46.0, board=22.0, esp32=10.0, clip_sw=14.0, wires=12.0, screws=4.0, disp=7.0)
SHEET = (255.0, 355.0)
STRIP = (245.0, 96.5)        # 第 1 張 #24＋#37 並排後下方剩下的長條（sheet 分析）

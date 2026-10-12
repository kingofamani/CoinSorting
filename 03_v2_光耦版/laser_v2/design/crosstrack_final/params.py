# crosstrack_final 參數表（單位 mm）。實品模組量到後只改這裡，再依序重跑：
#   python3 -B model.py && python3 -B checks.py && python3 -B export.py && python3 -B fig.py
# 也可用環境變數覆寫：CT_OVR='{"slot_d":8.8,"wing":"down"}' python3 -B checks.py
import json, os

P = dict(
    # ---------- 模組（暫定，待實量） ----------
    slot_w=10.0,     # 槽寬：兩臂內面距（沿光束＝W'）
    slot_d=9.0,      # 槽深：臂頂到槽底
    beam_sb=5.0,     # 光束中心離槽底
    arm_t=7.0,       # 單臂沿光束厚
    arm_w=6.4,       # 臂寬（沿軌道 s）
    arm_top=12.0,    # 臂頂離 PCB 上面
    pcb_L=27.6,      # PCB 沿光束長
    pcb_W=20.0,      # PCB 垂直光束寬（沿 s）
    pcb_t=1.6,       # PCB 厚
    pcb_e=0.5,       # 光耦本體側邊到 PCB 短邊（本體靠 PCB 一邊；置中時改 wing='center'）
    wing='up',       # PCB 長邊（翼）朝哪邊：'up'＝上游（往右、往轉盤）、'down'＝下游（往左）、'center'＝本體置中
    comp_h=2.0,      # PCB 上面零件最高
    bump_h=1.5,      # PCB 下面焊點／插件腳凸出
    hdr_len=8.0,     # 3P 排針沿光束方向佔的長度（含杜邦頭外殼）
    hdr_up=14.0,     # 排針＋杜邦頭從 PCB 上面往上（+n）的高度（直立排針朝上時）
    # ---------- 設計 ----------
    h=2.5,           # 光束中心離軌道面（垂直軌道量）。使用者原值「約 3」，見 spec §d
    delta_u={'S5': 0.0, 'S10': 0.0, 'S50': 0.0},   # 光束 U 相對間隔條中心的偏移（光束高度處）
    c=0.4,           # PCB 寬段開窗、隔板缺口的單邊餘隙
    c_body=0.15,     # 窗窄段（光耦本體）單邊餘隙：靠它定位光束 s 位置
    c_ntop=1.0,      # 隔板缺口頂端（臂頂上方）餘隙
    g_strip=0.2,     # 軌下保留條底面到光耦槽底
    c_slide=1.0,     # 低位推入時臂頂到保留條底面
    c_back=0.3,      # 後臂內面到 #26 背面（往前推到底時）
    c_stop=0.5,      # 擋面往後再讓 0.5（靜止時後臂外面貼擋面）
    c_v=0.3,         # 零件頂、焊點底的上下餘隙
    lh_u=1.8,        # #26 光孔沿 U 寬（兩側邊平行開口邊，即沿 V）
    lh_n=3.6,        # #26 光孔垂直軌道高（光束 ±1.8）
    fit=0.1,         # 新零件與窗、孔的繪製單邊間隙（切縫另計）
    cap_m=3.0,       # 蓋板 C1 超出窗的邊寬
    t=3.0,           # 板厚
    v_drawer=97.5,   # #24 前方任何東西的 V 上限（#24 下緣 V98，抽屜在下方）
    chamfer=2.0,     # 隔板擋面下端導角
    min_web=2.0,     # 開窗後殘料小於此值就併入開口（不留易斷碎片）
    kerf=0.15,       # 雷切切縫（只用於公差估算，不做補償；原始檔也沒做）
)

ovr = os.environ.get('CT_OVR')
if ovr:
    P.update(json.loads(ovr))


def derived(P=P):
    D = {}
    D['n_sb'] = P['h'] - P['beam_sb']                          # 光耦槽底
    D['n_arm_top'] = D['n_sb'] + P['slot_d']                    # 臂頂
    D['n_pcb_top'] = D['n_sb'] - (P['arm_top'] - P['slot_d'])   # PCB 上面
    D['n_pcb_bot'] = D['n_pcb_top'] - P['pcb_t']                # PCB 下面
    D['n_comp'] = D['n_pcb_top'] + P['comp_h']                  # 零件頂
    D['n_bump'] = D['n_pcb_bot'] - P['bump_h']                  # 焊點底
    D['n_strip'] = D['n_sb'] + P['g_strip']                     # 保留條底（窗窄段頂）
    D['n_shoulder'] = D['n_comp'] + P['c_v']                    # 窗寬段頂（PCB 翼上方）
    D['slide'] = D['n_arm_top'] - (D['n_strip'] - P['c_slide'])  # 上滑行程
    D['n_win_bot'] = D['n_bump'] - D['slide'] - P['c']          # 窗底
    a = P['arm_w'] / 2
    short = a + P['pcb_e']; long_ = P['pcb_W'] - short
    if P['wing'] == 'up':
        D['pcb_up'], D['pcb_dn'] = long_, short
    elif P['wing'] == 'down':
        D['pcb_up'], D['pcb_dn'] = short, long_
    else:
        D['pcb_up'] = D['pcb_dn'] = P['pcb_W'] / 2
    # W'（靜止：後臂外面貼擋面）
    D['W_stop'] = P['c_back'] + P['c_stop'] + P['arm_t']        # 隔板擋面
    D['W_ra'] = (D['W_stop'] - P['arm_t'], D['W_stop'])        # 後臂
    D['W_fa'] = (D['W_ra'][0] - P['slot_w'] - P['arm_t'], D['W_ra'][0] - P['slot_w'])
    ov = (P['pcb_L'] - 2 * P['arm_t'] - P['slot_w']) / 2
    D['pcb_ov'] = ov
    D['W_pcb'] = (D['W_fa'][0] - ov, D['W_ra'][1] + ov)
    D['W_deep'] = D['W_pcb'][1] + P['c']                        # 隔板深缺口後壁
    D['t_strip'] = -D['n_strip']                                # #24 保留條厚（光耦段）
    D['t_shoulder'] = -D['n_shoulder']                          # #24 肩部厚（PCB 翼段）
    return D


if __name__ == '__main__':
    D = derived()
    for k, v in D.items():
        print(k, v if not isinstance(v, float) else round(v, 3))

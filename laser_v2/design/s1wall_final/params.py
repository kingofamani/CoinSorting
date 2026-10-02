"""S1 最終規格（方案 A：右櫃側板加高成 1 元滑道右牆＋背插卡匣＋前臂導流帽）參數表。
實品模組量到後只改 MOD；也可用環境變數 S1F_OVR='{"slot_w":9.6,"arm_top":11.8}' 覆寫任何鍵。
"""
import os, json, copy

# ---------------- 模組（暫定值，實量後改） ----------------
MOD = dict(
    pcb_L=27.6,     # PCB 沿光束方向長（裝好後沿 W'）
    pcb_W=20.0,     # PCB 垂直光束寬（裝好後沿 V）
    pcb_t=1.6,      # PCB 厚（裝好後沿 U）
    arm_t=7.0,      # 單臂沿光束厚
    arm_w=6.4,      # 臂寬（垂直光束、平行 PCB；裝好後沿 V），也當作光耦本體寬
    arm_top=12.0,   # 臂頂離 PCB 元件面
    slot_w=10.0,    # 槽寬（兩臂內面距）
    slot_d=9.0,     # 槽深（臂頂到槽底）
    beam_sb=5.0,    # 光束中心離槽底
    body_e=0.5,     # 光耦本體側邊到 PCB 長邊（本體靠 PCB 的一條長邊）
    pcb_ovf=0.0,    # PCB 前端（W' 小）超出前臂外面的量；本體置中時 =(pcb_L-24)/2=1.8
    comp_h=2.0,     # PCB 元件面最高零件（SOIC-8 約 1.75）
    back_h=2.0,     # PCB 背面焊點／插件腳凸出
    aperture=1.0,   # 光窗寬（估計；用於「遮光餘量」扣除）
)

# ---------------- 設計參數 ----------------
DES = dict(
    T=3.0,            # 合板標稱厚（實際 2.7~3.2）
    s_pcb=1.0,        # PCB 背面離牆滑道面 U107.875 的墊高＝1.0 mm 雙面泡棉膠（0~1.5 可調光束 U，見 §d）
    Vb=74.0,          # 光束中心 V
    wb=29.3,          # 後臂內面 W'（#37 內面 29.0 之後 0.3）
    c_tab=0.15,       # 木榫槽單邊餘隙（長、寬兩向都加）
    c_opt=0.4,        # 光耦／臂／導流帽通過 #37 窗的單邊餘隙
    c_pcb=0.4,        # PCB 通過 #37 窗的單邊餘隙
    fit=0.1,          # 小填塊（S1-P、S1-K）比窗縮小的單邊量
    wall_top=30.0,    # 加高牆頂 V（1 元開口右端頂緣約 V31.4；能量上界見 §e）
    tabs_front=[(50.5, 56.0), (68.0, 74.5)],   # #13R 前榫（插 #26）V 範圍：都在軌道以下（#24 實料擋在前面）
    tabs_back=[(36.0, 48.0)],                  # #13R 後榫（插 #37）V 範圍：在背蓋 S1-F 範圍（V≥50.7）之外
    tab_len_26=2.6,   # 插 #26 的榫長（< 最薄板 2.7，榫尖不露出 #26 前面）
    tab_len_37=3.0,   # 插 #37 的榫長（＝#37 厚）
    corner_fix=True,  # 修 KNOWN_DEFECTS['37-cutout-corners'] 右側：#13R 在 #37 板厚內讓到 V84.0
    corner_fix_V=84.0,
    # 前臂導流帽 S1-H（3 片 (V,W') 剖面片，黏在前臂頂面）
    cap=True,
    cap_h=4.5,        # 帽頂前緣比臂頂高（沿 V）；坡角約 63°
    cap_layers=3,
    # 背蓋與螺絲
    cover_v1=78.0,    # 背蓋下緣 V（#13R 在 #37 後方的櫃頂邊約 V79.7）
    screw='M3 尼龍螺絲＋螺帽（預黏在 #37 空腔側）',
    screw_hole_cover=3.4, screw_hole_37=3.4,
    # S1-C 前榫（插 #26 槽 C）
    tabC_front_v=(59.0, 65.0),
    comp_band_free=False,   # 實品 PCB 在 W'29~35、本體以上那條帶上沒有元件時改 True：背蓋不切元件帶、另切 S1-K 填塊
    s1c_v1=78.5,
)

GEO = dict(U13_out=104.875, U13_in=107.875, U7_in=135.876, W37=29.0, W37_out=32.0,
           open1=(114.104, 134.604), D=20.0, t=1.85)


def _ovr():
    s = os.environ.get('S1F_OVR')
    if s:
        for k, v in json.loads(s).items():
            (MOD if k in MOD else DES)[k] = v


_ovr()


def derived(M=None, Dd=None):
    M = MOD if M is None else M
    Dd = DES if Dd is None else Dd
    g = GEO
    h_sb = M['arm_top'] - M['slot_d']                     # 槽底（本體頂）離 PCB 元件面
    h_beam = h_sb + M['beam_sb']                          # 光束離 PCB 元件面
    U_pcb_back = g['U13_in'] + Dd['s_pcb']
    U_pcb = U_pcb_back + M['pcb_t']
    wb = Dd['wb']; wa = wb - M['slot_w']
    fa = (wa - M['arm_t'], wa); ba = (wb, wb + M['arm_t'])
    body_len = 2 * M['arm_t'] + M['slot_w']
    pw0 = fa[0] - M['pcb_ovf']
    pw1 = pw0 + M['pcb_L']
    Vb = Dd['Vb']
    av = (Vb - M['arm_w'] / 2, Vb + M['arm_w'] / 2)
    pv1 = av[1] + M['body_e']
    pv0 = pv1 - M['pcb_W']
    D = dict(h_sb=h_sb, h_beam=h_beam, h_beam_back=h_beam + M['pcb_t'],
             U_pcb_back=U_pcb_back, U_pcb=U_pcb, U_sb=U_pcb + h_sb, Ub=U_pcb + h_beam,
             U_tip=U_pcb + M['arm_top'], U_comp=U_pcb + M['comp_h'], U_solder=U_pcb_back - M['back_h'],
             wa=wa, wb=wb, front_arm=fa, back_arm=ba, pcb_w=(pw0, pw1), pcb_v=(pv0, pv1),
             Vb=Vb, arm_v=av, body_len=body_len)
    D['cap_Vr'] = av[0] - Dd['cap_h']
    D['cap_U'] = (D['U_sb'], D['U_tip'])
    return D


def snapshot():
    return copy.deepcopy(MOD), copy.deepcopy(DES)


if __name__ == '__main__':
    for k, v in derived().items():
        print(k, v)

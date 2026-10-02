"""敏感度：一次改一個尺寸，從名目往兩側掃，找第一個失效點。只用 2D／解析判據（快），
判據與 checks.py 同一套門檻。→ sens_out.txt、sens.json"""
import types, copy
from model import *
import params as PR0


def clone(**kw):
    pr = types.SimpleNamespace(**{k: copy.deepcopy(getattr(PR0, k)) for k in dir(PR0) if not k.startswith('_')})
    for k, v in kw.items():
        if '.' in k:
            a, b = k.split('.')
            getattr(pr, a)[b] = v
        else:
            setattr(pr, k, v)
    return pr


def auto(pr):
    """產生器自動規則：板長變大時左牆往左移（保留 6 mm 走線灣），下限 S1 禁區 U133+1。"""
    U_bd0 = pr.BOX['U_WR'] - pr.BOARD['c_end'] - pr.BOARD['L']
    pr.BOX['U_WL'] = min(146.0, U_bd0 - 6.0 - pr.T)
    return pr


G12 = G12_WV; G21 = G21_WV


def fails(M, pr):
    f = []
    D = M.D
    # ---- 顯示器
    pcb = rect(*M.disp['PCB'][:4])
    if not pcb.buffer(-1.5).contains(M.WIN):
        f.append('LED 窗超出 PCB 內縮 1.5（PCB 壓不住 #24 背面）')
    if D['body_H'] - 3.0 < 0.5:
        f.append('LED 面凸出 #24 <0.5（會被窗緣遮）')
    front = unary_union([M.WIN] + M.screw_heads)
    for nm, e in ENG_NEW.items():
        if front.distance(e) < 2.0:
            f.append(f'窗／螺絲頭碰雕刻{nm}（{front.distance(e):.2f}）')
    okL = [lab for lab, e in (('L2', M.logo), ('L1', M.logo_alt)) if e['clear'] >= 3.0 and e['see'] == 0 and e['inside']]
    if not okL:
        f.append(f'Logo 的 L2、L1 兩個位置都不行（L2 {M.logo["clear"]:.2f}／L1 {M.logo_alt["clear"]:.2f}；需重新搜尋）')
    if M.holes and min(v for u, v in M.holes) - (D['hole_d'] / 2 + pr.C_SCREW) - 4.0 < pr.MIN_WEB:
        f.append('M2 孔到 #24 頂邊料寬 <2')
    if M.WIN.bounds[1] - 4.0 < 3.0:
        f.append('窗上緣料寬 <3')
    if M.NOTCH26.distance(LineString([(243, 0), (243, 120)])) < 3.0 or M.NOTCH26.bounds[2] > 240.0:
        f.append('#26 缺口離 #26 左緣 <3（PCB 太寬／太靠左）')
    for c, op in OPEN.items():
        if M.NOTCH26.distance(op) < 10:
            f.append(f'#26 缺口離 {c} 元開口 <10'); break
    if M.NOTCH26.distance(SLOT24) < 8:
        f.append('#26 缺口離斜槽靠背區 <8')
    slots26 = [h for h in H26 if h.area < 120 and not h.intersects(rect(198.3, 201.5, 16.9, 27.1))]
    for h in slots26:
        if h.distance(M.NOTCH26) < 2.5:
            f.append(f'#26 缺口離隔板榫槽 U{h.bounds[0]:.0f} V{h.bounds[1]:.0f} <2.5'); break
    ct6 = Polygon(CTJ['parts']['#26_slot_tab6']['UV'])
    if ct6.distance(M.NOTCH26) < 2.5:
        f.append('#26 缺口離 crosstrack 新 #6 槽 <2.5')
    if M.DIV5_CUT_W > 6.0:
        f.append(f'#5 前上角要削到 W\'{M.DIV5_CUT_W:.1f}（>6，隔板頂太弱）')
    if M.DIV5_WV.geom_type != 'Polygon':
        f.append('#5 v2 斷成兩塊')
    if M.NOTCH_B is not None and M.riser[0] < 168.626 + 0.5:
        f.append('上升線壓到 #6 隔板（U168.6）')
    # ---- 電子盒
    if pr.BOX['U_WL'] < 134.0 - 1e-9:
        f.append(f'左牆要移到 U{pr.BOX["U_WL"]:.1f}（<134，進入 S1 禁區）')
    if M.U_E0 < pr.CABLE_U + pr.CABLE_NOTCH_37['w'] / 2 + 1.5 - 1e-9:
        f.append(f'電池帶太長：端擋 EB-E 要到 U{M.U_E0:.1f}，擋到顯示器線越頂處')
    sw_body_u1 = pr.SWITCH['U0'] + pr.SWITCH['cut_a'] + 1.0
    if sw_body_u1 > pr.CABLE_U - 2.8 - 1.0:
        f.append('開關本體擋到顯示器線')
    if M.Vb > 77.5 + 1e-9:
        f.append(f'盒底 V{M.Vb:.2f} > 77.5')
    bot = Polygon([(pr.BOX['W_front'], M.Vb - 5), (pr.BOX['W_back'], M.Vb - 5), (pr.BOX['W_back'], M.Vb), (pr.BOX['W_front'], M.Vb)])
    if bot.distance(G12) < 2.0 or bot.distance(G21) < 2.0:
        f.append(f'盒底離 #12／#21 <2（{min(bot.distance(G12), bot.distance(G21)):.2f}）')
    BD = pr.BOARD
    Wgvs1 = M.board[5] + BD['male_h'] + BD['dup_len'] + BD['bend']
    if Wgvs1 > pr.BOX['W_back'] - 1.0:
        f.append(f'杜邦頭＋彎線到 W\'{Wgvs1:.1f}，超出盒後緣')
    def ov(a, b, m):   # 兩個區間在餘隙 m 下是否相交
        return a[0] < b[1] + m and b[0] < a[1] + m
    sw = M.CONTENTS['開關本體']
    for other in ('未用排針列（上）', 'ESP32 開發板＋母座', '擴展板 PCB'):
        o = M.CONTENTS[other]
        if ov(sw[0:2], o[0:2], 1.0) and ov(sw[2:4], o[2:4], 1.0) and ov(sw[4:6], o[4:6], 1.0):
            f.append(f'開關本體碰到{other}'); break
    wr = [b for b in M.BOX if b.name.startswith('EB-WR')][0]
    if wr.poly.geom_type != 'Polygon' or M.SERVICE_WIN.bounds[0] < pr.BOX['W_front'] + 2.0 or M.SERVICE_WIN.bounds[2] > pr.BOX['W_back'] - 2.0 \
            or M.SERVICE_WIN.bounds[3] > M.Vb - 2.0 or M.SERVICE_WIN.bounds[1] < 17.1 + 2.0:
        f.append(f'服務窗超出右牆可用範圍（W\'{M.SERVICE_WIN.bounds[0]:.1f}~{M.SERVICE_WIN.bounds[2]:.1f}，V{M.SERVICE_WIN.bounds[1]:.1f}~{M.SERVICE_WIN.bounds[3]:.1f}）')
    for b in M.BOX:
        if b.poly.geom_type != 'Polygon':
            f.append(f'{b.name} 斷成多塊'); break
    if 70.0 - M.W_S0 < 9.0:
        f.append('電池太厚（W\'）：頂板後條太窄')
    if M.board[3] > M.Vb:
        f.append('擴展板超出盒底')
    return f


def sweep(label, key, nominal, lo, hi, step, rebuild=lambda v: {}, use_auto=False):
    vals_up = np.arange(nominal, hi + 1e-9, step); vals_dn = np.arange(nominal, lo - 1e-9, -step)
    res = {}
    for direction, vals in (('上', vals_up), ('下', vals_dn)):
        last_ok = nominal; why = '掃描範圍內不失效'
        for v in vals:
            pr = clone(**{key: v}, **rebuild(v))
            if use_auto:
                pr = auto(pr)
            M = build(pr)
            fl = fails(M, pr)
            if fl:
                why = f'{v:.2f}：' + '；'.join(fl[:2]); break
            last_ok = v
        res[direction] = (last_ok, why)
    return dict(label=label, nominal=nominal, ok_range=(res['下'][0], res['上'][0]), fail_up=res['上'][1], fail_dn=res['下'][1])


if __name__ == '__main__':
    base_fail = fails(build(PR0), PR0)
    rows = []
    rows.append(sweep('TM1637 PCB 寬 pcb_w', 'DISP.pcb_w', 42.0, 34.0, 52.0, 0.5))
    rows.append(sweep('TM1637 PCB 高 pcb_h', 'DISP.pcb_h', 24.0, 16.0, 34.0, 0.5))
    rows.append(sweep('LED 塊寬 body_w', 'DISP.body_w', 30.0, 22.0, 42.0, 0.5))
    rows.append(sweep('LED 塊高 body_h', 'DISP.body_h', 14.0, 8.0, 24.0, 0.5))
    rows.append(sweep('LED 塊離 PCB 高 body_H', 'DISP.body_H', 7.2, 2.0, 14.0, 0.2))
    rows.append(sweep('LED 塊左右偏 body_dx', 'DISP.body_dx', 0.0, -8.0, 8.0, 0.5))
    rows.append(sweep('LED 塊上下偏 body_dy', 'DISP.body_dy', 0.0, -8.0, 8.0, 0.5))
    rows.append(sweep('背面零件高 back_h', 'DISP.back_h', 2.6, 0.0, 8.0, 0.2))
    rows.append(sweep('杜邦頭長 dup_len', 'DISP.dup_len', 14.0, 8.0, 30.0, 0.5))
    rows.append(sweep('固定孔 hole_dx', 'DISP.hole_dx', 19.0, 12.0, 24.0, 0.5))
    rows.append(sweep('固定孔 hole_dy', 'DISP.hole_dy', 10.0, 5.0, 14.0, 0.5))
    rows.append(sweep('擴展板長 L（左牆自動左移）', 'BOARD.L', 78.0, 70.0, 100.0, 0.5, use_auto=True))
    rows.append(sweep('擴展板寬 W', 'BOARD.W', 53.5, 45.0, 62.0, 0.25))
    rows.append(sweep('墊高 standoff', 'BOARD.standoff', 4.8, 2.0, 12.0, 0.2))
    rows.append(sweep('開發板母座高 hdr_h', 'BOARD.hdr_h', 8.5, 5.0, 14.0, 0.25))
    rows.append(sweep('USB 中心離板上緣 usb_V_off', 'BOARD.usb_V_off', 26.75, 10.0, 45.0, 0.5))
    rows.append(sweep('DC 座中心離板上緣 dc_V_off', 'BOARD.dc_V_off', 6.5, 3.0, 30.0, 0.5))
    rows.append(sweep('9V 電池長 L（沿 U）', 'BATT.L', 48.5, 44.0, 56.0, 0.25))
    rows.append(sweep('電池扣長 clip', 'BATT.clip', 12.5, 6.0, 20.0, 0.25))
    rows.append(sweep('9V 電池厚 Tk（沿 V）', 'BATT.Tk', 17.5, 14.0, 22.0, 0.25))
    rows.append(sweep('9V 電池寬 W（沿 W\'）', 'BATT.W', 26.5, 22.0, 32.0, 0.25))
    rows.append(sweep('電池凸出盒頂 proud', 'BATT.proud', 4.0, 0.0, 10.0, 0.5))
    rows.append(sweep('開關本體深 body_depth', 'SWITCH.body_depth', 14.0, 8.0, 30.0, 0.5))
    with open(HERE + '/sens_out.txt', 'w') as fo:
        fo.write(f'名目狀態失效項：{base_fail or "無"}\n')
        for r in rows:
            fo.write(f"{r['label']}：名目 {r['nominal']}；可用 {r['ok_range'][0]:.2f} ~ {r['ok_range'][1]:.2f}；往上失效 {r['fail_up']}；往下失效 {r['fail_dn']}\n")
        pr = clone(**{'DISP.hdr_mode': 'STRAIGHT'})
        M = build(pr); fo.write(f"排針改直針朝後（STRAIGHT）：{fails(M, pr) or 'OK'}；#26 缺口 {[round(v, 2) for v in M.NOTCH26.bounds]}\n")
        pr = clone(**{'DISP.use_screws': False})
        M = build(pr); fo.write(f"不用 M2 螺絲（熱熔膠）：{fails(M, pr) or 'OK'}\n")
        for vv in (28.0, 30.0, 34.0):
            pr = clone(**{'DISP.use_screws': False, 'DISP.pcb_h': vv})
            M = build(pr); fo.write(f"不用螺絲、pcb_h={vv}：{fails(M, pr) or 'OK'}\n")
    json.dump(rows, open(HERE + '/sens.json', 'w'), ensure_ascii=False, indent=1, default=float)
    print(open(HERE + '/sens_out.txt').read())

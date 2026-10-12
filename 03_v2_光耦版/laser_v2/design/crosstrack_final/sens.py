# 敏感度：v2 已依名目切好，實品模組某尺寸偏差多少會失效（一次只動一個）；以及設計參數 h 的比較
import copy, json
from model import *
from checks import run

P_nom = copy.deepcopy(P0)
D_nom = derived(P_nom)
APERT_H = 1.2     # 假設光耦收發窗高（n 方向），用來算光束可偏的範圍


def fit_margins(Pa):
    """切割幾何用名目（D_nom），模組用實品 Pa。回傳各項餘量（<0 即失效）"""
    Da = derived(Pa)
    a_nom = P_nom['arm_w'] / 2
    m = {}
    # 模組靜止：PCB 下面壓在 P1 上（n_pcb_bot 名目），各高度相對 PCB 下面
    pb = D_nom['n_pcb_bot']
    sb = pb + Pa['pcb_t'] + (Pa['arm_top'] - Pa['slot_d'])         # 實際槽底
    beam = sb + Pa['beam_sb']
    m['光束在光孔內（含收發窗半高）'] = min(beam - APERT_H / 2 - (P_nom['h'] - P_nom['lh_n'] / 2),
                              (P_nom['h'] + P_nom['lh_n'] / 2) - (beam + APERT_H / 2))
    m['槽底低於保留條（P1 塞得進）'] = D_nom['n_strip'] - sb
    # 低位：模組整體下降 slide（名目），臂頂要低於保留條
    arm_top_low = sb + Pa['slot_d'] - D_nom['slide']
    m['低位臂頂低於保留條'] = D_nom['n_strip'] - arm_top_low
    m['臂頂低於隔板缺口頂'] = (D_nom['n_arm_top'] + P_nom['c_ntop'] * 0.94) - (sb + Pa['slot_d'])
    m['本體寬進得了窗窄段'] = (2 * a_nom + 2 * P_nom['c_body']) - Pa['arm_w']
    # W'：後臂外面貼擋面 W_stop
    m['後臂內面在 #26 背面之後'] = D_nom['W_stop'] - Pa['arm_t'] - 0.0
    fa_in = D_nom['W_stop'] - Pa['arm_t'] - Pa['slot_w']
    m['前臂內面離 #24 前面（板厚 3.2 時）'] = (-6.0 - 0.2) - fa_in - 0.3
    pcb_back = D_nom['W_stop'] + (Pa['pcb_L'] - 2 * Pa['arm_t'] - Pa['slot_w']) / 2
    m['PCB 後端不碰深缺口'] = D_nom['W_deep'] - pcb_back
    # s：本體貼窄段下游壁 → 光束 s = a_nom - arm_w/2
    s_beam = a_nom - Pa['arm_w'] / 2
    m['光束 s 在光孔內（收發窗寬 1.0）'] = (P_nom['lh_u'] / T[0] / 2 - 0.5) - abs(s_beam)
    m['PCB 下游邊在窗內'] = (D_nom['pcb_dn'] + P_nom['c']) - (s_beam + Da['pcb_dn'])
    m['PCB 上游邊在窗內'] = (D_nom['pcb_up'] + P_nom['c'] + 2 * P_nom['c_body']) - (Da['pcb_up'] - s_beam)
    m['零件頂低於肩部'] = D_nom['n_shoulder'] - (pb + Pa['pcb_t'] + Pa['comp_h'])
    m['焊點不碰 P1 讓位／窗底'] = min((pb - Pa['bump_h']) - (D_nom['n_bump'] - P_nom['c_v']),
                                (pb - Pa['bump_h'] - D_nom['slide']) - D_nom['n_win_bot'])
    return m


def thresholds():
    rows = []
    tests = [('beam_sb', 5.0), ('slot_d', 9.0), ('arm_top', 12.0), ('pcb_t', 1.6), ('arm_w', 6.4), ('arm_t', 7.0),
             ('slot_w', 10.0), ('pcb_L', 27.6), ('pcb_W', 20.0), ('pcb_e', 0.5), ('comp_h', 2.0), ('bump_h', 1.5)]
    for key, nom in tests:
        lo = hi = None
        for d in np.arange(0, 6.01, 0.05):
            Pa = copy.deepcopy(P_nom); Pa[key] = nom + d
            if hi is None and min(fit_margins(Pa).values()) < -1e-9:
                hi = round(d - 0.05, 2); hi_fail = min(fit_margins(Pa).items(), key=lambda kv: kv[1])[0]
            Pa = copy.deepcopy(P_nom); Pa[key] = nom - d
            if lo is None and (nom - d <= 0 or min(fit_margins(Pa).values()) < -1e-9):
                lo = round(d - 0.05, 2); lo_fail = min(fit_margins(Pa).items(), key=lambda kv: kv[1])[0] if nom - d > 0 else '—'
        rows.append(dict(param=key, nominal=nom, minus=lo, minus_fail=lo_fail if lo is not None else '',
                         plus=hi, plus_fail=hi_fail if hi is not None else ''))
    return rows


def h_study():
    out = []
    for h in (2.0, 2.5, 3.0):
        P = copy.deepcopy(P_nom); P['h'] = h
        C = run(P)
        st = C['stations']
        out.append(dict(h=h, strip24_body=st['S5']['strip24_body'], strip24_wing=st['S5']['strip24_wing'],
                        S10_web_bottom=st['S10'].get('win_to_24_bottom'), S50_exit_final=st['S50']['exit_plane_clear_final'],
                        gap_5_5=st['S5']['touching_gap']['5-5']['at_beam'], gap_10_10=st['S10']['touching_gap']['10-10']['at_beam'],
                        gap_50_50=st['S50']['touching_gap']['50-50']['at_beam'],
                        lh_bottom=st['S5']['lh_n_range'][0], S5_dn_tip_arm=st['S5']['tip_fall_sweep']['5元']['hits'].get('後臂', {}).get('depth')))
    return out


if __name__ == '__main__':
    print('名目餘量', {k: round(v, 2) for k, v in fit_margins(P_nom).items()})
    T_ = thresholds()
    for r_ in T_:
        print(r_)
    H = h_study()
    for r_ in H:
        print(r_)
    json.dump(dict(nominal_margins={k: round(v, 3) for k, v in fit_margins(P_nom).items()}, thresholds=T_, h_study=H),
              open('sens.json', 'w'), ensure_ascii=False, indent=1)

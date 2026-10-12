"""裁判重算：設計 1、設計 2 的關鍵數字與問題（輸出 verify_designs.txt）。"""
import sys, json, math
sys.dont_write_bytecode = True
import numpy as np
from shapely.geometry import Polygon, box, LineString, Point
from shapely.ops import unary_union
import base as B
L = []
def log(*a):
    s = ' '.join(str(x) for x in a); L.append(s); print(s)
# ---- 共用 ----
o0, o1 = B.OPEN1
log('1 元開口 U', round(o0, 3), round(o1, 3), '；#7 右面', B.U7[0], '；#13 滑道面', B.U13[1])
log('保證覆蓋區（硬幣平行 #37）', round(B.U7[0] - 20, 3), '~', round(B.U13[1] + 20, 3))
# ---- 設計 1 ----
log('\n== 設計 1 ==')
ub = 107.875 + 1.6 + 3.0 + 5.0
log('光束 U', ub, '離左界', round(ub - (B.U7[0] - 20), 3))
# S1-B 讓位孔料寬
log('S1-B 外框 (0,0)-(16.7,19)+榫，讓位孔 (1.5,2.8)-(16.2,17.5) → 後側料寬', round(16.7 - 16.2, 2), 'mm（太細）')
# 齒孔修正方式
log('#26 齒孔：設計 1 用「往上補 1.0（聯集）」→ 孔變 V84.03~88.98（高 4.95）；catalog KNOWN_DEFECTS 修法是整孔平移 (−1.000 V, −0.134 U) → V84.025~87.975、U104.899~107.849（與 #24 孔對齊、孔高不變）')
# ---- 設計 2 ----
log('\n== 設計 2 ==')
ramp = Polygon([(0.3, 59.5), (9.3, 63.0), (19.3, 69.5), (19.3, 81.5), (0.3, 81.5)])
for w in ('up', 'down', 'center'):
    S = B.s5_boxes(w)
    sw = S['sweep_UV']; Wmax = max(S['W_max'], S['W_deep'])
    # 3D 交集（體積）：U 在導流坡 U113.875~134.875，W' ≤ Wmax，(W',V) 在 ramp 內 且 (U,V) 在 sweep 內
    vol = 0.0
    dU = 0.25; dW = 0.25; dV = 0.25
    for U in np.arange(113.875 + dU / 2, 134.875, dU):
        seg = LineString([(U, 0), (U, 120)]).intersection(sw)
        if seg.is_empty:
            continue
        v0, v1 = seg.bounds[1], seg.bounds[3]
        sec = ramp.intersection(box(0, v0, Wmax, v1))
        vol += sec.area * dU
    fin = unary_union([g for nm, g, (w0, w1) in S['mod_final'] if w1 > 0])
    vol_f = 0.0
    for U in np.arange(113.875 + dU / 2, 134.875, dU):
        seg = LineString([(U, 0), (U, 120)]).intersection(fin)
        if seg.is_empty:
            continue
        sec = ramp.intersection(box(0, seg.bounds[1], 9.6, seg.bounds[3]))
        vol_f += sec.area * dU
    log(f'導流坡 L1~L7 與 S5（翼 {w}）重疊：最終位置 ≈{vol_f:.0f} mm³、含安裝掃掠 ≈{vol:.0f} mm³（掃掠 (U,V) {[round(x,1) for x in sw.bounds]}，W\'≤{Wmax:.1f}）')
# 槽 A 位置
seg = LineString([(106.375, -5), (106.375, 60)]).intersection(B.SLOT24)
log('#24 斜槽在 U106.375 的 V 範圍', [round(x, 2) for x in seg.bounds[1::2]], '；#26 頂緣在 U104.9~107.8 約 V4.0~4.9')
x = LineString([(106.375, -5), (106.375, 60)]).intersection(B.O26)
log('#26 外形在 U106.375 從 V', round(x.bounds[1], 2))
log('設計 2 槽 A：U104.925~107.825 × V12.425~15.575 → 離 #24 斜槽頂', round(seg.bounds[1] - 15.575, 2), '（槽 A 在 #24 斜槽上緣之上，被 #24 實料擋住）')
# 通道證明
nW = None
for t in np.linspace(0.8, 1.0, 20001):
    if 20 * math.sqrt(1 - t * t) + 1.57 * t <= 9.7:
        nW = t; break
nU = math.sqrt(1 - nW ** 2)
log(f'設計 2 通道 9.7：n_W≥{nW:.3f}（夾角 ≤{math.degrees(math.acos(nW)):.1f}°）→ U 寬 ≥{20*math.sqrt(1-nU**2)+1.57*nU:.2f}，右緣 ≤{135.876-(20*math.sqrt(1-nU**2)+1.57*nU):.2f}（光束 117.475）')
open('verify_designs.txt', 'w').write('\n'.join(L) + '\n')

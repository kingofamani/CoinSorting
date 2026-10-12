import sys, json
sys.dont_write_bytecode = True
import sim
import os
cases = json.loads(os.environ['CASES']) if os.environ.get('CASES') else [('Z', {}), ('B', {'s_pcb': 0.0}), ('B', {'s_pcb': 0.5}), ('B', {'s_pcb': 1.0}), ('B', {'s_pcb': 1.5}),
         ('A', {'s_pcb': 1.0}), ('D', {'s_pcb': 0.0}), ('D', {'s_pcb': 1.0}), ('C', {'s_pcb': 1.0})]
cases = [(c[0], c[1]) for c in cases]
OUT = os.environ.get('OUT', 'sim_random.json')
n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
res = sim.main_random(n, [c[0] for c in cases], [c[1] for c in cases])
def entered(r): return any(pt[3] > 0.5 for pt in r['path'])
rows = []
for var, over in cases:
    R = [r for r in res if r['variant'] == var and r['over'] == over]
    E = [r for r in R if entered(r)]
    ok = sum(r['outcome'] == 'exit' and r['pulses'] == 1 for r in E)
    miss = sum(r['outcome'] == 'exit' and r['pulses'] == 0 for r in E)
    dbl = sum(r['pulses'] >= 2 for r in E)
    jam = sum(r['outcome'] != 'exit' for r in E)
    tS1 = sum(any(t.startswith('S1_') for t in r['touched']) for r in E)
    w = [x for r in E if r['pulses'] == 1 for x in r['widths_ms']]
    rows.append(dict(var=var, over=over, n=len(R), entered=len(E), ok=ok, miss=miss, double=dbl, jam=jam, touch_S1=tS1,
                     wmin=min(w) if w else None, wmed=sorted(w)[len(w)//2] if w else None))
    print(rows[-1], flush=True)
json.dump(dict(rows=rows, runs=res), open(OUT, 'w'), ensure_ascii=False)

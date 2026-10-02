"""依序重跑：model（自檢）→ checks → sens → export → fig。python3 -B run_all.py"""
import subprocess, sys
for f in ('model.py', 'checks.py', 'sens.py', 'export.py', 'fig.py'):
    print('==>', f, flush=True)
    r = subprocess.run([sys.executable, '-B', f], cwd=__file__.rsplit('/', 1)[0])
    if r.returncode:
        sys.exit(r.returncode)

#!/usr/bin/env python3
"""Run a bounded strict-native boot test and retain status and a rendered frame."""
from pathlib import Path
import os
import subprocess
import time

root = Path(__file__).resolve().parents[1]
control = root / 'private' / ('smoke-' + str(time.time_ns()))
control.mkdir(parents=True)
log_path = root / 'logs' / 'smoke-native.log'
env = dict(os.environ, MELEE_STRICT_NATIVE='1', MODERNGEKKO_STATICRECOMP='1')
with log_path.open('w') as log:
    proc = subprocess.Popen([str(root/'scripts/run_macos.sh'), '--automation-dir', str(control)],
                            stdout=log, stderr=subprocess.STDOUT, env=env)
    try:
        deadline = time.monotonic() + 30
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(0.25)
        if proc.poll() is not None:
            print(log_path.read_text()[-5000:])
            raise SystemExit(f'Boot exited early: {proc.returncode}')
        status = control/'status.txt'
        print(status.read_text() if status.exists() else 'No status produced')
        subprocess.run(['python3',str(root/'scripts/control.py'),'--directory',str(control),
                        'screenshot','path=boot.png'],check=True)
        deadline = time.monotonic()+5
        while not (control/'boot.png').exists() and time.monotonic()<deadline:
            time.sleep(0.1)
        print('Evidence directory:',control)
        if not (control/'boot.png').exists():
            raise SystemExit('Boot produced no screenshot')
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        print('Runtime exit:',proc.returncode)
        print('Log:',log_path)

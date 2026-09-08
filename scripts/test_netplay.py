#!/usr/bin/env python3
"""Two local peers, isolated saves, synchronized boot, bounded runtime."""
import os
import subprocess
import time
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
folder=ROOT/'private'/('netplay-test-'+str(int(time.time())))
folder.mkdir()
peers=[]
try:
    for role in ('host','join'):
        user=folder/role
        (user/'Config').mkdir(parents=True)
        (user/'Config/GCPadNew.ini').write_text((ROOT/'config/GCPadNew.ini').read_text())
        env=dict(os.environ, MODERNGEKKO_STATICRECOMP='1', MELEE_STRICT_NATIVE='1', MELEE_NETPLAY_SMOKE='1')
        env.pop('MELEE_FRONTEND',None)
        log=(folder/(role+'.log')).open('w')
        args=[str(ROOT/'build/runtime/moderngekko-run'),'--game',str(ROOT/'private/GALE01r2'),'--module',str(ROOT/'build/game/gGALE01_recomp.dylib'),'--user-dir',str(user),'--graphics','Metal','--audio','Null','--no-mods','--automation-dir',str(user/'automation'),'--netplay-port',os.environ.get('MELEE_TEST_PORT','32626'),'--nickname',role,'--controller','Quartz/0/Keyboard & Mouse']
        args+=['--netplay-host'] if role=='host' else ['--netplay-join','127.0.0.1']
        proc=subprocess.Popen(args,env=env,stdout=log,stderr=subprocess.STDOUT)
        peers.append((role,proc,log,user))
        if role=='host': time.sleep(3)
    deadline=time.time()+75
    passed=False
    while time.time()<deadline:
        snapshots={}
        for role,proc,log,user in peers:
            status=user/'automation/status.txt'
            snapshots[role]=dict(line.split('=',1) for line in status.read_text().splitlines() if '=' in line) if status.exists() else {}
        if all(int(s.get('frame_count','0'))>=300 for s in snapshots.values()):
            passed=True
            break
        if any(p.poll() is not None for _,p,_,_ in peers): break
        time.sleep(1)
    report={'passed':passed,'folder':str(folder),'status':snapshots}
    (folder/'result.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)
finally:
    for role,proc,log,user in peers:
        proc.terminate()
    for role,proc,log,user in peers:
        try: proc.wait(timeout=10)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        log.close()

#!/usr/bin/env python3
"""Bounded two-peer native boot with real paired WebSocket phone inputs.

Run with private/phonepad-venv/bin/python scripts/test_phone_netplay.py.
Requires a complete native build and locally supplied game data.
"""
import asyncio
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time

from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[1]


def free_port(kind):
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def status(path):
    if not path.exists():
        return {}
    return dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)


async def phone(url, token):
    async with connect(url) as ws:
        await ws.send(json.dumps({'p': 0, 'token': token}))
        reply = json.loads(await ws.recv())
        if not reply.get('ok'):
            raise RuntimeError(f'Phone pairing failed: {reply}')
        # Exercise Start and A through the phone bridge, then keep the controller
        # live. This verifies input transport, not full match correctness.
        for buttons in (32, 0, 1, 0, 1, 0):
            await ws.send(json.dumps({'p': 0, 'b': buttons}))
            await asyncio.sleep(.2)
        while True:
            await ws.send('{"p":0,"b":0}')
            await asyncio.sleep(.2)


async def main():
    folder = ROOT/'private'/f'phone-netplay-test-{time.time_ns()}'
    folder.mkdir(parents=True)
    peers = []
    phones = []
    net_port = free_port(socket.SOCK_DGRAM)
    report = {'passed': False, 'folder': str(folder), 'scope': 'two local peers; native boot and phone transport, not a full internet match'}
    try:
        for role in ('host', 'join'):
            user = folder/role
            web_port = free_port(socket.SOCK_STREAM)
            udp_port = free_port(socket.SOCK_DGRAM)
            log = (folder/f'{role}.log').open('w')
            args = [str(ROOT/'scripts/play_phones.sh'), role]
            if role == 'join':
                args += ['127.0.0.1']
            args += ['--netplay-port', str(net_port), '--web-port', str(web_port),
                     '--udp-port', str(udp_port), '--nickname', role,
                     '--lan-address', '127.0.0.1', '--user-dir', str(user),
                     '--automation-dir', str(user/'automation'), '--audio', 'Null']
            proc = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT,
                                    env=dict(os.environ, MELEE_NETPLAY_SMOKE='1'), start_new_session=True)
            peers.append((role, proc, log, user, web_port))
            # Wait for actual controller receiver readiness before joining.
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                text = (folder/f'{role}.log').read_text()
                match = re.search(r'Phone pairing link: http://[^\s]+#([^\s]+)', text)
                if match:
                    phones.append(asyncio.create_task(phone(f'ws://127.0.0.1:{web_port}/ws', match[1])))
                    break
                if proc.poll() is not None:
                    raise RuntimeError(f'{role} exited: {text[-2000:]}')
                await asyncio.sleep(.2)
            else:
                raise RuntimeError(f'{role} never became ready; see {folder}')
        deadline = time.monotonic() + 75
        while time.monotonic() < deadline:
            snapshots = {role: status(user/'automation/status.txt') for role, _, _, user, _ in peers}
            logs = {role: (user/'Logs/phone-input.log').read_text() for role, _, _, user, _ in peers}
            for task in phones:
                if task.done():
                    task.result()
            if all(int(s.get('frame_count', 0)) >= 600 and s.get('booted') == '1'
                   for s in snapshots.values()) and all('packets: P1=' in log for log in logs.values()):
                report.update(passed=True, status=snapshots)
                break
            if any(proc.poll() is not None for _, proc, _, _, _ in peers):
                raise RuntimeError('A peer exited before the frame target')
            await asyncio.sleep(.5)
        if not report['passed']:
            report['error'] = 'Native peers did not reach the frame/input target before timeout'
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        for task in phones:
            task.cancel()
        await asyncio.gather(*phones, return_exceptions=True)
        for _, proc, _, _, _ in peers:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGINT)
        for _, proc, log, _, _ in peers:
            try:
                await asyncio.to_thread(proc.wait, timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                await asyncio.to_thread(proc.wait)
            log.close()
        (folder/'result.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))

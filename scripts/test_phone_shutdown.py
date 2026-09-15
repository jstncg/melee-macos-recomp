#!/usr/bin/env python3
"""Opt-in native regression: terminating a phone launcher must stop its game.

Requires a complete native build and phone setup. Runs SIGTERM and SIGHUP checks
with isolated saves. Uses actual child PIDs and ports to verify cleanup.
"""
from pathlib import Path
import os
import signal
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def free_port(kind):
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def check(signum):
    user = ROOT/'private'/f'phone-shutdown-test-{time.time_ns()}'
    user.mkdir(parents=True)
    web_port = free_port(socket.SOCK_STREAM)
    udp_port = free_port(socket.SOCK_DGRAM)
    children = []
    with (user/'launch.log').open('w') as log:
        proc = subprocess.Popen([str(ROOT/'scripts/play_phones.sh'), 'local',
             '--web-port', str(web_port), '--udp-port', str(udp_port),
             '--user-dir', str(user), '--audio', 'Null', '--lan-address', '127.0.0.1'],
             stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic()+45
            while time.monotonic() < deadline:
                if 'Phone pairing link:' in (user/'launch.log').read_text():
                    break
                if proc.poll() is not None:
                    raise RuntimeError((user/'launch.log').read_text())
                time.sleep(.1)
            else:
                raise RuntimeError(f'Launcher did not become ready: {user}')
            children = [int(x) for x in subprocess.check_output(
                ['pgrep', '-P', str(proc.pid)], text=True).split()]
            if not children:
                raise RuntimeError('No native game child was launched')
            proc.send_signal(signum)
            proc.wait(timeout=10)
            for pid in children:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    continue
                raise RuntimeError(f'{signum.name} left native game {pid} running')
            for kind, port in ((socket.SOCK_STREAM, web_port), (socket.SOCK_DGRAM, udp_port)):
                with socket.socket(socket.AF_INET, kind) as probe:
                    probe.bind(('127.0.0.1', port))
            print(f'{signum.name}: game stopped and both phone ports released', flush=True)
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            for pid in children:
                try:
                    os.killpg(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass


if __name__ == '__main__':
    for signum in (signal.SIGTERM, signal.SIGHUP):
        check(signum)

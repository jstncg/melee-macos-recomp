#!/usr/bin/env python3
"""Send one command to this port's local development automation directory."""
import argparse
from pathlib import Path
import time
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('command', choices=['pad', 'pad_frames', 'clear_pad', 'pause', 'resume', 'screenshot', 'stop'])
p.add_argument('fields', nargs='*', help='key=value fields, e.g. port=0 frames=2 start=1')
p.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[1]/'private'/'automation')
a = p.parse_args()
if any('=' not in f or '\n' in f or '\r' in f for f in a.fields):
    p.error('fields must be single-line key=value pairs')
d = a.directory / 'commands'
d.mkdir(parents=True, exist_ok=True)
name = f'{time.time_ns():020d}'
tmp = a.directory / (name + '.tmp')
tmp.write_text('\n'.join(['command='+a.command, *a.fields])+'\n')
tmp.rename(d / (name + '.txt'))

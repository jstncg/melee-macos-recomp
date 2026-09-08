#!/usr/bin/env python3
"""Fail if the Git index includes non-source artifacts or likely credentials."""
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={'.gitattributes','.gitignore','README.md','CREDITS.md','CONTRIBUTING.md','LICENSE','Brewfile'}
ALLOWED={'scripts':{'.py','.sh'},'patches':{'.patch'},'config':{'.ini'},
         'tests':{'.py'},'macos':{'.c','.inc','.md'},'.github':{'.yml','.yaml'}}
paths=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
errors=[]
for name in filter(None,paths):
    path=Path(name)
    if name not in ROOT_FILES and path.suffix not in ALLOWED.get(path.parts[0],set()):
        errors.append(f'Not in source allowlist: {name}')
        continue
    data=subprocess.check_output(['git','show',':'+name],cwd=ROOT)
    if len(data)>1_000_000 or b'\0' in data:
        errors.append(f'Binary or unexpectedly large file: {name}')
        continue
    text=data.decode('utf-8',errors='strict')
    if re.search(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)',text):
        errors.append(f'Potential credential: {name}')
if errors:
    print('\n'.join(errors),file=sys.stderr)
    sys.exit(1)
print(f'Source audit passed: {len([p for p in paths if p])} tracked files; no excluded artifacts.')

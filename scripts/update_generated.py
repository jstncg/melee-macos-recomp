#!/usr/bin/env python3
"""Install fresh generated code without rebuilding byte-identical translation units."""
from pathlib import Path
import shutil
root = Path(__file__).resolve().parents[1]
source = root/'private/recompiled-next/generated'
target = root/'private/recompiled/generated'
changed = 0
for path in source.rglob('*'):
    if path.is_file():
        dest = target/path.relative_to(source)
        if not dest.exists() or path.read_bytes() != dest.read_bytes():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            changed += 1
for path in (target/'chunks').glob('*.c'):
    if not (source/path.relative_to(target)).exists():
        path.unlink()
print(f'Updated {changed} generated files')

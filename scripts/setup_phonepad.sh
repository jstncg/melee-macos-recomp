#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo 'Phone play requires Apple Silicon macOS.' >&2; exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
python3 -m venv "$ROOT/private/phonepad-venv"
"$ROOT/private/phonepad-venv/bin/python" -m pip install -r "$ROOT/phonepad/requirements.txt"
mkdir -p "$ROOT/build/phonepad"
clang -dynamiclib -O2 -Wall -Wextra -arch arm64 \
  -o "$ROOT/build/phonepad/gcshim.dylib" "$ROOT/phonepad/gcshim.c"
echo 'Phone controller setup complete. Check the game build with ./scripts/play_phones.sh --check'

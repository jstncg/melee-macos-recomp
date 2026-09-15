#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT/private/phonepad-venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  echo 'Run ./scripts/setup_phonepad.sh first.' >&2; exit 1
fi
exec "$PYTHON" "$ROOT/phonepad/launch.py" "$@"

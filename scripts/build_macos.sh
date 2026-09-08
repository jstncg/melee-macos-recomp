#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
JOBS="${JOBS:-8}"
TEMPLATE="$ROOT/upstream/ModernGekko-Template"
RUNTIME="$TEMPLATE/lib/ModernGekko"
DOLPHIN="$RUNTIME/vendor/dolphin"
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo 'This proof of concept requires Apple Silicon macOS.' >&2; exit 1
fi
for tool in git clang cmake ninja python3; do
  command -v "$tool" >/dev/null || { echo "Missing dependency: $tool" >&2; exit 1; }
done
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
if [[ ! -f private/GALE01r2.iso && ! -f "${1:-}" ]]; then
  echo 'Usage: ./scripts/build_macos.sh /absolute/path/to/your-disc.iso' >&2
  echo 'Supply your own Melee USA revision 2 ISO, GCM, or CISO.' >&2
  exit 1
fi
mkdir -p logs build private
if [[ ! -d "$TEMPLATE/.git" ]]; then
  git clone https://github.com/ExpansionPak/ModernGekko-Template.git "$TEMPLATE"
  git -C "$TEMPLATE" checkout eedda2b02dde3aefc02796d859f0033b916aad03
fi
if [[ "$(git -C "$TEMPLATE" rev-parse HEAD)" != eedda2b02dde3aefc02796d859f0033b916aad03 ]]; then
  echo "Unexpected template revision; refusing an unpinned build." >&2
  exit 1
fi
git -C "$TEMPLATE" submodule update --init --recursive
if git -C "$DOLPHIN" apply --reverse --check "$ROOT/patches/strict-native.patch" 2>/dev/null; then
  : # Local verification patch is already applied.
else
  git -C "$DOLPHIN" apply --check "$ROOT/patches/strict-native.patch"
  git -C "$DOLPHIN" apply "$ROOT/patches/strict-native.patch"
fi
if ! git -C "$RUNTIME" apply --reverse --check "$ROOT/patches/cpu-abi.patch" 2>/dev/null; then
  git -C "$RUNTIME" apply --check "$ROOT/patches/cpu-abi.patch"
  git -C "$RUNTIME" apply "$ROOT/patches/cpu-abi.patch"
fi
if ! git -C "$TEMPLATE/lib/DolRecomp" apply --reverse --check "$ROOT/patches/native-spr-codegen.patch" 2>/dev/null; then
  git -C "$TEMPLATE/lib/DolRecomp" apply --check "$ROOT/patches/native-spr-codegen.patch"
  git -C "$TEMPLATE/lib/DolRecomp" apply "$ROOT/patches/native-spr-codegen.patch"
fi
if ! git -C "$RUNTIME" apply --reverse --check "$ROOT/patches/netplay.patch" 2>/dev/null; then
  git -C "$RUNTIME" apply --check "$ROOT/patches/netplay.patch"
  git -C "$RUNTIME" apply "$ROOT/patches/netplay.patch"
fi
if ! git -C "$RUNTIME" apply --reverse --check "$ROOT/patches/media-settings.patch" 2>/dev/null; then
  git -C "$RUNTIME" apply --check "$ROOT/patches/media-settings.patch"
  git -C "$RUNTIME" apply "$ROOT/patches/media-settings.patch"
fi
cp "$ROOT/macos/MeleeFrontend.inc" "$DOLPHIN/Source/Core/DolphinNoGUI/MeleeFrontend.inc"
python3 scripts/check_cpu_abi.py
cmake -S "$TEMPLATE/lib/DolRecomp" -B build/dolrecomp -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF -DDOLRECOMP_ENABLE_LLVM=OFF
cmake --build build/dolrecomp --target dolrecomp -j "$JOBS"
if [[ ! -f private/GALE01r2.iso ]]; then
  DISC="$1"
  python3 scripts/prepare_disc.py "$DISC" private/GALE01r2.iso
fi
if [[ ! -f private/GALE01r2/sys/main.dol ]]; then
  build/dolrecomp/dolrecomp extract private/GALE01r2.iso private/GALE01r2
fi
python3 - <<'PY'
import hashlib
from pathlib import Path
p=Path('private/GALE01r2/sys/main.dol')
if hashlib.sha1(p.read_bytes()).hexdigest() != '08e0bf20134dfcb260699671004527b2d6bb1a45':
    raise SystemExit('Executable does not match supported GALE01 revision 2')
PY
cmake -S "$RUNTIME" -B build/runtime -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=OFF -DDOLRECOMP_ENABLE_LLVM=OFF -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DMODERNGEKKO_FRONTEND_NAME='Melee macOS' -DMODERNGEKKO_REQUIRED_DISC_ID=GALE01 \
  -DMODERNGEKKO_GAMECUBE_CONTROLLERS=ON \
  -DMODERNGEKKO_DEFAULT_WINDOW_TITLE='Melee — macOS Recompilation'
cmake --build build/runtime --target moderngekko-run -j "$JOBS"
build/dolrecomp/dolrecomp -j"$JOBS" --cpu gekko --gamecube \
  private/GALE01r2/sys/main.dol private/recompiled-next
python3 scripts/update_generated.py
if ! cmp -s private/GALE01r2/sys/main.dol private/recompiled/generated/main.dol; then
  cp private/GALE01r2/sys/main.dol private/recompiled/generated/main.dol
fi
cmake -S "$DOLPHIN/module-template" -B build/game -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_ARCHITECTURES=arm64 -DGAME_ID=GALE01 \
  -DGENERATED_DIR="$ROOT/private/recompiled/generated" -DGXRUNTIME_DIR="$DOLPHIN/GXRuntime"
cmake --build build/game -j "$JOBS"
./scripts/package_macos.sh
echo 'Build complete. Launch with ./scripts/run_macos.sh'

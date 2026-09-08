#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
USER_DIR="$ROOT/private/user"
mkdir -p "$USER_DIR/Config" "$ROOT/logs"
if [[ ! -f "$USER_DIR/Config/GCPadNew.ini" ]]; then
  cp "$ROOT/config/GCPadNew.ini" "$USER_DIR/Config/GCPadNew.ini"
fi
if [[ ! -f "$USER_DIR/config.ini" ]]; then
  cat > "$USER_DIR/config.ini" <<'INI'
resolution=640x528
show_fps_in_title=true
fullscreen=false
INI
fi
GAME_PATH="$ROOT/private/GALE01r2"
PREFS="$USER_DIR/Config/MeleeFrontend.plist"
if [[ -f "$PREFS" ]]; then
  SELECTED=$(/usr/libexec/PlistBuddy -c 'Print :game_path' "$PREFS" 2>/dev/null || true)
  if [[ -n "$SELECTED" && -f "$SELECTED/sys/main.dol" ]] && cmp -s "$SELECTED/sys/main.dol" "$ROOT/private/GALE01r2/sys/main.dol"; then
    GAME_PATH="$SELECTED"
  fi
fi
export MODERNGEKKO_STATICRECOMP=1
export MELEE_STRICT_NATIVE="${MELEE_STRICT_NATIVE:-1}"
if [[ -z "${MELEE_FRONTEND:-}" ]]; then
  exec "${MELEE_RUNNER_PATH:-$ROOT/build/runtime/moderngekko-run}" \
    --game "$GAME_PATH" --module "$ROOT/build/game/gGALE01_recomp.dylib" \
    --user-dir "$USER_DIR" --graphics Metal --audio Cubeb --no-mods "$@"
fi
REQUEST="$USER_DIR/Config/NetplayRequest.plist"
# A request belongs only to the running local session, never a previous crash.
rm -f "$REQUEST"
RESULT=0
"${MELEE_RUNNER_PATH:-$ROOT/build/runtime/moderngekko-run}" \
  --game "$GAME_PATH" \
  --module "$ROOT/build/game/gGALE01_recomp.dylib" \
  --user-dir "$USER_DIR" --graphics Metal --audio Cubeb --no-mods "$@" || RESULT=$?

if [[ -f "$REQUEST" && "${MELEE_FRONTEND:-}" == 1 ]]; then
  ROLE=$(/usr/libexec/PlistBuddy -c 'Print :role' "$REQUEST")
  ADDRESS=$(/usr/libexec/PlistBuddy -c 'Print :address' "$REQUEST")
  PORT=$(/usr/libexec/PlistBuddy -c 'Print :port' "$REQUEST")
  NICKNAME=$(/usr/libexec/PlistBuddy -c 'Print :nickname' "$REQUEST")
  rm -f "$REQUEST"
  NET_ARGS=(--netplay-port "$PORT" --nickname "$NICKNAME" --buffer auto)
  if [[ "$ROLE" == host ]]; then NET_ARGS+=(--netplay-host)
  elif [[ "$ROLE" == join ]]; then NET_ARGS+=(--netplay-join "$ADDRESS")
  else exit 2
  fi
  # Pausing one peer with the local overlay would stall a synchronized match.
  unset MELEE_FRONTEND
  RESULT=0
  "${MELEE_RUNNER_PATH:-$ROOT/build/runtime/moderngekko-run}" \
    --game "$GAME_PATH" --module "$ROOT/build/game/gGALE01_recomp.dylib" \
    --user-dir "$USER_DIR" --graphics Metal --audio Cubeb --no-mods "${NET_ARGS[@]}" || RESULT=$?
  if [[ "$RESULT" != 0 ]]; then
    export MELEE_NETPLAY_ERROR="$RESULT"
  fi
  export MELEE_FRONTEND=1
  exec /bin/bash "$ROOT/scripts/run_macos.sh"
fi
exit "$RESULT"

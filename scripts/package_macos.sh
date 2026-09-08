#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/Melee macOS.app"
mkdir -p "$APP/Contents/MacOS" "$ROOT/logs"
clang -O2 -arch arm64 "$ROOT/macos/launcher.c" -o "$APP/Contents/MacOS/Melee"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>Melee</string>
<key>CFBundleIdentifier</key><string>local.melee.macos.recomp</string>
<key>CFBundleName</key><string>Melee macOS</string>
<key>CFBundleDisplayName</key><string>Melee macOS</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>0.1</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
cp "$ROOT/build/runtime/moderngekko-run" "$APP/Contents/MacOS/MeleeRuntime"
mkdir -p "$APP/Contents/Resources"
if [[ -f "$ROOT/macos/assets/AppIcon.png" ]]; then
  "$ROOT/scripts/build_icon.sh"
  cp "$ROOT/build/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
  /usr/libexec/PlistBuddy -c 'Add :CFBundleIconFile string AppIcon.icns' "$APP/Contents/Info.plist"
fi
cp -R "$ROOT/build/runtime/Sys" "$APP/Contents/Resources/"
codesign --force --sign - "$APP/Contents/MacOS/MeleeRuntime"
codesign --force --sign - "$APP"
echo "Development launcher: $APP (keep it in this workspace)"

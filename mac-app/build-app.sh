#!/usr/bin/env bash
# Build the Tandem command-bar app and bundle it into Tandem.app (menu-bar only).
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/3] compiling"
swift build -c release

BIN=".build/release/Tandem"
APP="Tandem.app"
echo "[2/3] bundling ${APP}"
rm -rf "${APP}"
mkdir -p "${APP}/Contents/MacOS" "${APP}/Contents/Resources"
cp "${BIN}" "${APP}/Contents/MacOS/Tandem"
[ -f AppIcon.icns ] && cp AppIcon.icns "${APP}/Contents/Resources/AppIcon.icns"

cat > "${APP}/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Tandem</string>
  <key>CFBundleIdentifier</key><string>com.tandem.assistant</string>
  <key>CFBundleExecutable</key><string>Tandem</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
</dict>
</plist>
PLIST

echo "[3/3] done -> open ${APP}   (Option+Space to summon; needs backend on :8000)"

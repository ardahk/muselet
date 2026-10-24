#!/usr/bin/env bash
# Build MuseletApp (release) and assemble + codesign app/build/Muselet.app.
#
#   bash app/scripts/build_app.sh            # release build
#   CONFIG=debug bash app/scripts/build_app.sh
#   SIGN_IDENTITY="-" bash app/scripts/build_app.sh   # ad-hoc (TCC grants won't persist)
#
# Uses --scratch-path .build-app so it never clashes with other `swift build`s.
# Signed with a stable Apple Development identity so TCC grants (Accessibility,
# Screen Recording, Microphone, Input Monitoring) survive rebuilds.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${CONFIG:-release}"
SCRATCH="$APP_DIR/.build-app"
OUT="$APP_DIR/build"
APP="$OUT/Muselet.app"
BUNDLE_ID="ai.muselet.app"
EXE_NAME="Muselet"
VERSION="0.1.0"
BUILD_NUMBER="$(date +%Y%m%d%H%M)"
SIGN_IDENTITY="${SIGN_IDENTITY:-Apple Development: Arda Höke (G989U5X359)}"
# The keychain may store the name decomposed (ö = o + U+0308), so resolve the
# same identity's SHA-1 by its unique certificate id as a fallback.
SIGN_SHA1_FALLBACK="$(security find-identity -v -p codesigning 2>/dev/null \
  | awk '/Apple Development: .*\(G989U5X359\)/ {print $2; exit}')"
SIGN_SHA1_FALLBACK="${SIGN_SHA1_FALLBACK:-EE0C5B8383F682888A4B29538BF4BE7632139F10}"

cd "$APP_DIR"
echo "==> swift build ($CONFIG) MuseletApp"
swift build -c "$CONFIG" --scratch-path "$SCRATCH" --product MuseletApp
BIN_DIR="$(swift build -c "$CONFIG" --scratch-path "$SCRATCH" --show-bin-path)"

echo "==> assembling $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN_DIR/MuseletApp" "$APP/Contents/MacOS/$EXE_NAME"

# SwiftPM resource bundles (e.g. FluidAudio_FluidAudio.bundle) go in Resources/.
shopt -s nullglob
for b in "$BIN_DIR"/*.bundle; do
  cp -R "$b" "$APP/Contents/Resources/"
done
shopt -u nullglob

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>${BUNDLE_ID}</string>
  <key>CFBundleName</key><string>Muselet</string>
  <key>CFBundleDisplayName</key><string>muselet</string>
  <key>CFBundleExecutable</key><string>${EXE_NAME}</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundleVersion</key><string>${BUILD_NUMBER}</string>
  <key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
  <key>CFBundleDevelopmentRegion</key><string>en</string>
  <key>LSMinimumSystemVersion</key><string>26.0</string>
  <key>LSUIElement</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.productivity</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSSupportsAutomaticTermination</key><false/>
  <key>NSSupportsSuddenTermination</key><false/>
  <key>NSHumanReadableCopyright</key><string>muselet — fully on-device voice agent</string>
  <key>NSMicrophoneUsageDescription</key>
  <string>muselet listens only while you hold the push-to-talk key, and transcribes on this Mac.</string>
  <key>NSSpeechRecognitionUsageDescription</key>
  <string>muselet can fall back to Apple's on-device speech recognition to understand your voice commands.</string>
  <key>NSAppleEventsUsageDescription</key>
  <string>muselet controls apps on your behalf when you ask it to (e.g. Music, Finder, Mail).</string>
  <key>NSCalendarsFullAccessUsageDescription</key>
  <string>muselet reads and creates calendar events when you ask it to.</string>
  <key>NSRemindersFullAccessUsageDescription</key>
  <string>muselet reads and creates reminders when you ask it to.</string>
  <key>NSBluetoothAlwaysUsageDescription</key>
  <string>muselet turns Bluetooth on or off when you ask it to.</string>
  <key>NSContactsUsageDescription</key>
  <string>Muselet looks up the person you ask it to message.</string>
</dict>
</plist>
PLIST
printf 'APPL????' > "$APP/Contents/PkgInfo"

ENT="$OUT/Muselet.entitlements"
cat > "$ENT" <<'ENTS'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.app-sandbox</key><false/>
  <key>com.apple.security.device.audio-input</key><true/>
  <key>com.apple.security.automation.apple-events</key><true/>
  <key>com.apple.security.personal-information.calendars</key><true/>
  <key>com.apple.security.personal-information.addressbook</key><true/>
</dict>
</plist>
ENTS

echo "==> codesign ($SIGN_IDENTITY)"
sign() {
  local id="$1"
  # Nested bundles first, then the app (no --deep: sign inside-out explicitly).
  shopt -s nullglob
  for b in "$APP/Contents/Resources/"*.bundle; do
    codesign --force --timestamp=none --sign "$id" "$b"
  done
  shopt -u nullglob
  codesign --force --timestamp=none --options runtime \
    --entitlements "$ENT" --identifier "$BUNDLE_ID" --sign "$id" "$APP"
}
if ! sign "$SIGN_IDENTITY" 2>/tmp/muselet-sign.err; then
  echo "    name lookup failed (unicode normalization); signing with SHA-1 $SIGN_SHA1_FALLBACK"
  sign "$SIGN_SHA1_FALLBACK"
fi
codesign --verify --strict --verbose=1 "$APP"
echo "==> built $APP"

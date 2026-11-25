#!/usr/bin/env bash
# Erstellt «Jarvis.app» im Programme-Ordner – Start per Klick, Dock oder Spotlight.
#   bash install_app.sh              → App mit futuristischem HUD-Fenster
#   bash install_app.sh --terminal   → App, die Jarvis im Terminal startet
#   bash install_app.sh --autostart  → zusätzlich bei jeder Anmeldung starten
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/Applications"
APP="$APP_DIR/Jarvis.app"
MODE="gui"; AUTOSTART=0
for arg in "$@"; do
  case "$arg" in
    --terminal) MODE="terminal" ;;
    --autostart) AUTOSTART=1 ;;
  esac
done

echo "🔧 Installiere Fenster-Komponente (pywebview) ..."
"$DIR/.venv/bin/pip" install -q "pywebview>=5.0"

echo "🔧 Erstelle Jarvis.app ..."
mkdir -p "$APP_DIR"
rm -rf "$APP"

if [ "$MODE" = "gui" ]; then
  # Startet das HUD im Hintergrund (nur einmal, auch bei mehrfachem Klicken)
  osacompile -o "$APP" \
    -e "do shell script \"pgrep -f 'python -m jarvis --gui' >/dev/null || (cd '$DIR' && nohup ./jarvis.sh --gui > /tmp/jarvis.log 2>&1 &)\""
else
  osacompile -o "$APP" \
    -e 'tell application "Terminal"' \
    -e '  activate' \
    -e "  do script \"clear; cd '$DIR' && ./jarvis.sh\"" \
    -e 'end tell'
fi

# Mikrofon-Erlaubnis für die App anfragen dürfen
plutil -replace NSMicrophoneUsageDescription \
  -string "Jarvis hört auf dein Kommando «Jarvis, …»." "$APP/Contents/Info.plist"
plutil -replace CFBundleIdentifier -string "ch.dalipi.jarvis" "$APP/Contents/Info.plist"

# Eigenes Symbol
if [ -f "$DIR/assets/icon.png" ]; then
  TMP="$(mktemp -d)"; ICONSET="$TMP/Jarvis.iconset"; mkdir -p "$ICONSET"
  for size in 16 32 128 256 512; do
    sips -z $size $size "$DIR/assets/icon.png" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    double=$((size * 2))
    sips -z $double $double "$DIR/assets/icon.png" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/applet.icns"
  rm -rf "$TMP"
fi

# Nach den Änderungen neu signieren (lokal, ohne Apple-Konto)
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
touch "$APP"

echo "✅ Fertig: $APP"
echo "   Starten: Cmd+Leertaste → «Jarvis» → Enter"
echo "   Ins Dock: Jarvis.app aus dem geöffneten Finder-Fenster ins Dock ziehen"

if [ "$AUTOSTART" = "1" ]; then
  osascript -e "tell application \"System Events\" to make login item at end with properties {path:\"$APP\", hidden:false}" >/dev/null
  echo "🚀 Autostart aktiviert – Jarvis startet bei jeder Anmeldung."
fi

open -R "$APP"

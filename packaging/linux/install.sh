#!/usr/bin/env bash
# Installs a CRYSTA AI launcher icon for Debian/Ubuntu/Chromebook (Crostini) and other Linux desktops.
# Usage: ./packaging/linux/install.sh [--apt]     (--apt also installs the window component with sudo)
set -e
APPDIR="$(cd "$(dirname "$0")/../.." && pwd)"
command -v python3 >/dev/null || { echo "python3 is required: sudo apt install python3"; exit 1; }
if ! python3 -c "import gi" 2>/dev/null && ! python3 -c "import webview" 2>/dev/null; then
  if [ "$1" = "--apt" ]; then
    sudo apt update && sudo apt install -y python3-gi gir1.2-webkit2-4.1 || sudo apt install -y python3-gi gir1.2-webkit2-4.0
  else
    echo "Window component missing. Run once:  sudo apt install python3-gi gir1.2-webkit2-4.1"
    echo "(or re-run this script with --apt). Continuing to create the launcher anyway."
  fi
fi
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$DEST"
cat > "$DEST/crysta-ai.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=CRYSTA AI
Comment=Local-first personal AI assistant
Exec=python3 "$APPDIR/desktop.py"
Path=$APPDIR
Icon=$APPDIR/web/crysta.svg
Terminal=false
Categories=Utility;Development;
StartupWMClass=CRYSTA AI
DESK
chmod +x "$DEST/crysta-ai.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$DEST" || true
echo "Done. Find 'CRYSTA AI' in your app launcher (Chromebook: search for it in the launcher's Linux apps)."
echo "Self-test any time:  python3 $APPDIR/desktop.py --check"

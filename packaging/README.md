# Packaging CRYSTA AI as a desktop application

CRYSTA's desktop mode is `desktop.py`: one Python process = backend + a native window (no browser, no Node, no Electron).
It is a thin launcher, so there is nothing to compile and no large runtime to download.

| Platform | One-time setup | Launch |
|---|---|---|
| Linux / Chromebook (Crostini) | `./packaging/linux/install.sh --apt` | App launcher icon "CRYSTA AI", or `python3 desktop.py` |
| Windows 10/11 | `powershell -ExecutionPolicy Bypass -File packaging\windows\install.ps1` | Desktop shortcut "CRYSTA AI" (no console window) |
| macOS | `python3 -m pip install pywebview` | Double-click `packaging/macos/CRYSTA.command` |

Check any machine: `python3 desktop.py --check` (tests the backend lifecycle and says which window back-end is available).

## Optional: single-file executable (NOT tested by the author)
`pip install pyinstaller` then, from the project folder:
- Linux/macOS: `pyinstaller --noconsole --name CRYSTA --add-data "web:web" --add-data "knowledge:knowledge" desktop.py`
- Windows:     `pyinstaller --noconsole --name CRYSTA --add-data "web;web" --add-data "knowledge;knowledge" desktop.py`
Bundled builds are larger (50-100 MB) and slower to start; the scripts above are the recommended, lighter method.

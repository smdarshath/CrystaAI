# Desktop application

`desktop.py` runs CRYSTA in **its own native window**. No Chrome, no browser tab, no Node/Electron.

## How it works
- One Python process: the backend runs in a thread, the window shows the existing UI. Nothing else is started, so memory stays low (backend ≈ 30 MB RSS measured).
- The UI is loaded from a loopback address on a **random port**; every launch generates a secret that only the app window holds (cookie, HttpOnly, SameSite=Strict). Other programs, other browser tabs and websites get HTTP 401.
- Closing the window stops the backend, cancels running agent work, stops speech, closes the database and removes `data/desktop.lock`. A second copy of the app is refused with a clear message.
- Startup errors are shown in a dialog (works without a console) and saved to `data/startup-error.log`.
- Fully offline: nothing needs the internet to start. Only ZYKRON's live research/YouTube do, and they say so.

## Window back-ends (first available is used)
1. **pywebview** — Windows (Edge WebView2, already on Windows 10/11), macOS (WKWebView), Linux.
2. **GTK3 + WebKit2** directly — Debian/Ubuntu/Chromebook Linux: `sudo apt install python3-gi gir1.2-webkit2-4.1` (or `-4.0`).
If neither is installed CRYSTA tells you what to install. It never silently opens a browser (`--browser` is an explicit opt-in).

## Install / launch
| Platform | Setup | Launch |
|---|---|---|
| Linux, Chromebook (Crostini) | `./packaging/linux/install.sh --apt` | launcher icon "CRYSTA AI" or `./start.sh` |
| Windows 10/11 | `powershell -ExecutionPolicy Bypass -File packaging\windows\install.ps1` | Desktop shortcut or `start.bat` |
| macOS | `python3 -m pip install pywebview` | `packaging/macos/CRYSTA.command` |

`python3 desktop.py --check` prints the platform, which window back-end exists, and tests the backend lifecycle (secret enforced, clean shutdown).

## Voice inside the app window
- **Speech output:** browser voices when the window has them; otherwise the operating-system engine through the backend (Linux `espeak-ng`, macOS `say`, Windows SAPI).
- **Speech input:** browser recognition when the window supports it. Many embedded webviews (notably WebKitGTK) do **not**; then CRYSTA uses optional offline recognition: `pip install vosk sounddevice` and put a model folder (e.g. `vosk-model-small-en-in-0.4`) in `models/`. Without it, the mic button explains this and typing still works.
- Microphone access in the GTK window is granted only to CRYSTA's own page.

## Server mode (phones, development)
`./start-server.sh` / `python3 run.py [--lan]` is the previous browser-based mode, kept for pairing a phone (docs/DEVICE_PAIRING.md).

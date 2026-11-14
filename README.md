# CRYSTA AI

A local-first, voice-first personal AI assistant: one main assistant (**CRYSTA**) plus eight specialist agents, each with its own
workspace. It runs on your own computer in **its own desktop window** (no Chrome / browser needed), works offline for everything local,
and uses the internet only when you ask for live research. **Created by Arshath.**

## Install and launch

**1. Install Python 3.9+** (nothing else is required for the backend).
**2. Install the window component once** (this is what lets CRYSTA open its own window instead of using a browser):

| Platform | One-time setup | Launch |
|---|---|---|
| Chromebook (Linux/Crostini), Debian, Ubuntu | `./packaging/linux/install.sh --apt` | "CRYSTA AI" in the app launcher, or `./start.sh` |
| Windows 10/11 | `powershell -ExecutionPolicy Bypass -File packaging\windows\install.ps1` | "CRYSTA AI" Desktop shortcut, or `start.bat` |
| macOS | `python3 -m pip install pywebview` | `packaging/macos/CRYSTA.command` |

Check your machine any time: `python3 desktop.py --check`. Stop CRYSTA by closing its window (the backend shuts down with it).

**Upgrading an existing copy:** unzip this next to the old one, then `python3 scripts/upgrade_from.py /path/to/old/crysta-ai`
(copies your data, settings and models; never touches the old folder; your database is upgraded in place with a backup kept).

## The nine interfaces
Say or type "open volt", "nova thira", "zykron" … or use the buttons on the home screen. Every workspace has a **◂ CRYSTA** button (and Esc).

| | Workspace |
|---|---|
| CRYSTA | The orb home screen: voice/text, agent navigation, activity and status |
| ZYKRON | Research command centre: official-first live research, competitions & scholarships (dates, registration links), source verification, YouTube + captions, history |
| NOVA | IDE: file explorer, code editor, terminal, problems (error explanations), logs, run/test |
| ASTRA | Science lab: subjects, knowledge panels, animated diagrams, formula solver, maths plotter |
| VEGA | File manager: folder tree, preview, info, create/rename/copy/move/open/delete with permissions |
| ECHO | Voice studio: live mic level, voice & language, speed/pitch/volume, speech tests |
| NEXUS | Memory archive: searchable notes, project notes, timeline, categories, memory controls |
| ORION | Project workspace: kanban, milestones/roadmap, timeline, progress |
| VOLT | Hardware dashboard: real CPU, RAM, storage, battery, network, OS — "unavailable" when the OS hides it |

CRYSTA understands English, Tamil and Tanglish (e.g. "maanavar pottigal thedu", "un peyar enna", "settings thira") and answers identity,
time/date and small talk itself, without searching the internet.

## What was tested (and what was not)
**Actually run, in the build environment (Linux x86_64, Ubuntu 24.04, Python 3.12, headless Chromium):**
- 110 automated Python tests — all pass (`cd tests && python3 -m unittest discover`).
- 12 end-to-end browser steps driving every workspace's real controls — all pass (`python3 scripts/ui_test.py`, needs `pip install playwright`).
- All nine interfaces open, are visually distinct, show the right identity and return to CRYSTA; no horizontal overflow at 1366×768, 1280×720, 1024×600, 800×600, 412×780.
- Desktop backend lifecycle (secret enforced, clean shutdown, single instance) via `python3 desktop.py --check`.
- Resource use: backend ≈ 30 MB RAM, starts in under 0.1 s, only the agents you use are loaded, frontend 63 KB gzipped with no libraries.

**NOT tested — please check on your machine:**
- The native window itself (GTK/WebKit2 and pywebview code paths): the build environment has no GUI toolkit. Run `python3 desktop.py --check`, then launch it.
- Windows, macOS, and a real Chromebook (Crostini). Only Linux x86_64 was run.
- Real microphone / speech recognition / speech output, offline Vosk, Tamil voices.
- Live web and YouTube research (no internet in the build environment; parsers and ranking are tested against saved pages). YouTube may change its pages.
- Ollama/local language models, pyautogui keyboard/mouse control, phone pairing with a real phone, PyInstaller bundles.

## Honest limitations
- Without a language model CRYSTA is a capable tool-user, not a general chatbot (it says so). Add one with Ollama (`ollama pull llama3.2:3b`).
- Voice input depends on the window: some embedded webviews have no speech recognition; use the optional offline Vosk setup (docs/DESKTOP.md) or type.
- Battery and CPU temperature are often unavailable on Chromebook Linux and VMs; VOLT says so instead of guessing.
- Code editor has no syntax highlighting; NOVA cannot write code without a language model.
- Custom extension agents get a card, not a custom workspace (docs/EXTENSIONS.md).

## Safety in one paragraph
Everything CRYSTA does on your computer goes through permissions you control (VEGA → Permissions): read/open allowed, writes and commands ask, deleting/overwriting always asks, and a never-run list (sudo, format, shutdown…) is blocked. Files are restricted to folders you approve. In desktop mode only the app's own window can talk to the backend. Details: `docs/SECURITY.md`.

## Docs
`docs/UPGRADE.md` (what changed) · `DESKTOP.md` · `AGENTS.md` · `EXTENSIONS.md` · `ARCHITECTURE.md` · `SECURITY.md` · `RESEARCH.md` · `DEVICE_PAIRING.md` · `TROUBLESHOOTING.md` · `packaging/README.md`

## Uninstall
Close CRYSTA and delete the folder (and the launcher entry: `~/.local/share/applications/crysta-ai.desktop` on Linux, the Desktop shortcut on Windows). Your data lives in `data/`.

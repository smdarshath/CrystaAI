# Troubleshooting

| Problem | Fix |
|---|---|
| "No window component is installed" | Linux: `sudo apt install python3-gi gir1.2-webkit2-4.1`; Windows/macOS: `python3 -m pip install pywebview`. Check with `python3 desktop.py --check`. |
| "CRYSTA is already running" | Close the other CRYSTA window. If it crashed, delete `data/desktop.lock`. |
| Mic button says the window has no speech recognition | Embedded windows often lack it. Install offline recognition (`pip install vosk sounddevice` + model in `models/`) or type (T). |
| Battery/temperature show "unavailable" | The OS/container doesn't expose them (typical for Chromebook Linux). On Windows/macOS `pip install psutil` can add them. |
| Nothing speaks | Linux: `sudo apt install espeak-ng`, then ECHO → SPEAK. |
| `python3: command not found` | Windows: use `py run.py`. Mac/Linux: install Python 3.9+. |
| "Port 8765 in use" | `python3 run.py --port 8766` (Crysta never kills other programs). |
| Mic button does nothing / "not supported" | Use Chrome or Edge. Firefox has no speech recognition. Press **T** to type. |
| "Microphone permission blocked" | Click the lock icon in the address bar → allow microphone. |
| "Speech service unreachable" | Browser speech recognition needs internet. Type instead. |
| Tamil voice sounds wrong / silent | Install a Tamil voice in your OS/browser; recognition language support varies. |
| Research says "couldn't reach any search source" | Check internet; free endpoints may be rate-limited — try again in a minute. |
| "BRAIN · BASIC" | No language model connected. Optional: install Ollama, `ollama pull llama3.2:3b`, restart Crysta. |
| Open app does nothing | Linux needs a desktop session; app name must exist on the system. Check Computer → Recent actions. |
| Keyboard/mouse unavailable | `pip install pyautogui` (Wayland/macOS may need extra permissions). |
| Phone can't connect | Start with `--lan`, same Wi-Fi, allow the port in your firewall. |
| Reset everything | Stop Crysta, delete `data/crysta.db`. |

Logs: `data/crysta.log`. Environment check: `python3 scripts/check_environment.py`.

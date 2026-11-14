"""Computer control: open apps/URLs, run commands, keyboard/mouse. Every call is verified and honest."""
from __future__ import annotations

import os
import platform
import re
import shlex
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path

from ..errors import CrystaError, PermissionDenied, ToolUnavailable

SYSTEM = platform.system()
BLOCKED = [r"\bsudo\b", r"\bmkfs", r"\bdd\b.*\bof=/dev", r":\(\)\s*\{", r"\brm\s+-[a-z]*r[a-z]*\s+(/|~)(\s|$)",
           r"\bformat\s+[a-z]:", r"\bdel\s+/[sfq]", r"\b(shutdown|reboot|poweroff|halt)\b", r"(curl|wget)[^|]*\|\s*(sh|bash)",
           r"\bchmod\s+-R\s+777\s+/"]
CHAIN = re.compile(r"[;&|<>`]|\$\(")
SAFE_SIMPLE = {"ls", "dir", "pwd", "whoami", "date", "echo", "hostname", "uname", "df", "free", "uptime", "ver", "cd"}
SAFE_ARGS = {"python": [["--version"]], "python3": [["--version"]], "node": [["--version"], ["-v"]],
             "npm": [["--version"], ["-v"]], "pip": [["--version"]], "pip3": [["--version"]],
             "git": [["--version"], ["status"], ["log"], ["diff"], ["branch"]]}
DESTRUCTIVE = {"rm", "rmdir", "del", "erase", "rd", "mv", "move", "kill", "killall", "pkill", "taskkill", "chmod",
               "chown", "truncate", "shred", "apt", "apt-get", "brew", "winget", "choco", "pip", "pip3", "npm", "yum", "dnf"}

WIN_APPS = {"calculator": "calc", "notepad": "notepad", "chrome": "chrome", "edge": "msedge", "files": "explorer",
            "file explorer": "explorer", "explorer": "explorer", "terminal": "wt", "cmd": "cmd", "vscode": "code",
            "vs code": "code", "paint": "mspaint", "word": "winword", "excel": "excel", "spotify": "spotify",
            "firefox": "firefox", "settings": "ms-settings:", "browser": "msedge"}
MAC_APPS = {"calculator": "Calculator", "chrome": "Google Chrome", "files": "Finder", "finder": "Finder",
            "terminal": "Terminal", "vscode": "Visual Studio Code", "vs code": "Visual Studio Code", "safari": "Safari",
            "firefox": "Firefox", "notes": "Notes", "spotify": "Spotify", "browser": "Safari", "settings": "System Settings"}
LINUX_APPS = {"calculator": ["gnome-calculator", "kcalc", "galculator", "xcalc"],
              "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
              "browser": ["xdg-open"], "firefox": ["firefox"], "files": ["nautilus", "nemo", "thunar", "dolphin", "pcmanfm"],
              "terminal": ["x-terminal-emulator", "gnome-terminal", "konsole", "xfce4-terminal", "xterm"],
              "vscode": ["code", "codium"], "vs code": ["code", "codium"],
              "text editor": ["gedit", "kate", "mousepad", "xed"], "settings": ["gnome-control-center"]}


def classify_command(command):
    """Return ('blocked'|'safe'|'destructive'|'normal', argv). Raises CrystaError for chaining."""
    if any(re.search(p, command, re.I) for p in BLOCKED):
        return "blocked", []
    if CHAIN.search(command):
        raise CrystaError("I run one plain command at a time (no pipes, chaining or redirects).")
    try:
        argv = shlex.split(command, posix=(SYSTEM != "Windows"))
    except ValueError:
        raise CrystaError("I couldn't parse that command (unbalanced quotes?).")
    if not argv:
        raise CrystaError("Empty command.")
    exe = os.path.basename(argv[0]).lower().removesuffix(".exe")
    if exe in SAFE_SIMPLE or (exe in SAFE_ARGS and argv[1:] in SAFE_ARGS[exe]) \
            or (exe == "git" and argv[1:2] in (["status"], ["log"], ["diff"], ["branch"])):
        return "safe", argv
    if exe in DESTRUCTIVE:
        return "destructive", argv
    return "normal", argv


def run(argv, timeout=30, cwd=None):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd or str(Path.home()),
                           shell=False, errors="replace")
    except FileNotFoundError:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": "", "message": f"Command not found: {argv[0]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": "", "timed_out": True,
                "message": f"Stopped after {timeout}s (timed out)."}
    out, err = p.stdout[-8000:], p.stderr[-4000:]
    return {"ok": p.returncode == 0, "returncode": p.returncode, "stdout": out, "stderr": err,
            "message": "Command finished successfully." if p.returncode == 0 else f"Command failed (exit code {p.returncode})."}


def _headless():
    return SYSTEM == "Linux" and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def open_app(name):
    name = name.strip()
    if not re.fullmatch(r"[\w .+\-]{1,60}", name):
        raise CrystaError("That app name has characters I won't pass to the system.")
    key = name.lower()
    if _headless():
        raise ToolUnavailable("No graphical desktop is available here, so I can't open apps.")
    if SYSTEM == "Windows":
        argv = ["cmd", "/c", "start", "", WIN_APPS.get(key, name)]
    elif SYSTEM == "Darwin":
        argv = ["open", "-a", MAC_APPS.get(key, name)]
    else:
        cands = LINUX_APPS.get(key, [key.replace(" ", "-")])
        exe = next((c for c in cands if shutil.which(c)), None)
        if not exe:
            raise CrystaError(f"I couldn't find an app called '{name}' on this system.")
        argv = [exe, "about:blank"] if exe == "xdg-open" else [exe]
    try:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=(SYSTEM != "Windows"))
    except OSError as e:
        return {"ok": False, "message": f"Couldn't start '{name}': {e}"}
    time.sleep(0.8)
    rc = p.poll()
    if rc not in (None, 0):
        return {"ok": False, "message": f"'{name}' exited immediately with code {rc}, so it probably didn't open."}
    return {"ok": True, "message": f"Asked the system to open {name} (process started; I can't see the window itself)."}


def open_url(url):
    if not re.match(r"^https?://", url, re.I):
        raise CrystaError("I only open http/https links.")
    if _headless():
        raise ToolUnavailable("No graphical desktop is available here, so I can't open a browser.")
    ok = webbrowser.open(url)
    return {"ok": bool(ok), "message": "Opened in your default browser." if ok else "The system couldn't open a browser."}


def _pyautogui():
    try:
        import pyautogui  # optional
        return pyautogui
    except Exception as e:
        raise ToolUnavailable("Keyboard/mouse control needs the optional package 'pyautogui' "
                              "(pip install pyautogui). " + str(e)[:80])


def keyboard(action, text="", x=None, y=None, data_dir=None):
    pg = _pyautogui()
    if action == "type":
        pg.write(text, interval=0.02)
    elif action == "hotkey":
        pg.hotkey(*[k.strip() for k in text.split("+") if k.strip()])
    elif action == "click":
        pg.click(int(x), int(y))
    elif action == "screenshot":
        d = Path(data_dir or ".") / "screenshots"
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"shot-{int(time.time())}.png"
        pg.screenshot(str(path))
        return {"ok": path.is_file(), "path": str(path), "message": f"Saved screenshot to {path}"}
    else:
        raise CrystaError("Unknown keyboard action.")
    return {"ok": True, "message": f"Sent '{action}' to the keyboard/mouse (I can't visually confirm the result)."}


def open_path(path):
    """Open a file or folder with the operating system's default application."""
    if _headless():
        raise ToolUnavailable("No graphical desktop is available here, so I can't open files.")
    try:
        if SYSTEM == "Windows":
            os.startfile(path)  # noqa: S606 - path already validated against approved folders
            return {"ok": True, "message": f"Asked Windows to open {path}."}
        argv = ["open", path] if SYSTEM == "Darwin" else ["xdg-open", path]
        if not shutil.which(argv[0]):
            raise CrystaError(f"'{argv[0]}' isn't installed, so I can't open files with the default app.")
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        time.sleep(0.6)
        rc = p.poll()
        if rc not in (None, 0):
            return {"ok": False, "message": f"The system could not open that file (exit code {rc})."}
        return {"ok": True, "message": f"Asked the system to open {path} with its default app."}
    except OSError as e:
        return {"ok": False, "message": f"Could not open it: {e}"}

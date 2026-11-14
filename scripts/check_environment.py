#!/usr/bin/env python3
"""Pre-flight check: python3 scripts/check_environment.py  (needs only Python 3.9+)."""
import os
import platform
import shutil
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ok = True


def line(good, label, detail=""):
    global ok
    ok = ok and good
    print(f"  [{'OK' if good else '!!'}] {label}" + (f" - {detail}" if detail else ""))


print(f"Crysta AI environment check ({platform.system()} {platform.machine()})")
line(sys.version_info >= (3, 9), "Python 3.9+", sys.version.split()[0])
free = shutil.disk_usage(ROOT).free / 1e9
line(free > 0.2, "Free disk space", f"{free:.1f} GB")
try:
    mem = [int(l.split()[1]) for l in open("/proc/meminfo") if l.startswith("MemTotal")][0] // 1024
    line(mem >= 1000, "RAM", f"{mem} MB")
except OSError:
    print("  [--] RAM: not measurable on this OS")
for d in ("crysta", "web", "knowledge"):
    line((ROOT / d).is_dir(), f"folder '{d}' present")
try:
    (ROOT / "data").mkdir(exist_ok=True)
    t = ROOT / "data" / ".write_test"
    t.write_text("x"); t.unlink()
    line(True, "data/ folder writable")
except OSError as e:
    line(False, "data/ folder writable", str(e))
port = int(os.environ.get("CRYSTA_PORT", "8765"))
with socket.socket() as s:
    s.settimeout(0.5)
    busy = s.connect_ex(("127.0.0.1", port)) == 0
line(not busy, f"Port {port} free", "in use - run with: python3 run.py --port 8766" if busy else "")
print("  [..] Optional: Node " + (shutil.which("node") or "not installed (not needed)"))
try:
    import pyautogui  # noqa: F401
    print("  [OK] Optional: pyautogui installed (keyboard/mouse control available)")
except Exception:
    print("  [--] Optional: pyautogui not installed (pip install pyautogui) - only needed for keyboard/mouse control")
import urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1.5)
    print("  [OK] Optional: Ollama is running (open-ended answers available)")
except Exception:
    print("  [--] Optional: Ollama not running (see README to add a local model)")
print("\nAll required checks passed." if ok else "\nFix the [!!] items above, then run again.")
sys.exit(0 if ok else 1)

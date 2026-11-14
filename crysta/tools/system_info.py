"""Measured system facts vs clearly-labelled estimates."""
from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path


def _ram_mb():
    try:
        if platform.system() == "Linux":
            info = {l.split(":")[0]: int(l.split()[1]) for l in open("/proc/meminfo") if ":" in l}
            return info["MemTotal"] // 1024, info.get("MemAvailable", 0) // 1024
        if platform.system() == "Darwin":
            tot = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=3).stdout)
            return tot // 1048576, None
        if platform.system() == "Windows":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("p", ctypes.c_ulong), ("tp", ctypes.c_ulonglong),
                            ("ap", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong),
                            ("c", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
            m = MS()
            m.l = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.tp // 1048576, m.ap // 1048576
    except Exception:
        pass
    return None, None


def port_in_use(port, host="127.0.0.1"):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def internet_ok(timeout=1.5):
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=timeout).close()
        return True
    except OSError:
        return False


def tool_version(cmd):
    exe = shutil.which(cmd)
    if not exe:
        return None
    try:
        return subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=3).stdout.strip().splitlines()[0]
    except Exception:
        return "installed (version unknown)"


def collect(data_dir, port=8765, ollama_ok=None):
    total, avail = _ram_mb()
    du = shutil.disk_usage(str(data_dir if Path(data_dir).exists() else Path.home()))
    measured = {"os": f"{platform.system()} {platform.release()}", "machine": platform.machine(),
                "python": platform.python_version(), "cpu_cores": os.cpu_count(), "ram_total_mb": total,
                "ram_available_mb": avail, "disk_total_gb": round(du.total / 1e9, 1), "disk_free_gb": round(du.free / 1e9, 1),
                "node": tool_version("node"), "git": tool_version("git"), "internet": internet_ok(),
                "crysta_port_in_use": port_in_use(port), "ollama_running": ollama_ok}
    warnings, est = [], {}
    if measured["disk_free_gb"] < 2:
        warnings.append("Less than 2 GB of free disk space.")
    if total and total < 4000:
        warnings.append("Under 4 GB of RAM: prefer small local models or none.")
    if total:
        est["suggested_local_model_size"] = ("1B-3B quantised" if total < 6000 else
                                              "7B-8B quantised" if total < 14000 else "up to ~13B quantised")
        est["note"] = "Estimate from RAM only; real speed depends on your CPU/GPU."
    return {"measured": measured, "estimates": est, "warnings": warnings}

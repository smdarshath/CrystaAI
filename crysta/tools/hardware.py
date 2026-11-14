"""Real hardware/OS information. Every metric is either measured or explicitly marked unavailable (never invented).
Uses only the standard library; if `psutil` is installed it is used for wider Windows/macOS coverage."""
from __future__ import annotations

import ctypes
import os
import platform
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

try:
    import psutil  # optional
except Exception:  # pragma: no cover
    psutil = None

SYS = platform.system()


def ok(value, unit=None, source=""):
    return {"available": True, "value": value, "unit": unit, "source": source}


def na(reason):
    return {"available": False, "value": None, "unit": None, "reason": reason}


def _read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


# ---------- CPU
def cpu_model():
    if SYS == "Linux":
        for line in (_read("/proc/cpuinfo") or "").splitlines():
            if line.lower().startswith(("model name", "hardware", "cpu model")):
                return ok(line.split(":", 1)[1].strip(), source="/proc/cpuinfo")
    if SYS == "Darwin":
        try:
            return ok(subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=3).stdout.strip(), source="sysctl")
        except Exception:
            pass
    if platform.processor():
        return ok(platform.processor(), source="platform")
    return na("The OS did not report a CPU model.")


def _linux_stat():
    line = (_read("/proc/stat") or "").splitlines()[:1]
    if not line:
        return None
    v = [int(x) for x in line[0].split()[1:]]
    return sum(v), v[3] + (v[4] if len(v) > 4 else 0)


def _win_times():
    class FT(ctypes.Structure):
        _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]
    i, k, u = FT(), FT(), FT()
    ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u))
    f = lambda t: (t.hi << 32) | t.lo
    return f(k) + f(u), f(i)


def cpu_percent(interval=0.25):
    try:
        if psutil:
            return ok(psutil.cpu_percent(interval=interval), "%", "psutil")
        sampler = _linux_stat if SYS == "Linux" else _win_times if SYS == "Windows" else None
        if sampler:
            a = sampler(); time.sleep(interval); b = sampler()
            dt = b[0] - a[0]
            return ok(round(100 * (1 - (b[1] - a[1]) / dt), 1) if dt > 0 else 0.0, "%", "/proc/stat" if SYS == "Linux" else "GetSystemTimes")
        la = os.getloadavg()[0]
        return ok(round(min(100.0, 100 * la / (os.cpu_count() or 1)), 1), "% (load average estimate)", "getloadavg")
    except Exception as e:
        return na(f"Could not sample CPU usage ({type(e).__name__}).")


def cpu_temp():
    try:
        if psutil and hasattr(psutil, "sensors_temperatures"):
            t = psutil.sensors_temperatures()
            for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
                if t.get(key):
                    return ok(round(t[key][0].current, 1), "°C", f"psutil:{key}")
    except Exception:
        pass
    if SYS == "Linux":
        zones = sorted(Path("/sys/class/thermal").glob("thermal_zone*"))
        for z in zones:
            raw, typ = _read(z / "temp"), (_read(z / "type") or "")
            if raw and raw.lstrip("-").isdigit() and any(k in typ.lower() for k in ("x86_pkg", "cpu", "coretemp", "soc", "acpitz")):
                return ok(round(int(raw) / 1000, 1), "°C", f"{z.name}:{typ}")
        for h in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
            raw = _read(h / "temp1_input")
            if raw and raw.lstrip("-").isdigit():
                return ok(round(int(raw) / 1000, 1), "°C", f"{h.name}:{_read(h / 'name')}")
        return na("This Linux system exposes no CPU temperature sensor (common in containers/VMs such as Chromebook Linux).")
    return na(f"CPU temperature is not readable on {SYS} without extra drivers.")


# ---------- memory / disks
def memory():
    try:
        if SYS == "Linux":
            info = {l.split(":")[0]: int(l.split()[1]) for l in (_read("/proc/meminfo") or "").splitlines() if ":" in l}
            total, avail = info["MemTotal"] * 1024, info.get("MemAvailable", info.get("MemFree", 0)) * 1024
            sw_t, sw_f = info.get("SwapTotal", 0) * 1024, info.get("SwapFree", 0) * 1024
            return {"total": total, "available": avail, "used": total - avail, "percent": round(100 * (total - avail) / total, 1), "swap_total": sw_t, "swap_used": sw_t - sw_f, "ok": True}
        if psutil:
            m = psutil.virtual_memory(); s = psutil.swap_memory()
            return {"total": m.total, "available": m.available, "used": m.total - m.available, "percent": m.percent, "swap_total": s.total, "swap_used": s.used, "ok": True}
        if SYS == "Windows":
            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong), ("c", ctypes.c_ulonglong)]
            m = MS(); m.l = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return {"total": m.tp, "available": m.ap, "used": m.tp - m.ap, "percent": m.load, "swap_total": None, "swap_used": None, "ok": True}
        if SYS == "Darwin":
            tot = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=3).stdout)
            return {"total": tot, "available": None, "used": None, "percent": None, "swap_total": None, "swap_used": None, "ok": True, "note": "Install psutil for live usage on macOS."}
    except Exception as e:
        return {"ok": False, "reason": f"Could not read memory ({type(e).__name__})."}
    return {"ok": False, "reason": "Memory information is not available on this OS."}


REAL_FS = {"ext2", "ext3", "ext4", "btrfs", "xfs", "vfat", "exfat", "ntfs", "fuseblk", "f2fs", "apfs", "hfs", "zfs"}


def _noop():
    pass


def disks():
    mounts = []
    try:
        if psutil:
            for p in psutil.disk_partitions(all=False):
                if p.fstype.lower() in REAL_FS or p.mountpoint in ("/", "C:\\") or SYS == "Windows":
                    mounts.append((p.mountpoint, p.fstype, p.device))
        elif SYS == "Linux":
            for line in (_read("/proc/mounts") or "").splitlines():
                dev, mp, fs = line.split()[:3]
                if fs in REAL_FS or mp == "/":
                    mounts.append((mp.replace("\\040", " "), fs, dev))
        elif SYS == "Windows":
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            mounts = [(f"{chr(65 + i)}:\\", "", "") for i in range(26) if mask & (1 << i)]
        else:
            mounts = [("/", "", "")] + [(str(p), "", "") for p in Path("/Volumes").glob("*")] if SYS == "Darwin" else [("/", "", "")]
    except Exception:
        mounts = [(str(Path.home().anchor or "/"), "", "")]
    out, seen = [], set()
    for mp, fs, dev in mounts:
        try:
            u = shutil.disk_usage(mp)
        except OSError:
            continue
        key = (u.total, u.used)
        if mp in seen or u.total == 0 or (key in seen):
            continue
        seen.add(mp); seen.add(key)
        out.append({"mount": mp, "fstype": fs, "total": u.total, "used": u.used, "free": u.free, "percent": round(100 * u.used / u.total, 1)})
    return out


# ---------- battery
def battery():
    try:
        if psutil and hasattr(psutil, "sensors_battery"):
            b = psutil.sensors_battery()
            if b:
                return {"available": True, "percent": round(b.percent), "charging": bool(b.power_plugged), "minutes_left": None if b.secsleft in (None, -1, -2) else round(b.secsleft / 60), "source": "psutil"}
        if SYS == "Linux":
            for bat in sorted(Path("/sys/class/power_supply").glob("BAT*")):
                cap, st = _read(bat / "capacity"), (_read(bat / "status") or "").lower()
                if cap and cap.isdigit():
                    return {"available": True, "percent": int(cap), "charging": st in ("charging", "full"), "status_text": st, "minutes_left": None, "source": str(bat)}
            return {"available": False, "reason": "No battery exposed (desktop PC, or a container/VM such as Chromebook Linux that can't see the battery)."}
        if SYS == "Windows":
            class SPS(ctypes.Structure):
                _fields_ = [("ac", ctypes.c_ubyte), ("flag", ctypes.c_ubyte), ("pct", ctypes.c_ubyte), ("r", ctypes.c_ubyte), ("life", ctypes.c_ulong), ("full", ctypes.c_ulong)]
            s = SPS(); ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s))
            if s.flag == 128 or s.pct == 255:
                return {"available": False, "reason": "Windows reports no battery."}
            return {"available": True, "percent": s.pct, "charging": s.ac == 1, "minutes_left": None if s.life == 0xFFFFFFFF else round(s.life / 60), "source": "GetSystemPowerStatus"}
        if SYS == "Darwin":
            out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=3).stdout
            m = re.search(r"(\d+)%;\s*([\w ]+)", out)
            if m:
                return {"available": True, "percent": int(m.group(1)), "charging": "discharging" not in m.group(2), "minutes_left": None, "source": "pmset"}
            return {"available": False, "reason": "macOS reports no battery."}
    except Exception as e:
        return {"available": False, "reason": f"Could not read the battery ({type(e).__name__})."}
    return {"available": False, "reason": "Battery information is not available on this OS."}


# ---------- network
def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def network(internet_ok=None):
    info = {"hostname": socket.gethostname(), "local_ip": local_ip(), "internet": internet_ok, "interfaces": []}
    try:
        if SYS == "Linux":
            for d in sorted(Path("/sys/class/net").iterdir()):
                if d.name != "lo":
                    info["interfaces"].append({"name": d.name, "state": _read(d / "operstate")})
            tot = {"rx": 0, "tx": 0}
            for line in (_read("/proc/net/dev") or "").splitlines()[2:]:
                name, data = line.split(":")
                if name.strip() != "lo":
                    f = data.split(); tot["rx"] += int(f[0]); tot["tx"] += int(f[8])
            info["bytes_received"], info["bytes_sent"] = tot["rx"], tot["tx"]
        elif psutil:
            for n, st in psutil.net_if_stats().items():
                if not n.startswith("lo"):
                    info["interfaces"].append({"name": n, "state": "up" if st.isup else "down"})
            c = psutil.net_io_counters(); info["bytes_received"], info["bytes_sent"] = c.bytes_recv, c.bytes_sent
    except Exception:
        pass
    return info


def uptime():
    try:
        if SYS == "Linux":
            return ok(round(float((_read("/proc/uptime") or "").split()[0])), "s", "/proc/uptime")
        if psutil:
            return ok(round(time.time() - psutil.boot_time()), "s", "psutil")
        if SYS == "Windows":
            return ok(ctypes.windll.kernel32.GetTickCount64() // 1000, "s", "GetTickCount64")
    except Exception:
        pass
    return na("Uptime is not available on this system.")


def own_process():
    rss = None
    try:
        if SYS == "Linux":
            for line in (_read("/proc/self/status") or "").splitlines():
                if line.startswith("VmRSS"):
                    rss = int(line.split()[1]) * 1024
        elif psutil:
            rss = psutil.Process().memory_info().rss
        else:
            import resource
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if SYS == "Darwin" else 1024)
    except Exception:
        pass
    import threading
    return {"rss": rss, "threads": threading.active_count(), "pid": os.getpid()}


def snapshot(internet_ok=None):
    mem = memory()
    return {"time": time.time(),
            "system": {"os": f"{platform.system()} {platform.release()}", "version": platform.version()[:120], "architecture": platform.machine(),
                       "hostname": socket.gethostname(), "python": platform.python_version(), "uptime": uptime(),
                       "cores_logical": os.cpu_count(), "cores_physical": (psutil.cpu_count(logical=False) if psutil else None)},
            "cpu": {"model": cpu_model(), "usage": cpu_percent(), "temperature": cpu_temp()},
            "memory": mem, "disks": disks(), "battery": battery(), "network": network(internet_ok), "crysta": own_process(),
            "psutil": bool(psutil)}

from __future__ import annotations

from .base import Agent


class Volt(Agent):
    id, name = "volt", "VOLT"
    description = "Hardware and device intelligence: real CPU, RAM, storage, battery, network and OS information; unavailable values are shown as unavailable."
    system_instruction = ("You are Volt, a diagnostics agent. Distinguish measured values from estimates. Never change settings or "
                          "install anything without authorisation.")
    permitted_tools = frozenset({"hardware", "system_info", "explain_error", "llm_status"})

    @staticmethod
    def _gb(b):
        return f"{b / 1e9:.1f} GB" if b is not None else "unknown"

    def do_diagnose(self, sub, ctx):
        h = self.tool(ctx, "hardware")
        sysd, cpu, mem = h["system"], h["cpu"], h["memory"]
        val = lambda m, f="{}": f.format(m["value"]) if m["available"] else f"unavailable ({m['reason']})"
        lines = [f"Measured on this computer ({time_now()}):",
                 f"• OS: {sysd['os']} · {sysd['architecture']}",
                 f"• CPU: {val(cpu['model'])} · {sysd['cores_logical']} logical cores",
                 "• CPU usage: " + (f"{cpu['usage']['value']}{cpu['usage']['unit']}" if cpu["usage"]["available"] else val(cpu["usage"])),
                 "• CPU temperature: " + (f"{cpu['temperature']['value']} °C" if cpu["temperature"]["available"] else val(cpu["temperature"]))]
        lines.append(f"• RAM: {self._gb(mem['used'])} used of {self._gb(mem['total'])} ({mem['percent']}%)" if mem.get("ok") and mem.get("used") is not None else
                     f"• RAM: {self._gb(mem.get('total'))} total; usage unavailable" if mem.get("ok") else f"• RAM: unavailable ({mem.get('reason')})")
        for d in h["disks"][:3]:
            lines.append(f"• Disk {d['mount']}: {self._gb(d['free'])} free of {self._gb(d['total'])} ({d['percent']}% used)")
        b = h["battery"]
        lines.append(f"• Battery: {b['percent']}% · {'charging' if b['charging'] else 'on battery'}" if b["available"] else f"• Battery: unavailable ({b['reason']})")
        n = h["network"]
        lines.append(f"• Network: {'internet reachable' if n['internet'] else 'internet not reachable'} · local IP {n['local_ip'] or 'unknown'}")
        warn = []
        if h["disks"] and min(d["free"] for d in h["disks"][:1]) < 2e9:
            warn.append("Less than 2 GB free on the main disk.")
        if mem.get("ok") and mem.get("percent") and mem["percent"] > 90:
            warn.append("RAM is almost full.")
        if warn:
            lines += ["Warnings:"] + [f"• {w}" for w in warn]
        d0 = h["disks"][0] if h["disks"] else None
        speech = f"Storage: {self._gb(d0['free'])} free of {self._gb(d0['total'])}." if d0 else "I could not read storage information."
        return self.ok("\n".join(lines), data=h, limitations=["Read-only: I changed nothing.", "Values marked unavailable are not exposed by this operating system or container."], speech=speech)

    do_hardware = do_diagnose


def time_now():
    import time
    return time.strftime("%H:%M:%S")

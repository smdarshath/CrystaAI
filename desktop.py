#!/usr/bin/env python3
"""CRYSTA AI - standalone desktop application launcher.

Opens CRYSTA in its OWN native window (not a browser tab, no Chrome needed). The backend runs inside this same
process on a random loopback port protected by a per-launch secret, and is shut down when the window closes.

Window back-ends (first available is used):
  1. pywebview  - Windows (Edge WebView2, preinstalled on Win10/11), macOS (WKWebView), Linux (GTK/Qt)
  2. GTK3 + WebKit2 directly (Debian/Ubuntu/Chromebook Linux: sudo apt install python3-gi gir1.2-webkit2-4.1)
If neither exists CRYSTA tells you what to install; it never silently opens a web browser (use --browser if you want that).

    python3 desktop.py            start the app window
    python3 desktop.py --check    test the backend lifecycle and report which window back-end is available
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import platform
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

TITLE = "CRYSTA AI"
SYS = platform.system()


# ------------------------------------------------------------------ helpers
def show_error(title: str, message: str) -> None:
    """Show an error even when launched without a console (double-click / pythonw / .desktop)."""
    print(f"{title}: {message}", file=sys.stderr)
    try:
        if SYS == "Windows":
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
        elif SYS == "Darwin":
            subprocess.run(["osascript", "-e", f'display dialog {json.dumps(message)} with title {json.dumps(title)} buttons {{"OK"}} with icon stop'], timeout=60)
        else:
            for cmd in (["zenity", "--error", "--title", title, "--text", message], ["kdialog", "--error", message, "--title", title], ["notify-send", title, message]):
                if shutil.which(cmd[0]):
                    subprocess.run(cmd, timeout=60)
                    break
    except Exception:
        pass


def pid_alive(pid: int) -> bool:
    try:
        if SYS == "Windows":
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
    except PermissionError:
        return True


def available_gui():
    """Return the window back-end that can be used right now (or None) plus a human reason."""
    try:
        import webview  # noqa: F401
        return "webview", "pywebview"
    except Exception:
        pass
    if SYS == "Linux":
        try:
            import gi
            gi.require_version("Gtk", "3.0")
            for v in ("4.1", "4.0"):
                try:
                    gi.require_version("WebKit2", v)
                    from gi.repository import Gtk, WebKit2  # noqa: F401
                    return "gtk", f"GTK3 + WebKit2 {v}"
                except (ValueError, ImportError):
                    continue
        except Exception:
            pass
    return None, "none"


INSTALL_HELP = {
    "Linux": "Install a window component once:\n  sudo apt install python3-gi gir1.2-webkit2-4.1   (if that package is missing: gir1.2-webkit2-4.0)\n"
             "or:  python3 -m pip install pywebview",
    "Windows": "Install the window component once (in a terminal):\n  py -m pip install pywebview\nWindows 10/11 already includes the Edge WebView2 runtime it uses.",
    "Darwin": "Install the window component once (in Terminal):\n  python3 -m pip install pywebview",
}


# ------------------------------------------------------------------ runtime (backend lifecycle)
class Runtime:
    """Starts and safely stops the CRYSTA backend that lives inside this process."""

    def __init__(self):
        from crysta.app import App
        from crysta.config import Config
        from crysta.server import make_server
        self.cfg = Config()
        self.cfg.host, self.cfg.port = "127.0.0.1", 0
        self.cfg.session_token = secrets.token_urlsafe(24)
        self.lock = self.cfg.data_dir / "desktop.lock"
        self._check_single_instance()
        self.app = App(self.cfg)
        self.server = make_server(self.app, "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, name="crysta-backend", daemon=True)
        self.stopped = False
        atexit.register(self.stop)

    def _check_single_instance(self):
        self.cfg.data_dir.mkdir(parents=True, exist_ok=True)
        if self.lock.exists():
            try:
                info = json.loads(self.lock.read_text())
                if pid_alive(int(info["pid"])):
                    raise RuntimeError(f"CRYSTA is already running (process {info['pid']}). Close it first or switch to its window.")
            except (ValueError, KeyError, OSError):
                pass  # stale/corrupt lock file: ignore

    def start(self) -> str:
        self.thread.start()
        self.lock.write_text(json.dumps({"pid": os.getpid(), "port": self.port, "started": time.time()}))
        return f"http://127.0.0.1:{self.port}/?s={self.cfg.session_token}"

    def stop(self):
        if self.stopped:
            return
        self.stopped = True
        try:
            self.app.coordinator.cancel()
            self.app.coordinator.pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        try:
            from crysta.tools import voice
            voice.stop()
        except Exception:
            pass
        try:
            if self.thread.is_alive():          # shutdown() blocks forever if serve_forever() never ran
                self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
        try:
            self.app.db.close()
        except Exception:
            pass
        try:
            self.lock.unlink()
        except OSError:
            pass


# ------------------------------------------------------------------ window back-ends
def run_pywebview(url: str, rt: Runtime):
    import webview
    window = webview.create_window(TITLE, url, width=1280, height=800, min_size=(800, 560), text_select=True)
    window.events.closed += rt.stop
    storage = rt.cfg.data_dir / "webview"
    storage.mkdir(exist_ok=True)
    try:
        webview.start(private_mode=False, storage_path=str(storage))   # keeps localStorage between launches
    except TypeError:
        webview.start()                                                  # older pywebview


def run_gtk(url: str, rt: Runtime):
    import gi
    gi.require_version("Gtk", "3.0")
    for v in ("4.1", "4.0"):
        try:
            gi.require_version("WebKit2", v)
            break
        except ValueError:
            continue
    from gi.repository import Gtk, WebKit2

    origin = f"http://127.0.0.1:{rt.port}"
    storage = rt.cfg.data_dir / "webview"
    storage.mkdir(exist_ok=True)
    manager = WebKit2.WebsiteDataManager(base_data_directory=str(storage), base_cache_directory=str(storage / "cache"))
    context = WebKit2.WebContext.new_with_website_data_manager(manager)
    view = WebKit2.WebView.new_with_context(context)
    settings = view.get_settings()
    settings.set_enable_media_stream(True)          # microphone for voice features
    settings.set_enable_developer_extras(False)
    settings.set_enable_write_console_messages_to_stdout(False)

    def on_permission(_view, request):               # only our own page may use the microphone
        if isinstance(request, WebKit2.UserMediaPermissionRequest) and _view.get_uri().startswith(origin):
            request.allow()
        else:
            request.deny()
        return True

    def on_policy(_view, decision, dtype):           # never navigate the app window away from CRYSTA
        if dtype == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            uri = decision.get_navigation_action().get_request().get_uri()
            if not uri.startswith(origin):
                decision.ignore()
                webbrowser.open(uri)
                return True
        return False

    view.connect("permission-request", on_permission)
    view.connect("decide-policy", on_policy)
    win = Gtk.Window(title=TITLE)
    win.set_default_size(1280, 800)
    win.set_size_request(800, 560)
    win.connect("destroy", lambda *_: (rt.stop(), Gtk.main_quit()))
    win.add(view)
    view.load_uri(url)
    win.show_all()
    signal.signal(signal.SIGINT, lambda *_: Gtk.main_quit())
    signal.signal(signal.SIGTERM, lambda *_: Gtk.main_quit())
    Gtk.main()


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=TITLE + " desktop application")
    ap.add_argument("--check", action="store_true", help="self-test the backend and report the window back-end, then exit")
    ap.add_argument("--gui", choices=["webview", "gtk"], help="force a window back-end")
    ap.add_argument("--browser", action="store_true", help="explicitly use your default web browser instead of a native window")
    a = ap.parse_args(argv)
    rt = None
    try:
        gui, label = available_gui()
        if a.check:
            return selfcheck(gui, label)
        gui = a.gui or gui
        if not gui and not a.browser:
            show_error(TITLE, "No window component is installed, so CRYSTA can't open its own window.\n\n" + INSTALL_HELP.get(SYS, INSTALL_HELP["Linux"]) +
                       "\n\n(Advanced: run with --browser to use your default web browser instead.)")
            return 2
        rt = Runtime()
        url = rt.start()
        print(f"CRYSTA backend ready on 127.0.0.1:{rt.port} (window: {gui or 'default browser'})")
        if a.browser and not gui:
            print("Opening your default browser (explicit --browser mode). Press Ctrl+C to stop.")
            webbrowser.open(url)
            try:
                while True:
                    time.sleep(3600)
            except KeyboardInterrupt:
                pass
        elif gui == "gtk":
            run_gtk(url, rt)
        else:
            run_pywebview(url, rt)
        return 0
    except Exception as e:
        msg = f"CRYSTA could not start: {e}"
        try:
            d = (rt.cfg.data_dir if rt else ROOT / "data")
            d.mkdir(parents=True, exist_ok=True)
            (d / "startup-error.log").write_text(traceback.format_exc())
            msg += f"\n\nDetails were saved to {d / 'startup-error.log'}"
        except Exception:
            pass
        show_error(TITLE, msg)
        return 1
    finally:
        if rt:
            rt.stop()


def selfcheck(gui, label) -> int:
    import http.client
    print(f"Platform: {SYS} {platform.machine()} · Python {platform.python_version()}")
    print(f"Window back-end: {label if gui else 'NONE - ' + INSTALL_HELP.get(SYS, '')}")
    rt = Runtime()
    url = rt.start()
    try:
        c = http.client.HTTPConnection("127.0.0.1", rt.port, timeout=5)
        c.request("GET", "/api/status"); r = c.getresponse(); r.read()
        blocked = r.status == 401
        print(f"API without the session secret: HTTP {r.status} (expected 401 = protected)")
        c.request("GET", "/?s=" + rt.cfg.session_token); r = c.getresponse(); r.read()
        cookie = r.getheader("Set-Cookie", "").split(";")[0]
        c.request("GET", "/api/status", headers={"Cookie": cookie}); r = c.getresponse(); body = r.read().decode()
        print(f"API with the app window's secret: HTTP {r.status} (version {json.loads(body).get('version')})")
        ok = r.status == 200 and blocked
    finally:
        rt.stop()
    port_closed = False
    try:
        import socket
        socket.create_connection(("127.0.0.1", rt.port), timeout=1).close()
    except OSError:
        port_closed = True
    print("Backend stopped cleanly: " + ("yes, port released" if port_closed else "NO - port still open"))
    return 0 if ok and port_closed else 1


if __name__ == "__main__":
    sys.exit(main())

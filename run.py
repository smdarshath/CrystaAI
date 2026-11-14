#!/usr/bin/env python3
"""Start Crysta AI:  python3 run.py   (Windows: py run.py)"""
import argparse
import socket
import sys
import threading
import webbrowser

if sys.version_info < (3, 9):
    sys.exit("Crysta AI needs Python 3.9 or newer. Your version: " + sys.version.split()[0])

from crysta.app import App  # noqa: E402
from crysta.config import Config  # noqa: E402
from crysta.server import make_server  # noqa: E402


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "your-computer-ip"


def main():
    ap = argparse.ArgumentParser(description="Crysta AI - local-first personal assistant")
    ap.add_argument("--port", type=int)
    ap.add_argument("--lan", action="store_true", help="listen on your local network so a paired phone can connect")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    cfg = Config()
    if a.port:
        cfg.port = a.port
    if a.lan:
        cfg.host = "0.0.0.0"
    app = App(cfg)
    try:
        srv = make_server(app)
    except OSError as e:
        sys.exit(f"Could not start on port {cfg.port}: {e}\nSomething else is using it. Try:  python3 run.py --port {cfg.port + 1}")
    scheme = "https" if cfg.tls_cert else "http"
    url = f"{scheme}://localhost:{cfg.port}"
    print(f"\n  CRYSTA AI {app.version} is running\n  Open: {url}\n  Data folder: {cfg.data_dir}\n  Stop: press Ctrl+C\n")
    if a.lan:
        print(f"  LAN mode ON. Phone address: {scheme}://{lan_ip()}:{cfg.port}")
        if scheme == "http":
            print("  Warning: plain HTTP is not encrypted. Use only on a network you trust (see docs/DEVICE_PAIRING.md).\n")
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down. Bye!")
    finally:
        srv.server_close()
        app.db.close()


if __name__ == "__main__":
    main()

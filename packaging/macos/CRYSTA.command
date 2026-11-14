#!/usr/bin/env bash
# Double-click in Finder (first time: right-click > Open). Needs: python3 -m pip install pywebview
cd "$(dirname "$0")/../.." && exec python3 desktop.py

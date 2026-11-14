#!/usr/bin/env bash
# Starts the CRYSTA desktop application (own window, no browser).
cd "$(dirname "$0")"
exec python3 desktop.py "$@"

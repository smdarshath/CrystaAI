#!/usr/bin/env bash
# Server-only mode (for pairing a phone with --lan, or developing). Opens your web browser.
cd "$(dirname "$0")"
exec python3 run.py "$@"

#!/usr/bin/env bash
cd "$(dirname "$0")/../tests" && python3 -m unittest discover -v -p "test_*.py"

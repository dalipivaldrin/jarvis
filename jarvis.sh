#!/usr/bin/env bash
# Startet Jarvis aus der virtuellen Umgebung
cd "$(dirname "$0")"
source .venv/bin/activate
python -m jarvis "$@"

#!/usr/bin/env bash
set -e
KIT="$(cd "$(dirname "$0")" && pwd)"
command -v ffmpeg >/dev/null || { echo "Install ffmpeg first (Mac: brew install ffmpeg, Linux: sudo apt install ffmpeg)"; exit 1; }
PYTHON="${PYTHON:-python3}"
[ -d "$KIT/.venv" ] || "$PYTHON" -m venv "$KIT/.venv"
PY="$KIT/.venv/bin/python"; [ -x "$PY" ] || PY="$KIT/.venv/Scripts/python.exe"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r "$KIT/requirements.txt"
"$PY" "$KIT/fx_engine.py" --fetch
echo "KIT_READY  python: $PY"

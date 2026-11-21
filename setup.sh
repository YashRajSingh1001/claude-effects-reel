#!/usr/bin/env bash
# One-time setup (about 2 minutes). Safe to re-run: prints KIT_READY when everything is in place.
# usage: bash setup.sh [engine_dir]   (default ~/claude-video-effects)
set -e
KIT="$(cd "$(dirname "$0")" && pwd)"
ENGINE="${1:-$HOME/claude-video-effects}"
PIN=60840acc7e126a5e34068276a23e912ec4c8c34c   # upstream version this kit was tested against
if [ ! -d "$ENGINE/.git" ]; then
  git clone -q https://github.com/Vibha-Ramprakash/claude-video-effects "$ENGINE"
  git -C "$ENGINE" -c advice.detachedHead=false checkout -q "$PIN"
fi
bash "$ENGINE/scripts/setup.sh"
cp "$KIT/fx_engine.py" "$ENGINE/scripts/fx_engine.py"
"$ENGINE/.venv/bin/python" -c "import scipy" 2>/dev/null || "$ENGINE/.venv/bin/python" -m pip install -q scipy
echo "KIT_READY  python: $ENGINE/.venv/bin/python"

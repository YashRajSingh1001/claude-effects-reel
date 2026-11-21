---
name: effects-reel
description: Turn a talking-head clip into a "Claude types /effects X, the edit reveals" reel - chat screens, 18 face-tracked effects, an end card and a beat with UI sounds. Use when someone shares a clip and asks for this reel or these effects.
---

# Effects reel

All paths are relative to this folder. The user is usually not technical: do the work, keep replies short.

1. Set up once: `bash setup.sh` (prints KIT_READY; installs Python packages into `.venv` and downloads fonts and models).
   It needs ffmpeg and Python 3.10+. If either is missing, install it for them: Mac `brew install ffmpeg python`,
   Windows `winget install Gyan.FFmpeg Python.Python.3.12` (then open a new shell), Linux `sudo apt install ffmpeg python3-venv`.
   Afterwards use `PY=.venv/bin/python` (Windows: `.venv/Scripts/python`).
2. Get the clip (vertical, person in frame, about 3.7 s per effect + 1 s) and ask which effects (1-11) plus their name,
   handle and any real numbers for charts. If they don't say, use the 7 in `example_config.json`. Never invent stats.
3. Copy `example_config.json` to `reel.json` next to the clip and fill it in (README lists every key and option; all effects:
   `$PY fx_engine.py --list`).
4. `$PY make_reel.py <clip> --config reel.json --check`, then look at `<clip>_reel_work/check_*.png` and `ui_*.png`.
   Fix anything covering the face or unreadable (shorter text, `"guard": "0"` for panels hidden behind hands).
5. `$PY make_reel.py <clip> --config reel.json` -> `<clip>_claude_reel.mp4`. Tell them where it is and to watch it before posting.

Effects (pick 1-11; options per effect are in README.md):
glass-widgets, documentary, orbit, chart-split, spotlight, checklist, timeline, backdrop-word, moody, lean-in,
slow-push, locked-on, led-sign, reject-stamp, countdown-flip, huge-strike, tape-label, messages.

Rendering takes 10-15 minutes on a normal laptop: run it in the background and tell the user it is working.

The voice is replaced by a synthesized beat + UI sounds. Effects are starter versions; captions and trending audio go on in CapCut/Instagram.

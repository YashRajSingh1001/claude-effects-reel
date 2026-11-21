---
name: effects-reel
description: Turn a talking-head clip into a "Claude types /effects X, the edit reveals" reel - chat screens, 18 effects (most face-tracked), an end card and a beat with UI sounds. Use when someone shares a clip and asks for this reel or these effects.
---

# Effects reel

All paths are relative to this folder. The user is usually not technical: do the work, keep replies short.

1. Set up once: `bash setup.sh` (prints KIT_READY; installs Python packages into `.venv` and downloads fonts and models).
   It needs ffmpeg and Python 3.10+. If either is missing, install it for them: Mac `brew install ffmpeg python`,
   Windows `winget install Gyan.FFmpeg Python.Python.3.12` (then open a new shell), Linux `sudo apt install ffmpeg python3-venv`.
   Afterwards use `PY=.venv/bin/python` (Windows: `.venv/Scripts/python`).
2. Get the clip (vertical, person in frame, about 3.7 s per effect + 1 s) and ask which effects (1-11) plus their name,
   handle and any real numbers for charts. If they don't say, use the 7 in `example_config.json`. Never invent stats.
3. Copy `example_config.json` to `reel.json` next to the clip and fill it in using effect names from the list below
   (README lists every config key and each effect's options).
4. `$PY make_reel.py <clip> --config reel.json --check`, then look at `<clip>_reel_work/check_*.png` and `ui_*.png`.
   Fix anything covering the face or unreadable (shorter text, `"guard": "0"` for panels hidden behind hands).
5. `$PY make_reel.py <clip> --config reel.json` -> `<clip>_claude_reel.mp4`. Tell them where it is and to watch it before posting.

## Effects (use these exact names in the "fx" field)
- glass-widgets: frosted glass widgets around your head
- documentary: black and white you, stamped words
- orbit: your reels circle your head (if the user says "orbital", use "orbit")
- chart-split: a live chart on top, you below
- spotlight: kill the lights, keep you lit
- checklist: Claude ticks off every step
- timeline: a live editing timeline
- backdrop-word: a giant word behind you
- moody: a moody colour grade (whole frame, not face-tracked)
- lean-in: a punch-in on one word
- slow-push: a slow cinematic push-in
- locked-on: brackets lock onto your face
- led-sign: a glowing LED sign types out
- reject-stamp: a big red stamp slams down
- countdown-flip: a 3, 2, 1 flip clock
- huge-strike: a huge word gets crossed out
- tape-label: yellow tape lands on your chest
- messages: chat pop-ups stack up

Pick 1 to 11 per reel. Default is the first 7 (same as example_config.json).

Rendering takes 10-15 minutes on a normal laptop: run it in the background and tell the user it is working.

The voice is replaced by a synthesized beat + UI sounds. Effects are starter versions; captions and trending audio go on in CapCut/Instagram.

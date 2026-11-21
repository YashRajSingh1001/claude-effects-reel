# claude-effects-reel

Turns one talking-head clip into a "Claude types `/effects X` → the edit reveals" reel:
Claude chat screens with typing and the slash menu, a dot-reveal preview card, a zoom to the full-screen edit,
an end card ("Comment 'claude'"), and a synthesized beat + UI sound design (voice muted).

## Setup (once per machine, ~2 min)
```bash
bash setup.sh            # clones the effects engine to ~/claude-video-effects and installs everything
```

## Make a reel
1. Copy `example_config.json` to `reel.json` and edit it: your name/handle, the effects (1–11, in order) and their text/numbers.
   Any effect from the engine works (`~/claude-video-effects/.venv/bin/python ~/claude-video-effects/scripts/fx_engine.py --list`).
2. Optional: put reel screenshots in a folder and set `reels_folder` (used by orbit, phone-fan, noise...).
3. Check frames (fast), then render:
```bash
PY=~/claude-video-effects/.venv/bin/python
$PY make_reel.py myclip.mp4 --config reel.json --check   # stills in myclip_reel_work/
$PY make_reel.py myclip.mp4 --config reel.json           # -> myclip_claude_reel.mp4
```
The clip needs about 3.7 s per effect (7 effects ≈ 26 s). Each edit gets 2 s of typing, 1 s of card, 2 s full screen.

## Config keys
| key | default | what it does |
|---|---|---|
| `name` | Yash | used in "Evening, <name>" |
| `handle` | @yashraj.decodes | end card |
| `clip_start` | 0 | where to start in your clip (seconds) |
| `reels_folder` / `crop_instagram` | – / true | screenshots for card effects; crops Instagram UI from phone screenshots |
| `comment_word` | claude | the word typed on the outro and used in the CTA |
| `reply`, `end_title`, `end_pill`, `end_line1`, `end_line2`, `more_tile` | auto | outro text overrides (`more_tile` = `big|line|line`) |
| `effects[].desc` | built-in | the one-liner under the name in the slash menu |
| `effects[].guard` | "1" | "0" lets the panel sit in front of hands/mic (use for checklist, timeline, widgets) |

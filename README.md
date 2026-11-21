# claude-effects-reel

Turn one talking-head clip into a **"Claude types `/effects X` → the edit reveals"** reel:

- Claude chat screens: typing, the slash menu, "Editing with X…"
- a dot-reveal preview card that zooms into the full-screen edit
- 18 face-tracked effects (orbit, spotlight, glass widgets, checklist, timeline, LED sign, chart split…)
- an end card ("Comment 'claude'") with every edit as a tile
- a beat + UI sound design (voice muted), with every reveal landing on a downbeat

Created by **Yash Raj Singh** ([@yashraj.decodes](https://instagram.com/yashraj.decodes)).

## Easiest way: let Claude do it
Open **Claude Code** (or any Claude that can run code), attach your clip and paste:

> Clone https://github.com/YashRajSingh1001/claude-effects-reel, follow its SKILL.md and make me a reel from this clip.
> Effects: glass-widgets, orbit, spotlight, checklist. My name is ___, my handle is ___.

**As a Claude Code skill** (then just type "make an effects reel from this clip"):
```bash
git clone https://github.com/YashRajSingh1001/claude-effects-reel ~/.claude/skills/effects-reel
```

## Run it yourself
Needs ffmpeg and Python 3.10+ (Mac, Linux, or Windows with Git Bash/WSL).
```bash
bash setup.sh                                  # once, ~2 min: packages, fonts, face/person models
cp example_config.json reel.json               # edit: name, handle, effects (1–11) and their text/numbers
PY=.venv/bin/python                            # Windows: .venv/Scripts/python
$PY fx_engine.py --list                        # every effect
$PY make_reel.py myclip.mp4 --config reel.json --check   # quick stills in myclip_reel_work/
$PY make_reel.py myclip.mp4 --config reel.json           # -> myclip_claude_reel.mp4
```
The clip needs about 3.7 s per effect (7 effects ≈ 27 s). Each edit gets ~2 s of typing, 1 s of card, 2 s full screen.

## Config keys
| key | default | what it does |
|---|---|---|
| `name` | there | "Evening, <name>" on the outro |
| `handle` | – | shown on the end card |
| `clip_start` | 0 | where to start in your clip (seconds) |
| `reels_folder` / `crop_instagram` | – / true | screenshots for card effects (orbit, phone-fan…); crops Instagram UI from phone screenshots |
| `comment_word` | claude | the word typed on the outro and used in the CTA |
| `reply`, `end_title`, `end_pill`, `end_line1`, `end_line2`, `more_tile` | auto | outro text (`more_tile` = `big|line|line`) |
| `effects[].fx` + options | – | any effect from `fx_engine.py --list`; options below |
| `effects[].desc` | built-in | the one-liner under the name in the slash menu |
| `effects[].guard` | auto | "1" puts the panel behind you, "0" in front of hands/mic; auto = behind above your head, in front below your chin |

## Effect options
| effect | options |
|---|---|
| `glass-widgets` | `text`, `sub`, `name`, `handle`, `top`, `bars`, `day`, `date`, `event` |
| `documentary` | `text` (lines split by `|`), `hl`, `name`, `handle`, `tag`, `wall` |
| `orbit` | `count`, `images` (folder; defaults to `reels_folder` or stills from your clip) |
| `chart-split` | `title`, `labels`, `vals` |
| `spotlight`, `backdrop-word`, `lean-in`, `led-sign`, `reject-stamp`, `tape-label`, `locked-on` | `text` (`backdrop-word` also `color` as `r,g,b`) |
| `checklist` | `text` (`step::detail|step::detail`), `look` (`light`/`dark`) |
| `timeline` | `text`, `sub` |
| `countdown-flip` | `seq` (default `3|2|1`), `text` (last card) |
| `huge-strike` | `text`, `sub` |
| `messages` | `text` (messages split by `|`), `from` |
| `moody`, `slow-push` | – |

These are starter edits: watch before you post, and add captions/trending audio in CapCut or Instagram.

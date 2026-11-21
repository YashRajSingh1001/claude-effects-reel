# claude-effects-reel

Turn one short selfie video into a ready-to-post Instagram Reel where **Claude "types" an effect and the edit appears on screen**: no editing app, no editing skills.

Created by **Yash Raj Singh** ([@yashraj.decodes](https://instagram.com/yashraj.decodes)).

## Start here: paste this into Claude
Open the **Claude desktop app → Code tab** (or Claude Code), attach your video, and paste:

> Clone https://github.com/YashRajSingh1001/claude-effects-reel and follow its SKILL.md to make me an effects reel from the video I attached.
> My name is ___ and my Instagram handle is ___.

Claude does the rest: it installs what it needs, shows you preview pictures, then makes the video and tells you where it saved it.

## What you get
A vertical 1080×1920 video (`yourclip_claude_reel.mp4`) with:
- Claude chat screens: typing `/effects orbit`, the menu, "Editing with orbit…"
- a preview card that zooms into the full-screen edit
- 1 to 11 effects of your choice, out of 18 (most follow your face) (see the list below)
- an end card ("Comment 'claude'") showing every edit as a tile
- a beat with typing and whoosh sounds, timed to every reveal (your voice is muted)

## What you need
1. **A clip:** a vertical video of you talking to the camera, face clearly visible. Roughly **4 seconds per effect** (7 effects ≈ 30 seconds).
2. **Claude with the Code tab:** the [Claude desktop app](https://claude.com/download) (Code tab) or [Claude Code](https://claude.com/claude-code). It needs to run things on your computer, so the normal chat window alone won't work.
3. **Your details:** your name, your Instagram handle, and any real numbers you want in charts (for example your top reels' views).

That's it. Claude installs everything else itself (about 2 minutes the first time).

## Want to choose the effects?
Use this longer version of the message instead:

> Clone https://github.com/YashRajSingh1001/claude-effects-reel and follow its SKILL.md to make me a reel from my clip at ___.
> My name is ___ and my handle is ___.
> Effects: glass-widgets, documentary, orbit, chart-split, spotlight, checklist, timeline.
> For the chart use these real numbers: ___ (or say "skip the chart").

Claude will set things up, show you preview stills first, then render the final video and tell you where it saved it. **Watch it before posting**, then add captions or trending audio in CapCut or Instagram if you like.

**Use it again and again (Claude Code):** install it once as a skill, then just say *"make an effects reel from this clip"*:
```bash
git clone https://github.com/YashRajSingh1001/claude-effects-reel ~/.claude/skills/effects-reel
```

## The effects
Pick any 1 to 11 for one reel.

| effect | what it looks like |
|---|---|
| `glass-widgets` | frosted glass widgets around you: a big number, a bar chart, your name card, a calendar |
| `documentary` | black-and-white you with big stamped words behind you |
| `orbit` | your reels (or stills from your clip) circle your head |
| `chart-split` | a live bar chart of your real numbers on top, you below |
| `spotlight` | the room goes dark, you stay lit, a word appears behind you |
| `checklist` | Claude ticks off steps one by one |
| `timeline` | an editing timeline slides up with a moving playhead |
| `backdrop-word` | a giant word behind you |
| `moody` | a moody film colour grade |
| `lean-in` | a quick punch-in on your face with one word |
| `slow-push` | a slow cinematic zoom |
| `locked-on` | green "target locked" brackets snap onto your face |
| `led-sign` | a glowing LED sign types out above you |
| `reject-stamp` | a big red stamp slams down |
| `countdown-flip` | a 3, 2, 1 flip clock |
| `huge-strike` | a huge word gets crossed out and replaced |
| `tape-label` | yellow tape with your words lands on your chest |
| `messages` | message notifications stack up |

## Tips
- Good light and your face in the top half of the frame give the cleanest results.
- If a panel covers your face or hands, tell Claude, e.g. *"move the checklist in front of my hands"* or *"shorten that text"*.
- Want your real reel covers in `orbit`? Put screenshots of your reels in a folder and tell Claude where it is.
- Never let it invent stats: give it your real numbers or ask it to skip the chart.
- No video handy? Any phone selfie video works; just talk to the camera for 30 seconds.

---

## For developers

### Run it by hand
Needs ffmpeg and Python 3.10+ (Mac, Linux, or Windows with Git Bash/WSL).
```bash
bash setup.sh                                  # once, ~2 min: packages, fonts, face/person models
cp example_config.json reel.json               # edit: name, handle, effects (1–11) and their text/numbers
PY=.venv/bin/python                            # Windows: .venv/Scripts/python
$PY fx_engine.py --list                        # every effect
$PY make_reel.py myclip.mp4 --config reel.json --check   # quick stills in myclip_reel_work/
$PY make_reel.py myclip.mp4 --config reel.json           # -> myclip_claude_reel.mp4
```
The clip needs about 3.7 s per effect plus 1 s. Each edit gets ~2 s of typing, 1 s of card, 2 s full screen. See `examples/yash.json` for a filled-in config.

### Config keys
| key | default | what it does |
|---|---|---|
| `name` | there | "Evening, <name>" on the outro |
| `handle` | – | shown on the end card |
| `clip_start` | 0 | where to start in your clip (seconds) |
| `reels_folder` / `crop_instagram` | – / true | screenshots for `orbit`; crops the Instagram UI from phone screenshots |
| `comment_word` | claude | the word typed on the outro and used in the call to action |
| `reply`, `end_title`, `end_pill`, `end_line1`, `end_line2`, `more_tile` | auto | outro text (`more_tile` = `big\|line\|line`) |
| `effects[].fx` + options | – | any effect from `fx_engine.py --list`; options below |
| `effects[].desc` | built-in | the one-liner under the name in the slash menu |
| `effects[].guard` | auto | "1" puts the panel behind you, "0" in front of hands/mic; auto = behind above your head, in front below your chin |

### Effect options
Lists are separated with `|`, e.g. `"labels": "Reel 1|Reel 2|Reel 3"`.

| effect | options |
|---|---|
| `glass-widgets` | `text`, `sub`, `name`, `handle`, `top`, `bars`, `day`, `date`, `event` |
| `documentary` | `text` (one line per item), `hl` (word shown in red), `name`, `handle`, `tag`, `wall` |
| `orbit` | `count`, `images` (folder; defaults to `reels_folder` or stills from your clip) |
| `chart-split` | `title`, `labels`, `vals` |
| `spotlight`, `backdrop-word`, `lean-in`, `led-sign`, `reject-stamp`, `tape-label`, `locked-on` | `text` (`backdrop-word` also `color` as `r,g,b`) |
| `checklist` | `text` (items as `step::detail`), `look` (`light` or `dark`) |
| `timeline` | `text`, `sub` |
| `countdown-flip` | `seq` (default `3\|2\|1`), `text` (last card) |
| `huge-strike` | `text`, `sub` |
| `messages` | `text` (one item per message), `from` |
| `moody`, `slow-push` | – |

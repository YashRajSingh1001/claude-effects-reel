# Credits

`fx_engine.py` is a modified copy of `scripts/fx.py` from
[Vibha-Ramprakash/claude-video-effects](https://github.com/Vibha-Ramprakash/claude-video-effects) by @vibha.in.progress,
MIT licence. The fonts and face/person models are loaded from that repo at runtime (setup.sh clones it); their
licences are in its `fonts/` and `models/` folders.

Changes in this copy: added the `documentary` and `kallaway-split` effects, a `look=dark` checklist card,
a `guard=0` option (lets below-the-chin panels sit in front of hands/mic), and data options on `glass-widgets`
(`top`, `bars`). `reel.py`, `audio.py` and `make_reel.py` are new.

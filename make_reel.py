#!/usr/bin/env python3
"""One command: talking-head clip -> 'Claude chat types /effects X -> edit reveals' reel with music + UI sounds.

usage:
  python make_reel.py <video> --config reel.json [--out reel.mp4] [--check]

  --check   only render one still per effect (fast) into <workdir>/check_*.png, then stop
Run it with the kit's Python: .venv/bin/python (setup.sh prepares it).
"""
import argparse, glob, json, os, shutil, subprocess, sys
import cv2

KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
from fx_engine import EFFECTS, FONTS
PY = sys.executable
WIN0, WIN_LEN, WIN_GAP = 0.3, 3.4, 3.7          # effect windows on the source clip: start, length, spacing

CARD_FX = ('orbit',)


def run(cmd, **kw):
    print('$', ' '.join(str(c) for c in cmd[:6]), '...', flush=True)
    subprocess.run(cmd, check=True, **kw)


def prep_reels(folder, out, crop_instagram):
    """Copy reel screenshots/covers; optionally crop away the Instagram UI from full-screen phone screenshots."""
    from PIL import Image
    os.makedirs(out, exist_ok=True); n = 0
    for p in sorted(glob.glob(os.path.join(folder, '*'))):
        if p.lower().rsplit('.', 1)[-1] not in ('png', 'jpg', 'jpeg', 'webp'): continue
        im = Image.open(p).convert('RGB')
        if crop_instagram and im.height > im.width * 1.9:      # a phone screenshot of a reel
            w, h = im.size; im = im.crop((int(w * 0.083), int(h * 0.076), int(w * 0.80), int(h * 0.664)))
        im.save(os.path.join(out, f'{n:02d}.jpg'), quality=92); n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('video'); ap.add_argument('--config', required=True); ap.add_argument('--out')
    ap.add_argument('--workdir'); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    cfg = json.load(open(a.config, encoding='utf-8')); fx = cfg['effects']
    if not 1 <= len(fx) <= 11: sys.exit('Use between 1 and 11 effects.')
    base = os.path.splitext(os.path.abspath(a.video))[0]
    wd = os.path.abspath(a.workdir or base + '_reel_work'); os.makedirs(wd, exist_ok=True)
    out = os.path.abspath(a.out or base + '_claude_reel.mp4')
    engine_py = os.path.join(KIT, 'fx_engine.py')
    bad = [e['fx'] for e in fx if e['fx'] not in EFFECTS]
    if bad: sys.exit(f"Unknown effect(s): {', '.join(bad)}. See: python fx_engine.py --list")
    if not os.path.exists(os.path.join(FONTS, 'Inter.ttf')): sys.exit('Fonts missing. Run setup.sh first.')

    # 1. silent working clip, long enough for every effect window
    need = WIN0 + WIN_GAP * (len(fx) - 1) + WIN_LEN + 0.6
    cap = cv2.VideoCapture(a.video); dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30); cap.release()
    start = float(cfg.get('clip_start', 0))
    if dur - start < need: sys.exit(f'Clip too short: need {need:.1f}s from {start}s for {len(fx)} effects, have {dur - start:.1f}s.')
    clip = os.path.join(wd, 'clip.mp4')
    run(['ffmpeg', '-v', 'error', '-y', '-ss', str(start), '-i', a.video, '-t', f'{need:.2f}', '-an', '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920',
         '-r', '30', '-c:v', 'libx264', '-crf', '16', '-preset', 'fast', '-pix_fmt', 'yuv420p', clip])

    # 2. reel screenshots for card effects (orbit etc.)
    reels = None
    if cfg.get('reels_folder'):
        reels = os.path.join(wd, 'reels')
        if prep_reels(os.path.expanduser(cfg['reels_folder']), reels, cfg.get('crop_instagram', True)) == 0: reels = None

    # 3. plan: evenly spaced windows
    plan = []
    for i, e in enumerate(fx):
        d = dict(e); d['start'] = round(WIN0 + WIN_GAP * i, 2); d['end'] = round(d['start'] + WIN_LEN, 2)
        if d['fx'] in CARD_FX and reels and 'images' not in d: d['images'] = reels
        d.setdefault('desc', EFFECTS[d['fx']][1])
        plan.append(d)
    json.dump({'effects': plan}, open(os.path.join(wd, 'plan.json'), 'w'), indent=1)
    json.dump(dict(cfg, fx_total=len(EFFECTS)), open(os.path.join(wd, 'config.json'), 'w'), indent=1)

    # 4. effects
    if a.check:
        stills = ','.join(f"{p['start'] + 2.2:.2f}" for p in plan)
        run([PY, engine_py, '--plan', os.path.join(wd, 'plan.json'), clip, os.path.join(wd, 'check.png'), '--still', stills])
        env = dict(os.environ, FX_FONTS=FONTS)
        run([PY, os.path.join(KIT, 'reel.py'), 'preview', wd], env=env)
        print('CHECK_READY', wd); return
    run([PY, engine_py, '--plan', os.path.join(wd, 'plan.json'), clip, os.path.join(wd, 'effects.mp4')])

    # 5. chat screens + reveals, 6. soundtrack, 7. mux
    env = dict(os.environ, FX_FONTS=FONTS)
    run([PY, os.path.join(KIT, 'reel.py'), wd], env=env)
    run([PY, os.path.join(KIT, 'audio.py'), wd])
    run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(wd, 'reel_video.mp4'), '-i', os.path.join(wd, 'soundtrack.wav'), '-map', '0:v', '-map', '1:a',
         '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out])
    print('REEL_READY', out)


if __name__ == '__main__':
    main()

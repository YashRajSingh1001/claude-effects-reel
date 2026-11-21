#!/usr/bin/env python3
"""One command: talking-head clip -> 'Claude chat types /effects X -> edit reveals' reel with music + UI sounds.

usage:
  python make_reel.py <video> --config reel.json [--out reel.mp4] [--check]

  --check   only render one still per effect (fast) into <workdir>/check_*.png, then stop
Run it with the effects engine's Python: ~/claude-video-effects/.venv/bin/python (setup.sh prepares it).
"""
import argparse, glob, json, os, shutil, subprocess, sys

KIT = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.environ.get('FX_ENGINE', os.path.expanduser('~/claude-video-effects'))
PY = sys.executable
WIN0, WIN_LEN, WIN_GAP = 0.3, 3.4, 3.7          # effect windows on the source clip: start, length, spacing

# Short one-liners shown under the effect name in the slash menu.
DESC = {
    'noise': 'reels pile up behind your head', 'lineup': 'numbered tiles fan out above you', 'locked-on': 'brackets lock onto your face',
    'orbit': 'your reels circle your head', 'lean-in': 'a punch-in on one word', 'backdrop-word': 'a giant word behind you',
    'spotlight': 'kill the lights, keep you lit', 'the-bill': 'your prompt prints like a receipt', 'moody': 'a moody colour grade',
    'swipe': 'a before and after slider', 'todo': 'a checklist that ticks as you talk', 'comment-box': 'a comment types itself and posts',
    'tap': 'Follow flips to Following', 'pause-point': 'freeze frame with an arrow', 'uninstall': 'a glitchy uninstall bar',
    'reel-frame': 'your video shrinks into a reel card', 'shortcut-rain': 'keyboard keys rain behind you', 'reject-stamp': 'a big red stamp slams down',
    'countdown-flip': 'a 3, 2, 1 flip clock', 'rabbit-hole': 'the room tunnels away', 'cover-star': 'you become a magazine cover',
    'scribble': 'marker doodles draw around you', 'glass-widgets': 'frosted glass widgets around your head', 'red-collage': 'black and white you, a red word behind',
    'split-headline': 'a headline card pushes you down', 'pastel-word': 'lavender room, a giant word behind', 'check-pills': 'grid paper, pills get clicked',
    'timeline': 'a live editing timeline', 'headline-box': 'a punch-in with a headline', 'profile-wall': 'your grid fills the wall',
    'tier-list': 'a tier list drops in', 'broll-split': 'b-roll on top, you below', 'phone-fan': 'your reels fan out like phones',
    'dot-reveal': 'you build out of glowing dots', 'headline-wall': 'your headlines pile up behind you', 'checklist': 'Claude ticks off every step',
    'liquid-glass-graph': 'a glass card with a climbing graph', 'carousel-spin': 'your reels spin around you', 'match-cut': 'news pages cut on one word',
    'apple-toggles': 'iPhone switches flip on', 'led-sign': 'a glowing LED sign types out', 'slow-push': 'a slow cinematic push-in',
    'over-the-shoulder-zoom': 'corner zooms with glass graphs', 'messages': 'iMessage pop-ups stack up', 'place-in-grid': 'you land in your 3x3 grid',
    'tape-label': 'yellow tape lands on your chest', 'select-resize': 'a cursor drags your number bigger', 'wave-trim': 'silences trim away on screen',
    'huge-strike': 'a huge word gets crossed out', 'crayon-write': 'a red crayon writes your word', 'fan-build': 'covers deal into a fan',
    'documentary': 'black and white you, stamped words', 'kallaway-split': 'a live chart on top, you below',
}
CARD_FX = ('fan-build', 'noise', 'orbit', 'carousel-spin', 'place-in-grid', 'check-pills', 'profile-wall', 'phone-fan', 'broll-split')


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
    cfg = json.load(open(a.config)); fx = cfg['effects']
    if not 1 <= len(fx) <= 11: sys.exit('Use between 1 and 11 effects.')
    base = os.path.splitext(os.path.abspath(a.video))[0]
    wd = os.path.abspath(a.workdir or base + '_reel_work'); os.makedirs(wd, exist_ok=True)
    out = os.path.abspath(a.out or base + '_claude_reel.mp4')
    engine_py = os.path.join(ENGINE, 'scripts', 'fx_engine.py')
    if not os.path.exists(engine_py): sys.exit(f'Engine not found at {engine_py}. Run setup.sh first.')

    # 1. silent working clip, long enough for every effect window
    need = WIN0 + WIN_GAP * (len(fx) - 1) + WIN_LEN + 0.6
    dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', a.video], capture_output=True, text=True).stdout)
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
        d.setdefault('desc', DESC.get(d['fx'], 'video effect'))
        plan.append(d)
    json.dump({'effects': plan}, open(os.path.join(wd, 'plan.json'), 'w'), indent=1)
    json.dump(cfg, open(os.path.join(wd, 'config.json'), 'w'), indent=1)

    # 4. effects
    if a.check:
        stills = ','.join(f"{p['start'] + 2.2:.2f}" for p in plan)
        run([PY, engine_py, '--plan', os.path.join(wd, 'plan.json'), clip, os.path.join(wd, 'check.png'), '--still', stills])
        env = dict(os.environ, FX_FONTS=os.path.join(ENGINE, 'fonts'))
        run([PY, os.path.join(KIT, 'reel.py'), 'preview', wd], env=env)
        print('CHECK_READY', wd); return
    run([PY, engine_py, '--plan', os.path.join(wd, 'plan.json'), clip, os.path.join(wd, 'effects.mp4')])

    # 5. chat screens + reveals, 6. soundtrack, 7. mux
    env = dict(os.environ, FX_FONTS=os.path.join(ENGINE, 'fonts'))
    run([PY, os.path.join(KIT, 'reel.py'), wd], env=env)
    run([PY, os.path.join(KIT, 'audio.py'), wd])
    run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(wd, 'reel_video.mp4'), '-i', os.path.join(wd, 'soundtrack.wav'), '-map', '0:v', '-map', '1:a',
         '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', out])
    print('REEL_READY', out)


if __name__ == '__main__':
    main()

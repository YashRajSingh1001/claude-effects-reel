#!/usr/bin/env python3
"""Builds the 'Claude chat -> effect' reel: typing screens, dot-reveal card, zoom to full screen, end card.
usage: python reel.py <workdir>   (reads workdir/plan.json, workdir/effects.mp4, workdir/clip.mp4, workdir/config.json)
Writes workdir/reel_video.mp4 (silent) and workdir/events.json (sound-design cue times)."""
import json, math, os, random, subprocess, sys
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
FX = os.environ.get('FX_FONTS', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')) + '/'
BG, PANEL, KBBG, KEY, KEYD = (37, 37, 34), (48, 48, 45), (27, 27, 25), (70, 69, 65), (48, 47, 44)
ORANGE, GREY, WHITE = (217, 119, 87), (160, 158, 150), (240, 238, 232)
BUBBLE, BUBBLE_T = (64, 40, 32), (236, 132, 100)

_fc = {}
def F(kind, size):
    k = (kind, size)
    if k not in _fc:
        path = {'ui': 'Inter.ttf', 'mono': 'SpaceMono-Bold.ttf', 'serif': 'PlayfairDisplay.ttf'}[kind]
        f = ImageFont.truetype(FX + path, size)
        if kind == 'ui':
            pass
        _fc[k] = f
    return _fc[k]
def FW(size, wght):
    k = ('uiw', size, wght)
    if k not in _fc:
        f = ImageFont.truetype(FX + 'Inter.ttf', size)
        try: f.set_variation_by_axes([min(32, max(14, size)), wght])
        except Exception:
            try: f.set_variation_by_axes([wght])
            except Exception: pass
        _fc[k] = f
    return _fc[k]
def FS(size):
    k = ('serif', size)
    if k not in _fc:
        f = ImageFont.truetype(FX + 'PlayfairDisplay.ttf', size)
        try: f.set_variation_by_axes([420])
        except Exception: pass
        _fc[k] = f
    return _fc[k]

def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return 3 * x * x - 2 * x * x * x
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3

# ---------- plan ----------
WD = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == 'preview' else (sys.argv[1] if len(sys.argv) > 1 else '.')
J = lambda n: os.path.join(WD, n)
CFG = json.load(open(J('config.json'))) if os.path.exists(J('config.json')) else {}
plan = json.load(open(J('plan.json')))['effects'] if os.path.exists(J('plan.json')) else []
NAME = CFG.get('name', 'there'); HANDLE = CFG.get('handle', ''); NFX = len(plan)
DESC = {e['fx']: e.get('desc', '') for e in plan}
MENU_SUB = CFG.get('menu_sub', '51 video effects for your clips')
GREETING = CFG.get('greeting', f'Evening, {NAME}')
COMMENT_WORD = CFG.get('comment_word', 'claude')
REPLY = CFG.get('reply', f'Comment \u201c{COMMENT_WORD}\u201d and I\u2019ll send you all {NFX} effects')
END_TITLE = CFG.get('end_title', f'Comment \u201c{COMMENT_WORD}\u201d')
END_PILL = CFG.get('end_pill', f'for all {NFX} Claude effects')
END_LINE1 = CFG.get('end_line1', f'One clip. {NFX} edits. Zero editing apps.')
END_LINE2 = CFG.get('end_line2', 'All typed in Claude.')
MORE = CFG.get('more_tile', '+44|more effects|in the repo')
BEAT = 0.50625
T_TYPE, T_CARD, T_FULL = 2 * BEAT, 2 * BEAT, 4 * BEAT
CYCLE = T_TYPE + T_CARD + T_FULL
O_TYPE, O_CARD, O_END = 2 * BEAT, 3 * BEAT, 5 * BEAT
TOTAL = CYCLE * len(plan) + O_TYPE + O_CARD + O_END
events = []
def build_events():
    ev = []
    for ci, e in enumerate(plan):
        b = ci * CYCLE
        ev += [{'t': t, 'kind': 'key'} for t in key_times(e['fx'], b)]
        ev += [{'t': b + T_TYPE, 'kind': 'send'}, {'t': b + T_TYPE, 'kind': 'riser', 'd': T_CARD},
               {'t': b + T_TYPE + 0.72 * T_CARD, 'kind': 'whoosh'}, {'t': b + T_TYPE + T_CARD, 'kind': 'impact'}]
    O0 = CYCLE * len(plan); a, z = 0.18, O_TYPE - 0.2; nw = len(COMMENT_WORD)
    ev += [{'t': O0 + a + j * (z - a) / nw, 'kind': 'key'} for j in range(nw)]
    ev += [{'t': O0 + O_TYPE, 'kind': 'send'}, {'t': O0 + O_TYPE + 0.35, 'kind': 'riser', 'd': O_CARD - 0.35},
           {'t': O0 + O_TYPE + 0.74 * O_CARD, 'kind': 'whoosh'}, {'t': O0 + O_TYPE + O_CARD, 'kind': 'impact'}]
    sec = []   # music: 0 = muffled (typing), ramps during the card, 1 = open (reveal)
    for ci in range(len(plan)):
        b = ci * CYCLE; sec += [[b, b + T_TYPE, 0, 0], [b + T_TYPE, b + T_TYPE + T_CARD, 0, 0.55], [b + T_TYPE + T_CARD, b + CYCLE, 1, 1]]
    sec += [[O0, O0 + O_TYPE, 0, 0], [O0 + O_TYPE, O0 + O_TYPE + O_CARD, 0, 0.55], [O0 + O_TYPE + O_CARD, TOTAL + 0.3, 1, 1]]
    return sorted(ev, key=lambda x: x['t']), sec

# ---------- source frames ----------
def frame_at(path, t):
    out = subprocess.run(['ffmpeg', '-v', 'error', '-ss', f'{t:.3f}', '-i', path, '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True, check=True).stdout
    return Image.open(__import__('io').BytesIO(out)).convert('RGB')

class Reader:
    """Sequential reader of the effects video; get(t) returns the frame at time t (t must not go backwards)."""
    def __init__(self, path):
        self.p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE, bufsize=10 ** 8)
        self.i = -1; self.cur = None
    def get(self, t):
        want = int(round(t * FPS))
        while self.i < want:
            b = self.p.stdout.read(W * H * 3)
            if len(b) < W * H * 3: break
            self.cur = np.frombuffer(b, np.uint8).reshape(H, W, 3); self.i += 1
        return self.cur

thumb_src = frame_at(J('clip.mp4'), 1.0) if os.path.exists(J('clip.mp4')) else Image.new('RGB', (540, 960), (90, 90, 90))

def rounded(im, r):
    im = im.convert('RGBA'); m = Image.new('L', im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], r, fill=255); im.putalpha(m); return im

def cover(im, w, h):
    s = max(w / im.width, h / im.height); im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2; return im.crop((l, t, l + w, t + h))

THUMB_IN = rounded(cover(thumb_src, 120, 170), 14)
THUMB_MSG = rounded(cover(thumb_src, 108, 178), 14)

# ---------- drawing pieces ----------
def asterisk(d, cx, cy, r, col=ORANGE, w=None):
    w = w or max(3, int(r * 0.28))
    for k in range(10):
        a = k * math.pi / 5 + 0.2
        rr = r * (1.0 if k % 2 == 0 else 0.82)
        d.line([(cx + r * 0.18 * math.cos(a), cy + r * 0.18 * math.sin(a)), (cx + rr * math.cos(a), cy + rr * math.sin(a))], fill=col, width=w)
    d.ellipse([cx - r * 0.22, cy - r * 0.22, cx + r * 0.22, cy + r * 0.22], fill=col)

def top_bar(im):
    d = ImageDraw.Draw(im)
    d.ellipse([60, 96, 116, 152], fill=(44, 44, 41))
    for dy in (-6, 6): d.line([(77, 124 + dy), (99, 124 + dy)], fill=WHITE, width=3)
    d.ellipse([964, 96, 1020, 152], fill=(44, 44, 41))
    d.rounded_rectangle([980, 112, 1004, 136], 4, outline=WHITE, width=3); d.line([(990, 126), (1006, 110)], fill=WHITE, width=3)
    d.rounded_rectangle([372, 92, 708, 156], 32, fill=(52, 51, 48))
    d.rounded_rectangle([540, 98, 702, 150], 26, fill=(78, 76, 71))
    d.text((456, 124), 'Chat', font=FW(37, 500), fill=GREY, anchor='mm')
    d.text((621, 124), 'Code', font=FW(37, 650), fill=WHITE, anchor='mm')

def send_btn(d, cx, cy, active=True):
    d.rounded_rectangle([cx - 46, cy - 40, cx + 46, cy + 40], 22, fill=ORANGE if active else (90, 88, 82))
    d.line([(cx, cy + 18), (cx, cy - 18)], fill=WHITE, width=5); d.line([(cx - 14, cy - 4), (cx, cy - 18), (cx + 14, cy - 4)], fill=WHITE, width=5, joint='curve')

def mic(d, cx, cy, col=GREY):
    d.rounded_rectangle([cx - 8, cy - 18, cx + 8, cy + 6], 8, outline=col, width=3)
    d.arc([cx - 14, cy - 10, cx + 14, cy + 14], 0, 180, fill=col, width=3); d.line([(cx, cy + 14), (cx, cy + 20)], fill=col, width=3)

def plus_sliders(d, x, y):
    d.line([(x - 12, y), (x + 12, y)], fill=GREY, width=3); d.line([(x, y - 12), (x, y + 12)], fill=GREY, width=3)
    for k, (yy, kx) in enumerate(((y - 7, x + 62), (y + 7, x + 54))):
        d.line([(x + 40, yy), (x + 76, yy)], fill=GREY, width=3); d.ellipse([kx - 5, yy - 5, kx + 5, yy + 5], fill=BG, outline=GREY, width=3)

ROWS = ['qwertyuiop', 'asdfghjkl', 'zxcvbnm']
KW, KH, KG = 94, 112, 11
def key_rects():
    r = {}
    y0 = 1356
    for ri, row in enumerate(ROWS):
        n = len(row); tot = n * KW + (n - 1) * KG; x0 = (W - tot) / 2
        if ri == 2: x0 = (W - tot) / 2
        for k, ch in enumerate(row): r[ch] = (x0 + k * (KW + KG), y0 + ri * (KH + 26))
    return r
KR = key_rects()

def keyboard(im, typed_word, pressed=None):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 1240, W, H], fill=KBBG)
    if typed_word: d.text((126, 1287), f'“{typed_word}”', font=FW(34, 500), fill=WHITE, anchor='lm')
    for ch, (x, y) in KR.items():
        d.rounded_rectangle([x, y, x + KW, y + KH], 14, fill=KEY)
        d.text((x + KW / 2, y + KH / 2 - 4), ch, font=FW(52, 420), fill=WHITE, anchor='mm')
    yb = 1356 + 2 * (KH + 26)
    for x0, x1, kind in ((14, 132, 'shift'), (W - 132, W - 14, 'del')):
        d.rounded_rectangle([x0, yb, x1, yb + KH], 14, fill=KEYD); cx, cy = (x0 + x1) / 2, yb + KH / 2
        if kind == 'shift': d.polygon([(cx, cy - 20), (cx - 20, cy + 2), (cx - 9, cy + 2), (cx - 9, cy + 18), (cx + 9, cy + 18), (cx + 9, cy + 2), (cx + 20, cy + 2)], outline=WHITE, width=3)
        else:
            d.polygon([(cx - 30, cy), (cx - 14, cy - 18), (cx + 26, cy - 18), (cx + 26, cy + 18), (cx - 14, cy + 18)], outline=WHITE, width=3)
            d.line([(cx - 2, cy - 8), (cx + 14, cy + 8)], fill=WHITE, width=3); d.line([(cx + 14, cy - 8), (cx - 2, cy + 8)], fill=WHITE, width=3)
    yb2 = yb + KH + 26
    for x0, x1, lab in ((62, 202, '123'), (213, 538, 'space'), (549, 686, '/')):
        d.rounded_rectangle([x0, yb2, x1, yb2 + KH], 14, fill=KEY if lab != '123' else KEYD)
        d.text(((x0 + x1) / 2, yb2 + KH / 2), lab, font=FW(38 if lab != '/' else 46, 420), fill=WHITE, anchor='mm')
    if pressed == '/':
        x0, x1 = 549, 686; d.rounded_rectangle([x0 + 20, yb2 - 120, x1 - 20, yb2 + KH], 18, fill=(98, 96, 90))
        d.text(((x0 + x1) / 2, yb2 - 50), '/', font=FW(72, 420), fill=WHITE, anchor='mm')
    elif pressed and pressed in KR:
        x, y = KR[pressed]
        d.rounded_rectangle([x - 18, y - 136, x + KW + 18, y + KH], 20, fill=(98, 96, 90))
        d.text((x + KW / 2, y - 62), pressed, font=FW(80, 420), fill=WHITE, anchor='mm')

def input_box(im, text, top, with_thumb=True, cursor_on=True, orange_cmd=False):
    d = ImageDraw.Draw(im)
    h = 400 if with_thumb else 212
    d.rounded_rectangle([32, top, W - 32, top + h], 34, fill=PANEL)
    ty = top + 128 + (172 if with_thumb else 0) - 128
    if with_thumb:
        im.alpha_composite(THUMB_IN, (62, top + 24))
        d = ImageDraw.Draw(im); d.ellipse([162, top + 16, 190, top + 44], fill=WHITE); d.line([(170, top + 24), (182, top + 36)], fill=(30, 30, 30), width=3); d.line([(182, top + 24), (170, top + 36)], fill=(30, 30, 30), width=3)
        ty = top + 236
    else:
        ty = top + 64
    f = FW(48, 450)
    if text:
        col = BUBBLE_T if orange_cmd else WHITE
        d.text((60, ty), text, font=f, fill=col, anchor='lm')
        if cursor_on: x = 62 + f.getlength(text); d.line([(x, ty - 28), (x, ty + 28)], fill=ORANGE, width=4)
    else:
        if cursor_on: d.line([(62, ty - 28), (62, ty + 28)], fill=ORANGE, width=4)
        d.text((74, ty), 'Reply to Claude...', font=f, fill=(120, 118, 110), anchor='lm')
    by = top + h - 62
    plus_sliders(d, 80, by); mic(d, W - 186, by); send_btn(d, W - 96, by, True)

def menu(im, items, bottom):
    d = ImageDraw.Draw(im)
    ih = 128; h = ih * len(items) + 16; top = bottom - h
    d.rounded_rectangle([32, top, W - 32, bottom], 28, fill=PANEL)
    for k, (t, s) in enumerate(items):
        y = top + 8 + k * ih
        if k == 0 and len(items) == 1: d.rounded_rectangle([44, y + 6, W - 44, y + ih - 6], 20, fill=(58, 58, 54))
        d.text((70, y + 46), t, font=FW(44, 600), fill=WHITE, anchor='lm')
        d.text((70, y + 92), s, font=FW(32, 420), fill=GREY, anchor='lm')

def bottom_reply(im):
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([32, 1770, W - 32, 1876], 53, fill=PANEL)
    d.line([(64, 1823), (88, 1823)], fill=GREY, width=3); d.line([(76, 1811), (76, 1835)], fill=GREY, width=3)
    d.text((112, 1823), 'Reply to Claude...', font=FW(42, 420), fill=(150, 148, 140), anchor='lm')
    mic(d, W - 186, 1823)
    d.ellipse([W - 130, 1783, W - 50, 1863], fill=(64, 63, 59)); d.line([(W - 90, 1838), (W - 90, 1808)], fill=WHITE, width=4); d.line([(W - 102, 1820), (W - 90, 1808), (W - 78, 1820)], fill=WHITE, width=4)

# ---------- dot reveal ----------
CARD = (37, 551, 676, 1691)
rng = np.random.default_rng(7)
def dot_card(src_rgb, prog, w, h, seed=0):
    """prog 0..1: 0-0.3 sparse orange dots, 0.3-0.6 halftone of the image, 0.6-1 crossfade to the real frame."""
    cell = 15; cols, rows = w // cell + 1, h // cell + 1
    small = cv2.resize(src_rgb, (cols, rows), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    lum = small @ np.float32([0.299, 0.587, 0.114])
    im = Image.new('RGB', (w, h), (22, 21, 20)); d = ImageDraw.Draw(im)
    r_ = np.random.default_rng(seed + int(prog * 40))
    rnd = r_.random((rows, cols))
    p1 = clamp(prog / 0.3); p2 = clamp((prog - 0.3) / 0.3)
    warm = np.float32([0.98, 0.55, 0.32])
    for yy in range(rows):
        for xx in range(cols):
            if p2 <= 0:
                if rnd[yy, xx] > 0.25 + 0.55 * p1: continue
                b = 0.35 + 0.65 * rnd[yy, xx]; rad = cell * 0.22; col = tuple(int(255 * b * c) for c in warm)
            else:
                L = lum[yy, xx]; rad = cell * (0.18 + 0.32 * (0.35 + 0.65 * L) * (0.6 + 0.4 * p2))
                c = small[yy, xx] * p2 * 0.8 + warm * L * (1 - p2 * 0.8) + warm * 0.12
                col = tuple(int(255 * clamp(v)) for v in c)
            cx, cy = xx * cell + cell / 2, yy * cell + cell / 2
            d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=col)
    p3 = clamp((prog - 0.6) / 0.4)
    if p3 > 0:
        real = Image.fromarray(cv2.resize(src_rgb, (w, h), interpolation=cv2.INTER_AREA))
        im = Image.blend(im, real, ease(p3))
    return im

def card_src(frame):
    """Crop a full 9:16 frame to the card's aspect (same aspect, just resize)."""
    return frame

# ---------- screens ----------
def chat_screen(name, show_card=None, card_rect=None, card_r=30, typing_line=None):
    im = Image.new('RGBA', (W, H), BG + (255,)); top_bar(im); d = ImageDraw.Draw(im)
    im.alpha_composite(THUMB_MSG, (W - 54 - THUMB_MSG.width, 200))
    msg = f'/effects {name}'; f = FW(39, 480); tw = f.getlength(msg)
    d.rounded_rectangle([W - 54 - tw - 44, 398, W - 54, 466], 34, fill=BUBBLE); d.text((W - 54 - 22, 432), msg, font=f, fill=BUBBLE_T, anchor='rm')
    asterisk(d, 78, 512, 18)
    d.text((114, 512), typing_line if typing_line is not None else f'Editing with {name}...', font=FW(35, 450), fill=(205, 203, 196), anchor='lm')
    d.text((W - 54, 512), 'SPED UP', font=F('mono', 22), fill=(130, 128, 120), anchor='rm')
    bottom_reply(im)
    if show_card is not None:
        x0, y0, x1, y1 = card_rect; w, h = int(x1 - x0), int(y1 - y0)
        c = show_card.resize((w, h), Image.LANCZOS) if show_card.size != (w, h) else show_card
        im.alpha_composite(rounded(c, int(card_r)), (int(x0), int(y0)))
    return im

def type_states(name, t):
    """Typing timeline within T_TYPE. Returns (text, menu_items, pressed_key, orange)."""
    keys = [('/', 0.06), ('e', 0.16), ('f', 0.26)]
    auto_t = 0.36
    n = len(name); name_t0, name_t1 = 0.42, T_TYPE - 0.16
    pressed = None
    for ch, kt in keys:
        if kt <= t < kt + 0.09: pressed = ch
    if t < keys[0][1]: return '', None, pressed, False
    if t < keys[1][1]: return '/', [('/effects', MENU_SUB), ('/init', 'set up Claude in this folder'), ('/review', 'review my latest changes')], pressed, False
    if t < keys[2][1]: return '/e', [('/effects', MENU_SUB)], pressed, False
    if t < auto_t: return '/ef', [('/effects', MENU_SUB)], pressed, False
    if t < name_t0: return '/effects ', [('/effects', MENU_SUB)], None, True
    k = min(n, int((t - name_t0) / (name_t1 - name_t0) * n) + 1)
    kt = name_t0 + (k - 1) * (name_t1 - name_t0) / n
    ch = name[k - 1]
    if t - kt < 0.07 and ch.isalpha(): pressed = ch
    return '/effects ' + name[:k], [(name, DESC.get(name, ''))], pressed, True

def typing_screen(name, t):
    im = Image.new('RGBA', (W, H), BG + (255,)); top_bar(im)
    text, items, pressed, orange = type_states(name, t)
    word = text.split(' ')[-1].lstrip('/') if text else ''
    input_box(im, text, 814, True, int(t * 4) % 2 == 0 or bool(text), orange)
    if items: menu(im, items, 798)
    keyboard(im, word, pressed)
    return im

def key_times(name, t0):
    ts = [t0 + 0.06, t0 + 0.16, t0 + 0.26, t0 + 0.36]
    n = len(name); a, b = 0.42, T_TYPE - 0.16
    ts += [t0 + a + i * (b - a) / n for i in range(n)]
    return ts

# ---------- end card ----------
def end_card(tiles):
    im = Image.new('RGBA', (W, H), (34, 32, 30, 255)); d = ImageDraw.Draw(im)
    ft = FW(98, 800); size = 98
    while ft.getlength(END_TITLE) > W - 80 and size > 50: size -= 4; ft = FW(size, 800)
    d.text((W / 2, 196), END_TITLE, font=ft, fill=WHITE, anchor='mm')
    pt = END_PILL; f = FW(44, 700); tw = f.getlength(pt)
    d.rounded_rectangle([W / 2 - tw / 2 - 30, 268, W / 2 + tw / 2 + 30, 340], 12, fill=(229, 108, 74)); d.text((W / 2, 304), pt, font=f, fill=(40, 18, 10), anchor='mm')
    ntile = len(tiles) + 1; cols = 4 if ntile > 4 else ntile; rows = math.ceil(ntile / cols)
    tw_, gap = (236 if cols == 4 else 300), 14; th_ = int(tw_ * 1.78)
    if rows >= 3: tw_ = 200; th_ = int(tw_ * 1.78)
    x0 = (W - cols * tw_ - (cols - 1) * gap) / 2; y0 = 400
    for i in range(ntile):
        x = x0 + (i % cols) * (tw_ + gap); y = y0 + (i // cols) * (th_ + gap)
        if i < len(tiles):
            name, img = tiles[i]; t = cover(img, tw_, th_).convert('RGBA')
            grad = Image.new('L', (1, th_)); [grad.putpixel((0, k), int(200 * clamp((k - th_ * 0.7) / (th_ * 0.3)))) for k in range(th_)]
            shade = Image.new('RGBA', (tw_, th_), (0, 0, 0, 255)); shade.putalpha(grad.resize((tw_, th_))); t.alpha_composite(shade)
            td = ImageDraw.Draw(t); td.ellipse([10, 10, 50, 50], fill=(229, 108, 74)); td.text((30, 30), str(i + 1), font=FW(26, 800), fill=(40, 18, 10), anchor='mm')
            td.text((12, th_ - 22), f'/{name}', font=F('mono', 20), fill=WHITE, anchor='lm')
            im.alpha_composite(rounded(t, 14), (int(x), int(y)))
            ImageDraw.Draw(im).rounded_rectangle([x, y, x + tw_, y + th_], 14, outline=(80, 78, 72), width=2)
        else:
            d = ImageDraw.Draw(im); d.rounded_rectangle([x, y, x + tw_, y + th_], 14, fill=(48, 45, 42), outline=(80, 78, 72), width=2)
            m = (MORE.split('|') + ['', '', ''])[:3]
            d.text((x + tw_ / 2, y + th_ / 2 - 24), m[0], font=FW(72 if tw_ > 210 else 60, 800), fill=(236, 132, 100), anchor='mm')
            d.text((x + tw_ / 2, y + th_ / 2 + 40), m[1], font=FW(30, 500), fill=WHITE, anchor='mm')
            d.text((x + tw_ / 2, y + th_ / 2 + 80), m[2], font=FW(30, 500), fill=GREY, anchor='mm')
    d = ImageDraw.Draw(im); yl = y0 + rows * (th_ + gap) + 80
    d.text((W / 2, yl), END_LINE1, font=FW(44, 600), fill=WHITE, anchor='mm')
    d.text((W / 2, yl + 66), END_LINE2, font=FS(52), fill=(236, 132, 100), anchor='mm')
    d.text((W / 2, 1800), HANDLE, font=FW(38, 600), fill=GREY, anchor='mm')
    return im

def home_screen(text, t, pressed):
    im = Image.new('RGBA', (W, H), BG + (255,)); top_bar(im); d = ImageDraw.Draw(im)
    asterisk(d, W / 2, 488, 44)
    d.text((W / 2, 612), GREETING, font=FS(84), fill=WHITE, anchor='mm')
    input_box(im, text, 1004, False, int(t * 4) % 2 == 0 or bool(text), False)
    keyboard(im, text, pressed)
    return im

def reply_screen(reply_txt, card=None, card_rect=None, card_r=30):
    im = Image.new('RGBA', (W, H), BG + (255,)); top_bar(im); d = ImageDraw.Draw(im)
    f = FW(39, 480); tw = f.getlength(COMMENT_WORD)
    d.rounded_rectangle([W - 54 - tw - 44, 200, W - 54, 268], 34, fill=(60, 59, 55)); d.text((W - 76, 234), COMMENT_WORD, font=f, fill=WHITE, anchor='rm')
    asterisk(d, 78, 330, 18)
    lines = []; cur = ''
    for wd in reply_txt.split(' '):
        if FW(38, 450).getlength(cur + ' ' + wd) > 860 and cur: lines.append(cur); cur = wd
        else: cur = (cur + ' ' + wd).strip()
    if cur: lines.append(cur)
    for k, ln in enumerate(lines): d.text((114, 330 + k * 52), ln, font=FW(38, 450), fill=(225, 223, 216), anchor='lm')
    bottom_reply(im)
    if card is not None:
        x0, y0, x1, y1 = card_rect; w, h = int(x1 - x0), int(y1 - y0)
        im.alpha_composite(rounded(card.resize((w, h), Image.LANCZOS), int(card_r)), (int(x0), int(y0)))
    return im

# ---------- render ----------
def main():
    out = J('reel_video.mp4')
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-c:v', 'libx264', '-crf', '17', '-preset', 'medium', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    rd = Reader(J('effects.mp4'))
    tiles = []
    nframes = int(round(TOTAL * FPS))
    dot_cache = {}
    CARD2 = (190, 520, 890, 1765)   # end-card preview card in the reply screen
    endim = None
    for i in range(nframes):
        T = i / FPS
        ci = int(T // CYCLE)
        if ci < len(plan):
            e = plan[ci]; name = e['fx']; s = e['start']; lt = T - ci * CYCLE
            if lt < T_TYPE:
                im = typing_screen(name, lt).convert('RGB'); arr = np.asarray(im)
            elif lt < T_TYPE + T_CARD:
                q = lt - T_TYPE
                fr = rd.get(s + q)
                exp0 = 0.72 * T_CARD
                prog = clamp(q / exp0 * 1.0)
                card = dot_card(fr, prog, CARD[2] - CARD[0], CARD[3] - CARD[1], seed=ci * 100)
                if q < exp0:
                    im = chat_screen(name, card, CARD)
                else:
                    k = ease((q - exp0) / (T_CARD - exp0))
                    rect = tuple(a + (b - a) * k for a, b in zip(CARD, (0, 0, W, H)))
                    real = Image.fromarray(fr)
                    im = chat_screen(name, real, rect, 30 * (1 - k))
                arr = np.asarray(im.convert('RGB'))
            else:
                q = lt - T_TYPE - T_CARD
                arr = rd.get(s + T_CARD + q)
                if len(tiles) == ci and q >= T_FULL * 0.55: tiles.append((name, Image.fromarray(arr.copy())))
        else:
            lt = T - CYCLE * len(plan)
            if endim is None: endim = end_card(tiles)
            if lt < O_TYPE:
                word = COMMENT_WORD; nw = len(word); a, b = 0.18, O_TYPE - 0.2
                k = 0 if lt < a else min(nw, int((lt - a) / (b - a) * nw) + 1)
                kt = a + (k - 1) * (b - a) / nw; pressed = word[k - 1] if k and lt - kt < 0.07 else None
                arr = np.asarray(home_screen(word[:k], lt, pressed).convert('RGB'))
            elif lt < O_TYPE + O_CARD:
                q = lt - O_TYPE
                reply = REPLY
                nchar = int(len(reply) * clamp(q / 0.45)); txt = reply[:nchar]
                card = None; rect = CARD2; r = 30
                exp0 = O_CARD * 0.74
                if q > 0.35:
                    pc = clamp((q - 0.35) / (exp0 - 0.35))
                    src = np.asarray(endim.convert('RGB'))
                    if q < exp0: card = dot_card(src, pc, CARD2[2] - CARD2[0], CARD2[3] - CARD2[1], seed=999)
                    else:
                        k = ease((q - exp0) / (O_CARD - exp0)); card = endim.convert('RGB'); r = 30 * (1 - k)
                        rect = tuple(a + (b - a) * k for a, b in zip(CARD2, (0, 0, W, H)))
                arr = np.asarray(reply_screen(txt, card, rect, r).convert('RGB'))
            else:
                q = lt - O_TYPE - O_CARD
                arr = np.asarray(endim.convert('RGB'))
        enc.stdin.write(np.ascontiguousarray(arr, dtype=np.uint8).tobytes())
        if i % 150 == 0: print(f'{T:5.1f}s / {TOTAL:.1f}s', flush=True)
    enc.stdin.close(); enc.wait()
    ev, sec = build_events()
    json.dump({'total': TOTAL, 'beat': BEAT, 'events': ev, 'sections': sec}, open(J('events.json'), 'w'), indent=0)
    print('done', out, TOTAL)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'preview':
        n0 = plan[0]['fx'] if plan else 'orbit'
        typing_screen(n0, 0.75).convert('RGB').save(J('ui_typing.png'))
        fr = np.asarray(thumb_src.resize((W, H)))
        chat_screen(n0, dot_card(fr, 0.45, 639, 1140), CARD).convert('RGB').save(J('ui_chat.png'))
        home_screen(COMMENT_WORD[:3], 0.5, None).convert('RGB').save(J('ui_home.png'))
        end_card([(e['fx'], Image.fromarray(fr)) for e in plan]).convert('RGB').save(J('ui_end.png'))
        print('TOTAL', TOTAL)
    else:
        main()

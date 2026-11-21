#!/usr/bin/env python3
import argparse, glob, json, math, os, random, shutil, subprocess, sys, urllib.request
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

USAGE = """Effects engine for claude-effects-reel by Yash Raj Singh (@yashraj.decodes)

  python fx_engine.py --list
  python fx_engine.py --fetch
  python fx_engine.py --plan plan.json in.mp4 out.mp4 [--still 2.5,6.2]
  python fx_engine.py orbit in.mp4 out.mp4 --start 1 --end 4.4 [--opt text=HELLO]
"""

KIT = os.path.dirname(os.path.abspath(__file__))
FONTS = os.environ.get('FX_FONTS', os.path.join(KIT, 'fonts'))
MODELS = os.environ.get('FX_MODELS', os.path.join(KIT, 'models'))
ASSETS = {
    os.path.join(FONTS, 'Inter.ttf'): 'https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf',
    os.path.join(FONTS, 'SpaceMono-Bold.ttf'): 'https://raw.githubusercontent.com/google/fonts/main/ofl/spacemono/SpaceMono-Bold.ttf',
    os.path.join(FONTS, 'PlayfairDisplay.ttf'): 'https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf',
    os.path.join(MODELS, 'face.tflite'): 'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite',
    os.path.join(MODELS, 'person.tflite'): 'https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite',
}

ORANGE, RED, CREAM, INK = (217, 119, 87), (226, 38, 44), (246, 240, 229), (24, 23, 21)


def fetch():
    for path, url in ASSETS.items():
        if os.path.exists(path) and os.path.getsize(path) > 1000: continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print('downloading', os.path.basename(path), flush=True)
        req = urllib.request.Request(url, headers={'User-Agent': 'fx-engine'})
        with urllib.request.urlopen(req, timeout=120) as r, open(path + '.part', 'wb') as f: shutil.copyfileobj(r, f)
        os.replace(path + '.part', path)
    print('ASSETS_READY')


def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return x * x * (3 - 2 * x)
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3
def back_out(x, s=1.6): x = clamp(x) - 1; return 1 + x * x * ((s + 1) * x + s)
def lerp(a, b, k): return a + (b - a) * k


_fonts = {}
def font(kind, size, weight=None):
    size = max(6, int(size)); k = (kind, size, weight)
    if k in _fonts: return _fonts[k]
    file = {'ui': 'Inter.ttf', 'mono': 'SpaceMono-Bold.ttf', 'serif': 'PlayfairDisplay.ttf'}[kind]
    path = os.path.join(FONTS, file)
    try:
        f = ImageFont.truetype(path, size)
        if weight and kind != 'mono':
            for axes in ([min(32, max(14, size)), weight], [weight]):
                try: f.set_variation_by_axes(axes); break
                except Exception: pass
    except OSError:
        f = ImageFont.load_default(size)
    _fonts[k] = f
    return f


def fit_font(kind, text, max_w, start, weight=None, min_size=12):
    s = int(start)
    while s > min_size and font(kind, s, weight).getlength(text) > max_w: s = int(s * 0.94)
    return font(kind, s, weight)


class Tracker:
    def __init__(self):
        self.face = self.seg = None; self.cascade = None
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision
            self.mp = mp
            fp, sp = os.path.join(MODELS, 'face.tflite'), os.path.join(MODELS, 'person.tflite')
            if os.path.exists(fp):
                self.face = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(base_options=BaseOptions(model_asset_path=fp), min_detection_confidence=0.45))
            if os.path.exists(sp):
                self.seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path=sp), output_confidence_masks=True))
        except Exception as ex:
            print('mediapipe unavailable, using fallback tracking:', ex, file=sys.stderr)
        if self.face is None:
            self.cascade = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml'))
        self.last = None

    def reset(self): self.last = None

    def analyse(self, rgb):
        H, W = rgb.shape[:2]; sc = 540 / W
        small = np.ascontiguousarray(cv2.resize(rgb, (540, int(H * sc)), interpolation=cv2.INTER_AREA))
        box = None
        if self.face is not None:
            r = self.face.detect(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=small))
            if r.detections:
                b = max(r.detections, key=lambda d: d.bounding_box.width).bounding_box
                box = ((b.origin_x + b.width / 2) / sc, (b.origin_y + b.height / 2) / sc, b.width / sc)
        elif self.cascade is not None:
            g = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
            fs = self.cascade.detectMultiScale(g, 1.1, 5, minSize=(40, 40))
            if len(fs):
                x, y, w, h = max(fs, key=lambda f: f[2]); box = ((x + w / 2) / sc, (y + h / 2) / sc, w / sc)
        if box is None: box = self.last or (W / 2, H * 0.36, W * 0.3)
        if self.last: box = tuple(lerp(a, b, 0.35) for a, b in zip(self.last, box))
        self.last = box
        if self.seg is not None:
            m = self.seg.segment(self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=small)).confidence_masks[0].numpy_view()
            m = np.squeeze(m).astype(np.float32)
        else:
            m = np.zeros(small.shape[:2], np.float32); fx, fy, fw = (v * sc for v in box)
            cv2.ellipse(m, (int(fx), int(fy)), (int(fw * 0.62), int(fw * 0.85)), 0, 0, 360, 1, -1)
            cv2.ellipse(m, (int(fx), int(fy + fw * 2.4)), (int(fw * 1.5), int(fw * 1.7)), 0, 0, 360, 1, -1)
        m = cv2.GaussianBlur(cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR), (0, 0), 2.2)
        m = np.clip((m - 0.35) / 0.4, 0, 1)
        return box, m


class Ctx:
    def __init__(self, img, t, e, box, mask, thumbs, state):
        self.img = img.astype(np.float32); self.H, self.W = img.shape[:2]
        self.t = t; self.e = e; self.lt = t - e['start']; self.d = max(0.1, e['end'] - e['start'])
        self.p = clamp(self.lt / self.d); self.fx, self.fy, self.fw = box; self.mask = mask
        self.thumbs = thumbs; self.state = state

    def o(self, k, default=''):
        v = self.e.get(k, default); return default if v in (None, '') else v

    @property
    def alpha(self): return clamp(self.lt / 0.22) * clamp((self.d - self.lt) / 0.22)

    def canvas(self): return Image.new('RGBA', (self.W, self.H), (0, 0, 0, 0))

    def guard(self):
        g = self.e.get('guard')
        if g in (None, ''): return not getattr(self, 'below', False)
        return str(g) != '0'

    def comp(self, layer, behind=None, alpha=None):
        a = np.asarray(layer, dtype=np.float32); la = a[..., 3:4] / 255.0 * (self.alpha if alpha is None else alpha)
        if (self.guard() if behind is None else behind): la = la * (1 - self.mask[..., None])
        self.img = self.img * (1 - la) + a[..., :3] * la

    def zone(self, h):
        top = self.fy - self.fw * 0.85
        self.below = top - 70 < h
        if not self.below: return max(110, top - h - 30)
        return clamp(self.fy + self.fw * 1.2, 110, self.H - h - 100)

    def out(self): return np.clip(self.img, 0, 255).astype(np.uint8)


EFFECTS = {}
def effect(name, desc):
    def reg(fn): EFFECTS[name] = (fn, desc); return fn
    return reg


def rounded_mask(w, h, r):
    m = Image.new('L', (max(1, int(w)), max(1, int(h))), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, m.width - 1, m.height - 1], int(r), fill=255); return m


def card(w, h, r, fill, shadow=60):
    pad = 40; im = Image.new('RGBA', (int(w) + pad * 2, int(h) + pad * 2), (0, 0, 0, 0))
    if shadow:
        sh = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle([pad, pad + 12, pad + w, pad + h + 12], r, fill=(0, 0, 0, shadow))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(18)))
    ImageDraw.Draw(im).rounded_rectangle([pad, pad, pad + w, pad + h], r, fill=fill)
    return im, pad


def paste_scaled(dst, im, cx, cy, s=1.0, rot=0.0, alpha=1.0):
    if s <= 0.01 or alpha <= 0.01: return
    if s != 1: im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BICUBIC)
    if rot: im = im.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 1:
        a = im.getchannel('A').point(lambda v: int(v * alpha)); im = im.copy(); im.putalpha(a)
    _paste_clip(dst, im, int(cx - im.width / 2), int(cy - im.height / 2))


def _paste_clip(dst, im, x, y):
    x0, y0 = max(0, x), max(0, y); x1, y1 = min(dst.width, x + im.width), min(dst.height, y + im.height)
    if x1 <= x0 or y1 <= y0: return
    dst.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def face_chip(c, size):
    s = int(c.fw * 1.5); x0, y0 = int(c.fx - s / 2), int(c.fy - s / 2)
    pad = np.pad(c.img.astype(np.uint8), ((s, s), (s, s), (0, 0)), mode='edge')
    crop = Image.fromarray(pad[y0 + s:y0 + 2 * s, x0 + s:x0 + 2 * s]).resize((int(size), int(size)), Image.LANCZOS).convert('RGBA')
    m = Image.new('L', crop.size, 0); ImageDraw.Draw(m).ellipse([0, 0, crop.width - 1, crop.height - 1], fill=255); crop.putalpha(m)
    return crop


def zoom(img, cx, cy, s):
    H, W = img.shape[:2]
    cx2 = clamp(cx, W / (2 * s), W - W / (2 * s)); cy2 = clamp(cy, H / (2 * s), H - H / (2 * s))
    M = np.float32([[s, 0, W / 2 - cx2 * s], [0, s, H / 2 - cy2 * s]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)


def grade_gray(img, contrast=1.25):
    g = img @ np.array([0.299, 0.587, 0.114], np.float32)
    g = np.clip((g - 128) * contrast + 128, 0, 255); return np.repeat(g[..., None], 3, 2)


def grain(c, amt=10):
    rng = np.random.default_rng(int(c.t * 1000))
    n = rng.normal(0, amt, (c.H // 2, c.W // 2)).astype(np.float32)
    c.img = c.img + cv2.resize(n, (c.W, c.H))[..., None]


def vignette(c, k=0.55):
    if 'vig' not in c.state:
        y, x = np.ogrid[:c.H, :c.W]; r = np.sqrt(((x - c.W / 2) / (c.W * 0.62)) ** 2 + ((y - c.H / 2) / (c.H * 0.62)) ** 2)
        c.state['vig'] = np.clip(1 - (r - 0.55) * 1.2, 0, 1).astype(np.float32)
    c.img = c.img * (1 - k + k * c.state['vig'][..., None])


def splits(s, default):
    s = s if s not in (None, '') else default
    return [x.strip() for x in str(s).split('|') if x.strip() != '']


def nums(s, default):
    out = []
    for x in splits(s, default):
        x2 = x.upper().replace(',', '')
        mul = 1000 if x2.endswith('K') else 1_000_000 if x2.endswith('M') else 1
        try: out.append(float(x2.rstrip('KM')) * mul)
        except ValueError: out.append(0.0)
    return out


@effect('glass-widgets', 'frosted glass widgets around your head')
def fx_glass_widgets(c):
    W = c.W; gw, gap = 450, 22; h1, h2 = 270, 150; total = h1 + gap + h2 * 2 + gap
    y0 = c.zone(total); x0 = (W - (gw * 2 + gap)) / 2
    rects = [(x0, y0, gw, h1), (x0 + gw + gap, y0, gw, h1), (x0, y0 + h1 + gap, gw * 2 + gap, h2), (x0, y0 + h1 + gap * 2 + h2, gw * 2 + gap, h2)]
    if 'blur' not in c.state or c.state.get('blur_t') != c.t:
        sm = cv2.resize(c.img, (W // 4, c.H // 4)); c.state['blur'] = cv2.resize(cv2.GaussianBlur(sm, (0, 0), 7), (W, c.H)); c.state['blur_t'] = c.t
    blur = c.state['blur']
    glass = Image.new('L', (W, c.H), 0); ink = c.canvas(); gd = ImageDraw.Draw(glass)
    for i, (x, y, w, h) in enumerate(rects):
        k = back_out((c.lt - 0.12 * i) / 0.42)
        if k <= 0.01: continue
        cx, cy = x + w / 2, y + h / 2; w2, h2_ = w * k, h * k
        gd.rounded_rectangle([cx - w2 / 2, cy - h2_ / 2, cx + w2 / 2, cy + h2_ / 2], int(46 * k), fill=255)
        panel = Image.new('RGBA', (int(w), int(h)), (0, 0, 0, 0)); d = ImageDraw.Draw(panel)
        d.rounded_rectangle([1, 1, w - 2, h - 2], 46, outline=(255, 255, 255, 120), width=3)
        if i == 0:
            big = str(c.o('text', '7')); sub = splits(c.o('sub'), 'edits|one clip')
            d.text((40, 18), big, font=fit_font('ui', big, w - 80, 160, 800), fill=(255, 255, 255, 255))
            for j, line in enumerate(sub[:2]): d.text((44, h - 86 + j * 38), line, font=font('ui', 32, 500), fill=(255, 255, 255, 220))
        elif i == 1:
            vals = nums(c.o('bars'), '12|9|8|6|4|3'); top = str(c.o('top', ''))
            d.text((36, 24), 'Top reel', font=font('ui', 28, 500), fill=(255, 255, 255, 210))
            d.text((36, 56), top or f'{int(max(vals)):,}', font=font('ui', 62, 800), fill=(255, 255, 255, 255))
            n = max(1, len(vals)); bw = (w - 72 - (n - 1) * 14) / n; base = h - 36; mx = max(vals) or 1
            for j, v in enumerate(vals):
                g = ease_out((c.lt - 0.35 - 0.06 * j) / 0.5); bh = (h - 160) * v / mx * g
                bx = 36 + j * (bw + 14)
                if bh > 2: d.rounded_rectangle([bx, base - bh, bx + bw, base], 10, fill=(255, 255, 255, 235 if j == 0 else 150))
        elif i == 2:
            chip = face_chip(c, h - 56); panel.alpha_composite(chip, (28, 28))
            d.text((h + 4, h / 2 - 4), str(c.o('name', 'Your Name')), font=font('ui', 48, 750), fill=(255, 255, 255, 255), anchor='ls')
            d.text((h + 6, h / 2 + 42), str(c.o('handle', '@yourhandle')), font=font('ui', 32, 450), fill=(255, 255, 255, 210), anchor='ls')
        else:
            import datetime as _dt
            now = _dt.date.today(); day = str(c.o('day', now.strftime('%a').upper())); date = str(c.o('date', now.day))
            d.text((70, 26), day, font=font('ui', 26, 700), fill=(255, 95, 90, 255), anchor='mt')
            d.text((70, 58), date, font=font('ui', 64, 800), fill=(255, 255, 255, 255), anchor='mt')
            d.line([(140, 36), (140, h - 36)], fill=(255, 255, 255, 90), width=2)
            ev = str(c.o('event', 'Post the reel · tonight'))
            d.text((170, h / 2), ev, font=fit_font('ui', ev, w - 210, 46, 600), fill=(255, 255, 255, 255), anchor='lm')
        paste_scaled(ink, panel, cx, cy, k)
    g = np.asarray(glass, np.float32)[..., None] / 255.0 * c.alpha
    if c.guard(): g = g * (1 - c.mask[..., None])
    tinted = blur * 0.72 + 255 * 0.16
    c.img = c.img * (1 - g) + tinted * g
    c.comp(ink)


@effect('documentary', 'black and white you, stamped words')
def fx_documentary(c):
    W, H = c.W, c.H; k = c.alpha
    gray = grade_gray(c.img, 1.35); bg = gray * 0.32
    c.img = lerp(c.img, bg * (1 - c.mask[..., None]) + gray * c.mask[..., None], k)
    wall = str(c.o('wall', 'EDITED')); back = c.canvas(); d = ImageDraw.Draw(back)
    fw = font('ui', 120, 900); step = fw.getlength(wall + '  ')
    for r in range(-1, 18):
        off = (c.lt * 60 * (1 if r % 2 else -1)) % step - step
        x = off
        while x < W:
            d.text((x, r * 130), wall, font=fw, fill=(255, 255, 255, 22)); x += step
    lines = splits(c.o('text'), 'ONE CLIP.|7 EDITS.'); hl = str(c.o('hl', '')).upper()
    top = max(160, c.fy - c.fw * 1.9); lh = 210
    for i, line in enumerate(lines[:3]):
        s = (c.lt - 0.25 - 0.32 * i) / 0.18
        if s <= 0: continue
        sc = lerp(1.6, 1.0, ease_out(s)); f = fit_font('ui', line, W * 0.92, 230, 900)
        tw = Image.new('RGBA', (W, lh + 40), (0, 0, 0, 0)); td = ImageDraw.Draw(tw); x = (W - f.getlength(line)) / 2
        for word in line.split(' '):
            col = RED if hl and hl in word.upper() else (255, 255, 255)
            td.text((x, 10), word, font=f, fill=col + (255,)); x += f.getlength(word + ' ')
        paste_scaled(back, tw, W / 2, top + i * lh + lh / 2, sc, 0, clamp(s * 2))
    c.comp(back, behind=True)
    fr = c.canvas(); d = ImageDraw.Draw(fr)
    tag = str(c.o('tag', 'A DAILY SERIES')); s = ease_out((c.lt - 0.1) / 0.4)
    tf = font('mono', 30); tw_ = tf.getlength(tag) + 90
    d.rectangle([60, 110, 60 + tw_ * s, 172], fill=(0, 0, 0, 200)); d.ellipse([84, 131, 104, 151], fill=RED + (255,))
    if s > 0.9: d.text((120, 141), tag, font=tf, fill=(255, 255, 255, 255), anchor='lm')
    s2 = ease_out((c.lt - 0.6) / 0.45); y = H - 330
    d.rectangle([60, y, 60 + 14, y + 150], fill=RED + (int(255 * s2),))
    nm = str(c.o('name', 'YOUR NAME')).upper(); hd = str(c.o('handle', '@yourhandle'))
    d.text((100 - (1 - s2) * 60, y + 8), nm, font=fit_font('ui', nm, W - 200, 92, 900), fill=(255, 255, 255, int(255 * s2)))
    d.text((102 - (1 - s2) * 60, y + 110), hd, font=font('mono', 34), fill=(230, 230, 230, int(230 * s2)))
    c.comp(fr, behind=c.guard())
    grain(c, 9 * k); vignette(c, 0.5 * k)


def thumb_card(img, w, h, r=26, border=6):
    im = Image.fromarray(img).convert('RGB') if isinstance(img, np.ndarray) else img.convert('RGB')
    s = max(w / im.width, h / im.height); im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    l, t = (im.width - w) // 2, (im.height - h) // 2; im = im.crop((l, t, l + w, t + h)).convert('RGBA')
    im.putalpha(rounded_mask(w, h, r))
    out, pad = card(w + border * 2, h + border * 2, r + border, (255, 255, 255, 255), 90)
    out.alpha_composite(im, (pad + border, pad + border)); return out


@effect('orbit', 'your reels circle your head')
def fx_orbit(c):
    n = int(c.o('count', 6)); thumbs = c.thumbs or [c.img.astype(np.uint8)]
    key = ('orbit_cards', n)
    if key not in c.state:
        cw = int(min(c.fw * 0.55, c.W * 0.2)); ch = int(cw * 16 / 9)
        c.state[key] = [thumb_card(thumbs[i % len(thumbs)], cw, ch) for i in range(n)]
    cards = c.state[key]; back, front = c.canvas(), c.canvas()
    ox, oy = c.fx, c.fy; rx, ry = min(c.fw * 1.5, c.W * 0.42) * ease_out(c.lt / 0.5), c.fw * 0.5
    order = []
    for i in range(n):
        a = 2 * math.pi * i / n + c.lt * 1.3 - 0.5
        depth = math.sin(a); order.append((depth, i, a))
    for depth, i, a in sorted(order):
        s = 0.62 + 0.38 * (depth + 1) / 2
        paste_scaled(front if depth > 0 else back, cards[i], ox + rx * math.cos(a), oy + ry * depth, s, -math.cos(a) * 8, 0.55 + 0.45 * (depth + 1) / 2)
    c.comp(back, behind=True); c.comp(front, behind=False)


@effect('chart-split', 'a live chart on top, you below')
def fx_chart_split(c):
    W, H = c.W, c.H; k = ease_out(c.lt / 0.45) * clamp((c.d - c.lt) / 0.25)
    src = c.img.copy(); ph = int(H * 0.5)
    cw, chh = W - 100, H - ph - 110; scale = (chh / H) * 1.35
    crop_h = chh / scale; crop_w = cw / scale
    cx = clamp(c.fx, crop_w / 2, W - crop_w / 2); cy = clamp(c.fy + c.fw * 0.55, crop_h / 2, H - crop_h / 2)
    x0, y0 = int(cx - crop_w / 2), int(cy - crop_h / 2)
    person = cv2.resize(src[y0:y0 + int(crop_h), x0:x0 + int(crop_w)], (cw, chh))
    out = Image.new('RGBA', (W, H), (18, 18, 17, 255))
    pim = Image.fromarray(np.clip(person, 0, 255).astype(np.uint8)).convert('RGBA'); pim.putalpha(rounded_mask(cw, chh, 48))
    out.alpha_composite(pim, (50, ph + 50))
    panel = Image.new('RGBA', (W, ph), CREAM + (255,)); d = ImageDraw.Draw(panel)
    title = str(c.o('title', 'My top reels'))
    d.text((70, 120), title, font=fit_font('serif', title, W - 140, 86, 700), fill=INK + (255,))
    labels = splits(c.o('labels'), 'A|B|C|D|E'); vals = nums(c.o('vals'), '5|4|3|2|1')
    n = min(len(labels), len(vals)) or 1; mx = max(vals[:n]) or 1
    left, right, base, top = 70, W - 70, ph - 120, 300; bw = (right - left - (n - 1) * 26) / n
    d.line([(left, base), (right, base)], fill=(INK + (90,)), width=3)
    for i in range(n):
        g = ease_out((c.lt - 0.35 - 0.1 * i) / 0.6); bh = (base - top) * vals[i] / mx * g; x = left + i * (bw + 26)
        if bh > 1: d.rounded_rectangle([x, base - bh, x + bw, base], 14, fill=(ORANGE if i == 0 else (60, 58, 54)) + (255,))
        v = vals[i] * g; vs = f'{v / 1000:.1f}K' if vals[i] >= 1000 else f'{int(round(v))}'
        d.text((x + bw / 2, base - bh - 14), vs, font=font('ui', 36, 750), fill=INK + (255,), anchor='ms')
        lab = labels[i]; d.text((x + bw / 2, base + 22), lab, font=fit_font('ui', lab, bw + 20, 30, 550), fill=INK + (200,), anchor='mt')
    out.alpha_composite(panel, (0, int(-ph * (1 - ease_out(c.lt / 0.5)))))
    final = np.asarray(out, np.float32)[..., :3]
    c.img = c.img * (1 - k) + final * k


@effect('spotlight', 'kill the lights, keep you lit')
def fx_spotlight(c):
    k = c.alpha; y, x = np.ogrid[:c.H, :c.W]
    r = np.sqrt((x - c.fx) ** 2 + ((y - c.fy - c.fw * 0.4) * 0.8) ** 2).astype(np.float32)
    light = np.clip(1.2 - r / (c.fw * 1.25), 0, 1)
    light = np.maximum(light * 0.85, c.mask * 0.9)[..., None]
    lit = c.img * np.array([1.08, 1.0, 0.9], np.float32)
    target = c.img * 0.07 * (1 - light) + lit * light
    word = str(c.o('text', ''))
    if word:
        tl = c.canvas(); d = ImageDraw.Draw(tl); f = fit_font('ui', word, c.W * 0.94, 340, 900)
        d.text((c.W / 2, c.fy - c.fw * 0.1), word, font=f, fill=(255, 255, 255, int(240 * ease_out((c.lt - 0.35) / 0.4))), anchor='mm')
        a = np.asarray(tl, np.float32); la = a[..., 3:4] / 255 * (1 - c.mask[..., None])
        target = target * (1 - la) + a[..., :3] * la
    c.img = c.img * (1 - k) + target * k


def tick_icon(size, col):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse([0, 0, size - 1, size - 1], fill=col + (255,))
    d.line([(size * 0.27, size * 0.52), (size * 0.44, size * 0.68), (size * 0.74, size * 0.34)], fill=(255, 255, 255, 255), width=max(3, size // 9), joint='curve')
    return im


def asterisk(d, cx, cy, r, col=ORANGE):
    for kk in range(8):
        a = kk * math.pi / 4
        d.line([(cx, cy), (cx + r * math.cos(a), cy + r * math.sin(a))], fill=col + (255,), width=max(3, int(r * 0.3)))


@effect('checklist', 'Claude ticks off every step')
def fx_checklist(c):
    dark = str(c.o('look', 'light')) == 'dark'
    raw = splits(c.o('text'), 'Found your face|Cut you out of the room|Put the text behind you|Graded the colour|Rendered for Reels')
    items = [(x.split('::') + [''])[:2] for x in raw][:7]
    w = c.W - 120; rowh = 92; h = 130 + rowh * len(items) + 30
    y0 = c.zone(h); bg = (30, 30, 28, 240) if dark else (255, 255, 255, 245)
    fg = (240, 238, 232) if dark else INK; mut = (150, 148, 140) if dark else (120, 118, 112)
    im, pad = card(w, h, 44, bg, 80); d = ImageDraw.Draw(im); ox, oy = pad, pad
    asterisk(d, ox + 62, oy + 66, 24)
    n = len(items); per = (c.d - 0.9) / max(1, n); done = clamp((c.lt - 0.4) / per, 0, n)
    d.text((ox + 104, oy + 66), 'Claude', font=font('ui', 40, 700), fill=fg + (255,), anchor='lm')
    status = 'Done' if done >= n else 'Working' + '.' * (int(c.lt * 4) % 4)
    d.text((ox + w - 44, oy + 66), status, font=font('ui', 32, 500), fill=(ORANGE if done < n else (70, 170, 100)) + (255,), anchor='rm')
    for i, (a, b) in enumerate(items):
        y = oy + 130 + i * rowh + rowh / 2; on = done >= i + 1; cur = i <= done < i + 1
        if on:
            s = back_out((done - i - 1) * per / 0.25 + 1 if done < i + 1.3 else 1)
            t = tick_icon(52, (70, 170, 100)); paste_scaled(im, t, ox + 62, y, min(1.0, max(0.3, s)))
        else:
            d.ellipse([ox + 38, y - 24, ox + 86, y + 24], outline=mut + (255,), width=3)
            if cur:
                ang = c.lt * 400 % 360; d.arc([ox + 38, y - 24, ox + 86, y + 24], ang, ang + 90, fill=ORANGE + (255,), width=5)
        d.text((ox + 112, y), a, font=fit_font('ui', a, w - 420, 40, 600 if on else 450), fill=(fg if on or cur else mut) + (255,), anchor='lm')
        if b and on: d.text((ox + w - 44, y), b, font=font('ui', 32, 500), fill=mut + (255,), anchor='rm')
    lay = c.canvas(); s = back_out(c.lt / 0.45)
    paste_scaled(lay, im, c.W / 2, y0 + h / 2, s)
    c.comp(lay)


@effect('timeline', 'a live editing timeline')
def fx_timeline(c):
    W, H = c.W, c.H; ph = 560; y0 = H - ph + (1 - ease_out(c.lt / 0.45)) * ph
    lay = c.canvas(); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([0, y0, W, H + 60], 40, fill=(22, 22, 21, 238))
    for i in range(0, 13):
        x = 60 + i * (W - 120) / 12; d.line([(x, y0 + 60), (x, y0 + (80 if i % 2 == 0 else 72))], fill=(120, 118, 112, 255), width=2)
        if i % 2 == 0: d.text((x + 6, y0 + 40), f'00:{i:02d}', font=font('mono', 20), fill=(130, 128, 120, 255))
    tracks = [('V1', (79, 128, 220)), ('T1', ORANGE), ('A1', (90, 180, 120))]
    rnd = random.Random(7)
    for j, (nm, col) in enumerate(tracks):
        ty = y0 + 110 + j * 120; d.text((24, ty + 40), nm, font=font('mono', 22), fill=(150, 148, 140, 255), anchor='lm')
        x = 70
        while x < W - 40:
            bw = rnd.randint(160, 330); x2 = min(W - 40, x + bw)
            d.rounded_rectangle([x, ty, x2 - 8, ty + 84], 14, fill=col + (200,))
            if nm == 'A1':
                for xx in range(int(x) + 8, int(x2) - 14, 8):
                    a = 8 + abs(math.sin(xx * 0.07) * math.cos(xx * 0.013)) * 30
                    d.line([(xx, ty + 42 - a), (xx, ty + 42 + a)], fill=(255, 255, 255, 170), width=3)
            elif nm == 'T1':
                d.text((x + 18, ty + 42), str(c.o('text', 'AUTO-EDIT')), font=font('ui', 28, 700), fill=(255, 255, 255, 255), anchor='lm')
            x = x2
    px = 70 + (W - 120) * clamp(c.lt / c.d)
    d.line([(px, y0 + 50), (px, y0 + 470)], fill=RED + (255,), width=4); d.polygon([(px - 14, y0 + 46), (px + 14, y0 + 46), (px, y0 + 66)], fill=RED + (255,))
    c.comp(lay, behind=False)
    top = c.canvas(); d = ImageDraw.Draw(top); s = ease_out((c.lt - 0.3) / 0.4)
    title = str(c.o('text', 'AUTO-EDIT')); sub = str(c.o('sub', ''))
    ty = H - ph - 190
    d.text((W / 2, ty + (1 - s) * 40), title, font=fit_font('ui', title, W - 120, 130, 900), fill=(255, 255, 255, int(255 * s)), anchor='mm')
    if sub: d.text((W / 2, ty + 100 + (1 - s) * 40), sub, font=font('ui', 40, 500), fill=(255, 255, 255, int(220 * s)), anchor='mm')
    c.comp(top)


@effect('backdrop-word', 'a giant word behind you')
def fx_backdrop_word(c):
    word = str(c.o('text', 'FOCUS')); lay = c.canvas(); d = ImageDraw.Draw(lay)
    f = fit_font('ui', word, c.W * 0.96, 420, 900); s = ease_out(c.lt / 0.5)
    col = tuple(int(v) for v in str(c.o('color', '255,255,255')).split(','))[:3]
    d.text((c.W / 2, c.fy - c.fw * 0.1 + (1 - s) * 120), word, font=f, fill=col + (int(255 * s),), anchor='mm')
    c.img = c.img * (1 - 0.35 * c.alpha * (1 - c.mask[..., None]))
    c.comp(lay, behind=True)


@effect('moody', 'a moody colour grade')
def fx_moody(c):
    k = c.alpha; x = c.img / 255.0
    lum = (x @ np.array([0.299, 0.587, 0.114], np.float32))[..., None]
    x = lerp(x, lum, 0.35)
    x = np.clip((x - 0.5) * 1.35 + 0.44, 0, 1)
    sh = np.array([-0.02, 0.1, 0.14], np.float32); hi = np.array([0.12, 0.04, -0.06], np.float32)
    x = x + sh * (1 - lum) + hi * lum
    c.img = lerp(c.img, np.clip(x, 0, 1) * 255, k); vignette(c, 0.6 * k); grain(c, 7 * k)


@effect('lean-in', 'a punch-in on one word')
def fx_lean_in(c):
    s = lerp(1.0, 1.38, ease_out(c.lt / 0.25)) if c.lt < c.d - 0.25 else lerp(1.38, 1.0, ease((c.lt - c.d + 0.25) / 0.25))
    c.img = zoom(c.img, c.fx, c.fy + c.fw * 0.2, s).astype(np.float32)
    word = str(c.o('text', ''))
    if word:
        lay = c.canvas(); d = ImageDraw.Draw(lay); p = back_out((c.lt - 0.15) / 0.3)
        f = fit_font('ui', word, c.W - 140, 150, 900); y = c.H * 0.76
        im = Image.new('RGBA', (c.W, 260), (0, 0, 0, 0)); ImageDraw.Draw(im).text((c.W / 2, 130), word, font=f, fill=(255, 255, 255, 255), anchor='mm', stroke_width=10, stroke_fill=(0, 0, 0, 255))
        paste_scaled(lay, im, c.W / 2, y, max(0.01, p)); c.comp(lay, behind=False)


@effect('slow-push', 'a slow cinematic push-in')
def fx_slow_push(c):
    s = 1 + 0.16 * ease(c.p)
    c.img = zoom(c.img, c.fx, c.fy + c.fw * 0.3, s).astype(np.float32); vignette(c, 0.3 * c.alpha)


@effect('locked-on', 'brackets lock onto your face')
def fx_locked_on(c):
    lay = c.canvas(); d = ImageDraw.Draw(lay); k = ease_out(c.lt / 0.5)
    col = (120, 255, 140); half = c.fw * lerp(1.4, 0.62, k); hv = half * 1.3; L = half * 0.35
    x0, y0, x1, y1 = c.fx - half, c.fy - hv, c.fx + half, c.fy + hv
    for (x, y, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(x, y), (x + sx * L, y)], fill=col + (255,), width=7); d.line([(x, y), (x, y + sy * L)], fill=col + (255,), width=7)
    d.line([(c.fx - 18, c.fy), (c.fx + 18, c.fy)], fill=col + (180,), width=3); d.line([(c.fx, c.fy - 18), (c.fx, c.fy + 18)], fill=col + (180,), width=3)
    if k > 0.95 and int(c.lt * 6) % 2 == 0 or c.lt > 1.2:
        lab = str(c.o('text', 'TARGET LOCKED')); f = font('mono', 34)
        d.rectangle([x0, y0 - 64, x0 + f.getlength(lab) + 30, y0 - 14], fill=col + (230,))
        d.text((x0 + 15, y0 - 39), lab, font=f, fill=(0, 0, 0, 255), anchor='lm')
    f2 = font('mono', 22)
    for j, s in enumerate([f'X {int(c.fx):04d}', f'Y {int(c.fy):04d}', f'CONF {0.9 + 0.09 * math.sin(c.lt * 7):.2f}']):
        d.text((x1 + 16, y0 + j * 32), s, font=f2, fill=col + (220,))
    c.comp(lay, behind=False)


@effect('led-sign', 'a glowing LED sign types out')
def fx_led_sign(c):
    word = str(c.o('text', 'ON AIR')).upper(); n = int(clamp((c.lt - 0.2) / 0.09, 0, len(word)))
    key = ('led', word)
    if key not in c.state:
        f = ImageFont.truetype(os.path.join(FONTS, 'SpaceMono-Bold.ttf'), 14) if os.path.exists(os.path.join(FONTS, 'SpaceMono-Bold.ttf')) else ImageFont.load_default()
        bw = int(f.getlength(word)) + 4; bm = Image.new('L', (bw, 18), 0); ImageDraw.Draw(bm).text((2, 1), word, font=f, fill=255)
        c.state[key] = (np.asarray(bm) > 110, [int(f.getlength(word[:i])) + 2 for i in range(len(word) + 1)])
    bits, cuts = c.state[key]
    cell = min(18, (c.W - 140) / bits.shape[1]); sw, sh = bits.shape[1] * cell + 60, bits.shape[0] * cell + 60
    y0 = max(120, c.fy - c.fw * 1.1 - sh); x0 = (c.W - sw) / 2
    lay = c.canvas(); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([x0, y0, x0 + sw, y0 + sh], 24, fill=(14, 12, 10, 245), outline=(60, 55, 50, 255), width=4)
    glow = c.canvas(); g = ImageDraw.Draw(glow); col = (255, 150, 60)
    lim = cuts[n]
    for yy in range(bits.shape[0]):
        for xx in range(bits.shape[1]):
            cx, cy = x0 + 30 + xx * cell + cell / 2, y0 + 30 + yy * cell + cell / 2; r = cell * 0.36
            if bits[yy, xx] and xx < lim:
                g.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (255,))
            else:
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(40, 34, 30, 255))
    blur = glow.filter(ImageFilter.GaussianBlur(cell * 0.8)); lay.alpha_composite(blur); lay.alpha_composite(blur); lay.alpha_composite(glow)
    c.comp(lay, behind=True)


@effect('reject-stamp', 'a big red stamp slams down')
def fx_reject_stamp(c):
    word = str(c.o('text', 'REJECTED')).upper(); t0 = 0.35
    if c.lt < t0: return
    q = (c.lt - t0) / 0.16; s = lerp(2.6, 1.0, ease_out(q))
    if 0 < c.lt - t0 < 0.3:
        a = (0.3 - (c.lt - t0)) * 60; c.img = zoom(c.img, c.W / 2 + math.sin(c.lt * 90) * a, c.H / 2 + math.cos(c.lt * 70) * a, 1.03).astype(np.float32)
    key = ('stamp', word)
    if key not in c.state:
        f = fit_font('ui', word, c.W * 0.7, 170, 900); tw = int(f.getlength(word)) + 120; th = 260
        im = Image.new('RGBA', (tw, th), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle([8, 8, tw - 8, th - 8], 26, outline=RED + (255,), width=14); d.rounded_rectangle([30, 30, tw - 30, th - 30], 16, outline=RED + (255,), width=5)
        d.text((tw / 2, th / 2), word, font=f, fill=RED + (255,), anchor='mm')
        rng = np.random.default_rng(3); a = np.asarray(im.getchannel('A'), np.float32)
        a = a * (rng.random(a.shape) > 0.12) * np.clip(rng.normal(1, 0.15, a.shape), 0.6, 1)
        im.putalpha(Image.fromarray(a.astype(np.uint8))); c.state[key] = im
    lay = c.canvas(); paste_scaled(lay, c.state[key], c.W / 2, min(c.H - 260, c.fy + c.fw * 0.9), s, 12, clamp(q * 3) * 0.92)
    c.comp(lay, behind=False)


@effect('countdown-flip', 'a 3, 2, 1 flip clock')
def fx_countdown_flip(c):
    seq = splits(c.o('seq'), '3|2|1') + [str(c.o('text', 'GO'))]; per = c.d / len(seq)
    i = min(len(seq) - 1, int(c.lt / per)); q = (c.lt - i * per) / 0.28
    cw, ch = 520, 640; x0, y0 = (c.W - cw) / 2, c.zone(ch)

    def face_im(txt):
        im, pad = card(cw, ch, 50, (28, 28, 30, 255), 90); d = ImageDraw.Draw(im)
        d.text((pad + cw / 2, pad + ch / 2), txt, font=fit_font('ui', txt, cw - 80, 460, 800), fill=(245, 243, 238, 255), anchor='mm')
        d.line([(pad, pad + ch / 2), (pad + cw, pad + ch / 2)], fill=(10, 10, 10, 255), width=6); return im, pad
    cur, pad = face_im(seq[i]); prev = face_im(seq[i - 1])[0] if i > 0 else cur
    out = Image.new('RGBA', cur.size, (0, 0, 0, 0)); mid = pad + ch // 2
    out.alpha_composite(cur.crop((0, 0, cur.width, mid)), (0, 0)); out.alpha_composite(prev.crop((0, mid, cur.width, cur.height)), (0, mid))
    k = ease(q)
    if k < 0.5:
        top = prev.crop((0, 0, cur.width, mid)); hh = max(1, int(mid * (1 - k * 2)))
        out.alpha_composite(top.resize((cur.width, hh)), (0, mid - hh))
    else:
        bot = cur.crop((0, mid, cur.width, cur.height)); hh = max(1, int((cur.height - mid) * (k * 2 - 1)))
        out.alpha_composite(bot.resize((cur.width, hh)), (0, mid))
    if k >= 1: out = cur
    lay = c.canvas(); paste_scaled(lay, out, c.W / 2, y0 + ch / 2, back_out(c.lt / 0.35)); c.comp(lay)


@effect('huge-strike', 'a huge word gets crossed out')
def fx_huge_strike(c):
    word = str(c.o('text', 'EASY')).upper(); sub = str(c.o('sub', ''))
    lay = c.canvas(); d = ImageDraw.Draw(lay); f = fit_font('ui', word, c.W * 0.94, 400, 900)
    y = c.fy - c.fw * 0.15; s = ease_out(c.lt / 0.4)
    d.text((c.W / 2, y), word, font=f, fill=(255, 255, 255, int(255 * s)), anchor='mm')
    k = ease_out((c.lt - 0.7) / 0.35); tw = f.getlength(word)
    if k > 0:
        xa = c.W / 2 - tw / 2 - 30; d.line([(xa, y + 20), (xa + (tw + 60) * k, y - 30 * k)], fill=RED + (255,), width=34)
    c.img = c.img * (1 - 0.4 * c.alpha * (1 - c.mask[..., None]))
    c.comp(lay, behind=True)
    if sub:
        fr = c.canvas(); p = back_out((c.lt - 1.2) / 0.35)
        im = Image.new('RGBA', (c.W, 240), (0, 0, 0, 0)); ImageDraw.Draw(im).text((c.W / 2, 120), sub.upper(), font=fit_font('ui', sub.upper(), c.W - 160, 170, 900), fill=RED + (255,), anchor='mm', stroke_width=8, stroke_fill=(255, 255, 255, 255))
        paste_scaled(fr, im, c.W / 2, min(c.H - 220, c.fy + c.fw * 1.3), max(0.01, p), -4); c.comp(fr, behind=False)


@effect('tape-label', 'yellow tape lands on your chest')
def fx_tape_label(c):
    word = str(c.o('text', 'WORK IN PROGRESS')).upper(); key = ('tape', word)
    if key not in c.state:
        f = fit_font('ui', word, c.W * 0.95, 96, 900); tw = int(max(c.W * 1.1, f.getlength(word) + 200)); th = 150
        im = Image.new('RGBA', (tw, th), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        pts = [(0, 10)] + [(x, 10 + (6 if (x // 22) % 2 else 0)) for x in range(0, tw, 22)] + [(tw, 10), (tw, th - 10)] + [(x, th - 10 - (6 if (x // 22) % 2 else 0)) for x in range(tw, 0, -22)] + [(0, th - 10)]
        d.polygon(pts, fill=(250, 214, 40, 245)); d.text((tw / 2, th / 2), word, font=f, fill=(15, 15, 15, 255), anchor='mm')
        c.state[key] = im
    lay = c.canvas(); k = ease_out(c.lt / 0.35)
    paste_scaled(lay, c.state[key], c.W / 2 - (1 - k) * c.W * 1.2, min(c.H - 200, c.fy + c.fw * 1.6), 1, 4)
    c.comp(lay, behind=False)


@effect('messages', 'chat pop-ups stack up')
def fx_messages(c):
    msgs = splits(c.o('text'), 'did you edit this yourself?|how is this one clip|send the effects pls')
    sender = str(c.o('from', 'New message')); w = c.W - 140; hgt = 170; lay = c.canvas()
    shown = [i for i in range(len(msgs)) if c.lt >= 0.25 + i * 0.55]
    newest = shown[-1] if shown else 0; slide = ease_out((c.lt - 0.25 - newest * 0.55) / 0.3)
    for slot, i in enumerate(reversed(shown)):
        p = back_out((c.lt - 0.25 - i * 0.55) / 0.35); y = 130 + (slot - (1 - slide if slot else 0)) * (hgt + 20)
        im, pad = card(w, hgt, 40, (248, 248, 250, 240), 70); d = ImageDraw.Draw(im)
        d.rounded_rectangle([pad + 30, pad + 34, pad + 90, pad + 94], 16, fill=(70, 200, 100, 255))
        d.text((pad + 60, pad + 64), '•••', font=font('ui', 22, 800), fill=(255, 255, 255, 255), anchor='mm')
        d.text((pad + 116, pad + 44), sender, font=font('ui', 32, 700), fill=INK + (255,), anchor='lt')
        d.text((pad + w - 34, pad + 44), 'now', font=font('ui', 28, 400), fill=(130, 130, 135, 255), anchor='rt')
        d.text((pad + 116, pad + 92), msgs[i], font=fit_font('ui', msgs[i], w - 160, 36, 450), fill=(40, 40, 44, 255), anchor='lt')
        paste_scaled(lay, im, c.W / 2, y + hgt / 2, max(0.01, min(p, 1.05)))
    c.comp(lay)


def video_info(path):
    cap = cv2.VideoCapture(path); fps = cap.get(cv2.CAP_PROP_FPS) or 30; n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)); cap.release()
    return fps, n, w, h


def load_thumbs(e, clip, n=8):
    src = e.get('images')
    if src:
        files = sorted(glob.glob(os.path.join(src, '*'))) if isinstance(src, str) and os.path.isdir(src) else (src if isinstance(src, list) else [])
        ims = [np.asarray(Image.open(f).convert('RGB')) for f in files if f.lower().rsplit('.', 1)[-1] in ('png', 'jpg', 'jpeg', 'webp')]
        if ims: return ims
    cap = cv2.VideoCapture(clip); total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1; out = []
    tints = [(1, 1, 1), (1.1, 0.95, 0.85), (0.85, 0.95, 1.1), (1.05, 0.9, 1.05), (0.9, 1.05, 0.95), (1.1, 1.05, 0.8)]
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (i + 0.5) / n)); ok, fr = cap.read()
        if ok: out.append(np.clip(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB) * np.array(tints[i % len(tints)]), 0, 255).astype(np.uint8))
    cap.release(); return out


def ffmpeg_exe():
    p = os.environ.get('FFMPEG') or shutil.which('ffmpeg')
    if p: return p
    try:
        import imageio_ffmpeg; return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception: sys.exit('ffmpeg not found. Install ffmpeg and make sure it is on PATH.')


def active(plan, t):
    for e in plan:
        if e['start'] <= t < e['end']: return e
    return None


def render(plan, clip, out, stills=None):
    for e in plan:
        if e['fx'] not in EFFECTS: sys.exit(f"Unknown effect '{e['fx']}'. See: python fx_engine.py --list")
    fps, n, W, H = video_info(clip)
    if n <= 0 or W <= 0: sys.exit(f'Could not read video: {clip}')
    tr = Tracker(); thumbs = {}; states = {}
    def frame_for(img, t, e):
        key = id(e)
        if key not in thumbs: thumbs[key] = load_thumbs(e, clip) if e['fx'] in ('orbit',) else []
        box, mask = tr.analyse(img)
        c = Ctx(img, t, e, box, mask, thumbs[key], states.setdefault(key, {}))
        EFFECTS[e['fx']][0](c); return c.out()
    if stills:
        stem, ext = os.path.splitext(out); cap = cv2.VideoCapture(clip)
        for j, t in enumerate(stills, 1):
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000); ok, fr = cap.read()
            if not ok: continue
            img = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB); e = active(plan, t); tr.reset()
            if e: img = frame_for(img, t, e)
            Image.fromarray(img).save(f'{stem}_{j}{ext or ".png"}'); print('still', f'{stem}_{j}{ext or ".png"}', flush=True)
        cap.release(); return
    enc = subprocess.Popen([ffmpeg_exe(), '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', f'{fps:.4f}', '-i', '-',
                            '-c:v', 'libx264', '-crf', '16', '-preset', 'fast', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    cap = cv2.VideoCapture(clip); i = 0; last = None
    while True:
        ok, fr = cap.read()
        if not ok: break
        t = i / fps; img = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB); e = active(plan, t)
        if e is not last: tr.reset(); last = e
        if e: img = frame_for(img, t, e)
        enc.stdin.write(np.ascontiguousarray(img).tobytes()); i += 1
        if i % 60 == 0: print(f'frame {i}/{n}', flush=True)
    cap.release(); enc.stdin.close(); enc.wait()
    if enc.returncode: sys.exit('ffmpeg failed while writing ' + out)
    print('FX_DONE', out)


def main():
    if '--list' in sys.argv:
        for k, (_, d) in EFFECTS.items(): print(f'{k:16s} {d}')
        return
    if '--fetch' in sys.argv: fetch(); return
    ap = argparse.ArgumentParser(description=USAGE, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('args', nargs='+'); ap.add_argument('--plan'); ap.add_argument('--still')
    ap.add_argument('--start', type=float, default=0.0); ap.add_argument('--end', type=float); ap.add_argument('--opt', action='append', default=[])
    a = ap.parse_args()
    if a.plan:
        if len(a.args) != 2: ap.error('need: --plan plan.json in.mp4 out.mp4')
        plan = json.load(open(a.plan, encoding='utf-8'))['effects']; clip, out = a.args
    else:
        if len(a.args) != 3: ap.error('need: <effect> in.mp4 out.mp4')
        name, clip, out = a.args; fps, n, _, _ = video_info(clip)
        e = {'fx': name, 'start': a.start, 'end': a.end if a.end is not None else n / fps}
        for kv in a.opt:
            k, _, v = kv.partition('='); e[k] = v
        plan = [e]
    stills = [float(x) for x in a.still.split(',')] if a.still else None
    render(plan, clip, out, stills)


if __name__ == '__main__':
    main()

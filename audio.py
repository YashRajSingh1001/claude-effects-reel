#!/usr/bin/env python3
"""Synthesizes the reel's soundtrack: a punchy 4-on-the-floor beat locked to the edit grid, muffled while typing and
opening up on each reveal, plus UI sound design (key clicks, send pop, riser, whoosh, impact).
usage: python audio.py <workdir>   (reads workdir/events.json from reel.py, writes workdir/soundtrack.wav)"""
import json, math, os, sys
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 44100
WD = sys.argv[1] if len(sys.argv) > 1 else '.'
ev = json.load(open(os.path.join(WD, 'events.json'))); TOTAL = ev['total']; BEAT = ev['beat']
N = int(SR * (TOTAL + 0.2)); t_all = np.arange(N) / SR
rng = np.random.default_rng(3)

# ---- cue times come from reel.py ----
E = ev['events']
keys = [e['t'] for e in E if e['kind'] == 'key']; sends = [e['t'] for e in E if e['kind'] == 'send']
risers = [(e['t'], e['d']) for e in E if e['kind'] == 'riser']; whooshes = [e['t'] for e in E if e['kind'] == 'whoosh']
impacts = [e['t'] for e in E if e['kind'] == 'impact']
FIRST_TYPE_END = sends[0] if sends else 1.0

def add(buf, x, t0, g=1.0):
    i = int(t0 * SR)
    if i >= len(buf) or i + len(x) <= 0: return
    j0 = max(0, -i); x = x[j0:]; i = max(0, i); n = min(len(x), len(buf) - i); buf[i:i + n] += g * x[:n]

def env(n, a, d, sus=0.0):
    t = np.arange(n) / SR; e = np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d); return e * (1 - sus) + sus
def bp(x, lo, hi, order=2): return signal.sosfilt(signal.butter(order, [lo, hi], 'band', fs=SR, output='sos'), x)
def hp(x, f, order=2): return signal.sosfilt(signal.butter(order, f, 'high', fs=SR, output='sos'), x)
def lp(x, f, order=2): return signal.sosfilt(signal.butter(order, f, 'low', fs=SR, output='sos'), x)

# ---- instruments ----
def kick():
    n = int(0.42 * SR); t = np.arange(n) / SR
    f = 46 + 120 * np.exp(-t / 0.035); ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t / 0.22); x[:int(0.004 * SR)] += hp(rng.standard_normal(int(0.004 * SR)), 2000) * 0.5
    return np.tanh(x * 2.2) * 0.9
def clap():
    n = int(0.3 * SR); x = bp(rng.standard_normal(n), 900, 3800) * env(n, 0.001, 0.08)
    for d in (0.010, 0.021): add(x, bp(rng.standard_normal(int(0.02 * SR)), 900, 3800) * 0.6, d)
    t = np.arange(n) / SR; x += np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05) * 0.3
    return x * 0.55
def hat(open_=False):
    n = int((0.22 if open_ else 0.05) * SR); return hp(rng.standard_normal(n), 7500, 3) * env(n, 0.0005, 0.07 if open_ else 0.014) * (0.22 if open_ else 0.18)
def saw(f, n, detune=0.0):
    t = np.arange(n) / SR; out = 0
    for dt in ((0,) if not detune else (-detune, 0, detune)): out = out + signal.sawtooth(2 * np.pi * f * (1 + dt) * t + rng.random() * 6)
    return out / (1 if not detune else 3)
def note(m): return 440 * 2 ** ((m - 69) / 12)

K, CL = kick(), clap()
drums = np.zeros(N); bass = np.zeros(N); pad = np.zeros(N); arp = np.zeros(N); duck = np.ones(N)
prog = [(57, [57, 60, 64]), (53, [53, 57, 60]), (48, [48, 52, 55]), (55, [55, 59, 62])]   # Am F C G
nbeats = int(TOTAL / BEAT) + 2
for bi in range(nbeats):
    tb = bi * BEAT; bar = bi // 4; pos = bi % 4
    intro = tb < FIRST_TYPE_END * 0.999   # very first typing: lighter
    add(drums, K, tb, 0.75 if intro else 1.0)
    d = np.ones(int(0.32 * SR)); tt = np.arange(len(d)) / SR; d = 1 - 0.75 * np.exp(-tt / 0.09); i = int(tb * SR); n = min(len(d), N - i)
    if n > 0: duck[i:i + n] = np.minimum(duck[i:i + n], d[:n])
    if pos in (1, 3) and not intro: add(drums, CL, tb)
    for h in range(2):
        add(drums, hat(open_=(h == 1 and pos % 2 == 1)), tb + h * BEAT / 2)
    add(drums, hat(), tb + BEAT * 0.75, 0.6)
    root, chord = prog[bar % 4]
    for e8 in range(2):
        nn = int(BEAT / 2 * SR); f = note(root - 24 + (12 if e8 == 1 and pos == 3 else 0))
        x = lp(saw(f, nn), 900) * env(nn, 0.003, 0.16) * 0.42 + np.sin(2 * np.pi * f * np.arange(nn) / SR) * env(nn, 0.003, 0.22) * 0.38
        add(bass, x, tb + e8 * BEAT / 2)
    if pos == 0:
        nn = int(4 * BEAT * SR); x = sum(lp(saw(note(m), nn, 0.004), 1800) for m in chord) / 3
        tt = np.arange(nn) / SR; add(pad, x * np.minimum(1, tt / 0.08) * np.minimum(1, (4 * BEAT - tt) / 0.1) * 0.22, tb)
    for s16 in range(4):
        m = chord[(bi * 4 + s16) % 3] + 12 + (12 if s16 == 3 else 0); nn = int(0.14 * SR)
        x = lp(signal.square(2 * np.pi * note(m) * np.arange(nn) / SR, 0.3), 3500) * env(nn, 0.002, 0.05) * 0.07
        add(arp, x, tb + s16 * BEAT / 4)

music_full = drums + (bass + pad) * duck + arp * duck
# muffled while typing / card build, open on each reveal
open_amt = np.zeros(N)
for t0, t1, v0, v1 in ev['sections']:
    i0_, i1_ = int(t0 * SR), min(N, int(t1 * SR))
    if i1_ > i0_: open_amt[i0_:i1_] = np.linspace(v0, v1, i1_ - i0_)
open_amt = np.convolve(open_amt, np.ones(400) / 400, mode='same')
music_muf = lp(music_full, 600, 4) * 0.45
music = music_muf * (1 - open_amt) + music_full * open_amt

# ---- UI sound design ----
sfx = np.zeros(N)
def click():
    n = int(0.03 * SR); t = np.arange(n) / SR
    x = hp(rng.standard_normal(n), 2500) * np.exp(-t / 0.004) * 0.6 + np.sin(2 * np.pi * (1700 + rng.random() * 300) * t) * np.exp(-t / 0.006) * 0.35
    return x
def pop():
    n = int(0.12 * SR); t = np.arange(n) / SR; f = 520 + 900 * (t / 0.12) ** 0.5
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.035) * 0.55
def riser(d):
    n = int(d * SR); t = np.arange(n) / SR; k = t / d
    nz = rng.standard_normal(n); out = np.zeros(n); step = 2048
    for i in range(0, n, step):
        fc = 600 + 6000 * (i / n) ** 2; out[i:i + step] = bp(nz[i:i + step + 0][:step], fc * 0.6, min(fc * 1.6, 18000))[:len(out[i:i + step])]
    f = 300 + 900 * k ** 2; tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.12
    sh = sum(np.sin(2 * np.pi * np.cumsum(f * m) / SR) for m in (2, 3)) * 0.03
    return (out * 0.5 + tone + sh) * k ** 1.6
def whoosh():
    n = int(0.32 * SR); t = np.arange(n) / SR; e = np.sin(np.pi * np.clip(t / 0.32, 0, 1)) ** 2
    return bp(rng.standard_normal(n), 400, 5000) * e * 0.55
def impact():
    n = int(0.9 * SR); t = np.arange(n) / SR; f = 38 + 70 * np.exp(-t / 0.05)
    boom = np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.35) * 2.5) * 0.85
    crack = hp(rng.standard_normal(n), 1500) * np.exp(-t / 0.03) * 0.35
    shimmer = hp(rng.standard_normal(n), 6000) * np.exp(-t / 0.25) * 0.08
    return boom + crack + shimmer

for k in keys: add(sfx, click(), k, 0.32)
for s in sends: add(sfx, pop(), s, 0.8)
for t0, d in risers: add(sfx, riser(d), t0, 0.75)
for w in whooshes: add(sfx, whoosh(), w, 0.8)
for im in impacts: add(sfx, impact(), im, 0.95)

mix = music * 0.55 + sfx * 0.6
fade = np.ones(N); fl = int(1.2 * SR); fade[-fl:] = np.linspace(1, 0, fl); fade[:int(0.02 * SR)] = np.linspace(0, 1, int(0.02 * SR))
mix = np.tanh(mix * 1.15) / np.tanh(1.15) * fade
mix = mix / (np.abs(mix).max() + 1e-9) * 0.93
st = np.stack([mix, mix], 1)
# a touch of stereo width on the music/arp via a short delay on the right channel
st[:, 1] = np.roll(mix, int(0.006 * SR)) * 0.35 + mix * 0.65
wavfile.write(os.path.join(WD, 'soundtrack.wav'), SR, (st * 32767).astype(np.int16))
print('ok', TOTAL, 'rms', float(np.sqrt(np.mean(mix ** 2))))

"""Post-production for assemble.py: scene transitions, sound design, music bed and word captions.

Everything is generated here, offline and free: no sound libraries, no paid APIs.

- Transitions: every scene change gets a short visual move (zoom punch, whip pan, white flash; a dip
  from/to black at the very start and end) plus a matching whoosh or hit.
- Sound design: pops for labels, typewriter ticks for date stamps, booms for titles and flashes,
  pings for map pins, soft swishes on cuts, ambience beds picked from each picture's prompt
  (wind, rain, sea, battle, fire, crowd, factory), and the real sound of Flow/Veo clips.
- Music: a slow dark synth pad, one chord per scene, ducked under the narration.
- Captions: 1-3 words at a time, bold caps, the spoken word in yellow (ASS karaoke, burned in).
"""
import json
import math
import random
import re
import wave
from pathlib import Path

import numpy as np

SR = 44100
FPS = 25
TRANSITIONS = ["zoom", "whip", "flash", "whip"]  # cycled over scene changes
TRANS_FRAMES = {"zoom": (5, 7), "whip": (5, 6), "flash": (3, 6), "dip": (12, 12)}  # (exit, entry)

# ---------------------------------------------------------------- transitions (frame level)


def transition_plan(n_scenes):
    """Kind of the transition INTO each scene (scene 0 = dip from black); 'out' of the last = dip."""
    return ["dip"] + [TRANSITIONS[(i - 1) % len(TRANSITIONS)] for i in range(1, n_scenes)]


def apply_transition(img, kind, side, k):
    """img: PIL frame. side 'in' (k: 0 at the cut -> 1 settled) or 'out' (k: 0 settled -> 1 at the cut)."""
    from PIL import Image, ImageFilter
    w, h = img.size
    a = (1 - k) if side == "in" else k  # 1 = at the cut
    a = a * a * (3 - 2 * a)
    if a <= 0.001:
        return img
    if kind == "dip":
        return Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), a)
    if kind == "flash":
        return Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), min(1.0, a * 1.1))
    if kind == "zoom":
        z = 1 + (0.22 if side == "out" else 0.16) * a
        cw, ch = w / z, h / z
        out = img.resize((w, h), Image.BILINEAR, box=((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2))
        out = out.filter(ImageFilter.GaussianBlur(6 * a))
        return Image.blend(out, Image.new("RGB", img.size, (255, 255, 255)), 0.25 * a) if side == "in" else out
    if kind == "whip":
        dx = int(w * 0.35 * a) * (-1 if side == "out" else 1)
        small = img.resize((w // 4, h // 4), Image.BILINEAR)
        acc = np.zeros((h // 4, w // 4, 3), np.float32)
        arr = np.asarray(small, np.float32)
        steps = 9
        for s in range(steps):  # horizontal motion blur
            acc += np.roll(arr, int((dx / 4) * s / steps), axis=1)
        blur = Image.fromarray((acc / steps).astype(np.uint8)).resize((w, h), Image.BILINEAR)
        return Image.blend(img, blur, min(1.0, a * 1.6))
    return img


def frame_transition(img, f, frames, kind_in, kind_out):
    """Apply the entry/exit transition of a scene to its frame f (of `frames`)."""
    if kind_in:
        n = TRANS_FRAMES[kind_in][1]
        if f < n:
            img = apply_transition(img, kind_in, "in", (f + 1) / (n + 1))
    if kind_out:
        n = TRANS_FRAMES[kind_out][0]
        if f >= frames - n:
            img = apply_transition(img, kind_out, "out", (f - (frames - n) + 1) / (n + 1))
    return img


# ---------------------------------------------------------------- timeline of sound events


AMBIENCE = {
    "battle": r"attack|firing|fires? at|explod|explosion|artillery|bomb|shell|skirmish|charg|fighting|war-torn|"
              r"muzzle|invasion|tracer|dogfight|air raid|pounded|tanks rolling|bazooka|fighters?",
    "wind": r"snow|blizzard|frozen|winter|icy|frost|steppe|bare hill",
    "rain": r"\brain|monsoon",
    "sea": r"\bsea\b|harbou?r|\bship|strait|waves|tidal|ocean|landing boats|coast|warships",
    "fire": r"burning|fireball|flames|on fire|smoke rising|smouldering",
    "crowd": r"crowd|parade|refugees|cheering|ticker-tape|marching|celebrat",
    "factory": r"factory|assembly line|industrial|chimneys",
}


def shot_ambience(shot):
    text = f"{shot.get('prompt', '')} {shot.get('flow', '')}".lower()
    found = [k for k, rx in AMBIENCE.items() if re.search(rx, text)]
    return found[:2]


def sound_events(scene_plans, scene_starts, scene_lengths, kinds_in, art_dir=None):
    """scene_plans: per scene [(shot, start, dur)] (doodle.scene_shots). Returns a list of events."""
    ev = []
    for si, (plan, t0, length) in enumerate(zip(scene_plans, scene_starts, scene_lengths)):
        if si > 0:
            ev.append({"t": t0, "kind": "trans_" + kinds_in[si]})
        for k, (shot, start, dur) in enumerate(plan or []):
            g0 = t0 + start
            if k > 0:
                ev.append({"t": g0, "kind": "cut"})
            for amb in shot_ambience(shot):
                ev.append({"t": g0, "kind": "bed_" + amb, "dur": dur})
            img = shot.get("_img_path") or shot.get("img")
            if img:
                clip = Path(img).with_suffix(".mp4")
                if clip.exists():
                    ev.append({"t": g0, "kind": "clip", "path": str(clip), "dur": dur})
            for it in shot.get("items", []):
                ti = g0 + it.get("in", 0) * dur
                if ti >= t0 + length:
                    continue
                if "label" in it:
                    ev.append({"t": ti, "kind": "pop"})
                elif "stamp" in it:
                    ev.append({"t": ti, "kind": "type", "n": len(it["stamp"])})
                elif "title" in it:
                    ev.append({"t": ti, "kind": "boom"})
                elif "pin" in it:
                    ev.append({"t": ti, "kind": "ping"})
                elif "flash" in it:
                    ev.append({"t": ti, "kind": "hit"})
            for j in shot.get("jolts", []):
                ev.append({"t": g0 + j * dur, "kind": "thud"})
    return ev


# ---------------------------------------------------------------- synthesis helpers


def _noise(n, rng, color="white"):
    x = rng.standard_normal(n).astype(np.float32)
    if color == "white":
        return x
    spec = np.fft.rfft(x)
    f = np.maximum(np.fft.rfftfreq(n, 1 / SR), 20.0)
    spec /= np.sqrt(f) if color == "pink" else f
    y = np.fft.irfft(spec, n).astype(np.float32)
    return y / (np.abs(y).max() + 1e-9)


def _band(x, lo, hi):
    """FFT band-pass with soft edges."""
    n = len(x)
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    gain = np.ones_like(f)
    if lo:
        gain *= 1 / (1 + (lo / np.maximum(f, 1)) ** 4)
    if hi:
        gain *= 1 / (1 + (f / hi) ** 4)
    return np.fft.irfft(spec * gain, n).astype(np.float32)


def _env(n, attack, release):
    e = np.ones(n, np.float32)
    a, r = min(n, int(attack * SR)), min(n, int(release * SR))
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r) ** 2
    return e


def _decay(n, tau):
    return np.exp(-np.arange(n) / (tau * SR)).astype(np.float32)


def _norm(x, peak=1.0):
    return (x / (np.abs(x).max() + 1e-9) * peak).astype(np.float32)


def sfx(kind, rng):
    """One-shot sound (mono float32) for an event kind."""
    if kind in ("trans_whip", "cut"):
        dur = 0.55 if kind == "trans_whip" else 0.32
        n = int(dur * SR)
        x = _noise(n, rng, "pink")
        t = np.linspace(0, 1, n)
        # sweep a band-pass up then down by filtering in short blocks
        out = np.zeros(n, np.float32)
        blk = 1024
        for b in range(0, n, blk):
            c = 400 + 3800 * math.sin(math.pi * min(1, b / n)) ** 2
            out[b:b + blk] = _band(x[b:b + blk + 0], c * 0.5, c * 1.6)[:len(out[b:b + blk])]
        env = np.sin(np.pi * t) ** 2.5
        return _norm(out * env, 0.9 if kind == "trans_whip" else 0.35)
    if kind == "trans_zoom":
        a = sfx("trans_whip", rng)
        b = sfx("thud", rng) * 0.8
        out = np.zeros(len(a) + len(b), np.float32)
        out[:len(a)] += a
        out[int(len(a) * 0.55):int(len(a) * 0.55) + len(b)] += b
        return _norm(out, 0.9)
    if kind in ("boom", "trans_flash", "hit", "trans_dip"):
        n = int(2.2 * SR)
        t = np.arange(n) / SR
        f = 55 * np.exp(-t * 1.5) + 32
        body = np.sin(2 * np.pi * np.cumsum(f) / SR) * _decay(n, 0.55)
        crack = _band(_noise(n, rng), 80, 2500) * _decay(n, 0.08)
        tail = _band(_noise(n, rng, "brown"), 20, 300) * _decay(n, 0.9) * 0.6
        out = body + 0.5 * crack + tail
        if kind == "trans_dip":
            out = body * 0.7 + tail
        return _norm(out, 0.95 if kind != "hit" else 0.8)
    if kind == "thud":
        n = int(0.6 * SR)
        t = np.arange(n) / SR
        out = np.sin(2 * np.pi * (70 * t - 20 * t * t)) * _decay(n, 0.12) + \
            0.4 * _band(_noise(n, rng), 60, 900) * _decay(n, 0.04)
        return _norm(out, 0.7)
    if kind == "pop":
        n = int(0.18 * SR)
        t = np.arange(n) / SR
        f0 = rng.uniform(520, 700)
        out = np.sin(2 * np.pi * (f0 * t + 900 * t * t)) * _decay(n, 0.035) + \
            0.3 * _band(_noise(n, rng), 1500, 6000) * _decay(n, 0.006)
        return _norm(out, 0.45)
    if kind == "tick":
        n = int(0.05 * SR)
        out = _band(_noise(n, rng), 1800, 7000) * _decay(n, 0.006) + \
            np.sin(2 * np.pi * rng.uniform(1900, 2400) * np.arange(n) / SR) * _decay(n, 0.01) * 0.4
        return _norm(out, 0.32)
    if kind == "ping":
        n = int(1.4 * SR)
        t = np.arange(n) / SR
        out = (np.sin(2 * np.pi * 1320 * t) + 0.3 * np.sin(2 * np.pi * 2640 * t)) * _decay(n, 0.35)
        return _norm(out * _env(n, 0.004, 0.2), 0.3)
    return np.zeros(1, np.float32)


def bed(kind, n, rng):
    """Looping ambience (mono float32, peak ~1) of n samples."""
    t = np.arange(n) / SR
    if kind == "wind":
        x = _band(_noise(n, rng, "pink"), 150, 1400)
        lfo = 0.55 + 0.45 * np.sin(2 * np.pi * 0.09 * t + rng.uniform(0, 6)) * np.sin(2 * np.pi * 0.23 * t)
        return _norm(x * lfo)
    if kind == "rain":
        x = _band(_noise(n, rng), 2500, 11000) * 0.6
        drops = np.zeros(n, np.float32)
        idx = rng.integers(0, n, size=int(n / SR * 60))
        drops[idx] = rng.uniform(0.3, 1.0, len(idx))
        drops = _band(drops, 1500, 8000) * 6
        return _norm(x + drops)
    if kind == "sea":
        x = _band(_noise(n, rng, "pink"), 60, 900)
        swell = 0.35 + 0.65 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t + rng.uniform(0, 6))) ** 2
        return _norm(x * swell)
    if kind == "battle":
        out = _band(_noise(n, rng, "brown"), 20, 400) * 0.25
        tt = rng.uniform(0.2, 1.5)
        while tt < n / SR:  # distant booms
            b = sfx("boom", rng)
            b = _band(b, 20, 500) * rng.uniform(0.3, 0.8)
            i = int(tt * SR)
            m = min(len(b), n - i)
            out[i:i + m] += b[:m]
            if rng.random() < 0.5:  # a burst of small-arms fire
                for _ in range(rng.integers(3, 9)):
                    i += int(rng.uniform(0.06, 0.14) * SR)
                    s = sfx("tick", rng) * rng.uniform(0.6, 1.4)
                    s = _band(np.concatenate([s, np.zeros(2000, np.float32)]), 300, 4000) * 2.5
                    m = min(len(s), n - i)
                    if m > 0:
                        out[i:i + m] += s[:m]
            tt += rng.uniform(1.2, 3.5)
        return _norm(out)
    if kind == "fire":
        x = _band(_noise(n, rng, "brown"), 30, 600) * 0.5
        cr = np.zeros(n, np.float32)
        idx = rng.integers(0, n, size=int(n / SR * 25))
        cr[idx] = rng.uniform(0.2, 1, len(idx))
        cr = _band(cr, 800, 6000) * 8
        return _norm(x + cr)
    if kind == "crowd":
        x = _band(_noise(n, rng, "pink"), 250, 2200)
        am = np.abs(_band(_noise(n, rng), 0, 7)) * 6 + 0.4  # syllable-rate wobble
        return _norm(x * am)
    if kind == "factory":
        out = _band(_noise(n, rng, "brown"), 30, 300) * 0.4
        period = rng.uniform(0.7, 1.1)
        for k in range(int(n / SR / period)):
            i = int((k * period + rng.uniform(-0.03, 0.03)) * SR)
            m = min(int(0.5 * SR), n - i)
            if m <= 0:
                break
            tt = np.arange(m) / SR
            clank = sum(np.sin(2 * np.pi * f * tt) for f in (410, 667, 1130, 1790)) * _decay(m, 0.06)
            out[i:i + m] += clank * 0.25
        return _norm(out)
    return np.zeros(n, np.float32)


BED_GAIN = {"wind": 0.10, "rain": 0.09, "sea": 0.10, "battle": 0.16, "fire": 0.08, "crowd": 0.07, "factory": 0.08}
SFX_GAIN = {"trans_whip": 0.32, "trans_zoom": 0.38, "trans_flash": 0.30, "trans_dip": 0.22, "cut": 0.10,
            "pop": 0.22, "tick": 0.20, "boom": 0.34, "hit": 0.30, "ping": 0.16, "thud": 0.22}


def _read_clip_audio(path):
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def render_effects(events, total_s, seed=7):
    """Stereo float32 array [n, 2] with every sound effect, bed and clip sound placed."""
    rng = np.random.default_rng(seed)
    n = int(total_s * SR) + SR
    out = np.zeros((n, 2), np.float32)

    def place(x, t, gain, pan=0.0):
        i = int(t * SR)
        if i >= n or i + len(x) <= 0:
            return
        x = x[: n - i]
        l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
        out[i:i + len(x), 0] += x * gain * l * 1.41
        out[i:i + len(x), 1] += x * gain * r * 1.41

    cache = {}
    for e in events:
        k = e["kind"]
        if k.startswith("bed_"):
            kind = k[4:]
            m = int((e["dur"] + 0.8) * SR)
            key = (kind, m)
            if key not in cache:
                cache[key] = bed(kind, m, rng)
            x = cache[key][:m] * _env(m, 0.6, 0.9)
            place(x, max(0, e["t"] - 0.3), BED_GAIN[kind], rng.uniform(-0.3, 0.3))
        elif k == "clip":
            x = _read_clip_audio(e["path"])
            m = min(len(x), int(e["dur"] * SR))
            if m > SR // 10:
                x = x[:m] * _env(m, 0.05, min(1.0, m / SR / 3))
                place(_norm(x, 1.0) if np.abs(x).max() > 0.01 else x, e["t"], 0.30)
        elif k == "type":
            for c in range(e["n"]):
                if rng.random() < 0.85:
                    place(sfx("tick", rng), e["t"] + 1.2 * c / max(1, e["n"]), SFX_GAIN["tick"], -0.4)
        else:
            x = sfx(k, rng)
            pan = rng.uniform(-0.5, 0.5) if k in ("pop", "ping") else 0.0
            if k in ("trans_whip", "trans_zoom"):
                place(x, e["t"] - 0.28, SFX_GAIN[k], 0.0)
            else:
                place(x, e["t"], SFX_GAIN.get(k, 0.2), pan)
    return out


# ---------------------------------------------------------------- music bed

# D minor world: each scene holds one chord, crossfaded; root notes in Hz
CHORDS = [[146.83, 174.61, 220.00], [116.54, 146.83, 174.61], [130.81, 164.81, 196.00], [110.00, 130.81, 164.81],
          [146.83, 174.61, 220.00], [98.00, 116.54, 146.83], [116.54, 146.83, 174.61], [110.00, 138.59, 164.81]]


def music_bed(scene_starts, total_s, seed=3):
    """Dark, slow synth pad (stereo float32, peak ~0.5): one chord per scene, 3 s crossfades."""
    rng = np.random.default_rng(seed)
    n = int(total_s * SR) + SR
    out = np.zeros((n, 2), np.float32)
    bounds = list(scene_starts) + [total_s + 1]
    for si in range(len(scene_starts)):
        a, b = max(0.0, bounds[si] - 1.5), bounds[si + 1] + 1.5
        i0, i1 = int(a * SR), min(n, int(b * SR))
        m = i1 - i0
        if m <= 0:
            continue
        t = np.arange(m) / SR + a
        chord = CHORDS[si % len(CHORDS)] + [CHORDS[si % len(CHORDS)][0] / 2]
        seg = np.zeros((m, 2), np.float32)
        for ni, f0 in enumerate(chord):
            for side, det in ((0, -0.18), (1, 0.21)):
                f = f0 + det * (1 + ni * 0.3)
                ph = rng.uniform(0, 6.28)
                tone = sum(np.sin(2 * np.pi * f * h * t + ph * h) / h ** 1.6 for h in range(1, 6))
                trem = 0.75 + 0.25 * np.sin(2 * np.pi * (0.05 + 0.02 * ni) * t + ph)
                seg[:, side] += (tone * trem).astype(np.float32) * (1.4 if f0 < 80 else 1.0)
        env = _env(m, 1.5 if si else 4.0, 3.0)
        out[i0:i1] += seg * env[:, None]
    # gentle low-pass for warmth
    for c in range(2):
        out[:, c] = _band(out[:, c], 0, 1800)
    return _norm(out, 0.5)


def duck(music, voice_env, depth=0.5):
    """Lower the music where the narrator speaks. voice_env: per-sample 0..1 at SR."""
    m = min(len(music), len(voice_env))
    g = 1 - depth * voice_env[:m]
    music[:m] *= g[:, None]
    return music


def voice_envelope(voice, rate, n_out):
    """Smoothed 0..1 loudness envelope of the narration, resampled to SR."""
    hop = int(rate * 0.05)
    k = len(voice) // hop
    rms = np.sqrt(np.mean(voice[: k * hop].reshape(k, hop) ** 2, axis=1))
    rms = np.minimum(1, rms / (np.percentile(rms, 95) + 1e-9))
    # hold + smooth (attack fast, release ~0.6 s)
    sm = np.zeros_like(rms)
    v = 0.0
    for i, x in enumerate(rms):
        v = x if x > v else v * 0.92
        sm[i] = v
    src_t = (np.arange(k) + 0.5) * hop / rate
    return np.interp(np.arange(n_out) / SR, src_t, sm).astype(np.float32)


def read_wav(path):
    with wave.open(str(path)) as w:
        rate, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw == 2:
        x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    elif sw == 4:
        x = np.frombuffer(raw, np.int32).astype(np.float32) / 2 ** 31
    else:
        raise ValueError(f"{path}: {sw * 8}-bit wav not supported")
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, rate


def write_wav(path, stereo):
    x = np.clip(stereo, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def background_track(voice_wav, events, scene_starts, total_s, out_wav, music=True):
    """Music (ducked) + effects -> one stereo wav to mix under the narration."""
    voice, rate = read_wav(voice_wav)
    fx = render_effects(events, total_s)
    env = voice_envelope(voice, rate, len(fx))
    fx_duck = 1 - 0.35 * env  # effects and beds step back a little under speech
    fx *= fx_duck[:, None]
    if music:
        mus = duck(music_bed(scene_starts, total_s), env, 0.55)
        m = min(len(mus), len(fx))
        fx[:m] += mus[:m] * 0.16
    write_wav(out_wav, fx)
    return out_wav


# ---------------------------------------------------------------- captions


def scene_words(text, seconds, timed=None):
    """[(word, start, end)] for one scene. timed = Kokoro word timings if available, else spread by length."""
    words = text.split()
    if timed:
        # Kokoro tokens -> match to the script words in order (punctuation tokens dropped)
        toks = [w for w in timed if re.search(r"\w", w[0])]
        if toks and abs(len(toks) - len(words)) <= max(2, len(words) // 10):
            out, j = [], 0
            for w in words:
                if j < len(toks):
                    out.append((w, toks[j][1], toks[j][2]))
                    j += 1
                else:
                    out.append((w, out[-1][2], out[-1][2] + 0.25))
            return out
    weights = [len(re.sub(r"\W", "", w)) + 1.5 + (2.5 if re.search(r"[.!?]$", w) else 1.0 if w.endswith(",") else 0)
               for w in words]
    tot = sum(weights) or 1
    out, t = [], 0.0
    for w, wt in zip(words, weights):
        d = seconds * wt / tot
        out.append((w, t, t + d * 0.92))
        t += d
    return out


def caption_chunks(words, max_words=3, max_chars=22):
    """Group (word, start, end) into 1-3 word chunks, breaking after punctuation."""
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        text = " ".join(x[0] for x in cur)
        if len(cur) >= max_words or len(text) >= max_chars or re.search(r"[.,!?;:—]$", w[0]):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def busy_bands(scene_plans, scene_starts, scene_lengths):
    """[(start, end, top_y)] for overlays drawn into the bottom caption band of a 16:9 frame."""
    out = []
    for plan, t0, length in zip(scene_plans, scene_starts, scene_lengths):
        for shot, start, dur in plan or []:
            for it in shot.get("items", []):
                if "stamp" in it:
                    y, half = it.get("y", 960), it.get("size", 54) * 0.8
                elif "label" in it:
                    y, half = it.get("y", 160), it.get("size", 80) * 0.75 + 4
                elif "title" in it:
                    sz = it.get("size", 170)
                    y, half = it.get("y", 200), sz * 0.6 + (sz * 0.85 + it.get("sub_size", 70) if it.get("sub") else 0)
                elif "pin" in it:
                    y, half = it.get("y", 540), 34
                else:
                    continue
                if y + half < 905:
                    continue
                a = t0 + start + it.get("in", 0) * dur
                b = min(t0 + length, t0 + start + it.get("out", 1.01) * dur)
                if b > a:
                    out.append((a, b, y - half))
    return out


def _ass_time(t):
    cs = int(round(max(0, t) * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _clean(w):
    return re.sub(r"[{}\\]", "", w).upper()


def write_ass(all_words, path, vertical=False, busy=()):
    """Karaoke captions: the chunk on screen, the word being spoken in yellow, a small pop per chunk."""
    W, H = (1080, 1920) if vertical else (1920, 1080)
    size, outline, y = (84, 7, 1520) if vertical else (66, 6, 1000)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 2\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
            "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Cap,DejaVu Sans,{size},&H00FFFFFF,&H00FFFFFF,&H00141414,&H96000000,1,0,0,0,100,100,1,0,1,"
            f"{outline},3,2,60,60,40,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
            "MarginV, Effect, Text\n")
    lines = []
    chunks = caption_chunks(all_words, 2 if vertical else 3, 16 if vertical else 22)
    for ci, ch in enumerate(chunks):
        c_end = ch[-1][2]
        nxt = chunks[ci + 1][0][1] if ci + 1 < len(chunks) else c_end + 0.6
        if nxt - c_end < 0.7:
            c_end = nxt  # no flicker between close chunks
        tops = [top for a, b, top in busy if a < c_end and b > ch[0][1]]
        yy = y if not tops else max(560, int(min(tops)) - 22)  # step above overlays in the bottom band
        for wi, (w, s, e) in enumerate(ch):
            s0 = ch[0][1] if wi == 0 else s
            e0 = ch[wi + 1][1] if wi + 1 < len(ch) else c_end
            if e0 <= s0:
                continue
            parts = []
            for k, (x, _, _) in enumerate(ch):
                parts.append("{\\c&H00D7FF&}" + _clean(x) + "{\\c&HFFFFFF&}" if k == wi else _clean(x))
            pop = "{\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 else ""
            lines.append(f"Dialogue: 0,{_ass_time(s0)},{_ass_time(e0)},Cap,,0,0,0,,"
                         f"{{\\an2\\pos({W // 2},{yy})}}{pop}{' '.join(parts)}")
    Path(path).write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    return path


def load_word_timings(vo_dir, scene_id):
    f = Path(vo_dir) / f"{scene_id}.words.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            return None
    return None

"""Automatic first edit: art + voiceover -> captioned video, subtitles and YouTube chapters.

Usage:
    python tools/assemble.py episodes/EP001-korean-war/script.md            # 16:9 episode
    python tools/assemble.py episodes/EP001-korean-war/shorts/short1.md --vertical

Needs: ffmpeg on PATH, Pillow, and the voiceover from make_voiceover.py (folder vo_<script name>
next to the script, one S01.wav ... per scene).

Art: put images in an "art" folder next to the episode script, named after the scene they belong to:
art/S04.png, art/S04_b.jpg, art/S04_c.png ... Several images per scene share its time, each with a slow
push-in or pan. A scene with no image gets a paper title card, so the video always renders.
A Shorts script can borrow episode art with {art: S12, S05} in a scene header.

Output (folder "out" next to the script): <name>.mp4, <name>.srt (captions to upload to YouTube),
<name>_chapters.txt (paste into the description). Shorts get captions burned in.
"""
import argparse
import math
import json
import re
import subprocess
import tempfile
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

PAUSE = 0.6  # must match make_voiceover.PAUSE_BETWEEN_SCENES
FPS = 25
PAPER = (243, 236, 220)
INK = (24, 22, 20)
RED = (190, 30, 30)
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}
NO_CHAPTER = {"PATTERN INTERRUPT", "INTRO"}
FONT_DIRS = ["/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts", "/Library/Fonts", "/System/Library/Fonts/Supplemental"]


def parse_script(path: Path):
    """Scenes as dicts: id, title, art (borrowed scene ids), text (what is read aloud)."""
    text = path.read_text(encoding="utf-8").split("## Sources")[0]
    scenes = []
    for m in re.finditer(r"\[(S\d+)\]([^\n]*)\n(.*?)(?=\n\s*\[S\d+\]|\n---|\Z)", text, re.S):
        header = m.group(2)
        art = re.search(r"\{art:\s*([^}]*)\}", header)
        title = re.sub(r"\{[^}]*\}", "", header).strip()
        body = re.sub(r"\s*\[VERIFY[^\]]*\]", "", m.group(3)).strip()
        if body:
            scenes.append({"id": m.group(1), "title": title,
                           "art": [a.strip() for a in art.group(1).split(",")] if art else [],
                           "text": body})
    return scenes


def wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def chunk_captions(text: str, max_words: int) -> list[str]:
    """Sentences, long ones split at commas or every max_words words."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", text):
        words, cur = sent.split(), []
        for w in words:
            cur.append(w)
            if len(cur) >= max_words or (w.endswith(",") and len(cur) >= max_words // 2):
                out.append(" ".join(cur))
                cur = []
        if cur:
            if len(cur) < 4 and out and len(words) > len(cur):  # no orphan tails like "inches wide."
                out[-1] += " " + " ".join(cur)
            else:
                out.append(" ".join(cur))
    return out


def fmt_srt(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def fmt_chapter(t: float) -> str:
    s = int(t)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def timeline(scenes, durations, max_words=12):
    """Start time of each scene, captions (start, end, text) and chapter lines."""
    t, starts, caps, chapters = 0.0, [], [], []
    for sc, d in zip(scenes, durations):
        starts.append(t)
        chunks = chunk_captions(sc["text"], max_words)
        total = sum(len(c) for c in chunks) or 1
        c0 = t
        for c in chunks:
            c1 = c0 + d * len(c) / total
            caps.append((c0, c1, c))
            c0 = c1
        title = sc["title"].split("—")[-1].strip().title() if "—" in sc["title"] else sc["title"].title()
        if not chapters:
            chapters.append(f"0:00 Intro")
        elif sc["title"].upper() not in NO_CHAPTER:
            chapters.append(f"{fmt_chapter(t)} {title}")
        t += d + PAUSE
    return starts, caps, chapters


def font(size: int, bold=True):
    names = ["DejaVuSerif-Bold.ttf", "georgiab.ttf", "Georgia Bold.ttf"] if bold else ["DejaVuSerif.ttf", "georgia.ttf"]
    for d in FONT_DIRS:
        for n in names:
            p = Path(d) / n
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def title_card(title: str, size: tuple[int, int], path: Path):
    """Paper card with the scene title in ink and a red underline (stand-in until art exists)."""
    w, h = size
    img = Image.new("RGB", size, PAPER)
    noise = Image.effect_noise(size, 18).convert("L").filter(ImageFilter.GaussianBlur(1))
    img = Image.composite(img, Image.new("RGB", size, (228, 219, 198)), noise.point(lambda v: 255 if v > 110 else 200))
    d = ImageDraw.Draw(img)
    label = title.split("—")[-1].strip() if "—" in title else title
    kicker = title.split("—")[0].strip() if "—" in title else ""
    f = font(int(w * 0.055))
    lines, line = [], ""
    for word in label.split():
        test = (line + " " + word).strip()
        if d.textlength(test, font=f) > w * 0.8 and line:
            lines.append(line)
            line = word
        else:
            line = test
    lines.append(line)
    y = h * 0.42 - len(lines) * f.size * 0.6
    if kicker:
        fk = font(int(w * 0.03))
        d.text((w / 2, y - fk.size * 1.6), kicker, font=fk, fill=RED, anchor="mm")
    for ln in lines:
        d.text((w / 2, y), ln, font=f, fill=INK, anchor="mm")
        y += f.size * 1.2
    d.line([(w * 0.35, y), (w * 0.65, y)], fill=RED, width=max(4, w // 240))
    img.save(path)


def scene_images(sc, art_dirs):
    ids = sc["art"] or [sc["id"]]
    found = []
    for sid in (i.rstrip("!") for i in ids):
        for d in art_dirs:
            if d.is_dir():
                found += sorted(p for p in d.iterdir() if p.suffix.lower() in IMG_EXT
                                and re.match(rf"{sid}(?![0-9])", p.stem, re.I))
    return found


def ken_burns(img: Path, seconds: float, size: tuple[int, int], move: int, out: Path):
    """One still -> clip with a slow push-in or pan (cover-fit to the frame)."""
    w, h = size
    frames = max(1, round(seconds * FPS))
    big_w, big_h = int(w * 1.25), int(h * 1.25)
    cover = f"scale={big_w}:{big_h}:force_original_aspect_ratio=increase,crop={big_w}:{big_h}"
    p = f"on/{frames}"
    z, x, y = [
        (f"1+0.12*{p}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),            # push in
        (f"1.12-0.12*{p}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),         # pull out
        ("1.1", f"(iw-iw/zoom)*{p}", "ih/2-(ih/zoom/2)"),                   # pan right
        ("1.1", f"(iw-iw/zoom)*(1-{p})", "ih/2-(ih/zoom/2)"),               # pan left
    ][move % 4]
    vf = f"{cover},zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps={FPS},format=yuv420p"
    run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(img), "-vf", vf,
         "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", str(out)])


def run(cmd):
    subprocess.run(cmd, check=True)


def write_srt(caps, path: Path):
    path.write_text("".join(f"{i}\n{fmt_srt(a)} --> {fmt_srt(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(caps, 1)),
                    encoding="utf-8")


def spec_dir(script: Path) -> Path:
    """Episode folder (Shorts live in <episode>/shorts/)."""
    return script.parent.parent if script.parent.name == "shorts" else script.parent


def load_spec(script: Path):
    """animation.yaml next to the episode script (Shorts use their episode's)."""
    for d in (script.parent, script.parent.parent):
        f = d / "animation.yaml"
        if f.exists():
            import yaml
            return yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return {}


def scene_spec(sc, spec, art_dir=None):
    ids = sc["art"] or [sc["id"]]
    shots = []
    for sid in ids:
        bare = sid.endswith("!")  # "S10.1!" = that picture without its overlays (labels from another context)
        sid = sid.rstrip("!")
        base, _, idx = sid.partition(".")  # "S10.4" = 4th shot of scene S10 only
        v = spec.get(base)
        if v:
            v = v if isinstance(v, list) else [v]
            if idx.isdigit() and 0 < int(idx) <= len(v):
                v = [v[int(idx) - 1]]
                v = [{k: x for k, x in v[0].items() if k != "at"}]
            shots += [dict(s, items=[]) if bare else dict(s) for s in v]
    for s in shots:  # pictures live in the episode's art/ folder; 9:16 versions for Shorts in art_916/
        if "img" in s:
            s["_img_path"] = str(art_dir / s["img"]) if art_dir else s["img"]
            v = art_dir.parent / "art_916" / s["img"] if art_dir else None
            if v and (v.exists() or v.with_suffix(".mp4").exists()):
                s["_img916"] = str(v)
    if len(ids) > 1:  # borrowed from several scenes: equal split
        for s in shots:
            s.pop("at", None)
    return shots or None


CUT_S = 1.8  # Shorts: longest time on one picture or framing before a cut
LONG_CUT_S = 4.0  # long episodes: same idea, a new picture or framing at least every ~4 s
CUT_MOVES = [("push", [0.5, 0.42]), ("pan_left", [0.5, 0.5]), ("pull", [0.45, 0.4]), ("pan_right", [0.5, 0.55]),
             ("push", [0.6, 0.6]), ("pan_up", [0.5, 0.5])]


SPOT_ITEMS = ("pin", "label", "arrow")  # overlays tied to a spot in their own picture


def fast_cuts(shots, seconds, max_s=CUT_S, extras=False):
    """Split every shot longer than max_s into pieces with different framings, so the picture changes every
    ~max_s seconds. Overlays stay where they were in time; later pieces show them without a new pop or sound.
    extras=True: a shot's `also:` pictures (art/<img>, when the file exists) fill alternate pieces; those pieces
    keep stamps and titles only, and a piece where a label or pin pops in stays on the original picture."""
    import doodle
    plan = doodle.scene_shots(shots, seconds)
    out, n_cut = [], 0
    for shot, start, dur in plan:
        n = max(1, math.ceil(dur / max_s - 0.15))
        alts = []
        if extras and shot.get("_img_path"):
            art = Path(shot["_img_path"]).parent
            alts = [x.get("img") if isinstance(x, dict) else x for x in shot.get("also", [])]
            alts = [x for x in alts if x and ((art / x).exists() or (art / x).with_suffix(".mp4").exists())]
        n_alt = 0
        for k in range(n):
            a, b = start + dur * k / n, start + dur * (k + 1) / n
            piece = dict(shot, at=a / seconds)
            if k:
                mv, focus = CUT_MOVES[(n_cut + k) % len(CUT_MOVES)]
                piece.update(move=mv, focus=focus, amount=1.3, jolts=[], _cont=True, _t0=a - start)
                piece["_quiet"] = extras  # long episodes: a reframe of the same picture cuts without a whoosh
            else:
                piece["_span"] = dur
                piece["jolts"] = [j * dur / (b - a) for j in shot.get("jolts", []) if j * dur < b - a]
            items = []
            for it in shot.get("items", []):
                t_in, t_out = it.get("in", 0) * dur, it.get("out", 1.01) * dur
                if t_out <= a - start or (t_in >= b - start):
                    continue
                if t_in >= a - start:  # starts in this piece: normal pop-in
                    items.append(dict(it, **{"in": (t_in - (a - start)) / (b - a)},
                                      out=(t_out - (a - start)) / (b - a)))
                else:  # already on screen: stays, no new pop
                    items.append(dict(it, **{"in": -1.0}, out=(t_out - (a - start)) / (b - a)))
            spot_pops = any(any(t in it for t in SPOT_ITEMS) and it["in"] >= 0 for it in items)
            if k % 2 and alts and not spot_pops:  # cut away to another picture of the same moment
                img = alts[n_alt % len(alts)]
                n_alt += 1
                piece.update(img=img, _img_path=str(Path(shot["_img_path"]).parent / img), _t0=0.0,
                             flow=None, prompt="")
                piece.pop("_img916", None)
                piece["_quiet"] = False
                items = [it for it in items if not any(t in it for t in SPOT_ITEMS)]
            piece["items"] = items
            out.append(piece)
        n_cut += n
    return out


def short_title(script: Path):
    m = re.search(r"^Title:\s*(.+)$", script.read_text(encoding="utf-8"), re.M)
    return re.sub(r"\s*#\w+", "", m.group(1)).strip() if m else ""


def title_lines(title, size=84, width=980):
    import doodle
    lines, cur = [], ""
    for wd in title.split():
        if doodle.font(size).getlength((cur + " " + wd).strip()) > width and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    return lines + [cur] if cur else lines


def vertical_title(img, title, frame):
    """Short title over a full-screen picture: white with a heavy outline on a soft dark band at the top."""
    import doodle
    from PIL import ImageDraw
    size = 76
    lines = title_lines(title, size)
    while len(lines) > 3 and size > 52:
        size -= 6
        lines = title_lines(title, size)
    band = Image.new("L", (1, 520))
    band.putdata([int(150 * max(0, 1 - y / 520) ** 1.6) for y in range(520)])
    shade = Image.new("RGB", (1080, 520), (0, 0, 0))
    img.paste(shade, (0, 0), band.resize((1080, 520)))
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines[:3]):
        d.text((540, 200 + i * size * 1.18 - (len(lines[:3]) - 1) * size * 0.3), ln, font=doodle.font(size),
               fill=(255, 255, 255), anchor="mm", stroke_width=max(4, size // 12), stroke_fill=(20, 20, 20))


CTA_S = 3.2  # seconds of end card at the end of a Short
BRAND = Path(__file__).resolve().parent.parent / "brand"
LOGO = BRAND / "logo_round.png"  # round channel logo (Shorts end card)
END_S = 12.0  # long episodes: silent end screen (channel banner) for YouTube's end-screen elements


def end_screen(final, tmp):
    """Append END_S seconds of the channel banner (slow push-in, fade from black) to a long episode, so YouTube's
    end-screen elements (subscribe + next video) sit on the brand instead of covering the last narration."""
    banner = BRAND / "banner_1920.jpg"
    if not banner.exists():
        return final
    slate = tmp / "endscreen.mp4"
    n = round(END_S * FPS)
    vf = (f"scale=2112:1188,zoompan=z='min(1.0+on/{n}*0.05,1.05)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':"
          f"d={n}:s=1920x1080:fps={FPS},fade=t=in:st=0:d=0.8,format=yuv420p")
    run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(banner), "-f", "lavfi", "-i",
         "anullsrc=r=44100:cl=stereo", "-vf", vf, "-t", f"{END_S}", "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
         str(slate)])
    body = tmp / "body.mp4"
    final.replace(body)
    (tmp / "end_list.txt").write_text(f"file '{body}'\nfile '{slate}'\n")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "end_list.txt"),
         "-c", "copy", "-movflags", "+faststart", str(final)])
    return final


def end_card(img, life):
    """Short end card: 'FULL EPISODE' box and an arrow bouncing down at the related-video link (bottom left)."""
    import math
    import doodle
    from PIL import ImageDraw
    k = min(1.0, life / 0.25)
    s = 1 + 0.2 * math.sin(k * math.pi) if k < 1 else 1
    shade = Image.new("RGB", img.size, (0, 0, 0))
    img.paste(Image.blend(img, shade, 0.35 * k))
    d = ImageDraw.Draw(img)
    w, h = int(860 * s), int(330 * s)
    x0, y0 = 540 - w // 2, 870 - h // 2
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], 34, fill=(20, 20, 20), outline=(255, 210, 0), width=10)
    d.text((540, y0 + h * 0.36), "FULL EPISODE", font=doodle.font(int(110 * s)), fill=(255, 210, 0), anchor="mm",
           stroke_width=5, stroke_fill=(20, 20, 20))
    d.text((540, y0 + h * 0.74), "TAP THE LINK BELOW", font=doodle.font(int(62 * s)), fill=(255, 255, 255),
           anchor="mm")
    if LOGO.exists():  # channel logo above the box
        logo = Image.open(LOGO).convert("RGBA")
        r = int(250 * s)
        logo = logo.resize((r, r), Image.LANCZOS)
        img.paste(logo, (540 - r // 2, y0 - r - 30), logo)
    bob = 26 * math.sin(life * 9)
    ax, ay = 150, 1250 + bob
    d.rectangle([ax - 26, ay - 170, ax + 26, ay], fill=(255, 210, 0), outline=(20, 20, 20), width=6)
    d.polygon([(ax - 80, ay - 10), (ax + 80, ay - 10), (ax, ay + 110)], fill=(255, 210, 0), outline=(20, 20, 20),
              width=6)


def render_anim(job):
    """Worker: one scene's animation -> mp4 segment (silent). job = dict, see build()."""
    import doodle
    import numpy as np
    import polish
    shots, seconds, wav, out, vertical, title = (job[k] for k in ("shots", "seconds", "wav", "out", "vertical", "title"))
    t_in, t_out = job.get("trans_in"), job.get("trans_out")
    frames = max(1, round(seconds * FPS))
    with wave.open(wav) as w:
        samples = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        rate = w.getframerate()
    talk = doodle.loudness(samples, rate, frames)
    plan = doodle.scene_shots(shots, seconds)
    size = (1080, 1920) if vertical else (1920, 1080)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{size[0]}x{size[1]}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                           "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    frame0 = job["frame0"]
    for f in range(frames):
        t = f / FPS
        shot, start, dur = next((x for x in reversed(plan) if t >= x[1]), plan[0])
        native = vertical and shot.get("_img916")
        if native:  # full-screen 9:16 picture, title drawn over it
            img = doodle.render_vertical_frame(shot, t - start, dur, frame0 + f)
            img = polish.frame_transition(img, f, frames, t_in, t_out)
            if title:
                vertical_title(img, title, frame0 + f)
        else:
            img = doodle.render_shot_frame(shot, t - start, dur, frame0 + f, talk[f])
            img = polish.frame_transition(img, f, frames, t_in, t_out)  # picture only; a Short's title stays still
        if vertical and not native:
            canvas = Image.new("RGB", size, doodle.C["paper"])
            canvas.paste(img.resize((1080, 810), Image.BILINEAR, box=(240, 0, 1680, 1080)), (0, 470))
            if title:
                tp = doodle.Pen(canvas, frame0 + f)
                words, lines, cur = title.split(), [], ""
                for wd in words:
                    if doodle.font(84).getlength((cur + " " + wd).strip()) > 980 and cur:
                        lines.append(cur)
                        cur = wd
                    else:
                        cur = (cur + " " + wd).strip()
                lines.append(cur)
                for i, ln in enumerate(lines[:3]):
                    tp.text(540, 230 + i * 100 - (len(lines) - 1) * 50, ln, 84, "ink")
            img = canvas
        if job.get("cta") and t >= seconds - CTA_S:
            end_card(img, t - (seconds - CTA_S))
        ff.stdin.write(img.tobytes())
    ff.stdin.close()
    if ff.wait():
        raise RuntimeError(f"ffmpeg failed for {out}")
    return out


def build(script: Path, vertical: bool = False, plain: bool = False):
    """plain=True: the old edit (hard cuts, voice only, no burned captions on the 16:9 video)."""
    import polish
    script = script.resolve()
    scenes = parse_script(script)
    vo = script.parent / f"vo_{script.stem}"
    durations = [wav_seconds(vo / f"{sc['id']}.wav") for sc in scenes]
    size = (1080, 1920) if vertical else (1920, 1080)
    out = script.parent / "out"
    out.mkdir(exist_ok=True)
    name = script.parent.name if script.stem == "script" else script.stem
    art_dirs = [script.parent / "art", script.parent.parent / "art"]
    starts, caps, chapters = timeline(scenes, durations, 6 if vertical else 12)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clips, move, report = [], 0, []
        spec = load_spec(script)
        jobs, frame0 = {}, 0
        kinds = [None] * len(scenes) if plain else polish.transition_plan(len(scenes))
        if vertical and not plain:
            kinds[0] = "zoom"  # Shorts open on a punch-in, not a fade from black
        plans = []
        # Shorts: the end card gets its own silent tail after the last line, so it never covers captions
        tail = CTA_S if vertical and not plain else 0.0
        spans = [d + PAUSE + (tail if i == len(scenes) - 1 else 0.0) for i, d in enumerate(durations)]
        for i, (sc, d) in enumerate(zip(scenes, durations)):
            shots = scene_spec(sc, spec, spec_dir(script) / "art")
            if vertical and not plain and i == 0 and shots:  # hook: the first picture lands with a shake
                shots[0] = dict(shots[0], jolts=[0.0] + list(shots[0].get("jolts", [])))
            if vertical and not plain and shots:  # fast cuts: a new picture or framing every ~1.5 s
                shots = fast_cuts(shots, spans[i])
            elif not plain and shots:  # long episode: a new picture or framing every ~4 s
                shots = fast_cuts(shots, spans[i], LONG_CUT_S, extras=True)
            plans.append(__import__("doodle").scene_shots(shots, spans[i]) if shots else [])
            if shots:
                jobs[sc["id"]] = {"shots": shots, "seconds": spans[i], "wav": str(vo / f"{sc['id']}.wav"),
                                  "out": str(tmp / f"{sc['id']}_anim.mp4"), "vertical": vertical,
                                  "title": short_title(script) if vertical and plain else "", "frame0": frame0,
                                  "cta": vertical and not plain and i == len(scenes) - 1,
                                  "trans_in": kinds[i],
                                  "trans_out": None if plain else (kinds[i + 1] if i + 1 < len(scenes) else "dip")}
            frame0 += round(spans[i] * FPS)
        if jobs:
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor() as ex:
                list(ex.map(render_anim, sorted(jobs.values(), key=lambda j: -j["seconds"])))
        for i, (sc, d) in enumerate(zip(scenes, durations)):
            if sc["id"] in jobs:
                clips.append(Path(jobs[sc["id"]]["out"]))
                report.append({"scene": sc["id"], "seconds": round(spans[i], 1), "images": ["animated"]})
                continue
            imgs = scene_images(sc, art_dirs)
            if not imgs:
                card = tmp / f"{sc['id']}_card.png"
                title_card(sc["title"], size, card)
                imgs = [card]
            span = spans[i]
            each = span / len(imgs)
            for k, img in enumerate(imgs):
                clip = tmp / f"{sc['id']}_{k}.mp4"
                ken_burns(img, each, size, move, clip)
                move += 1
                clips.append(clip)
            report.append({"scene": sc["id"], "seconds": round(span, 1), "images": [p.name for p in imgs]})
        (tmp / "list.txt").write_text("".join(f"file '{c}'\n" for c in clips))
        video = tmp / "video.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
             "-c", "copy", str(video)])
        srt = out / f"{name}.srt"
        write_srt(caps, srt)
        total = sum(spans)
        final = out / f"{name}.mp4"
        if plain:
            vf = []
            if vertical:  # burned-in captions for Shorts
                style = ("FontName=Comic Neue,Fontsize=14,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00141618,"
                         "BorderStyle=1,Outline=2.5,Shadow=0,Alignment=2,MarginV=45")
                vf = ["-vf", f"subtitles={srt}:force_style='{style}'"]
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(vo / "vo_full.wav"), *vf,
                 "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                 "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(final)])
        else:
            # sound design + music under the narration, word-by-word captions burned in
            events = polish.sound_events(plans, starts, spans, kinds)
            if vertical:  # hook impact on the first frame, a pop when the end card lands
                events += [{"t": 0.0, "kind": "boom"}, {"t": 0.02, "kind": "hit"},
                           {"t": max(0.0, total - CTA_S), "kind": "pop"}]
            bg = polish.background_track(vo / "vo_full.wav", events, starts, total, tmp / "bg.wav")
            words = []
            for sc, d, t0 in zip(scenes, durations, starts):
                timed = polish.load_word_timings(vo, sc["id"])
                words += [(w, t0 + a, t0 + b) for w, a, b in polish.scene_words(sc["text"], d, timed)]
            busy = [] if vertical else polish.busy_bands(plans, starts, [d + PAUSE for d in durations])
            ass = polish.write_ass(words, tmp / "captions.ass", vertical, busy)
            mix = ("[1:a]aresample=44100,pan=stereo|c0=c0|c1=c0[v];"
                   "[v][2:a]amix=inputs=2:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(vo / "vo_full.wav"), "-i", str(bg),
                 "-filter_complex", mix, "-vf", f"ass={ass}", "-map", "0:v", "-map", "[a]",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
                 "-ar", "44100", "-shortest", "-movflags", "+faststart", str(final)])
            if not vertical:
                end_screen(final, tmp)
    (out / f"{name}_chapters.txt").write_text("\n".join(chapters) + "\n", encoding="utf-8")
    (out / f"{name}_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    missing = [r["scene"] for r in report if r["images"][0].endswith("_card.png")]
    print(f"{final}: {sum(spans):.0f} s, {len(scenes)} scenes, "
          f"title cards for {missing or 'none'}")
    return final


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--vertical", action="store_true", help="9:16 Short with burned-in captions")
    ap.add_argument("--plain", action="store_true", help="old edit: no transitions, sound design, music or karaoke captions")
    a = ap.parse_args()
    build(Path(a.script), a.vertical, a.plain)

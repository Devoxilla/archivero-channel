"""Automatic first edit: art + voiceover -> captioned video, subtitles and YouTube chapters.

Usage:
    python tools/assemble.py episodes/EP001-prison-security-levels/script.md            # 16:9 episode
    python tools/assemble.py episodes/EP001-prison-security-levels/shorts/short1.md --vertical

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
    for sid in ids:
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


def build(script: Path, vertical: bool = False):
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
        for i, (sc, d) in enumerate(zip(scenes, durations)):
            imgs = scene_images(sc, art_dirs)
            if not imgs:
                card = tmp / f"{sc['id']}_card.png"
                title_card(sc["title"], size, card)
                imgs = [card]
            span = d + PAUSE
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
        vf = []
        if vertical:  # burned-in captions for Shorts
            style = ("FontName=DejaVu Serif,Fontsize=13,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00141618,"
                     "BorderStyle=1,Outline=2,Shadow=0,Alignment=2,MarginV=70")
            vf = ["-vf", f"subtitles={srt}:force_style='{style}'"]
        final = out / f"{name}.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-i", str(vo / "vo_full.wav"), *vf,
             "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(final)])
    (out / f"{name}_chapters.txt").write_text("\n".join(chapters) + "\n", encoding="utf-8")
    (out / f"{name}_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    missing = [r["scene"] for r in report if r["images"][0].endswith("_card.png")]
    print(f"{final}: {sum(durations) + PAUSE * len(durations):.0f} s, {len(scenes)} scenes, "
          f"title cards for {missing or 'none'}")
    return final


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--vertical", action="store_true", help="9:16 Short with burned-in captions")
    a = ap.parse_args()
    build(Path(a.script), a.vertical)

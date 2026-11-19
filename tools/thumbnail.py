"""YouTube thumbnail (1280x720) from one picture plus 1-2 short text lines.

Usage: python tools/thumbnail.py art/thumbnail_bg.png "LEVEL 6" "4-inch window" [--out thumb.png]
The first line is drawn big in ink black on a paper strip, the second smaller in red.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from assemble import INK, PAPER, RED, font

W, H = 1280, 720


def make(bg: Path, line1: str, line2: str = "", out: Path | None = None) -> Path:
    img = ImageOps.fit(Image.open(bg).convert("RGB"), (W, H))
    d = ImageDraw.Draw(img)
    f1, f2 = font(118), font(64)
    w1 = d.textlength(line1, font=f1)
    w2 = d.textlength(line2, font=f2) if line2 else 0
    box_w = max(w1, w2) + 70
    box_h = 150 + (85 if line2 else 0)
    x0, y0 = W - box_w - 40, H - box_h - 40
    d.rectangle([x0 + 10, y0 + 10, x0 + box_w + 10, y0 + box_h + 10], fill=INK)  # cut-paper shadow
    d.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=PAPER, outline=INK, width=6)
    d.text((x0 + 35, y0 + 20), line1, font=f1, fill=INK)
    if line2:
        d.text((x0 + 35, y0 + 150), line2, font=f2, fill=RED)
    out = out or bg.with_name("thumbnail.png")
    img.save(out)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("background")
    ap.add_argument("line1")
    ap.add_argument("line2", nargs="?", default="")
    ap.add_argument("--out")
    a = ap.parse_args()
    print(make(Path(a.background), a.line1, a.line2, Path(a.out) if a.out else None))

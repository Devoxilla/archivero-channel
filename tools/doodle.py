"""Doodle animation engine: crude, hand-drawn 2D explainer animation rendered frame by frame with Pillow.

Everything is drawn from code (no image generator, no credits): wobbly "boiling" ink lines, stick-figure
characters that walk, talk, blink, shake and change expression, a talking host whose mouth follows the
voiceover, animated props (clocks, searchlights, waves, flames, CCTV) and pop-up labels.

A scene's look is described in the episode's animation.yaml (see docs in README, "Animation"):

S05:                      # scene id from the script
  - bg: paper             # shot 1 (starts at the scene start)
    cam: [1.0, 1.08]      # zoom from -> to over the shot
    items:
      - {char: gary, x: 600, y: 900, face: happy}
      - {prop: fence, x: 1300, y: 900, w: 700}
      - {label: "NO FENCE?", x: 960, y: 200, in: 0.4}
    beats:
      - {t: 0.2, who: gary, walk: [1100, 900], dur: 0.3}
      - {t: 0.6, who: gary, face: scared, shake: 0.1}
  - at: 0.5               # shot 2 starts halfway through the scene
    ...
All times (at, in, out, t, dur) are fractions of the shot (or scene for "at"). World is 1920x1080.
"""
import math
import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FPS = 25
BOIL = 4  # frames per line wobble (6 fps "boil", like hand-drawn animation)

C = {
    "ink": (22, 22, 24), "paper": (250, 247, 240), "red": (214, 40, 40), "khaki": (196, 168, 112),
    "orange": (238, 122, 36), "blue": (60, 96, 170), "navy": (36, 52, 92), "skin": (246, 214, 180),
    "grey": (150, 150, 155), "light": (215, 215, 218), "concrete": (178, 176, 170), "sky": (150, 200, 235),
    "night": (28, 34, 54), "grass": (110, 170, 80), "brown": (130, 88, 52), "white": (255, 255, 255),
    "yellow": (250, 210, 60), "green": (70, 150, 70), "dark": (40, 40, 44), "water": (60, 120, 180),
    "dusk": (244, 200, 160), "pink": (240, 150, 170), "cardigan": (139, 94, 60),
}
BG = {"paper": C["paper"], "night": C["night"], "dusk": C["dusk"], "grey": (222, 222, 224),
      "dark": (34, 34, 38), "red": (150, 30, 30), "sky": (200, 228, 246)}

FONT_PATHS = ["/usr/share/fonts/truetype/comic-neue/ComicNeue-Bold.ttf",
              "/usr/share/fonts/opentype/comic-neue/ComicNeue-Bold.otf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "C:/Windows/Fonts/comicbd.ttf", "/Library/Fonts/Comic Sans MS Bold.ttf"]
_fonts = {}


def font(size):
    if size not in _fonts:
        for p in FONT_PATHS:
            if Path(p).exists():
                _fonts[size] = ImageFont.truetype(p, size)
                break
        else:
            _fonts[size] = ImageFont.load_default()
    return _fonts[size]


def col(c):
    if isinstance(c, (list, tuple)):
        return tuple(c)
    return C.get(c, C["ink"])


def ease(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


class Pen:
    """ImageDraw wrapper whose points wobble a little, changing every BOIL frames."""

    def __init__(self, img, frame, wobble=2.2):
        self.d = ImageDraw.Draw(img)
        self.boil = frame // BOIL
        self.n = 0
        self.wob = wobble

    def j(self, x, y, amt=None):
        self.n += 1
        r = random.Random(self.boil * 100003 + self.n * 7919)
        a = self.wob if amt is None else amt
        return (x + r.uniform(-a, a), y + r.uniform(-a, a))

    def line(self, pts, w=7, c="ink"):
        pts = [self.j(*p) for p in pts]
        self.d.line(pts, fill=col(c), width=int(w), joint="curve")
        r = w / 2
        for x, y in (pts[0], pts[-1]):
            self.d.ellipse([x - r, y - r, x + r, y + r], fill=col(c))

    def poly(self, pts, fill=None, outline="ink", w=7):
        pts = [self.j(*p) for p in pts]
        if fill is not None:
            self.d.polygon(pts, fill=col(fill))
        if outline is not None:
            self.d.line(pts + [pts[0]], fill=col(outline), width=int(w), joint="curve")

    def rect(self, x0, y0, x1, y1, fill=None, outline="ink", w=7):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, outline, w)

    def circle(self, cx, cy, r, fill=None, outline="ink", w=7, steps=None):
        steps = steps or max(14, int(r / 3))
        pts = [(cx + r * math.cos(2 * math.pi * i / steps), cy + r * math.sin(2 * math.pi * i / steps))
               for i in range(steps)]
        self.poly(pts, fill, outline, w)

    def ellipse(self, cx, cy, rx, ry, fill=None, outline="ink", w=7):
        steps = max(16, int(max(rx, ry) / 3))
        pts = [(cx + rx * math.cos(2 * math.pi * i / steps), cy + ry * math.sin(2 * math.pi * i / steps))
               for i in range(steps)]
        self.poly(pts, fill, outline, w)

    def arc(self, cx, cy, r, a0, a1, w=6, c="ink"):
        steps = 10
        pts = [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
                cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / steps))) for i in range(steps + 1)]
        self.line(pts, w, c)

    def dot(self, x, y, r, c="ink"):
        x, y = self.j(x, y, 1)
        self.d.ellipse([x - r, y - r, x + r, y + r], fill=col(c))

    def text(self, x, y, s, size=60, c="ink", anchor="mm", stroke=0, stroke_c="white"):
        x, y = self.j(x, y, 1.2)
        self.d.text((x, y), s, font=font(int(size)), fill=col(c), anchor=anchor,
                    stroke_width=stroke, stroke_fill=col(stroke_c))


# ---------------------------------------------------------------- characters

OUTFITS = {"gary": "khaki", "inmate": "khaki", "guard": "navy", "staff": "blue", "orange": "orange"}


def person(p: Pen, x, y, s=1.0, shirt="khaki", face="neutral", walk=None, arms="down", hat=None,
           blink=False, flip=False, talk=0.0, skin="skin", hair=None, pants=None):
    """Stick-ish doodle person standing on (x, y). walk = leg phase in radians or None."""
    k = s
    sw = 7 * k
    hip = (x, y - 150 * k)
    neck = (x, y - 265 * k)
    head = (x, y - 325 * k)
    # legs
    sw_a = math.sin(walk) * 0.45 if walk is not None else 0.13
    for sign in (1, -1):
        a = sw_a * sign
        knee = (hip[0] + math.sin(a) * 75 * k, hip[1] + math.cos(a) * 75 * k)
        foot = (knee[0] + math.sin(a * 0.6) * 75 * k, y)
        p.line([hip, knee, foot], 10 * k, pants or "ink")
        p.line([foot, (foot[0] + (14 if not flip else -14) * k, foot[1])], 10 * k, "ink")
    # torso
    p.poly([(neck[0] - 45 * k, neck[1]), (neck[0] + 45 * k, neck[1]),
            (hip[0] + 38 * k, hip[1]), (hip[0] - 38 * k, hip[1])], shirt, "ink", sw)
    # arms
    sh_l, sh_r = (neck[0] - 42 * k, neck[1] + 12 * k), (neck[0] + 42 * k, neck[1] + 12 * k)
    swing = math.sin(walk) * 30 * k if walk is not None else 0
    poses = {
        "down": [(-60 - swing, 115), (60 + swing, 115)],
        "up": [(-80, -110), (80, -110)],
        "point": [(-55, 115), (135, -25)],
        "wave": [(-55, 115), (95, -120 + 20 * math.sin(p.boil * 1.3))],
        "hips": [(-70, 60), (70, 60)],
        "shrug": [(-110, -20), (110, -20)],
        "cross": [(45, 60), (-45, 60)],
        "hold": [(-30, 70), (30, 70)],
    }
    (lx, ly), (rx, ry) = poses.get(arms, poses["down"])
    if flip:
        lx, rx = -rx, -lx
        ly, ry = ry, ly
    for sh, (dx, dy) in ((sh_l, (lx, ly)), (sh_r, (rx, ry))):
        elbow = (sh[0] + dx * 0.55 * k, sh[1] + dy * 0.45 * k + 15 * k)
        hand = (sh[0] + dx * k, sh[1] + dy * k)
        p.line([sh, elbow, hand], 9 * k, "ink")
        p.dot(hand[0], hand[1], 9 * k, skin)
    # head
    p.circle(head[0], head[1], 58 * k, skin, "ink", sw)
    if hair:
        p.arc(head[0], head[1] - 5 * k, 56 * k, 200, 340, 16 * k, hair)
    face_parts(p, head[0], head[1], k, face, blink, flip, talk)
    if hat == "cap":
        p.poly([(head[0] - 60 * k, head[1] - 30 * k), (head[0] + 60 * k, head[1] - 30 * k),
                (head[0] + 50 * k, head[1] - 75 * k), (head[0] - 50 * k, head[1] - 75 * k)], "navy", "ink", sw)
        p.line([(head[0] + (55 if not flip else -55) * k, head[1] - 30 * k),
                (head[0] + (95 if not flip else -95) * k, head[1] - 25 * k)], 10 * k, "ink")
        p.dot(head[0], head[1] - 55 * k, 7 * k, "yellow")


def face_parts(p, hx, hy, k, face, blink, flip, talk):
    off = -8 * k if flip else 8 * k
    ex = 20 * k
    for sx in (-1, 1):
        cx = hx + sx * ex + off
        if blink:
            p.line([(cx - 9 * k, hy - 8 * k), (cx + 9 * k, hy - 8 * k)], 5 * k)
        elif face == "scared":
            p.circle(cx, hy - 10 * k, 11 * k, "white", "ink", 4 * k)
            p.dot(cx, hy - 10 * k, 4 * k)
        elif face == "dead":
            p.line([(cx - 8 * k, hy - 16 * k), (cx + 8 * k, hy)], 5 * k)
            p.line([(cx + 8 * k, hy - 16 * k), (cx - 8 * k, hy)], 5 * k)
        else:
            p.dot(cx, hy - 8 * k, 6.5 * k)
        if face == "angry":
            p.line([(cx - 12 * sx * k - 0, hy - 30 * k), (cx + 10 * sx * k, hy - 22 * k)], 6 * k)
        if face == "sad":
            p.line([(cx - 10 * sx * k, hy - 22 * k), (cx + 10 * sx * k, hy - 30 * k)], 5 * k)
    mx, my = hx + off, hy + 22 * k
    if talk > 0.08:
        p.ellipse(mx, my, 14 * k, (5 + 14 * min(1, talk)) * k, "dark", "ink", 4 * k)
    elif face in ("happy", "smug"):
        p.arc(mx, my - 12 * k, 20 * k, 30, 150, 6 * k)
    elif face in ("sad", "dead"):
        p.arc(mx, my + 14 * k, 18 * k, 210, 330, 6 * k)
    elif face == "scared":
        p.ellipse(mx, my + 4 * k, 9 * k, 13 * k, "dark", "ink", 4 * k)
    elif face == "angry":
        p.line([(mx - 16 * k, my + 4 * k), (mx + 16 * k, my)], 6 * k)
    else:
        p.line([(mx - 14 * k, my), (mx + 14 * k, my)], 6 * k)


def host(p: Pen, x, y, s=1.0, talk=0.0, blink=False, face="neutral", t=0.0, lamp=True):
    """The Archivero: round ink-blob archivist, tiny round glasses, brown cardigan, red-flame lamp."""
    k = s
    bob = math.sin(t * 2.2) * 5 * k
    cy = y - 190 * k + bob
    p.ellipse(x, cy, 120 * k, 135 * k, "ink", "ink", 6)
    # cardigan
    p.poly([(x - 112 * k, cy + 40 * k), (x + 112 * k, cy + 40 * k), (x + 100 * k, y - 25 * k + bob),
            (x - 100 * k, y - 25 * k + bob)], "cardigan", "ink", 6 * k)
    p.line([(x, cy + 45 * k), (x, y - 30 * k + bob)], 5 * k, "ink")
    for by in (cy + 75 * k, cy + 115 * k):
        p.dot(x + 14 * k, by, 6 * k, "yellow")
    # feet
    p.ellipse(x - 50 * k, y - 10 * k, 32 * k, 12 * k, "ink", "ink", 4)
    p.ellipse(x + 50 * k, y - 10 * k, 32 * k, 12 * k, "ink", "ink", 4)
    # glasses + eyes
    for sx in (-1, 1):
        gx = x + sx * 38 * k
        p.circle(gx, cy - 35 * k, 26 * k, "white", "light", 5 * k)
        if blink:
            p.line([(gx - 10 * k, cy - 35 * k), (gx + 10 * k, cy - 35 * k)], 5 * k)
        else:
            p.dot(gx + 3 * k, cy - 33 * k, 8 * k)
        if face == "smug":
            p.line([(gx - 22 * k, cy - 70 * k), (gx + 22 * k, cy - 62 * k + sx * 4 * k)], 6 * k, "light")
    p.line([(x - 12 * k, cy - 35 * k), (x + 12 * k, cy - 35 * k)], 4 * k, "light")
    # mouth
    if talk > 0.08:
        p.ellipse(x, cy + 15 * k, 22 * k, (6 + 20 * min(1, talk)) * k, "red", "light", 4 * k)
    elif face in ("smug", "happy"):
        p.arc(x, cy, 26 * k, 30, 150, 6 * k, "light")
    else:
        p.line([(x - 18 * k, cy + 15 * k), (x + 18 * k, cy + 15 * k)], 6 * k, "light")
    if lamp:
        lx, ly = x + 150 * k, y - 120 * k + bob
        p.line([(x + 105 * k, cy + 60 * k), (lx, ly - 70 * k)], 9 * k, "ink")
        flame(p, lx, ly - 40 * k, 0.8 * k, t)
        p.poly([(lx - 30 * k, ly - 60 * k), (lx + 30 * k, ly - 60 * k), (lx + 22 * k, ly),
                (lx - 22 * k, ly)], None, "ink", 6 * k)
        p.rect(lx - 32 * k, ly, lx + 32 * k, ly + 14 * k, "brown", "ink", 5 * k)


def flame(p, x, y, s, t):
    f = 1 + 0.15 * math.sin(t * 13) + 0.1 * math.sin(t * 7.3)
    p.poly([(x - 14 * s, y + 10 * s), (x, y - 38 * s * f), (x + 14 * s, y + 10 * s)], "red", "red", 3)
    p.poly([(x - 6 * s, y + 8 * s), (x, y - 14 * s * f), (x + 6 * s, y + 8 * s)], "yellow", None)


# ---------------------------------------------------------------- props
# Each prop: fn(p, it, t) where it = item dict (x, y, w, h, s ...) and t = seconds into the shot.

def g(it, k, d=None):
    return it.get(k, d)


def pr_ground(p, it, t):
    y = g(it, "y", 900)
    c = g(it, "c", "grass")
    p.d.rectangle([0, y, W, H], fill=col(c))
    p.line([(0, y), (W / 2, y + 4), (W, y)], 8)
    if c == "grass":
        for i in range(0, W, 110):
            xx = i + (i * 37) % 50
            p.line([(xx, y + 30), (xx + 8, y + 12), (xx + 16, y + 30)], 4, "green")


def pr_floor(p, it, t):
    y = g(it, "y", 900)
    p.d.rectangle([0, y, W, H], fill=col(g(it, "c", "concrete")))
    p.line([(0, y), (W, y)], 8)


def pr_house(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 900), g(it, "s", 1)
    w, h = 420 * s, 300 * s
    p.rect(x - w / 2, y - h, x + w / 2, y, "white")
    p.poly([(x - w / 2 - 30 * s, y - h), (x, y - h - 200 * s), (x + w / 2 + 30 * s, y - h)], "red")
    p.rect(x - 45 * s, y - 170 * s, x + 45 * s, y, "brown")
    for wx in (x - 140 * s, x + 140 * s):
        p.rect(wx - 45 * s, y - 230 * s, wx + 45 * s, y - 150 * s, "sky")
        p.line([(wx, y - 230 * s), (wx, y - 150 * s)], 5 * s)


def pr_fence(p, it, t):
    x, y, w, h = g(it, "x", 960), g(it, "y", 900), g(it, "w", 800), g(it, "h", 220)
    rows = 2 if g(it, "double", False) else 1
    for r in range(rows):
        yy = y - r * 40
        xx0 = x - w / 2 + r * 40
        p.line([(xx0, yy - h), (xx0 + w, yy - h)], 5, "grey")
        step = 34
        for i in range(int(w / step) + 1):
            a = xx0 + i * step
            p.line([(a, yy), (min(a + h * 0.5, xx0 + w), yy - h)], 2, "grey")
            p.line([(a, yy - h), (min(a + h * 0.5, xx0 + w), yy)], 2, "grey")
        for i in range(int(w / 160) + 1):
            px = xx0 + i * 160
            p.line([(px, yy), (px, yy - h - 30)], 8)
        if g(it, "wire", False):
            for i in range(int(w / 40)):
                p.circle(xx0 + 20 + i * 40, yy - h - 30, 16, None, "grey", 3, steps=8)
    if g(it, "sensor", False):
        on = int(t * 2) % 2 == 0
        p.dot(x + w / 2 - 20, y - h - 50, 14, "red" if on else "dark")


def pr_wall(p, it, t):
    x, y, w, h = g(it, "x", 960), g(it, "y", 900), g(it, "w", 1200), g(it, "h", 500)
    p.rect(x - w / 2, y - h, x + w / 2, y, g(it, "c", "concrete"))
    if g(it, "bricks", True):
        bh = 60
        for r in range(int(h / bh)):
            yy = y - r * bh
            p.line([(x - w / 2, yy), (x + w / 2, yy)], 3, "grey")
            off = 60 if r % 2 else 0
            for i in range(int(w / 120)):
                bx = x - w / 2 + off + i * 120
                if bx < x + w / 2:
                    p.line([(bx, yy), (bx, yy - bh)], 3, "grey")
    if g(it, "wire", False):
        for i in range(int(w / 50)):
            p.circle(x - w / 2 + 25 + i * 50, y - h - 18, 18, None, "grey", 3, steps=8)


def pr_tower(p, it, t):
    x, y, s = g(it, "x", 300), g(it, "y", 900), g(it, "s", 1)
    p.poly([(x - 50 * s, y), (x + 50 * s, y), (x + 35 * s, y - 420 * s), (x - 35 * s, y - 420 * s)], "concrete")
    p.rect(x - 90 * s, y - 520 * s, x + 90 * s, y - 420 * s, "light")
    p.rect(x - 70 * s, y - 505 * s, x + 70 * s, y - 450 * s, "dark")
    p.poly([(x - 110 * s, y - 520 * s), (x, y - 590 * s), (x + 110 * s, y - 520 * s)], "red")
    if g(it, "light", False):
        a = math.radians(70 + 45 * math.sin(t * 0.9))
        sx, sy = x, y - 480 * s
        L = 1300
        beam = [(sx, sy), (sx + L * math.cos(a - 0.12), sy + L * math.sin(a - 0.12)),
                (sx + L * math.cos(a + 0.12), sy + L * math.sin(a + 0.12))]
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(overlay).polygon(beam, fill=(230, 50, 40, 90))
        p.d._image.paste(Image.alpha_composite(p.d._image.convert("RGBA"), overlay).convert("RGB"))


def pr_building(p, it, t):
    x, y, w, h = g(it, "x", 960), g(it, "y", 900), g(it, "w", 700), g(it, "h", 380)
    p.rect(x - w / 2, y - h, x + w / 2, y, g(it, "c", "light"))
    rows, cols = g(it, "rows", 3), g(it, "cols", 8)
    for r in range(rows):
        for c_ in range(cols):
            wx = x - w / 2 + (c_ + 0.5) * w / cols
            wy = y - h + (r + 0.5) * (h - 60) / rows + 20
            if g(it, "slits", False):
                p.rect(wx - 5, wy - 30, wx + 5, wy + 30, "dark", "ink", 3)
            else:
                p.rect(wx - 20, wy - 22, wx + 20, wy + 22, "dark", "ink", 4)
                for bx in (-8, 8):
                    p.line([(wx + bx, wy - 22), (wx + bx, wy + 22)], 3, "grey")
    if g(it, "sign"):
        sw_ = max(160, font(40).getlength(it["sign"]) / 2 + 30)
        p.rect(x - sw_, y - h - 70, x + sw_, y - h - 5, "white")
        p.text(x, y - h - 38, it["sign"], 40)


def pr_bars(p, it, t):
    x, y, w, h = g(it, "x", 960), g(it, "y", 900), g(it, "w", 600), g(it, "h", 600)
    p.line([(x - w / 2, y - h), (x + w / 2, y - h)], 14, "dark")
    p.line([(x - w / 2, y - h * 0.5), (x + w / 2, y - h * 0.5)], 10, "dark")
    for i in range(int(w / 60) + 1):
        bx = x - w / 2 + i * 60
        p.line([(bx, y), (bx, y - h)], 11, "dark")


def pr_cell(p, it, t):
    x, y, w, h = g(it, "x", 960), g(it, "y", 900), g(it, "w", 700), g(it, "h", 560)
    p.rect(x - w / 2, y - h, x + w / 2, y, g(it, "c", "light"))
    p.line([(x - w / 2, y - 70), (x + w / 2, y - 70)], 4, "grey")


def pr_bunk(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 900), g(it, "s", 1)
    for lvl in ([0, 1] if g(it, "double", True) else [0]):
        by = y - 110 * s - lvl * 190 * s
        p.rect(x - 160 * s, by - 30 * s, x + 160 * s, by, g(it, "blanket", "blue"))
        p.ellipse(x - 120 * s, by - 40 * s, 35 * s, 16 * s, "white", "ink", 5 * s)
        if lvl == 0 and g(it, "dummy", False):
            p.circle(x - 120 * s, by - 70 * s, 34 * s, "skin", "ink", 5 * s)
            p.arc(x - 120 * s, by - 74 * s, 32 * s, 190, 350, 12 * s, "red")
            p.line([(x - 132 * s, by - 72 * s), (x - 122 * s, by - 72 * s)], 4 * s)
            p.line([(x - 112 * s, by - 72 * s), (x - 102 * s, by - 72 * s)], 4 * s)
    top = y - (110 + 190 + 60) * s if g(it, "double", True) else y - 170 * s
    for sx in (-1, 1):
        p.line([(x + sx * 160 * s, y), (x + sx * 160 * s, top)], 9 * s)


def pr_concrete_bed(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 900), g(it, "s", 1)
    p.rect(x - 200 * s, y - 110 * s, x + 200 * s, y, "concrete")
    p.rect(x - 190 * s, y - 135 * s, x + 190 * s, y - 110 * s, "light")


def pr_desk(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 900), g(it, "s", 1)
    c = g(it, "c", "brown")
    p.rect(x - 220 * s, y - 190 * s, x + 220 * s, y - 160 * s, c)
    p.rect(x - 200 * s, y - 160 * s, x - 160 * s, y, c)
    p.rect(x + 160 * s, y - 160 * s, x + 200 * s, y, c)
    if g(it, "papers", False):
        for i in range(5):
            p.rect(x - 150 * s + i * 8, y - 190 * s - (i + 1) * 14 * s, x - 30 * s + i * 8, y - 190 * s - i * 14 * s,
                   "white", "ink", 4)


def pr_stool(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 900), g(it, "s", 1)
    p.rect(x - 50 * s, y - 100 * s, x + 50 * s, y, g(it, "c", "concrete"))


def pr_toilet(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 900), g(it, "s", 1)
    p.rect(x - 40 * s, y - 160 * s, x + 40 * s, y - 90 * s, "light")
    p.ellipse(x, y - 75 * s, 70 * s, 22 * s, "white")
    p.poly([(x - 45 * s, y - 70 * s), (x + 45 * s, y - 70 * s), (x + 30 * s, y), (x - 30 * s, y)], "white")


def pr_door(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 900), g(it, "s", 1)
    p.rect(x - 90 * s, y - 330 * s, x + 90 * s, y, g(it, "c", "grey"))
    p.rect(x - 40 * s, y - 280 * s, x + 40 * s, y - 230 * s, "dark")
    if g(it, "slot", False):
        p.rect(x - 50 * s, y - 150 * s, x + 50 * s, y - 125 * s, "dark")
        if g(it, "tray", False):
            k = ease((t % 6) / 2)
            p.rect(x - 45 * s, y - 150 * s + 0, x + 45 * s, y - 135 * s, "light")
            p.rect(x - 45 * s - 0, y - 150 * s, x - 45 * s + 140 * s * k, y - 128 * s, "light")
    p.dot(x + 65 * s, y - 160 * s, 9 * s)


def pr_slit_window(p, it, t):
    x, y, h = g(it, "x", 960), g(it, "y", 500), g(it, "h", 360)
    w = g(it, "w", 26)
    p.rect(x - w / 2 - 16, y - h / 2 - 16, x + w / 2 + 16, y + h / 2 + 16, "grey")
    p.rect(x - w / 2, y - h / 2, x + w / 2, y + h / 2, g(it, "sky", "sky"))


def pr_clock(p, it, t):
    x, y, r = g(it, "x", 960), g(it, "y", 300), g(it, "r", 120)
    p.circle(x, y, r, "white", "ink", 9)
    for i in range(12):
        a = 2 * math.pi * i / 12
        p.line([(x + 0.82 * r * math.cos(a), y + 0.82 * r * math.sin(a)),
                (x + 0.92 * r * math.cos(a), y + 0.92 * r * math.sin(a))], 5)
    sp = g(it, "speed", 1.0)
    am = t * sp * 2 * math.pi / 4
    ah = am / 12
    p.line([(x, y), (x + 0.75 * r * math.sin(am), y - 0.75 * r * math.cos(am))], 7)
    p.line([(x, y), (x + 0.5 * r * math.sin(ah), y - 0.5 * r * math.cos(ah))], 11, "red")


def pr_ladder(p, it, t):
    x, y, h = g(it, "x", 960), g(it, "y", 980), g(it, "h", 900)
    labels = g(it, "labels", [])
    n = max(len(labels), g(it, "rungs", 7))
    w = g(it, "w", 260)
    p.line([(x - w / 2, y), (x - w / 2, y - h)], 12, "brown")
    p.line([(x + w / 2, y), (x + w / 2, y - h)], 12, "brown")
    hi = g(it, "highlight", None)
    for i in range(n):
        ry = y - h + (i + 0.5) * h / n
        p.line([(x - w / 2, ry), (x + w / 2, ry)], 9, "red" if hi == i else "brown")
        if i < len(labels):
            p.text(x + w / 2 + 30, ry, labels[i], 50, "red" if hi == i else "ink", "lm")


def pr_form(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 540), g(it, "s", 1)
    rows = g(it, "rows", ["CRIME", "VIOLENCE", "ESCAPE", "SENTENCE", "DETAINERS"])
    p.rect(x - 260 * s, y - 330 * s, x + 260 * s, y + 330 * s, "white")
    p.text(x, y - 280 * s, g(it, "title", "SECURITY SCORE"), 44 * s)
    dur = g(it, "fill", 6.0)
    for i, r in enumerate(rows):
        ry = y - 190 * s + i * 85 * s
        p.text(x - 220 * s, ry, r, 34 * s, "ink", "lm")
        p.rect(x + 150 * s, ry - 25 * s, x + 200 * s, ry + 25 * s, "white", "ink", 5 * s)
        if t > dur * (i + 1) / (len(rows) + 1):
            p.line([(x + 155 * s, ry), (x + 172 * s, ry + 18 * s), (x + 210 * s, ry - 35 * s)], 8 * s, "red")
    if t > dur:
        tot = g(it, "total", "?")
        p.text(x, y + 250 * s, f"TOTAL: {tot}", 54 * s, "red")
        p.ellipse(x, y + 250 * s, 190 * s, 50 * s, None, "red", 6 * s)


def pr_camera(p, it, t):
    x, y, s = g(it, "x", 1600), g(it, "y", 250), g(it, "s", 1)
    a = math.sin(t * 0.8) * 0.35
    p.line([(x, y - 80 * s), (x, y)], 8 * s)
    bx, by = x - math.cos(a) * 90 * s, y + math.sin(a) * 30 * s
    p.poly([(x, y - 30 * s), (x, y + 30 * s), (bx, by + 25 * s), (bx, by - 25 * s)], "light")
    p.dot(bx, by, 12 * s, "red" if int(t * 2) % 2 else "dark")


def pr_water(p, it, t):
    y = g(it, "y", 800)
    p.d.rectangle([0, y, W, H], fill=col("water"))
    for r in range(4):
        yy = y + 30 + r * 70
        pts = [(xx, yy + 10 * math.sin(xx / 60 + t * 2 + r)) for xx in range(-40, W + 60, 40)]
        p.line(pts, 4, "white")


def pr_island(p, it, t):
    x, y, w = g(it, "x", 960), g(it, "y", 800), g(it, "w", 700)
    p.poly([(x - w / 2, y), (x - w / 3, y - 90), (x + w / 3, y - 110), (x + w / 2, y)], "brown")
    pr_building(p, {"x": x, "y": y - 90, "w": w * 0.6, "h": 200, "rows": 2, "cols": 6}, t)
    pr_tower(p, {"x": x + w * 0.38, "y": y - 80, "s": 0.5, "light": g(it, "light", False)}, t)


def pr_raft(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 850), g(it, "s", 1)
    x += g(it, "drift", 0) * t
    y += 8 * math.sin(t * 2)
    p.poly([(x - 150 * s, y), (x + 150 * s, y), (x + 120 * s, y + 35 * s), (x - 120 * s, y + 35 * s)], "yellow")
    for i in range(3):
        person(p, x - 80 * s + i * 80 * s, y, 0.32 * s, "orange", "scared", arms="up" if i == 1 else "down")


def pr_mountains(p, it, t):
    y = g(it, "y", 700)
    for mx, mh, mw in ((300, 380, 500), (800, 480, 600), (1350, 420, 560), (1750, 360, 460)):
        p.poly([(mx - mw / 2, y), (mx, y - mh), (mx + mw / 2, y)], "light")
        p.poly([(mx - mw * 0.12, y - mh * 0.76), (mx, y - mh), (mx + mw * 0.12, y - mh * 0.76)], "white")


def pr_road(p, it, t):
    y = g(it, "y", 950)
    p.d.rectangle([0, y - 50, W, y + 50], fill=col("dark"))
    for i in range(0, W, 160):
        xx = (i + t * g(it, "speed", 0) * 100) % (W + 160) - 80
        p.line([(xx, y), (xx + 80, y)], 8, "yellow")


def pr_cupcake(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 900), g(it, "s", 1)
    p.poly([(x - 60 * s, y - 90 * s), (x + 60 * s, y - 90 * s), (x + 45 * s, y), (x - 45 * s, y)], "pink")
    p.ellipse(x, y - 110 * s, 75 * s, 45 * s, "white")
    p.dot(x, y - 165 * s, 14 * s, "red")


def pr_phone(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 700), g(it, "s", 1)
    sh = 6 * math.sin(t * 40) if int(t) % 2 == 0 else 0
    p.rect(x - 45 * s + sh, y - 80 * s, x + 45 * s + sh, y + 80 * s, "dark")
    p.rect(x - 35 * s + sh, y - 65 * s, x + 35 * s + sh, y + 55 * s, "sky", "ink", 3)
    if sh:
        for r in (70, 100):
            p.arc(x + 40 * s, y - 60 * s, r * s, 270, 360, 5 * s)


def pr_sun(p, it, t):
    x, y, r = g(it, "x", 1650), g(it, "y", 180), g(it, "r", 80)
    p.circle(x, y, r, "yellow", "ink", 6)
    for i in range(10):
        a = 2 * math.pi * i / 10 + t * 0.2
        p.line([(x + (r + 20) * math.cos(a), y + (r + 20) * math.sin(a)),
                (x + (r + 50) * math.cos(a), y + (r + 50) * math.sin(a))], 6)


def pr_moon(p, it, t):
    x, y, r = g(it, "x", 1650), g(it, "y", 180), g(it, "r", 70)
    p.circle(x, y, r, "yellow", "ink", 6)
    p.circle(x + 30, y - 20, r * 0.85, col("night"), None)
    for i in range(14):
        sx, sy = (i * 397) % W, (i * 211) % 420 + 30
        p.dot(sx, sy, 4 if (i + int(t * 2)) % 3 else 6, "white")


def pr_tree(p, it, t):
    x, y, s = g(it, "x", 200), g(it, "y", 900), g(it, "s", 1)
    p.rect(x - 22 * s, y - 220 * s, x + 22 * s, y, "brown")
    p.circle(x, y - 290 * s, 110 * s, "green")


def pr_cage(p, it, t):
    x, y, w, h = g(it, "x", 960), g(it, "y", 900), g(it, "w", 420), g(it, "h", 420)
    p.rect(x - w / 2, y - h, x + w / 2, y, None, "grey", 6)
    for i in range(int(w / 40) + 1):
        p.line([(x - w / 2 + i * 40, y), (x - w / 2 + i * 40, y - h)], 4, "grey")
    for j in range(int(h / 40) + 1):
        p.line([(x - w / 2, y - j * 40), (x + w / 2, y - j * 40)], 3, "grey")
    p.rect(x + w / 2 - 30, y - h / 2 - 20, x + w / 2 + 10, y - h / 2 + 20, "red", "ink", 4)


def pr_pit(p, it, t):
    x, y, w, h = g(it, "x", 960), g(it, "y", 900), g(it, "w", 600), g(it, "h", 260)
    p.rect(x - w / 2, y, x + w / 2, y + h, "dark")


def pr_flashlight(p, it, t):
    x, y = g(it, "x", 960), g(it, "y", 700)
    sweep = g(it, "sweep", 200) * math.sin(t * 0.8)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).polygon([(g(it, "fx", 1700), g(it, "fy", 150)), (x + sweep - 140, y + 60),
                                     (x + sweep + 140, y + 60)], fill=(240, 70, 50, 85))
    p.d._image.paste(Image.alpha_composite(p.d._image.convert("RGBA"), overlay).convert("RGB"))


def pr_envelope(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 500), g(it, "s", 1)
    y += 10 * math.sin(t * 3)
    p.rect(x - 90 * s, y - 55 * s, x + 90 * s, y + 55 * s, "white")
    p.line([(x - 90 * s, y - 55 * s), (x, y + 10 * s), (x + 90 * s, y - 55 * s)], 5 * s)


def pr_crowd(p, it, t):
    x, y, w = g(it, "x", 960), g(it, "y", 900), g(it, "w", 1400)
    rows, per = g(it, "rows", 3), g(it, "per", 22)
    c = g(it, "c", "khaki")
    for r in range(rows):
        for i in range(per):
            px = x - w / 2 + (i + 0.5 + (r % 2) * 0.5) * w / per
            py = y - r * 70 + 3 * math.sin(t * 3 + i + r)
            p.rect(px - 14, py - 50, px + 14, py, c, "ink", 3)
            p.circle(px, py - 68, 16, "skin", "ink", 3, steps=10)


def pr_sign(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 900), g(it, "s", 1)
    txt = g(it, "text", "SIGN")
    tw = max(200, font(int(46 * s)).getlength(txt) + 60 * s)
    p.line([(x, y), (x, y - 220 * s)], 12 * s, "brown")
    p.rect(x - tw / 2, y - 330 * s, x + tw / 2, y - 210 * s, g(it, "c", "white"))
    p.text(x, y - 270 * s, txt, 46 * s, g(it, "tc", "ink"))


def pr_lamp(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 700), g(it, "s", 1)
    flame(p, x, y - 40 * s, 1.0 * s, t)
    p.poly([(x - 34 * s, y - 75 * s), (x + 34 * s, y - 75 * s), (x + 26 * s, y), (x - 26 * s, y)], None, "ink", 6)
    p.rect(x - 38 * s, y, x + 38 * s, y + 16 * s, "brown")


def pr_shelf(p, it, t):
    x, y, w, h = g(it, "x", 960), g(it, "y", 900), g(it, "w", 900), g(it, "h", 700)
    p.rect(x - w / 2, y - h, x + w / 2, y, "brown")
    shelves = 4
    for r in range(shelves):
        sy = y - h + (r + 1) * h / shelves
        p.line([(x - w / 2, sy), (x + w / 2, sy)], 8)
        for i in range(int(w / 50) - 1):
            fx = x - w / 2 + 30 + i * 50
            hh = 100 + (i * 37 + r * 13) % 50
            p.rect(fx, sy - hh, fx + 38, sy - 8, ["white", "light", "khaki", "red"][(i + r) % 4], "ink", 4)


def pr_arrow(p, it, t):
    x0, y0, x1, y1 = g(it, "x0", 500), g(it, "y0", 500), g(it, "x1", 900), g(it, "y1", 500)
    k = ease(t / max(0.01, g(it, "draw", 0.6)))
    xe, ye = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
    c = g(it, "c", "red")
    p.line([(x0, y0), (xe, ye)], 12, c)
    if k > 0.95:
        a = math.atan2(y1 - y0, x1 - x0)
        for da in (2.6, -2.6):
            p.line([(x1, y1), (x1 + 50 * math.cos(a + da), y1 + 50 * math.sin(a + da))], 12, c)


def pr_question(p, it, t):
    x, y, s = g(it, "x", 960), g(it, "y", 300), g(it, "s", 1)
    p.text(x, y + 15 * math.sin(t * 3), "?", 220 * s, g(it, "c", "red"), stroke=8, stroke_c="ink")


def pr_counter(p, it, t):
    x, y = g(it, "x", 960), g(it, "y", 300)
    a, b = g(it, "from", 0), g(it, "to", 100)
    v = int(a + (b - a) * ease(t / g(it, "dur", 3.0)))
    p.text(x, y, g(it, "prefix", "") + f"{v:,}" + g(it, "suffix", ""), g(it, "size", 130), g(it, "c", "red"),
           stroke=6, stroke_c="white")


def pr_pillars(p, it, t):
    """Bar chart: values as percent, labels below."""
    x, y = g(it, "x", 960), g(it, "y", 850)
    vals, labels = g(it, "values", []), g(it, "labels", [])
    bw, gap = g(it, "bw", 150), 50
    total_w = len(vals) * (bw + gap)
    hi = g(it, "highlight", None)
    for i, v in enumerate(vals):
        bx = x - total_w / 2 + i * (bw + gap)
        hh = 600 * v / max(vals) * ease(t / 1.5)
        p.rect(bx, y - hh, bx + bw, y, "red" if i == hi else "light")
        p.text(bx + bw / 2, y + 45, labels[i] if i < len(labels) else "", 36)


PROPS = {k[3:]: v for k, v in globals().items() if k.startswith("pr_")}


# ---------------------------------------------------------------- scene rendering

def label(p, it, t, life):
    """Pop-in text: scale bounce on entry."""
    k = min(1.0, life / 0.25)
    s = 1 + 0.25 * math.sin(k * math.pi) if k < 1 else 1
    size = g(it, "size", 80) * s
    x, y = g(it, "x", 960), g(it, "y", 160)
    txt = it["label"]
    if g(it, "box", True):
        tw = font(int(size)).getlength(txt)
        p.rect(x - tw / 2 - 30, y - size * 0.75, x + tw / 2 + 30, y + size * 0.75, g(it, "bc", "white"), "ink", 7)
    p.text(x, y, txt, size, g(it, "c", "ink"))


class CharState:
    def __init__(self, it):
        self.it = it
        self.x, self.y = g(it, "x", 960), g(it, "y", 900)
        self.face = g(it, "face", "neutral")
        self.arms = g(it, "arms", "down")
        self.shirt = g(it, "shirt", OUTFITS.get(it["char"], "khaki"))
        self.flip = g(it, "flip", False)
        self.visible = True
        self.walk = None
        self.shake = 0.0
        self.jump = 0.0


def char_at(it, beats, tt, dur):
    """State of character `it` at shot time tt (seconds) by replaying its beats."""
    st = CharState(it)
    name = g(it, "id", it["char"])
    for b in beats:
        if b.get("who") != name:
            continue
        b0 = b.get("t", 0) * dur
        if tt < b0:
            continue
        for key in ("face", "arms", "shirt"):
            if key in b:
                setattr(st, key, b[key])
        if "flip" in b:
            st.flip = b["flip"]
        if "hide" in b:
            st.visible = not b["hide"]
        if "show" in b:
            st.visible = bool(b["show"])
        if "walk" in b:
            bd = max(0.05, b.get("dur", 0.2) * dur)
            k = (tt - b0) / bd
            tx, ty = b["walk"]
            if k < 1:
                st.flip = tx < st.x
                st.x, st.y = st.x + (tx - st.x) * k, st.y + (ty - st.y) * k
                st.walk = (tt - b0) * 9
            else:
                st.flip = b.get("face_after_flip", tx < st.x) if "flip" not in b else b["flip"]
                st.x, st.y = tx, ty
        if "shake" in b and tt - b0 < b["shake"] * dur:
            st.shake = 1.0
        if b.get("jump") and tt - b0 < 0.5:
            st.jump = math.sin((tt - b0) / 0.5 * math.pi)
    return st


# ---------------------------------------------------------------- illustrated shots (pictures from art/)

_img_cache = {}
MOVES = ("push", "pull", "pan_left", "pan_right", "pan_up", "pan_down", "shake", "static", "push_shake")


def picture(path, prompt=""):
    """Cover-fit picture at 1.2x the frame (room to move). Missing file -> 'art needed' card."""
    key = str(path)
    if key not in _img_cache:
        bw, bh = int(W * 1.2), int(H * 1.2)
        if path and Path(path).exists():
            im = Image.open(path).convert("RGB")
            r = max(bw / im.width, bh / im.height)
            im = im.resize((int(im.width * r + 1), int(im.height * r + 1)), Image.LANCZOS)
            x0, y0 = (im.width - bw) // 2, int((im.height - bh) * 0.35)  # keep heads: crop a bit above centre
            im = im.crop((x0, y0, x0 + bw, y0 + bh))
        else:
            im = Image.new("RGB", (bw, bh), (238, 232, 220))
            d = ImageDraw.Draw(im)
            d.rectangle([60, 60, bw - 60, bh - 60], outline=C["ink"], width=10)
            d.text((bw / 2, bh * 0.36), "ART NEEDED: " + Path(str(path)).name, font=font(70), fill=C["red"], anchor="mm")
            words, lines, cur = prompt.split(), [], ""
            for w_ in words:
                if font(44).getlength((cur + " " + w_).strip()) > W - 360 and cur:
                    lines.append(cur)
                    cur = w_
                else:
                    cur = (cur + " " + w_).strip()
            if cur:
                lines.append(cur)
            for i, ln in enumerate(lines[:6]):
                d.text((bw / 2, bh * 0.5 + i * 60), ln, font=font(44), fill=C["ink"], anchor="mm")
        _img_cache[key] = im
    return _img_cache[key]


def clip_for(path):
    """A video clip saved next to a picture (art/S06_a.mp4 for S06_a.png) replaces the still."""
    if not path:
        return None
    c = Path(str(path)).with_suffix(".mp4")
    return c if c.exists() else None


def clip_frames(clip):
    """Decode a clip once to cover-fit JPEG frames at FPS (1.2x the frame, like picture()). Returns the paths."""
    key = str(clip)
    if key not in _img_cache:
        import hashlib
        import shutil
        import subprocess
        import tempfile
        st = Path(clip).stat()
        h = hashlib.md5(f"{Path(clip).resolve()}:{st.st_size}:{st.st_mtime}".encode()).hexdigest()[:12]
        out = Path(tempfile.gettempdir()) / "doodle_clips" / h
        if not out.exists():
            tmp = out.with_name(f"{h}.{os.getpid()}")
            tmp.mkdir(parents=True, exist_ok=True)
            bw, bh = int(W * 1.2), int(H * 1.2)
            vf = (f"fps={FPS},scale={bw}:{bh}:force_original_aspect_ratio=increase,"
                  f"crop={bw}:{bh}:(iw-{bw})/2:(ih-{bh})*0.35")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-an", "-vf", vf, "-q:v", "3",
                            str(tmp / "%05d.jpg")], check=True)
            try:
                tmp.rename(out)
            except OSError:  # another worker finished first
                shutil.rmtree(tmp, ignore_errors=True)
        _img_cache[key] = sorted(out.glob("*.jpg"))
    return _img_cache[key]


def moving_picture(shot, tt, dur, frame):
    clip = clip_for(shot.get("_img_path"))
    if clip:  # play the clip once at normal speed, then hold its last frame; the camera move stays gentle
        frames = clip_frames(clip)
        im = Image.open(frames[min(int(tt * FPS), len(frames) - 1)]).convert("RGB") if frames else \
            picture(shot.get("_img_path"), shot.get("prompt", ""))
        shot = dict(shot, amount=shot.get("amount", 1.0) * 0.4, jolts=[])
        if shot.get("move") in ("shake", "push_shake"):
            shot["move"] = "push"
    else:
        im = picture(shot.get("_img_path"), shot.get("prompt", ""))
    bw, bh = im.size
    k = ease(tt / max(dur, 0.01)) if shot.get("ease", True) else tt / max(dur, 0.01)
    mv = shot.get("move", "push")
    amt = shot.get("amount", 1.0)
    z = 1.0
    cx, cy = 0.5, 0.5
    if mv in ("push", "push_shake"):
        z = 1.0 + 0.16 * amt * k
    elif mv == "pull":
        z = 1.0 + 0.16 * amt * (1 - k)
    elif mv in ("pan_left", "pan_right"):
        z = 1.04
        cx = 0.5 + (0.08 * amt) * ((1 - 2 * k) if mv == "pan_left" else (2 * k - 1))
    elif mv in ("pan_up", "pan_down"):
        z = 1.04
        cy = 0.5 + (0.08 * amt) * ((1 - 2 * k) if mv == "pan_up" else (2 * k - 1))
    elif mv == "shake":
        z = 1.06
    fx, fy = shot.get("focus", [0.5, 0.5])
    cx += (fx - 0.5) * (z - 1) * 2
    cy += (fy - 0.5) * (z - 1) * 2
    cw, ch = W / z, H / z
    jx = jy = 0.0
    shaking = mv in ("shake", "push_shake") or any(abs(tt - s * dur) < 0.35 for s in shot.get("jolts", []))
    if shaking:
        r = random.Random(frame)
        a = shot.get("shake_px", 14)
        jx, jy = r.uniform(-a, a), r.uniform(-a, a)
    x0 = min(max(cx * bw - cw / 2 + jx, 0), bw - cw)
    y0 = min(max(cy * bh - ch / 2 + jy, 0), bh - ch)
    return im.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))


def stamp(p, it, life):
    """Typewriter date/place stamp, white on black, lower left by default."""
    txt = it["stamp"]
    n = max(1, int(len(txt) * min(1.0, life / 1.2)))
    size = g(it, "size", 54)
    x, y = g(it, "x", 80), g(it, "y", 960)
    tw = font(size).getlength(txt)
    p.d.rectangle([x - 24, y - size * 0.8, x + tw + 24, y + size * 0.8], fill=C["ink"])
    p.d.text((x, y), txt[:n], font=font(size), fill=C["white"], anchor="lm")


def title(p, it, life):
    """Huge block-letter title with heavy outline, optional subtitle line."""
    k = min(1.0, life / 0.3)
    s = 1 + 0.18 * math.sin(k * math.pi) if k < 1 else 1
    size = g(it, "size", 170) * s
    x, y = g(it, "x", 960), g(it, "y", 200)
    p.d.text((x, y), it["title"], font=font(int(size)), fill=col(g(it, "c", "white")), anchor="mm",
             stroke_width=int(size * 0.07), stroke_fill=C["ink"])
    if it.get("sub"):
        ss = g(it, "sub_size", 70)
        p.d.text((x, y + size * 0.85), it["sub"], font=font(int(ss)), fill=col(g(it, "sub_c", "yellow")),
                 anchor="mm", stroke_width=int(ss * 0.1), stroke_fill=C["ink"])


def pin(p, it, life):
    x, y = g(it, "x", 960), g(it, "y", 540)
    r = 16 + 6 * math.sin(life * 6)
    ring = 20 + (life * 60) % 60
    p.d.ellipse([x - ring, y - ring, x + ring, y + ring], outline=C["red"], width=5)
    p.d.ellipse([x - r, y - r, x + r, y + r], fill=C["red"], outline=C["ink"], width=5)
    if it.get("pin"):
        size = g(it, "size", 52)
        left = it.get("side") == "left"
        p.d.text((x - 40 if left else x + 40, y), it["pin"], font=font(size), fill=C["white"],
                 anchor="rm" if left else "lm",
                 stroke_width=6, stroke_fill=C["ink"])


def flash(img, life):
    if life < 0.25:
        a = int(255 * (1 - life / 0.25))
        return Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), a / 255)
    return img


def render_shot_frame(shot, tt, dur, frame, talk=0.0):
    if "img" in shot:
        img = moving_picture(shot, tt, dur, frame)
    else:
        img = Image.new("RGB", (W, H), BG.get(shot.get("bg", "paper"), C["paper"]))
    p = Pen(img, frame)
    flashes = []
    beats = shot.get("beats", [])
    for idx, it in enumerate(shot.get("items", [])):
        t_in, t_out = g(it, "in", 0) * dur, g(it, "out", 1.01) * dur
        if not (t_in <= tt < t_out):
            continue
        life = tt - t_in
        if "prop" in it:
            fn = PROPS.get(it["prop"])
            if fn:
                fn(p, it, life)
        elif "label" in it:
            label(p, it, tt, life)
        elif "stamp" in it:
            stamp(p, it, life)
        elif "title" in it:
            title(p, it, life)
        elif "pin" in it:
            pin(p, it, life)
        elif "flash" in it:
            flashes.append(life)
        elif "char" in it:
            st = char_at(it, beats, tt, dur)
            if not st.visible:
                continue
            blink = (frame + idx * 37) % 90 < 4
            if it["char"] == "host":
                host(p, st.x, st.y, g(it, "s", 1), talk if g(it, "talk", True) else 0, blink, st.face, tt,
                     g(it, "lamp", True))
                continue
            dx = 6 * math.sin(frame * 2.1) if st.shake else 0
            dy = -120 * st.jump + (0 if st.walk is not None else 3 * math.sin(tt * 2 + idx))
            person(p, st.x + dx, st.y + dy, g(it, "s", 1), st.shirt, st.face, st.walk, st.arms,
                   g(it, "hat", "cap" if it["char"] == "guard" else None), blink, st.flip,
                   0.0, g(it, "skin", "skin"), g(it, "hair", None), g(it, "pants", None))
    for life in flashes:
        img = flash(img, life)
    if "img" in shot:
        return img
    z0, z1 = shot.get("cam", [1.0, 1.06])
    z = z0 + (z1 - z0) * ease(tt / max(dur, 0.01))
    if abs(z - 1) > 0.002:
        fx, fy = shot.get("focus", [W / 2, H / 2])
        cw, ch = W / z, H / z
        x0 = min(max(fx - cw / 2, 0), W - cw)
        y0 = min(max(fy - ch / 2, 0), H - ch)
        img = img.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + cw, y0 + ch))
    return img


def scene_shots(spec, scene_dur):
    """[(shot, start, dur)] for a scene spec (list of shots with optional 'at' fractions)."""
    shots = spec if isinstance(spec, list) else [spec]
    starts = [s.get("at", i / len(shots)) * scene_dur for i, s in enumerate(shots)]
    out = []
    for i, s in enumerate(shots):
        end = starts[i + 1] if i + 1 < len(shots) else scene_dur
        out.append((s, starts[i], max(0.04, end - starts[i])))
    return out


def loudness(samples, rate, frames):
    """Per-video-frame mouth opening (0..1) from the voiceover samples."""
    import numpy as np
    hop = rate / FPS
    out = []
    peak = float(np.percentile(np.abs(samples), 99)) or 1.0
    for f in range(frames):
        a, b = int(f * hop), int((f + 1) * hop)
        seg = samples[a:b]
        v = float(np.sqrt(np.mean(seg ** 2))) / (peak * 0.35) if len(seg) else 0.0
        out.append(min(1.0, v))
    return out

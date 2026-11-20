"""Write shotlist.md for an episode: one ready-to-paste image prompt per picture in animation.yaml.

    python tools/shotlist.py episodes/EP001-pov-roman-legionary [--vertical]

Prompts in animation.yaml can use {grunt}, {host}, {crowd} (defined under `characters:`) and {style}.
The house style from STYLE.md is appended to every prompt. Pictures used by several shots appear once.
"""
import argparse
import re
from pathlib import Path

import yaml

STYLE = ("bold thick black outlines, flat bright colours with simple cel shading, cartoon illustration in the style "
         "of a modern adult animated history explainer, expressive slightly exaggerated faces, clean background with "
         "clear depth, high detail, no text, no watermark")


def expand(prompt, chars, aspect="16:9"):
    def sub(m):
        k = m.group(1)
        if k == "style":
            return STYLE
        return chars.get(k, m.group(0)).strip()
    text = re.sub(r"\{(\w+)\}", sub, prompt.strip())
    return f"{text}, {STYLE}, {aspect}"


def pictures(spec):
    """[(img, scene, shot_no, prompt)] in order, first use of each picture only."""
    seen, out = set(), []
    for sid, shots in spec.items():
        if not re.fullmatch(r"S\d+", str(sid)):
            continue
        for i, s in enumerate(shots if isinstance(shots, list) else [shots], 1):
            img = s.get("img")
            if img and img not in seen:
                seen.add(img)
                out.append((img, sid, i, s.get("prompt", "")))
    return out


def build(ep: Path, aspect="16:9"):
    spec = yaml.safe_load((ep / "animation.yaml").read_text(encoding="utf-8")) or {}
    chars = spec.get("characters", {})
    pics = pictures(spec)
    art = ep / "art"
    done = [p for p in pics if (art / p[0]).exists()]
    lines = [f"# Shot list: {ep.name}", "",
             f"{len(pics)} pictures, {len(done)} done. Make each one with a free generator "
             "(Bing Image Creator / Microsoft Designer, Gemini, Leonardo, Ideogram), choose landscape 16:9, "
             f"save it under the name shown, and put it in `{ep.name}/art/`.",
             "For pictures with the Grunt or the Archivero, give the generator your saved reference picture of "
             "that character and start the prompt with \"same character, same outfit, new pose:\".", ""]
    for img, sid, i, prompt in pics:
        tick = "x" if (art / img).exists() else " "
        lines += [f"## [{tick}] {img}  ({sid}, shot {i})", "", "```", expand(prompt, chars, aspect), "```", ""]
    out = ep / "shotlist.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out, len(pics), len(done)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=Path)
    ap.add_argument("--vertical", action="store_true", help="9:16 prompts")
    a = ap.parse_args()
    out, n, d = build(a.episode, "9:16" if a.vertical else "16:9")
    print(f"{out}: {n} pictures, {d} done")

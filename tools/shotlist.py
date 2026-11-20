"""Write shotlist.md for an episode: one ready-to-paste image prompt per picture in animation.yaml.

    python tools/shotlist.py episodes/EP001-korean-war [--vertical]

Prompts in animation.yaml can use {grunt}, {host}, {crowd} (defined under `characters:`) and {style}.
The house style from STYLE.md is appended to every prompt. Pictures used by several shots appear once.
Character reference pictures (`refs:`) come first; every later prompt that uses {grunt} or {host} is
made with that reference picture attached.
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


def has_art(art, img):
    """A picture counts as done when its PNG or a video clip with the same name (S06_a.mp4) is in art/."""
    return (art / img).exists() or (art / img).with_suffix(".mp4").exists()


def uses(prompt, refs):
    """Reference characters a prompt needs, e.g. ['grunt']."""
    return [k for k in refs if "{" + k + "}" in prompt]


def pictures(spec):
    """[(img, scene, shot_no, prompt)] in order, first use of each picture only (refs not included)."""
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
    chars, refs = spec.get("characters", {}), spec.get("refs", {})
    pics = pictures(spec)
    art = ep / "art"
    done = [p for p in pics if has_art(art, p[0])]
    lines = [f"# Shot list: {ep.name}", "",
             f"{len(pics)} pictures, {len(done)} done, plus {len(refs)} character references.", "",
             "**In the Gemini app** (gemini.google.com, Plus plan):",
             "1. Make the character references first (top of this list). Keep the best one of each.",
             "2. Open one Gemini chat per character. Attach that reference picture, then paste the prompts marked with "
             "that character one after another in the same chat. Prompts without a character can go in any chat.",
             "3. Download each picture. File names don't matter: upload them in the chat with Claude (or to "
             f"`{ep.name}/art/inbox/` on GitHub) and Claude matches each one to its shot.",
             "Pictures should be landscape (16:9). If Gemini returns a square, ask: \"same picture, wide 16:9\".", ""]
    if refs:
        lines += ["## Character references", ""]
        for k, r in refs.items():
            tick = "x" if (art / r["img"]).exists() else " "
            lines += [f"### [{tick}] {r['img']}  (the {k})", "", "```", expand(r["prompt"], chars, "16:9"), "```", ""]
        lines += ["## Shots", ""]
    for img, sid, i, prompt in pics:
        tick = "x" if has_art(art, img) else " "
        need = uses(prompt, refs)
        tag = f"  · attach {', '.join(refs[k]['img'] for k in need)}" if need else ""
        lines += [f"### [{tick}] {img}  ({sid}, shot {i}){tag}", "", "```", expand(prompt, chars, aspect), "```", ""]
    out = ep / "shotlist.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    flow_list(ep, spec, chars)
    return out, len(pics), len(done)


FLOW_STYLE = ("2D cartoon animation, bold thick black outlines, flat bright colours with simple cel shading, "
              "in the style of a modern adult animated history explainer, smooth simple motion. No text, no "
              "subtitles, no captions, no logos, no watermark, no speech")


def flow_list(ep: Path, spec, chars):
    """flow.md: one Google Flow (Veo) prompt per shot marked `flow:` in animation.yaml. The clip saved as
    art/<picture name>.mp4 replaces that shot's still picture in the build."""
    shots = [(sid, i, s) for sid, sh in spec.items() if re.fullmatch(r"S\d+", str(sid))
             for i, s in enumerate(sh if isinstance(sh, list) else [sh], 1) if isinstance(s, dict) and s.get("flow")]
    out = ep / "flow.md"
    if not shots:
        return None
    art = ep / "art"
    lines = [f"# Google Flow clips: {ep.name}", "",
             f"{len(shots)} short video clips for the key moments. Each one replaces a still picture in the video.", "",
             "**In Google Flow** (labs.google/flow, with your Gemini plan):",
             "1. New project. Choose **Text to Video**, model **Veo** (Fast is fine), landscape **16:9**, 1 output.",
             "2. Paste one prompt below and generate. If a still picture for that shot already exists, you can use "
             "**Frames to Video** instead and give it that picture as the first frame, with the same prompt.",
             "3. Download the clip (720p or 1080p) and rename it to the name above its prompt, e.g. `S06_a.mp4`.",
             "4. Upload the clips in the chat with Claude (or to "
             f"`episodes/{ep.name}/art/` on GitHub). The next build plays them; the voice-over replaces their sound.",
             ""]
    for sid, i, s in shots:
        name = Path(s["img"]).with_suffix(".mp4").name
        tick = "x" if (art / name).exists() else " "
        scene = re.sub(r"\{(\w+)\}", lambda m: chars.get(m.group(1), m.group(0)).strip(), s["prompt"].strip())
        lines += [f"### [{tick}] {name}  ({sid}, shot {i})", "", "```",
                  f"{scene}. {s['flow'].strip()} {FLOW_STYLE}.", "```", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=Path)
    ap.add_argument("--vertical", action="store_true", help="9:16 prompts")
    a = ap.parse_args()
    out, n, d = build(a.episode, "9:16" if a.vertical else "16:9")
    print(f"{out}: {n} pictures, {d} done")

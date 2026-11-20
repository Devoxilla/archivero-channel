"""Make an episode's missing pictures with the Gemini API (needs GEMINI_API_KEY).

    GEMINI_API_KEY=... python tools/gemini_art.py episodes/EP001-pov-roman-legionary --max 40

Character references (`refs:` in animation.yaml) are made first; every prompt that uses {grunt} or {host}
is sent with that reference picture attached, so the character stays the same. Pictures that already
exist in art/ are never made again, so the script can be run as often as needed (daily quotas).
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import shotlist  # noqa: E402

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def request_body(prompt, ref_pngs, aspect="16:9"):
    parts = [{"inline_data": {"mime_type": "image/png", "data": base64.b64encode(b).decode()}} for b in ref_pngs]
    if ref_pngs:
        prompt = "Use the attached character reference: same character, same face, same outfit. " + prompt
    parts.append({"text": prompt})
    return {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}}}


def image_from(resp):
    for c in resp.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            d = p.get("inlineData") or p.get("inline_data")
            if d and d.get("data"):
                return base64.b64decode(d["data"])
    raise RuntimeError("no image in response: " + json.dumps(resp)[:400])


def generate(body, key, model, tries=3):
    req = urllib.request.Request(API.format(model=model), data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    for n in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return image_from(json.load(r))
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:600]
            if e.code == 429 and "limit: 0" in msg:
                raise SystemExit("This API key has no image quota (free tier = 0). Turn on billing for the key's "
                                 "Google Cloud project, or make the pictures in the Gemini app. " + msg)
            if e.code in (429, 500, 503) and n + 1 < tries:
                time.sleep(20 * (n + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {msg}")


def jobs(spec, art):
    """[(img, prompt, [ref names])] still missing: refs first, then shots."""
    refs = spec.get("refs", {})
    out = [(r["img"], r["prompt"], []) for r in refs.values()]
    out += [(img, p, [refs[k]["img"] for k in shotlist.uses(p, refs)]) for img, _, _, p in shotlist.pictures(spec)]
    return [j for j in out if not (art / j[0]).exists()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=Path)
    ap.add_argument("--max", type=int, default=40, help="pictures per run")
    ap.add_argument("--model", default=os.environ.get("GEMINI_IMAGE_MODEL") or "gemini-2.5-flash-image")
    a = ap.parse_args()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY is not set")
    spec = yaml.safe_load((a.episode / "animation.yaml").read_text(encoding="utf-8"))
    chars, art = spec.get("characters", {}), a.episode / "art"
    art.mkdir(exist_ok=True)
    todo = jobs(spec, art)
    print(f"{len(todo)} pictures missing, making up to {a.max}")
    made = 0
    for img, prompt, refnames in todo[:a.max]:
        missing = [r for r in refnames if not (art / r).exists()]
        if missing:
            print(f"skip {img}: reference {missing} not made yet")
            continue
        body = request_body(shotlist.expand(prompt, chars), [(art / r).read_bytes() for r in refnames])
        try:
            data = generate(body, key, a.model)
        except RuntimeError as e:
            print(f"FAILED {img}: {e}")
            continue
        from PIL import Image
        import io
        Image.open(io.BytesIO(data)).convert("RGB").save(art / img)
        made += 1
        print(f"made {img}")
    left = len(jobs(spec, art))
    print(f"made {made}, {left} still missing")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"made={made}\nleft={left}\n")


if __name__ == "__main__":
    main()

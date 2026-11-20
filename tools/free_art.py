"""Make an episode's missing pictures with free image APIs (runs on GitHub Actions).

    python tools/free_art.py episodes/EP001-pov-roman-legionary [--max 120] [--backend auto]

Backends:
  cloudflare    (default) Workers AI free tier: 10,000 neurons a day, about 100+ Flux schnell pictures.
                Needs the repository secrets CF_ACCOUNT_ID + CF_API_TOKEN. Square 1024 output, the build crops it.
  pollinations  no key, but the anonymous tier is 1 picture per 45 s, low resolution, watermarked and does not
                follow the style: only used when asked for, or with a POLLINATIONS_TOKEN.
When the day's free allowance is used up the run stops; the daily schedule continues the next day.
Character references (`refs:` in animation.yaml) are made first. Their look is held by the long character
description in every prompt plus a fixed seed per character; when the backend accepts a reference image
(pollinations kontext), the reference picture is passed too. Existing pictures are never made again.
"""
import argparse
import base64
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import gemini_art  # noqa: E402  (jobs)
import shotlist  # noqa: E402

UA = {"User-Agent": "archivero-channel-build/1.0"}
W, H = 1344, 768


def seed_for(img, refnames):
    """Same seed family for a character's pictures (helps keep the face), otherwise per picture."""
    key = refnames[0] if refnames else img
    return int(hashlib.sha1(key.encode()).hexdigest()[:6], 16)


def fetch(req, timeout=240):
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def as_image(data):
    im = Image.open(io.BytesIO(data))
    im.load()
    if im.width < 400 or im.height < 300:
        raise RuntimeError(f"image too small ({im.width}x{im.height})")
    return im.convert("RGB")


def pollinations(prompt, seed, ref_url=None):
    token = os.environ.get("POLLINATIONS_TOKEN")
    q = {"width": W, "height": H, "seed": seed, "model": "flux", "nologo": "true", "private": "true",
         "enhance": "false"}
    if ref_url:
        q.update(model="kontext", image=ref_url)
    if token:
        q["token"] = token
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt[:1800]) + "?" + urllib.parse.urlencode(q)
    hdr = dict(UA)
    if token:
        hdr["Authorization"] = f"Bearer {token}"
    data, ctype = fetch(urllib.request.Request(url, headers=hdr))
    if "image" not in ctype:
        raise RuntimeError(f"pollinations returned {ctype}: {data[:200]!r}")
    return as_image(data)


def cloudflare(prompt, seed, ref_url=None):
    acc, tok = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
    if not (acc and tok):
        raise RuntimeError("CF_ACCOUNT_ID / CF_API_TOKEN not set")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    prompt = prompt.replace(", 16:9", "") + ", wide cinematic composition with the main subject in the middle band"
    body = json.dumps({"prompt": prompt[:2000], "steps": 8, "seed": seed}).encode()
    data, _ = fetch(urllib.request.Request(url, data=body, headers={**UA, "Authorization": f"Bearer {tok}",
                                                                      "Content-Type": "application/json"}))
    res = json.loads(data)
    if not res.get("success", True) or "result" not in res:
        raise RuntimeError(f"cloudflare: {str(res)[:300]}")
    return as_image(base64.b64decode(res["result"]["image"]))


BACKENDS = {"cloudflare": cloudflare, "pollinations": pollinations}


class QuotaDone(Exception):
    pass


def retry_after(msg, default=46):
    m = re.search(r"[Rr]etry after (\d+)", msg)
    return int(m.group(1)) + 3 if m else default


def make(prompt, seed, order, ref_url=None, tries=6):
    errs = []
    for name in order:
        for n in range(tries):
            try:
                try:
                    return BACKENDS[name](prompt, seed, ref_url), name
                except Exception:
                    if ref_url:  # reference-image mode not available: text only
                        return BACKENDS[name](prompt, seed, None), name
                    raise
            except urllib.error.HTTPError as e:
                msg = e.read()[:300].decode(errors="replace")
                errs.append(f"{name} HTTP {e.code}: {msg}")
                if name == "cloudflare" and (e.code == 429 or "4006" in msg or "neurons" in msg.lower()):
                    raise QuotaDone(msg)
                if e.code in (401, 403) or (e.code == 402 and "FREE_LIMIT" not in msg):
                    break
                time.sleep(retry_after(msg, 20 * (n + 1)))  # rate limit / busy: wait as told
            except Exception as e:  # noqa: BLE001
                errs.append(f"{name}: {e}")
                if "not set" in str(e):
                    break
                time.sleep(15 * (n + 1))
    raise RuntimeError("; ".join(errs[-3:]))


def raw_url(path):
    """Public URL of a committed file (for reference-image mode), when running on GitHub."""
    repo, sha = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("REF_BRANCH", "main")
    return f"https://raw.githubusercontent.com/{repo}/{sha}/{path.as_posix()}" if repo else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode", type=Path)
    ap.add_argument("--max", type=int, default=120)
    ap.add_argument("--backend", default="auto", choices=["auto", *BACKENDS])
    ap.add_argument("--pause", type=float, default=float(os.environ.get("ART_PAUSE", "46")))
    a = ap.parse_args()
    if a.backend == "auto":
        order = ["cloudflare"] + (["pollinations"] if os.environ.get("POLLINATIONS_TOKEN") else [])
    else:
        order = [a.backend]
    spec = yaml.safe_load((a.episode / "animation.yaml").read_text(encoding="utf-8"))
    chars, art = spec.get("characters", {}), a.episode / "art"
    art.mkdir(exist_ok=True)
    todo = gemini_art.jobs(spec, art)
    print(f"{len(todo)} pictures missing, making up to {a.max} ({' > '.join(order)})", flush=True)
    made, failed = 0, []
    for img, prompt, refnames in todo[:a.max]:
        if any(not (art / r).exists() for r in refnames):
            print(f"skip {img}: reference not made yet", flush=True)
            continue
        ref_url = raw_url(art / refnames[0]) if refnames and os.environ.get("REFS_PUBLIC") else None
        t0 = time.time()
        try:
            im, used = make(shotlist.expand(prompt, chars), seed_for(img, refnames), order, ref_url)
        except QuotaDone as e:
            print(f"Free daily allowance used up ({e}). The daily run continues tomorrow.", flush=True)
            break
        except RuntimeError as e:
            failed.append(img)
            print(f"FAILED {img}: {e}", flush=True)
            continue
        im.save(art / img)
        made += 1
        print(f"made {img} via {used} in {time.time() - t0:.0f}s ({im.width}x{im.height})", flush=True)
        time.sleep(a.pause)
    left = len(gemini_art.jobs(spec, art))
    print(f"made {made}, failed {len(failed)}, {left} still missing", flush=True)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"made={made}\nleft={left}\n")


if __name__ == "__main__":
    main()

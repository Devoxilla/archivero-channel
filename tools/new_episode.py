"""Create a new episode folder: episodes/EPnnn-<slug>/ with script.md and checklist.md.

Usage: python tools/new_episode.py "Every Prison Security Level Explained" [--slug prison-levels]
"""
import argparse
import datetime as dt
import re
from pathlib import Path

CHANNEL = Path(__file__).resolve().parents[1]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48].strip("-")


def next_code(episodes: Path) -> str:
    nums = [int(m.group(1)) for p in episodes.glob("EP*") if (m := re.match(r"EP(\d+)", p.name))]
    return f"EP{max(nums, default=0) + 1:03d}"


def create(title: str, slug: str | None = None, channel: Path = CHANNEL, today: str | None = None) -> Path:
    episodes = channel / "episodes"
    episodes.mkdir(parents=True, exist_ok=True)
    code = next_code(episodes)
    folder = episodes / f"{code}-{slugify(slug or title)}"
    folder.mkdir()
    fields = {"code": code, "title": title, "date": today or dt.date.today().isoformat()}
    for name in ("script_template.md", "checklist.md"):
        text = (channel / "templates" / name).read_text(encoding="utf-8")
        out = "script.md" if name == "script_template.md" else name
        (folder / out).write_text(text.format(**fields), encoding="utf-8")
    return folder


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("title")
    ap.add_argument("--slug")
    a = ap.parse_args()
    print(create(a.title, a.slug))

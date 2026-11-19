"""Weekly channel snapshot from the YouTube Data API v3 (free API key, no OAuth).

Env: YT_API_KEY, YT_CHANNEL_ID. Writes analytics/<date>.csv (one row per video)
and prints a short Markdown summary (used as the GitHub Actions job summary).
Exits 0 with a note when the key or channel id is missing, so the schedule never fails.
"""
import csv
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.googleapis.com/youtube/v3/"
OUT = Path(__file__).resolve().parents[1] / "analytics"


def http_get(endpoint: str, params: dict) -> dict:
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def fetch(key: str, channel_id: str, get=http_get, limit: int = 200) -> tuple[dict, list[dict]]:
    ch = get("channels", {"part": "statistics,contentDetails,snippet", "id": channel_id, "key": key})["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while len(ids) < limit:
        params = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50, "key": key}
        if token:
            params["pageToken"] = token
        page = get("playlistItems", params)
        ids += [i["contentDetails"]["videoId"] for i in page.get("items", [])]
        token = page.get("nextPageToken")
        if not token:
            break
    videos = []
    for i in range(0, len(ids), 50):
        res = get("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids[i:i + 50]), "key": key})
        for v in res.get("items", []):
            s = v.get("statistics", {})
            videos.append({
                "video_id": v["id"],
                "published": v["snippet"]["publishedAt"][:10],
                "title": v["snippet"]["title"],
                "duration": v["contentDetails"]["duration"],
                "short": is_short(v["contentDetails"]["duration"]),
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
            })
    return ch, videos


def is_short(iso: str) -> bool:
    """ISO 8601 duration (PT1M5S) -> True when 3 minutes or less (YouTube Shorts limit)."""
    import re
    m = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return False
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s <= 180


def summary(ch: dict, videos: list[dict], today: str) -> str:
    st = ch["statistics"]
    lines = [f"## {ch['snippet']['title']} — {today}",
             f"Subscribers {int(st.get('subscriberCount', 0)):,} · views {int(st.get('viewCount', 0)):,} · videos {st.get('videoCount', 0)}",
             "", "| Top videos | Views | Likes | Comments |", "| --- | ---: | ---: | ---: |"]
    for v in sorted(videos, key=lambda v: -v["views"])[:10]:
        kind = "Short" if v["short"] else "Episode"
        lines.append(f"| {v['title']} ({kind}) | {v['views']:,} | {v['likes']:,} | {v['comments']:,} |")
    return "\n".join(lines)


def main() -> int:
    key, cid = os.environ.get("YT_API_KEY"), os.environ.get("YT_CHANNEL_ID")
    if not key or not cid:
        print("YT_API_KEY or YT_CHANNEL_ID not set: add them in the repo settings (see README.md). Skipping.")
        return 0
    today = dt.date.today().isoformat()
    ch, videos = fetch(key, cid)
    OUT.mkdir(exist_ok=True)
    with open(OUT / f"{today}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(videos[0]) if videos else ["video_id"])
        w.writeheader()
        w.writerows(videos)
    print(summary(ch, videos, today))
    return 0


if __name__ == "__main__":
    sys.exit(main())

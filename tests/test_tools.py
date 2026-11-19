import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import make_voiceover  # noqa: E402
import new_episode  # noqa: E402
import youtube_stats  # noqa: E402


def test_read_scenes_ep001():
    scenes = make_voiceover.read_scenes(ROOT / "episodes/EP001-prison-security-levels/script.md")
    assert [s for s, _ in scenes][:3] == ["S01", "S02", "S03"]
    assert all("[VERIFY" not in body and "## Sources" not in body for _, body in scenes)


def test_new_episode_numbers_and_template(tmp_path):
    (tmp_path / "templates").mkdir()
    for f in ("script_template.md", "checklist.md"):
        (tmp_path / "templates" / f).write_text((ROOT / "templates" / f).read_text())
    (tmp_path / "episodes" / "EP001-x").mkdir(parents=True)
    folder = new_episode.create("Why Ships Sink!", channel=tmp_path, today="2026-11-20")
    assert folder.name == "EP002-why-ships-sink"
    script = (folder / "script.md").read_text()
    assert script.startswith("# EP002 — Why Ships Sink!") and "[S01] HOOK" in script
    assert make_voiceover.read_scenes(folder / "script.md")  # template parses


def test_is_short():
    assert youtube_stats.is_short("PT59S") and youtube_stats.is_short("PT3M")
    assert not youtube_stats.is_short("PT11M5S") and not youtube_stats.is_short("PT1H")


def test_fetch_and_summary_with_mock_api():
    def get(endpoint, params):
        if endpoint == "channels":
            return {"items": [{"snippet": {"title": "Archivero"},
                               "statistics": {"subscriberCount": "120", "viewCount": "5000", "videoCount": "2"},
                               "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
        if endpoint == "playlistItems":
            return {"items": [{"contentDetails": {"videoId": "a"}}, {"contentDetails": {"videoId": "b"}}]}
        return {"items": [
            {"id": "a", "snippet": {"publishedAt": "2026-11-20T10:00:00Z", "title": "EP001"},
             "contentDetails": {"duration": "PT11M2S"}, "statistics": {"viewCount": "4000", "likeCount": "300"}},
            {"id": "b", "snippet": {"publishedAt": "2026-11-21T10:00:00Z", "title": "Short 1"},
             "contentDetails": {"duration": "PT45S"}, "statistics": {"viewCount": "1000", "commentCount": "9"}},
        ]}
    ch, videos = youtube_stats.fetch("k", "c", get=get)
    assert [v["short"] for v in videos] == [False, True]
    text = youtube_stats.summary(ch, videos, "2026-11-23")
    assert "Subscribers 120" in text and text.index("EP001") < text.index("Short 1")


def test_stats_skips_without_secrets(monkeypatch, capsys):
    monkeypatch.delenv("YT_API_KEY", raising=False)
    assert youtube_stats.main() == 0
    assert "Skipping" in capsys.readouterr().out

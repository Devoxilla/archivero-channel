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


import assemble  # noqa: E402


def test_assemble_parses_script_and_shorts():
    ep = ROOT / "episodes/EP001-prison-security-levels"
    scenes = assemble.parse_script(ep / "script.md")
    assert scenes[0]["id"] == "S01" and len(scenes) == 13
    short = assemble.parse_script(ep / "shorts/short1-four-inch-window.md")
    assert short[1]["art"] == ["S12.3"]
    assert make_voiceover.read_scenes(ep / "shorts/short1-four-inch-window.md")[0][1].startswith("This prison window")


def test_timeline_chapters_and_captions():
    scenes = [{"id": "S01", "title": "HOOK", "text": "One. Two three four five six seven eight nine ten eleven twelve thirteen."},
              {"id": "S02", "title": "INTRO", "text": "Hello there."},
              {"id": "S03", "title": "LEVEL 0 — THE HALFWAY HOUSE", "text": "A house."}]
    starts, caps, chapters = assemble.timeline(scenes, [10.0, 5.0, 20.0])
    assert starts == [0.0, 10.6, 16.2]
    assert chapters == ["0:00 Intro", "0:16 The Halfway House"]
    assert abs(caps[-1][1] - 36.2) < 1e-6 and caps[0][0] == 0.0
    assert assemble.fmt_srt(3725.5) == "01:02:05,500"


def test_title_card_and_scene_images(tmp_path):
    card = tmp_path / "c.png"
    assemble.title_card("LEVEL 5 — ADMINISTRATIVE AND THE SUPERMAX", (640, 360), card)
    assert card.exists()
    art = tmp_path / "art"
    art.mkdir()
    for n in ("S1.png", "S12.png", "S12_b.jpg", "S120.png", "notes.txt"):
        (art / n).write_bytes(b"x")
    imgs = assemble.scene_images({"id": "S12", "art": []}, [art])
    assert [p.name for p in imgs] == ["S12.png", "S12_b.jpg"]


def test_animation_spec_renders_every_shot():
    import yaml
    import doodle
    ep = ROOT / "episodes/EP001-prison-security-levels"
    spec = yaml.safe_load((ep / "animation.yaml").read_text())
    scenes = assemble.parse_script(ep / "script.md")
    assert {s["id"] for s in scenes} <= set(spec)
    for sid, shots in spec.items():
        for shot, start, dur in doodle.scene_shots(shots, 20.0):
            for frac in (0.1, 0.9):
                img = doodle.render_shot_frame(shot, dur * frac, dur, int(start * 25), 0.4)
                assert img.size == (1920, 1080)
    short = assemble.parse_script(ep / "shorts/short2-alcatraz-escape.md")
    assert len(assemble.scene_spec(short[0], spec)) == 1

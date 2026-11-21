import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import make_voiceover  # noqa: E402
import new_episode  # noqa: E402
import youtube_stats  # noqa: E402


def test_read_scenes_ep001():
    scenes = make_voiceover.read_scenes(ROOT / "episodes/pilot-prison-security-levels/script.md")
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
            return {"items": [{"snippet": {"title": "Brinkman"},
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
    ep = ROOT / "episodes/pilot-prison-security-levels"
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
    ep = ROOT / "episodes/pilot-prison-security-levels"
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


import pytest


@pytest.mark.parametrize("name,n_scenes,min_pics", [("EP001-korean-war", 22, 80), ("EP002-pov-roman-legionary", 23, 80)])
def test_image_episode_shots_shotlist_and_shorts(tmp_path, name, n_scenes, min_pics):
    import yaml
    import doodle
    import shotlist
    from PIL import Image
    ep = ROOT / "episodes" / name
    spec = yaml.safe_load((ep / "animation.yaml").read_text())
    scenes = assemble.parse_script(ep / "script.md")
    assert len(scenes) == n_scenes and {s["id"] for s in scenes} <= set(spec)
    pics = shotlist.pictures(spec)
    assert len(pics) == len({p[0] for p in pics}) > min_pics
    for img, *_ , prompt in pics:  # every token expands, every prompt carries the house style
        full = shotlist.expand(prompt, spec["characters"])
        assert "{" not in full and full.endswith("no watermark, 16:9")
    # a real picture moves; a missing one becomes an ART NEEDED card; overlays draw on both
    Image.new("RGB", (800, 450), (40, 90, 60)).save(tmp_path / "S01_a.png")
    shots = assemble.scene_spec({"id": "S01", "art": []}, spec, tmp_path)
    for shot, start, dur in doodle.scene_shots(shots, 30.0):
        for frac in (0.05, 0.5, 0.95):
            assert doodle.render_shot_frame(shot, dur * frac, dur, 7, 0).size == (1920, 1080)
    a = doodle.render_shot_frame(shots[0], 0.1, 6, 1)
    b = doodle.render_shot_frame(shots[0], 5.9, 6, 1)
    assert a.getpixel((960, 300)) != (238, 232, 220) and a.tobytes() != b.tobytes()
    for f in sorted((ep / "shorts").glob("*.md")):
        for sc in assemble.parse_script(f):
            assert sc["art"] and len(assemble.scene_spec(sc, spec, tmp_path)) == len(sc["art"])


def test_gemini_art_jobs_and_request(tmp_path):
    import base64
    import gemini_art
    spec = {"characters": {"grunt": "a pale soldier"},
            "refs": {"grunt": {"img": "REF_grunt.png", "prompt": "sheet of {grunt}"}},
            "S01": [{"img": "S01_a.png", "prompt": "{grunt} in rain"}, {"img": "S01_b.png", "prompt": "a map"}]}
    assert [j[0] for j in gemini_art.jobs(spec, tmp_path)] == ["REF_grunt.png", "S01_a.png", "S01_b.png"]
    assert gemini_art.jobs(spec, tmp_path)[1][2] == ["REF_grunt.png"]
    (tmp_path / "S01_b.png").write_bytes(b"x")
    assert [j[0] for j in gemini_art.jobs(spec, tmp_path)] == ["REF_grunt.png", "S01_a.png"]
    body = gemini_art.request_body("a pale soldier in rain", [b"PNG"])
    parts = body["contents"][0]["parts"]
    assert base64.b64decode(parts[0]["inline_data"]["data"]) == b"PNG" and "same character" in parts[1]["text"]
    assert body["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9"
    img = base64.b64encode(b"IMG").decode()
    assert gemini_art.image_from({"candidates": [{"content": {"parts": [{"inlineData": {"data": img}}]}}]}) == b"IMG"


def test_free_art_retry_after_and_seeds():
    import free_art
    assert free_art.retry_after("Free limit reached. Retry after 27s, or get") == 30
    assert free_art.retry_after("busy", 12) == 12
    assert free_art.seed_for("S01_b.png", ["REF_grunt.png"]) == free_art.seed_for("S05_b.png", ["REF_grunt.png"])
    assert free_art.seed_for("S01_a.png", []) != free_art.seed_for("S01_c.png", [])


def test_flow_clip_replaces_still(tmp_path):
    import shutil
    import subprocess
    import doodle
    import shotlist
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg missing")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=24:duration=2",
                    str(tmp_path / "S01_a.mp4")], check=True)
    assert shotlist.has_art(tmp_path, "S01_a.png")
    shot = {"img": "S01_a.png", "_img_path": str(tmp_path / "S01_a.png"), "move": "push_shake"}
    a = doodle.render_shot_frame(shot, 0.1, 4, 1)
    b = doodle.render_shot_frame(shot, 1.5, 4, 2)
    c = doodle.render_shot_frame(shot, 3.9, 4, 3)  # past the clip's end: holds the last frame
    assert a.size == (1920, 1080) and a.tobytes() != b.tobytes() and a.getpixel((960, 300)) != (238, 232, 220)
    assert c.size == (1920, 1080)


def test_polish_transition_plan_and_frames():
    import numpy as np
    from PIL import Image
    import polish
    plan = polish.transition_plan(6)
    assert plan[0] == "dip" and len(plan) == 6 and set(plan[1:]) <= set(polish.TRANSITIONS)
    img = Image.new("RGB", (192, 108), (120, 60, 30))
    first = polish.frame_transition(img, 0, 100, "dip", "zoom")
    mid = polish.frame_transition(img, 50, 100, "dip", "zoom")
    assert np.asarray(first).mean() < np.asarray(mid).mean()  # opens from black
    assert np.array_equal(np.asarray(mid), np.asarray(img))  # untouched in the middle


def test_polish_words_chunks_and_ass(tmp_path):
    import polish
    words = polish.scene_words("Then came the most daring move of the war.", 4.0)
    assert len(words) == 9 and words[0][1] == 0 and words[-1][2] <= 4.0
    timed = polish.scene_words("Then came the", 2.0, timed=[["Then", 0.1, 0.4], ["came", 0.5, 0.8], ["the", 0.9, 1.0]])
    assert timed[1] == ("came", 0.5, 0.8)
    chunks = polish.caption_chunks(words)
    assert all(1 <= len(c) <= 3 for c in chunks) and sum(len(c) for c in chunks) == 9
    busy = [(0.0, 10.0, 900.0)]
    ass = (polish.write_ass(words, tmp_path / "c.ass", busy=busy)).read_text()
    assert "\\pos(960,878)" in ass and "&H00D7FF&" in ass  # stepped above the stamp, active word in yellow
    vert = polish.write_ass(words, tmp_path / "v.ass", vertical=True).read_text()
    assert "PlayResX: 1080" in vert and "\\pos(540,1520)" in vert


def test_polish_busy_bands():
    import polish
    shot = {"items": [{"stamp": "CHOSIN", "in": 0.1}, {"label": "30,000", "y": 620}, {"label": "X", "y": 900}]}
    bands = polish.busy_bands([[(shot, 0.0, 10.0)]], [5.0], [10.0])
    assert len(bands) == 2 and bands[0][0] == 6.0 and bands[1][2] < bands[0][2] < 1000


def test_vertical_items_stay_on_screen():
    import doodle
    a = doodle.vertical_item({"label": "~10 MILLION SEPARATED FAMILIES", "x": 1700, "y": 900}, 0)
    b = doodle.vertical_item({"label": "CARRIED 14,000", "x": 1350, "y": 160}, 1)
    assert a["x"] == 540 and b["y"] > a["y"]  # labels stack under each other, centred
    assert doodle.font(int(a["size"])).getlength(a["label"]) <= 900
    s = doodle.vertical_item({"stamp": "HUNGNAM · DECEMBER 1950"})
    assert s["x"] == 60 and 1200 < s["y"] < 1400  # above the captions


def test_shorts_list_ep001():
    import shotlist
    import yaml
    ep = ROOT / "episodes/EP001-korean-war"
    imgs = shotlist.shorts_pictures(ep, yaml.safe_load((ep / "animation.yaml").read_text()))
    assert "S12_e.png" in imgs and len(imgs) == len(set(imgs))


def test_fast_cuts_split_long_shots():
    import assemble
    shots = [{"img": "a.png", "items": [{"label": "X", "in": 0.1}, {"stamp": "S", "in": 0.8}]}, {"img": "b.png"}]
    out = assemble.fast_cuts(shots, 8.0)
    assert len(out) >= 5 and all("at" in s for s in out)
    first = [s for s in out if s["img"] == "a.png"]
    assert not first[0].get("_cont") and all(s.get("_cont") for s in first[1:])
    assert first[1]["items"][0]["in"] == -1.0  # label already on screen: no second pop
    sc = {"id": "S01", "art": ["S01.1!"]}
    got = assemble.scene_spec(sc, {"S01": [{"img": "x.png", "items": [{"label": "Y"}]}]})
    assert got[0]["items"] == []

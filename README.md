# The Archivero — channel workflow

English documentary-animation channel (dark infotainment "every level explained" files), hosted by the Archivero: an ink-blob archivist with tiny round glasses, a brown cardigan and an oil lamp with a red flame. Two-colour ink-on-paper art, one red accent.

Everything here is free: GitHub Actions (free minutes on private repos: 2,000/month), Kokoro TTS (Apache-2.0), YouTube Data API key (free quota).

## Weekly loop
1. **Start an episode**: Actions → *New episode* → Run workflow → type the title. It creates `episodes/EPnnn-<slug>/` with `script.md` and `checklist.md`.
2. **Write the script** in `script.md`. Keep the scene markers `[S01]`, `[S02]` …; text after `## Sources` and `[VERIFY …]` notes are not read aloud.
3. **Art**: free tools (Microsoft Designer / Bing Image Creator or the Gemini app), using the episode's `shotlist.md`. Save pictures in the episode's `art/` folder named after their scene (`S04.png`, `S04_b.png` ...). Upload them on GitHub: open the folder → Add file → Upload files.
4. **Animation**: the episode's `animation.yaml` describes each scene as doodle shots (characters, props, pop-up labels, moves). `tools/doodle.py` draws and animates them from code: wobbly hand-drawn lines, walking and talking stick characters, the Archivero whose mouth follows the voice. Scenes without an animation entry fall back to pictures in `art/` (slow pan) or a title card. Shorts borrow shots with `{art: S10.4}` (4th shot of scene S10).
5. **Build**: every push that changes an episode's script, Shorts or art runs *Build episode (voice + video)*. It reads the script with Kokoro (free), then edits the video automatically: each picture gets a slow push-in or pan, scenes without art get a paper title card, and the episode's Shorts are built in 9:16 with burned-in captions. Download from the run page → Artifacts → `episode-build`:
   - `out/<episode>.mp4` (16:9, 1080p), `out/<episode>.srt` (captions to upload), `out/<episode>_chapters.txt` (paste into the description)
   - `shorts/out/<short>.mp4` (9:16)
   To change voice or speed, run it by hand: Actions → *Build episode* → Run workflow (`bm_george`, `bm_lewis` British; `am_michael`, `am_adam` with lang `a` for American; speed 0.92 default). About 15–25 min per episode.
6. **Publish**: fill in the episode's `publish.md` (titles, description, tags, Shorts schedule), make the thumbnail with `tools/thumbnail.py` or Canva Free, polish in CapCut if you want (music bed, sound effects), then schedule in YouTube Studio.
7. **Analytics**: every Monday 08:00 UTC *Weekly analytics* saves `analytics/<date>.csv` (views, likes, comments per video, Shorts flagged) and shows the top 10 on the run's summary page.

## One-time setup
- **YouTube API key** (for analytics): Google Cloud Console → new project → enable *YouTube Data API v3* → Credentials → *API key*. In this repo: Settings → Secrets and variables → Actions → **New repository secret** `YT_API_KEY`.
- **Channel id**: YouTube Studio → Settings → Channel → Advanced settings (starts with `UC`). Same page → *Variables* tab → **New repository variable** `YT_CHANNEL_ID`.
- Until both exist, the weekly run just skips.

## Run locally
```
pip install kokoro soundfile pillow   # plus ffmpeg; Windows: also install espeak-ng
python tools/make_voiceover.py episodes/EP001-prison-security-levels/script.md
python tools/assemble.py episodes/EP001-prison-security-levels/script.md
python tools/new_episode.py "Every Castle Defence Explained"
pytest -q
```

## Layout
- `episodes/` one folder per episode: script, shot list, publish sheet, `art/`, `shorts/`
- `templates/` script and checklist templates
- `tools/` voiceover, automatic edit (assemble), thumbnail, new-episode and analytics scripts
- `analytics/` weekly CSV snapshots

# The Archivero — channel workflow

English documentary-animation channel (dark infotainment "every level explained" files), hosted by the Archivero: an ink-blob archivist with tiny round glasses, a brown cardigan and an oil lamp with a red flame. Two-colour ink-on-paper art, one red accent.

Everything here is free: GitHub Actions (free minutes on private repos: 2,000/month), Kokoro TTS (Apache-2.0), YouTube Data API key (free quota).

## Weekly loop
1. **Start an episode**: Actions → *New episode* → Run workflow → type the title. It creates `episodes/EPnnn-<slug>/` with `script.md` and `checklist.md`.
2. **Write the script** in `script.md`. Keep the scene markers `[S01]`, `[S02]` …; text after `## Sources` and `[VERIFY …]` notes are not read aloud.
3. **Voiceover**: every push that changes a `script.md` runs *Voiceover (free, Kokoro)*. Download the WAVs from the run page → Artifacts → `voiceover` (one WAV per scene + `vo_full.wav`). To pick another voice, run it by hand: Actions → *Voiceover* → Run workflow (`bm_george`, `bm_lewis` British; `am_michael`, `am_adam` with lang `a` for American). About 10–20 min per 11-min episode on the free runner.
4. **Art**: Microsoft Designer / Bing Image Creator or the Gemini app, using the prompts in the episode's `shotlist.md` and this house style:
   > two-colour ink illustration on off-white paper texture, thick wobbly hand-drawn black outlines, flat fills, single red accent, cut-paper feel, simple composition, generous empty space, no text, 16:9
5. **Edit** in CapCut free or DaVinci Resolve; **thumbnail** in Canva Free; **schedule** in YouTube Studio. Cut 3 Shorts from each episode.
6. **Analytics**: every Monday 08:00 UTC *Weekly analytics* saves `analytics/<date>.csv` (views, likes, comments per video, Shorts flagged) and shows the top 10 on the run's summary page.

## One-time setup
- **YouTube API key** (for analytics): Google Cloud Console → new project → enable *YouTube Data API v3* → Credentials → *API key*. In this repo: Settings → Secrets and variables → Actions → **New repository secret** `YT_API_KEY`.
- **Channel id**: YouTube Studio → Settings → Channel → Advanced settings (starts with `UC`). Same page → *Variables* tab → **New repository variable** `YT_CHANNEL_ID`.
- Until both exist, the weekly run just skips.

## Run locally
```
pip install kokoro soundfile          # Windows: also install espeak-ng
python tools/make_voiceover.py episodes/EP001-prison-security-levels/script.md
python tools/new_episode.py "Every Castle Defence Explained"
pytest -q
```

## Layout
- `episodes/` one folder per episode (script, checklist, shot list)
- `templates/` script and checklist templates
- `tools/` voiceover, new-episode and analytics scripts
- `analytics/` weekly CSV snapshots

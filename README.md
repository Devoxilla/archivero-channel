# The Archivero — channel workflow

English animated history channel: wars, empires, spies and geopolitics, told as dark, funny, fact-dense explainers and second-person POV stories (25–45 min episodes plus 3 Shorts each). Hosted by the Archivero, a round archivist with tiny glasses, a brown cardigan and an oil lamp with a red flame; "you" are the Grunt, a pale deadpan soldier whose uniform changes with the era. Bold black-outline cartoon illustrations, bright flat colours. Style guide, characters and prompt templates: `STYLE.md`. Formats: `templates/formats/`. Backlog: `ideas.md`.

Everything here is free: GitHub Actions (free minutes on private repos: 2,000/month), Kokoro TTS (Apache-2.0), YouTube Data API key (free quota).

## Weekly loop
1. **Start an episode**: Actions → *New episode* → Run workflow → type the title. It creates `episodes/EPnnn-<slug>/` with `script.md` and `checklist.md`.
2. **Write the script** in `script.md`. Keep the scene markers `[S01]`, `[S02]` …; text after `## Sources` and `[VERIFY …]` notes are not read aloud.
3. **Animation plan**: the episode's `animation.yaml` splits every scene into 3–8 shots. Each shot is one illustrated picture plus a camera move (`push`, `pull`, `pan_left/right/up/down`, `shake`, `push_shake`, `jolts` on impacts) and overlays drawn by the build: typewriter date stamps, block-letter titles, pop-up labels, pulsing map pins, white flashes. `python tools/shotlist.py episodes/<episode>` turns it into `shotlist.md`: one ready-to-paste prompt per picture, house style included.
4. **Art**: make each picture once with a free tool (Bing Image Creator / Microsoft Designer, the Gemini app, Leonardo or Ideogram free tiers), save it under the name in the shot list (`S04_b.png`) and upload it to the episode's `art/` folder (on GitHub: open the folder → Add file → Upload files). For the Grunt and the Archivero, always give the tool your reference picture of the character. Missing pictures render as an "ART NEEDED" card, so you can build and watch before the art is finished. **Gemini app (Plus plan):** follow the steps at the top of `shotlist.md`: character references first, one chat per character with its reference attached, any file names (Claude matches uploads in `art/inbox/` or in the chat to their shots). **Automatic option:** add a Google AI Studio key as the repository secret `GEMINI_API_KEY`, then Actions → *Make art (Gemini)* → Run workflow with the episode folder. It makes the missing pictures (references first, attached to every prompt with that character), commits them and starts the build when the set is complete. The API's free tier has no image quota, so the key's Google Cloud project needs billing turned on (about $0.04 per picture, about $4 per episode). Shorts borrow shots with `{art: S10.4}` (4th shot of scene S10). The older code-drawn doodle shots (stick characters, props) still work; see `episodes/pilot-prison-security-levels`.
5. **Build**: every push that changes an episode's script, Shorts or art runs *Build episode (voice + video)*. It reads the script with Kokoro (free), then edits the video automatically: each shot's picture moves as planned in `animation.yaml` with its overlays, and the episode's Shorts are built in 9:16 with burned-in captions. Download from the run page → Artifacts → `episode-build`:
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
python tools/make_voiceover.py episodes/EP001-pov-roman-legionary/script.md
python tools/assemble.py episodes/EP001-pov-roman-legionary/script.md
python tools/shotlist.py episodes/EP001-pov-roman-legionary
python tools/new_episode.py "How the KGB Worked From the Inside"
pytest -q
```

## Layout
- `episodes/` one folder per episode: script, shot list, publish sheet, `art/`, `shorts/`
- `templates/` script and checklist templates
- `tools/` voiceover, automatic edit (assemble), thumbnail, new-episode and analytics scripts
- `analytics/` weekly CSV snapshots

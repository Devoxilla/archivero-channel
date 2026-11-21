# The Archivero — style guide and prompt templates

Niche: history, wars, military units, spies, empires and geopolitics, told as dark, funny, fact-dense
explainers and first-person stories. Long episodes of 25–45 minutes, plus 3 Shorts per episode.

Look: bold black-outline cartoon illustration, bright flat colours, simple cel shading, slightly grotesque,
deadpan characters, busy battlefields behind a big foreground figure. The channel is original: its own host,
its own recurring soldier, its own colours. No copied characters, logos, frames or thumbnails from other channels.

---

## 1. House style (paste at the end of EVERY image prompt)

> bold thick black outlines, flat bright colours with simple cel shading, cartoon illustration in the style of a
> modern adult animated history explainer, expressive slightly exaggerated faces, clean background with clear
> depth, high detail, no text, no watermark, 16:9

For Shorts or a vertical scene, replace `16:9` with `9:16`.

Free tools that do this style well:
- **Microsoft Designer / Bing Image Creator** (free daily boosts, choose 16:9 / "landscape")
- **Gemini app** (free; best for keeping the same character: upload the reference picture and write "same
  character, same outfit, new pose: ...")
- **Leonardo.ai free tier** or **Ideogram free tier** as backups

Make each picture once, keep the best, name it after its shot (`S03_a.png`) and drop it in the episode's `art/`.

---

## 2. Recurring characters (make each once, then always give the tool the reference picture)

**The Archivero (host, appears in the intro, the mid-roll question and the outro)**
> a short round-bodied archivist with a pale round face, tiny round wire glasses, a few grey hairs combed over, an
> oversized brown wool cardigan with yellow buttons, holding an old brass oil lamp with a red flame, standing in a
> cramped archive full of shelves of files and maps, warm lamp light, smug half-smile

**The Grunt (our recurring soldier, the "you" of every POV episode)**
> a skinny young soldier with a very pale, round, deadpan face, dark tired circles under small dot eyes, a thin
> flat mouth, slightly oversized helmet, uniform of [ERA / ARMY], holding [WEAPON], in [PLACE]

Swap the uniform for each era: Roman legionary, medieval levy, Napoleonic line infantry, WW1 poilu, WW2 GI,
Soviet conscript, Vietnam grunt. Same face every time: that face is the channel's mascot.

**Crowd soldiers**
> rows of identical small cartoon soldiers with pale round deadpan faces in [UNIFORM], marching in formation

**Historical leaders (dead figures only for caricature)**
> caricature portrait of [NAME, ERA], recognisable but cartoonish, stern exaggerated expression, in [UNIFORM /
> CLOTHING], [PROP: pistol, map, sword, throne], dramatic background of [SCENE]

Living politicians: many free generators refuse them, and caricatures of living people carry more risk.
Use a silhouette, a back view, an empty podium with a flag, or a generic "president" character with the
country's flag instead.

---

## 3. Shot types (one picture per shot; most scenes use 3–6 shots)

| Shot | Prompt pattern | Typical move |
| --- | --- | --- |
| Establishing | wide view of [PLACE, YEAR], [WEATHER], small figures for scale | slow push-in or pan |
| Character close-up | the Grunt / leader close-up, [EMOTION], [ACTION] | push-in, shake on impacts |
| Battle | chaotic battle between [ARMY A] and [ARMY B], explosions, smoke, foreground soldier running | shake + pan |
| Daily life | [SOLDIERS] doing [TASK: eating, digging, gambling, marching] | slow pan |
| Object / weapon | close-up of [OBJECT] on [SURFACE], dramatic light | push-in |
| Map | stylised cartoon map of [REGION] in [YEAR], bright flat colours, no labels | the build adds pins, arrows, labels |
| Comparison | split image, left [A], right [B] | static + labels |
| Host | the Archivero at his desk / pointing at a map / holding a file | push-in |

Maps and labels are drawn by the build (pins, arrows, names, dates), so map pictures should have NO text.

---

## 4. Thumbnails (1280x720, made in Canva Free or with `tools/thumbnail.py`)

- One big foreground character (leader caricature or the Grunt) on one side, a busy colourful scene on the other.
- 1–3 words in huge block capitals, white or black with a heavy outline, one word in red if it helps.
- Formats that work in this niche: `TOPIC + YEARS` ("ROME 753 BC – 476 AD"), a shocking claim
  ("THEY NEVER SURRENDERED"), or colour-coded labels ("BLUE / GREEN / RED").
- Prompt: the house style + "YouTube thumbnail composition, big character on the [left/right] third, empty space
  on the other side for a title".

---

## 5. Episode formats (templates in `templates/formats/`)

| Format | Title pattern | Length |
| --- | --- | --- |
| Entire history | The Entire History of [X] Summarized | 30–45 min |
| POV | POV: You're a [soldier] in [war] | 25–40 min |
| Inside an organisation | How [KGB / Foreign Legion / Ottoman Janissaries] Worked From the Inside | 25–35 min |
| Every X explained | Every [Military Rank / Beret / Elite Unit] Explained | 20–35 min |
| One-man story | The [Soldier] Who [did the impossible] | 20–30 min |
| Conflict summarized | The Entire [Conflict] Summarized | 25–40 min |

Rules for every script: a cold-open hook in the first 20 seconds, a chapter every 3–5 minutes, one dark-funny line
per minute, a question for the comments around 40%, real sources at the end, no invented quotes.

## Shorts rules (default since 2026-11-20)
- First line = an aggressive hook in under 2 seconds: short punchy fragments, the shocking number or betrayal first ("Two men. Thirty minutes. One pencil line."). No dates or set-up before the hook.
- No title text on screen: only the word-by-word captions. The build opens on a punch-in with a shake and an impact sound.
- Last line sends viewers to the full episode: "... is in the episode linked below. Watch it now." The build adds a FULL EPISODE end card with an arrow at the Related-video link, in its own 3 s silent tail AFTER the last spoken line (it never covers captions).
- Each Short file has `Related video:` (set in YouTube Studio when uploading) and a pinned comment with the episode link.
- Full-screen 9:16 pictures in `art_916/` (prompts in `shorts_916.md`).
- Fast cuts: list 3-6 pictures per Short scene (`{art: S12.5, S12.4, S19.3}`), about one per 2-3 s of narration. The build cuts to a new picture or a new framing at least every 1.8 s. `S10.1!` borrows a picture without its overlays.

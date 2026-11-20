# EP001 shot list v2 (matches script v2, scenes S01–S13)

Save every picture in `episodes/EP001-prison-security-levels/art/`, named after its scene: `S04.png`, then `S04_b.png`, `S04_c.png` for more pictures in the same scene. The "Build episode" action splits each scene's time between its pictures and adds a slow push-in or pan. Scenes with no picture get a paper title card, so you can upload art a few frames at a time.

**House style** (paste after every prompt):
> two-colour ink illustration on off-white paper texture, thick wobbly hand-drawn black outlines, flat fills, single red accent, cut-paper feel, simple composition, generous empty space, no text, 16:9

**Host** (the Archivero, in every HOST prompt): a round black ink-blob archivist with tiny round glasses, an oversized brown cardigan and an oil lamp with a red flame. Make him once, then reuse: give the tool your best host picture as a reference (Gemini app: upload it and say "same character"), or cut him out in Canva and paste him onto backgrounds.

Free tools: Microsoft Designer / Bing Image Creator (16:9 option), Gemini app. Aim for 3 pictures per long scene and 1–2 per short scene: about 35 pictures for an 11-minute episode.

## Already made (pilot, ElevenLabs flow): download, rename, drop in art/
| File name | Pilot shot | Picture |
| --- | --- | --- |
| S01.png | ★01 | Slit window in a thick concrete wall, red sky |
| S02.png | ★03 | Archivero at his desk, lamp, piles of folders |
| S04.png | ★05 | House with a sign-in clipboard and a curfew clock |
| S05.png | ★07 | Low dorms in a field, no fence, red cupcake on a picnic table |
| S06.png | ★09 | Double chain-link fence around bunk rows |
| S08.png | ★11 | Cell block corridor, red sensor light outside |
| S10.png | ★13 | Fortress wall, watchtower, red searchlight beam |
| S10_c.png | ★14 | Alcatraz at night, three tiny figures on a raft |
| S11.png | ★15 | Solitary cell from above, tray through a slot |
| S12.png | ★17 | Bare concrete cell, slit window, lone figure |
| S12_c.png | ★18 | Isolated building, snowy mountains |

## Still to make (prompt + house style)
| File name | Prompt |
| --- | --- |
| S01_b.png | A very long ladder descending into darkness, each rung a different small building: house, cabin, fence, cell block, fortress, a tiny window at the very bottom glowing red |
| S02_b.png | HOST pulling a thick folder from a tall shelf, the folder stamped with a red wax seal, dust in the lamp light |
| S02_c.png | Thousands of tiny identical figures standing on the rungs of a giant ladder, seen from far away |
| S03.png | A paper scoring form on a desk with checkboxes and a red total circled, an ink stamp beside it |
| S03_b.png | A balance scale weighing a heavy black block labelled only by shape against small feathers, red pointer |
| S03_c.png | A figure on a ladder rung, arrows pointing both up and down, one arrow red |
| S04_b.png | Person with a briefcase walking toward a bus stop at dawn, the small house behind them |
| S04_c.png | A phone ringing on a kitchen table next to a calendar with one day circled in red |
| S05_b.png | Inmates raking leaves on a lawn, a guard sipping coffee, open field to the horizon |
| S05_c.png | A tiny cottage in the shadow of a huge castle-like prison |
| S06_b.png | Rows of bunk beds separated by half walls, seen from above, one red blanket |
| S06_c.png | A security camera on a pole looking straight at the viewer |
| S07.png | HOST looking straight at the viewer, one eyebrow raised, a red question mark floating above the lamp |
| S08_b.png | A small cell with a door, bunk, toilet and two figures facing away from each other |
| S08_c.png | A giant wall clock towering over a tiny line of inmates |
| S09.png | A day drawn as a circular clock face divided into slices: bed, tray, tools, yard, letters, a red slice for night |
| S09_b.png | A guard's flashlight beam (red) falling on a sleeping figure in a bunk, night |
| S09_c.png | Mail call: a hand holding up a single envelope above a crowd of raised hands |
| S10_b.png | A long corridor with figures walking in single file, guards at every door |
| S10_d.png | Three papier-mâché heads lying on pillows in prison bunks, one with red hair |
| S11_b.png | A cutaway building where every floor has a dark basement cell underneath |
| S11_c.png | A small outdoor cage under a grey sky, one figure, red lock |
| S12_b.png | A concrete bed, desk and stool, all one grey block, the slit window throwing a thin red line of light |
| S12_d.png | An empty walled exercise pen like a drained swimming pool, one small figure in the corner |
| S12_e.png | A staircase of five steps leading slowly up out of a dark pit, a faint red light at the top |
| S13.png | The full ladder from a little house at the top to a tiny window at the bottom, in one tall image |
| S13_b.png | One straight desert road with four prison buildings side by side, from a cabin to a fortress, mountains behind |
| S13_c.png | HOST turning the lamp down, smug little smile, the room going dark around him |

## Thumbnail
`thumbnail_bg.png` (16:9): S12 slit window close-up OR the full ladder (S13), host small in the bottom-left corner looking up at it. Run `python tools/thumbnail.py episodes/EP001-prison-security-levels/art/thumbnail_bg.png "LEVEL 5" "4-inch window"` (or make it in Canva Free: 2–3 words max, ink black with one red word).

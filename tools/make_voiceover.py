"""
Free voiceover for any episode script, using Kokoro TTS (open source, Apache-2.0).
Runs on a normal computer, no GPU or account needed.

One-time setup (Windows, Mac or Linux, Python 3.10-3.12):
    pip install kokoro soundfile
    (Windows only, also install espeak-ng: https://github.com/espeak-ng/espeak-ng/releases)

Run:
    python tools/make_voiceover.py episodes/EP001-pov-roman-legionary/script.md
    python tools/make_voiceover.py episodes/EP001-pov-roman-legionary/script.md --voice am_michael --lang a   # American narrator

Output: a folder "vo_<script name>" with one WAV per scene (S01.wav, S02.wav ...) plus vo_full.wav.
Scenes are the [S01], [S02] ... markers in the script. Text after "## Sources" is ignored,
and [VERIFY ...] notes are removed before reading.

Voices to try: British male bm_george, bm_lewis; American male am_michael, am_adam.
Use --lang b for British voices and --lang a for American voices.
"""
import argparse
import re
from pathlib import Path


SAMPLE_RATE = 24000
PAUSE_BETWEEN_SCENES = 0.6  # seconds of silence between scenes


def read_scenes(path: Path):
    text = path.read_text(encoding="utf-8")
    text = text.split("## Sources")[0]
    scenes = []
    for match in re.finditer(r"\[(S\d+)\][^\n]*\n(.*?)(?=\n\s*\[S\d+\]|\n---|\Z)", text, re.S):
        body = re.sub(r"\s*\[VERIFY[^\]]*\]", "", match.group(2)).strip()
        if body:
            scenes.append((match.group(1), body))
    return scenes


def main():
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    parser = argparse.ArgumentParser()
    parser.add_argument("script")
    parser.add_argument("--voice", default="bm_george")
    parser.add_argument("--lang", default="b", help="b = British English, a = American English")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()

    script = Path(args.script)
    out_dir = script.parent / f"vo_{script.stem}"
    out_dir.mkdir(exist_ok=True)

    pipeline = KPipeline(lang_code=args.lang)
    silence = np.zeros(int(SAMPLE_RATE * PAUSE_BETWEEN_SCENES), dtype=np.float32)
    full = []

    for scene_id, body in read_scenes(script):
        chunks = [audio for _, _, audio in pipeline(body, voice=args.voice, speed=args.speed)]
        audio = np.concatenate([np.asarray(c, dtype=np.float32) for c in chunks])
        sf.write(out_dir / f"{scene_id}.wav", audio, SAMPLE_RATE)
        full.extend([audio, silence])
        print(f"{scene_id}: {len(audio) / SAMPLE_RATE:.1f} s")

    total = np.concatenate(full)
    sf.write(out_dir / "vo_full.wav", total, SAMPLE_RATE)
    print(f"Done: {out_dir / 'vo_full.wav'} ({len(total) / SAMPLE_RATE / 60:.1f} min)")


if __name__ == "__main__":
    main()

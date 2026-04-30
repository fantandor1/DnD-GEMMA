from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rpg_dm.services.silero_tts_service import SileroSegment, get_silero_tts


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Russian speech with local Silero TTS.")
    parser.add_argument("--text", required=True, help="Text to synthesize.")
    parser.add_argument("--voice", default="", help="Requested speaker/voice.")
    parser.add_argument("--emotion", default="neutral", choices=["neutral", "happy", "amazed", "thinking", "annoyed", "shy"])
    parser.add_argument("--rate", default=1.0, type=float, help="Speech speed multiplier.")
    parser.add_argument("--output", required=True, help="Output WAV path.")
    args = parser.parse_args()

    tts = get_silero_tts()
    speakers = tts.speakers
    print("Available Silero speakers:", ", ".join(speakers), file=sys.stderr, flush=True)
    selected = tts.select_voice(args.voice)
    print(f"Selected Silero speaker: {selected}", file=sys.stderr, flush=True)

    audio = tts.synthesize(
        SileroSegment(text=args.text, speaker=selected, emotion=args.emotion, rate=args.rate),
        voice=selected,
        rate=args.rate,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(audio)
    print(str(output), file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

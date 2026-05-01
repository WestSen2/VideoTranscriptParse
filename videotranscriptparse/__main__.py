from __future__ import annotations

import argparse
import sys

from .core import get_transcript_text


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="videotranscriptparse",
        description="Create a transcript from a YouTube link (captions-first).",
    )
    p.add_argument("url", help="YouTube URL (or video id)")
    p.add_argument("--lang", default=None, help='Language code to prefer (e.g. "en")')
    p.add_argument("--out", default=None, help="Write transcript to this file path")
    p.add_argument(
        "--transcribe",
        action="store_true",
        help="If captions are unavailable, download audio and transcribe (requires ffmpeg + faster-whisper).",
    )
    p.add_argument(
        "--model",
        default="base",
        help='Whisper model to use when --transcribe is set (e.g. "base", "small", "medium", "large-v3").',
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        text = get_transcript_text(
            args.url,
            lang=args.lang,
            fallback_to_transcription=bool(args.transcribe),
            transcription_model=str(args.model),
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)


_VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


@dataclass(frozen=True)
class TranscriptLine:
    start: float
    duration: float
    text: str


def extract_video_id(youtube_url_or_id: str) -> str:
    """
    Accepts a YouTube URL (watch/shorts/embed/youtu.be) or a raw video id.
    Returns the 11-char video id.
    """
    s = youtube_url_or_id.strip()
    if _VIDEO_ID_RE.match(s):
        return s

    # Common URL shapes:
    # - https://www.youtube.com/watch?v=VIDEOID
    # - https://youtu.be/VIDEOID
    # - https://www.youtube.com/shorts/VIDEOID
    # - https://www.youtube.com/embed/VIDEOID
    m = re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", s)
    if m:
        return m.group(1)

    m = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", s)
    if m:
        return m.group(1)

    m = re.search(r"/shorts/([a-zA-Z0-9_-]{11})", s)
    if m:
        return m.group(1)

    m = re.search(r"/embed/([a-zA-Z0-9_-]{11})", s)
    if m:
        return m.group(1)

    raise ValueError(f"Could not extract YouTube video id from: {youtube_url_or_id!r}")


def _lines_to_text(lines: Iterable[TranscriptLine]) -> str:
    # Keep it simple: one line per caption chunk.
    return "\n".join(l.text.strip() for l in lines if l.text and l.text.strip()).strip() + "\n"


def _download_audio_with_ytdlp(youtube_url_or_id: str, *, tmp_dir: Path) -> Path:
    """
    Download best-available audio to `tmp_dir` and return the file path.

    Uses the Python `yt_dlp` library (installed via `yt-dlp` requirement).
    """
    try:
        import yt_dlp  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Audio transcription fallback requires `yt-dlp` to be importable."
        ) from e

    outtmpl = str(tmp_dir / "audio.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url_or_id, download=True)
        requested = info.get("requested_downloads") if isinstance(info, dict) else None
        if requested and isinstance(requested, list) and requested and isinstance(requested[0], dict):
            fp = requested[0].get("filepath")
            if fp:
                return Path(fp)

        for p in tmp_dir.glob("audio.*"):
            if p.is_file():
                return p

    raise RuntimeError("Failed to download audio for transcription.")


def _transcribe_with_faster_whisper(
    audio_path: Path,
    *,
    lang: Optional[str],
    model: str,
) -> list[TranscriptLine]:
    """
    Transcribe audio using faster-whisper (optional dependency).

    Note: faster-whisper often relies on `ffmpeg` being available on PATH to
    decode common media containers.
    """
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Transcription fallback requires `faster-whisper`.\n"
            "Install it with: pip install faster-whisper\n"
            "Also ensure `ffmpeg` is installed and available on your PATH."
        ) from e

    whisper_model = WhisperModel(model, device="auto", compute_type="auto")
    segments, _info = whisper_model.transcribe(
        str(audio_path),
        language=lang,
        vad_filter=True,
    )

    lines: list[TranscriptLine] = []
    for seg in segments:
        start = float(getattr(seg, "start", 0.0))
        end = float(getattr(seg, "end", start))
        text = str(getattr(seg, "text", "")).strip()
        if not text:
            continue
        lines.append(TranscriptLine(start=start, duration=max(0.0, end - start), text=text))
    return lines


def get_transcript_lines(
    youtube_url_or_id: str,
    *,
    lang: Optional[str] = None,
    fallback_to_transcription: bool = False,
    transcription_model: str = "base",
) -> list[TranscriptLine]:
    """
    Fetch transcript lines from YouTube captions (official or auto-generated).

    If `lang` is provided, we try it first (e.g. "en"), then fall back to any
    available transcript if that language isn't present.
    """
    video_id = extract_video_id(youtube_url_or_id)
    api = YouTubeTranscriptApi()

    try:
        # Newer youtube-transcript-api versions use instance methods:
        # - `api.fetch(video_id, languages=...)` returns a FetchedTranscript
        # - `api.list(video_id)` returns a TranscriptList
        if lang:
            fetched = api.fetch(video_id, languages=(lang,))
        else:
            # Default behavior: prefer English if available, else we'll fall back below.
            fetched = api.fetch(video_id, languages=("en",))
    except (NoTranscriptFound, TranscriptsDisabled) as e:
        # Try selecting *any* available transcript.
        try:
            transcripts = api.list(video_id)

            chosen = None
            if lang:
                try:
                    chosen = transcripts.find_transcript([lang])
                except Exception:
                    chosen = None

            if chosen is None:
                # Prefer manually created transcripts first, then auto-generated.
                all_langs = [t.language_code for t in transcripts]
                try:
                    chosen = transcripts.find_manually_created_transcript(all_langs)
                except Exception:
                    chosen = transcripts.find_generated_transcript(all_langs)

            fetched = chosen.fetch()
        except Exception:
            if not fallback_to_transcription:
                raise e

            with tempfile.TemporaryDirectory(prefix="videotranscriptparse_") as td:
                audio_path = _download_audio_with_ytdlp(youtube_url_or_id, tmp_dir=Path(td))
                return _transcribe_with_faster_whisper(
                    audio_path,
                    lang=lang,
                    model=transcription_model,
                )
    except VideoUnavailable as e:
        raise RuntimeError("Video unavailable (private, removed, or region-blocked).") from e

    return [
        TranscriptLine(
            start=float(seg.start),
            duration=float(seg.duration),
            text=str(seg.text),
        )
        for seg in fetched
    ]


def get_transcript_text(
    youtube_url_or_id: str,
    *,
    lang: Optional[str] = None,
    fallback_to_transcription: bool = False,
    transcription_model: str = "base",
) -> str:
    return _lines_to_text(
        get_transcript_lines(
            youtube_url_or_id,
            lang=lang,
            fallback_to_transcription=fallback_to_transcription,
            transcription_model=transcription_model,
        )
    )


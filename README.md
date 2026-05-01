# VideoTranscriptParse
HEAD
Paste Youtube Link and you get what the video says!
=======

Turn a YouTube link into a transcript.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Print transcript to stdout:

```bash
python -m videotranscriptparse "Paste Youtube URL here"
```

If the video has no captions, fall back to speech-to-text transcription:

```bash
python -m videotranscriptparse "Paste Youtube URL here" --transcribe
```

Choose a Whisper model for transcription fallback:

```bash
python -m videotranscriptparse "Paste Youtube URL here" --transcribe --model base
```

Write transcript to a file:

```bash
python -m videotranscriptparse "Paste Youtube URL here" --out transcript.txt
```

Prefer a specific language (example: English):

```bash
python -m videotranscriptparse "Paste Youtube URL here" --lang en
```

## Notes

- By default this uses **YouTube's existing captions** (fastest, best quality).
- If you pass `--transcribe`, the tool will download audio (via `yt-dlp`) and transcribe it using **faster-whisper**.
  - Install: `pip install faster-whisper`
  - You also need an `ffmpeg` binary available on your PATH (e.g. `brew install ffmpeg` on macOS).

>>>>>>> 53dd991 (Initial commit: captions-first transcript tool)

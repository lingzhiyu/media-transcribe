# media-transcribe

A Claude Code skill that transcribes media URLs into clean, organised Markdown files saved to your Obsidian vault.

Paste a YouTube, TikTok, Instagram, or Substack link — Claude runs the transcription, generates a key-ideas summary, and saves everything automatically.

## Supported sources

| Source | Method | Status |
|--------|--------|--------|
| YouTube | yt-dlp SRT captions (manual > auto) | ✅ Working |
| TikTok | yt-dlp audio extraction + Whisper | ✅ Working |
| Instagram | yt-dlp audio extraction + Whisper | ✅ Working |
| Substack | Static HTML parse + Tesseract OCR | ✅ Working |
| Reddit | — | ❌ Not supported yet |

## Output

Each transcript is saved to:
```
~/Obsidian/media-gobbler/{source}/YYYYMMDD_HHMMSS_{title}.md
```

Every file contains:
- **Title** — from video/post metadata, or derived from the transcript if missing
- **Source URL**
- **Summary** — 5–8 key-idea bullets written by Claude
- **Full Transcript** — complete text with natural paragraph breaks

## Installation

**Requires macOS + Homebrew.**

```bash
git clone https://github.com/lingzhiyu/media-transcribe
cd media-transcribe
./install.sh
```

`install.sh` installs:
- System tools via `brew`: `yt-dlp`, `ffmpeg`, `tesseract`
- Python packages via `pip3`: see `requirements.txt`
- Chromium browser via `playwright`

## Usage

### As a Claude Code skill

Add to your global Claude Code skills:

```bash
mkdir -p ~/.claude/skills/media-transcribe
cp .claude/SKILL.md ~/.claude/skills/media-transcribe/SKILL.md
```

Then in any Claude Code session:

```
Transcribe this: https://www.youtube.com/watch?v=...
```

Claude will run the script, OCR any images, write a summary, update the saved file, and show you the key ideas.

### As a standalone script

```bash
python3 transcribe.py "https://www.youtube.com/watch?v=..."
python3 transcribe.py "https://www.tiktok.com/@user/video/..."
python3 transcribe.py "https://www.instagram.com/reels/..."
python3 transcribe.py "https://substack.com/@author/note/..."
```

## How it works

| Step | What happens |
|------|-------------|
| 1 | `detect_source()` routes the URL by domain |
| 2 | Source handler extracts content (captions / audio / OCR) |
| 3 | Text is parsed into natural paragraphs using silence gaps (>1.5s) |
| 4 | Title is derived from metadata, falling back to first transcript sentence |
| 5 | File saved to Obsidian vault under `/{source}/YYYYMMDD_title.md` |
| 6 | Claude reads the transcript, writes a 5–8 bullet summary, updates the file |

### Substack notes
Substack notes are fetched statically (no browser needed). The note text comes from `og:description`; attached document images are downloaded and OCR'd with Tesseract in page order. Square avatar thumbnails are filtered out automatically.

### TikTok / Instagram
Uses `yt-dlp -x` to extract the native AAC audio stream (avoids the video-only MP4 issue), then transcribes with OpenAI Whisper locally — no API key required.

### YouTube
Uses `yt-dlp` to download SRT captions, preferring manual subtitles over auto-generated. Paragraph breaks are detected from timestamp gaps in the SRT file.

## Storage path

Defaults to:
```
~/Library/Mobile Documents/iCloud~md~obsidian/Documents/ZY Combined/media-gobbler/
```

Change `STORAGE_ROOT` at the top of `transcribe.py` to point to your own vault.

## Requirements

- macOS (Homebrew)
- Python 3.10+
- See `requirements.txt` for Python packages

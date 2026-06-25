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
$STORAGE_ROOT/{source}/YYYYMMDD_HHMMSS_{title}.md
```

Every file contains:
- **Title** — from video/post metadata, or derived from the transcript if missing
- **Source URL**
- **Summary** — key-idea bullets
- **Full Transcript** — complete text with natural paragraph breaks

## Installation

**System dependencies:** `yt-dlp`, `ffmpeg`, `tesseract` — install via Homebrew (macOS) or your package manager (Linux).

```bash
git clone https://github.com/lingzhiyu/media-transcribe
cd media-transcribe
./install.sh
```

`install.sh`:
- Installs system tools via `brew` on macOS (`apt` on Linux)
- Creates a Python virtual environment at `venv/`
- Installs Python packages from `requirements.txt` into the venv

## Configuration

Copy the example env file and set your storage path:

```bash
cp .env.example .env
```

Then edit `.env`:

```
STORAGE_ROOT=/path/to/your/obsidian/vault/Transcription
```

Paths with spaces and `~` are both supported, e.g.:

```
STORAGE_ROOT=/mnt/g/My Drive/Andy's Obsidian Vault/Transcription
STORAGE_ROOT=~/Documents/Obsidian/Transcription
```

`STORAGE_ROOT` is required — the script will exit with a clear error if it is not set.

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
# With venv activated
source venv/bin/activate
python3 transcribe.py "https://www.youtube.com/watch?v=..."

# Or directly
./venv/bin/python3 transcribe.py "https://www.tiktok.com/@user/video/..."
./venv/bin/python3 transcribe.py "https://www.instagram.com/reels/..."
./venv/bin/python3 transcribe.py "https://substack.com/@author/note/..."
./venv/bin/python3 transcribe.py "https://www.reddit.com/r/..."
```

## How it works

| Step | What happens |
|------|-------------|
| 1 | `detect_source()` routes the URL by domain |
| 2 | Source handler extracts content (captions / audio / OCR) |
| 3 | Text is parsed into natural paragraphs using silence gaps (>1.5s) |
| 4 | Title is derived from metadata, falling back to first transcript sentence |
| 5 | File saved to `$STORAGE_ROOT/{source}/YYYYMMDD_title.md` |
| 6 | Claude reads the transcript, writes a summary, updates the file |

### Substack notes
Substack notes are fetched statically (no browser needed). The note text comes from `og:description`; attached document images are downloaded and OCR'd with Tesseract in page order. Square avatar thumbnails are filtered out automatically.

### TikTok / Instagram
Uses `yt-dlp -x` to extract the native AAC audio stream (avoids the video-only MP4 issue), then transcribes with OpenAI Whisper locally — no API key required.

### YouTube
Uses `yt-dlp` to download SRT captions, preferring manual subtitles over auto-generated. Paragraph breaks are detected from timestamp gaps in the SRT file.

## Requirements

- Python 3.10+
- `yt-dlp`, `ffmpeg`, `tesseract` (system packages)
- See `requirements.txt` for Python packages (installed into `venv/` by `install.sh`)

# TikTok Transcription Setup

**Status:** ✅ Implementation complete | ⚠️ TikTok access requires additional setup

## Installation Checklist

✅ `openai-whisper` - Installed  
✅ `yt-dlp` - Installed  
✅ `ffmpeg` - Installed  
✅ `playwright` - Installed (for browser automation)  
✅ `chromium` - Installed (Playwright browser)  

### Verify Installation

```bash
# Test each component
python3 -c "import whisper; print('✅ Whisper OK')"
python3 -c "import yt_dlp; print('✅ yt-dlp OK')"
which ffmpeg  # Should show path
python3 -c "from playwright.async_api import async_playwright; print('✅ Playwright OK')"
```

### Whisper Model Auto-Download

On first TikTok transcription, Whisper downloads model (~140MB):
```bash
# This will trigger download if not already cached
python3 /Users/zhiyuling/lingzhiyu/media-gobbler/transcribe.py "<tiktok_url>"
```

## Known Issues & Workarounds

### Issue: TikTok Blocks yt-dlp
**Error:** `Requested format is not available` or `impersonate target is not available`

**Why:** TikTok actively blocks automated downloads. yt-dlp requires browser impersonation to work.

### Solution: Install playwright (browser automation)

```bash
pip3 install --break-system-packages playwright
python3 -m playwright install chromium
```

This enables yt-dlp to use a real browser to access TikTok.

### Alternative: Use TikTok Web directly

If playwright fails, try:
```bash
yt-dlp --list-formats "https://www.tiktok.com/@username/video/ID"
```

And manually specify the best audio format if available.

## Expected Output

When working, TikTok transcription produces:

```
# @creator: Description of video...

**Source:** https://www.tiktok.com/...
**Saved to:** /path/to/media-gobbler/tiktok/TIMESTAMP_filename.md

## Summary
- Overview of content
- Section 1: Key point
- Section 2: Key point
...

## Contents
1. First topic...
2. Second topic...

## Full Transcript
[Complete transcribed text with natural paragraphs]
```

## Timing Expectations

- **Download:** 10-30 seconds
- **Transcription:** ~1-2 minutes per 10 minutes of audio
- **Total:** 2-5 minutes per TikTok video

## Model Size vs Quality

```
tiny    (39MB)   - Fast, lower accuracy
base    (140MB)  - Good balance ✅ (default)
small   (244MB)  - Better accuracy
medium  (1.5GB)  - High accuracy
large   (2.9GB)  - Best accuracy (very slow)
```

To use larger model:
```python
# In transcribe.py, line ~252:
model = whisper.load_model("small")  # Change "base" to "small", etc.
```

## Troubleshooting

### "Whisper not installed"
```bash
pip3 install --break-system-packages openai-whisper
```

### "yt-dlp failed to download audio"
1. Install playwright: `pip3 install playwright && python3 -m playwright install chromium`
2. Try direct browser access: `yt-dlp "url" -j --list-formats`
3. Manually check if video is available for download

### "Audio codec error"
Make sure ffmpeg is installed:
```bash
brew install ffmpeg
```

### Slow transcription
- Use smaller model: `whisper.load_model("tiny")` for speed
- Or larger model: `whisper.load_model("medium")` for quality
- GPU support: Install torch with CUDA for ~3-5x speedup

## Files Generated

Saved transcripts go to:
```
~/Library/Mobile Documents/iCloud~md~obsidian/Documents/ZY Combined/media-gobbler/tiktok/
└── YYYYMMDD_HHMMSS_creator_description.md
```

Each file contains:
- Title (creator + description)
- Summary with key points
- Table of contents
- Full transcript with natural paragraphs
- Source URL and save path metadata

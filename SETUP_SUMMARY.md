# Media Transcriber Setup Summary

Complete setup instructions and dependencies for `/media-transcribe` skill.

## ✅ Installed Dependencies

### Core Tools
```bash
yt-dlp                  # Video/audio download
ffmpeg                  # Audio/video conversion
python3.12              # Python runtime
```

### Python Packages
```bash
pip3 install --break-system-packages:
  - openai-whisper      # Audio transcription (Whisper)
  - praw                # Reddit API (PRAW)
  - playwright          # Browser automation (TikTok)
  - beautifulsoup4      # HTML scraping (Substack, Instagram)
  - requests            # HTTP requests
  - brotli              # Compression support
```

### Browser Engines
```bash
chromium               # Installed via: python3 -m playwright install chromium
```

## 📋 Supported Media Sources

### ✅ YouTube
- **Method:** yt-dlp + SRT captions
- **Requires:** Nothing extra (ready to use)
- **Quality:** Manual > Auto captions
- **Speed:** ~30 seconds per video

**Example:**
```bash
python3 transcribe.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### ✅ Reddit (Optional)
- **Method:** PRAW API or public JSON endpoint
- **Requires:** Optional Reddit app credentials
- **Setup:** See REDDIT_SETUP.md
- **Speed:** ~2-5 seconds per post

**Example:**
```bash
# Without auth (fallback to public API):
python3 transcribe.py "https://www.reddit.com/r/Python/comments/..."

# With PRAW auth (optional):
export REDDIT_CLIENT_ID="..."
export REDDIT_CLIENT_SECRET="..."
export REDDIT_USER_AGENT="..."
python3 transcribe.py "https://www.reddit.com/r/Python/comments/..."
```

### ⚠️ TikTok (Implemented, Limited)
- **Method:** yt-dlp + Whisper transcription
- **Requires:** Audio stream to be available
- **Status:** Code implemented, TikTok access may be blocked
- **Speed:** 2-5 minutes per video
- **Known Issue:** TikTok blocks automated access; requires active workaround

**Example:**
```bash
python3 transcribe.py "https://www.tiktok.com/@username/video/..."
```

### 🚧 Coming Soon
- **Substack (text):** beautifulsoup4 (no extra setup)
- **Substack (images):** Claude Vision API (optional, paid)
- **Instagram Reels:** yt-dlp + Whisper (similar to TikTok)

## 📊 Output Format (All Sources)

Saved files contain:

```markdown
# [Media Title / Creator Name]

**Source:** [URL]

## Summary
- **Overview:** What the media is about
- **Section 1:** Key point from first section
- **Section 2:** Key point from second section
... (up to 8 sections)

**Stats:** [word count] words across [section count] sections

## Contents
1. First topic preview...
2. Second topic preview...
... (TOC from all sections)

## Full Transcript
[Complete transcribed text, organized by natural pauses]
```

## 📁 Storage Structure

```
~/Library/Mobile Documents/iCloud~md~obsidian/Documents/ZY Combined/media-gobbler/
├── youtube/
│   └── 20260624_114943_Video_Title_Here.md
├── reddit/
│   └── 20260624_120000_Subreddit_Name_Description.md
├── tiktok/
│   └── 20260624_120500_Creator_Name_Description.md
├── substack/
├── instagram/
└── [other sources...]
```

Each file is timestamped and named after the media title for easy discovery.

## 🚀 Usage Examples

### Transcribe YouTube video
```bash
python3 /Users/zhiyuling/lingzhiyu/media-gobbler/transcribe.py \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Transcribe Reddit post
```bash
python3 /Users/zhiyuling/lingzhiyu/media-gobbler/transcribe.py \
  "https://www.reddit.com/r/Python/comments/abc123/..."
```

### Transcribe TikTok video
```bash
python3 /Users/zhiyuling/lingzhiyu/media-gobbler/transcribe.py \
  "https://www.tiktok.com/@creator/video/..."
```

## ⚙️ Configuration

### Whisper Model Size
Default: `base` (140MB, 85-95% accuracy)

To change, edit `transcribe.py` line ~252:
```python
model = whisper.load_model("small")  # Options: tiny, base, small, medium, large
```

### Reddit Authentication (Optional)
Set environment variables:
```bash
export REDDIT_CLIENT_ID="your_id"
export REDDIT_CLIENT_SECRET="your_secret"
export REDDIT_USER_AGENT="media-transcribe/1.0 by your_username"
```

See: REDDIT_SETUP.md

## 🔧 Troubleshooting

### "Module not found" errors
```bash
# Reinstall missing package
pip3 install --break-system-packages openai-whisper
```

### yt-dlp can't download from TikTok
TikTok actively blocks access. Workarounds:
1. Ensure playwright is installed: `pip3 install playwright`
2. Ensure chromium is installed: `python3 -m playwright install chromium`
3. Try again (TikTok blocking measures change frequently)

### Slow transcription (TikTok)
Whisper transcription takes 1-2 min per 10 min of audio.
- To speed up: use smaller model: `whisper.load_model("tiny")`
- For better quality: use larger model: `whisper.load_model("medium")`
- For GPU acceleration: Install PyTorch with CUDA support

### ffmpeg not found
```bash
brew install ffmpeg
```

## 📝 File Locations

**Main script:** `/Users/zhiyuling/lingzhiyu/media-gobbler/transcribe.py`

**Setup docs:**
- YouTube: (built-in, no setup needed)
- Reddit: `/Users/zhiyuling/lingzhiyu/media-gobbler/REDDIT_SETUP.md`
- TikTok: `/Users/zhiyuling/lingzhiyu/media-gobbler/TIKTOK_SETUP.md`

**Skill definition:** `/Users/zhiyuling/lingzhiyu/media-gobbler/.claude/SKILL.md`

**Saved transcripts:** `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/ZY Combined/media-gobbler/`

## 🎯 Next Steps

1. ✅ All core dependencies installed
2. ✅ YouTube support working
3. ✅ Reddit support working (with optional auth)
4. ✅ TikTok support implemented
5. ⏳ Optional: Set up Reddit API credentials (REDDIT_SETUP.md)
6. ⏳ Optional: Improve TikTok access if blocked
7. Ready: `/media-transcribe` skill can be packaged

## 📊 Comparison

| Source | Setup | Speed | Quality | Cost |
|--------|-------|-------|---------|------|
| YouTube | ✅ Ready | Fast | 85-95% | Free |
| Reddit | ✅ Ready | Very Fast | 100% | Free |
| TikTok | ⚠️ Blocked | Slow | 85-95% | Free |
| Substack | 🚧 Coming | Fast | 100% | Free |
| Instagram | 🚧 Coming | Slow | 85-95% | Free |

---

**Ready to create the `/media-transcribe` Claude Code skill!**

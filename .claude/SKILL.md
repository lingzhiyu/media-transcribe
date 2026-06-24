---
name: media-transcribe
description: Transcribe videos and media to text. Use this skill whenever the user wants to transcribe a YouTube video, TikTok, Instagram reel, or Substack post into readable text. Handles auto-captions and manual subtitles, extracts the full transcript, and saves it organized by source. Automatically generates a summary and table of contents for easy navigation through the transcript.
---

# Media Transcribe

Transcribe videos and media URLs into searchable, organized text files.

## Supported Sources

- **YouTube** ✅ — yt-dlp auto-captions (prioritizes manual subs if available) + video title
- **Reddit** ✅ — Post text + top 5 comments (uses PRAW when configured, falls back to public JSON API)
- **Substack** — text and image extraction (coming soon)
- **Instagram Reels** — Whisper transcription (coming soon)
- **TikTok** — Whisper transcription (coming soon)

## How It Works

1. **Detect source** from URL pattern
2. **Extract captions** using the cheapest/fastest method:
   - YouTube: yt-dlp with SRT conversion (prefers manual > auto)
   - Other sources: fallback to Whisper or Claude vision
3. **Parse and format** into readable paragraphs (splits on >1.5s silence gaps)
4. **Save automatically** to organized folders: `media-gobbler/{source}/{timestamp}.md`
5. **Return formatted output** with summary, table of contents, and full text

## Output Format

```
# Transcript

**Source:** [URL]
**Saved to:** [path in Obsidian]

## Summary
[First paragraph + word/section count]

## Contents
1. [Section 1 preview]...
2. [Section 2 preview]...
...

## Full Transcript
[Complete transcript, organized by natural pauses]
```

## Error Handling

- **Unsupported URL**: "Error: Unsupported URL" — skill not yet implemented for that source
- **No captions/subtitles**: "Error: No captions found. Video may lack subtitles."
- **yt-dlp failure**: Full error message from yt-dlp (usually due to ffmpeg missing, video unavailable, or account restrictions)

## Quality Notes

- **Manual subtitles** are preferred over auto-generated captions (better punctuation, proper nouns)
- **SRT format** produces cleaner output than VTT (no HTML entities like `&gt;&gt;`)
- **Paragraph breaks** use audio silence detection (~1.5s gaps) for natural flow
- **Deduplication** removes repeated cues from overlapping subtitle windows
- **Reddit posts** include the post title as the header and summarize with top 5 comments
- **PRAW support** — Reddit API access can be configured with environment variables for better reliability

## Reddit Setup (Optional)

For better Reddit support, configure PRAW:

1. Create a Reddit app at https://www.reddit.com/prefs/apps
2. Set environment variables:
   ```
   export REDDIT_CLIENT_ID="your_id"
   export REDDIT_CLIENT_SECRET="your_secret"
   export REDDIT_USER_AGENT="media-transcribe/1.0 by your_username"
   ```
3. Reload shell: `source ~/.zshrc`

Without credentials, the skill falls back to Reddit's public JSON API (still works, but may be rate-limited).

## Usage Example

```
Transcribe this for me: https://www.youtube.com/watch?v=dQw4w9WgXcQ
```

The skill will:
1. Download captions via yt-dlp
2. Parse and organize into paragraphs
3. Save to `media-gobbler/youtube/20260623_203257_https_www_youtube_com_watch_v_dQw4w9WgXcQ.md`
4. Return formatted output with summary + TOC + full text

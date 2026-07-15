---
name: media-transcribe
description: Transcribe videos and media to text. Use this skill whenever the user wants to transcribe a YouTube video, TikTok, Instagram reel, Reddit post, or Substack post into readable text. Handles auto-captions, manual subtitles, and Whisper audio transcription. Saves organized Markdown files to Obsidian vault with a worth-consuming verdict, substantiated summary, and reflection prompts.
---

# Media Transcribe

Act as a personal media assistant: read the media for the user, return a verdict on whether the original is worth their time, distil the ideas with supporting evidence, and provide reflection prompts to internalise the lessons.

**Script:** `/Users/zhiyuling/lingzhiyu/media-gobbler/transcribe.py`

## How to invoke

Follow these steps in order:

### Step 1 — Run the script

```bash
python3 /Users/zhiyuling/lingzhiyu/media-gobbler/transcribe.py "<URL>"
```

Pass the URL exactly as given. The script handles source detection, transcription, and saving automatically. Multiple URLs may be run in parallel as background tasks.

### Step 1b — Verify image page sequence (Substack only)

If the source is Substack and the transcript contains OCR'd image pages, verify the page order is correct by checking that page markers (e.g. `Page 1`, `Page 2`, …) appear in ascending order through the `## Full Transcript`. If any pages are out of order, reorder the sections manually before proceeding.

### Step 2 — Choose the treatment by content length

Read the saved file (path is in the `**Saved to:**` output) and gauge the substance of the `## Full Transcript`:

- **Light treatment** (caption-only reels, short notes, < ~300 words of substance): 3–5 summary bullets *without* sub-points, 3–5 reflection prompts. Padding a thin piece to the full format makes it worse, not better.
- **Full treatment** (talks, interviews, essays, anything with real depth): everything in Steps 3–5 below.

### Step 3 — Generate the Worth Consuming? verdict

Answer the user's implicit question: *should I spend time on the original?* Three parts:

1. **Verdict** — one of:
   - `Skip — summary covers it` (talking-head content, listicles, anything where the words are the whole value)
   - `Watch/Listen — the original adds value` (visuals, demos, delivery, or emotional register that text can't carry; say what specifically)
   - `Read transcript only` (dense content worth full detail, but no reason to sit through the video)
2. **Signal-to-noise** — e.g. "32-min video, ~8 min of substance, two long sponsor segments".
3. **Time cost** — original runtime/length vs. ~1 min to read this file.

### Step 4 — Generate the summary and title

**Summary:** 5–8 distinct ideas. Each idea is one bold concise sentence, followed by **3 sub-bullets substantiating it** — the concrete examples, evidence, stories, or reasoning the source actually uses. The sub-bullets are what let the user grip the idea without consuming the original.

```
## Summary
- **Idea stated as one sentence:**
  - Concrete example/evidence from the source.
  - Second supporting point or story.
  - Third supporting point, contrast, or consequence.
```

**Title:** Determine the best title:
1. Look for an explicit title in the transcript content itself — e.g. a document header, cover page heading, or article title. Use that verbatim if found.
2. If no official title exists, generate a short descriptive title (4–8 words) that captures the topic based on the content — do NOT use the author's name or publication name as the title.

### Step 5 — Generate reflection prompts

One prompt per summary idea, in the same order, each tagged with the idea it belongs to. Calibrate the register to the nature of the idea:

- **Technical/analytical ideas** (mechanisms, market dynamics, craft techniques): a discussion prompt that deepens understanding of the idea itself — why it works, where it applies, what it implies. Do not force personal framing onto technical material; it strips the context that gives the idea meaning.
- **Self-applicable ideas** (habits, mindset, values, life choices): an introspective prompt that connects the idea to one's own patterns and experiences.

Do not assume or bring in the user's personal context — prompts must stand on the content alone.

```
## Prompts for Reflection
1. *(Idea tag)* Prompt...
2. *(Idea tag)* Prompt...
```

### Step 6 — Update the saved file

1. Replace the auto-generated `## Summary` block with: `## Worth Consuming?` (verdict block), `## Summary` (substantiated bullets), `## Prompts for Reflection` (calibrated prompts) — in that order, all before `## Full Transcript`.
2. Replace the `# Title` H1 at the top of the file with your determined title.
3. Rename the file on disk to match the new title (use `mv` via Bash), sanitizing it the same way: replace non-word characters with `_`, max 80 chars, keep the `YYYYMMDD_HHMMSS_` prefix.

### Step 7 — Report to the user

Print the final title, verdict, summary, and reflection prompts in your response so the user can triage without opening the file.

If the piece is framework-heavy or clearly worth deeper work (it teaches a method, has fillable structure, or the user reacts strongly), offer to run `/article-exercise` on the saved file to turn it into a fillable worksheet.

## Supported sources

| Source | Method | Status |
|--------|--------|--------|
| YouTube | yt-dlp SRT captions | ✅ Working |
| TikTok | yt-dlp audio + Whisper | ✅ Working |
| Reddit | PRAW / public JSON API | ❌ Not supported yet |
| Instagram reels | Playwright: caption (og:description) + frame OCR + MPEG-DASH audio → Whisper | ✅ Working |
| Instagram carousels (`/p/`) | Playwright: caption + slide screenshot OCR | ✅ Working |
| Substack notes (`/note/`) | og:description + Tesseract OCR on attached images | ✅ Working |
| Substack articles (`/p/`) | JSON API (`body_html`) parsed to clean text | ✅ Working |

## Instagram reel strategy

For every reel the script always attempts all three content sources, then combines whatever succeeded:

1. **Caption** — extracted from the rendered Playwright page via `og:description` (most reliable), with fallbacks to `h1` and `article span` elements. Runs unconditionally.
2. **Frame OCR** — after playback, seeks to N evenly-spaced timestamps, screenshots each frame, and OCRs for text overlays. Catches slide-style or text-heavy reels with no voiceover.
3. **Audio → Whisper** — intercepts MPEG-DASH segments from both `cdninstagram.com` and `fbcdn.net` CDN domains (Instagram uses both), concatenates the `m78` audio stream, remuxes with ffmpeg, transcribes with Whisper. Skipped gracefully if no audio segments are captured.

The script only errors if all three come up empty.

## Output

The script prints the full transcript to stdout with:
- `# Title` (H1 from video/post title, or derived from transcript if title is generic)
- `**Source:**` and `**Saved to:**` metadata
- `## Summary` — auto-generated placeholder (always replaced by Claude in Step 6)
- `## Full Transcript` — complete text with natural paragraph breaks

Files are saved to:
```
~/Library/Mobile Documents/iCloud~md~obsidian/Documents/ZY Combined/media-gobbler/{source}/
```
Filename: `YYYYMMDD_HHMMSS_{sanitized_title}.md`

## Error handling

If the script fails, it exits with code 1 and prints an error to stderr. Common causes:
- `No captions found` — YouTube video has no subtitles; no Whisper fallback for YouTube yet
- `yt-dlp failed` — video unavailable, geo-blocked, or platform changed
- `Whisper not installed` — run `pip3 install openai-whisper`
- `Unsupported URL` — source not yet implemented
- Instagram reels: only errors if caption, frame OCR, *and* audio all fail (e.g. genuine login wall). A reel with content only in the caption or only as text overlays will still succeed.

## Dependencies

Run once to install everything:

```bash
./install.sh
```

- **System** (`brew`): `yt-dlp`, `ffmpeg`, `tesseract`
- **Python** (`requirements.txt`): `openai-whisper`, `pytesseract`, `Pillow`, `praw`, `playwright`, `beautifulsoup4`, `requests`, `brotli`, `anthropic`
- **Browser**: Chromium via `playwright install chromium`

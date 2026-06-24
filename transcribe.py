#!/usr/bin/env python3
import re
import subprocess
import sys
import tempfile
import os
import json
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

STORAGE_ROOT = Path("/Users/zhiyuling/Library/Mobile Documents/iCloud~md~obsidian/Documents/ZY Combined/media-gobbler")


def detect_source(url: str) -> str:
    if re.search(r"(youtube\.com|youtu\.be)", url):
        return "youtube"
    if re.search(r"substack\.com", url):
        return "substack"
    if re.search(r"instagram\.com", url):
        return "instagram"
    if re.search(r"tiktok\.com", url):
        return "tiktok"
    if re.search(r"reddit\.com", url):
        return "reddit"
    raise ValueError(f"Unsupported URL: {url}")


def transcribe_youtube(url: str) -> tuple[str, str]:
    """Returns (transcript_text, video_title)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                "yt-dlp",
                "--write-sub",
                "--write-auto-sub",
                "--write-info-json",
                "--sub-langs", "en,en-US",
                "--convert-subs", "srt",
                "--skip-download",
                "--output", os.path.join(tmpdir, "transcript"),
                url,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed:\n{result.stderr}")

        srt_files = list(Path(tmpdir).glob("*.srt"))
        if not srt_files:
            raise RuntimeError("No captions found. Video may lack subtitles.")

        # prefer manual sub over auto-generated
        manual = [f for f in srt_files if "auto" not in f.name]
        srt_path = manual[0] if manual else srt_files[0]
        raw = srt_path.read_text()

        # Extract video title from JSON info
        title = "Untitled"
        json_files = list(Path(tmpdir).glob("*.json"))
        if json_files:
            try:
                info = json.loads(json_files[0].read_text())
                title = info.get('title', 'Untitled')
            except:
                pass

    transcript = _parse_srt(raw)
    return transcript, title


def _srt_time_to_seconds(t: str) -> float:
    h, m, rest = t.split(":")
    s, ms = rest.replace(",", ".").split(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _parse_srt(raw: str) -> str:
    PARAGRAPH_GAP = 1.5  # seconds of silence → new paragraph

    # parse cues: (start_sec, end_sec, text)
    cues = []
    current_lines = []
    start = end = None

    for line in raw.splitlines():
        line = line.strip()
        if re.match(r"^\d+$", line):
            continue
        if "-->" in line:
            parts = re.split(r"\s*-->\s*", line)
            start = _srt_time_to_seconds(parts[0])
            end = _srt_time_to_seconds(parts[1].split()[0])
            current_lines = []
        elif line == "" and start is not None:
            if current_lines:
                text = " ".join(current_lines)
                text = re.sub(r"<[^>]+>", "", text)
                text = text.replace(r"\h", " ").strip()
                if text:
                    cues.append((start, end, text))
            start = end = None
            current_lines = []
        elif start is not None:
            current_lines.append(line)

    if current_lines and start is not None:
        text = " ".join(current_lines)
        text = re.sub(r"<[^>]+>", "", text).replace(r"\h", " ").strip()
        if text:
            cues.append((start, end, text))

    # merge cues into paragraphs, deduplicating adjacent repeated phrases
    paragraphs = []
    current_para = []
    prev_end = None
    seen_lines = set()

    for start, end, text in cues:
        if text in seen_lines:
            continue
        seen_lines.add(text)

        if prev_end is not None and (start - prev_end) > PARAGRAPH_GAP:
            if current_para:
                paragraphs.append(" ".join(current_para))
                current_para = []

        current_para.append(re.sub(r" {2,}", " ", text))
        prev_end = end

    if current_para:
        paragraphs.append(" ".join(current_para))

    return "\n\n".join(paragraphs)


def transcribe_reddit(url: str) -> tuple[str, str]:
    """Returns (transcript_text, post_title). Uses PRAW if available and configured."""
    if PRAW_AVAILABLE and _has_praw_credentials():
        return _transcribe_reddit_praw(url)
    else:
        return _transcribe_reddit_json(url)


def _has_praw_credentials() -> bool:
    """Check if PRAW credentials are configured via environment variables."""
    return all([
        os.getenv('REDDIT_CLIENT_ID'),
        os.getenv('REDDIT_CLIENT_SECRET'),
        os.getenv('REDDIT_USER_AGENT')
    ])


def _transcribe_reddit_praw(url: str) -> tuple[str, str]:
    """Fetch Reddit post using PRAW API."""
    try:
        reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT'),
        )
        submission = reddit.submission(url=url)
        post_title = submission.title

        parts = []

        # Add selftext (post body)
        if submission.selftext and submission.selftext != '[removed]':
            parts.append(submission.selftext)

        # Add top 5 comments
        submission.comments.replace_more(limit=0)  # Load all top-level comments
        for comment in list(submission.comments)[:5]:
            if comment.body and comment.body not in ['[removed]', '[deleted]']:
                author = comment.author.name if comment.author else 'unknown'
                parts.append(f"**{author}**: {comment.body}")

        text = "\n\n".join(parts)
        if not text.strip():
            raise RuntimeError("Reddit post appears to be empty or removed")

        return text, post_title

    except Exception as e:
        raise RuntimeError(f"PRAW error: {e}")


def _transcribe_reddit_json(url: str) -> tuple[str, str]:
    """Fallback: Fetch Reddit post using public JSON API (no authentication)."""
    # Convert reddit URL to JSON API endpoint
    api_url = re.sub(r'(\?[^#]*)?(#.*)?$', '', url.rstrip('/'))
    api_url = f"{api_url}.json"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        req = Request(api_url, headers=headers)
        response = urlopen(req, timeout=10)
        data = json.loads(response.read().decode())
    except Exception as e:
        raise RuntimeError(f"Failed to fetch Reddit post: {e}")

    if not isinstance(data, list) or not data:
        raise RuntimeError("Invalid Reddit URL or post not found")

    post = data[0]['data']['children'][0]['data']
    post_title = post.get('title', 'Untitled')

    # Extract post content
    parts = []

    # Add selftext (post body)
    if post.get('selftext') and post['selftext'] != '[removed]':
        parts.append(post['selftext'])

    # Add top 5 comments
    if len(data) > 1 and data[1]['data']['children']:
        parts.append("\n\n--- Top Comments ---\n")
        for comment_data in data[1]['data']['children'][:5]:  # top 5 comments
            comment = comment_data['data']
            if comment.get('body') and comment['body'] not in ['[removed]', '[deleted]']:
                parts.append(f"**{comment.get('author', 'unknown')}**: {comment['body']}")

    text = "\n\n".join(parts)
    if not text.strip():
        raise RuntimeError("Reddit post appears to be empty or removed")

    return text, post_title


def _whisper_transcribe(audio_path: str, model_name: str = "base", language: str = "en") -> dict:
    """Transcribe audio using Whisper Python API or CLI fallback."""
    if WHISPER_AVAILABLE:
        model = whisper.load_model(model_name)
        return model.transcribe(audio_path, language=language)

    # Fallback: call whisper CLI and parse the resulting JSON
    result = subprocess.run(
        ["whisper", audio_path, "--model", model_name, "--language", language,
         "--output_format", "json", "--output_dir", os.path.dirname(audio_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"whisper CLI failed:\n{result.stderr}")
    json_path = os.path.splitext(audio_path)[0] + ".json"
    return json.loads(Path(json_path).read_text())


def transcribe_tiktok(url: str) -> tuple[str, str]:
    """Returns (transcript_text, video_title). Uses yt-dlp audio extraction + Whisper."""
    whisper_available = WHISPER_AVAILABLE or bool(subprocess.run(
        ["which", "whisper"], capture_output=True).returncode == 0)
    if not whisper_available:
        raise RuntimeError("Whisper not installed. Run: pip3 install openai-whisper")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "video.mp3")

        # Fetch metadata first (title)
        print("[fetching metadata...]", file=sys.stderr)
        meta_result = subprocess.run(
            ["yt-dlp", "--dump-json", url],
            capture_output=True, text=True,
        )
        title = "TikTok Video"
        if meta_result.returncode == 0:
            try:
                info = json.loads(meta_result.stdout)
                uploader = info.get("uploader", "Unknown")
                description = info.get("description", "")[:100]
                title = f"{uploader}: {description}" if description else uploader
            except:
                pass

        # Download audio (keep native AAC to avoid ffprobe codec detection issues)
        print("[downloading audio...]", file=sys.stderr)
        result = subprocess.run(
            [
                "yt-dlp",
                "-f", "worstaudio[acodec=aac]/bestaudio[acodec=aac]/worstvideo[acodec=aac]/bestaudio/worst",
                "-x",
                "-o", os.path.join(tmpdir, "video.%(ext)s"),
                url,
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed to download audio:\n{result.stderr}")

        # Find the audio/video file produced
        audio_files = (list(Path(tmpdir).glob("*.m4a")) or
                       list(Path(tmpdir).glob("*.mp3")) or
                       list(Path(tmpdir).glob("*.mp4")) or
                       list(Path(tmpdir).glob("video.*")))
        if not audio_files:
            raise RuntimeError("yt-dlp did not produce any audio file")
        audio_path = str(audio_files[0])

        # Transcribe with Whisper
        print("[transcribing with Whisper...]", file=sys.stderr)
        try:
            transcript_result = _whisper_transcribe(audio_path)
        except Exception as e:
            raise RuntimeError(f"Whisper transcription failed: {e}")

        text = _parse_whisper_output(transcript_result)
        return text, title


def _parse_whisper_output(whisper_result: dict) -> str:
    """Parse Whisper JSON output into paragraphs split by silence gaps."""
    PARAGRAPH_GAP = 1.5  # seconds of silence → new paragraph

    segments = whisper_result.get("segments", [])
    if not segments:
        raise RuntimeError("Whisper produced no segments")

    paragraphs = []
    current_para = []
    prev_end = None
    seen_text = set()

    for segment in segments:
        text = segment.get("text", "").strip()
        end_time = segment.get("end", 0)

        if not text or text in seen_text:
            continue

        seen_text.add(text)

        # Check for paragraph gap
        if prev_end is not None and (segment.get("start", 0) - prev_end) > PARAGRAPH_GAP:
            if current_para:
                paragraphs.append(" ".join(current_para))
                current_para = []

        current_para.append(text)
        prev_end = end_time

    if current_para:
        paragraphs.append(" ".join(current_para))

    return "\n\n".join(paragraphs)


def transcribe_substack(url: str) -> tuple[str, str]:
    """Returns (transcript_text, post_title). Parses text from meta tags + OCRs content images."""
    import urllib.request as _req
    import urllib.parse as _parse

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }

    req = _req.Request(url, headers=headers)
    html = _req.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")

    # --- Extract note/post text from og:description ---
    title_match = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
    desc_match = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html)

    title = "Substack Post"
    if title_match:
        raw = title_match.group(1)
        # Strip " (@handle)" suffix Substack appends to note titles
        title = re.sub(r'\s*\(@[^)]+\)\s*$', '', raw).strip() or raw.strip()

    note_text = ""
    if desc_match:
        import html as _html
        note_text = _html.unescape(desc_match.group(1)).strip()

    # --- Find content image URLs (S3-hosted, skip profile pics by size pattern) ---
    # Substack CDN URLs embed original S3 paths; content images are 2550x3300 or large
    s3_urls = re.findall(
        r'https://substack-post-media\.s3\.amazonaws\.com/public/images/([^"\'&]+\.(?:jpeg|jpg|png))',
        html
    )
    # Build full S3 URLs, deduplicate, filter out tiny profile pics (named with _72 or _108 etc.)
    seen = set()
    content_images = []
    for fname in s3_urls:
        # Skip small square thumbnails (profile pics, avatars) — content pages are tall
        size_match = re.search(r'_(\d+)x(\d+)\.', fname)
        if size_match:
            w, h = int(size_match.group(1)), int(size_match.group(2))
            if w == h and w < 800:  # square and small → avatar/profile pic
                continue
        s3 = f"https://substack-post-media.s3.amazonaws.com/public/images/{fname}"
        if s3 not in seen:
            seen.add(s3)
            content_images.append(s3)

    # Prefer highest-res CDN variant for OCR accuracy
    cdn_images = []
    for s3 in content_images:
        encoded = _parse.quote(s3, safe="")
        cdn = f"https://substackcdn.com/image/fetch/w_1456,c_limit,f_auto,q_auto:good/{encoded}"
        cdn_images.append(cdn)

    # --- OCR each image with tesseract ---
    image_texts = []
    if cdn_images:
        try:
            import pytesseract
            from PIL import Image
            import io
        except ImportError:
            raise RuntimeError("Install: pip3 install pytesseract Pillow && brew install tesseract")

        for i, img_url in enumerate(cdn_images, 1):
            print(f"[OCR image {i}/{len(cdn_images)}...]", file=sys.stderr)
            try:
                img_req = _req.Request(img_url, headers=headers)
                img_data = _req.urlopen(img_req, timeout=20).read()
                img = Image.open(io.BytesIO(img_data))
                ocr_text = pytesseract.image_to_string(img, lang="eng").strip()
                if ocr_text:
                    image_texts.append(ocr_text)
            except Exception as e:
                print(f"[OCR failed for image {i}: {e}]", file=sys.stderr)

    # --- Combine note text + OCR'd image text ---
    parts = [note_text] if note_text else []
    parts.extend(image_texts)
    full_text = "\n\n---\n\n".join(parts)

    if not full_text.strip():
        raise RuntimeError("No content found in Substack post")

    return full_text, title


def _transcribe_video_url(url: str, source_label: str = "Video") -> tuple[str, str]:
    """Generic video URL transcriber via yt-dlp -x + Whisper. Used for Instagram etc."""
    whisper_available = WHISPER_AVAILABLE or bool(subprocess.run(
        ["which", "whisper"], capture_output=True).returncode == 0)
    if not whisper_available:
        raise RuntimeError("Whisper not installed. Run: pip3 install openai-whisper")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Fetch metadata
        meta_result = subprocess.run(
            ["yt-dlp", "--dump-json", url], capture_output=True, text=True,
        )
        title = f"{source_label} Video"
        if meta_result.returncode == 0:
            try:
                info = json.loads(meta_result.stdout)
                title = info.get("title") or info.get("description", "")[:80] or title
            except:
                pass

        # Download audio (keep native format to avoid codec detection issues)
        result = subprocess.run(
            ["yt-dlp", "-x", "-o", os.path.join(tmpdir, "video.%(ext)s"), url],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed:\n{result.stderr}")

        mp3_files = (list(Path(tmpdir).glob("*.m4a")) or
                     list(Path(tmpdir).glob("*.mp3")) or
                     list(Path(tmpdir).glob("*.mp4")) or
                     list(Path(tmpdir).glob("video.*")))
        if not mp3_files:
            raise RuntimeError("yt-dlp did not produce any audio file")

        transcript_result = _whisper_transcribe(str(mp3_files[0]))
        text = _parse_whisper_output(transcript_result)
        return text, title


def transcribe_instagram(url: str) -> tuple[str, str]:
    """Returns (transcript_text, title). Uses same approach as TikTok."""
    return _transcribe_video_url(url, source_label="Instagram")


HANDLERS = {
    "youtube": transcribe_youtube,
    "reddit": transcribe_reddit,
    "tiktok": transcribe_tiktok,
    "substack": transcribe_substack,
    "instagram": transcribe_instagram,
}


def _extract_key_points(text: str) -> str:
    """Extract key content points from transcript sections."""
    paragraphs = text.split("\n\n")

    key_points = []

    # Create overview from first paragraph (usually intro)
    if paragraphs:
        first = paragraphs[0].split('.')
        overview = first[0] if first else "Video content"
        key_points.append(f"**Overview:** {overview}")
        key_points.append("")

    # Extract key point from each section (first 8 sections)
    for i, para in enumerate(paragraphs[1:9], 1):  # Skip intro, get next 8
        sentences = re.split(r'(?<=[.!?])\s+', para.strip())
        if sentences:
            # Extract key topic: first sentence, condensed
            sent = sentences[0]
            # Remove filler words and keep core message
            sent = re.sub(r'^(We|I|You|This|The|It|There)\s+(are|is|was|were|started|made|got|found|had|did|can|will)\s+', '', sent)
            if len(sent) > 100:
                sent = sent[:100].rsplit(' ', 1)[0] + "..."
            if sent and sent not in key_points:  # Avoid duplicates
                key_points.append(f"**Section {i}:** {sent}")

    return "\n".join(key_points)


_GENERIC_TITLES = {
    "", "untitled", "transcript", "video", "tiktok video", "instagram video",
    "substack post", "reddit post", "youtube video",
}

def _derive_title(text: str, max_len: int = 80) -> str:
    """Derive a title from the first meaningful sentence of the transcript."""
    for para in text.split("\n\n"):
        para = para.strip()
        if not para or para.startswith("---"):
            continue
        # Take first sentence
        sentence = re.split(r'(?<=[.!?])\s+', para)[0].strip()
        sentence = re.sub(r'\s+', ' ', sentence)
        if len(sentence) < 10:
            continue
        if len(sentence) > max_len:
            sentence = sentence[:max_len].rsplit(' ', 1)[0] + "…"
        return sentence
    return "Transcript"


def save_transcript(source: str, url: str, text: str, title: str = "") -> Path:
    folder = STORAGE_ROOT / source
    folder.mkdir(parents=True, exist_ok=True)

    # Fall back to content-derived title if metadata title is missing or generic
    if not title or title.lower().strip() in _GENERIC_TITLES:
        title = _derive_title(text)

    filename_title = re.sub(r"[^\w\-]", "_", title)[:80]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = folder / f"{timestamp}_{filename_title}.md"

    # Build content with summary + TOC + full transcript
    paragraphs = text.split("\n\n")

    # Generate TOC
    toc_lines = []
    for i, para in enumerate(paragraphs, 1):
        para_title = " ".join(para.split()[:8]).rstrip(".,!?;:") + "..."
        toc_lines.append(f"{i}. {para_title}")
    toc = "\n".join(toc_lines)

    # Generate key points summary
    key_points = _extract_key_points(text)
    word_count = len(text.split())
    summary = f"""{key_points}

**Stats:** {word_count} words across {len(paragraphs)} sections"""

    # Build file content
    header = f"# {title}" if title else "# Transcript"
    content = f"""{header}

**Source:** {url}

## Summary
{summary}

## Full Transcript
{text}
"""
    path.write_text(content)
    return path


def transcribe(url: str) -> tuple[str, Path, str]:
    """Returns (transcript_text, saved_path, title)"""
    source = detect_source(url)
    result = HANDLERS[source](url)

    # Handle handlers that return (text, title) vs just text
    if isinstance(result, tuple):
        text, title = result
    else:
        text = result
        title = ""

    saved = save_transcript(source, url, text, title)
    return text, saved, title


def format_output(url: str, text: str, saved_path: Path, title: str = "") -> str:
    paragraphs = text.split("\n\n")

    # Generate summary with key points
    key_points = _extract_key_points(text)
    word_count = len(text.split())
    summary = f"""{key_points}

**Stats:** {word_count} words across {len(paragraphs)} sections"""

    if not title or title.lower().strip() in _GENERIC_TITLES:
        title = _derive_title(text)
    header = f"# {title}"

    output = f"""{header}

**Source:** {url}
**Saved to:** {saved_path}

## Summary
{summary}

## Full Transcript
{text}
"""
    return output


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python transcribe.py <url>", file=sys.stderr)
        sys.exit(1)
    try:
        url = sys.argv[1]
        text, saved_path, title = transcribe(url)
        output = format_output(url, text, saved_path, title)
        print(output)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

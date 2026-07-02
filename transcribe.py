#!/usr/bin/env python3
import re
import subprocess
import sys
import tempfile
import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

from dotenv import load_dotenv
load_dotenv()

# Resolve binaries from the venv that owns this interpreter, falling back to PATH.
# Works correctly whether invoked as `./venv/bin/python3` or with system Python.
_VENV_BIN = Path(sys.executable).parent
def _resolve_bin(name: str) -> str:
    venv_path = _VENV_BIN / name
    if os.access(venv_path, os.X_OK):
        return str(venv_path)
    on_path = shutil.which(name)
    return on_path if on_path else name

YT_DLP = _resolve_bin("yt-dlp")
WHISPER_BIN = _resolve_bin("whisper")

def _require_ytdlp() -> None:
    if not os.access(YT_DLP, os.X_OK):
        raise RuntimeError(
            "yt-dlp not found. Run ./install.sh, then invoke via ./venv/bin/python3 "
            "or activate the venv first: source venv/bin/activate"
        )

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

_storage_root_env = os.getenv("STORAGE_ROOT")
if not _storage_root_env:
    raise RuntimeError(
        "STORAGE_ROOT is not set. Copy .env.example to .env and set:\n"
        "  STORAGE_ROOT=/path/to/your/vault/folder"
    )
STORAGE_ROOT = Path(_storage_root_env).expanduser()


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
    _require_ytdlp()
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                YT_DLP,
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
        [WHISPER_BIN, audio_path, "--model", model_name, "--language", language,
         "--output_format", "json", "--output_dir", os.path.dirname(audio_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"whisper CLI failed:\n{result.stderr}")
    json_path = os.path.splitext(audio_path)[0] + ".json"
    return json.loads(Path(json_path).read_text())


def transcribe_tiktok(url: str) -> tuple[str, str]:
    """Returns (transcript_text, video_title). Uses yt-dlp audio extraction + Whisper."""
    _require_ytdlp()
    whisper_available = WHISPER_AVAILABLE or os.access(WHISPER_BIN, os.X_OK)
    if not whisper_available:
        raise RuntimeError("Whisper not installed. Run: pip3 install openai-whisper")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "video.mp3")

        # Fetch metadata first (title)
        print("[fetching metadata...]", file=sys.stderr)
        meta_result = subprocess.run(
            [YT_DLP, "--dump-json", url],
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
                YT_DLP,
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


def _html_to_text(body_html: str) -> str:
    """Convert Substack body_html to plain text paragraphs."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError("Install: pip3 install beautifulsoup4")
    import html as _html_mod
    soup = BeautifulSoup(body_html, "html.parser")
    for tag in soup(["script", "style", "figure", "figcaption"]):
        tag.decompose()
    paragraphs = []
    for elem in soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "blockquote"]):
        # Skip <p> tags nested directly inside <li> — the <li> already captures the text
        if elem.name == "p" and elem.parent and elem.parent.name == "li":
            continue
        text = elem.get_text(" ", strip=True)
        text = _html_mod.unescape(text).strip()
        if text and len(text) > 2:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def transcribe_substack(url: str) -> tuple[str, str]:
    """Returns (transcript_text, post_title).
    - Full articles: fetches body_html from Substack JSON API.
    - Notes (/note/...): parses og:description + OCRs attached images.
    """
    import urllib.request as _req
    import urllib.parse as _parse
    import html as _html

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }

    # --- Detect URL type ---
    is_note = "/note/" in url

    # --- Fetch HTML for title + images regardless ---
    req = _req.Request(url, headers=headers)
    html_page = _req.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")

    title_match = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html_page)
    title = "Substack Post"
    if title_match:
        raw = _html.unescape(title_match.group(1))
        title = re.sub(r'\s*\(@[^)]+\)\s*$', '', raw).strip() or raw.strip()

    # --- Full article: use JSON API ---
    if not is_note:
        # Extract publication domain + slug from URL
        m = re.match(r'https?://([^/]+)/p/([^/?#]+)', url)
        if m:
            domain, slug = m.group(1), m.group(2)
            api_url = f"https://{domain}/api/v1/posts/{slug}"
            try:
                api_req = _req.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
                api_data = json.loads(_req.urlopen(api_req, timeout=15).read())
                body_html = api_data.get("body_html", "")
                if body_html:
                    title = api_data.get("title") or title
                    article_text = _html_to_text(body_html)
                    if article_text.strip():
                        return article_text, title
            except Exception as e:
                print(f"[API fetch failed, falling back to HTML: {e}]", file=sys.stderr)

    # --- Notes (or API fallback): og:description + image OCR ---
    desc_match = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html_page)
    note_text = ""
    if desc_match:
        note_text = _html.unescape(desc_match.group(1)).strip()

    # --- Find content image URLs (S3-hosted, skip profile pics by size pattern) ---
    # Substack CDN URLs embed original S3 paths; content images are 2550x3300 or large
    s3_urls = re.findall(
        r'https://substack-post-media\.s3\.amazonaws\.com/public/images/([^"\'&]+\.(?:jpeg|jpg|png))',
        html_page
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

        # Sort pages by the "Page N" footer OCR typically picks up (e.g. "Page 1", "Page 2")
        def _page_num(t: str) -> int:
            m = re.search(r'\bPage\s+(\d+)\b', t, re.IGNORECASE)
            return int(m.group(1)) if m else 9999

        image_texts.sort(key=_page_num)

    # --- Combine note text + OCR'd image text ---
    parts = [note_text] if note_text else []
    parts.extend(image_texts)
    full_text = "\n\n---\n\n".join(parts)

    if not full_text.strip():
        raise RuntimeError("No content found in Substack post")

    return full_text, title


def _transcribe_video_url(url: str, source_label: str = "Video") -> tuple[str, str]:
    """Generic video URL transcriber via yt-dlp -x + Whisper. Used for Instagram etc."""
    _require_ytdlp()
    whisper_available = WHISPER_AVAILABLE or os.access(WHISPER_BIN, os.X_OK)
    if not whisper_available:
        raise RuntimeError("Whisper not installed. Run: pip3 install openai-whisper")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Fetch metadata
        meta_result = subprocess.run(
            [YT_DLP, "--dump-json", url], capture_output=True, text=True,
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
            [YT_DLP, "-x", "-o", os.path.join(tmpdir, "video.%(ext)s"), url],
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
    """Returns (transcript_text, title).

    Strategy:
    - Scrapes the /embed/ page to get the caption and detect post type.
    - Carousels / image posts: uses Playwright to screenshot each slide (bypasses
      CDN auth) then OCRs the screenshots.
    - Video posts: falls back to yt-dlp audio + Whisper.
    """
    import urllib.request as _req, html as _html_mod

    # ── Step 1: Fetch embed page for metadata & post-type detection ──────────
    shortcode = re.search(r'/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
    if not shortcode:
        raise RuntimeError(f"Cannot parse Instagram shortcode from URL: {url}")
    sc = shortcode.group(1)
    embed_url = f"https://www.instagram.com/p/{sc}/embed/"

    embed_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html",
    }
    try:
        page_html = _req.urlopen(
            _req.Request(embed_url, headers=embed_headers), timeout=15
        ).read().decode("utf-8", errors="replace")
    except Exception as e:
        page_html = ""

    # /reel/ and /tv/ URLs are always videos; /p/ can be image, carousel, or video
    is_reel = bool(re.search(r'/(?:reel|tv)/', url))
    is_video = is_reel or bool(re.search(r'"is_video"\s*:\s*true', page_html))

    # Caption from embed JSON
    normalised = page_html.replace(r"\\/", "/").replace(r"\/", "/")
    cap_m = re.search(
        r'"edge_media_to_caption".*?"text"\s*:\s*"((?:[^"\\]|\\.)*)"',
        normalised, re.DOTALL
    )
    caption = ""
    if cap_m:
        try:
            caption = cap_m.group(1).encode("utf-8").decode("unicode_escape")
        except Exception:
            caption = cap_m.group(1)
        caption = caption.replace("\\n", "\n").strip()

    # Title from caption first line, or fallback
    first_line = caption.split("\n")[0].strip() if caption else ""
    title = first_line[:80] if first_line else f"Instagram Post {sc}"

    # ── Step 2a: Image / carousel → Playwright screenshot + OCR ─────────────
    if not is_video:
        try:
            import pytesseract
            from PIL import Image
            import io as _io
        except ImportError:
            raise RuntimeError(
                "Install: pip3 install pytesseract Pillow && brew install tesseract"
            )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "Install: pip3 install playwright && playwright install chromium"
            )

        screenshots: list[bytes] = []
        with sync_playwright() as pw:
            tmp_profile = tempfile.mkdtemp(prefix="ig_pw_")
            try:
                ctx = pw.chromium.launch_persistent_context(
                    user_data_dir=tmp_profile,
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                pg = ctx.new_page()
                pg.goto(url, wait_until="domcontentloaded", timeout=30000)
                pg.wait_for_timeout(2000)

                # Dismiss login/signup modal if present (Escape or close button)
                try:
                    pg.keyboard.press("Escape")
                    pg.wait_for_timeout(500)
                except Exception:
                    pass
                try:
                    close = pg.locator("[aria-label='Close']").first
                    if close.is_visible(timeout=1000):
                        close.click(force=True)
                        pg.wait_for_timeout(500)
                except Exception:
                    pass

                # Find the article/post container
                article = pg.locator("article").first

                def _shot_slide() -> bytes:
                    """Screenshot the slide image area only (left ~55% of article).
                    Instagram desktop layout: image on left, caption sidebar on right.
                    Cropping to left side excludes the repeating caption sidebar from OCR.
                    """
                    try:
                        raw = article.screenshot()
                    except Exception:
                        raw = pg.screenshot()
                    img_full = Image.open(_io.BytesIO(raw))
                    w, h = img_full.size
                    # Crop to the square image area (left portion, height-based)
                    # The slide image is square, so crop to min(w*0.55, h) width
                    crop_w = min(int(w * 0.55), h)
                    cropped = img_full.crop((0, 0, crop_w, h))
                    buf = _io.BytesIO()
                    cropped.save(buf, format="PNG")
                    return buf.getvalue()

                screenshots.append(_shot_slide())

                # Navigate carousel using force=True to bypass overlay interception
                for _ in range(20):
                    nxt = pg.locator("[aria-label='Next']").first
                    if not nxt.is_visible(timeout=1000):
                        break
                    try:
                        nxt.click(force=True, timeout=5000)
                    except Exception:
                        break
                    pg.wait_for_timeout(600)
                    screenshots.append(_shot_slide())

                ctx.close()
            finally:
                shutil.rmtree(tmp_profile, ignore_errors=True)

        # OCR screenshots — deduplicate text seen in previous slides
        image_texts: list[str] = []
        seen_lines: set[str] = set()
        for i, ss in enumerate(screenshots, 1):
            print(f"[OCR slide {i}/{len(screenshots)}...]", file=sys.stderr)
            img = Image.open(_io.BytesIO(ss))
            text = pytesseract.image_to_string(img, lang="eng").strip()
            if not text or len(text) < 15:
                continue
            # Remove lines that appeared in previous slides (UI chrome repeats)
            lines = text.splitlines()
            fresh = [l for l in lines if l.strip() and l.strip() not in seen_lines]
            seen_lines.update(l.strip() for l in lines if l.strip())
            clean = "\n".join(fresh).strip()
            if clean and len(clean) > 15:
                image_texts.append(clean)

        parts = [caption] if caption else []
        parts.extend(image_texts)
        if not parts:
            raise RuntimeError("No content extracted from Instagram post")
        return "\n\n---\n\n".join(parts), title

    # ── Step 2b: Video → yt-dlp + Whisper ────────────────────────────────────
    else:
        # Instagram serves reels as MPEG-DASH (fragmented MP4 over blob: URLs).
        # yt-dlp can't decrypt macOS Keychain cookies, so we use Playwright to
        # intercept ALL video/mp4 CDN segment responses in arrival order, concatenate
        # them (init segment first gives ffmpeg the moov/trex boxes it needs), then
        # pass the reassembled file to Whisper.
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("Install: pip3 install playwright && playwright install chromium")

        # Instagram serves DASH: m86 = video stream, m78 = audio stream.
        # The browser makes multiple HTTP Range requests to the same CDN URL.
        # We collect ALL responses (not deduped) and separate by stream type.
        # Whisper only needs audio, so we reassemble only the m78 audio stream.
        audio_chunks: list[bytes] = []   # m78 audio range responses, in order
        video_init_chunks: list[bytes] = []  # m86 init (first small response) + data

        post_url = f"https://www.instagram.com/p/{sc}/"
        with sync_playwright() as pw:
            tmp_profile2 = tempfile.mkdtemp(prefix="ig_pw_video_")
            try:
                ctx2 = pw.chromium.launch_persistent_context(
                    user_data_dir=tmp_profile2,
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                pg2 = ctx2.new_page()

                def _capture_segment(resp):
                    ct = resp.headers.get("content-type", "")
                    if "video" not in ct and "mp4" not in resp.url:
                        return
                    if "cdninstagram.com" not in resp.url:
                        return
                    try:
                        data = resp.body()
                    except Exception:
                        return
                    if not data or len(data) < 100:
                        return
                    # m78 = audio stream, m86 = video stream (we want both for muxing)
                    if "/m78/" in resp.url:
                        audio_chunks.append(data)
                    elif "/m86/" in resp.url or "/m85/" in resp.url:
                        video_init_chunks.append(data)

                def _play_and_wait(pg):
                    """Start video, wait for full duration so all audio segments are fetched."""
                    pg.keyboard.press("Escape")
                    pg.wait_for_timeout(1000)
                    duration = None
                    try:
                        duration = pg.evaluate(
                            "() => { const v = document.querySelector('video'); return v ? v.duration : null; }"
                        )
                        pg.evaluate(
                            "() => { const v = document.querySelector('video'); if (v) { v.currentTime = 0; v.play(); } }"
                        )
                    except Exception:
                        pass
                    wait_ms = int((duration or 90) * 1000) + 8000
                    print(f"[Reel duration {duration or '?'}s — waiting {wait_ms//1000}s for full audio...]", file=sys.stderr)
                    pg.wait_for_timeout(wait_ms)

                pg2.on("response", _capture_segment)
                pg2.goto(post_url, wait_until="networkidle", timeout=30000)
                _play_and_wait(pg2)

                if not audio_chunks and not video_init_chunks:
                    pg2.goto(url, wait_until="networkidle", timeout=30000)
                    _play_and_wait(pg2)

                ctx2.close()
            finally:
                shutil.rmtree(tmp_profile2, ignore_errors=True)

        if not audio_chunks and not video_init_chunks:
            raise RuntimeError(
                "Could not capture video/audio from Instagram reel via Playwright. "
                "The post may require login or the video didn't load."
            )

        audio_kb = sum(len(c) for c in audio_chunks) // 1024
        video_kb = sum(len(c) for c in video_init_chunks) // 1024
        print(f"[Captured audio={audio_kb}KB video={video_kb}KB, muxing...]", file=sys.stderr)

        whisper_available = WHISPER_AVAILABLE or os.access(WHISPER_BIN, os.X_OK)
        if not whisper_available:
            raise RuntimeError("Whisper not installed. Run: pip3 install openai-whisper")

        with tempfile.TemporaryDirectory() as tmpdir:
            if audio_chunks:
                # Write raw-concatenated audio stream (fMP4: init + data segments)
                audio_raw = os.path.join(tmpdir, "audio_raw.mp4")
                with open(audio_raw, "wb") as f:
                    for chunk in audio_chunks:
                        f.write(chunk)
                # Re-mux into a proper MP4 so ffmpeg/Whisper can decode it
                audio_mux = os.path.join(tmpdir, "audio.mp4")
                mux = subprocess.run(
                    ["ffmpeg", "-y", "-i", audio_raw, "-c:a", "copy", audio_mux],
                    capture_output=True, text=True,
                )
                out_path = audio_mux if mux.returncode == 0 and os.path.exists(audio_mux) else audio_raw
            else:
                # Fallback: use video stream (has audio track too for most reels)
                video_raw = os.path.join(tmpdir, "video_raw.mp4")
                with open(video_raw, "wb") as f:
                    for chunk in video_init_chunks:
                        f.write(chunk)
                out_path = video_raw

            print(f"[Whisper transcribing reel...]", file=sys.stderr)
            spoken = _parse_whisper_output(_whisper_transcribe(out_path))

        parts = [caption] if caption else []
        if spoken:
            parts.append(spoken)
        return "\n\n---\n\n".join(parts), title


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

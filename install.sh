#!/bin/bash
set -e

echo "→ Installing system dependencies..."
if command -v brew &>/dev/null; then
    brew install yt-dlp ffmpeg tesseract
elif [[ "$(uname)" == "Linux" ]]; then
    echo "  (Linux detected — installing via apt-get)"
    sudo apt-get update -qq
    sudo apt-get install -y ffmpeg tesseract-ocr
    # yt-dlp not in apt; install via pip below
else
    echo "  (unknown OS — install yt-dlp, ffmpeg, and tesseract manually)"
fi

echo "→ Creating Python virtual environment..."
python3 -m venv venv

echo "→ Installing Python packages into venv..."
./venv/bin/pip install -r requirements.txt

echo "→ Installing Playwright browser (needed for Instagram image/carousel posts)..."
./venv/bin/python -m playwright install chromium

echo ""
echo "✅ Done. Activate the venv and run:"
echo "   source venv/bin/activate"
echo "   python transcribe.py <url>"
echo ""
echo "Or without activating:"
echo "   ./venv/bin/python transcribe.py <url>"
echo ""
echo "Don't forget to copy .env.example → .env and set STORAGE_ROOT."

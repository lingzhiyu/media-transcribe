#!/bin/bash
# Install all dependencies for media-transcribe

set -e

echo "→ Installing system dependencies..."
brew install yt-dlp ffmpeg tesseract

echo "→ Installing Python packages..."
pip3 install --break-system-packages -r requirements.txt

echo "→ Installing Playwright browser..."
python3 -m playwright install chromium

echo "✅ Done. Run: python3 transcribe.py <url>"

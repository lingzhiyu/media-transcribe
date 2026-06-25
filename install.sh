#!/bin/bash
set -e

echo "→ Installing system dependencies..."
if command -v brew &>/dev/null; then
    brew install ffmpeg tesseract
elif [[ "$(uname)" == "Linux" ]]; then
    echo "  (Linux detected — installing via apt-get)"
    sudo apt-get update -qq
    sudo apt-get install -y ffmpeg tesseract-ocr
else
    echo "  (unknown OS — install ffmpeg and tesseract manually)"
fi

echo "→ Creating Python virtual environment..."
python3 -m venv venv

echo "→ Installing Python packages into venv..."
./venv/bin/pip install -r requirements.txt

echo ""
echo "✅ Done. Activate the venv and run:"
echo "   source venv/bin/activate"
echo "   python transcribe.py <url>"
echo ""
echo "Or without activating:"
echo "   ./venv/bin/python transcribe.py <url>"
echo ""
echo "Don't forget to copy .env.example → .env and set STORAGE_ROOT."

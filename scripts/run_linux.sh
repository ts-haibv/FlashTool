#!/bin/bash
# ────────────────────────────────────────────────────────────────────────────
# FlashTool — Linux launcher
# ────────────────────────────────────────────────────────────────────────────
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SCRIPT_DIR"

echo "⚡ FlashTool — G6-family ROM Flash Tool"
echo "─────────────────────────────────"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install: sudo apt install python3 python3-pip"
    exit 1
fi

# Check tkinter
python3 -c "import tkinter" 2>/dev/null || {
    echo "❌ tkinter not found. Install: sudo apt install python3-tk"
    exit 1
}

# Check adb/fastboot
for tool in adb fastboot; do
    if command -v $tool &> /dev/null; then
        echo "  ✅ $tool: $(which $tool)"
    else
        echo "  ⚠️  $tool not found. Install: sudo apt install android-tools-adb android-tools-fastboot"
    fi
done

# Setup venv if needed
if [ ! -d ".venv" ]; then
    echo ""
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo ""
echo "📦 Checking dependencies..."
pip install -q -r requirements.txt

# Launch
echo ""
echo "🚀 Launching FlashTool..."
python main.py

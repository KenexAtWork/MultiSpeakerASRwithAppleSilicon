#!/bin/bash
# Web Live ASR — startup script
set -e

SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

# Activate venv
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Load .env
if [ -f ".env" ]; then
    set -a; source .env; set +a
fi

# Check deps
python -c "import fastapi" 2>/dev/null || {
    echo "⏳ Installing web dependencies..."
    uv pip install -r web/requirements.txt
}

echo "🚀 Starting Web Live ASR at http://localhost:8000"
echo "💡 Press Ctrl+C to stop"
echo ""
uvicorn web.server:app --host 0.0.0.0 --port 8000

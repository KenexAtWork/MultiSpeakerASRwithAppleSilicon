#!/bin/bash

# ASR GUI 啟動腳本

set -e

# 取得腳本所在目錄
SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 檢查並啟動虛擬環境
if [ -d ".venv" ]; then
    echo "✓ 使用 .venv 虛擬環境"
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "✓ 使用 venv 虛擬環境"
    source venv/bin/activate
else
    echo "⚠️  未找到虛擬環境，使用系統 Python"
    echo "建議建立虛擬環境："
    echo "  python3 -m venv .venv"
    echo "  或"
    echo "  uv venv --python /opt/homebrew/bin/python3"
    echo ""
fi

# 檢查必要套件（使用 pip list 避免 import 時的初始化延遲）
echo "檢查必要套件..."

MISSING_PACKAGES=()

if ! python -m pip list 2>/dev/null | grep -q "mlx-whisper"; then
    MISSING_PACKAGES+=("mlx-whisper")
fi

if ! python -m pip list 2>/dev/null | grep -q "pyannote.audio"; then
    MISSING_PACKAGES+=("pyannote-audio")
fi

if ! python -m pip list 2>/dev/null | grep -q "PyQt6"; then
    MISSING_PACKAGES+=("PyQt6")
fi

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo "❌ 缺少以下套件: ${MISSING_PACKAGES[*]}"
    echo "請執行: python -m pip install ${MISSING_PACKAGES[*]}"
    exit 1
fi

echo "✓ 所有套件已就緒"

# 載入 .env 檔案（如果存在）
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
    echo "✓ 已載入 .env 檔案"
fi

# 檢查 HF_TOKEN
if [ -z "$HF_TOKEN" ]; then
    echo ""
    echo "⚠️  警告：未設定 HF_TOKEN"
    echo "說話者分離功能需要 Hugging Face token"
    echo "請在 .env 檔案中設定或執行："
    echo "  export HF_TOKEN=your_token_here"
    echo ""
    read -p "是否繼續啟動 GUI？[y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 啟動 GUI
echo ""
echo "🚀 啟動 ASR GUI..."
python gui/main.py

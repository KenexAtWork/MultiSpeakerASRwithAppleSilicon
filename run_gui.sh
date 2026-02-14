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
    echo "⚠️  未找到虛擬環境"
    echo "請先建立虛擬環境："
    echo "  uv venv --python 3.10"
    echo "  source .venv/bin/activate"
    exit 1
fi

# 檢查必要套件，缺少則自動安裝
echo "檢查必要套件..."

# 優先用 uv pip list，fallback 到 python -m pip list
if command -v uv &>/dev/null; then
    PIP_LIST=$(uv pip list 2>/dev/null)
else
    PIP_LIST=$(python -m pip list 2>/dev/null)
fi

MISSING_PACKAGES=()

if ! echo "$PIP_LIST" | grep -q "mlx-whisper"; then
    MISSING_PACKAGES+=("mlx-whisper")
fi

if ! echo "$PIP_LIST" | grep -q "pyannote-audio"; then
    MISSING_PACKAGES+=("pyannote-audio")
fi

if ! echo "$PIP_LIST" | grep -q "PyQt6"; then
    MISSING_PACKAGES+=("PyQt6")
fi

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo "⏳ 安裝缺少的套件: ${MISSING_PACKAGES[*]}"
    if command -v uv &>/dev/null; then
        uv pip install "${MISSING_PACKAGES[@]}"
    else
        python -m pip install "${MISSING_PACKAGES[@]}"
    fi
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

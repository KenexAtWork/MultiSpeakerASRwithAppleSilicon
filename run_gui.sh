#!/bin/bash

# ASR GUI 啟動腳本

set -e

# 取得腳本所在目錄
SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 啟動虛擬環境
if [ ! -d ".venv" ]; then
    echo "錯誤：找不到虛擬環境 .venv"
    echo "請先執行安裝步驟"
    exit 1
fi

source .venv/bin/activate

# 檢查 PyQt6 是否已安裝
if ! python -c "import PyQt6" 2>/dev/null; then
    echo "正在安裝 PyQt6..."
    pip install PyQt6
fi

# 載入 .env 檔案（如果存在）
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
    echo "✓ 已載入 .env 檔案"
fi

# 啟動 GUI
echo "啟動 ASR GUI..."
python gui/main.py

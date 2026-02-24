#!/bin/bash

# ASR Multi-Speaker 安裝腳本
# 適用於 macOS (Apple Silicon)

set -e

echo "=========================================="
echo "  ASR Multi-Speaker 安裝程式"
echo "=========================================="
echo ""

# 取得腳本所在目錄
SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. 檢查 Python 版本
echo "📋 [1/5] 檢查 Python 版本..."

# 嘗試找到合適的 Python 版本
PYTHON_CMD=""
for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v $cmd &>/dev/null; then
        VERSION=$($cmd --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo $VERSION | cut -d. -f1)
        MINOR=$(echo $VERSION | cut -d. -f2)
        
        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON_CMD=$cmd
            PYTHON_VERSION=$VERSION
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ 錯誤：未找到 Python 3.10 或更新版本"
    echo ""
    echo "請安裝 Python 3.10+："
    echo "  方法 1 - 使用 Homebrew（推薦）："
    echo "    brew install python@3.10"
    echo ""
    echo "  方法 2 - 從官網下載："
    echo "    https://www.python.org/downloads/"
    echo ""
    exit 1
fi

echo "✓ 找到 Python：$PYTHON_CMD"
echo "✓ 版本：$PYTHON_VERSION"
echo ""

# 2. 檢查/安裝 uv
echo "📋 [2/5] 檢查 uv 套件管理器..."
if ! command -v uv &>/dev/null; then
    echo "⏳ 安裝 uv（Python 套件管理器）..."
    echo "提示：uv 比 pip 快 10-100 倍"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # 重新載入 PATH
    export PATH="$HOME/.cargo/bin:$PATH"
    
    if ! command -v uv &>/dev/null; then
        echo "❌ uv 安裝失敗"
        echo "請手動安裝：https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
fi

echo "✓ uv 已安裝"
echo ""

# 3. 建立虛擬環境
echo "📋 [3/5] 建立虛擬環境..."
if [ -d ".venv" ]; then
    echo "⚠️  虛擬環境已存在，是否重新建立？[y/N]"
    read -r -n 1 REPLY
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf .venv
        uv venv --python $PYTHON_CMD
        echo "✓ 虛擬環境已重新建立"
    else
        echo "✓ 使用現有虛擬環境"
    fi
else
    uv venv --python $PYTHON_CMD
    echo "✓ 虛擬環境已建立（使用 $PYTHON_CMD）"
fi

# 啟動虛擬環境
source .venv/bin/activate
echo ""

# 4. 安裝依賴套件
echo "📋 [4/5] 安裝依賴套件..."
echo "⏳ 這可能需要 2-5 分鐘，請稍候..."
echo ""

# 顯示安裝進度
uv pip install -e ".[all]"

echo ""
echo "✓ 所有套件已安裝"
echo ""

# 5. 設定環境變數
echo "📋 [5/5] 設定環境變數..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "✓ 已建立 .env 檔案（從 .env.example 複製）"
    else
        cat > .env << 'EOF'
# Hugging Face Token（用於說話者分離）
# 請到 https://huggingface.co/settings/tokens 取得
HF_TOKEN=

# AWS 設定（用於摘要功能，可選）
AWS_REGION=us-west-2
AWS_PROFILE=default
EOF
        echo "✓ 已建立 .env 檔案"
    fi
    
    echo ""
    echo "⚠️  請編輯 .env 檔案並填入你的 Hugging Face Token："
    echo "   1. 前往 https://huggingface.co/settings/tokens"
    echo "   2. 建立新 token（需要 read 權限）"
    echo "   3. 將 token 填入 .env 檔案的 HF_TOKEN="
    echo ""
else
    echo "✓ .env 檔案已存在"
    echo ""
fi

# 完成
echo "=========================================="
echo "  ✅ 安裝完成！"
echo "=========================================="
echo ""
echo "📝 下一步："
echo "   1. 編輯 .env 檔案，填入 HF_TOKEN"
echo "   2. 執行 ./run_gui.sh 啟動 GUI"
echo ""
echo "💡 提示："
echo "   - 首次執行會下載 AI 模型（約 1.7 GB）"
echo "   - 需要穩定的網路連線"
echo "   - 下載完成後會自動快取，之後啟動很快"
echo ""

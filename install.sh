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

# 1. 檢查/安裝 uv
echo "📋 [1/4] 檢查 uv 套件管理器..."
if ! command -v uv &>/dev/null; then
    echo "⏳ 安裝 uv（Python 套件管理器）..."
    echo "提示：uv 比 pip 快 10-100 倍，且可自動管理 Python 版本"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # 重新載入 PATH（uv 可能安裝在 ~/.local/bin 或 ~/.cargo/bin）
    if [ -f "$HOME/.local/bin/env" ]; then
        source "$HOME/.local/bin/env"
    fi
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    
    if ! command -v uv &>/dev/null; then
        echo "❌ uv 安裝失敗"
        echo "請手動安裝：https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
fi

echo "✓ uv 已安裝"
echo ""

# 2. 建立虛擬環境（uv 會自動下載 Python 3.10）
echo "📋 [2/4] 建立虛擬環境..."
if [ -d ".venv" ]; then
    echo "⚠️  虛擬環境已存在，是否重新建立？[y/N]"
    read -r -n 1 REPLY
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf .venv
        echo "⏳ 建立虛擬環境（uv 會自動下載 Python 3.10，首次需要 1-2 分鐘）..."
        uv venv --python 3.10
        echo "✓ 虛擬環境已重新建立"
    else
        echo "✓ 使用現有虛擬環境"
    fi
else
    echo "⏳ 建立虛擬環境（uv 會自動下載 Python 3.10，首次需要 1-2 分鐘）..."
    uv venv --python 3.10
    echo "✓ 虛擬環境已建立"
fi

# 啟動虛擬環境
source .venv/bin/activate
echo ""

# 3. 安裝依賴套件
echo "📋 [3/4] 安裝依賴套件..."
echo "⏳ 這可能需要 2-5 分鐘，請稍候..."
echo ""

# 顯示安裝進度
uv pip install -e ".[all]"

echo ""
echo "✓ 所有套件已安裝"
echo ""

# 4. 設定環境變數
echo "📋 [4/4] 設定環境變數..."
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
    echo "   💡 注意：HF_TOKEN 是可選的"
    echo "      - 有 token：可使用說話者分離功能"
    echo "      - 無 token：仍可使用語音轉錄功能"
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
echo "   1. （可選）編輯 .env 檔案，填入 HF_TOKEN"
echo "      - 有 HF_TOKEN：可使用說話者分離功能"
echo "      - 無 HF_TOKEN：仍可使用語音轉錄功能"
echo "   2. 執行 ./run_gui.sh 啟動 GUI"
echo ""
echo "💡 提示："
echo "   - 首次執行會下載 AI 模型（約 1.5 GB）"
echo "   - 需要穩定的網路連線"
echo "   - 下載完成後會自動快取，之後啟動很快"
echo ""

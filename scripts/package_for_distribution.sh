#!/bin/bash
# 打包專案供分發使用

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

VERSION=$(date +%Y%m%d)
PACKAGE_NAME="MultiSpeakerASR-${VERSION}"
OUTPUT_FILE="${PACKAGE_NAME}.tar.gz"

echo "=========================================="
echo "打包 ASR Multi-Speaker 專案"
echo "=========================================="
echo ""
echo "版本: ${VERSION}"
echo "輸出: ${OUTPUT_FILE}"
echo ""

# 檢查是否有未提交的變更
if [ -d ".git" ]; then
    if ! git diff-index --quiet HEAD --; then
        echo "⚠️  警告：有未提交的變更"
        read -p "是否繼續？[y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# 使用 git archive（如果有 .git）
if [ -d ".git" ]; then
    echo "⏳ 使用 git archive 打包..."
    git archive --format=tar.gz --prefix="${PACKAGE_NAME}/" -o "../${OUTPUT_FILE}" HEAD
    echo "✓ 打包完成：../${OUTPUT_FILE}"
else
    # 手動打包，排除不需要的檔案
    echo "⏳ 手動打包（排除不需要的檔案）..."
    cd ..
    tar -czf "${OUTPUT_FILE}" \
        --exclude='.git' \
        --exclude='.venv' \
        --exclude='.venv.old' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='*.pyo' \
        --exclude='.DS_Store' \
        --exclude='.env' \
        --exclude='*.log' \
        --exclude='*_transcription.srt' \
        --exclude='*_transcription.txt' \
        --exclude='test-meeting.mp4' \
        --exclude='tests/visual/screenshots' \
        --transform="s|^$(basename "$PROJECT_ROOT")|${PACKAGE_NAME}|" \
        "$(basename "$PROJECT_ROOT")"
    
    echo "✓ 打包完成：${OUTPUT_FILE}"
fi

# 顯示檔案大小
if [ -f "../${OUTPUT_FILE}" ]; then
    SIZE=$(du -h "../${OUTPUT_FILE}" | cut -f1)
    echo ""
    echo "📦 檔案大小：${SIZE}"
    echo ""
    echo "📝 使用說明："
    echo "   1. 傳送檔案給使用者"
    echo "   2. 使用者解壓：tar -xzf ${OUTPUT_FILE}"
    echo "   3. 執行安裝：cd ${PACKAGE_NAME} && ./install.sh"
    echo ""
fi

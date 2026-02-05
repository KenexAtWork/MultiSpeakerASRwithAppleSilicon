#!/bin/bash

# 清理腳本 - 準備 Git 提交

set -e

echo "=== 清理 asr 目錄準備 Git 提交 ==="
echo ""

cd "$(dirname "$0")"

echo "當前目錄: $(pwd)"
echo ""

# 列出將被刪除的檔案
echo "將刪除以下檔案："
echo ""

echo "測試影片和音訊："
ls -lh *.mp4 *.wav 2>/dev/null || echo "  (無)"

echo ""
echo "輸出和日誌："
ls -lh *_transcription*.txt *.log test_*.txt 2>/dev/null || echo "  (無)"

echo ""
echo "舊版腳本："
ls -lh run*.sh setup*.sh quick_test.py test_*.py asr_multi_speaker2.py asr_multi_speaker_v3.py 2>/dev/null || echo "  (無)"

echo ""
read -p "確定要刪除這些檔案？[y/N] " -n 1 -r
echo

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

echo ""
echo "開始清理..."

# 刪除測試檔案
rm -f *.mp4 *.wav 2>/dev/null && echo "✓ 已刪除影片和音訊檔案" || echo "  (無影片和音訊檔案)"
rm -f *_transcription*.txt 2>/dev/null && echo "✓ 已刪除輸出檔案" || echo "  (無輸出檔案)"
rm -f *.log 2>/dev/null && echo "✓ 已刪除日誌檔案" || echo "  (無日誌檔案)"
rm -f test_*.txt 2>/dev/null && echo "✓ 已刪除測試檔案" || echo "  (無測試檔案)"

# 刪除舊版腳本
rm -f run.sh run_asr.sh run_with_env.sh run_arm64.sh 2>/dev/null && echo "✓ 已刪除舊版執行腳本" || echo "  (無舊版執行腳本)"
rm -f setup.sh setup_native_env.sh 2>/dev/null && echo "✓ 已刪除舊版設定腳本" || echo "  (無舊版設定腳本)"
rm -f quick_test.py test_diarization_api.py 2>/dev/null && echo "✓ 已刪除測試腳本" || echo "  (無測試腳本)"
rm -f asr_multi_speaker2.py asr_multi_speaker_v3.py 2>/dev/null && echo "✓ 已刪除舊版 Python 腳本" || echo "  (無舊版 Python 腳本)"

echo ""
echo "=== 清理完成！==="
echo ""
echo "保留的檔案："
ls -lh *.py *.sh *.md *.toml LICENSE .gitignore .env.example 2>/dev/null

echo ""
echo "下一步："
echo "  1. 檢查 git status"
echo "  2. git add ."
echo "  3. git commit -m 'Initial commit'"
echo "  4. 參考 SETUP_GIT.md 推送到 GitHub"

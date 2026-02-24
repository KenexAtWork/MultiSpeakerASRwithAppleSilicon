#!/bin/bash
# CI/CD 測試腳本 - 適用於任何 CI 系統

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "ASR CI/CD 測試"
echo "=========================================="
echo ""

# 檢查環境
echo "檢查環境..."
python3 --version
ffmpeg -version | head -1

# 檢查 Python 環境
if [ ! -d ".venv" ]; then
    echo "建立虛擬環境..."
    python3 -m venv .venv
fi

PYTHON=".venv/bin/python"

# 安裝依賴（如果需要）
echo ""
echo "檢查依賴..."
if ! $PYTHON -c "import mlx_whisper" 2>/dev/null; then
    echo "安裝 Python 依賴..."
    .venv/bin/pip install -q --upgrade pip
    .venv/bin/pip install -q -r requirements.txt
    .venv/bin/pip install -q -r gui/requirements.txt
fi

echo ""
echo "=========================================="
echo "執行測試套件"
echo "=========================================="
echo ""

# 測試計數
TOTAL=0
PASSED=0
FAILED=0

# 執行測試函式
run_test() {
    local name=$1
    local cmd=$2
    
    TOTAL=$((TOTAL + 1))
    echo "[$TOTAL] 測試: $name"
    
    if eval "$cmd" > /tmp/test_$TOTAL.log 2>&1; then
        echo "    ✓ 通過"
        PASSED=$((PASSED + 1))
    else
        echo "    ✗ 失敗"
        cat /tmp/test_$TOTAL.log
        FAILED=$((FAILED + 1))
    fi
}

# 執行所有測試（快速模式）
run_test "合併邏輯" "$PYTHON tests/test_merge_srt.py"
run_test "SRT 解析" "$PYTHON tests/test_srt_parser.py"
run_test "錯誤處理" "$PYTHON tests/test_error_handling.py"
run_test "GUI 媒體" "$PYTHON tests/test_gui_media_url.py"
run_test "Pipeline (快速)" "$PYTHON tests/test_pipeline_e2e.py --fast"

# 清理
rm -f /tmp/test_*.log

echo ""
echo "=========================================="
echo "測試結果"
echo "=========================================="
echo "總計: $TOTAL"
echo "通過: $PASSED"
echo "失敗: $FAILED"
echo ""

if [ $FAILED -gt 0 ]; then
    echo "❌ 測試失敗"
    exit 1
else
    echo "✅ 所有測試通過"
    exit 0
fi

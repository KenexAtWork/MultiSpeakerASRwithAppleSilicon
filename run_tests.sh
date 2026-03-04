#!/bin/bash
# 執行所有測試的便利腳本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 檢查 Python 環境
if [ ! -d ".venv" ]; then
    echo -e "${RED}錯誤: .venv 不存在${NC}"
    echo "請先執行: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

PYTHON=".venv/bin/python"

# 解析參數
FAST_MODE=false
VERBOSE=false
SPECIFIC_TEST=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --fast)
            FAST_MODE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --test)
            SPECIFIC_TEST="$2"
            shift 2
            ;;
        --help|-h)
            echo "用法: $0 [選項]"
            echo ""
            echo "選項:"
            echo "  --fast          快速模式（跳過 diarization 測試）"
            echo "  --verbose, -v   顯示詳細輸出"
            echo "  --test <name>   只執行特定測試"
            echo "  --help, -h      顯示此說明"
            echo ""
            echo "可用的測試:"
            echo "  pipeline        Pipeline 端到端測試"
            echo "  merge           合併邏輯測試"
            echo "  gui_media       GUI 媒體播放器測試"
            echo "  srt_parser      SRT 解析測試"
            echo "  error           錯誤處理測試"
            echo "  s2t             Qwen3-ASR 簡繁轉換測試 (unit)"
            echo "  live_summary    Live Summary 測試 (unit)"
            echo "  speaker_map     Speaker Name Mapping 測試 (unit)"
            echo "  realtime_unit   所有 realtime 相關 unit tests"
            echo ""
            echo "範例:"
            echo "  $0                    # 執行所有測試"
            echo "  $0 --fast             # 快速模式"
            echo "  $0 --test pipeline    # 只執行 pipeline 測試"
            exit 0
            ;;
        *)
            echo -e "${RED}未知選項: $1${NC}"
            echo "使用 --help 查看說明"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}ASR 自動化測試套件${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 測試計數器
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# 執行單個測試的函式
run_test() {
    local test_name=$1
    local test_file=$2
    local test_args=$3
    
    echo -e "${YELLOW}執行: $test_name${NC}"
    echo "----------------------------------------"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    # Check if this is a pytest-based test
    if [[ "$test_file" == PYTEST:* ]]; then
        local pytest_args="${test_file#PYTEST:}"
        local cmd="$PYTHON -m pytest tests/$pytest_args -v"
        if $VERBOSE; then
            if eval $cmd; then
                echo -e "${GREEN}✓ $test_name 通過${NC}"
                PASSED_TESTS=$((PASSED_TESTS + 1))
            else
                echo -e "${RED}✗ $test_name 失敗${NC}"
                FAILED_TESTS=$((FAILED_TESTS + 1))
            fi
        else
            if output=$(eval $cmd 2>&1); then
                echo -e "${GREEN}✓ $test_name 通過${NC}"
                PASSED_TESTS=$((PASSED_TESTS + 1))
            else
                echo -e "${RED}✗ $test_name 失敗${NC}"
                echo "$output"
                FAILED_TESTS=$((FAILED_TESTS + 1))
            fi
        fi
    else
        if $VERBOSE; then
            if $PYTHON "tests/$test_file" $test_args; then
                echo -e "${GREEN}✓ $test_name 通過${NC}"
                PASSED_TESTS=$((PASSED_TESTS + 1))
            else
                echo -e "${RED}✗ $test_name 失敗${NC}"
                FAILED_TESTS=$((FAILED_TESTS + 1))
            fi
        else
            if output=$($PYTHON "tests/$test_file" $test_args 2>&1); then
                echo -e "${GREEN}✓ $test_name 通過${NC}"
                PASSED_TESTS=$((PASSED_TESTS + 1))
            else
                echo -e "${RED}✗ $test_name 失敗${NC}"
                echo "$output"
                FAILED_TESTS=$((FAILED_TESTS + 1))
            fi
        fi
    fi
    
    echo ""
}

# 定義測試列表（使用簡單變數而非關聯陣列）
TEST_NAMES="pipeline merge gui_media srt_parser error"
TEST_pipeline="test_pipeline_e2e.py"
TEST_merge="test_merge_srt.py"
TEST_gui_media="test_gui_media_url.py"
TEST_srt_parser="test_srt_parser.py"
TEST_error="test_error_handling.py"

get_test_file() {
    local name=$1
    case $name in
        pipeline) echo "$TEST_pipeline" ;;
        merge) echo "$TEST_merge" ;;
        gui_media) echo "$TEST_gui_media" ;;
        srt_parser) echo "$TEST_srt_parser" ;;
        error) echo "$TEST_error" ;;
        s2t) echo "PYTEST:test_qwen3_s2t.py -k unit" ;;
        live_summary) echo "PYTEST:test_live_summary.py" ;;
        speaker_map) echo "PYTEST:test_speaker_mapping.py" ;;
        realtime_unit) echo "PYTEST:test_qwen3_s2t.py -k unit test_live_summary.py test_speaker_mapping.py" ;;
        *) echo "" ;;
    esac
}

# 執行測試
if [ -n "$SPECIFIC_TEST" ]; then
    # 執行特定測試
    test_file=$(get_test_file "$SPECIFIC_TEST")
    if [ -z "$test_file" ]; then
        echo -e "${RED}錯誤: 未知的測試名稱 '$SPECIFIC_TEST'${NC}"
        echo "使用 --help 查看可用的測試"
        exit 1
    fi
    
    test_args=""
    if [ "$SPECIFIC_TEST" = "pipeline" ] && $FAST_MODE; then
        test_args="--fast"
    fi
    
    run_test "$SPECIFIC_TEST" "$test_file" "$test_args"
else
    # 執行所有測試
    
    # 1. Pipeline 測試
    if $FAST_MODE; then
        run_test "Pipeline (快速模式)" "$TEST_pipeline" "--fast"
    else
        run_test "Pipeline (完整模式)" "$TEST_pipeline" ""
    fi
    
    # 2. 合併邏輯測試
    run_test "合併邏輯" "$TEST_merge" ""
    
    # 3. GUI 媒體測試
    run_test "GUI 媒體播放器" "$TEST_gui_media" ""
    
    # 4. SRT 解析測試
    run_test "SRT 解析" "$TEST_srt_parser" ""
    
    # 5. 錯誤處理測試
    run_test "錯誤處理" "$TEST_error" ""
    
    # 6. Realtime unit tests (pytest-based)
    run_test "Qwen3-ASR 簡繁轉換 (unit)" "PYTEST:test_qwen3_s2t.py -k unit" ""
    run_test "Live Summary (unit)" "PYTEST:test_live_summary.py" ""
    run_test "Speaker Mapping (unit)" "PYTEST:test_speaker_mapping.py" ""
fi

# 顯示總結
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}測試總結${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "總測試數: $TOTAL_TESTS"
echo -e "${GREEN}通過: $PASSED_TESTS${NC}"
if [ $FAILED_TESTS -gt 0 ]; then
    echo -e "${RED}失敗: $FAILED_TESTS${NC}"
fi
if [ $SKIPPED_TESTS -gt 0 ]; then
    echo -e "${YELLOW}跳過: $SKIPPED_TESTS${NC}"
fi
echo ""

# 退出碼
if [ $FAILED_TESTS -gt 0 ]; then
    echo -e "${RED}有測試失敗${NC}"
    exit 1
else
    echo -e "${GREEN}✓ 所有測試通過${NC}"
    exit 0
fi

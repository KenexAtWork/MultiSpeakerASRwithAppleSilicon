#!/bin/bash

# ASR 多說話者轉錄腳本
# 使用方式：
#   asr.sh input.mp4
#   asr.sh input.mp4 output.txt
#   asr.sh input.mp4 output.txt --language en

set -e

# 取得腳本的實際路徑（處理符號連結，macOS 相容）
SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_PATH" ]; do
    SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"
    SCRIPT_PATH="$(readlink "$SCRIPT_PATH")"
    [[ $SCRIPT_PATH != /* ]] && SCRIPT_PATH="$SCRIPT_DIR/$SCRIPT_PATH"
done

# 取得腳本所在目錄（asr 目錄）
SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
PYTHON_SCRIPT="$SCRIPT_DIR/asr_multi_speaker_v5_fast.py"

# 載入 .env 檔案（如果存在）
if [ -f "$SCRIPT_DIR/.env" ]; then
    # 讀取 .env 並 export 變數
    set -a  # 自動 export 所有變數
    source "$SCRIPT_DIR/.env"
    set +a  # 關閉自動 export
    echo "✓ 已載入 .env 檔案"
fi

# 檢查虛擬環境是否存在
if [ ! -d "$VENV_DIR" ]; then
    echo "錯誤：找不到虛擬環境 $VENV_DIR"
    echo "請先執行以下指令建立環境："
    echo "  cd $SCRIPT_DIR"
    echo "  uv venv --python /opt/homebrew/bin/python3"
    echo "  source .venv/bin/activate"
    echo "  uv pip install mlx-whisper pyannote-audio"
    exit 1
fi

# 檢查 Python 腳本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "錯誤：找不到 Python 腳本 $PYTHON_SCRIPT"
    exit 1
fi

# 檢查參數
if [ $# -lt 1 ]; then
    echo "使用方式："
    echo "  $(basename $0) <input_video> [output_file] [其他參數...]"
    echo ""
    echo "範例："
    echo "  $(basename $0) video.mp4"
    echo "  $(basename $0) video.mp4 output.txt"
    echo "  $(basename $0) video.mp4 output.txt --language en"
    echo "  $(basename $0) video.mp4 output.txt --model small"
    echo "  $(basename $0) video.mp4 output.txt --skip-diarization"
    echo "  $(basename $0) video.mp4 output.txt --no-gpu"
    echo ""
    echo "參數說明："
    echo "  --language LANG    語言代碼（預設: zh，留空自動偵測）"
    echo "  --model SIZE       模型大小：tiny, base, small, medium, large（預設: medium）"
    echo "  --format FORMAT    輸出格式：srt 或 txt（預設: srt）"
    echo "  --skip-diarization 跳過說話者分離"
    echo "  --no-gpu           停用 GPU 加速"
    echo "  --hf-token TOKEN   Hugging Face token（說話者分離需要）"
    echo ""
    echo "模型記憶體使用參考："
    echo "  tiny   - ~1 GB   (最快，準確度較低)"
    echo "  base   - ~1.5 GB (快速，準確度中等)"
    echo "  small  - ~2.5 GB (平衡選擇，推薦記憶體不足時使用)"
    echo "  medium - ~5 GB   (預設，準確度高)"
    echo "  large  - ~10 GB  (最準確，最慢)"
    echo ""
    echo "注意：輸入檔案路徑相對於當前目錄"
    exit 1
fi

# 啟動虛擬環境
source "$VENV_DIR/bin/activate"

# 準備參數
INPUT_FILE="$1"
shift

# 將相對路徑轉換為絕對路徑
if [[ "$INPUT_FILE" != /* ]]; then
    INPUT_FILE="$(pwd)/$INPUT_FILE"
fi

# 檢查輸入檔案是否存在
if [ ! -f "$INPUT_FILE" ]; then
    echo "錯誤：找不到輸入檔案 $INPUT_FILE"
    exit 1
fi

# 建立參數陣列
ARGS=("--input" "$INPUT_FILE")

# 如果第一個參數不是以 -- 開頭，視為輸出檔案
if [[ $# -gt 0 ]] && [[ ! "$1" =~ ^-- ]]; then
    OUTPUT_FILE="$1"
    # 將相對路徑轉換為絕對路徑
    if [[ "$OUTPUT_FILE" != /* ]]; then
        OUTPUT_FILE="$(pwd)/$OUTPUT_FILE"
    fi
    ARGS+=("--output" "$OUTPUT_FILE")
    shift
fi

# 加入其他參數
ARGS+=("$@")

# 如果沒有指定 hf-token，使用預設值
HAS_TOKEN=false
for arg in "${ARGS[@]}"; do
    if [[ "$arg" == "--hf-token" ]]; then
        HAS_TOKEN=true
        break
    fi
done

if [[ "$HAS_TOKEN" == false ]]; then
    # 檢查環境變數
    if [[ -n "$HF_TOKEN" ]]; then
        ARGS+=("--hf-token" "$HF_TOKEN")
    else
        echo "警告：未提供 Hugging Face token"
        echo "說話者分離功能需要 HF token"
        echo "請設定環境變數：export HF_TOKEN=your_token"
        echo "或使用參數：--hf-token YOUR_TOKEN"
        echo ""
        read -p "是否繼續（只執行 ASR 轉錄）？[y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
        ARGS+=("--skip-diarization")
    fi
fi

# 執行 Python 腳本
echo "執行 ASR 轉錄..."
echo "當前目錄: $(pwd)"
echo "輸入檔案: $INPUT_FILE"
echo ""

python "$PYTHON_SCRIPT" "${ARGS[@]}"

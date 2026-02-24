#!/bin/bash

# ASR 分段處理腳本 - 降低記憶體使用
# 使用方式：asr_chunked.sh input.mp4 [chunk_minutes] [其他 asr.sh 參數...]

set -e

# 取得腳本目錄
SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_PATH" ]; do
    SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"
    SCRIPT_PATH="$(readlink "$SCRIPT_PATH")"
    [[ $SCRIPT_PATH != /* ]] && SCRIPT_PATH="$SCRIPT_DIR/$SCRIPT_PATH"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"

# 檢查參數
if [ $# -lt 1 ]; then
    echo "使用方式："
    echo "  $(basename $0) <input_video> [chunk_minutes] [其他參數...]"
    echo ""
    echo "範例："
    echo "  $(basename $0) long-video.mp4              # 預設 10 分鐘分段"
    echo "  $(basename $0) long-video.mp4 15           # 15 分鐘分段"
    echo "  $(basename $0) long-video.mp4 10 --model small"
    echo ""
    echo "說明："
    echo "  - 將長影片切成多段處理，降低記憶體使用"
    echo "  - 自動合併字幕並調整時間戳記"
    echo "  - 說話者編號會自動重新對應"
    exit 1
fi

INPUT_FILE="$1"
CHUNK_MINUTES="${2:-10}"  # 預設 10 分鐘
shift
shift || true  # 移除前兩個參數，剩下的傳給 asr.sh

# 轉換為絕對路徑
if [[ "$INPUT_FILE" != /* ]]; then
    INPUT_FILE="$(pwd)/$INPUT_FILE"
fi

if [ ! -f "$INPUT_FILE" ]; then
    echo "錯誤：找不到輸入檔案 $INPUT_FILE"
    exit 1
fi

# 取得影片資訊
echo "分析影片..."
DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$INPUT_FILE")
DURATION_INT=$(printf "%.0f" "$DURATION")
CHUNK_SECONDS=$((CHUNK_MINUTES * 60))

echo "影片總長度: $DURATION_INT 秒 ($(($DURATION_INT / 60)) 分鐘)"
echo "分段長度: $CHUNK_MINUTES 分鐘"

# 計算需要多少段
NUM_CHUNKS=$(( ($DURATION_INT + $CHUNK_SECONDS - 1) / $CHUNK_SECONDS ))
echo "將分成 $NUM_CHUNKS 段處理"
echo ""

# 建立臨時目錄
BASE_NAME=$(basename "$INPUT_FILE" | sed 's/\.[^.]*$//')
TEMP_DIR=$(mktemp -d -t asr_chunks_XXXXXX)
echo "臨時目錄: $TEMP_DIR"

# 清理函數
cleanup() {
    echo ""
    echo "清理臨時檔案..."
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# 切割影片並處理
for i in $(seq 0 $((NUM_CHUNKS - 1))); do
    START_TIME=$((i * CHUNK_SECONDS))
    CHUNK_FILE="$TEMP_DIR/chunk_${i}.mp4"
    
    echo "=========================================="
    echo "處理第 $((i + 1))/$NUM_CHUNKS 段 (從 $START_TIME 秒開始)"
    echo "=========================================="
    
    # 切割影片
    echo "切割影片片段..."
    ffmpeg -v error -ss $START_TIME -i "$INPUT_FILE" -t $CHUNK_SECONDS -c copy "$CHUNK_FILE"
    
    # 執行 ASR
    echo "執行 ASR 轉錄..."
    "$SCRIPT_DIR/asr.sh" "$CHUNK_FILE" "$@"
    
    echo "✓ 第 $((i + 1)) 段完成"
    echo ""
done

# 合併字幕
echo "=========================================="
echo "合併字幕檔案..."
echo "=========================================="

OUTPUT_FILE="$(dirname "$INPUT_FILE")/${BASE_NAME}_transcription.srt"
python3 - "$TEMP_DIR" "$OUTPUT_FILE" "$CHUNK_SECONDS" <<'PYTHON_SCRIPT'
import sys
import os
import re
from pathlib import Path

temp_dir = sys.argv[1]
output_file = sys.argv[2]
chunk_seconds = int(sys.argv[3])

def parse_srt_time(time_str):
    """將 SRT 時間格式轉換為秒數"""
    h, m, s = time_str.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)

def format_srt_time(seconds):
    """將秒數轉換為 SRT 時間格式"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')

# 收集所有字幕檔案
srt_files = sorted(Path(temp_dir).glob("chunk_*_transcription.srt"))
print(f"找到 {len(srt_files)} 個字幕檔案")

# 建立說話者對應表（跨片段統一說話者編號）
speaker_map = {}
next_speaker_id = 0

merged_segments = []
segment_index = 1

for chunk_idx, srt_file in enumerate(srt_files):
    print(f"處理: {srt_file.name}")
    time_offset = chunk_idx * chunk_seconds
    
    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析 SRT 格式
    blocks = content.strip().split('\n\n')
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        
        # 解析時間戳記
        time_line = lines[1]
        match = re.match(r'(\S+) --> (\S+)', time_line)
        if not match:
            continue
        
        start_time = parse_srt_time(match.group(1)) + time_offset
        end_time = parse_srt_time(match.group(2)) + time_offset
        
        # 解析文字和說話者
        text_line = lines[2]
        speaker_match = re.match(r'\[([^\]]+)\]\s*(.*)', text_line)
        
        if speaker_match:
            original_speaker = speaker_match.group(1)
            text = speaker_match.group(2)
            
            # 統一說話者編號
            speaker_key = f"chunk{chunk_idx}_{original_speaker}"
            if speaker_key not in speaker_map:
                speaker_map[speaker_key] = f"SPEAKER_{next_speaker_id:02d}"
                next_speaker_id += 1
            
            unified_speaker = speaker_map[speaker_key]
        else:
            unified_speaker = "Unknown"
            text = text_line
        
        merged_segments.append({
            'index': segment_index,
            'start': start_time,
            'end': end_time,
            'speaker': unified_speaker,
            'text': text
        })
        segment_index += 1

# 寫入合併後的字幕
print(f"\n寫入合併字幕: {output_file}")
with open(output_file, 'w', encoding='utf-8') as f:
    for seg in merged_segments:
        f.write(f"{seg['index']}\n")
        f.write(f"{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}\n")
        f.write(f"[{seg['speaker']}] {seg['text']}\n\n")

print(f"✓ 合併完成！")
print(f"✓ 共 {len(merged_segments)} 個字幕段落")
print(f"✓ 偵測到 {len(set(seg['speaker'] for seg in merged_segments))} 位說話者")
PYTHON_SCRIPT

echo ""
echo "=========================================="
echo "✓ 全部完成！"
echo "✓ 輸出檔案: $OUTPUT_FILE"
echo "=========================================="

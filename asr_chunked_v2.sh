#!/bin/bash

# ASR 分段處理腳本 V2 - 完整說話者分離 + 分段 ASR
# 使用方式：asr_chunked_v2.sh input.mp4 [chunk_minutes] [其他參數...]

set -e

SCRIPT_PATH="${BASH_SOURCE[0]}"
while [ -L "$SCRIPT_PATH" ]; do
    SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"
    SCRIPT_PATH="$(readlink "$SCRIPT_PATH")"
    [[ $SCRIPT_PATH != /* ]] && SCRIPT_PATH="$SCRIPT_DIR/$SCRIPT_PATH"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SCRIPT_PATH")" && pwd)"

if [ $# -lt 1 ]; then
    echo "使用方式："
    echo "  $(basename $0) <input_video> [chunk_minutes] [其他參數...]"
    echo ""
    echo "範例："
    echo "  $(basename $0) long-video.mp4              # 預設 10 分鐘分段"
    echo "  $(basename $0) long-video.mp4 15 --model small"
    echo ""
    echo "說明："
    echo "  - 先對完整影片做說話者分離（一次性，記憶體高峰）"
    echo "  - 然後分段做 ASR 轉錄（降低記憶體）"
    echo "  - 最後合併結果，說話者編號保持一致"
    exit 1
fi

INPUT_FILE="$1"
CHUNK_MINUTES="${2:-10}"
shift
shift || true

if [[ "$INPUT_FILE" != /* ]]; then
    INPUT_FILE="$(pwd)/$INPUT_FILE"
fi

if [ ! -f "$INPUT_FILE" ]; then
    echo "錯誤：找不到輸入檔案 $INPUT_FILE"
    exit 1
fi

BASE_NAME=$(basename "$INPUT_FILE" | sed 's/\.[^.]*$//')
TEMP_DIR=$(mktemp -d -t asr_chunks_v2_XXXXXX)
echo "臨時目錄: $TEMP_DIR"

cleanup() {
    echo ""
    echo "清理臨時檔案..."
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Step 1: 完整說話者分離
echo "=========================================="
echo "Step 1: 對完整影片執行說話者分離"
echo "=========================================="

DIARIZATION_FILE="$TEMP_DIR/diarization.json"

# 檢查是否有 HF_TOKEN
if [[ -z "$HF_TOKEN" ]]; then
    echo "警告：未設定 HF_TOKEN，將跳過說話者分離"
    SKIP_DIARIZATION="--skip-diarization"
else
    # 只做說話者分離，使用 Python 腳本
    python3 - "$INPUT_FILE" "$DIARIZATION_FILE" "$HF_TOKEN" <<'PYTHON_SCRIPT'
import sys
import os
import json
import tempfile
import subprocess

video_file = sys.argv[1]
output_file = sys.argv[2]
hf_token = sys.argv[3]

print("提取音訊...")
temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
temp_wav_path = temp_wav.name
temp_wav.close()

cmd = [
    'ffmpeg', '-v', 'error',
    '-i', video_file,
    '-ar', '16000',
    '-ac', '1',
    '-acodec', 'pcm_s16le',
    '-y', temp_wav_path
]
subprocess.run(cmd, check=True)

print("執行說話者分離...")
import torch
torch.set_num_threads(8)

from pyannote.audio import Pipeline
pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=hf_token
)

if torch.backends.mps.is_available():
    pipeline.to(torch.device("mps"))
    print("✓ 使用 MPS GPU 加速")

from pyannote.audio.pipelines.utils.hook import ProgressHook
with ProgressHook() as hook:
    diarization = pipeline(temp_wav_path, hook=hook)

# 提取說話者時間軸
timeline = []
for segment, _, speaker in diarization.itertracks(yield_label=True):
    timeline.append({
        'start': float(segment.start),
        'end': float(segment.end),
        'speaker': speaker
    })

# 儲存為 JSON
with open(output_file, 'w') as f:
    json.dump(timeline, f)

num_speakers = len(set(sp['speaker'] for sp in timeline))
print(f"✓ 偵測到 {num_speakers} 位說話者")
print(f"✓ 共 {len(timeline)} 個說話者片段")

os.unlink(temp_wav_path)
PYTHON_SCRIPT

    if [ $? -ne 0 ]; then
        echo "說話者分離失敗，將跳過"
        SKIP_DIARIZATION="--skip-diarization"
    else
        echo "✓ 說話者分離完成"
    fi
fi

# Step 2: 分段 ASR
echo ""
echo "=========================================="
echo "Step 2: 分段執行 ASR 轉錄"
echo "=========================================="

DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$INPUT_FILE")
DURATION_INT=$(printf "%.0f" "$DURATION")
CHUNK_SECONDS=$((CHUNK_MINUTES * 60))
NUM_CHUNKS=$(( ($DURATION_INT + $CHUNK_SECONDS - 1) / $CHUNK_SECONDS ))

echo "影片總長度: $DURATION_INT 秒"
echo "將分成 $NUM_CHUNKS 段處理"
echo ""

for i in $(seq 0 $((NUM_CHUNKS - 1))); do
    START_TIME=$((i * CHUNK_SECONDS))
    CHUNK_FILE="$TEMP_DIR/chunk_${i}.mp4"
    
    echo "處理第 $((i + 1))/$NUM_CHUNKS 段..."
    
    ffmpeg -v error -ss $START_TIME -i "$INPUT_FILE" -t $CHUNK_SECONDS -c copy "$CHUNK_FILE"
    
    # 只做 ASR，跳過說話者分離
    "$SCRIPT_DIR/asr.sh" "$CHUNK_FILE" --skip-diarization "$@"
    
    echo "✓ 第 $((i + 1)) 段完成"
done

# Step 3: 合併結果
echo ""
echo "=========================================="
echo "Step 3: 合併 ASR 結果與說話者資訊"
echo "=========================================="

OUTPUT_FILE="$(dirname "$INPUT_FILE")/${BASE_NAME}_transcription.srt"

python3 - "$TEMP_DIR" "$OUTPUT_FILE" "$CHUNK_SECONDS" "$DIARIZATION_FILE" <<'PYTHON_SCRIPT'
import sys
import os
import re
import json
from pathlib import Path

temp_dir = sys.argv[1]
output_file = sys.argv[2]
chunk_seconds = int(sys.argv[3])
diarization_file = sys.argv[4]

def parse_srt_time(time_str):
    h, m, s = time_str.replace(',', '.').split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)

def format_srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')

# 載入說話者時間軸
speaker_timeline = []
if os.path.exists(diarization_file):
    with open(diarization_file, 'r') as f:
        speaker_timeline = json.load(f)
    print(f"✓ 載入說話者資訊: {len(speaker_timeline)} 個片段")

# 收集所有字幕檔案
srt_files = sorted(Path(temp_dir).glob("chunk_*_transcription.srt"))
print(f"✓ 找到 {len(srt_files)} 個字幕檔案")

merged_segments = []
segment_index = 1

for chunk_idx, srt_file in enumerate(srt_files):
    time_offset = chunk_idx * chunk_seconds
    
    with open(srt_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = content.strip().split('\n\n')
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        
        time_line = lines[1]
        match = re.match(r'(\S+) --> (\S+)', time_line)
        if not match:
            continue
        
        start_time = parse_srt_time(match.group(1)) + time_offset
        end_time = parse_srt_time(match.group(2)) + time_offset
        
        # 移除原本的說話者標記（因為是分段產生的，不準確）
        text_line = lines[2]
        text = re.sub(r'^\[.*?\]\s*', '', text_line)
        
        # 從完整的說話者時間軸找出對應的說話者
        speaker = "Unknown"
        segment_mid = (start_time + end_time) / 2
        
        for sp in speaker_timeline:
            if sp['start'] <= segment_mid <= sp['end']:
                speaker = sp['speaker']
                break
        
        merged_segments.append({
            'index': segment_index,
            'start': start_time,
            'end': end_time,
            'speaker': speaker,
            'text': text
        })
        segment_index += 1

# 寫入合併後的字幕
with open(output_file, 'w', encoding='utf-8') as f:
    for seg in merged_segments:
        f.write(f"{seg['index']}\n")
        f.write(f"{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}\n")
        f.write(f"[{seg['speaker']}] {seg['text']}\n\n")

print(f"✓ 合併完成！")
print(f"✓ 共 {len(merged_segments)} 個字幕段落")
if speaker_timeline:
    print(f"✓ 偵測到 {len(set(seg['speaker'] for seg in merged_segments))} 位說話者")
PYTHON_SCRIPT

echo ""
echo "=========================================="
echo "✓ 全部完成！"
echo "✓ 輸出檔案: $OUTPUT_FILE"
echo "=========================================="

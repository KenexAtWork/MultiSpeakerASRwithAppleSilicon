#!/bin/bash
#
# ASR Benchmark: CPU vs GPU 效能比較
# 每個檔案各跑 10 次，記錄 ASR / Diarization / 總時間
# 輸出 CSV
#

set -e

SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d ".venv" ]; then source .venv/bin/activate; fi
if [ -f ".env" ]; then set -a; source .env; set +a; fi

PYTHON_SCRIPT="$SCRIPT_DIR/asr_multi_speaker_v5_fast.py"
RUNS=10
SLEEP_BETWEEN=5

FILES=(
    "/Users/yushengh/Utils/asr/examples/sample-01.mp4"
    "/Users/yushengh/Documents/SA/Customers/Nokia/ECV-Nokia合作案/EVCNokia報價討論-20260211.m4a"
    "$HOME/Documents/SA/Customers/00-Industry-Territory/GME/irenechen-territory-overview-20260203/irenechen-territory-overview-20260203.mp4"
)

FILE_LABELS=(
    "Sample-01"
    "Nokia-meeting"
    "Territory-overview"
)

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$SCRIPT_DIR/benchmark_results"
REPORT="$SCRIPT_DIR/benchmark_results/benchmark_${TIMESTAMP}.csv"
TMP_OUTPUT="/tmp/asr_benchmark_${TIMESTAMP}.srt"

echo "file,mode,run,asr_sec,diarization_sec,total_sec,asr_realtime_x,diarization_realtime_x,overall_realtime_x" > "$REPORT"

parse_output() {
    local output="$1"
    ASR_SEC=$(echo "$output" | grep -o 'ASR 轉錄: [0-9]*' | grep -o '[0-9]*$' || echo "0")
    DIAR_SEC=$(echo "$output" | grep -o '說話者分離: [0-9]*' | grep -o '[0-9]*$' || echo "0")
    ASR_SPEED=$(echo "$output" | grep 'ASR 轉錄' | grep -o '[0-9]*\.[0-9]*x 即時速度' | grep -o '^[0-9]*\.[0-9]*' || echo "0")
    DIAR_SPEED=$(echo "$output" | grep '說話者分離' | grep -o '[0-9]*\.[0-9]*x 即時速度' | grep -o '^[0-9]*\.[0-9]*' || echo "0")
    OVERALL_SPEED=$(echo "$output" | grep '整體速度' | grep -o '= [0-9]*\.[0-9]*x' | grep -o '[0-9]*\.[0-9]*' || echo "0")
    TOTAL_MIN=$(echo "$output" | grep '總處理時間' | grep -o '[0-9]* 分' | grep -o '[0-9]*' || echo "0")
    TOTAL_S=$(echo "$output" | grep '總處理時間' | grep -o '[0-9]* 秒' | grep -o '[0-9]*' || echo "0")
    TOTAL_SEC=$((TOTAL_MIN * 60 + TOTAL_S))
}

echo "============================================================"
echo "ASR Benchmark: CPU vs GPU"
echo "日期: $(date)"
echo "每個檔案各 ${RUNS} 次，模型: medium"
echo "每次間隔 ${SLEEP_BETWEEN} 秒（記憶體釋放）"
echo "輸出: $REPORT"
echo "============================================================"
echo ""

for mode in "gpu" "cpu"; do
    gpu_flag=""
    [ "$mode" = "cpu" ] && gpu_flag="--no-gpu"

    echo ">>> 模式: $mode"
    echo ""

    for i in "${!FILES[@]}"; do
        file="${FILES[$i]}"
        label="${FILE_LABELS[$i]}"
        echo "  檔案: $label"

        for run in $(seq 1 $RUNS); do
            echo -n "    Run $run/$RUNS ... "

            output=$(python "$PYTHON_SCRIPT" \
                --input "$file" \
                --output "$TMP_OUTPUT" \
                --language zh \
                --model medium \
                --format srt \
                --hf-token "$HF_TOKEN" \
                $gpu_flag 2>&1)

            parse_output "$output"
            echo "ASR: ${ASR_SEC}s (${ASR_SPEED}x) | Diar: ${DIAR_SEC}s (${DIAR_SPEED}x) | Total: ${TOTAL_SEC}s (${OVERALL_SPEED}x)"
            echo "$label,$mode,$run,$ASR_SEC,$DIAR_SEC,$TOTAL_SEC,$ASR_SPEED,$DIAR_SPEED,$OVERALL_SPEED" >> "$REPORT"
            rm -f "$TMP_OUTPUT"

            # 等待記憶體釋放
            sleep $SLEEP_BETWEEN
        done
        echo ""
    done
done

# 計算平均並附加到 CSV
python3 -c "
import csv
from collections import defaultdict

rows = []
with open('$REPORT') as f:
    for r in csv.DictReader(f):
        rows.append(r)

groups = defaultdict(list)
for r in rows:
    groups[(r['file'], r['mode'])].append(r)

with open('$REPORT', 'a') as f:
    f.write('\n')
    f.write('file,mode,run,asr_sec,diarization_sec,total_sec,asr_realtime_x,diarization_realtime_x,overall_realtime_x\n')
    for (file, mode), items in sorted(groups.items()):
        n = len(items)
        f.write('{},{},AVG,{:.1f},{:.1f},{:.1f},{:.2f},{:.2f},{:.2f}\n'.format(
            file, mode,
            sum(float(r['asr_sec']) for r in items) / n,
            sum(float(r['diarization_sec']) for r in items) / n,
            sum(float(r['total_sec']) for r in items) / n,
            sum(float(r['asr_realtime_x']) for r in items) / n,
            sum(float(r['diarization_realtime_x']) for r in items) / n,
            sum(float(r['overall_realtime_x']) for r in items) / n,
        ))

print('✓ 平均值已附加到 CSV')
"

echo "============================================================"
echo "✓ Benchmark 完成"
echo "✓ CSV: $REPORT"
echo "============================================================"

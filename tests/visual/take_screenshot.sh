#!/bin/bash
# 遞增截圖編號並截圖
DIR="$(dirname "$0")/screenshots"
COUNTER_FILE="$DIR/counter.txt"
N=$(cat "$COUNTER_FILE")
N=$((N + 1))
echo "$N" > "$COUNTER_FILE"
FILE="$DIR/screenshot_${N}.png"
screencapture -x "$FILE"
echo "$FILE"

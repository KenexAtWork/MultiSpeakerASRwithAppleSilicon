#!/bin/bash
SSDIR="$(dirname "$0")/screenshots"

take_ss() {
    local N=$(cat "$SSDIR/counter.txt")
    N=$((N + 1))
    echo "$N" > "$SSDIR/counter.txt"
    local FILE="$SSDIR/screenshot_${N}.png"
    screencapture -x "$FILE"
    echo "$FILE"
}

focus_gui() {
    osascript -e 'tell application "System Events" to set frontmost of (first process whose name is "Python") to true' 2>/dev/null
    sleep 0.3
}

describe() {
    local IMG="$1"
    local PROMPT="$2"
    python3 asr/tests/visual/describe_screenshot.py --image "$IMG" --prompt "$PROMPT"
}

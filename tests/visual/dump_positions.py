#!/usr/bin/env python3
"""連接到運行中的 GUI 進程，dump widget 座標（透過 AppleScript 模擬）
實際上我們用偏移量計算：讀取 widget_positions.json + 視窗位移"""
import json, sys
from pathlib import Path

positions_file = Path(__file__).parent / "widget_positions.json"
data = json.loads(positions_file.read_text())

# 原始視窗位置（launch_and_locate dump 時的位置）和新位置
old_win_x, old_win_y = float(sys.argv[1]), float(sys.argv[2])
new_win_x, new_win_y = float(sys.argv[3]), float(sys.argv[4])

dx = new_win_x - old_win_x
dy = new_win_y - old_win_y

for w in data:
    w["x"] = int(w["x"] + dx)
    w["y"] = int(w["y"] + dy)

positions_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
for w in data:
    if w["visible"]:
        print(f"{w['type']:>10} | ({w['x']:>4},{w['y']:>4}) | {w['text']}")

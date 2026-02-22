#!/usr/bin/env python3
"""
合併同 speaker 相鄰短段落
- 可被 pipeline import 使用
- 也可獨立 CLI 對任何 SRT 檔案做合併

用法: python merge_srt.py <input.srt> [--gap 1.5] [--max-duration 8] [--max-chars 40]
"""
import re, sys, argparse


def merge_segments(segments, max_gap=1.5, max_duration=8.0, max_chars=40):
    """
    合併同 speaker 相鄰段落

    Args:
        segments: list of dict, 每個 dict 需有 start, end, speaker, text
        max_gap: 兩段之間最大間隔（秒），超過就不合併
        max_duration: 合併後最大長度（秒）
        max_chars: 合併後最大字數
    Returns:
        合併後的 segments list（重新編號）
    """
    if not segments:
        return []

    merged = [dict(segments[0])]

    for seg in segments[1:]:
        prev = merged[-1]
        gap = seg["start"] - prev["end"]
        combined_duration = seg["end"] - prev["start"]
        combined_chars = len(prev["text"]) + len(seg["text"])

        if (seg["speaker"] == prev["speaker"]
                and seg["speaker"] != "Unknown"
                and gap <= max_gap
                and combined_duration <= max_duration
                and combined_chars <= max_chars):
            prev_last = prev["text"][-1] if prev["text"] else ""
            seg_first = seg["text"][0] if seg["text"] else ""
            if prev_last.isascii() or seg_first.isascii():
                sep = " "
            else:
                sep = "，" if prev_last not in "，。！？!?.；;…、：:" else ""
            prev["end"] = seg["end"]
            prev["text"] = prev["text"] + sep + seg["text"]
        else:
            merged.append(dict(seg))

    for i, seg in enumerate(merged, 1):
        seg["index"] = i

    return merged

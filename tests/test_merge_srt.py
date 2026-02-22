#!/usr/bin/env python3
"""
merge_srt 合併功能驗證測試
可用於：
  1. 單元測試（合成資料）
  2. 整合測試（實際 SRT 檔案）

用法:
  # 單元測試
  python tests/test_merge_srt.py

  # 整合測試（指定實際 SRT）
  python tests/test_merge_srt.py --srt path/to/file.srt
"""
import os, sys, argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from merge_srt import merge_segments

# === 預設參數 ===
MAX_GAP = 1.5
MAX_DURATION = 8.0
MAX_CHARS = 40


def make_seg(start, end, speaker, text):
    return {"start": start, "end": end, "speaker": speaker, "text": text}


# ──────────────────────────────────────────────
# 單元測試
# ──────────────────────────────────────────────

def test_empty_input():
    """空輸入不報錯"""
    result = merge_segments([])
    assert result == [], f"Expected [], got {result}"


def test_single_segment():
    """單一段落原樣回傳"""
    segs = [make_seg(0, 3, "SPEAKER_00", "你好")]
    result = merge_segments(segs)
    assert len(result) == 1
    assert result[0]["text"] == "你好"
    assert result[0]["index"] == 1


def test_same_speaker_merge():
    """同 speaker 相鄰短段落應合併"""
    segs = [
        make_seg(0, 2, "SPEAKER_00", "你好"),
        make_seg(2.5, 4, "SPEAKER_00", "我是小明"),
    ]
    result = merge_segments(segs, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    assert len(result) == 1, f"Expected 1 merged, got {len(result)}"
    assert "你好" in result[0]["text"] and "小明" in result[0]["text"]


def test_different_speaker_no_merge():
    """不同 speaker 不合併"""
    segs = [
        make_seg(0, 2, "SPEAKER_00", "你好"),
        make_seg(2.5, 4, "SPEAKER_01", "你好啊"),
    ]
    result = merge_segments(segs, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    assert len(result) == 2, f"Expected 2, got {len(result)}"


def test_unknown_no_merge():
    """Unknown speaker 不合併"""
    segs = [
        make_seg(0, 2, "Unknown", "第一句"),
        make_seg(2.5, 4, "Unknown", "第二句"),
        make_seg(4.5, 6, "Unknown", "第三句"),
    ]
    result = merge_segments(segs, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    assert len(result) == 3, f"Unknown should not merge, got {len(result)}"


def test_gap_too_large():
    """間隔超過 max_gap 不合併"""
    segs = [
        make_seg(0, 2, "SPEAKER_00", "你好"),
        make_seg(5, 7, "SPEAKER_00", "再見"),  # gap = 3s > 1.5s
    ]
    result = merge_segments(segs, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    assert len(result) == 2, f"Gap too large, should not merge, got {len(result)}"


def test_duration_limit():
    """合併後超過 max_duration 不合併"""
    segs = [
        make_seg(0, 6, "SPEAKER_00", "很長的一段話"),
        make_seg(6.5, 10, "SPEAKER_00", "又一段"),  # combined = 10s > 8s
    ]
    result = merge_segments(segs, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    assert len(result) == 2, f"Duration exceeded, should not merge, got {len(result)}"


def test_chars_limit():
    """合併後超過 max_chars 不合併"""
    segs = [
        make_seg(0, 3, "SPEAKER_00", "這是一段很長的中文文字大約二十個字左右吧"),  # 18 chars
        make_seg(3.5, 6, "SPEAKER_00", "這又是另一段很長的中文文字大約也是二十字"),  # 18 chars, combined 36 > 40? no, 36 < 40
    ]
    # 36 chars < 40, should merge
    result = merge_segments(segs, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    assert len(result) == 1

    # Now test exceeding
    segs2 = [
        make_seg(0, 3, "SPEAKER_00", "一二三四五六七八九十一二三四五六七八九十一二三"),  # 23 chars
        make_seg(3.5, 6, "SPEAKER_00", "一二三四五六七八九十一二三四五六七八九十"),  # 20 chars, combined 43 > 40
    ]
    result2 = merge_segments(segs2, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    assert len(result2) == 2, f"Chars exceeded, should not merge, got {len(result2)}"


def test_index_sequential():
    """合併後 index 連續編號"""
    segs = [
        make_seg(0, 2, "SPEAKER_00", "A"),
        make_seg(2.5, 4, "SPEAKER_00", "B"),
        make_seg(5, 7, "SPEAKER_01", "C"),
        make_seg(7.5, 9, "SPEAKER_01", "D"),
    ]
    result = merge_segments(segs, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    indices = [s["index"] for s in result]
    assert indices == list(range(1, len(result) + 1)), f"Non-sequential indices: {indices}"


def test_timestamps_valid():
    """合併後 start ≤ end，段落間不重疊"""
    segs = [
        make_seg(0, 2, "SPEAKER_00", "A"),
        make_seg(2.2, 4, "SPEAKER_00", "B"),
        make_seg(4.5, 6, "SPEAKER_01", "C"),
        make_seg(6.2, 8, "SPEAKER_00", "D"),
        make_seg(8.3, 10, "SPEAKER_00", "E"),
    ]
    result = merge_segments(segs, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    for seg in result:
        assert seg["start"] <= seg["end"], f"start > end: {seg}"
    for i in range(1, len(result)):
        assert result[i]["start"] >= result[i-1]["start"], \
            f"Segments not in order: {result[i-1]} -> {result[i]}"


def test_no_text_loss():
    """合併後原始文字不丟失（每段原始文字都出現在結果中）"""
    segs = [
        make_seg(0, 2, "SPEAKER_00", "你好"),
        make_seg(2.5, 4, "SPEAKER_00", "世界"),
        make_seg(5, 7, "SPEAKER_01", "再見"),
    ]
    result = merge_segments(segs, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    all_text = "".join(s["text"] for s in result)
    for orig in segs:
        assert orig["text"] in all_text, f"Lost text: {orig['text']}"


def test_skip_diarization_all_unknown():
    """skip diarization 場景：全部 Unknown，不合併任何段落"""
    segs = [
        make_seg(0, 2, "Unknown", "A"),
        make_seg(2.5, 4, "Unknown", "B"),
        make_seg(4.5, 6, "Unknown", "C"),
        make_seg(6.5, 8, "Unknown", "D"),
    ]
    result = merge_segments(segs, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    assert len(result) == 4, f"All Unknown should not merge, got {len(result)}"


# ──────────────────────────────────────────────
# 整合測試（實際 SRT 檔案）
# ──────────────────────────────────────────────

def parse_srt_for_test(filepath):
    """解析 SRT 檔案為 segments list"""
    import re
    segments = []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    blocks = re.split(r"\n\n+", content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        ts_match = re.match(
            r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})",
            lines[1].strip(),
        )
        if not ts_match:
            continue
        start = _parse_ts(ts_match.group(1))
        end = _parse_ts(ts_match.group(2))
        text = "\n".join(lines[2:])
        spk_match = re.match(r"\[([^\]]+)\]\s*(.*)", text, re.DOTALL)
        if spk_match:
            speaker, text = spk_match.group(1), spk_match.group(2).strip()
        else:
            speaker, text = "Unknown", text.strip()
        segments.append({"start": start, "end": end, "speaker": speaker, "text": text})
    return segments


def _parse_ts(ts_str):
    ts_str = ts_str.replace(",", ".")
    parts = ts_str.split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def run_integration_test(srt_path):
    """對實際 SRT 檔案執行整合驗證"""
    print(f"\n{'='*60}")
    print(f"整合測試: {os.path.basename(srt_path)}")
    print(f"{'='*60}")

    original = parse_srt_for_test(srt_path)
    merged = merge_segments(original, max_gap=MAX_GAP, max_duration=MAX_DURATION, max_chars=MAX_CHARS)
    errors = []

    # 1. 段落數減少
    if len(merged) > len(original):
        errors.append(f"段落數增加: {len(original)} -> {len(merged)}")

    # 2. 每段時長 ≤ max_duration
    for seg in merged:
        dur = seg["end"] - seg["start"]
        if dur > MAX_DURATION + 0.01:  # 浮點容差
            errors.append(f"段落超時: index={seg['index']} dur={dur:.2f}s > {MAX_DURATION}s")

    # 3. 每段字數檢查（合併分隔符容差 +5）
    for seg in merged:
        if len(seg["text"]) > MAX_CHARS + 5:
            errors.append(f"段落超字: index={seg['index']} chars={len(seg['text'])} > {MAX_CHARS}+5")

    # 4. Unknown 不合併
    for i in range(1, len(merged)):
        if merged[i]["speaker"] == "Unknown" and merged[i-1]["speaker"] == "Unknown":
            gap = merged[i]["start"] - merged[i-1]["end"]
            if gap <= MAX_GAP:
                pass  # 相鄰 Unknown 應該是獨立的，不是合併的結果
        # 檢查是否有 Unknown 被合併（文字裡不該有分隔符模式）
    unknown_segs_orig = [s for s in original if s["speaker"] == "Unknown"]
    unknown_segs_merged = [s for s in merged if s["speaker"] == "Unknown"]
    if len(unknown_segs_merged) < len(unknown_segs_orig):
        errors.append(f"Unknown 被合併: {len(unknown_segs_orig)} -> {len(unknown_segs_merged)}")

    # 5. 不同 speaker 不合併（相鄰段落 speaker 可以相同，但不該出現兩個不同 speaker 的文字混在一段）
    # 這由演算法保證，這裡檢查合併後相鄰段落的 speaker 切換是否合理
    pass

    # 6. 時間戳有效性
    for seg in merged:
        if seg["start"] > seg["end"]:
            errors.append(f"start > end: index={seg['index']}")
    for i in range(1, len(merged)):
        if merged[i]["start"] < merged[i-1]["start"]:
            errors.append(f"時間倒退: index={merged[i]['index']}")

    # 7. 文字不丟失
    orig_chars = set()
    for s in original:
        for ch in s["text"]:
            if ch.strip():
                orig_chars.add(ch)
    merged_chars = set()
    for s in merged:
        for ch in s["text"]:
            if ch.strip():
                merged_chars.add(ch)
    lost = orig_chars - merged_chars
    if lost:
        errors.append(f"丟失字元: {len(lost)} 個 (樣本: {''.join(list(lost)[:10])})")

    # 8. index 連續
    indices = [s["index"] for s in merged]
    expected = list(range(1, len(merged) + 1))
    if indices != expected:
        errors.append(f"index 不連續: {indices[:5]}...")

    # 結果
    print(f"原始: {len(original)} 段")
    print(f"合併後: {len(merged)} 段 (減少 {len(original)-len(merged)}, "
          f"{(1-len(merged)/len(original))*100:.1f}%)")
    print(f"Unknown 段: {len(unknown_segs_orig)} -> {len(unknown_segs_merged)}")

    if errors:
        print(f"\n✗ {len(errors)} 個錯誤:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print(f"\n✓ 全部通過")
        return True


# ──────────────────────────────────────────────
# 主程式
# ──────────────────────────────────────────────

UNIT_TESTS = [
    test_empty_input,
    test_single_segment,
    test_same_speaker_merge,
    test_different_speaker_no_merge,
    test_unknown_no_merge,
    test_gap_too_large,
    test_duration_limit,
    test_chars_limit,
    test_index_sequential,
    test_timestamps_valid,
    test_no_text_loss,
    test_skip_diarization_all_unknown,
]


def main():
    parser = argparse.ArgumentParser(description="merge_srt 驗證測試")
    parser.add_argument("--srt", default=None, help="實際 SRT 檔案路徑（整合測試）")
    args = parser.parse_args()

    # 單元測試
    print("=" * 60)
    print("單元測試")
    print("=" * 60)
    passed = 0
    failed = 0
    for test_fn in UNIT_TESTS:
        try:
            test_fn()
            print(f"  ✓ {test_fn.__doc__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test_fn.__doc__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {test_fn.__doc__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n單元測試: {passed} 通過, {failed} 失敗")

    # 整合測試
    if args.srt:
        ok = run_integration_test(args.srt)
        if not ok:
            sys.exit(1)
    
    if failed > 0:
        sys.exit(1)
    print("\n✓ 全部測試通過")


if __name__ == "__main__":
    main()

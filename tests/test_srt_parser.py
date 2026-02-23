#!/usr/bin/env python3
"""
SRT 解析邏輯測試
測試 GUI 中的 _parse_srt 方法（獨立測試，不依賴 Qt）

用法: python tests/test_srt_parser.py
"""
import os
import sys
import tempfile
import re
from pathlib import Path

# 獨立實作 parse_srt（與 GUI 中的邏輯相同）
def parse_srt(srt_path):
    """解析 SRT 檔案，回傳段落列表"""
    segments = []
    try:
        content = Path(srt_path).read_text(encoding='utf-8')
        blocks = content.strip().split('\n\n')
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                # 解析時間戳: 00:00:00,000 --> 00:00:02,500
                time_match = re.match(
                    r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})',
                    lines[1]
                )
                if time_match:
                    g = time_match.groups()
                    start_ms = (int(g[0])*3600 + int(g[1])*60 + int(g[2])) * 1000 + int(g[3])
                    end_ms = (int(g[4])*3600 + int(g[5])*60 + int(g[6])) * 1000 + int(g[7])
                    text = '\n'.join(lines[2:])
                    segments.append({
                        'start_ms': start_ms,
                        'end_ms': end_ms,
                        'text': text,
                        'time_str': lines[1],
                    })
    except Exception as e:
        print(f"⚠ SRT 解析失敗: {e}")
    return segments


# ──────────────────────────────────────────────
# 測試案例
# ──────────────────────────────────────────────

def test_basic_srt():
    """基本 SRT 格式解析"""
    srt_content = """1
00:00:00,000 --> 00:00:02,500
[SPEAKER_00] 你好

2
00:00:02,500 --> 00:00:05,000
[SPEAKER_01] 你好啊
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        srt_path = f.name
    
    try:
        segments = parse_srt(srt_path)
        assert len(segments) == 2, f"Expected 2 segments, got {len(segments)}"
        
        # 檢查第一段
        assert segments[0]['start_ms'] == 0
        assert segments[0]['end_ms'] == 2500
        assert '[SPEAKER_00]' in segments[0]['text']
        assert '你好' in segments[0]['text']
        
        # 檢查第二段
        assert segments[1]['start_ms'] == 2500
        assert segments[1]['end_ms'] == 5000
        assert '[SPEAKER_01]' in segments[1]['text']
    finally:
        os.unlink(srt_path)


def test_multiline_text():
    """多行文字解析"""
    srt_content = """1
00:00:00,000 --> 00:00:03,000
[SPEAKER_00] 這是第一行
這是第二行
這是第三行
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        srt_path = f.name
    
    try:
        segments = parse_srt(srt_path)
        assert len(segments) == 1
        text = segments[0]['text']
        assert '第一行' in text
        assert '第二行' in text
        assert '第三行' in text
        assert text.count('\n') == 2, "Should have 2 newlines for 3 lines"
    finally:
        os.unlink(srt_path)


def test_time_conversion():
    """時間戳轉換正確性"""
    srt_content = """1
01:23:45,678 --> 01:23:50,123
Test
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        srt_path = f.name
    
    try:
        segments = parse_srt(srt_path)
        assert len(segments) == 1
        
        # 1:23:45.678 = (1*3600 + 23*60 + 45) * 1000 + 678
        expected_start = (1*3600 + 23*60 + 45) * 1000 + 678
        assert segments[0]['start_ms'] == expected_start, \
            f"Expected {expected_start}, got {segments[0]['start_ms']}"
        
        expected_end = (1*3600 + 23*60 + 50) * 1000 + 123
        assert segments[0]['end_ms'] == expected_end
    finally:
        os.unlink(srt_path)


def test_chinese_characters():
    """中文字元處理"""
    srt_content = """1
00:00:00,000 --> 00:00:02,000
[說話者_00] 這是中文測試，包含標點符號！

2
00:00:02,000 --> 00:00:04,000
[說話者_01] 還有繁體中文：臺灣、測試
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        srt_path = f.name
    
    try:
        segments = parse_srt(srt_path)
        assert len(segments) == 2
        assert '中文測試' in segments[0]['text']
        assert '標點符號' in segments[0]['text']
        assert '臺灣' in segments[1]['text']
    finally:
        os.unlink(srt_path)


def test_empty_file():
    """空檔案處理"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write("")
        srt_path = f.name
    
    try:
        segments = parse_srt(srt_path)
        assert segments == [], f"Expected empty list, got {segments}"
    finally:
        os.unlink(srt_path)


def test_malformed_timestamp():
    """格式錯誤的時間戳"""
    srt_content = """1
00:00:00 --> 00:00:02
Invalid timestamp format

2
00:00:02,000 --> 00:00:04,000
[SPEAKER_00] Valid segment
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        srt_path = f.name
    
    try:
        segments = parse_srt(srt_path)
        # 第一段應該被跳過，只解析第二段
        assert len(segments) == 1
        assert 'Valid segment' in segments[0]['text']
    finally:
        os.unlink(srt_path)


def test_missing_text():
    """缺少文字內容"""
    srt_content = """1
00:00:00,000 --> 00:00:02,000

2
00:00:02,000 --> 00:00:04,000
[SPEAKER_00] Valid text
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        srt_path = f.name
    
    try:
        segments = parse_srt(srt_path)
        # 第一段只有 2 行（index + timestamp），沒有文字，應該被跳過（len(lines) < 3）
        assert len(segments) == 1
        assert 'Valid text' in segments[0]['text']
    finally:
        os.unlink(srt_path)


def test_extra_blank_lines():
    """額外空行處理"""
    srt_content = """1
00:00:00,000 --> 00:00:02,000
[SPEAKER_00] First



2
00:00:02,000 --> 00:00:04,000
[SPEAKER_01] Second


"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        srt_path = f.name
    
    try:
        segments = parse_srt(srt_path)
        assert len(segments) == 2
        assert 'First' in segments[0]['text']
        assert 'Second' in segments[1]['text']
    finally:
        os.unlink(srt_path)


def test_time_str_preserved():
    """time_str 欄位保留原始格式"""
    srt_content = """1
00:00:00,000 --> 00:00:02,500
Test
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        srt_path = f.name
    
    try:
        segments = parse_srt(srt_path)
        assert len(segments) == 1
        assert segments[0]['time_str'] == '00:00:00,000 --> 00:00:02,500'
    finally:
        os.unlink(srt_path)


def test_real_srt_file():
    """實際 SRT 檔案測試（如果存在）"""
    sample_srt = Path(__file__).parent.parent / 'examples' / 'sample-01_transcription.srt'
    if not sample_srt.exists():
        print("    (跳過: sample-01_transcription.srt 不存在)")
        return
    
    segments = parse_srt(str(sample_srt))
    assert len(segments) > 0, "Sample SRT should have segments"
    
    # 驗證基本結構
    for seg in segments:
        assert 'start_ms' in seg
        assert 'end_ms' in seg
        assert 'text' in seg
        assert 'time_str' in seg
        assert seg['start_ms'] <= seg['end_ms'], \
            f"start_ms should <= end_ms: {seg}"


def test_special_characters():
    """特殊字元處理"""
    srt_content = """1
00:00:00,000 --> 00:00:02,000
[SPEAKER_00] Test with "quotes" and 'apostrophes'

2
00:00:02,000 --> 00:00:04,000
[SPEAKER_01] Symbols: @#$%^&*()
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        srt_path = f.name
    
    try:
        segments = parse_srt(srt_path)
        assert len(segments) == 2
        assert '"quotes"' in segments[0]['text']
        assert "'apostrophes'" in segments[0]['text']
        assert '@#$%^&*()' in segments[1]['text']
    finally:
        os.unlink(srt_path)


def test_zero_duration():
    """零時長段落"""
    srt_content = """1
00:00:00,000 --> 00:00:00,000
[SPEAKER_00] Zero duration
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
        f.write(srt_content)
        srt_path = f.name
    
    try:
        segments = parse_srt(srt_path)
        assert len(segments) == 1
        assert segments[0]['start_ms'] == segments[0]['end_ms']
    finally:
        os.unlink(srt_path)


# ──────────────────────────────────────────────
# 主程式
# ──────────────────────────────────────────────

TESTS = [
    test_basic_srt,
    test_multiline_text,
    test_time_conversion,
    test_chinese_characters,
    test_empty_file,
    test_malformed_timestamp,
    test_missing_text,
    test_extra_blank_lines,
    test_time_str_preserved,
    test_real_srt_file,
    test_special_characters,
    test_zero_duration,
]


def main():
    print("=" * 60)
    print("SRT 解析邏輯測試")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_fn in TESTS:
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
    
    print(f"\n結果: {passed} 通過, {failed} 失敗")
    
    if failed > 0:
        sys.exit(1)
    print("✓ 全部通過")


if __name__ == "__main__":
    main()

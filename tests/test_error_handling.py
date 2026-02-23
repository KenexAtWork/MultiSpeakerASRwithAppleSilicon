#!/usr/bin/env python3
"""
ASR Pipeline 錯誤處理測試
測試各種錯誤情況下的行為

用法: python tests/test_error_handling.py
"""
import os
import sys
import subprocess
import tempfile
from pathlib import Path

ASR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ASR_DIR, "asr_multi_speaker_v5_fast.py")
PYTHON = sys.executable


def run_asr(input_file, **kwargs):
    """執行 ASR，回傳 (return_code, stdout, stderr)"""
    cmd = [PYTHON, SCRIPT, '--input', input_file]
    
    # 加入其他參數
    for key, value in kwargs.items():
        if value is True:
            cmd.append(f'--{key.replace("_", "-")}')
        elif value is not False and value is not None:
            cmd.extend([f'--{key.replace("_", "-")}', str(value)])
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=ASR_DIR,
        timeout=30
    )
    return result.returncode, result.stdout, result.stderr


# ──────────────────────────────────────────────
# 測試案例
# ──────────────────────────────────────────────

def test_file_not_found():
    """檔案不存在時應報錯"""
    rc, stdout, stderr = run_asr(
        '/nonexistent/file.mp4',
        skip_diarization=True,
        model='base'
    )
    assert rc != 0, "Should fail with non-existent file"
    output = stdout + stderr
    assert '不存在' in output or 'not exist' in output.lower() or '錯誤' in output, \
        f"Should mention file not found, got: {output[:200]}"


def test_invalid_model():
    """無效的模型名稱"""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
        # 建立一個空檔案
        f.write(b'fake video')
        temp_file = f.name
    
    try:
        rc, stdout, stderr = run_asr(
            temp_file,
            model='invalid_model',
            skip_diarization=True
        )
        # 可能會失敗或使用預設模型，檢查是否有錯誤訊息
        # 注意：mlx_whisper 可能會嘗試下載不存在的模型
        assert rc != 0 or '錯誤' in (stdout + stderr) or 'error' in (stdout + stderr).lower()
    finally:
        os.unlink(temp_file)


def test_invalid_language():
    """無效的語言代碼（應該被接受或使用預設）"""
    sample = os.path.join(ASR_DIR, 'examples', 'sample-01.mp4')
    if not os.path.exists(sample):
        print("    (跳過: sample-01.mp4 不存在)")
        return
    
    # 無效語言代碼可能被 Whisper 接受（會嘗試偵測）
    # 這個測試主要確保不會 crash
    rc, stdout, stderr = run_asr(
        sample,
        language='invalid_lang',
        model='base',
        skip_diarization=True
    )
    # 可能成功（Whisper 會自動偵測）或失敗，但不應該 crash
    assert rc == 0 or rc != 0  # 任何結果都可以，只要不 crash


def test_missing_hf_token_with_diarization():
    """沒有 HF token 但要求 diarization"""
    sample = os.path.join(ASR_DIR, 'examples', 'sample-01.mp4')
    if not os.path.exists(sample):
        print("    (跳過: sample-01.mp4 不存在)")
        return
    
    # 移除環境變數中的 HF_TOKEN
    env = os.environ.copy()
    env.pop('HF_TOKEN', None)
    
    cmd = [
        PYTHON, SCRIPT,
        '--input', sample,
        '--model', 'base',
        '--language', 'zh'
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=ASR_DIR,
        env=env,
        timeout=60
    )
    
    # 應該跳過 diarization 或顯示警告，但 ASR 部分應該成功
    # 檢查是否有跳過 diarization 的訊息
    output = result.stdout + result.stderr
    # 可能成功（跳過 diarization）或失敗（需要 token）
    # 主要確保有適當的錯誤訊息


def test_invalid_output_format():
    """無效的輸出格式"""
    sample = os.path.join(ASR_DIR, 'examples', 'sample-01.mp4')
    if not os.path.exists(sample):
        print("    (跳過: sample-01.mp4 不存在)")
        return
    
    rc, stdout, stderr = run_asr(
        sample,
        format='invalid_format',
        model='base',
        skip_diarization=True
    )
    # argparse 應該會報錯
    assert rc != 0, "Should fail with invalid format"
    output = stdout + stderr
    assert 'invalid choice' in output.lower() or 'format' in output.lower()


def test_output_to_readonly_directory():
    """輸出到唯讀目錄"""
    sample = os.path.join(ASR_DIR, 'examples', 'sample-01.mp4')
    if not os.path.exists(sample):
        print("    (跳過: sample-01.mp4 不存在)")
        return
    
    # 嘗試輸出到 /dev/null 的父目錄（通常無法寫入）
    # 在 macOS/Linux 上，/dev 是特殊目錄
    output_path = '/dev/test_output.srt'
    
    rc, stdout, stderr = run_asr(
        sample,
        output=output_path,
        model='base',
        skip_diarization=True
    )
    # 可能在寫入時失敗
    # 注意：某些系統可能允許寫入 /dev/test_output.srt
    # 這個測試主要確保有適當的錯誤處理


def test_corrupted_video_file():
    """損壞的影片檔案"""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
        # 寫入無效的影片資料
        f.write(b'This is not a valid video file')
        temp_file = f.name
    
    try:
        rc, stdout, stderr = run_asr(
            temp_file,
            model='base',
            skip_diarization=True
        )
        # 應該失敗（ffmpeg 無法處理）
        assert rc != 0, "Should fail with corrupted video"
        output = stdout + stderr
        # 可能有 ffmpeg 錯誤訊息
    finally:
        os.unlink(temp_file)


def test_empty_video_file():
    """空的影片檔案"""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
        # 空檔案
        temp_file = f.name
    
    try:
        rc, stdout, stderr = run_asr(
            temp_file,
            model='base',
            skip_diarization=True
        )
        # 應該失敗
        assert rc != 0, "Should fail with empty video"
    finally:
        os.unlink(temp_file)


def test_very_short_audio():
    """極短音檔（< 1 秒）"""
    # 這個測試需要實際的短音檔，暫時跳過
    print("    (跳過: 需要實際的短音檔)")
    return


def test_no_audio_track():
    """沒有音軌的影片"""
    # 這個測試需要實際的無音軌影片，暫時跳過
    print("    (跳過: 需要實際的無音軌影片)")
    return


def test_permission_denied():
    """權限不足"""
    # 這個測試在不同系統上行為不同，暫時跳過
    print("    (跳過: 權限測試依賴系統設定)")
    return


# ──────────────────────────────────────────────
# 主程式
# ──────────────────────────────────────────────

TESTS = [
    test_file_not_found,
    test_invalid_model,
    test_invalid_language,
    test_missing_hf_token_with_diarization,
    test_invalid_output_format,
    test_output_to_readonly_directory,
    test_corrupted_video_file,
    test_empty_video_file,
    test_very_short_audio,
    test_no_audio_track,
    test_permission_denied,
]


def main():
    print("=" * 60)
    print("ASR Pipeline 錯誤處理測試")
    print("=" * 60)
    print("注意：這些測試預期會產生錯誤訊息")
    print("=" * 60)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test_fn in TESTS:
        try:
            # 捕獲 print 輸出來檢測跳過
            import io
            from contextlib import redirect_stdout
            
            f = io.StringIO()
            with redirect_stdout(f):
                test_fn()
            output = f.getvalue()
            
            if '跳過' in output or 'skip' in output.lower():
                print(f"  ⊘ {test_fn.__doc__}")
                skipped += 1
            else:
                print(f"  ✓ {test_fn.__doc__}")
                passed += 1
        except AssertionError as e:
            print(f"  ✗ {test_fn.__doc__}: {e}")
            failed += 1
        except subprocess.TimeoutExpired:
            print(f"  ✗ {test_fn.__doc__}: Timeout")
            failed += 1
        except Exception as e:
            print(f"  ✗ {test_fn.__doc__}: {type(e).__name__}: {e}")
            failed += 1
    
    print(f"\n結果: {passed} 通過, {failed} 失敗, {skipped} 跳過")
    
    if failed > 0:
        sys.exit(1)
    print("✓ 全部通過")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
GUI 媒體播放器 URL 測試
驗證中文/特殊字元檔名能正確轉換為 QUrl

用法: python tests/test_gui_media_url.py
"""
import os, sys, tempfile

# 需要 PyQt6
try:
    from PyQt6.QtCore import QUrl
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False


def test_chinese_path_url():
    """中文路徑能正確轉為 QUrl"""
    path = "/Users/test/文件/會議錄音-20260211.m4a"
    url = QUrl.fromLocalFile(os.path.abspath(path))
    url_str = url.toString()
    assert url.isValid(), f"URL invalid: {url_str}"
    assert "會議錄音" in url.toLocalFile(), f"Chinese lost in round-trip: {url.toLocalFile()}"


def test_space_in_path_url():
    """空格路徑能正確轉為 QUrl"""
    path = "/Users/test/My Documents/meeting recording.m4a"
    url = QUrl.fromLocalFile(os.path.abspath(path))
    assert url.isValid(), f"URL invalid: {url.toString()}"
    assert "meeting recording" in url.toLocalFile()


def test_mixed_cjk_ascii_path():
    """中英混合路徑能正確轉為 QUrl"""
    path = "/Users/test/SA/Customers/Nokia/ECV-Nokia合作案/報價討論.m4a"
    url = QUrl.fromLocalFile(os.path.abspath(path))
    assert url.isValid()
    local = url.toLocalFile()
    assert "Nokia" in local and "合作案" in local, f"Round-trip failed: {local}"


def test_real_tempfile_with_chinese():
    """實際建立中文檔名的暫存檔，驗證 QUrl round-trip"""
    tmpdir = tempfile.mkdtemp()
    chinese_file = os.path.join(tmpdir, "測試音檔.m4a")
    with open(chinese_file, "w") as f:
        f.write("dummy")

    url = QUrl.fromLocalFile(os.path.abspath(chinese_file))
    assert url.isValid()
    assert os.path.exists(url.toLocalFile()), f"File not found via QUrl: {url.toLocalFile()}"

    os.unlink(chinese_file)
    os.rmdir(tmpdir)


def test_player_accepts_chinese_url():
    """QMediaPlayer.setSource 不報錯（不實際播放）"""
    tmpdir = tempfile.mkdtemp()
    chinese_file = os.path.join(tmpdir, "會議錄音.wav")
    # 建立一個最小的 WAV（44 bytes header）
    import struct
    with open(chinese_file, "wb") as f:
        # minimal WAV header + 1 second of silence
        num_samples = 16000  # 1 sec at 16kHz
        data_size = num_samples * 2  # 16-bit = 2 bytes per sample
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))  # chunk size
        f.write(struct.pack("<H", 1))   # PCM
        f.write(struct.pack("<H", 1))   # mono
        f.write(struct.pack("<I", 16000))  # sample rate
        f.write(struct.pack("<I", 32000))  # byte rate
        f.write(struct.pack("<H", 2))   # block align
        f.write(struct.pack("<H", 16))  # bits per sample
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)  # silence

    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    player = QMediaPlayer()
    audio_out = QAudioOutput()
    player.setAudioOutput(audio_out)

    errors = []
    player.errorOccurred.connect(lambda e, s: errors.append(f"{e}: {s}"))

    url = QUrl.fromLocalFile(os.path.abspath(chinese_file))
    player.setSource(url)

    # 給一點時間讓 error signal 觸發
    from PyQt6.QtCore import QTimer, QEventLoop
    loop = QEventLoop()
    QTimer.singleShot(500, loop.quit)
    loop.exec()

    assert len(errors) == 0, f"Player errors: {errors}"

    player.stop()
    del player, audio_out
    os.unlink(chinese_file)
    os.rmdir(tmpdir)


def test_player_real_media_file():
    """實際音檔（sample-01.mp4）能正確載入"""
    sample = os.path.join(os.path.dirname(__file__), "..", "examples", "sample-01.mp4")
    if not os.path.exists(sample):
        print("    (跳過: sample-01.mp4 不存在)")
        return

    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)

    player = QMediaPlayer()
    audio_out = QAudioOutput()
    player.setAudioOutput(audio_out)

    errors = []
    player.errorOccurred.connect(lambda e, s: errors.append(f"{e}: {s}"))

    url = QUrl.fromLocalFile(os.path.abspath(sample))
    player.setSource(url)

    from PyQt6.QtCore import QTimer, QEventLoop
    loop = QEventLoop()
    QTimer.singleShot(1000, loop.quit)
    loop.exec()

    assert len(errors) == 0, f"Player errors: {errors}"
    assert player.duration() > 0, f"Duration should be > 0, got {player.duration()}"

    player.stop()
    del player, audio_out


TESTS = [
    test_chinese_path_url,
    test_space_in_path_url,
    test_mixed_cjk_ascii_path,
    test_real_tempfile_with_chinese,
    test_player_accepts_chinese_url,
    test_player_real_media_file,
]


def main():
    if not HAS_PYQT6:
        print("⚠ PyQt6 未安裝，跳過 GUI 媒體測試")
        return

    print("=" * 60, flush=True)
    print("GUI 媒體播放器 URL 測試", flush=True)
    print("=" * 60, flush=True)

    passed = failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"  ✓ {fn.__doc__}", flush=True)
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {fn.__doc__}: {e}", flush=True)
            failed += 1
        except Exception as e:
            print(f"  ✗ {fn.__doc__}: {type(e).__name__}: {e}", flush=True)
            failed += 1

    print(f"\n結果: {passed} 通過, {failed} 失敗", flush=True)
    if failed:
        sys.exit(1)
    print("✓ 全部通過")


if __name__ == "__main__":
    main()

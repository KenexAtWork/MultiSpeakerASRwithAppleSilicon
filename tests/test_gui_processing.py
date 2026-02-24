#!/usr/bin/env python3
"""
測試 GUI 的 ASR Worker 功能
不啟動完整 GUI，只測試處理邏輯
"""
import sys
import os
from pathlib import Path
from PyQt6.QtCore import QCoreApplication

# 設定路徑
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

# 載入 .env（手動）
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()
    print(f"✓ 已載入 .env 檔案")
else:
    print(f"⚠️  未找到 .env 檔案")

from gui.core.asr_worker import ASRWorker


def test_asr_worker():
    """測試 ASR Worker"""
    app = QCoreApplication(sys.argv)
    
    # 測試檔案
    test_video = "examples/sample-01.mp4"
    output_file = "examples/sample-01_gui_test.srt"
    
    # 清理舊的測試輸出
    if Path(output_file).exists():
        Path(output_file).unlink()
    
    print("=" * 60)
    print("測試 GUI ASR Worker")
    print("=" * 60)
    print(f"輸入: {test_video}")
    print(f"輸出: {output_file}")
    print("=" * 60)
    
    # 建立 Worker
    worker = ASRWorker(
        video_file=test_video,
        output_file=output_file,
        language="zh",
        model_size="medium",
        output_format="srt",
        skip_diarization=False,
        use_gpu=True
    )
    
    # 連接信號
    def on_progress(value):
        print(f"進度: {value}%")
    
    def on_stage_changed(stage):
        print(f"階段: {stage}")
    
    def on_log_message(msg):
        print(f"LOG: {msg}")
    
    def on_finished(output):
        print("=" * 60)
        print(f"✓ 處理完成！")
        print(f"✓ 輸出檔案: {output}")
        print("=" * 60)
        
        # 檢查檔案是否存在
        if Path(output).exists():
            size = Path(output).stat().st_size
            print(f"✓ 檔案大小: {size} bytes")
            
            # 讀取前幾行
            with open(output, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:10]
                print(f"✓ 前 10 行內容:")
                print("".join(lines))
        else:
            print("✗ 輸出檔案不存在！")
        
        app.quit()
    
    def on_error(error_msg):
        print("=" * 60)
        print("✗ 處理失敗！")
        print(error_msg)
        print("=" * 60)
        app.quit()
    
    worker.progress.connect(on_progress)
    worker.stage_changed.connect(on_stage_changed)
    worker.log_message.connect(on_log_message)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)
    
    # 啟動處理
    print("\n開始處理...\n")
    worker.start()
    
    # 執行事件循環
    sys.exit(app.exec())


if __name__ == "__main__":
    test_asr_worker()

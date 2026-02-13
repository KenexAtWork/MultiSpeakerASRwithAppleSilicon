#!/usr/bin/env python3
"""
ASR Multi-Speaker Transcription - GUI Application
使用 PyQt6 建立的圖形界面版本
"""
import sys
import os
from pathlib import Path

# 將父目錄加入 Python 路徑，以便導入 asr_multi_speaker_v5_fast
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow


def main():
    """主程式入口"""
    # 啟用高 DPI 支援
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("ASR Multi-Speaker Transcription")
    app.setOrganizationName("ASR Tools")
    
    # 設定應用程式樣式
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

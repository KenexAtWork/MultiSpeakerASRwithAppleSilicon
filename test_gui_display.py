#!/usr/bin/env python3
"""
測試 GUI 界面是否能正常顯示
會啟動 GUI 並在 3 秒後自動關閉
"""
import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer

# 設定路徑
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

# 載入 .env
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

sys.path.insert(0, 'gui')
from ui.main_window import MainWindow


def test_gui_display():
    """測試 GUI 顯示"""
    print("=" * 60)
    print("測試 GUI 界面顯示")
    print("=" * 60)
    
    # 啟用高 DPI 支援
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("ASR Multi-Speaker Transcription")
    app.setOrganizationName("ASR Tools")
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    print("✓ GUI 視窗已顯示")
    print("✓ 視窗大小:", window.size().width(), "x", window.size().height())
    print("✓ 視窗標題:", window.windowTitle())
    
    # 3 秒後自動關閉
    def auto_close():
        print("\n✓ GUI 測試完成，自動關閉")
        print("=" * 60)
        app.quit()
    
    QTimer.singleShot(3000, auto_close)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    test_gui_display()

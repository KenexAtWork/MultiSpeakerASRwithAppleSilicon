#!/usr/bin/env python3
"""
取得 GUI 中指定 widget 的螢幕座標（邏輯座標，可直接用於 cliclick）
用法: 在 GUI main.py 啟動後，透過 import 使用，或獨立執行列出所有按鈕座標
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPoint


def get_all_buttons(window):
    """取得視窗中所有 QPushButton 的名稱和螢幕中心座標"""
    from PyQt6.QtWidgets import QPushButton
    results = []
    for btn in window.findChildren(QPushButton):
        text = btn.text()
        if not text:
            continue
        # 取得 widget 在螢幕上的全域座標
        global_pos = btn.mapToGlobal(QPoint(btn.width() // 2, btn.height() // 2))
        results.append({
            "text": text,
            "x": global_pos.x(),
            "y": global_pos.y(),
            "width": btn.width(),
            "height": btn.height(),
            "visible": btn.isVisible(),
            "enabled": btn.isEnabled()
        })
    return results


if __name__ == "__main__":
    import json
    app = QApplication.instance()
    if not app:
        print("錯誤: 需要在 GUI 執行環境中使用", file=sys.stderr)
        sys.exit(1)
    
    for widget in app.topLevelWidgets():
        if hasattr(widget, 'select_btn'):  # MainWindow
            buttons = get_all_buttons(widget)
            print(json.dumps(buttons, ensure_ascii=False, indent=2))
            break

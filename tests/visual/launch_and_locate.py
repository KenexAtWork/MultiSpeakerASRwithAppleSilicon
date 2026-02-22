#!/usr/bin/env python3
"""
啟動 ASR GUI 並輸出所有可互動元素的螢幕座標到 JSON 檔
用法:
  python tests/visual/launch_and_locate.py [--dump-and-exit] [--geometry=x,y,w,h]
"""
import sys
import os
import json
from pathlib import Path

# 確保能 import gui 模組（需要從 asr/ 目錄 import）
asr_dir = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, asr_dir)
sys.path.insert(0, str(Path(asr_dir) / "gui"))
os.chdir(asr_dir)

from PyQt6.QtWidgets import QApplication, QPushButton, QComboBox, QCheckBox
from PyQt6.QtCore import QTimer, QPoint
from gui.ui.main_window import MainWindow

OUTPUT_FILE = Path(__file__).parent / "widget_positions.json"


def dump_widgets(window):
    """收集所有可互動 widget 的螢幕座標"""
    widgets = []
    for btn in window.findChildren(QPushButton):
        text = btn.text().strip()
        if not text:
            continue
        gp = btn.mapToGlobal(QPoint(btn.width() // 2, btn.height() // 2))
        widgets.append({"type": "button", "text": text,
                        "x": gp.x(), "y": gp.y(),
                        "visible": btn.isVisible(), "enabled": btn.isEnabled()})
    for combo in window.findChildren(QComboBox):
        name = combo.objectName() or combo.currentText()
        gp = combo.mapToGlobal(QPoint(combo.width() // 2, combo.height() // 2))
        widgets.append({"type": "combobox", "text": name,
                        "current": combo.currentText(),
                        "x": gp.x(), "y": gp.y(),
                        "visible": combo.isVisible(), "enabled": combo.isEnabled()})
    for cb in window.findChildren(QCheckBox):
        gp = cb.mapToGlobal(QPoint(cb.width() // 2, cb.height() // 2))
        widgets.append({"type": "checkbox", "text": cb.text(),
                        "checked": cb.isChecked(),
                        "x": gp.x(), "y": gp.y(),
                        "visible": cb.isVisible(), "enabled": cb.isEnabled()})
    return widgets


def main():
    dump_and_exit = "--dump-and-exit" in sys.argv

    geometry = None
    for arg in sys.argv:
        if arg.startswith("--geometry="):
            parts = arg.split("=")[1].split(",")
            geometry = tuple(int(p) for p in parts)

    # 過濾掉自訂參數，避免 QApplication 解析錯誤
    qt_args = [a for a in sys.argv if not a.startswith("--geometry") and a != "--dump-and-exit"]
    app = QApplication(qt_args)
    window = MainWindow()

    if geometry:
        x, y, w, h = geometry
        window.setGeometry(x, y, w, h)

    window.show()

    def on_ready():
        if geometry:
            x, y, w, h = geometry
            window.move(x, y)
            window.resize(w, h)
        QTimer.singleShot(500, do_dump)

    def do_dump():
        widgets = dump_widgets(window)
        OUTPUT_FILE.write_text(json.dumps(widgets, ensure_ascii=False, indent=2))
        print(f"✓ Widget 座標已輸出至 {OUTPUT_FILE}")
        for w in widgets:
            if w["visible"]:
                extra = ""
                if w["type"] == "checkbox":
                    extra = f" checked={w['checked']}"
                elif w["type"] == "combobox":
                    extra = f" current='{w['current']}'"
                print(f"  {w['type']:>10} | ({w['x']:>4},{w['y']:>4}) | {w['text']}{extra}")
        if dump_and_exit:
            app.quit()

    QTimer.singleShot(1000, on_ready)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

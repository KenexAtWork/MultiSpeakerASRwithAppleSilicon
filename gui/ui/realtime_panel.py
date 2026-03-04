"""
Realtime ASR Panel - UI for live microphone transcription.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QTextEdit, QProgressBar, QGroupBox, QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtGui import QFont, QTextCursor
from pathlib import Path
import os

from core.realtime_worker import RealtimeASRWorker


class RealtimePanel(QWidget):
    """Panel for real-time microphone transcription."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._session_texts = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Realtime ASR")
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        subtitle = QLabel("Live microphone transcription using MLX Whisper")
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(subtitle)

        # Settings
        settings = QGroupBox("Settings")
        settings_layout = QHBoxLayout()

        settings_layout.addWidget(QLabel("Language:"))
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "auto (Auto-detect)", "zh (Chinese)", "en (English)",
            "ja (Japanese)",
        ])
        settings_layout.addWidget(self.language_combo)

        settings_layout.addSpacing(15)
        settings_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "tiny (~1-2 GB)", "base (~2-3 GB)",
            "small (~3-4 GB)", "medium (~5-7 GB)",
        ])
        self.model_combo.setCurrentIndex(1)  # base for low latency
        settings_layout.addWidget(self.model_combo)

        settings_layout.addSpacing(15)
        settings_layout.addWidget(QLabel("Mic:"))
        self.device_combo = QComboBox()
        self._refresh_devices()
        settings_layout.addWidget(self.device_combo)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(30)
        refresh_btn.setToolTip("Refresh audio devices")
        refresh_btn.clicked.connect(self._refresh_devices)
        settings_layout.addWidget(refresh_btn)

        settings_layout.addStretch()
        settings.setLayout(settings_layout)
        layout.addWidget(settings)

        # Controls
        ctrl_layout = QHBoxLayout()

        self.start_btn = QPushButton("🎙 Start")
        self.start_btn.setMinimumHeight(44)
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "font-size: 14px; font-weight: bold; border-radius: 6px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.start_btn.clicked.connect(self._toggle_recording)
        ctrl_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.setMinimumHeight(44)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._toggle_pause)
        ctrl_layout.addWidget(self.pause_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setMinimumHeight(44)
        self.clear_btn.clicked.connect(self._clear_transcript)
        ctrl_layout.addWidget(self.clear_btn)

        self.save_btn = QPushButton("Save TXT")
        self.save_btn.setMinimumHeight(44)
        self.save_btn.clicked.connect(self._save_transcript)
        ctrl_layout.addWidget(self.save_btn)

        layout.addLayout(ctrl_layout)

        # Status bar with VU meter
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setValue(0)
        self.level_bar.setFixedWidth(150)
        self.level_bar.setFixedHeight(16)
        self.level_bar.setTextVisible(False)
        self.level_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #ccc; border-radius: 3px; }"
            "QProgressBar::chunk { background-color: #4CAF50; }"
        )
        status_layout.addWidget(QLabel("Level:"))
        status_layout.addWidget(self.level_bar)

        layout.addLayout(status_layout)

        # Transcript area
        transcript_group = QGroupBox("Live Transcript")
        transcript_layout = QVBoxLayout()

        self.transcript_edit = QTextEdit()
        self.transcript_edit.setReadOnly(True)
        self.transcript_edit.setMinimumHeight(300)
        self.transcript_edit.setStyleSheet(
            "QTextEdit { font-size: 14px; line-height: 1.6; padding: 10px; }"
        )
        transcript_layout.addWidget(self.transcript_edit)

        transcript_group.setLayout(transcript_layout)
        layout.addWidget(transcript_group, stretch=1)

    def _refresh_devices(self):
        self.device_combo.clear()
        self.device_combo.addItem("Default", None)
        devices = RealtimeASRWorker.list_audio_devices()
        for idx, name in devices:
            self.device_combo.addItem(name, idx)

    def _get_language(self):
        text = self.language_combo.currentText()
        return text.split(" ")[0]

    def _get_model(self):
        text = self.model_combo.currentText()
        return text.split(" ")[0]

    def _get_device_index(self):
        return self.device_combo.currentData()

    def _toggle_recording(self):
        if self._worker and self._worker.isRunning():
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._worker = RealtimeASRWorker(
            language=self._get_language(),
            model_size=self._get_model(),
            device_index=self._get_device_index(),
        )
        self._worker.transcript_update.connect(self._on_transcript)
        self._worker.status_changed.connect(self._on_status)
        self._worker.error.connect(self._on_error)
        self._worker.level_update.connect(self._on_level)
        self._worker.stopped.connect(self._on_stopped)
        self._worker.start()

        self.start_btn.setText("⏹ Stop")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; "
            "font-size: 14px; font-weight: bold; border-radius: 6px; }"
            "QPushButton:hover { background-color: #d32f2f; }"
        )
        self.pause_btn.setEnabled(True)
        self.language_combo.setEnabled(False)
        self.model_combo.setEnabled(False)
        self.device_combo.setEnabled(False)

    def _stop_recording(self):
        if self._worker:
            self._worker.stop()
        self.start_btn.setEnabled(False)
        self.status_label.setText("Stopping...")

    def _on_stopped(self):
        self.start_btn.setText("🎙 Start")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "font-size: 14px; font-weight: bold; border-radius: 6px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.start_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("⏸ Pause")
        self.language_combo.setEnabled(True)
        self.model_combo.setEnabled(True)
        self.device_combo.setEnabled(True)
        self.level_bar.setValue(0)

    def _toggle_pause(self):
        if not self._worker:
            return
        if self._worker.is_paused:
            self._worker.resume()
            self.pause_btn.setText("⏸ Pause")
        else:
            self._worker.pause()
            self.pause_btn.setText("▶ Resume")

    def _on_transcript(self, text):
        self._session_texts.append(text)
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.transcript_edit.append(f"[{timestamp}] {text}")
        # Auto-scroll to bottom
        cursor = self.transcript_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.transcript_edit.setTextCursor(cursor)

    def _on_status(self, msg):
        self.status_label.setText(msg)

    def _on_error(self, msg):
        self.status_label.setText("Error")
        QMessageBox.critical(self, "Realtime ASR Error", msg)
        self._on_stopped()

    def _on_level(self, level):
        self.level_bar.setValue(int(level * 100))

    def _clear_transcript(self):
        self.transcript_edit.clear()
        self._session_texts.clear()

    def _save_transcript(self):
        if not self._session_texts:
            QMessageBox.information(self, "Save", "No transcript to save.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Transcript", str(Path.home() / "realtime_transcript.txt"),
            "Text Files (*.txt);;All Files (*)",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.transcript_edit.toPlainText())
            QMessageBox.information(self, "Saved", f"Transcript saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def cleanup(self):
        """Call on app exit to stop worker."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)

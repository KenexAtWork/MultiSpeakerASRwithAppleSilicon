"""
Realtime ASR Panel - UI for live microphone transcription.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QTextEdit, QProgressBar, QGroupBox, QFileDialog,
    QMessageBox, QSplitter, QSpinBox, QCheckBox,
)
from PyQt6.QtCore import Qt, QDateTime, QTimer
from PyQt6.QtGui import QFont, QTextCursor
from pathlib import Path
import os

from core.realtime_worker import RealtimeASRWorker, ENGINE_WHISPER, ENGINE_QWEN3
from core.live_summary_worker import LiveSummaryWorker


class RealtimePanel(QWidget):
    """Panel for real-time microphone transcription."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._session_texts = []
        # Mic preview stream (for VU meter before recording)
        self._preview_stream = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setInterval(100)
        self._preview_timer.timeout.connect(self._update_preview_level)
        self._preview_buffer = None
        # Live summary state
        self._summary_worker = None
        self._summary_pending_texts = []  # texts not yet summarized
        self._current_summary = ""
        self._summary_timer = QTimer(self)
        self._summary_timer.timeout.connect(self._trigger_summary)
        self._summary_segment_threshold = 10  # trigger after N new segments
        self._summary_interval_sec = 60       # or after T seconds
        self._init_ui()
        # Start mic preview immediately
        self._start_mic_preview()

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
        settings_layout.addWidget(QLabel("Engine:"))
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("MLX Whisper", ENGINE_WHISPER)
        self.engine_combo.addItem("Qwen3-ASR", ENGINE_QWEN3)
        self.engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        settings_layout.addWidget(self.engine_combo)

        settings_layout.addSpacing(15)
        settings_layout.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self._update_model_options()
        settings_layout.addWidget(self.model_combo)

        settings_layout.addSpacing(15)
        settings_layout.addWidget(QLabel("Mic:"))
        self.device_combo = QComboBox()
        self._refresh_devices()
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
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

        # --- Main content: Transcript (left) + Live Notes (right) ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

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
        splitter.addWidget(transcript_group)

        # Live Notes area
        notes_group = QGroupBox("Live Notes (Auto-Summary)")
        notes_layout = QVBoxLayout()

        # Summary settings row
        summary_settings = QHBoxLayout()

        self.summary_enabled = QCheckBox("Enable")
        self.summary_enabled.setChecked(False)
        self.summary_enabled.setToolTip("Auto-summarize transcript periodically via AWS Bedrock")
        summary_settings.addWidget(self.summary_enabled)

        summary_settings.addWidget(QLabel("Every"))
        self.summary_segments_spin = QSpinBox()
        self.summary_segments_spin.setRange(3, 50)
        self.summary_segments_spin.setValue(10)
        self.summary_segments_spin.setToolTip("Trigger summary after N new transcript segments")
        summary_settings.addWidget(self.summary_segments_spin)
        summary_settings.addWidget(QLabel("segments or"))

        self.summary_interval_spin = QSpinBox()
        self.summary_interval_spin.setRange(15, 300)
        self.summary_interval_spin.setValue(60)
        self.summary_interval_spin.setSuffix("s")
        self.summary_interval_spin.setToolTip("Trigger summary after N seconds")
        summary_settings.addWidget(self.summary_interval_spin)

        self.summary_now_btn = QPushButton("📝 Summarize Now")
        self.summary_now_btn.setToolTip("Trigger summary immediately")
        self.summary_now_btn.clicked.connect(self._trigger_summary)
        summary_settings.addWidget(self.summary_now_btn)

        self.save_notes_btn = QPushButton("💾 Save Notes")
        self.save_notes_btn.setToolTip("Save current live notes to file")
        self.save_notes_btn.clicked.connect(self._save_notes)
        summary_settings.addWidget(self.save_notes_btn)

        summary_settings.addStretch()
        notes_layout.addLayout(summary_settings)

        self.summary_status_label = QLabel("")
        self.summary_status_label.setStyleSheet("color: #888; font-size: 11px;")
        notes_layout.addWidget(self.summary_status_label)

        self.summary_edit = QTextEdit()
        self.summary_edit.setReadOnly(True)
        self.summary_edit.setMinimumHeight(250)
        self.summary_edit.setStyleSheet(
            "QTextEdit { font-size: 13px; line-height: 1.5; padding: 10px; }"
        )
        self.summary_edit.setPlaceholderText(
            "Live notes will appear here when auto-summary is enabled.\n"
            "Requires AWS Bedrock access (Claude / Nova)."
        )
        notes_layout.addWidget(self.summary_edit)

        notes_group.setLayout(notes_layout)
        splitter.addWidget(notes_group)

        splitter.setSizes([500, 400])
        layout.addWidget(splitter, stretch=1)

    def _refresh_devices(self):
        self.device_combo.clear()
        self.device_combo.addItem("Default", None)
        # Force sounddevice to re-scan hardware
        try:
            import sounddevice as sd
            sd._terminate()
            sd._initialize()
        except Exception:
            pass
        devices = RealtimeASRWorker.list_audio_devices()
        for idx, name in devices:
            self.device_combo.addItem(name, idx)
        # Restart preview with potentially new device
        self._start_mic_preview()

    # ---- Mic Preview (VU meter before recording) ----

    def _start_mic_preview(self):
        """Start a lightweight audio stream just for the VU meter."""
        self._stop_mic_preview()
        try:
            import sounddevice as sd
            import numpy as np

            self._preview_buffer = np.array([], dtype=np.float32)
            device_idx = self._get_device_index()

            def preview_callback(indata, frames, time_info, status):
                # Keep only last 1600 samples (~0.1s at 16kHz) for level calc
                self._preview_buffer = indata[:, 0].copy()

            self._preview_stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="float32",
                blocksize=1600,
                device=device_idx,
                callback=preview_callback,
            )
            self._preview_stream.start()
            self._preview_timer.start()
        except Exception:
            pass  # sounddevice not available or mic error — silently skip

    def _stop_mic_preview(self):
        """Stop the preview audio stream."""
        self._preview_timer.stop()
        if self._preview_stream is not None:
            try:
                self._preview_stream.stop()
                self._preview_stream.close()
            except Exception:
                pass
            self._preview_stream = None

    def _update_preview_level(self):
        """Update VU meter from preview stream."""
        if self._preview_buffer is not None and len(self._preview_buffer) > 0:
            import numpy as np
            rms = float(np.sqrt(np.mean(self._preview_buffer ** 2)))
            self.level_bar.setValue(int(min(rms * 10, 1.0) * 100))

    def _get_language(self):
        text = self.language_combo.currentText()
        return text.split(" ")[0]

    def _get_model(self):
        text = self.model_combo.currentText()
        engine = self.engine_combo.currentData()
        if engine == ENGINE_QWEN3:
            # Map UI label to a model_size hint the worker understands
            # "small" -> worker picks 0.6B, anything else -> 1.7B
            return "small" if "0.6B" in text else "large"
        return text.split(" ")[0]

    def _get_device_index(self):
        return self.device_combo.currentData()

    def _get_engine(self):
        return self.engine_combo.currentData()

    def _on_engine_changed(self, index):
        self._update_model_options()

    def _on_device_changed(self, index):
        """Restart mic preview when user selects a different device."""
        if not (self._worker and self._worker.isRunning()):
            self._start_mic_preview()

    def _update_model_options(self):
        engine = self.engine_combo.currentData()
        self.model_combo.clear()
        if engine == ENGINE_QWEN3:
            self.model_combo.addItems([
                "small (0.6B ~1.5 GB)",
                "large (1.7B ~3.5 GB)",
            ])
            self.model_combo.setCurrentIndex(0)
        else:
            self.model_combo.addItems([
                "tiny (~1-2 GB)", "base (~2-3 GB)",
                "small (~3-4 GB)", "medium (~5-7 GB)",
            ])
            self.model_combo.setCurrentIndex(1)

    def _toggle_recording(self):
        if self._worker and self._worker.isRunning():
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        # Stop mic preview — worker will open its own stream
        self._stop_mic_preview()

        self._worker = RealtimeASRWorker(
            language=self._get_language(),
            model_size=self._get_model(),
            device_index=self._get_device_index(),
            engine=self._get_engine(),
        )
        self._worker.transcript_update.connect(self._on_transcript)
        self._worker.status_changed.connect(self._on_status)
        self._worker.error.connect(self._on_error)
        self._worker.level_update.connect(self._on_level)
        self._worker.stopped.connect(self._on_stopped)
        self._worker.start()

        # Show loading state — model init takes time
        self.start_btn.setText("⏳ Loading model...")
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white; "
            "font-size: 14px; font-weight: bold; border-radius: 6px; }"
        )
        self.status_label.setText("Loading model, please wait...")
        self.pause_btn.setEnabled(False)
        self.language_combo.setEnabled(False)
        self.model_combo.setEnabled(False)
        self.device_combo.setEnabled(False)
        self.engine_combo.setEnabled(False)

        # Start summary timer if enabled
        if self.summary_enabled.isChecked():
            interval = self.summary_interval_spin.value() * 1000
            self._summary_timer.start(interval)

    def _stop_recording(self):
        if self._worker:
            self._worker.stop()
        self.start_btn.setEnabled(False)
        self.status_label.setText("Stopping...")

    def _on_stopped(self):
        self._summary_timer.stop()
        # Final summary on stop if there are pending texts
        if self.summary_enabled.isChecked() and self._summary_pending_texts:
            self._trigger_summary()

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
        self.engine_combo.setEnabled(True)
        self.level_bar.setValue(0)
        # Restart mic preview for VU meter
        self._start_mic_preview()

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
        self._summary_pending_texts.append(text)
        timestamp = QDateTime.currentDateTime().toString("hh:mm:ss")
        self.transcript_edit.append(f"[{timestamp}] {text}")
        # Auto-scroll to bottom
        cursor = self.transcript_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.transcript_edit.setTextCursor(cursor)
        # Check if we should trigger summary by segment count
        threshold = self.summary_segments_spin.value()
        if (self.summary_enabled.isChecked()
                and len(self._summary_pending_texts) >= threshold):
            self._trigger_summary()

    def _on_status(self, msg):
        self.status_label.setText(msg)
        # Transition from loading → recording when model is ready
        if msg == "Listening...":
            self.start_btn.setText("⏹ Stop")
            self.start_btn.setEnabled(True)
            self.start_btn.setStyleSheet(
                "QPushButton { background-color: #f44336; color: white; "
                "font-size: 14px; font-weight: bold; border-radius: 6px; }"
                "QPushButton:hover { background-color: #d32f2f; }"
            )
            self.pause_btn.setEnabled(True)

    def _on_error(self, msg):
        self.status_label.setText("Error")
        QMessageBox.critical(self, "Realtime ASR Error", msg)
        self._on_stopped()

    def _on_level(self, level):
        self.level_bar.setValue(int(level * 100))

    # ---- Live Summary ----

    def _trigger_summary(self):
        """Send pending transcript texts to Bedrock for summarization."""
        if not self._summary_pending_texts:
            return
        # Don't stack concurrent summary calls
        if self._summary_worker and self._summary_worker.isRunning():
            return

        texts = self._summary_pending_texts.copy()
        self._summary_pending_texts.clear()

        self._summary_worker = LiveSummaryWorker(
            new_texts=texts,
            previous_summary=self._current_summary,
        )
        self._summary_worker.summary_updated.connect(self._on_summary_updated)
        self._summary_worker.status.connect(self._on_summary_status)
        self._summary_worker.error.connect(self._on_summary_error)
        self._summary_worker.start()

        # Reset timer so next interval starts fresh
        if self._summary_timer.isActive():
            interval = self.summary_interval_spin.value() * 1000
            self._summary_timer.start(interval)

    def _on_summary_updated(self, summary):
        self._current_summary = summary
        self.summary_edit.setPlainText(summary)
        # Scroll to top so user sees the latest structure
        cursor = self.summary_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.summary_edit.setTextCursor(cursor)

    def _on_summary_status(self, msg):
        self.summary_status_label.setText(msg)

    def _on_summary_error(self, msg):
        self.summary_status_label.setText(f"⚠ {msg}")

    # ---- Transcript management ----

    def _clear_transcript(self):
        self.transcript_edit.clear()
        self._session_texts.clear()
        self._summary_pending_texts.clear()
        self._current_summary = ""
        self.summary_edit.clear()
        self.summary_status_label.setText("")

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

    def _save_notes(self):
        """Save live notes / summary to a markdown file."""
        text = self.summary_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Save", "No notes to save.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Notes",
            str(Path.home() / "realtime_notes.md"),
            "Markdown (*.md);;Text Files (*.txt);;All Files (*)",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, "Saved", f"Notes saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def cleanup(self):
        """Call on app exit to stop workers."""
        self._stop_mic_preview()
        self._summary_timer.stop()
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        if self._summary_worker and self._summary_worker.isRunning():
            self._summary_worker.wait(3000)

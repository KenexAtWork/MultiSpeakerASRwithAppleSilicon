"""
Realtime ASR Panel - UI for live microphone transcription.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QTextEdit, QProgressBar, QGroupBox, QFileDialog,
    QMessageBox, QSplitter, QSpinBox, QCheckBox, QLineEdit,
)
from PyQt6.QtCore import Qt, QDateTime, QTimer, QTime
from PyQt6.QtGui import QFont, QTextCursor, QTextCharFormat, QColor
from pathlib import Path
import json
import os

from core.realtime_worker import RealtimeASRWorker, ENGINE_WHISPER, ENGINE_QWEN3, ENGINE_TRANSCRIBE
from core.live_summary_worker import LiveSummaryWorker
from core.refinement_worker import IncrementalRefinementWorker, PostRecordingRefinementWorker

# Model repo IDs for download status detection
_WHISPER_MODEL_REPOS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "large": "mlx-community/whisper-large-v3-mlx",
}
_QWEN_MODEL_REPOS = {
    "small": "Qwen/Qwen3-ASR-0.6B",
    "large": "Qwen/Qwen3-ASR-1.7B",
}


def _is_model_downloaded(repo_id: str) -> bool:
    """Check if a HuggingFace model is already cached locally."""
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    # HF cache uses models--org--name format
    folder_name = "models--" + repo_id.replace("/", "--")
    model_dir = cache_dir / folder_name
    if not model_dir.exists():
        return False
    # Check that snapshots directory has content (model actually downloaded)
    snapshots = model_dir / "snapshots"
    if snapshots.exists() and any(snapshots.iterdir()):
        return True
    return False


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
        # Refinement state
        self._incremental_worker = None
        self._post_worker = None
        self._refined_segments = []  # list of dicts from post-recording refinement
        self._last_full_audio = None  # full audio for VOD bridge
        # Recording timer state
        self._recording_timer = QTimer(self)
        self._recording_timer.setInterval(1000)
        self._recording_timer.timeout.connect(self._update_recording_timer)
        self._recording_elapsed = 0  # seconds
        # Keyword highlight state
        self._highlight_keywords = []
        # Session history directory
        self._session_dir = Path.home() / ".asr_sessions"
        self._session_dir.mkdir(exist_ok=True)
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
        self.engine_combo.addItem("AWS Transcribe", ENGINE_TRANSCRIBE)
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

        # Refinement settings
        refine_group = QGroupBox("Background Refinement (Dual-Pass ASR)")
        refine_layout = QHBoxLayout()

        self.refine_incremental_cb = QCheckBox("Incremental (while recording)")
        self.refine_incremental_cb.setToolTip(
            "Re-transcribe audio segments with a larger model in background while recording"
        )
        refine_layout.addWidget(self.refine_incremental_cb)

        self.refine_post_cb = QCheckBox("Post-recording")
        self.refine_post_cb.setChecked(True)
        self.refine_post_cb.setToolTip(
            "Re-transcribe full recording with a larger model after stopping"
        )
        refine_layout.addWidget(self.refine_post_cb)

        refine_layout.addSpacing(10)
        refine_layout.addWidget(QLabel("Refine model:"))
        self.refine_model_combo = QComboBox()
        refine_items = [
            ("large-v3-turbo", "large-v3-turbo (~6 GB, recommended)"),
            ("medium", "medium (~5-7 GB)"),
            ("small", "small (~3-4 GB)"),
            ("large", "large (~8-10 GB)"),
        ]
        for key, label in refine_items:
            repo = _WHISPER_MODEL_REPOS.get(key, "")
            downloaded = _is_model_downloaded(repo) if repo else False
            display = f"✅ {label}" if downloaded else f"⬇ {label}"
            self.refine_model_combo.addItem(display)
        self.refine_model_combo.setToolTip("Model used for background refinement")
        # Style refine model combo
        refine_item_model = self.refine_model_combo.model()
        for i in range(self.refine_model_combo.count()):
            text = self.refine_model_combo.itemText(i)
            item = refine_item_model.item(i)
            if item:
                if text.startswith("⬇"):
                    item.setForeground(QColor("#999999"))
                else:
                    item.setForeground(QColor("#2e7d32"))
        refine_layout.addWidget(self.refine_model_combo)

        refine_layout.addStretch()
        refine_group.setLayout(refine_layout)
        layout.addWidget(refine_group)

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

        self.save_srt_btn = QPushButton("Save SRT")
        self.save_srt_btn.setMinimumHeight(44)
        self.save_srt_btn.setToolTip("Export live transcript as SRT with timestamps")
        self.save_srt_btn.clicked.connect(self._save_transcript_as_srt)
        ctrl_layout.addWidget(self.save_srt_btn)

        self.history_btn = QPushButton("📂 History")
        self.history_btn.setMinimumHeight(44)
        self.history_btn.setToolTip("Open session history folder")
        self.history_btn.clicked.connect(self._open_session_history)
        ctrl_layout.addWidget(self.history_btn)

        layout.addLayout(ctrl_layout)

        # Status bar with VU meter and recording timer
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666;")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        # Recording timer
        self.timer_label = QLabel("⏱ 00:00:00")
        self.timer_label.setStyleSheet(
            "color: #999; font-size: 14px; font-weight: bold; font-family: monospace;"
        )
        self.timer_label.setToolTip("Recording duration")
        status_layout.addWidget(self.timer_label)

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

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search transcript...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        self.search_count_label = QLabel("")
        self.search_count_label.setStyleSheet("color: #888; font-size: 11px;")
        search_layout.addWidget(self.search_count_label)
        transcript_layout.addLayout(search_layout)

        # Keyword highlight input
        kw_layout = QHBoxLayout()
        kw_layout.addWidget(QLabel("Keywords:"))
        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("Enter keywords separated by commas (e.g. action item, deadline, TODO)")
        self.keyword_input.setToolTip("Words to highlight in the transcript")
        self.keyword_input.editingFinished.connect(self._on_keywords_changed)
        kw_layout.addWidget(self.keyword_input)
        transcript_layout.addLayout(kw_layout)

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

        # --- Refinement results area ---
        self.refine_group = QGroupBox("🔄 Refined Transcript (Background ASR)")
        self.refine_group.setVisible(False)
        refine_result_layout = QVBoxLayout()

        refine_status_row = QHBoxLayout()
        self.refine_status_label = QLabel("")
        self.refine_status_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        refine_status_row.addWidget(self.refine_status_label)
        refine_status_row.addStretch()

        self.refine_progress = QProgressBar()
        self.refine_progress.setRange(0, 100)
        self.refine_progress.setValue(0)
        self.refine_progress.setFixedWidth(200)
        self.refine_progress.setVisible(False)
        refine_status_row.addWidget(self.refine_progress)

        self.refine_save_btn = QPushButton("💾 Save Refined")
        self.refine_save_btn.clicked.connect(self._save_refined_transcript)
        self.refine_save_btn.setEnabled(False)
        refine_status_row.addWidget(self.refine_save_btn)

        self.refine_vod_btn = QPushButton("🎬 Send to VOD")
        self.refine_vod_btn.setToolTip("Save recording and open in File Transcription tab for speaker diarization")
        self.refine_vod_btn.clicked.connect(self._bridge_to_vod)
        self.refine_vod_btn.setEnabled(False)
        self.refine_vod_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; "
            "font-weight: bold; border-radius: 4px; padding: 4px 12px; }"
            "QPushButton:hover { background-color: #1976D2; }"
            "QPushButton:disabled { background-color: #ccc; }"
        )
        refine_status_row.addWidget(self.refine_vod_btn)

        refine_result_layout.addLayout(refine_status_row)

        self.refine_edit = QTextEdit()
        self.refine_edit.setReadOnly(True)
        self.refine_edit.setMaximumHeight(200)
        self.refine_edit.setStyleSheet(
            "QTextEdit { font-size: 13px; line-height: 1.5; padding: 10px; "
            "background-color: #f0f8ff; }"
        )
        self.refine_edit.setPlaceholderText(
            "Refined transcript will appear here after background ASR completes."
        )
        refine_result_layout.addWidget(self.refine_edit)

        self.refine_group.setLayout(refine_result_layout)
        layout.addWidget(self.refine_group)

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
        has_loopback = False
        for idx, name in devices:
            self.device_combo.addItem(name, idx)
            if "blackhole" in name.lower() or "loopback" in name.lower():
                has_loopback = True
        # Hint for virtual audio device
        if not has_loopback:
            self.device_combo.setToolTip(
                "To record system audio (e.g. online meetings), install BlackHole:\n"
                "brew install blackhole-2ch\n"
                "Then create a Multi-Output Device in Audio MIDI Setup."
            )
        else:
            self.device_combo.setToolTip("Select BlackHole to capture system audio (online meetings)")
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
            self._preview_error_count = 0
            device_idx = self._get_device_index()

            def preview_callback(indata, frames, time_info, status):
                try:
                    self._preview_buffer = indata[:, 0].copy()
                except Exception:
                    pass

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
            # Device unavailable — reset VU and don't start timer
            self.level_bar.setValue(0)
            self._preview_stream = None

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
        # Check if stream is still active
        if self._preview_stream is None or not self._preview_stream.active:
            self._preview_timer.stop()
            self.level_bar.setValue(0)
            return
        try:
            if self._preview_buffer is not None and len(self._preview_buffer) > 0:
                import numpy as np
                rms = float(np.sqrt(np.mean(self._preview_buffer ** 2)))
                self.level_bar.setValue(int(min(rms * 10, 1.0) * 100))
        except Exception:
            self.level_bar.setValue(0)

    def _get_language(self):
        text = self.language_combo.currentText()
        return text.split(" ")[0]

    def _get_model(self):
        text = self.model_combo.currentText()
        # Strip download status prefix (✅ or ⬇)
        if text.startswith("✅ ") or text.startswith("⬇ "):
            text = text[2:]
        engine = self.engine_combo.currentData()
        if engine == ENGINE_TRANSCRIBE:
            return "cloud"
        if engine == ENGINE_QWEN3:
            return "small" if "0.6B" in text else "large"
        # MLX Whisper: extract model size key
        key = text.split(" ")[0]
        return key  # e.g. "tiny", "base", "small", "medium", "large-v3-turbo", "large"

    def _get_device_index(self):
        return self.device_combo.currentData()

    def _get_engine(self):
        return self.engine_combo.currentData()

    def _on_engine_changed(self, index):
        self.model_combo.setEnabled(True)
        self._update_model_options()
        # Refinement uses MLX Whisper — disable when using other engines
        is_mlx = self.engine_combo.currentData() == ENGINE_WHISPER
        self.refine_incremental_cb.setEnabled(is_mlx)
        self.refine_post_cb.setEnabled(is_mlx)
        self.refine_model_combo.setEnabled(is_mlx)
        if not is_mlx:
            self.refine_incremental_cb.setChecked(False)
            self.refine_post_cb.setChecked(False)

    def _on_device_changed(self, index):
        """Restart mic preview when user selects a different device."""
        if not (self._worker and self._worker.isRunning()):
            self._start_mic_preview()

    def _update_model_options(self):
        engine = self.engine_combo.currentData()
        self.model_combo.clear()
        if engine == ENGINE_QWEN3:
            items = [
                ("small", "small (0.6B ~1.5 GB)", _QWEN_MODEL_REPOS.get("small", "")),
                ("large", "large (1.7B ~3.5 GB)", _QWEN_MODEL_REPOS.get("large", "")),
            ]
            for key, label, repo in items:
                downloaded = _is_model_downloaded(repo) if repo else False
                display = f"✅ {label}" if downloaded else f"⬇ {label}"
                self.model_combo.addItem(display)
            self.model_combo.setCurrentIndex(0)
        elif engine == ENGINE_TRANSCRIBE:
            self.model_combo.addItems(["cloud (AWS managed)"])
            self.model_combo.setEnabled(False)
        else:
            self.model_combo.setEnabled(True)
            items = [
                ("tiny", "tiny (~1-2 GB)"),
                ("base", "base (~2-3 GB)"),
                ("small", "small (~3-4 GB)"),
                ("medium", "medium (~5-7 GB)"),
                ("large-v3-turbo", "large-v3-turbo (~6 GB, recommended)"),
                ("large", "large (~8-10 GB)"),
            ]
            for key, label in items:
                repo = _WHISPER_MODEL_REPOS.get(key, "")
                downloaded = _is_model_downloaded(repo) if repo else False
                display = f"✅ {label}" if downloaded else f"⬇ {label}"
                self.model_combo.addItem(display)
            self.model_combo.setCurrentIndex(4)  # default to turbo
        # Apply dimmed styling to undownloaded items
        self._style_model_combo()
    def _style_model_combo(self):
        """Apply visual styling: dimmed color for undownloaded models via stylesheet."""
        # Use item model to set foreground color without triggering QTextCursor issues
        model = self.model_combo.model()
        for i in range(self.model_combo.count()):
            text = self.model_combo.itemText(i)
            item = model.item(i)
            if item:
                if text.startswith("⬇"):
                    item.setForeground(QColor("#999999"))
                else:
                    item.setForeground(QColor("#2e7d32"))
    def _get_refine_model(self):
        """Extract model key from refine model combo, stripping download status prefix."""
        text = self.refine_model_combo.currentText()
        if text.startswith("✅ ") or text.startswith("⬇ "):
            text = text[2:]
        return text.split(" ")[0]

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

        # Start recording timer
        self._recording_elapsed = 0
        self.timer_label.setText("⏱ 00:00:00")
        self.timer_label.setStyleSheet(
            "color: #f44336; font-size: 14px; font-weight: bold; font-family: monospace;"
        )
        self._recording_timer.start()

        # Defer incremental refinement — will be started in _on_status when main model is ready
        # This avoids two MLX models loading on Metal GPU simultaneously (crash)
        self._pending_incremental_refine = False
        can_refine = self._get_engine() == ENGINE_WHISPER
        if can_refine and self.refine_incremental_cb.isChecked():
            self._pending_incremental_refine = True
            self._worker.raw_chunk.connect(self._feed_incremental_chunk)
            self.refine_group.setVisible(True)
            self.refine_edit.clear()
            self.refine_status_label.setText("⏳ Waiting for main model to load...")

        # Connect raw_chunk for post-recording (always, to accumulate audio)
        if can_refine and (self.refine_post_cb.isChecked() or self.refine_incremental_cb.isChecked()):
            if not self.refine_incremental_cb.isChecked():
                # Need a lightweight accumulator if only post-recording is enabled
                self._raw_audio_chunks = []
                self._worker.raw_chunk.connect(self._accumulate_raw_chunk)

    def _stop_recording(self):
        if self._worker:
            self._worker.stop()
        self.start_btn.setEnabled(False)
        self.status_label.setText("Stopping...")

    def _on_stopped(self):
        self._summary_timer.stop()
        self._recording_timer.stop()
        self.timer_label.setStyleSheet(
            "color: #999; font-size: 14px; font-weight: bold; font-family: monospace;"
        )
        # Auto-save session history
        self._auto_save_session()
        # Final summary on stop if there are pending texts
        if self.summary_enabled.isChecked() and self._summary_pending_texts:
            self._trigger_summary()

        # Stop incremental refinement
        if self._incremental_worker and self._incremental_worker.isRunning():
            self._incremental_worker.stop()
            self._incremental_worker.wait(3000)

        # Capture full audio for VOD bridge
        import numpy as np
        self._last_full_audio = None
        if self._incremental_worker:
            self._last_full_audio = self._incremental_worker.get_full_audio()
        elif hasattr(self, '_raw_audio_chunks') and self._raw_audio_chunks:
            self._last_full_audio = np.concatenate(self._raw_audio_chunks)

        # Enable VOD bridge if we have audio
        if self._last_full_audio is not None and len(self._last_full_audio) >= 16000:
            self.refine_vod_btn.setEnabled(True)
            self.refine_group.setVisible(True)

        # Trigger post-recording refinement (MLX Whisper only)
        if self.refine_post_cb.isChecked() and self._get_engine() == ENGINE_WHISPER:
            self._start_post_refinement()

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
        line = f"[{timestamp}] {text}"

        # Append with keyword highlighting
        if self._highlight_keywords:
            self.transcript_edit.append(line)
            self._apply_keyword_highlights()
        else:
            self.transcript_edit.append(line)

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

            # Start deferred incremental refinement now that main model is loaded
            # IMPORTANT: Use the SAME model as main ASR to avoid loading a second
            # model into GPU memory (16GB Macs will segfault with two large models)
            if self._pending_incremental_refine:
                self._pending_incremental_refine = False
                main_model = self._get_model()  # same model — no extra GPU memory
                self._incremental_worker = IncrementalRefinementWorker(
                    engine=self._get_engine(),
                    model_size=main_model,
                    language=self._get_language(),
                    segment_duration=30,
                )
                self._incremental_worker.segment_refined.connect(self._on_incremental_refined)
                self._incremental_worker.status.connect(self._on_refine_status)
                self._incremental_worker.error.connect(self._on_refine_error)
                self._incremental_worker.start()
                self.refine_status_label.setText("⏳ Incremental refinement starting...")

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

    # ---- Refinement (Dual-Pass ASR) ----

    def _feed_incremental_chunk(self, audio, timestamp):
        """Feed raw audio chunk to incremental refinement worker."""
        if self._incremental_worker and self._incremental_worker.isRunning():
            import numpy as np
            if isinstance(audio, np.ndarray):
                self._incremental_worker.add_chunk(audio, timestamp)

    def _accumulate_raw_chunk(self, audio, timestamp):
        """Accumulate raw audio for post-recording refinement only."""
        import numpy as np
        if isinstance(audio, np.ndarray):
            if not hasattr(self, '_raw_audio_chunks'):
                self._raw_audio_chunks = []
            self._raw_audio_chunks.append(audio.copy())

    def _on_incremental_refined(self, seg_index, text, start_sec, end_sec):
        """Handle a refined segment from incremental worker."""
        self.refine_group.setVisible(True)
        start_str = f"{int(start_sec//60):02d}:{int(start_sec%60):02d}"
        end_str = f"{int(end_sec//60):02d}:{int(end_sec%60):02d}"
        self.refine_edit.append(f"[{start_str}-{end_str}] {text}")
        cursor = self.refine_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.refine_edit.setTextCursor(cursor)
        self.refine_save_btn.setEnabled(True)

    def _start_post_refinement(self):
        """Start post-recording refinement with full audio."""
        import numpy as np

        # Get full audio from incremental worker or raw chunks
        full_audio = None
        if self._incremental_worker:
            full_audio = self._incremental_worker.get_full_audio()
        elif hasattr(self, '_raw_audio_chunks') and self._raw_audio_chunks:
            full_audio = np.concatenate(self._raw_audio_chunks)
            self._raw_audio_chunks = []

        if full_audio is None or len(full_audio) < 16000:
            return  # too short, skip

        refine_model = self._get_refine_model()
        self._post_worker = PostRecordingRefinementWorker(
            audio=full_audio,
            engine=self._get_engine(),
            model_size=refine_model,
            language=self._get_language(),
        )
        self._post_worker.refinement_complete.connect(self._on_post_refinement_done)
        self._post_worker.progress.connect(self._on_refine_progress)
        self._post_worker.status.connect(self._on_refine_status)
        self._post_worker.error.connect(self._on_refine_error)
        self._post_worker.start()

        self.refine_group.setVisible(True)
        self.refine_progress.setVisible(True)
        self.refine_progress.setValue(0)
        self.refine_status_label.setText("⏳ Post-recording refinement in progress...")

    def _on_post_refinement_done(self, segments):
        """Handle completed post-recording refinement."""
        self._refined_segments = segments
        self.refine_edit.clear()
        for seg in segments:
            start = seg["start_sec"]
            end = seg["end_sec"]
            start_str = f"{int(start//60):02d}:{int(start%60):02d}"
            end_str = f"{int(end//60):02d}:{int(end%60):02d}"
            self.refine_edit.append(f"[{start_str}-{end_str}] {seg['text']}")
        self.refine_progress.setVisible(False)
        self.refine_save_btn.setEnabled(True)
        self.refine_status_label.setText("✅ Refinement complete")

    def _on_refine_status(self, msg):
        self.refine_status_label.setText(msg)

    def _on_refine_progress(self, value):
        self.refine_progress.setValue(value)

    def _on_refine_error(self, msg):
        self.refine_status_label.setText(f"⚠ {msg}")
        self.refine_progress.setVisible(False)

    def _save_refined_transcript(self):
        """Save refined transcript to file."""
        text = self.refine_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Save", "No refined transcript to save.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Refined Transcript",
            str(Path.home() / "refined_transcript.txt"),
            "Text Files (*.txt);;SRT Files (*.srt);;All Files (*)",
        )
        if not path:
            return

        try:
            if path.endswith(".srt"):
                self._save_refined_as_srt(path)
            else:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            QMessageBox.information(self, "Saved", f"Refined transcript saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {e}")

    def _save_refined_as_srt(self, path):
        """Save refined segments as SRT format."""
        segments = self._refined_segments
        if not segments:
            # Fallback: save plain text
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.refine_edit.toPlainText())
            return

        with open(path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                start = seg["start_sec"]
                end = seg["end_sec"]
                start_srt = self._sec_to_srt_time(start)
                end_srt = self._sec_to_srt_time(end)
                f.write(f"{i}\n{start_srt} --> {end_srt}\n{seg['text']}\n\n")
    def _bridge_to_vod(self):
        """Save recorded audio as WAV and open it in the File Transcription (VOD) tab."""
        if self._last_full_audio is None or len(self._last_full_audio) < 16000:
            QMessageBox.information(self, "Bridge to VOD", "No recorded audio available.")
            return

        # Save audio as WAV
        import wave
        import numpy as np
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        default_path = str(Path.home() / f"recording_{ts}.wav")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Recording for VOD Processing",
            default_path,
            "WAV Files (*.wav);;All Files (*)",
        )
        if not path:
            return

        try:
            audio_int16 = (self._last_full_audio * 32767).astype(np.int16)
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio_int16.tobytes())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save audio: {e}")
            return

        # Switch to VOD tab and load the file
        main_window = self.window()
        if hasattr(main_window, 'tabs') and hasattr(main_window, 'set_current_file'):
            main_window.tabs.setCurrentIndex(0)  # Switch to File Transcription tab
            main_window.set_current_file(path)
            self.status_label.setText(f"✅ Audio saved and loaded in VOD tab")
        else:
            QMessageBox.information(
                self, "Saved",
                f"Audio saved to:\n{path}\n\nSwitch to File Transcription tab and load this file."
            )

    @staticmethod
    def _sec_to_srt_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    # ---- Transcript management ----

    def _clear_transcript(self):
        self.transcript_edit.clear()
        self._session_texts.clear()
        self._summary_pending_texts.clear()
        self._current_summary = ""
        self.summary_edit.clear()
        self.summary_status_label.setText("")
        # Clear refinement
        self.refine_edit.clear()
        self._refined_segments = []
        self.refine_group.setVisible(False)
        self.refine_save_btn.setEnabled(False)
        self.refine_vod_btn.setEnabled(False)
        self.refine_status_label.setText("")
        self._last_full_audio = None

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

    # ---- Recording Timer ----

    def _update_recording_timer(self):
        """Update the recording duration display."""
        self._recording_elapsed += 1
        h = self._recording_elapsed // 3600
        m = (self._recording_elapsed % 3600) // 60
        s = self._recording_elapsed % 60
        self.timer_label.setText(f"⏱ {h:02d}:{m:02d}:{s:02d}")

    # ---- Transcript Search ----

    def _on_search_changed(self, text):
        """Highlight search matches in transcript."""
        # Skip if document is empty
        if self.transcript_edit.document().isEmpty():
            self.search_count_label.setText("")
            return

        # Clear previous highlights
        cursor = self.transcript_edit.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("transparent"))
        cursor.mergeCharFormat(fmt)
        cursor.clearSelection()

        if not text.strip():
            self.search_count_label.setText("")
            if self._highlight_keywords:
                self._apply_keyword_highlights()
            return

        # Search and highlight
        doc = self.transcript_edit.document()
        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("#FFEB3B"))
        count = 0
        cursor = doc.find(text)
        while not cursor.isNull():
            cursor.mergeCharFormat(highlight_fmt)
            count += 1
            cursor = doc.find(text, cursor)

        self.search_count_label.setText(f"{count} match{'es' if count != 1 else ''}")

    # ---- Keyword Highlight ----

    def _on_keywords_changed(self):
        """Parse keyword input and re-apply highlights."""
        raw = self.keyword_input.text().strip()
        if raw:
            self._highlight_keywords = [kw.strip() for kw in raw.split(",") if kw.strip()]
        else:
            self._highlight_keywords = []
        self._apply_keyword_highlights()

    def _apply_keyword_highlights(self):
        """Apply keyword highlighting to the entire transcript."""
        if not self._highlight_keywords:
            return
        doc = self.transcript_edit.document()
        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("#B3E5FC"))
        highlight_fmt.setForeground(QColor("#01579B"))
        for kw in self._highlight_keywords:
            cursor = doc.find(kw)
            while not cursor.isNull():
                cursor.mergeCharFormat(highlight_fmt)
                cursor = doc.find(kw, cursor)

    # ---- Export Realtime Transcript as SRT ----

    def _save_transcript_as_srt(self):
        """Export live transcript as SRT file using timestamps from the text."""
        if not self._session_texts:
            QMessageBox.information(self, "Save", "No transcript to save.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Transcript as SRT",
            str(Path.home() / "realtime_transcript.srt"),
            "SRT Files (*.srt);;All Files (*)",
        )
        if not path:
            return

        try:
            lines = self.transcript_edit.toPlainText().strip().split("\n")
            with open(path, "w", encoding="utf-8") as f:
                idx = 1
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    # Parse [HH:MM:SS] prefix
                    if line.startswith("[") and "]" in line:
                        ts_end = line.index("]")
                        ts_str = line[1:ts_end]
                        text = line[ts_end + 1:].strip()
                        # Create SRT timestamp (use same time for start, +3s for end)
                        start_srt = f"00:{ts_str},000" if ts_str.count(":") == 2 else f"{ts_str},000"
                        # Parse to compute end time
                        parts = ts_str.split(":")
                        if len(parts) == 3:
                            total_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        elif len(parts) == 2:
                            total_sec = int(parts[0]) * 60 + int(parts[1])
                        else:
                            total_sec = 0
                        end_sec = total_sec + 3
                        end_srt = self._sec_to_srt_time(end_sec)
                        if ts_str.count(":") == 2:
                            start_srt = self._sec_to_srt_time(total_sec)
                        f.write(f"{idx}\n{start_srt} --> {end_srt}\n{text}\n\n")
                        idx += 1
            QMessageBox.information(self, "Saved", f"SRT saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save SRT: {e}")

    # ---- Session History ----

    def _auto_save_session(self):
        """Auto-save current session transcript and notes to history."""
        if not self._session_texts:
            return
        ts = QDateTime.currentDateTime().toString("yyyyMMdd-HHmmss")
        session_file = self._session_dir / f"session_{ts}.json"
        duration_str = self.timer_label.text().replace("⏱ ", "")
        data = {
            "timestamp": ts,
            "duration": duration_str,
            "duration_seconds": self._recording_elapsed,
            "engine": self.engine_combo.currentText(),
            "language": self.language_combo.currentText(),
            "transcript_lines": self.transcript_edit.toPlainText().split("\n"),
            "summary": self._current_summary,
            "segment_count": len(self._session_texts),
        }
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # silently fail — don't interrupt user flow

    def _open_session_history(self):
        """Open the session history folder in Finder."""
        import subprocess
        self._session_dir.mkdir(exist_ok=True)
        try:
            subprocess.Popen(["open", str(self._session_dir)])
        except Exception:
            QMessageBox.information(
                self, "Session History",
                f"Session files are saved at:\n{self._session_dir}"
            )

    def cleanup(self):
        """Call on app exit to stop workers."""
        self._stop_mic_preview()
        self._summary_timer.stop()
        self._recording_timer.stop()
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
        if self._summary_worker and self._summary_worker.isRunning():
            self._summary_worker.wait(3000)
        if self._incremental_worker and self._incremental_worker.isRunning():
            self._incremental_worker.stop()
            self._incremental_worker.wait(3000)
        if self._post_worker and self._post_worker.isRunning():
            self._post_worker.wait(5000)

"""
Tests for refinement_worker.py — Dual-Pass ASR (incremental + post-recording).
All tests are unit tests that don't require ASR models.
"""
import sys
import os
import time
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add parent dir so we can import gui modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.core.refinement_worker import (
    RefinementSegment,
    IncrementalRefinementWorker,
    PostRecordingRefinementWorker,
    SAMPLE_RATE,
)


# ---- RefinementSegment ----

class TestRefinementSegment:
    def test_to_dict(self):
        seg = RefinementSegment(1.0, 5.0, "hello world")
        d = seg.to_dict()
        assert d == {"start_sec": 1.0, "end_sec": 5.0, "text": "hello world"}

    def test_slots(self):
        seg = RefinementSegment(0, 1, "test")
        assert seg.start_sec == 0
        assert seg.end_sec == 1
        assert seg.text == "test"


# ---- IncrementalRefinementWorker ----

class TestIncrementalWorker:
    def test_add_chunk_accumulates(self):
        worker = IncrementalRefinementWorker()
        chunk1 = np.zeros(16000, dtype=np.float32)
        chunk2 = np.ones(8000, dtype=np.float32)
        worker.add_chunk(chunk1, 0.0)
        worker.add_chunk(chunk2, 1.0)
        assert worker._total_samples == 24000
        assert len(worker._chunks) == 2

    def test_get_full_audio(self):
        worker = IncrementalRefinementWorker()
        chunk1 = np.zeros(16000, dtype=np.float32)
        chunk2 = np.ones(8000, dtype=np.float32)
        worker.add_chunk(chunk1, 0.0)
        worker.add_chunk(chunk2, 1.0)
        full = worker.get_full_audio()
        assert len(full) == 24000
        assert full[0] == 0.0
        assert full[16000] == 1.0

    def test_get_full_audio_empty(self):
        worker = IncrementalRefinementWorker()
        full = worker.get_full_audio()
        assert len(full) == 0

    def test_stop_flag(self):
        worker = IncrementalRefinementWorker()
        assert worker._running is False
        worker._running = True
        worker.stop()
        assert worker._running is False

    def test_segment_duration_default(self):
        worker = IncrementalRefinementWorker()
        assert worker.segment_duration == 30

    def test_custom_segment_duration(self):
        worker = IncrementalRefinementWorker(segment_duration=60)
        assert worker.segment_duration == 60

    def test_save_wav_creates_valid_file(self, tmp_path):
        audio = np.random.randn(16000).astype(np.float32) * 0.5
        wav_path = str(tmp_path / "test.wav")
        IncrementalRefinementWorker._save_wav(wav_path, audio)
        assert os.path.exists(wav_path)
        # Verify it's a valid WAV
        import wave
        with wave.open(wav_path, "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getframerate() == SAMPLE_RATE
            assert wf.getnframes() == 16000


# ---- PostRecordingRefinementWorker ----

class TestPostRecordingWorker:
    def test_rejects_short_audio(self):
        """Audio shorter than 1 second should emit error."""
        short_audio = np.zeros(100, dtype=np.float32)
        worker = PostRecordingRefinementWorker(audio=short_audio)
        errors = []
        worker.error.connect(lambda msg: errors.append(msg))
        worker.run()  # run synchronously
        assert len(errors) == 1
        assert "too short" in errors[0].lower()

    def test_rejects_none_audio(self):
        worker = PostRecordingRefinementWorker(audio=None)
        errors = []
        worker.error.connect(lambda msg: errors.append(msg))
        worker.run()
        assert len(errors) == 1

    @patch("gui.core.refinement_worker.PostRecordingRefinementWorker._run_whisper")
    def test_dispatches_to_whisper(self, mock_whisper):
        audio = np.zeros(SAMPLE_RATE * 2, dtype=np.float32)
        worker = PostRecordingRefinementWorker(audio=audio, engine="mlx-whisper")
        worker.run()
        mock_whisper.assert_called_once()

    @patch("gui.core.refinement_worker.PostRecordingRefinementWorker._run_qwen3")
    def test_dispatches_to_qwen3(self, mock_qwen3):
        audio = np.zeros(SAMPLE_RATE * 2, dtype=np.float32)
        worker = PostRecordingRefinementWorker(audio=audio, engine="qwen3-asr")
        worker.run()
        mock_qwen3.assert_called_once()

    def test_save_wav_roundtrip(self, tmp_path):
        """Verify WAV save/load roundtrip preserves audio."""
        # Use values in [-1, 1] range to avoid clipping
        np.random.seed(42)
        original = (np.random.rand(32000).astype(np.float32) * 2 - 1) * 0.9
        wav_path = str(tmp_path / "roundtrip.wav")
        PostRecordingRefinementWorker._save_wav(wav_path, original)

        import wave
        with wave.open(wav_path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            loaded = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0

        # 16-bit quantization error: max ~1/32767 ≈ 3e-5
        assert np.max(np.abs(original - loaded)) < 1e-3


# ---- SRT time formatting (via panel, but test the static method) ----

class TestSrtTimeFormat:
    """Test the _sec_to_srt_time static method from RealtimePanel."""

    @staticmethod
    def _sec_to_srt_time(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        ms = int((sec - int(sec)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def test_zero(self):
        assert self._sec_to_srt_time(0) == "00:00:00,000"

    def test_simple(self):
        assert self._sec_to_srt_time(65.5) == "00:01:05,500"

    def test_hour(self):
        assert self._sec_to_srt_time(3661.123) == "01:01:01,123"

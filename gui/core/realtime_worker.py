"""
Realtime ASR Worker - Captures microphone audio and transcribes in real-time
using MLX Whisper with a sliding window approach.
"""
import os
import sys
import time
import tempfile
import threading
import numpy as np
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

# Audio config
SAMPLE_RATE = 16000
CHANNELS = 1
MIN_CHUNK_DURATION = 3    # minimum seconds before considering transcription
MAX_CHUNK_DURATION = 10   # force transcribe after this many seconds
SILENCE_SPLIT_DURATION = 0.6  # seconds of silence at tail to trigger split
SILENCE_THRESHOLD = 0.01  # RMS threshold for silence detection


class RealtimeASRWorker(QThread):
    """Captures mic audio and runs MLX Whisper transcription in near real-time."""

    transcript_update = pyqtSignal(str)  # new transcribed text segment
    status_changed = pyqtSignal(str)     # status message
    error = pyqtSignal(str)
    level_update = pyqtSignal(float)     # audio level 0.0-1.0 for VU meter
    stopped = pyqtSignal()

    def __init__(self, language="auto", model_size="base", device_index=None):
        super().__init__()
        self.language = language
        self.model_size = model_size
        self.device_index = device_index
        self._running = False
        self._paused = False
        self._lock = threading.Lock()
        self._prev_text = ""  # for dedup across chunks

    def stop(self):
        self._running = False

    def pause(self):
        self._paused = True
        self.status_changed.emit("Paused")

    def resume(self):
        self._paused = False
        self.status_changed.emit("Listening...")

    @property
    def is_paused(self):
        return self._paused

    def run(self):
        try:
            import sounddevice as sd
        except ImportError:
            self.error.emit(
                "sounddevice not installed.\n"
                "Run: uv pip install sounddevice"
            )
            return

        try:
            import mlx_whisper
        except ImportError:
            self.error.emit("mlx_whisper not installed.")
            return

        self._running = True
        self._paused = False
        self.status_changed.emit("Loading model...")

        # Load model once
        model_name = f"mlx-community/whisper-{self.model_size}-mlx"
        lang_arg = None if self.language == "auto" else self.language

        # Warm up model with a tiny silent audio
        try:
            dummy = np.zeros(SAMPLE_RATE, dtype=np.float32)
            _warmup_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            _warmup_path = _warmup_tmp.name
            _warmup_tmp.close()
            self._save_wav(_warmup_path, dummy)
            mlx_whisper.transcribe(
                _warmup_path,
                path_or_hf_repo=model_name,
                language=lang_arg,
            )
            os.unlink(_warmup_path)
        except Exception as e:
            self.error.emit(f"Failed to load model: {e}")
            return

        self.status_changed.emit("Listening...")

        # Audio buffer — use VAD-based chunking instead of fixed window
        audio_buffer = np.array([], dtype=np.float32)
        min_chunk_samples = int(MIN_CHUNK_DURATION * SAMPLE_RATE)
        max_chunk_samples = int(MAX_CHUNK_DURATION * SAMPLE_RATE)
        silence_samples = int(SILENCE_SPLIT_DURATION * SAMPLE_RATE)

        def audio_callback(indata, frames, time_info, status):
            if status:
                pass  # ignore overflow warnings
            if not self._paused:
                nonlocal audio_buffer
                with self._lock:
                    audio_buffer = np.append(audio_buffer, indata[:, 0])

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                blocksize=int(SAMPLE_RATE * 0.1),  # 100ms blocks
                device=self.device_index,
                callback=audio_callback,
            )
            stream.start()
        except Exception as e:
            self.error.emit(f"Microphone error: {e}")
            return

        tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp_wav.name
        tmp_wav.close()

        try:
            while self._running:
                time.sleep(0.1)

                # Emit audio level
                with self._lock:
                    if len(audio_buffer) > 0:
                        rms = float(np.sqrt(np.mean(audio_buffer[-1600:] ** 2)))
                        self.level_update.emit(min(rms * 10, 1.0))

                with self._lock:
                    buf_len = len(audio_buffer)

                # Need at least minimum chunk
                if buf_len < min_chunk_samples:
                    continue

                # Decide when to transcribe:
                # 1) If we hit max duration, force transcribe
                # 2) If we have enough audio AND detect a silence gap at the tail
                should_transcribe = False
                if buf_len >= max_chunk_samples:
                    should_transcribe = True
                elif buf_len >= min_chunk_samples:
                    # Check if tail is silent (natural pause = good split point)
                    with self._lock:
                        tail = audio_buffer[-silence_samples:]
                    tail_rms = float(np.sqrt(np.mean(tail ** 2)))
                    if tail_rms < SILENCE_THRESHOLD:
                        should_transcribe = True

                if not should_transcribe:
                    continue

                # Extract chunk
                with self._lock:
                    chunk = audio_buffer.copy()
                    audio_buffer = np.array([], dtype=np.float32)

                # Skip if entire chunk is mostly silence
                rms = float(np.sqrt(np.mean(chunk ** 2)))
                if rms < SILENCE_THRESHOLD:
                    continue

                # Transcribe
                self._save_wav(tmp_path, chunk)
                try:
                    result = mlx_whisper.transcribe(
                        tmp_path,
                        path_or_hf_repo=model_name,
                        language=lang_arg,
                        condition_on_previous_text=False,  # reduce hallucination carry-over
                        compression_ratio_threshold=2.0,   # tighter filter for garbage output
                        no_speech_threshold=0.5,           # skip segments Whisper thinks are not speech
                    )
                    text = result.get("text", "").strip()
                    if text and not self._is_hallucination(text):
                        self.transcript_update.emit(text)
                        self._prev_text = text
                except Exception as e:
                    self.status_changed.emit(f"Transcription error: {e}")

        finally:
            stream.stop()
            stream.close()
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            self.status_changed.emit("Stopped")
            self.stopped.emit()

    def _is_hallucination(self, text):
        """Detect and filter common Whisper hallucination patterns."""
        # 1. Repetition detection: if any 3+ char substring repeats 5+ times
        if len(text) > 30:
            for length in range(3, 10):
                for i in range(len(text) - length):
                    pattern = text[i:i + length]
                    if text.count(pattern) >= 5:
                        return True

        # 2. Exact duplicate of previous chunk
        if text == self._prev_text:
            return True

        # 3. Common Whisper hallucination phrases (appears on silence/noise)
        hallucination_phrases = [
            "thank you for watching",
            "thanks for watching",
            "please subscribe",
            "like and subscribe",
            "see you next time",
            "see you in the next",
            "bye bye",
            "字幕由",
            "字幕提供",
            "請不吝點讚訂閱",
            "謝謝觀看",
        ]
        text_lower = text.lower().strip()
        for phrase in hallucination_phrases:
            if text_lower == phrase or text_lower.startswith(phrase):
                return True

        # 4. Very short meaningless output (single repeated char)
        if len(set(text.replace(" ", ""))) <= 2 and len(text) > 5:
            return True

        return False

    @staticmethod
    def _save_wav(path, audio_data):
        """Save float32 numpy array as 16-bit WAV."""
        import wave
        audio_int16 = (audio_data * 32767).astype(np.int16)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

    @staticmethod
    def list_audio_devices():
        """Return list of available input devices."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            inputs = []
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0:
                    inputs.append((i, d["name"]))
            return inputs
        except ImportError:
            return []

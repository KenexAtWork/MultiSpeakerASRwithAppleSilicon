"""
Realtime ASR Worker - Captures microphone audio and transcribes in real-time.
Supports two engines:
  - mlx-whisper (Apple Silicon optimized, lightweight)
  - qwen3-asr (Qwen3-ASR via transformers, higher accuracy)
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
SILENCE_SPLIT_DURATION = 0.4  # seconds of silence at tail to trigger split
SILENCE_THRESHOLD = 0.01  # RMS threshold for silence detection

# Engine constants
ENGINE_WHISPER = "mlx-whisper"
ENGINE_QWEN3 = "qwen3-asr"

# Qwen3-ASR language name mapping (Qwen uses full names)
QWEN3_LANG_MAP = {
    "zh": "Chinese", "en": "English", "ja": "Japanese",
    "ko": "Korean", "fr": "French", "de": "German",
    "es": "Spanish", "pt": "Portuguese", "it": "Italian",
    "ru": "Russian", "ar": "Arabic", "th": "Thai",
    "vi": "Vietnamese", "id": "Indonesian", "nl": "Dutch",
    "auto": None,
}


class RealtimeASRWorker(QThread):
    """Captures mic audio and transcribes using selected engine."""

    transcript_update = pyqtSignal(str)  # new transcribed text segment
    status_changed = pyqtSignal(str)     # status message
    error = pyqtSignal(str)
    level_update = pyqtSignal(float)     # audio level 0.0-1.0 for VU meter
    raw_chunk = pyqtSignal(object, float)  # (np.ndarray, timestamp_sec) for refinement
    stopped = pyqtSignal()

    def __init__(self, language="auto", model_size="base",
                 device_index=None, engine=ENGINE_WHISPER):
        super().__init__()
        self.language = language
        self.model_size = model_size
        self.device_index = device_index
        self.engine = engine
        self._running = False
        self._paused = False
        self._lock = threading.Lock()
        self._prev_text = ""

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

        self._running = True
        self._paused = False

        # --- Load engine ---
        if self.engine == ENGINE_QWEN3:
            transcribe_fn = self._init_qwen3()
        else:
            transcribe_fn = self._init_whisper()

        if transcribe_fn is None:
            return  # error already emitted

        self.status_changed.emit("Listening...")

        # --- Audio capture loop ---
        _start_time = time.time()
        audio_buffer = np.array([], dtype=np.float32)
        min_chunk_samples = int(MIN_CHUNK_DURATION * SAMPLE_RATE)
        max_chunk_samples = int(MAX_CHUNK_DURATION * SAMPLE_RATE)
        silence_samples = int(SILENCE_SPLIT_DURATION * SAMPLE_RATE)

        def audio_callback(indata, frames, time_info, status):
            if not self._paused:
                nonlocal audio_buffer
                with self._lock:
                    audio_buffer = np.append(audio_buffer, indata[:, 0])

        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="float32",
                blocksize=int(SAMPLE_RATE * 0.1),
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

                if buf_len < min_chunk_samples:
                    continue

                # VAD-based split decision
                should_transcribe = False
                if buf_len >= max_chunk_samples:
                    should_transcribe = True
                elif buf_len >= min_chunk_samples:
                    with self._lock:
                        tail = audio_buffer[-silence_samples:]
                    tail_rms = float(np.sqrt(np.mean(tail ** 2)))
                    if tail_rms < SILENCE_THRESHOLD:
                        should_transcribe = True

                if not should_transcribe:
                    continue

                with self._lock:
                    chunk = audio_buffer.copy()
                    audio_buffer = np.array([], dtype=np.float32)

                rms = float(np.sqrt(np.mean(chunk ** 2)))
                if rms < SILENCE_THRESHOLD:
                    continue

                # Emit raw chunk for refinement worker (before transcription)
                chunk_time = time.time() - _start_time
                self.raw_chunk.emit(chunk, chunk_time)

                # Transcribe using selected engine
                self._save_wav(tmp_path, chunk)
                try:
                    text = transcribe_fn(tmp_path, chunk)
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

    # ---- Engine initializers ----

    def _init_whisper(self):
        """Initialize MLX Whisper and return a transcribe function."""
        try:
            import mlx_whisper
        except ImportError:
            self.error.emit("mlx_whisper not installed.")
            return None

        self.status_changed.emit("Loading MLX Whisper model...")
        model_name = f"mlx-community/whisper-{self.model_size}-mlx"
        lang_arg = None if self.language == "auto" else self.language

        # Warm up
        try:
            dummy = np.zeros(SAMPLE_RATE, dtype=np.float32)
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp_path = tmp.name
            tmp.close()
            self._save_wav(tmp_path, dummy)
            mlx_whisper.transcribe(tmp_path, path_or_hf_repo=model_name, language=lang_arg)
            os.unlink(tmp_path)
        except Exception as e:
            self.error.emit(f"Failed to load MLX Whisper: {e}")
            return None

        def transcribe_fn(wav_path, chunk_array):
            result = mlx_whisper.transcribe(
                wav_path,
                path_or_hf_repo=model_name,
                language=lang_arg,
                condition_on_previous_text=False,
                compression_ratio_threshold=2.0,
                no_speech_threshold=0.5,
            )
            return result.get("text", "").strip()

        return transcribe_fn

    def _init_qwen3(self):
        """Initialize Qwen3-ASR and return a transcribe function."""
        try:
            import torch
            from qwen_asr import Qwen3ASRModel
        except ImportError:
            self.error.emit(
                "qwen-asr not installed.\n"
                "Run: uv pip install qwen-asr"
            )
            return None

        # Suppress repetitive "Setting pad_token_id to eos_token_id" warnings
        import logging
        logging.getLogger("transformers").setLevel(logging.ERROR)

        self.status_changed.emit("Loading Qwen3-ASR model (first load downloads ~3.5 GB)...")

        # Pick model variant based on model_size hint
        if self.model_size in ("tiny", "base", "small"):
            qwen_model = "Qwen/Qwen3-ASR-0.6B"
        else:
            qwen_model = "Qwen/Qwen3-ASR-1.7B"

        # Determine device
        if torch.backends.mps.is_available():
            device = "mps"
            dtype = torch.float16
        elif torch.cuda.is_available():
            device = "cuda:0"
            dtype = torch.bfloat16
        else:
            device = "cpu"
            dtype = torch.float32

        try:
            model = Qwen3ASRModel.from_pretrained(
                qwen_model,
                dtype=dtype,
                device_map=device,
                max_new_tokens=256,
            )
        except Exception as e:
            self.error.emit(f"Failed to load Qwen3-ASR: {e}")
            return None

        lang_name = QWEN3_LANG_MAP.get(self.language)

        # Simplified → Traditional Chinese converter (optional)
        s2t_converter = None
        if self.language in ("zh", "auto"):
            try:
                from opencc import OpenCC
                s2t_converter = OpenCC("s2t")
            except ImportError:
                pass  # opencc not installed, output stays simplified

        def transcribe_fn(wav_path, chunk_array):
            # Qwen3-ASR accepts (np.ndarray, sample_rate) tuple
            results = model.transcribe(
                audio=[(chunk_array, SAMPLE_RATE)],
                language=[lang_name] if lang_name else None,
            )
            if results and results[0].text:
                text = results[0].text.strip()
                if s2t_converter and text:
                    text = s2t_converter.convert(text)
                return text
            return ""

        return transcribe_fn

    # ---- Hallucination filter ----

    def _is_hallucination(self, text):
        """Detect and filter common hallucination patterns."""
        # 1. Repetition detection
        if len(text) > 30:
            for length in range(3, 10):
                for i in range(len(text) - length):
                    pattern = text[i:i + length]
                    if text.count(pattern) >= 5:
                        return True

        # 2. Exact duplicate of previous chunk
        if text == self._prev_text:
            return True

        # 3. Common phantom phrases
        hallucination_phrases = [
            "thank you for watching", "thanks for watching",
            "please subscribe", "like and subscribe",
            "see you next time", "see you in the next", "bye bye",
            "字幕由", "字幕提供", "請不吝點讚訂閱", "謝謝觀看",
        ]
        text_lower = text.lower().strip()
        for phrase in hallucination_phrases:
            if text_lower == phrase or text_lower.startswith(phrase):
                return True

        # 4. Single repeated char spam
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

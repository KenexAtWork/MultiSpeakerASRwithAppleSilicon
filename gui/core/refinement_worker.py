"""
Refinement Worker - Background batch ASR to improve live transcription quality.

Two modes:
  1. Incremental: While live ASR runs, periodically re-transcribe accumulated
     audio segments with a larger model and replace live results.
  2. Post-recording: After live ASR stops, re-transcribe the full recording
     with a larger model for a high-quality final version.

Both modes skip pyannote diarization for speed.
"""
import os
import sys
import time
import tempfile
import numpy as np
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

SAMPLE_RATE = 16000


class RefinementSegment:
    """A segment of refined transcription with timing info."""
    __slots__ = ("start_sec", "end_sec", "text")

    def __init__(self, start_sec: float, end_sec: float, text: str):
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.text = text

    def to_dict(self):
        return {"start_sec": self.start_sec, "end_sec": self.end_sec, "text": self.text}


class IncrementalRefinementWorker(QThread):
    """Re-transcribes audio segments in background while live ASR is running.

    Receives audio chunks (numpy arrays) via `add_chunk()`, accumulates them,
    and every `segment_duration` seconds transcribes the latest segment with
    a larger model.
    """

    segment_refined = pyqtSignal(int, str, float, float)  # (seg_index, text, start_sec, end_sec)
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, engine="mlx-whisper", model_size="medium",
                 language="auto", segment_duration=30):
        super().__init__()
        self.engine = engine
        self.model_size = model_size
        self.language = language
        self.segment_duration = segment_duration  # seconds per batch segment
        self._running = False
        self._chunks = []          # list of (timestamp_sec, np.array)
        self._total_samples = 0
        self._processed_up_to = 0  # samples already refined
        self._seg_index = 0

    def add_chunk(self, audio: np.ndarray, timestamp_sec: float):
        """Called from live ASR thread to feed raw audio."""
        self._chunks.append((timestamp_sec, audio.copy()))
        self._total_samples += len(audio)

    def get_full_audio(self) -> np.ndarray:
        """Return all accumulated audio as a single array."""
        if not self._chunks:
            return np.array([], dtype=np.float32)
        return np.concatenate([c[1] for c in self._chunks])

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        transcribe_fn = self._load_model()
        if transcribe_fn is None:
            return

        self.status.emit("Incremental refinement active")
        segment_samples = int(self.segment_duration * SAMPLE_RATE)

        while self._running:
            time.sleep(1.0)
            available = self._total_samples - self._processed_up_to
            if available < segment_samples:
                continue

            # Extract the next segment
            all_audio = self.get_full_audio()
            seg_start = self._processed_up_to
            seg_end = seg_start + segment_samples
            segment = all_audio[seg_start:seg_end]
            self._processed_up_to = seg_end

            start_sec = seg_start / SAMPLE_RATE
            end_sec = seg_end / SAMPLE_RATE

            text = self._transcribe_segment(transcribe_fn, segment)
            if text:
                self.segment_refined.emit(self._seg_index, text, start_sec, end_sec)
            self._seg_index += 1

        # Process any remaining audio
        if self._total_samples > self._processed_up_to:
            remaining_samples = self._total_samples - self._processed_up_to
            if remaining_samples > SAMPLE_RATE:  # at least 1 second
                all_audio = self.get_full_audio()
                segment = all_audio[self._processed_up_to:]
                start_sec = self._processed_up_to / SAMPLE_RATE
                end_sec = self._total_samples / SAMPLE_RATE
                text = self._transcribe_segment(transcribe_fn, segment)
                if text:
                    self.segment_refined.emit(self._seg_index, text, start_sec, end_sec)
                self._seg_index += 1

        self.status.emit("Incremental refinement stopped")

    def _transcribe_segment(self, transcribe_fn, audio: np.ndarray) -> str:
        """Save audio to temp WAV and transcribe."""
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            self._save_wav(tmp_path, audio)
            return transcribe_fn(tmp_path)
        except Exception as e:
            self.status.emit(f"Refinement error: {e}")
            return ""
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _load_model(self):
        """Load the batch ASR model and return a transcribe function."""
        if self.engine == "qwen3-asr":
            return self._load_qwen3()
        else:
            return self._load_whisper()

    def _load_whisper(self):
        try:
            import mlx_whisper
        except ImportError:
            self.error.emit("mlx_whisper not installed for refinement.")
            return None

        self.status.emit(f"Loading refinement model (whisper-{self.model_size})...")
        model_name = f"mlx-community/whisper-{self.model_size}-mlx"
        lang = None if self.language == "auto" else self.language

        def transcribe_fn(wav_path):
            result = mlx_whisper.transcribe(
                wav_path,
                path_or_hf_repo=model_name,
                language=lang,
                condition_on_previous_text=False,
                compression_ratio_threshold=2.0,
                no_speech_threshold=0.5,
            )
            return result.get("text", "").strip()

        return transcribe_fn

    def _load_qwen3(self):
        try:
            import torch
            from qwen_asr import Qwen3ASRModel
        except ImportError:
            self.error.emit("qwen-asr not installed for refinement.")
            return None

        import logging
        logging.getLogger("transformers").setLevel(logging.ERROR)

        self.status.emit("Loading refinement model (Qwen3-ASR)...")

        if self.model_size in ("tiny", "base", "small"):
            qwen_model = "Qwen/Qwen3-ASR-0.6B"
        else:
            qwen_model = "Qwen/Qwen3-ASR-1.7B"

        if torch.backends.mps.is_available():
            device, dtype = "mps", torch.float16
        elif torch.cuda.is_available():
            device, dtype = "cuda:0", torch.bfloat16
        else:
            device, dtype = "cpu", torch.float32

        try:
            model = Qwen3ASRModel.from_pretrained(
                qwen_model, dtype=dtype, device_map=device, max_new_tokens=512,
            )
        except Exception as e:
            self.error.emit(f"Failed to load Qwen3-ASR for refinement: {e}")
            return None

        from core.realtime_worker import QWEN3_LANG_MAP
        lang_name = QWEN3_LANG_MAP.get(self.language)

        s2t_converter = None
        if self.language in ("zh", "auto"):
            try:
                from opencc import OpenCC
                s2t_converter = OpenCC("s2t")
            except ImportError:
                pass

        def transcribe_fn(wav_path):
            import numpy as _np
            import wave
            with wave.open(wav_path, "rb") as wf:
                frames = wf.readframes(wf.getnframes())
                audio = _np.frombuffer(frames, dtype=_np.int16).astype(_np.float32) / 32767.0
            results = model.transcribe(
                audio=[(audio, SAMPLE_RATE)],
                language=[lang_name] if lang_name else None,
            )
            if results and results[0].text:
                text = results[0].text.strip()
                if s2t_converter and text:
                    text = s2t_converter.convert(text)
                return text
            return ""

        return transcribe_fn

    @staticmethod
    def _save_wav(path, audio_data):
        import wave
        audio_int16 = (audio_data * 32767).astype(np.int16)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())


class PostRecordingRefinementWorker(QThread):
    """After live ASR stops, re-transcribe the full recording with a larger model."""

    refinement_complete = pyqtSignal(list)  # list of RefinementSegment dicts
    progress = pyqtSignal(int)              # 0-100
    status = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, audio: np.ndarray, engine="mlx-whisper",
                 model_size="medium", language="auto"):
        super().__init__()
        self.audio = audio
        self.engine = engine
        self.model_size = model_size
        self.language = language

    def run(self):
        if self.audio is None or len(self.audio) < SAMPLE_RATE:
            self.error.emit("No audio to refine (too short).")
            return

        self.status.emit("Loading refinement model...")
        self.progress.emit(5)

        if self.engine == "qwen3-asr":
            self._run_qwen3()
        else:
            self._run_whisper()

    def _run_whisper(self):
        try:
            import mlx_whisper
        except ImportError:
            self.error.emit("mlx_whisper not installed.")
            return

        model_name = f"mlx-community/whisper-{self.model_size}-mlx"
        lang = None if self.language == "auto" else self.language

        # Save full audio to temp file
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            self._save_wav(tmp_path, self.audio)
            self.status.emit(f"Refining with whisper-{self.model_size}...")
            self.progress.emit(20)

            result = mlx_whisper.transcribe(
                tmp_path,
                path_or_hf_repo=model_name,
                language=lang,
                condition_on_previous_text=True,  # full file, context helps
                compression_ratio_threshold=2.0,
                no_speech_threshold=0.5,
                word_timestamps=False,
            )

            self.progress.emit(80)
            segments = []
            for seg in result.get("segments", []):
                segments.append(RefinementSegment(
                    start_sec=seg["start"],
                    end_sec=seg["end"],
                    text=seg["text"].strip(),
                ).to_dict())

            # Fallback: if no segments but there's text
            if not segments and result.get("text", "").strip():
                duration = len(self.audio) / SAMPLE_RATE
                segments.append(RefinementSegment(
                    start_sec=0, end_sec=duration,
                    text=result["text"].strip(),
                ).to_dict())

            self.progress.emit(100)
            self.status.emit("✅ Post-recording refinement complete")
            self.refinement_complete.emit(segments)

        except Exception as e:
            self.error.emit(f"Refinement failed: {e}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _run_qwen3(self):
        try:
            import torch
            from qwen_asr import Qwen3ASRModel
        except ImportError:
            self.error.emit("qwen-asr not installed.")
            return

        import logging
        logging.getLogger("transformers").setLevel(logging.ERROR)

        if self.model_size in ("tiny", "base", "small"):
            qwen_model = "Qwen/Qwen3-ASR-0.6B"
        else:
            qwen_model = "Qwen/Qwen3-ASR-1.7B"

        if torch.backends.mps.is_available():
            device, dtype = "mps", torch.float16
        elif torch.cuda.is_available():
            device, dtype = "cuda:0", torch.bfloat16
        else:
            device, dtype = "cpu", torch.float32

        try:
            model = Qwen3ASRModel.from_pretrained(
                qwen_model, dtype=dtype, device_map=device, max_new_tokens=2048,
            )
        except Exception as e:
            self.error.emit(f"Failed to load Qwen3-ASR: {e}")
            return

        from core.realtime_worker import QWEN3_LANG_MAP
        lang_name = QWEN3_LANG_MAP.get(self.language)

        s2t_converter = None
        if self.language in ("zh", "auto"):
            try:
                from opencc import OpenCC
                s2t_converter = OpenCC("s2t")
            except ImportError:
                pass

        self.status.emit(f"Refining with Qwen3-ASR ({qwen_model.split('/')[-1]})...")
        self.progress.emit(20)

        # Qwen3-ASR: process in ~60s chunks for long audio
        chunk_duration = 60  # seconds
        chunk_samples = chunk_duration * SAMPLE_RATE
        total_samples = len(self.audio)
        segments = []
        offset = 0

        while offset < total_samples:
            end = min(offset + chunk_samples, total_samples)
            chunk = self.audio[offset:end]

            if len(chunk) < SAMPLE_RATE:  # skip < 1s
                break

            results = model.transcribe(
                audio=[(chunk, SAMPLE_RATE)],
                language=[lang_name] if lang_name else None,
            )

            if results and results[0].text:
                text = results[0].text.strip()
                if s2t_converter and text:
                    text = s2t_converter.convert(text)
                if text:
                    segments.append(RefinementSegment(
                        start_sec=offset / SAMPLE_RATE,
                        end_sec=end / SAMPLE_RATE,
                        text=text,
                    ).to_dict())

            pct = int(20 + 70 * end / total_samples)
            self.progress.emit(min(pct, 95))
            offset = end

        self.progress.emit(100)
        self.status.emit("✅ Post-recording refinement complete")
        self.refinement_complete.emit(segments)

    @staticmethod
    def _save_wav(path, audio_data):
        import wave
        audio_int16 = (audio_data * 32767).astype(np.int16)
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio_int16.tobytes())

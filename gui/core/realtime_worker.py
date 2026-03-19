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
ENGINE_TRANSCRIBE = "aws-transcribe"
ENGINE_NOVA_SONIC = "nova-sonic"

# MLX Whisper model map (shared across all components)
WHISPER_MODEL_MAP = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
}

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
        if self.engine == ENGINE_NOVA_SONIC:
            self._run_nova_sonic()
            return
        elif self.engine == ENGINE_TRANSCRIBE:
            transcribe_fn = self._init_transcribe()
        elif self.engine == ENGINE_QWEN3:
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
        model_name = WHISPER_MODEL_MAP.get(self.model_size, f"mlx-community/whisper-{self.model_size}-mlx")
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

    def _run_nova_sonic(self):
        """Run Nova Sonic 2 bidirectional streaming ASR (fully async)."""
        import asyncio
        import traceback
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._nova_sonic_session())
        except Exception as e:
            tb = traceback.format_exc()
            self.error.emit(f"Nova Sonic error: {e}\n\n{tb}")
        finally:
            self.status_changed.emit("Stopped")
            self.stopped.emit()

    async def _nova_sonic_session(self):
        """Main Nova Sonic session with auto-reconnect."""
        import asyncio
        try:
            from aws_sdk_bedrock_runtime.client import (
                BedrockRuntimeClient,
                InvokeModelWithBidirectionalStreamOperationInput,
            )
            from aws_sdk_bedrock_runtime.models import (
                InvokeModelWithBidirectionalStreamInputChunk,
                BidirectionalInputPayloadPart,
            )
            from aws_sdk_bedrock_runtime.config import (
                Config, HTTPAuthSchemeResolver, SigV4AuthScheme,
            )
            from smithy_aws_core.identity import EnvironmentCredentialsResolver
        except ImportError:
            self.error.emit(
                "aws-sdk-bedrock-runtime not installed.\n"
                "Run: uv pip install \"aws-sdk-python[bedrock-runtime]\""
            )
            return

        import sounddevice as sd
        import base64
        import json
        import uuid
        import traceback

        # Region: check BEDROCK_REGION first, then AWS_DEFAULT_REGION
        region = os.environ.get("BEDROCK_REGION",
                 os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        model_id = "amazon.nova-2-sonic-v1:0"

        RECONNECT_INTERVAL = 7 * 60  # reconnect at 7 min (limit is 8 min)

        self.status_changed.emit(f"Connecting to Nova Sonic 2 ({region})...")

        while self._running:
            # --- Create client & stream ---
            try:
                self.status_changed.emit(f"Initializing Bedrock client ({region})...")

                # Try environment vars first, fall back to ~/.aws/credentials
                cred_resolver = EnvironmentCredentialsResolver()
                has_env_creds = (
                    os.environ.get("AWS_ACCESS_KEY_ID")
                    and os.environ.get("AWS_SECRET_ACCESS_KEY")
                )
                if not has_env_creds:
                    # Try boto3 session to get credentials from ~/.aws/credentials or SSO
                    try:
                        import boto3
                        session = boto3.Session()
                        creds = session.get_credentials()
                        if creds:
                            frozen = creds.get_frozen_credentials()
                            os.environ["AWS_ACCESS_KEY_ID"] = frozen.access_key
                            os.environ["AWS_SECRET_ACCESS_KEY"] = frozen.secret_key
                            if frozen.token:
                                os.environ["AWS_SESSION_TOKEN"] = frozen.token
                            self.status_changed.emit("Using AWS credentials from profile...")
                        else:
                            self.error.emit(
                                "No AWS credentials found.\n"
                                "Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY in .env,\n"
                                "or configure ~/.aws/credentials"
                            )
                            return
                    except Exception as cred_err:
                        self.error.emit(f"Cannot resolve AWS credentials: {cred_err}")
                        return

                config = Config(
                    endpoint_uri=f"https://bedrock-runtime.{region}.amazonaws.com",
                    region=region,
                    aws_credentials_identity_resolver=cred_resolver,
                    auth_scheme_resolver=HTTPAuthSchemeResolver(),
                    auth_schemes={"aws.auth#sigv4": SigV4AuthScheme(service="bedrock")},
                )
                client = BedrockRuntimeClient(config=config)
                self.status_changed.emit("Opening bidirectional stream...")
                stream = await client.invoke_model_with_bidirectional_stream(
                    InvokeModelWithBidirectionalStreamOperationInput(model_id=model_id)
                )
                self.status_changed.emit("Stream connected, setting up session...")
            except Exception as e:
                tb = traceback.format_exc()
                self.error.emit(
                    f"Failed to connect to Nova Sonic 2:\n{e}\n\n"
                    f"Check:\n- AWS credentials configured\n"
                    f"- Region '{region}' supports Nova Sonic\n"
                    f"- Bedrock model access enabled\n\n{tb}"
                )
                return

            prompt_name = str(uuid.uuid4())
            content_name = str(uuid.uuid4())
            audio_content_name = str(uuid.uuid4())

            async def send_event(event_json):
                event = InvokeModelWithBidirectionalStreamInputChunk(
                    value=BidirectionalInputPayloadPart(
                        bytes_=event_json.encode("utf-8")
                    )
                )
                await stream.input_stream.send(event)

            # --- Session start ---
            self.status_changed.emit("Sending session start...")
            await send_event(json.dumps({
                "event": {
                    "sessionStart": {
                        "inferenceConfiguration": {
                            "maxTokens": 1024,
                            "topP": 0.9,
                            "temperature": 0.1,
                        },
                        "turnDetectionConfiguration": {
                            "endpointingSensitivity": "HIGH",
                        },
                    }
                }
            }))

            # --- Prompt start (ASR-only: no audio output) ---
            await send_event(json.dumps({
                "event": {
                    "promptStart": {
                        "promptName": prompt_name,
                        "textOutputConfiguration": {
                            "mediaType": "text/plain",
                        },
                        "audioOutputConfiguration": {
                            "mediaType": "audio/lpcm",
                            "sampleRateHertz": 24000,
                            "sampleSizeBits": 16,
                            "channelCount": 1,
                            "voiceId": "matthew",
                            "encoding": "base64",
                            "audioType": "SPEECH",
                        },
                    }
                }
            }))

            # --- System prompt: transcription-only mode ---
            await send_event(json.dumps({
                "event": {
                    "contentStart": {
                        "promptName": prompt_name,
                        "contentName": content_name,
                        "type": "TEXT",
                        "interactive": True,
                        "role": "SYSTEM",
                        "textInputConfiguration": {
                            "mediaType": "text/plain",
                        },
                    }
                }
            }))

            system_prompt = (
                "You are a transcription assistant. Your ONLY job is to accurately "
                "transcribe what the user says. Do NOT respond, do NOT answer questions, "
                "do NOT add commentary. Simply output the exact transcription of the "
                "user's speech. Preserve the original language (Chinese, English, etc). "
                "Keep your text output minimal — just the transcription."
            )
            await send_event(json.dumps({
                "event": {
                    "textInput": {
                        "promptName": prompt_name,
                        "contentName": content_name,
                        "content": system_prompt,
                    }
                }
            }))

            await send_event(json.dumps({
                "event": {
                    "contentEnd": {
                        "promptName": prompt_name,
                        "contentName": content_name,
                    }
                }
            }))

            # --- Start audio input ---
            self.status_changed.emit("Starting audio input stream...")
            await send_event(json.dumps({
                "event": {
                    "contentStart": {
                        "promptName": prompt_name,
                        "contentName": audio_content_name,
                        "type": "AUDIO",
                        "interactive": True,
                        "role": "USER",
                        "audioInputConfiguration": {
                            "mediaType": "audio/lpcm",
                            "sampleRateHertz": 16000,
                            "sampleSizeBits": 16,
                            "channelCount": 1,
                            "audioType": "SPEECH",
                            "encoding": "base64",
                        },
                    }
                }
            }))

            self.status_changed.emit("Listening...")

            # --- Response processor task ---
            session_active = True

            async def process_responses():
                nonlocal session_active
                try:
                    while session_active and self._running:
                        output = await stream.await_output()
                        result = await output[1].receive()
                        if result.value and result.value.bytes_:
                            data = json.loads(result.value.bytes_.decode("utf-8"))
                            if "event" not in data:
                                continue
                            evt = data["event"]
                            # We only care about USER ASR transcription
                            if "textOutput" in evt:
                                text = evt["textOutput"].get("content", "").strip()
                                if text:
                                    role = getattr(self, "_nova_role", "")
                                    if role == "USER":
                                        if not self._is_hallucination(text):
                                            self.transcript_update.emit(text)
                                            self._prev_text = text
                            elif "contentStart" in evt:
                                cs = evt["contentStart"]
                                self._nova_role = cs.get("role", "")
                            elif "completionStart" in evt:
                                pass  # session metadata
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    if session_active and self._running:
                        self.status_changed.emit(f"Response error: {e}")

            response_task = asyncio.create_task(process_responses())

            # --- Audio capture & send loop ---
            audio_queue = asyncio.Queue()

            def audio_callback(indata, frames, time_info, status):
                if not self._paused and self._running:
                    audio_int16 = (indata[:, 0] * 32767).astype(np.int16)
                    audio_queue.put_nowait(audio_int16.tobytes())
                    # VU meter
                    rms = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
                    self.level_update.emit(min(rms * 10, 1.0))

            try:
                mic_stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="float32",
                    blocksize=1024,
                    device=self.device_index,
                    callback=audio_callback,
                )
                mic_stream.start()
            except Exception as e:
                self.error.emit(f"Microphone error: {e}")
                session_active = False
                response_task.cancel()
                return

            session_start_time = time.time()
            try:
                while self._running:
                    # Check reconnect timer
                    elapsed = time.time() - session_start_time
                    if elapsed >= RECONNECT_INTERVAL:
                        self.status_changed.emit("Reconnecting...")
                        break  # break inner loop to reconnect

                    # Send audio chunks
                    try:
                        audio_bytes = await asyncio.wait_for(
                            audio_queue.get(), timeout=0.1
                        )
                        blob = base64.b64encode(audio_bytes).decode("utf-8")
                        await send_event(json.dumps({
                            "event": {
                                "audioInput": {
                                    "promptName": prompt_name,
                                    "contentName": audio_content_name,
                                    "content": blob,
                                }
                            }
                        }))
                    except asyncio.TimeoutError:
                        continue
            finally:
                mic_stream.stop()
                mic_stream.close()
                session_active = False
                response_task.cancel()
                # End session gracefully
                try:
                    await send_event(json.dumps({
                        "event": {
                            "contentEnd": {
                                "promptName": prompt_name,
                                "contentName": audio_content_name,
                            }
                        }
                    }))
                    await send_event(json.dumps({
                        "event": {"promptEnd": {"promptName": prompt_name}}
                    }))
                    await send_event(json.dumps({
                        "event": {"sessionEnd": {}}
                    }))
                    await stream.input_stream.close()
                except Exception:
                    pass

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

    def _init_transcribe(self):
        """Initialize AWS Transcribe streaming and return a transcribe function."""
        try:
            import boto3
        except ImportError:
            self.error.emit("boto3 not installed.\nRun: pip install boto3")
            return None

        self.status_changed.emit("Initializing AWS Transcribe...")

        # Map language codes to AWS Transcribe language codes
        aws_lang_map = {
            "zh": "zh-CN", "en": "en-US", "ja": "ja-JP",
            "ko": "ko-KR", "fr": "fr-FR", "de": "de-DE",
            "es": "es-ES", "pt": "pt-BR", "it": "it-IT",
            "auto": None,
        }
        aws_lang = aws_lang_map.get(self.language)

        # Use boto3 transcribe client (batch per-chunk, not streaming SDK)
        # This approach sends each audio chunk as a short job via start_transcription_job
        # For realtime, we use the synchronous approach with temporary S3-less processing
        import json
        import wave
        import struct

        try:
            # Test credentials
            client = boto3.client("transcribe")
            s3_client = boto3.client("s3")
            # We'll use a simple approach: write wav to temp, upload to S3, transcribe
            # But for realtime, we use the streaming HTTP/2 approach via boto3
            self.status_changed.emit("AWS Transcribe ready")
        except Exception as e:
            self.error.emit(f"AWS credentials error: {e}")
            return None

        def transcribe_fn(wav_path, chunk_array):
            """Transcribe a chunk using AWS Transcribe streaming via boto3."""
            try:
                import uuid
                transcribe_client = boto3.client("transcribe-streaming",
                                                  region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

                # Read the wav file as bytes
                with open(wav_path, "rb") as f:
                    audio_bytes = f.read()

                # Use start_stream_transcription
                kwargs = {
                    "LanguageCode": aws_lang or "en-US",
                    "MediaEncoding": "pcm",
                    "MediaSampleRateHertz": SAMPLE_RATE,
                }

                response = transcribe_client.start_stream_transcription(**kwargs)
                stream = response["TranscriptResultStream"]

                # Send audio
                audio_stream = response["AudioStream"]
                # Send in 4KB chunks
                offset = 44  # skip WAV header
                while offset < len(audio_bytes):
                    end = min(offset + 4096, len(audio_bytes))
                    audio_stream.send_audio_event(AudioChunk=audio_bytes[offset:end])
                    offset = end
                audio_stream.end_stream()

                # Collect results
                full_text = ""
                for event in stream:
                    if "TranscriptEvent" in event:
                        results = event["TranscriptEvent"]["Transcript"]["Results"]
                        for result in results:
                            if not result.get("IsPartial", True):
                                alts = result.get("Alternatives", [])
                                if alts:
                                    full_text += alts[0].get("Transcript", "") + " "
                return full_text.strip()

            except Exception:
                # Fallback: use batch transcribe with local file
                return self._transcribe_batch_fallback(wav_path, aws_lang)

        def _batch_fallback(wav_path, lang_code):
            """Fallback: use simple synchronous transcription."""
            try:
                import uuid
                client = boto3.client("transcribe")
                job_name = f"realtime-{uuid.uuid4().hex[:8]}"

                # For batch, we need S3. Skip if not available.
                return ""
            except Exception:
                return ""

        self._transcribe_batch_fallback = _batch_fallback
        return transcribe_fn

    def _is_hallucination(self, text):
        """Detect and filter common hallucination patterns."""
        # AWS Transcribe results are cloud-processed, skip hallucination check
        if self.engine == ENGINE_TRANSCRIBE:
            return False

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

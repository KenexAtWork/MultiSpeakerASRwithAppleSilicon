"""
Web Live ASR Server — FastAPI + WebSocket
Engines: AWS Transcribe Streaming, Nova Sonic 2
"""
import os
import json
import asyncio
import base64
import uuid
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("asr")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI(title="Web Live ASR")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


def _load_aws_credentials():
    """Ensure AWS creds in env vars, fallback to ~/.aws/credentials via boto3."""
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        return True
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
            return True
    except Exception:
        pass
    return False


# ==================== Nova Sonic 2 ====================

async def _run_nova_sonic(ws: WebSocket, language: str):
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

    region = os.environ.get("BEDROCK_REGION",
             os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

    await ws.send_json({"type": "status", "text": f"Connecting Nova Sonic 2 ({region})..."})

    config = Config(
        endpoint_uri=f"https://bedrock-runtime.{region}.amazonaws.com",
        region=region,
        aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
        auth_scheme_resolver=HTTPAuthSchemeResolver(),
        auth_schemes={"aws.auth#sigv4": SigV4AuthScheme(service="bedrock")},
    )
    client = BedrockRuntimeClient(config=config)
    stream = await client.invoke_model_with_bidirectional_stream(
        InvokeModelWithBidirectionalStreamOperationInput(model_id="amazon.nova-2-sonic-v1:0")
    )
    await ws.send_json({"type": "status", "text": "Connected"})

    prompt_name = str(uuid.uuid4())
    content_name = str(uuid.uuid4())
    audio_content_name = str(uuid.uuid4())

    async def send_evt(evt):
        await stream.input_stream.send(
            InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(
                    bytes_=json.dumps(evt).encode("utf-8")
                )
            )
        )

    # Session setup
    await send_evt({"event": {"sessionStart": {
        "inferenceConfiguration": {"maxTokens": 1024, "topP": 0.9, "temperature": 0.1},
        "turnDetectionConfiguration": {"endpointingSensitivity": "HIGH"},
    }}})
    await send_evt({"event": {"promptStart": {
        "promptName": prompt_name,
        "textOutputConfiguration": {"mediaType": "text/plain"},
        "audioOutputConfiguration": {
            "mediaType": "audio/lpcm", "sampleRateHertz": 24000,
            "sampleSizeBits": 16, "channelCount": 1,
            "voiceId": "matthew", "encoding": "base64", "audioType": "SPEECH",
        },
    }}})

    # System prompt
    lang_hint = f" The primary language is {language}." if language != "auto" else ""
    system_text = (
        "You are a transcription assistant. Your ONLY job is to accurately "
        "transcribe what the user says. Do NOT respond, do NOT answer questions, "
        "do NOT add commentary. Simply output the exact transcription of the "
        "user's speech. For Chinese, use Traditional Chinese (繁體中文). "
        "Keep your text output minimal — just the transcription."
        f"{lang_hint}"
    )
    await send_evt({"event": {"contentStart": {
        "promptName": prompt_name, "contentName": content_name,
        "type": "TEXT", "interactive": True, "role": "SYSTEM",
        "textInputConfiguration": {"mediaType": "text/plain"},
    }}})
    await send_evt({"event": {"textInput": {
        "promptName": prompt_name, "contentName": content_name,
        "content": system_text,
    }}})
    await send_evt({"event": {"contentEnd": {
        "promptName": prompt_name, "contentName": content_name,
    }}})

    # Audio input config
    await send_evt({"event": {"contentStart": {
        "promptName": prompt_name, "contentName": audio_content_name,
        "type": "AUDIO", "interactive": True, "role": "USER",
        "audioInputConfiguration": {
            "mediaType": "audio/lpcm", "sampleRateHertz": 16000,
            "sampleSizeBits": 16, "channelCount": 1,
            "audioType": "SPEECH", "encoding": "base64",
        },
    }}})

    await ws.send_json({"type": "status", "text": "Listening..."})

    # Response reader
    session_active = True
    nova_role = ""
    session_start = asyncio.get_event_loop().time()

    async def read_responses():
        nonlocal nova_role
        try:
            # Optional: Traditional Chinese converter
            s2t = None
            try:
                import opencc
                s2t = opencc.OpenCC('s2t')
            except ImportError:
                pass

            while session_active:
                output = await stream.await_output()
                result = await output[1].receive()
                if result.value and result.value.bytes_:
                    data = json.loads(result.value.bytes_.decode("utf-8"))
                    if "event" not in data:
                        continue
                    evt = data["event"]
                    if "textOutput" in evt:
                        text = evt["textOutput"].get("content", "").strip()
                        # Only take USER role = raw ASR transcription
                        if text and nova_role == "USER":
                            if s2t:
                                text = s2t.convert(text)
                            elapsed = asyncio.get_event_loop().time() - session_start
                            log.info(f"ASR: {text[:80]}")
                            await ws.send_json({"type": "transcript", "text": text, "time": round(elapsed, 2)})
                    elif "contentStart" in evt:
                        nova_role = evt["contentStart"].get("role", "")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Response reader error: {e}")

    reader_task = asyncio.create_task(read_responses())

    # Receive audio from browser and forward
    audio_chunk_count = 0
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if "bytes" in msg:
                audio_chunk_count += 1
                if audio_chunk_count <= 3 or audio_chunk_count % 50 == 0:
                    log.info(f"Audio chunk #{audio_chunk_count}, size={len(msg['bytes'])} bytes")
                audio_b64 = base64.b64encode(msg["bytes"]).decode("utf-8")
                await send_evt({"event": {"audioInput": {
                    "promptName": prompt_name,
                    "contentName": audio_content_name,
                    "content": audio_b64,
                }}})
            elif "text" in msg:
                data = json.loads(msg["text"])
                if data.get("action") == "stop":
                    break
    except WebSocketDisconnect:
        pass
    finally:
        session_active = False
        reader_task.cancel()
        try:
            await send_evt({"event": {"contentEnd": {
                "promptName": prompt_name, "contentName": audio_content_name,
            }}})
            await send_evt({"event": {"promptEnd": {"promptName": prompt_name}}})
            await send_evt({"event": {"sessionEnd": {}}})
            await stream.input_stream.close()
        except Exception:
            pass


# ==================== AWS Transcribe Streaming ====================

async def _run_transcribe(ws: WebSocket, language: str):
    """AWS Transcribe Streaming via amazon-transcribe SDK."""
    from amazon_transcribe.client import TranscribeStreamingClient
    from amazon_transcribe.handlers import TranscriptResultStreamHandler
    from amazon_transcribe.model import TranscriptEvent
    import traceback

    region = os.environ.get("BEDROCK_REGION",
             os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

    await ws.send_json({"type": "status", "text": f"Connecting AWS Transcribe ({region})..."})
    log.info(f"Transcribe: connecting to {region}")

    LANG_MAP = {
        "zh": "zh-CN", "en": "en-US", "ja": "ja-JP", "ko": "ko-KR",
        "fr": "fr-FR", "de": "de-DE", "es": "es-US", "pt": "pt-BR",
        "it": "it-IT", "auto": "en-US",
    }
    lang_code = LANG_MAP.get(language, language if "-" in str(language) else "en-US")
    log.info(f"Transcribe: lang_code={lang_code}")

    try:
        client = TranscribeStreamingClient(region=region)
        transcribe_stream = await client.start_stream_transcription(
            language_code=lang_code,
            media_sample_rate_hz=16000,
            media_encoding="pcm",
        )
        log.info("Transcribe: stream started")
    except Exception as e:
        tb = traceback.format_exc()
        log.error(f"Transcribe connect error: {e}\n{tb}")
        await ws.send_json({"type": "error", "text": f"Transcribe error: {e}"})
        return

    await ws.send_json({"type": "status", "text": "Listening..."})
    transcribe_start = asyncio.get_event_loop().time()

    class Handler(TranscriptResultStreamHandler):
        async def handle_transcript_event(self, transcript_event: TranscriptEvent):
            results = transcript_event.transcript.results
            for result in results:
                if not result.is_partial:
                    for alt in result.alternatives:
                        text = alt.transcript.strip()
                        if text:
                            elapsed = asyncio.get_event_loop().time() - transcribe_start
                            log.info(f"Transcribe ASR: {text[:80]}")
                            await ws.send_json({"type": "transcript", "text": text, "time": round(elapsed, 2)})

    handler = Handler(transcribe_stream.output_stream)
    handler_task = asyncio.create_task(handler.handle_events())

    audio_count = 0
    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if "bytes" in msg:
                audio_count += 1
                if audio_count <= 3 or audio_count % 100 == 0:
                    log.info(f"Transcribe audio chunk #{audio_count}, size={len(msg['bytes'])}")
                await transcribe_stream.input_stream.send_audio_event(
                    audio_chunk=msg["bytes"]
                )
            elif "text" in msg:
                data = json.loads(msg["text"])
                if data.get("action") == "stop":
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error(f"Transcribe receive error: {e}")
    finally:
        try:
            await transcribe_stream.input_stream.end_stream()
            await handler_task
        except Exception:
            pass


# ==================== WebSocket Endpoint ====================

@app.websocket("/ws/asr")
async def websocket_asr(ws: WebSocket):
    await ws.accept()

    # First message: config
    try:
        config_msg = await asyncio.wait_for(ws.receive_json(), timeout=10)
    except Exception:
        await ws.close(code=1008, reason="Expected config message")
        return

    engine = config_msg.get("engine", "nova-sonic")
    language = config_msg.get("language", "auto")
    log.info(f"WebSocket session: engine={engine}, language={language}")

    if not _load_aws_credentials():
        await ws.send_json({"type": "error", "text": "AWS credentials not found"})
        await ws.close()
        return

    try:
        if engine == "nova-sonic":
            await _run_nova_sonic(ws, language)
        elif engine == "transcribe":
            await _run_transcribe(ws, language)
        else:
            await ws.send_json({"type": "error", "text": f"Unknown engine: {engine}"})
    except Exception as e:
        log.error(f"Engine {engine} error: {e}", exc_info=True)
        try:
            await ws.send_json({"type": "error", "text": str(e)})
        except Exception:
            pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass

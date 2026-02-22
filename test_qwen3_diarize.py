#!/usr/bin/env python3
"""測試 Qwen3-ASR 1.7B + pyannote diarization"""
import os
import time

# 載入 .env 中的 HF_TOKEN
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
os.environ["PYANNOTE_AUTH_TOKEN"] = os.environ.get("HF_TOKEN", "")

from mlx_qwen3_asr import transcribe

audio_path = os.path.join(os.path.dirname(__file__), "test-meeting.mp4")

print("=== Qwen3-ASR 1.7B + Diarization 測試 ===")
print(f"音檔: {audio_path}")

t0 = time.time()
result = transcribe(
    audio_path,
    model="Qwen/Qwen3-ASR-1.7B",
    language=None,
    diarize=True,
    verbose=True,
)
elapsed = time.time() - t0

print(f"\n轉錄+分離完成: {elapsed:.2f}s")
print(f"語言: {result.language}")
print(f"文字長度: {len(result.text)} chars")

if result.speaker_segments:
    print(f"\n--- Speaker Segments ({len(result.speaker_segments)} 段) ---")
    for seg in result.speaker_segments:
        speaker = seg.get("speaker", "?")
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        text = seg.get("text", "")
        print(f"  [{start:6.2f}s - {end:6.2f}s] {speaker}: {text}")
else:
    print("\n沒有 speaker_segments，檢查 diarization 是否正常")
    print(f"result keys: {dir(result)}")

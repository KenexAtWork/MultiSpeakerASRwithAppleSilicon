#!/usr/bin/env python3
"""測試 Qwen3-ASR chunks 輸出格式"""
import os, time
from mlx_qwen3_asr import transcribe

audio_path = os.path.join(os.path.dirname(__file__), "examples", "sample-01.mp4")

print("=== Qwen3-ASR 0.6B chunks 測試 ===")
t0 = time.time()
result = transcribe(
    audio_path,
    model="Qwen/Qwen3-ASR-0.6B",
    language=None,
    return_chunks=True,
    return_timestamps=True,
    verbose=False,
)
print(f"耗時: {time.time()-t0:.2f}s")
print(f"語言: {result.language}")
print(f"text 長度: {len(result.text)}")

if result.chunks:
    print(f"\n--- chunks ({len(result.chunks)} 個) ---")
    for i, c in enumerate(result.chunks[:5]):
        print(f"  chunk {i}: {c}")

if result.segments:
    print(f"\n--- segments ({len(result.segments)} 個) ---")
    for i, s in enumerate(result.segments[:20]):
        print(f"  seg {i}: {s}")

#!/usr/bin/env python3
"""Qwen3-ASR 完整測試：ASR + Diarization + 簡轉繁"""
import time
import os

def simple_s2t(text):
    """簡體轉繁體（使用 opencc）"""
    try:
        import opencc
        converter = opencc.OpenCC('s2t')
        return converter.convert(text)
    except ImportError:
        print("    [WARN] opencc 未安裝，跳過簡轉繁")
        return text

def main():
    audio_path = os.path.join(os.path.dirname(__file__), "examples", "sample-01.mp4")
    print("=== Qwen3-ASR 完整測試 ===\n")

    # --- Test 1: ASR + Diarization ---
    print("[1] ASR + Speaker Diarization (0.6B)")
    from mlx_qwen3_asr import transcribe
    t0 = time.time()
    result = transcribe(
        audio_path,
        model="Qwen/Qwen3-ASR-0.6B",
        language="Chinese",
        diarize=True,
        verbose=True,
    )
    elapsed = time.time() - t0
    duration = 60.0
    print(f"\n    完成: {elapsed:.2f}s (RTF: {elapsed/duration:.3f})")
    print(f"    語言: {result.language}")

    if result.speaker_segments:
        print(f"    說話者段落數: {len(result.speaker_segments)}")
        print(f"\n--- Speaker Segments (前 15 段) ---")
        for seg in result.speaker_segments[:15]:
            print(f"  [{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['speaker']}: {seg['text']}")
    else:
        print("    [WARN] 無 speaker_segments")
        print(f"    text: {result.text[:200]}")

    # --- Test 2: 簡轉繁 ---
    print(f"\n[2] 簡體轉繁體")
    raw_text = result.text
    t0 = time.time()
    trad_text = simple_s2t(raw_text)
    print(f"    轉換耗時: {time.time()-t0:.3f}s")
    print(f"\n--- 簡體原文 (前 200 字) ---")
    print(raw_text[:200])
    print(f"\n--- 繁體結果 (前 200 字) ---")
    print(trad_text[:200])

    # 如果有 speaker segments，也轉繁體
    if result.speaker_segments:
        print(f"\n--- 繁體 Speaker Segments (前 10 段) ---")
        for seg in result.speaker_segments[:10]:
            trad = simple_s2t(seg['text'])
            print(f"  [{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['speaker']}: {trad}")

    # --- Test 3: Streaming 測試 ---
    print(f"\n[3] Streaming API 測試")
    from mlx_qwen3_asr import load_audio
    from mlx_qwen3_asr.streaming import init_streaming, feed_audio, finish_streaming
    import numpy as np

    audio = load_audio(audio_path)
    audio_np = np.array(audio)
    chunk_size = 16000 * 2  # 2 秒一個 chunk

    t0 = time.time()
    state = init_streaming(chunk_size_sec=2.0, max_context_sec=30.0)
    chunks_fed = 0
    for i in range(0, len(audio_np), chunk_size):
        chunk = audio_np[i:i+chunk_size]
        if len(chunk) == 0:
            break
        state = feed_audio(chunk, state)
        chunks_fed += 1
        if chunks_fed <= 5 or chunks_fed % 5 == 0:
            stable = getattr(state, 'stable_text', '') or ''
            partial = getattr(state, 'text', '') or ''
            display = stable if stable else partial
            print(f"    chunk {chunks_fed}: '{display[:60]}...'")

    state = finish_streaming(state)
    elapsed = time.time() - t0
    final_text = getattr(state, 'text', '') or getattr(state, 'stable_text', '')
    print(f"\n    Streaming 完成: {elapsed:.2f}s")
    print(f"    Chunks: {chunks_fed}")
    print(f"\n--- Streaming 結果 (前 300 字) ---")
    print(final_text[:300])
    print(f"\n--- 繁體 ---")
    print(simple_s2t(final_text[:300]))

if __name__ == "__main__":
    main()

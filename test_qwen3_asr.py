#!/usr/bin/env python3
"""快速測試 Qwen3-ASR on Apple Silicon (MLX)"""
import time
import sys

def main():
    print("=== Qwen3-ASR MLX 測試 ===")
    print()

    # 1. 測試 import
    print("[1] 載入 mlx_qwen3_asr...")
    t0 = time.time()
    from mlx_qwen3_asr import transcribe, load_audio
    print(f"    import 完成: {time.time()-t0:.2f}s")

    # 2. 載入音檔
    import os
    audio_path = os.path.join(os.path.dirname(__file__), "examples", "sample-01.mp4")
    print(f"\n[2] 載入音檔: {audio_path}")
    t0 = time.time()
    audio = load_audio(audio_path)
    duration = len(audio) / 16000
    print(f"    音檔長度: {duration:.1f}s, 載入耗時: {time.time()-t0:.2f}s")

    # 3. 1.7B 模型轉錄 (language=None 自動偵測，支援中英混合)
    print(f"\n[3] Qwen3-ASR-1.7B 轉錄中 (language=None)...")
    t0 = time.time()
    result = transcribe(
        audio_path,
        model="Qwen/Qwen3-ASR-1.7B",
        language=None,
        return_timestamps=True,
        verbose=True,
    )
    elapsed = time.time() - t0
    rtf = elapsed / duration
    print(f"\n    轉錄完成: {elapsed:.2f}s (RTF: {rtf:.3f})")
    print(f"    偵測語言: {result.language}")
    print(f"    文字長度: {len(result.text)} chars")
    print(f"\n--- 轉錄結果 (前 500 字) ---")
    print(result.text[:500])

    if result.segments:
        print(f"\n--- Timestamps (前 10 段) ---")
        for seg in result.segments[:10]:
            print(f"  [{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text']}")

    # 4. 輸出完整結果供比較
    print(f"\n--- 完整轉錄 ---")
    print(result.text)

if __name__ == "__main__":
    main()

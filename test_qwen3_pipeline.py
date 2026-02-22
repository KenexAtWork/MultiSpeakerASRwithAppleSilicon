#!/usr/bin/env python3
"""
完整 pipeline 測試：Qwen3-ASR + pyannote diarization
模擬 v5_fast 的架構，用 Qwen3-ASR 替換 Whisper
"""
import os, sys, time, gc, re, subprocess, tempfile

# 載入 .env
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

HF_TOKEN = os.environ.get("HF_TOKEN", "")
AUDIO = os.path.join(os.path.dirname(__file__), "examples", "sample-01.mp4")


def extract_audio_to_wav(video_file):
    """提取音訊為 16kHz mono WAV"""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    r = subprocess.run([
        "ffmpeg", "-y", "-i", video_file,
        "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", tmp.name
    ], capture_output=True)
    return tmp.name if r.returncode == 0 else None


def split_into_sentences(full_text, word_segments):
    """
    用完整文本的標點來切句子，再對齊 word_segments 的時間戳。
    full_text 有標點，word_segments 是逐字（無標點）。
    """
    if not word_segments or not full_text:
        return []

    sentence_ends = set("。！？!?.；;…")
    clause_ends = set("，,、：:")

    # 建立字元到 word_segment 的映射（跳過標點）
    seg_idx = 0
    char_times = []  # [(char, start, end), ...]

    for ch in full_text:
        if ch in sentence_ends or ch in clause_ends or ch in " \n\t\"'""''「」『』（）()【】":
            char_times.append((ch, None, None))  # 標點沒有時間
        else:
            if seg_idx < len(word_segments):
                ws = word_segments[seg_idx]
                char_times.append((ch, ws["start"], ws["end"]))
                seg_idx += 1
            else:
                char_times.append((ch, None, None))

    # 按標點切句子
    sentences = []
    current_chars = []
    current_start = None
    current_end = None

    for ch, start, end in char_times:
        current_chars.append(ch)
        if start is not None and current_start is None:
            current_start = start
        if end is not None:
            current_end = end

        if ch in sentence_ends:
            text = "".join(current_chars).strip()
            if text and current_start is not None:
                sentences.append({
                    "start": current_start,
                    "end": current_end,
                    "text": text,
                })
            current_chars = []
            current_start = None
            current_end = None
        elif ch in clause_ends and len(current_chars) > 25:
            text = "".join(current_chars).strip()
            if text and current_start is not None:
                sentences.append({
                    "start": current_start,
                    "end": current_end,
                    "text": text,
                })
            current_chars = []
            current_start = None
            current_end = None

    # 剩餘
    if current_chars:
        text = "".join(current_chars).strip()
        if text and current_start is not None:
            sentences.append({
                "start": current_start,
                "end": current_end,
                "text": text,
            })

    return sentences


def main():
    print("=" * 60)
    print("Qwen3-ASR + pyannote Pipeline 測試")
    print("=" * 60)
    total_start = time.time()
    stage_times = {}

    # === Step 1: Qwen3-ASR 轉錄 ===
    print("\n[1/3] Qwen3-ASR 0.6B 轉錄中...")
    asr_start = time.time()

    from mlx_qwen3_asr import transcribe
    result = transcribe(
        AUDIO,
        model="Qwen/Qwen3-ASR-0.6B",
        language=None,
        return_timestamps=True,
        verbose=False,
    )

    asr_time = time.time() - asr_start
    stage_times["asr"] = asr_time
    audio_duration = 60.0  # sample-01.mp4

    print(f"  語言: {result.language}")
    print(f"  文字: {len(result.text)} chars")
    print(f"  word segments: {len(result.segments)} 個")
    print(f"  耗時: {asr_time:.2f}s (RTF: {asr_time/audio_duration:.3f})")

    # 切成句子（用完整文本的標點 + word segments 的時間）
    sentences = split_into_sentences(result.text, result.segments)
    print(f"  切句後: {len(sentences)} 個句子")

    # 釋放 ASR 記憶體
    del result
    gc.collect()
    try:
        import mlx.core as mx
        mx.clear_cache()
    except:
        pass
    time.sleep(0.5)
    print("  ✓ ASR 記憶體已釋放")

    # === Step 2: pyannote diarization ===
    print("\n[2/3] pyannote 說話者分離中...")
    diar_start = time.time()

    import torch
    from pyannote.audio import Pipeline as PyannotePipeline

    wav_path = extract_audio_to_wav(AUDIO)
    if not wav_path:
        print("  ✗ 音訊提取失敗")
        return

    pipeline = PyannotePipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=HF_TOKEN,
    )
    if torch.backends.mps.is_available():
        pipeline.to(torch.device("mps"))
        print("  使用 MPS GPU")

    diarization_result = pipeline(wav_path)

    speaker_timeline = []
    annotation = diarization_result.speaker_diarization
    for segment, _, speaker in annotation.itertracks(yield_label=True):
        speaker_timeline.append({
            "start": float(segment.start),
            "end": float(segment.end),
            "speaker": speaker,
        })

    num_speakers = len(set(s["speaker"] for s in speaker_timeline))
    diar_time = time.time() - diar_start
    stage_times["diarization"] = diar_time
    print(f"  偵測到 {num_speakers} 位說話者")
    print(f"  耗時: {diar_time:.2f}s (RTF: {diar_time/audio_duration:.3f})")

    # 清理
    del pipeline, diarization_result
    gc.collect()
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    os.unlink(wav_path)

    # === Step 3: 合併 ===
    print("\n[3/3] 合併結果...")
    merged = []
    for i, seg in enumerate(sentences, 1):
        mid = (seg["start"] + seg["end"]) / 2
        speaker = "Unknown"
        for sp in speaker_timeline:
            if sp["start"] <= mid <= sp["end"]:
                speaker = sp["speaker"]
                break
        merged.append({
            "index": i,
            "start": seg["start"],
            "end": seg["end"],
            "speaker": speaker,
            "text": seg["text"],
        })

    # === 輸出 ===
    total_time = time.time() - total_start

    print("\n" + "=" * 60)
    print("轉錄結果 (SRT 格式)")
    print("=" * 60)
    for seg in merged:
        s = seg["start"]
        e = seg["end"]
        print(f"\n{seg['index']}")
        print(f"{int(s//3600):02d}:{int(s%3600//60):02d}:{s%60:06.3f} --> "
              f"{int(e//3600):02d}:{int(e%3600//60):02d}:{e%60:06.3f}")
        print(f"[{seg['speaker']}] {seg['text']}")

    print("\n" + "=" * 60)
    print("統計")
    print("=" * 60)
    print(f"  音檔長度: {audio_duration:.1f}s")
    print(f"  ASR 耗時: {stage_times['asr']:.2f}s ({stage_times['asr']/audio_duration:.3f}x)")
    print(f"  Diarization 耗時: {stage_times['diarization']:.2f}s ({stage_times['diarization']/audio_duration:.3f}x)")
    print(f"  總耗時: {total_time:.2f}s ({total_time/audio_duration:.3f}x)")
    print(f"  說話者: {num_speakers} 位")
    print(f"  句子數: {len(merged)}")


if __name__ == "__main__":
    main()

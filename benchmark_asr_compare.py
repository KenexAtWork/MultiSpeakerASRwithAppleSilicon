#!/usr/bin/env python3
"""
效能比較：MLX Whisper medium vs Qwen3-ASR 0.6B
兩者都搭配 pyannote diarization (MPS GPU)
使用同一個 sample file: examples/sample-01.mp4
"""
import os, sys, time, gc, subprocess, tempfile, json

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
AUDIO_DURATION = 60.0


def extract_wav(video_file):
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    subprocess.run([
        "ffmpeg", "-y", "-i", video_file,
        "-ac", "1", "-ar", "16000", "-acodec", "pcm_s16le", tmp.name
    ], capture_output=True)
    return tmp.name


def run_diarization(wav_path):
    """pyannote diarization — 共用部分"""
    import torch
    from pyannote.audio import Pipeline as PyannotePipeline

    t0 = time.time()
    pipeline = PyannotePipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1", token=HF_TOKEN)
    if torch.backends.mps.is_available():
        pipeline.to(torch.device("mps"))

    result = pipeline(wav_path)
    annotation = result.speaker_diarization

    timeline = []
    for seg, _, spk in annotation.itertracks(yield_label=True):
        timeline.append({"start": float(seg.start), "end": float(seg.end), "speaker": spk})

    elapsed = time.time() - t0
    num_speakers = len(set(s["speaker"] for s in timeline))

    del pipeline, result
    gc.collect()
    import torch as _torch
    if _torch.backends.mps.is_available():
        _torch.mps.empty_cache()

    return timeline, num_speakers, elapsed


def run_whisper_asr():
    """MLX Whisper medium ASR"""
    import mlx_whisper

    t0 = time.time()
    result = mlx_whisper.transcribe(
        AUDIO,
        path_or_hf_repo="mlx-community/whisper-medium-mlx",
        language="zh",
        word_timestamps=True,
        verbose=False,
    )
    elapsed = time.time() - t0

    segments = result["segments"]
    full_text = result.get("text", "")
    lang = result.get("language", "unknown")
    num_segments = len(segments)

    del result
    gc.collect()
    try:
        import mlx.core as mx
        mx.clear_cache()
    except:
        pass

    return segments, full_text, lang, num_segments, elapsed


def run_qwen3_asr():
    """Qwen3-ASR 0.6B"""
    from mlx_qwen3_asr import transcribe

    t0 = time.time()
    result = transcribe(
        AUDIO,
        model="Qwen/Qwen3-ASR-0.6B",
        language=None,
        return_timestamps=True,
        verbose=False,
    )
    elapsed = time.time() - t0

    full_text = result.text
    lang = result.language
    word_segs = result.segments  # character-level

    # 用標點切句子
    segments = split_qwen3_sentences(full_text, word_segs)

    del result
    gc.collect()
    try:
        import mlx.core as mx
        mx.clear_cache()
    except:
        pass

    return segments, full_text, lang, len(segments), elapsed


def split_qwen3_sentences(full_text, word_segments):
    """把 Qwen3 逐字結果按標點切成句子"""
    if not word_segments or not full_text:
        return []

    sentence_ends = set("。！？!?.；;…")
    clause_ends = set("，,、：:")
    skip_chars = set(" \n\t\"'""''「」『』（）()【】")

    seg_idx = 0
    char_times = []
    for ch in full_text:
        if ch in sentence_ends or ch in clause_ends or ch in skip_chars:
            char_times.append((ch, None, None))
        else:
            if seg_idx < len(word_segments):
                ws = word_segments[seg_idx]
                char_times.append((ch, ws["start"], ws["end"]))
                seg_idx += 1
            else:
                char_times.append((ch, None, None))

    sentences = []
    cur_chars, cur_start, cur_end = [], None, None

    for ch, start, end in char_times:
        cur_chars.append(ch)
        if start is not None and cur_start is None:
            cur_start = start
        if end is not None:
            cur_end = end

        if ch in sentence_ends or (ch in clause_ends and len(cur_chars) > 25):
            text = "".join(cur_chars).strip()
            if text and cur_start is not None:
                sentences.append({"start": cur_start, "end": cur_end, "text": text})
            cur_chars, cur_start, cur_end = [], None, None

    if cur_chars:
        text = "".join(cur_chars).strip()
        if text and cur_start is not None:
            sentences.append({"start": cur_start, "end": cur_end, "text": text})

    return sentences


def merge_results(segments, speaker_timeline, is_whisper=True):
    """合併 ASR segments + speaker timeline"""
    merged = []
    for i, seg in enumerate(segments, 1):
        if is_whisper:
            mid = (seg["start"] + seg["end"]) / 2
            text = seg["text"].strip()
        else:
            mid = (seg["start"] + seg["end"]) / 2
            text = seg["text"]

        speaker = "Unknown"
        for sp in speaker_timeline:
            if sp["start"] <= mid <= sp["end"]:
                speaker = sp["speaker"]
                break
        merged.append({"index": i, "start": seg["start"], "end": seg["end"],
                        "speaker": speaker, "text": text})
    return merged


def print_srt(merged, label):
    print(f"\n{'='*60}")
    print(f"{label} — 前 5 段")
    print(f"{'='*60}")
    for seg in merged[:5]:
        s, e = seg["start"], seg["end"]
        print(f"  [{s:6.2f}s-{e:6.2f}s] {seg['speaker']}: {seg['text']}")


def main():
    print("=" * 70)
    print("  效能比較: MLX Whisper medium vs Qwen3-ASR 0.6B")
    print("  音檔: sample-01.mp4 (60s, 2 speakers)")
    print("  Diarization: pyannote 3.1 (MPS GPU)")
    print("=" * 70)

    # 先提取 WAV（共用）
    wav_path = extract_wav(AUDIO)

    results = {}

    # === Test 1: MLX Whisper medium ===
    print("\n" + "-" * 50)
    print("[A] MLX Whisper medium + pyannote")
    print("-" * 50)

    print("  ASR 中...")
    w_segs, w_text, w_lang, w_nseg, w_asr_time = run_whisper_asr()
    print(f"  ASR 完成: {w_asr_time:.2f}s (RTF {w_asr_time/AUDIO_DURATION:.3f})")
    time.sleep(1)

    print("  Diarization 中...")
    w_timeline, w_nspk, w_diar_time = run_diarization(wav_path)
    print(f"  Diarization 完成: {w_diar_time:.2f}s (RTF {w_diar_time/AUDIO_DURATION:.3f})")

    w_merged = merge_results(w_segs, w_timeline, is_whisper=True)
    w_total = w_asr_time + w_diar_time

    results["whisper"] = {
        "asr_time": w_asr_time, "diar_time": w_diar_time, "total": w_total,
        "segments": w_nseg, "speakers": w_nspk, "text_len": len(w_text),
        "lang": w_lang,
    }

    del w_segs, w_timeline
    gc.collect()
    time.sleep(2)

    # === Test 2: Qwen3-ASR 0.6B ===
    print("\n" + "-" * 50)
    print("[B] Qwen3-ASR 0.6B + pyannote")
    print("-" * 50)

    print("  ASR 中...")
    q_segs, q_text, q_lang, q_nseg, q_asr_time = run_qwen3_asr()
    print(f"  ASR 完成: {q_asr_time:.2f}s (RTF {q_asr_time/AUDIO_DURATION:.3f})")
    time.sleep(1)

    print("  Diarization 中...")
    q_timeline, q_nspk, q_diar_time = run_diarization(wav_path)
    print(f"  Diarization 完成: {q_diar_time:.2f}s (RTF {q_diar_time/AUDIO_DURATION:.3f})")

    q_merged = merge_results(q_segs, q_timeline, is_whisper=False)
    q_total = q_asr_time + q_diar_time

    results["qwen3"] = {
        "asr_time": q_asr_time, "diar_time": q_diar_time, "total": q_total,
        "segments": q_nseg, "speakers": q_nspk, "text_len": len(q_text),
        "lang": q_lang,
    }

    # 清理
    os.unlink(wav_path)

    # === 輸出比較 ===
    print_srt(w_merged, "Whisper medium")
    print_srt(q_merged, "Qwen3-ASR 0.6B")

    print(f"\n{'='*70}")
    print(f"{'指標':<25} {'Whisper medium':>18} {'Qwen3-ASR 0.6B':>18}")
    print(f"{'='*70}")

    w, q = results["whisper"], results["qwen3"]
    print(f"{'ASR 耗時':<25} {w['asr_time']:>15.2f}s {q['asr_time']:>15.2f}s")
    print(f"{'ASR RTF':<25} {w['asr_time']/AUDIO_DURATION:>15.3f}x {q['asr_time']/AUDIO_DURATION:>15.3f}x")
    print(f"{'Diarization 耗時':<25} {w['diar_time']:>15.2f}s {q['diar_time']:>15.2f}s")
    print(f"{'總耗時':<25} {w['total']:>15.2f}s {q['total']:>15.2f}s")
    print(f"{'總 RTF':<25} {w['total']/AUDIO_DURATION:>15.3f}x {q['total']/AUDIO_DURATION:>15.3f}x")
    print(f"{'段落數':<25} {w['segments']:>15} {q['segments']:>15}")
    print(f"{'說話者數':<25} {w['speakers']:>15} {q['speakers']:>15}")
    print(f"{'文字長度':<25} {w['text_len']:>15} {q['text_len']:>15}")
    print(f"{'偵測語言':<25} {w['lang']:>15} {q['lang']:>15}")
    print(f"{'模型大小 (RAM)':<25} {'~5-7 GB':>15} {'~1.2 GB':>15}")
    print(f"{'='*70}")

    # 存結果
    out_path = os.path.join(os.path.dirname(__file__), "benchmark_results", "qwen3_vs_whisper.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n結果已存: {out_path}")


if __name__ == "__main__":
    main()

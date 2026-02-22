#!/usr/bin/env python3
"""
4-way 效能比較 (完整 sample-01.mp4, 60s, 2 speakers)
1. MLX Whisper medium + pyannote
2. MLX Whisper base + pyannote
3. Qwen3-ASR 0.6B + pyannote
4. Qwen3-ASR 1.7B + pyannote
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

    del pipeline, result, annotation
    gc.collect()
    import torch as _t
    if _t.backends.mps.is_available():
        _t.mps.empty_cache()

    return timeline, num_speakers, elapsed


def run_whisper(model_name, model_path):
    import mlx_whisper

    t0 = time.time()
    result = mlx_whisper.transcribe(
        AUDIO,
        path_or_hf_repo=model_path,
        language="zh",
        word_timestamps=True,
        verbose=False,
    )
    elapsed = time.time() - t0

    segments = result["segments"]
    full_text = result.get("text", "")
    lang = result.get("language", "unknown")

    del result
    gc.collect()
    try:
        import mlx.core as mx
        mx.clear_cache()
    except:
        pass

    return segments, full_text, lang, elapsed


def run_qwen3(model_id):
    from mlx_qwen3_asr import transcribe

    t0 = time.time()
    result = transcribe(
        AUDIO,
        model=model_id,
        language=None,
        return_timestamps=True,
        verbose=False,
    )
    elapsed = time.time() - t0

    full_text = result.text
    lang = result.language
    word_segs = result.segments

    segments = split_qwen3_sentences(full_text, word_segs)

    del result
    gc.collect()
    try:
        import mlx.core as mx
        mx.clear_cache()
    except:
        pass

    return segments, full_text, lang, elapsed


def split_qwen3_sentences(full_text, word_segments):
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


def merge_results(segments, speaker_timeline):
    merged = []
    for i, seg in enumerate(segments, 1):
        mid = (seg["start"] + seg["end"]) / 2
        text = seg.get("text", "").strip()
        speaker = "Unknown"
        for sp in speaker_timeline:
            if sp["start"] <= mid <= sp["end"]:
                speaker = sp["speaker"]
                break
        merged.append({"index": i, "start": seg["start"], "end": seg["end"],
                        "speaker": speaker, "text": text})
    return merged


CONFIGS = [
    ("Whisper medium", "whisper", "mlx-community/whisper-medium-mlx", "~5-7 GB"),
    ("Whisper base", "whisper", "mlx-community/whisper-base-mlx", "~140 MB"),
    ("Qwen3-ASR 0.6B", "qwen3", "Qwen/Qwen3-ASR-0.6B", "~1.2 GB"),
    ("Qwen3-ASR 1.7B", "qwen3", "Qwen/Qwen3-ASR-1.7B", "~3.4 GB"),
]


def main():
    print("=" * 75)
    print("  4-Way ASR Benchmark: sample-01.mp4 (60s, 2 speakers)")
    print("  All with pyannote speaker-diarization-3.1 (MPS GPU)")
    print("=" * 75)

    wav_path = extract_wav(AUDIO)
    all_results = {}

    for label, engine, model_path, ram in CONFIGS:
        print(f"\n{'─'*60}")
        print(f"  [{label}]  (RAM: {ram})")
        print(f"{'─'*60}")

        # ASR
        print(f"  ASR 中...")
        if engine == "whisper":
            segments, full_text, lang, asr_time = run_whisper(label, model_path)
        else:
            segments, full_text, lang, asr_time = run_qwen3(model_path)
        print(f"  ASR: {asr_time:.2f}s (RTF {asr_time/AUDIO_DURATION:.3f})")

        time.sleep(2)  # 讓記憶體釋放

        # Diarization
        print(f"  Diarization 中...")
        timeline, nspk, diar_time = run_diarization(wav_path)
        print(f"  Diar: {diar_time:.2f}s (RTF {diar_time/AUDIO_DURATION:.3f})")

        # Merge
        merged = merge_results(segments, timeline)
        total = asr_time + diar_time

        # 前 3 段
        print(f"  前 3 段:")
        for seg in merged[:3]:
            print(f"    [{seg['start']:5.1f}s-{seg['end']:5.1f}s] {seg['speaker']}: {seg['text'][:50]}")

        all_results[label] = {
            "asr_time": round(asr_time, 2),
            "diar_time": round(diar_time, 2),
            "total": round(total, 2),
            "asr_rtf": round(asr_time / AUDIO_DURATION, 3),
            "total_rtf": round(total / AUDIO_DURATION, 3),
            "segments": len(segments),
            "speakers": nspk,
            "text_len": len(full_text),
            "lang": lang,
            "ram": ram,
        }

        del segments, timeline, merged
        gc.collect()
        time.sleep(2)

    os.unlink(wav_path)

    # === 總表 ===
    labels = [c[0] for c in CONFIGS]
    print(f"\n{'='*90}")
    print(f"{'指標':<20}", end="")
    for lb in labels:
        print(f"{lb:>17}", end="")
    print(f"\n{'='*90}")

    rows = [
        ("ASR 耗時", lambda r: f"{r['asr_time']:.2f}s"),
        ("ASR RTF", lambda r: f"{r['asr_rtf']:.3f}x"),
        ("Diar 耗時", lambda r: f"{r['diar_time']:.2f}s"),
        ("總耗時", lambda r: f"{r['total']:.2f}s"),
        ("總 RTF", lambda r: f"{r['total_rtf']:.3f}x"),
        ("段落數", lambda r: f"{r['segments']}"),
        ("說話者", lambda r: f"{r['speakers']}"),
        ("文字長度", lambda r: f"{r['text_len']}"),
        ("語言", lambda r: f"{r['lang']}"),
        ("RAM", lambda r: f"{r['ram']}"),
    ]

    for row_label, fmt_fn in rows:
        print(f"{row_label:<20}", end="")
        for lb in labels:
            print(f"{fmt_fn(all_results[lb]):>17}", end="")
        print()

    print(f"{'='*90}")

    # 存結果
    out = os.path.join(os.path.dirname(__file__), "benchmark_results", "4way_benchmark.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n結果已存: {out}")


if __name__ == "__main__":
    main()

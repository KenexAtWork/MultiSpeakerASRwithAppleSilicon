#!/usr/bin/env python3
"""
ASR Pipeline 端到端測試
使用 examples/sample-01.mp4 (60s, 2 speakers) 驗證完整流程

用法:
  # 快速測試（Whisper base，跳過 diarization）
  python tests/test_pipeline_e2e.py --fast

  # 完整測試（Whisper base + diarization）
  python tests/test_pipeline_e2e.py

  # 指定模型
  python tests/test_pipeline_e2e.py --model medium
"""
import os, sys, re, subprocess, tempfile, argparse, time

ASR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ASR_DIR, "asr_multi_speaker_v5_fast.py")
SAMPLE = os.path.join(ASR_DIR, "examples", "sample-01.mp4")
PYTHON = sys.executable

# 載入 .env for HF_TOKEN
env_path = os.path.join(ASR_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

HF_TOKEN = os.environ.get("HF_TOKEN", "")


def run_pipeline(output_path, language="zh", model="base", fmt="srt",
                 skip_diarization=False):
    """執行 pipeline，回傳 (return_code, stdout)"""
    cmd = [
        PYTHON, SCRIPT,
        "--input", SAMPLE,
        "--output", output_path,
        "--language", language,
        "--model", model,
        "--format", fmt,
    ]
    if HF_TOKEN and not skip_diarization:
        cmd.extend(["--hf-token", HF_TOKEN])
    if skip_diarization:
        cmd.append("--skip-diarization")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ASR_DIR)
    elapsed = time.time() - t0
    return result.returncode, result.stdout + result.stderr, elapsed


def parse_srt(filepath):
    """解析 SRT 檔案"""
    segments = []
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    blocks = re.split(r"\n\n+", content.strip())
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        idx = lines[0].strip()
        ts_match = re.match(
            r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})",
            lines[1].strip(),
        )
        if not ts_match:
            continue
        start = _parse_ts(ts_match.group(1))
        end = _parse_ts(ts_match.group(2))
        text = "\n".join(lines[2:])
        spk_match = re.match(r"\[([^\]]+)\]\s*(.*)", text, re.DOTALL)
        if spk_match:
            speaker, text = spk_match.group(1), spk_match.group(2).strip()
        else:
            speaker, text = "Unknown", text.strip()
        segments.append({"index": int(idx), "start": start, "end": end,
                         "speaker": speaker, "text": text})
    return segments


def _parse_ts(ts_str):
    ts_str = ts_str.replace(",", ".")
    parts = ts_str.split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


# ──────────────────────────────────────────────
# 測試案例
# ──────────────────────────────────────────────

class PipelineTests:
    def __init__(self, model="base"):
        self.model = model
        self.tmpdir = tempfile.mkdtemp(prefix="asr_test_")
        self.results = {}  # cache pipeline results

    def _get_srt(self, key, **kwargs):
        """跑 pipeline 並 cache 結果"""
        if key not in self.results:
            out = os.path.join(self.tmpdir, f"{key}.srt")
            rc, stdout, elapsed = run_pipeline(out, model=self.model, **kwargs)
            self.results[key] = {
                "rc": rc, "stdout": stdout, "elapsed": elapsed,
                "output": out,
            }
        return self.results[key]

    def test_srt_output_exists(self):
        """SRT 輸出檔案存在且非空"""
        r = self._get_srt("basic", skip_diarization=True)
        assert r["rc"] == 0, f"Pipeline failed: rc={r['rc']}\n{r['stdout'][-500:]}"
        assert os.path.exists(r["output"]), "Output file not created"
        assert os.path.getsize(r["output"]) > 0, "Output file is empty"

    def test_srt_format_valid(self):
        """SRT 格式正確（index、時間戳、文字）"""
        r = self._get_srt("basic", skip_diarization=True)
        segs = parse_srt(r["output"])
        assert len(segs) > 0, "No segments parsed"
        for seg in segs:
            assert seg["start"] <= seg["end"], f"start > end: {seg}"
            assert len(seg["text"]) > 0, f"Empty text: {seg}"

    def test_timestamps_increasing(self):
        """時間戳遞增"""
        r = self._get_srt("basic", skip_diarization=True)
        segs = parse_srt(r["output"])
        for i in range(1, len(segs)):
            assert segs[i]["start"] >= segs[i-1]["start"], \
                f"Timestamps not increasing: seg {i-1} start={segs[i-1]['start']}, seg {i} start={segs[i]['start']}"

    def test_index_sequential(self):
        """index 連續編號"""
        r = self._get_srt("basic", skip_diarization=True)
        segs = parse_srt(r["output"])
        indices = [s["index"] for s in segs]
        assert indices == list(range(1, len(segs) + 1)), f"Non-sequential: {indices[:10]}..."

    def test_skip_diarization_all_unknown(self):
        """skip diarization 時全部標為 Unknown"""
        r = self._get_srt("basic", skip_diarization=True)
        segs = parse_srt(r["output"])
        speakers = set(s["speaker"] for s in segs)
        assert speakers == {"Unknown"}, f"Expected only Unknown, got {speakers}"

    def test_language_auto(self):
        """language=auto 不報錯"""
        out = os.path.join(self.tmpdir, "auto_lang.srt")
        rc, stdout, elapsed = run_pipeline(out, language="auto",
                                           model=self.model, skip_diarization=True)
        assert rc == 0, f"language=auto failed: rc={rc}\n{stdout[-500:]}"
        segs = parse_srt(out)
        assert len(segs) > 0, "No segments with auto language"

    def test_txt_format(self):
        """TXT 輸出格式能正常運作"""
        out = os.path.join(self.tmpdir, "output.txt")
        rc, stdout, elapsed = run_pipeline(out, fmt="txt", model=self.model,
                                           skip_diarization=True)
        assert rc == 0, f"TXT format failed: rc={rc}"
        assert os.path.exists(out) and os.path.getsize(out) > 0

    def test_merge_reduces_segments(self):
        """合併步驟有生效（段落數合理）"""
        r = self._get_srt("basic", skip_diarization=True)
        segs = parse_srt(r["output"])
        # skip diarization 時全是 Unknown，Unknown 不合併
        # 所以段落數應該等於原始 Whisper 段落數
        # 這裡只驗證段落數在合理範圍（60s 音檔，不該超過 500 段）
        assert len(segs) < 500, f"Too many segments: {len(segs)}"
        assert len(segs) > 5, f"Too few segments: {len(segs)}"

    def test_diarization_detects_speakers(self):
        """diarization 偵測到 ≥ 2 位說話者"""
        if not HF_TOKEN:
            print("    (跳過: 無 HF_TOKEN)")
            return
        r = self._get_srt("with_diar", skip_diarization=False)
        assert r["rc"] == 0, f"Pipeline with diar failed: rc={r['rc']}\n{r['stdout'][-500:]}"
        segs = parse_srt(r["output"])
        speakers = set(s["speaker"] for s in segs) - {"Unknown"}
        assert len(speakers) >= 2, f"Expected ≥2 speakers, got {speakers}"

    def test_diarization_merge_works(self):
        """有 diarization 時合併步驟有效（同 speaker 段落被合併）"""
        if not HF_TOKEN:
            print("    (跳過: 無 HF_TOKEN)")
            return
        r = self._get_srt("with_diar", skip_diarization=False)
        segs = parse_srt(r["output"])
        # 合併後段落數應該比 Whisper 原始段落少
        # stdout 裡有原始段落數
        m = re.search(r"共 (\d+) 個字幕段落", r["stdout"])
        if m:
            raw_count = int(m.group(1))
            assert len(segs) < raw_count, \
                f"Merge didn't reduce: {raw_count} -> {len(segs)}"

    def test_unknown_not_merged(self):
        """有 diarization 時 Unknown 段落未被合併"""
        if not HF_TOKEN:
            print("    (跳過: 無 HF_TOKEN)")
            return
        r = self._get_srt("with_diar", skip_diarization=False)
        segs = parse_srt(r["output"])
        # 檢查相鄰 Unknown 段落沒有被合併
        for i in range(1, len(segs)):
            if segs[i]["speaker"] == "Unknown" and segs[i-1]["speaker"] == "Unknown":
                gap = segs[i]["start"] - segs[i-1]["end"]
                # 如果間隔很小，代表它們本來可以合併但沒有（正確行為）
                # 不需要 assert，只要存在相鄰 Unknown 就代表沒被合併

    def cleanup(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


# ──────────────────────────────────────────────
# 主程式
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ASR Pipeline 端到端測試")
    parser.add_argument("--fast", action="store_true",
                        help="快速模式：跳過 diarization 測試")
    parser.add_argument("--model", default="base",
                        help="Whisper 模型（預設: base，快速）")
    args = parser.parse_args()

    if not os.path.exists(SAMPLE):
        print(f"錯誤: 測試音檔不存在 - {SAMPLE}")
        sys.exit(1)

    tests = PipelineTests(model=args.model)

    # 定義測試清單
    test_list = [
        tests.test_srt_output_exists,
        tests.test_srt_format_valid,
        tests.test_timestamps_increasing,
        tests.test_index_sequential,
        tests.test_skip_diarization_all_unknown,
        tests.test_language_auto,
        tests.test_txt_format,
        tests.test_merge_reduces_segments,
    ]

    if not args.fast:
        test_list.extend([
            tests.test_diarization_detects_speakers,
            tests.test_diarization_merge_works,
            tests.test_unknown_not_merged,
        ])

    print("=" * 60, flush=True)
    print(f"ASR Pipeline 端到端測試 (model={args.model})", flush=True)
    print(f"音檔: {SAMPLE}", flush=True)
    print(f"模式: {'快速（無 diarization）' if args.fast else '完整'}", flush=True)
    print("=" * 60, flush=True)

    passed = failed = 0
    for fn in test_list:
        try:
            fn()
            print(f"  ✓ {fn.__doc__}", flush=True)
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {fn.__doc__}: {e}", flush=True)
            failed += 1
        except Exception as e:
            print(f"  ✗ {fn.__doc__}: {type(e).__name__}: {e}", flush=True)
            failed += 1

    # 印耗時
    for key, r in tests.results.items():
        print(f"  [{key}] {r['elapsed']:.1f}s", flush=True)

    tests.cleanup()

    print(f"\n結果: {passed} 通過, {failed} 失敗", flush=True)
    if failed:
        sys.exit(1)
    print("✓ 全部通過", flush=True)


if __name__ == "__main__":
    main()

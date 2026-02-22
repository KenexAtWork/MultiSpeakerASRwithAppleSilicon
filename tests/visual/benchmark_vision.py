#!/usr/bin/env python3
"""
比較不同 Bedrock multimodal 模型在 UI 截圖座標定位的準確度

用法:
  python benchmark_vision.py <screenshot_with_grid.png>

測試圖片需已疊加座標網格（由 snap.py 或 overlay_grid.py 產生）。
結果存為同目錄下的 benchmark_results.json。
"""
import boto3
import json
import time
import sys
from pathlib import Path

REGION = "us-west-2"

# 候選模型（支援 image input + text output）
MODELS = [
    ("Claude Sonnet 4.6", "us.anthropic.claude-sonnet-4-6"),
    ("Claude Opus 4.6",   "us.anthropic.claude-opus-4-6-v1"),
    ("Nova Pro v1",       "us.amazon.nova-pro-v1:0"),
]

# 統一 prompt — 要求結構化輸出，方便自動比對
PROMPT = """This screenshot has a RED coordinate grid overlay on a fullscreen Mac Retina display.
- Red numbers along the TOP edge = X coordinates (logical screen pixels)
- Red numbers along the LEFT edge = Y coordinates (logical screen pixels)
- Major grid lines every 100 units, minor lines every 50 units.

A GUI window is in the upper-left area, starting around x=52, y=33, size 800x728.

Find these UI elements and report their coordinates by reading the nearest grid line numbers.

Answer ONLY in this exact format, one per line, no extra text:
SELECT_FILE_BTN: x,y
MODEL_DROPDOWN_ARROW: x,y
SKIP_DIARIZATION_CB: x,y
GPU_ACCEL_CB: x,y
START_BTN: x,y
MODEL_TEXT: <exact text in model dropdown>
SKIP_DIARIZATION_CHECKED: yes/no
GPU_ACCEL_CHECKED: yes/no"""


def run_model(client, model_id, image_bytes):
    """呼叫單一模型，回傳 (response_text, latency_sec, error)"""
    t0 = time.time()
    try:
        resp = client.converse(
            modelId=model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"image": {"format": "png", "source": {"bytes": image_bytes}}},
                    {"text": PROMPT}
                ]
            }],
            inferenceConfig={"maxTokens": 1024, "temperature": 0}
        )
        text = "".join(
            b["text"] for b in resp["output"]["message"]["content"] if "text" in b
        )
        return text.strip(), time.time() - t0, None
    except Exception as e:
        return "", time.time() - t0, str(e)


def parse_response(text):
    """解析結構化回應為 dict"""
    result = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip()
    return result


def main():
    if len(sys.argv) < 2:
        print("用法: python benchmark_vision.py <screenshot_with_grid.png>")
        sys.exit(1)

    image_path = sys.argv[1]
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    print(f"圖片: {image_path}")
    print(f"Region: {REGION}")
    print(f"測試 {len(MODELS)} 個模型")
    print(f"Prompt:\n{PROMPT[:100]}...\n")

    client = boto3.Session().client("bedrock-runtime", region_name=REGION)
    results = []

    for name, model_id in MODELS:
        print(f"{'='*60}")
        print(f"▶ {name} ({model_id})")
        print(f"{'='*60}")

        text, latency, error = run_model(client, model_id, image_bytes)

        entry = {
            "name": name,
            "model_id": model_id,
            "latency_sec": round(latency, 1),
            "error": error,
            "raw_response": text,
            "parsed": parse_response(text) if not error else {}
        }
        results.append(entry)

        if error:
            print(f"  ❌ 錯誤: {error}")
            print(f"  延遲: {latency:.1f}s\n")
            continue

        print(f"  延遲: {latency:.1f}s")
        print(f"  回應:")
        for line in text.strip().split("\n"):
            print(f"    {line}")
        print()

    # 儲存結果
    out_path = Path(image_path).parent / "benchmark_results.json"
    report = {
        "image": image_path,
        "region": REGION,
        "prompt": PROMPT,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": results
    }
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n✓ 結果已儲存: {out_path}")

    # 摘要比較表
    print(f"\n{'='*60}")
    print("摘要比較")
    print(f"{'='*60}")
    print(f"{'模型':<22} {'延遲':>6} {'SELECT_FILE':>14} {'START_BTN':>12} {'MODEL_TEXT':>20} {'GPU✓':>5} {'SKIP✓':>5}")
    print("-" * 90)
    for r in results:
        p = r["parsed"]
        print(f"{r['name']:<22} {r['latency_sec']:>5.1f}s "
              f"{p.get('SELECT_FILE_BTN','?'):>14} "
              f"{p.get('START_BTN','?'):>12} "
              f"{p.get('MODEL_TEXT','?'):>20} "
              f"{p.get('GPU_ACCEL_CHECKED','?'):>5} "
              f"{p.get('SKIP_DIARIZATION_CHECKED','?'):>5}")


if __name__ == "__main__":
    main()

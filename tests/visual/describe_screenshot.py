#!/usr/bin/env python3
"""
Visual UI Testing Tool — 透過 macOS screencapture + AWS Bedrock Claude 進行 UI 視覺驗證

用法:
  # 列出所有視窗
  python describe_screenshot.py --list

  # 截圖指定視窗並描述
  python describe_screenshot.py --window-id 1234 --prompt "檢查按鈕數量"

  # 截圖指定 App 的視窗並描述
  python describe_screenshot.py --app Python --prompt "描述 UI 佈局"

  # 截圖全螢幕並描述
  python describe_screenshot.py --fullscreen --prompt "找到 ASR 視窗並描述"

  # 只截圖不分析
  python describe_screenshot.py --app Python --capture-only

  # 指定輸出檔名
  python describe_screenshot.py --app Python --output my_test.png

環境需求:
  - macOS（需授予螢幕錄製權限給執行此 script 的 terminal app）
  - AWS credentials（Bedrock 存取權限）
  - boto3
"""
import argparse
import subprocess
import sys
import os
import json
from pathlib import Path
from datetime import datetime

# 截圖存放目錄
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"


def list_windows(filter_app=None):
    """列出螢幕上的視窗，回傳 [{id, app, title}, ...]"""
    swift_code = """
import Quartz
let list = CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID) as! [[String: Any]]
for win in list {
    let owner = win["kCGWindowOwnerName"] as? String ?? "Unknown"
    let id = win["kCGWindowNumber"] as? Int ?? 0
    let name = win["kCGWindowName"] as? String ?? ""
    let layer = win["kCGWindowLayer"] as? Int ?? 0
    if layer == 0 {
        print("\\(id)|\\(owner)|\\(name)")
    }
}
"""
    result = subprocess.run(
        ["swift", "-e", swift_code],
        capture_output=True, text=True
    )
    windows = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) == 3:
            wid, app, title = parts
            if filter_app and filter_app.lower() not in app.lower():
                continue
            windows.append({"id": int(wid), "app": app, "title": title})
    return windows


def capture_window(window_id, output_path):
    """截取指定視窗，回傳截圖路徑"""
    result = subprocess.run(
        ["screencapture", "-l", str(window_id), str(output_path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"screencapture 失敗: {result.stderr}")
    if not output_path.exists():
        raise RuntimeError("截圖檔案未產生，可能缺少螢幕錄製權限")
    return output_path


def capture_fullscreen(output_path):
    """截取全螢幕"""
    result = subprocess.run(
        ["screencapture", "-x", str(output_path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"screencapture 失敗: {result.stderr}")
    if not output_path.exists():
        raise RuntimeError("截圖檔案未產生，可能缺少螢幕錄製權限")
    return output_path


def describe_image(image_path, prompt=None, region="ap-northeast-1",
                   model_id="apac.anthropic.claude-sonnet-4-20250514-v1:0"):
    """透過 Bedrock Claude 描述圖片內容，回傳文字描述"""
    import boto3

    if not prompt:
        prompt = (
            "請詳細描述這張截圖的 UI 內容，包括所有可見的按鈕、文字、"
            "輸入框、佈局等元素。使用繁體中文回答。"
        )

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # 偵測格式
    ext = Path(image_path).suffix.lower().lstrip(".")
    fmt = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")

    session = boto3.Session()
    client = session.client("bedrock-runtime", region_name=region)

    response = client.converse(
        modelId=model_id,
        messages=[{
            "role": "user",
            "content": [
                {"image": {"format": fmt, "source": {"bytes": image_bytes}}},
                {"text": prompt}
            ]
        }],
        inferenceConfig={"maxTokens": 2048, "temperature": 0}
    )

    output = response["output"]["message"]["content"]
    description = "".join(block["text"] for block in output if "text" in block)

    # 自動存 JSON log（與圖片同名）
    json_path = Path(image_path).with_suffix(".json")
    log_entry = {
        "image": str(image_path),
        "timestamp": datetime.now().isoformat(),
        "model": model_id,
        "region": region,
        "temperature": 0,
        "prompt": prompt,
        "response": description
    }
    json_path.write_text(json.dumps(log_entry, ensure_ascii=False, indent=2))

    return description


def generate_output_path(prefix="screenshot"):
    """產生帶時間戳的截圖路徑"""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return SCREENSHOT_DIR / f"{prefix}_{ts}.png"


def main():
    parser = argparse.ArgumentParser(
        description="Visual UI Testing — screencapture + Bedrock Claude 視覺驗證工具"
    )
    # 截圖目標（三選一）
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--window-id", type=int, help="指定視窗 ID")
    group.add_argument("--app", type=str, help="依 App 名稱搜尋視窗（模糊比對）")
    group.add_argument("--fullscreen", action="store_true", help="截取全螢幕")
    group.add_argument("--list", action="store_true", help="列出所有視窗")
    group.add_argument("--image", type=str, help="直接分析已存在的圖片檔")

    # 選項
    parser.add_argument("--prompt", "-p", type=str, help="給 Claude 的分析提示")
    parser.add_argument("--output", "-o", type=str, help="截圖輸出檔名（存在 screenshots/ 下）")
    parser.add_argument("--capture-only", action="store_true", help="只截圖不分析")
    parser.add_argument("--region", default="ap-northeast-1", help="AWS Bedrock region")
    parser.add_argument("--model", default="apac.anthropic.claude-sonnet-4-20250514-v1:0",
                        help="Bedrock model ID")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式輸出結果")

    args = parser.parse_args()

    # 列出視窗
    if args.list:
        windows = list_windows()
        if not windows:
            print("沒有找到視窗")
            return
        for w in windows:
            print(f"ID: {w['id']:>5} | App: {w['app']:<25} | Title: {w['title']}")
        return

    # 決定截圖路徑
    if args.image:
        image_path = Path(args.image)
        if not image_path.exists():
            print(f"錯誤: 檔案不存在 {args.image}", file=sys.stderr)
            sys.exit(1)
    else:
        if args.output:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            image_path = SCREENSHOT_DIR / args.output
        else:
            prefix = args.app or "screen" if not args.window_id else f"win_{args.window_id}"
            image_path = generate_output_path(prefix)

        # 截圖
        try:
            if args.fullscreen:
                capture_fullscreen(image_path)
            elif args.window_id:
                capture_window(args.window_id, image_path)
            elif args.app:
                windows = list_windows(filter_app=args.app)
                if not windows:
                    print(f"錯誤: 找不到 App '{args.app}' 的視窗", file=sys.stderr)
                    sys.exit(1)
                # 取第一個符合的視窗
                win = windows[0]
                print(f"截取視窗: ID={win['id']} App={win['app']} Title={win['title']}")
                capture_window(win["id"], image_path)
            else:
                parser.print_help()
                return
        except RuntimeError as e:
            print(f"錯誤: {e}", file=sys.stderr)
            sys.exit(1)

        print(f"截圖已儲存: {image_path}")

    if args.capture_only:
        return

    # 分析
    print("分析中...")
    description = describe_image(
        image_path, prompt=args.prompt,
        region=args.region, model_id=args.model
    )

    if args.json:
        result = {
            "image": str(image_path),
            "timestamp": datetime.now().isoformat(),
            "prompt": args.prompt,
            "description": description
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*60}")
        print(description)
        print(f"{'='*60}")


if __name__ == "__main__":
    main()

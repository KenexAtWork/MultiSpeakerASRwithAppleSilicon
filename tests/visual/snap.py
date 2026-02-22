#!/usr/bin/env python3
"""
整合截圖工具 — 全螢幕截圖 + 自動 grid overlay + Bedrock 分析 + JSON log

每次任務使用獨立時間戳資料夾，避免干擾。
一律使用全螢幕截圖 + 絕對座標。
截圖自動加上座標網格。

用法:
  # 初始化任務（建立時間戳資料夾，重置計數器）
  python snap.py init

  # 截圖 + grid + 分析
  python snap.py capture --prompt "描述 GUI 佈局"

  # 只截圖（不分析）
  python snap.py capture --no-analyze

  # 分析已存在的圖片
  python snap.py analyze --image path/to/screenshot.png --prompt "..."

  # 列出視窗
  python snap.py list
"""
import argparse
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

# 預設 Bedrock 設定 — Claude Sonnet 4.6 via us-west-2
DEFAULT_REGION = "us-west-2"
DEFAULT_MODEL = "us.anthropic.claude-sonnet-4-6"

BASE_DIR = Path(__file__).parent / "screenshots"


def _get_task_dir():
    """取得當前任務目錄（從 .current_task 讀取）"""
    marker = BASE_DIR / ".current_task"
    if marker.exists():
        name = marker.read_text().strip()
        d = BASE_DIR / name
        if d.exists():
            return d
    return None


def _get_counter(task_dir):
    cf = task_dir / "counter.txt"
    if cf.exists():
        return int(cf.read_text().strip())
    return 0


def _inc_counter(task_dir):
    n = _get_counter(task_dir) + 1
    (task_dir / "counter.txt").write_text(str(n))
    return n


def cmd_init(args):
    """初始化新任務資料夾"""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    task_dir = BASE_DIR / ts
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "counter.txt").write_text("0")
    (BASE_DIR / ".current_task").write_text(ts)
    print(f"✓ 任務資料夾: {task_dir}")
    return str(task_dir)


def cmd_list(args):
    """列出螢幕上的視窗"""
    swift_code = '''
import Quartz
let list = CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID) as! [[String: Any]]
for win in list {
    let owner = win["kCGWindowOwnerName"] as? String ?? "Unknown"
    let id = win["kCGWindowNumber"] as? Int ?? 0
    let name = win["kCGWindowName"] as? String ?? ""
    let layer = win["kCGWindowLayer"] as? Int ?? 0
    if layer == 0 { print("\\(id)|\\(owner)|\\(name)") }
}
'''
    r = subprocess.run(["swift", "-e", swift_code], capture_output=True, text=True)
    for line in r.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) == 3:
            print(f"ID: {parts[0]:>5} | App: {parts[1]:<25} | Title: {parts[2]}")


def overlay_grid(image_path, output_path=None, spacing=100, sub_spacing=50):
    """在圖片上疊加座標網格（Retina 2x，origin=0,0 全螢幕絕對座標）"""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(image_path).convert("RGBA")
    w, h = img.size
    scale = 2  # Retina

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    major_color = (255, 0, 0, 90)
    minor_color = (255, 0, 0, 40)
    text_color = (255, 0, 0, 180)

    font_size = 18
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", font_size)
    except (OSError, IOError):
        font = ImageFont.load_default()

    # 垂直線
    lx = 0
    while lx * scale <= w:
        px = lx * scale
        is_major = (lx % spacing == 0)
        draw.line([(px, 0), (px, h)], fill=major_color if is_major else minor_color, width=1)
        if is_major and px < w - 30:
            draw.text((px + 3, 2), str(lx), fill=text_color, font=font)
        lx += sub_spacing

    # 水平線
    ly = 0
    while ly * scale <= h:
        py = ly * scale
        is_major = (ly % spacing == 0)
        draw.line([(0, py), (w, py)], fill=major_color if is_major else minor_color, width=1)
        if is_major and py < h - 15:
            draw.text((3, py + 2), str(ly), fill=text_color, font=font)
        ly += sub_spacing

    result = Image.alpha_composite(img, overlay).convert("RGB")
    out = output_path or image_path  # 直接覆蓋原圖
    result.save(str(out))
    return str(out)


def analyze_image(image_path, prompt=None, region=DEFAULT_REGION, model_id=DEFAULT_MODEL):
    """透過 Bedrock 分析圖片，回傳文字描述"""
    import boto3

    if not prompt:
        prompt = "請詳細描述這張截圖的 UI 內容。使用繁體中文回答。"

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = Path(image_path).suffix.lower().lstrip(".")
    fmt = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png"}.get(ext, "png")

    client = boto3.Session().client("bedrock-runtime", region_name=region)
    response = client.converse(
        modelId=model_id,
        messages=[{
            "role": "user",
            "content": [
                {"image": {"format": fmt, "source": {"bytes": image_bytes}}},
                {"text": prompt}
            ]
        }],
        inferenceConfig={"maxTokens": 4096, "temperature": 0}
    )

    output = response["output"]["message"]["content"]
    description = "".join(block["text"] for block in output if "text" in block)

    # JSON log
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


def cmd_capture(args):
    """全螢幕截圖 + grid + 可選分析"""
    task_dir = _get_task_dir()
    if not task_dir:
        print("錯誤: 請先執行 'python snap.py init'", file=sys.stderr)
        sys.exit(1)

    n = _inc_counter(task_dir)
    img_path = task_dir / f"screenshot_{n}.png"

    # 全螢幕截圖（-C 包含游標）
    r = subprocess.run(["screencapture", "-x", "-C", str(img_path)], capture_output=True, text=True)
    if r.returncode != 0 or not img_path.exists():
        print(f"錯誤: screencapture 失敗", file=sys.stderr)
        sys.exit(1)

    # 自動加 grid
    overlay_grid(img_path)
    print(f"screenshot_{n}.png")

    if args.no_analyze:
        return

    if not args.prompt:
        print("提示: 未指定 --prompt，跳過分析")
        return

    print("分析中...")
    desc = analyze_image(
        img_path, prompt=args.prompt,
        region=args.region or DEFAULT_REGION,
        model_id=args.model or DEFAULT_MODEL
    )
    print(f"\n{'='*60}")
    print(desc)
    print(f"{'='*60}")


def cmd_analyze(args):
    """分析已存在的圖片"""
    if not args.image:
        print("錯誤: 需要 --image 參數", file=sys.stderr)
        sys.exit(1)
    img = Path(args.image)
    if not img.exists():
        print(f"錯誤: 檔案不存在 {args.image}", file=sys.stderr)
        sys.exit(1)

    desc = analyze_image(
        img, prompt=args.prompt,
        region=args.region or DEFAULT_REGION,
        model_id=args.model or DEFAULT_MODEL
    )
    print(f"\n{'='*60}")
    print(desc)
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="整合截圖 + Grid + Bedrock 分析工具")
    sub = parser.add_subparsers(dest="command")

    # init
    sub.add_parser("init", help="初始化新任務資料夾")

    # list
    sub.add_parser("list", help="列出螢幕上的視窗")

    # capture
    cap = sub.add_parser("capture", help="全螢幕截圖 + grid + 分析")
    cap.add_argument("--prompt", "-p", type=str)
    cap.add_argument("--no-analyze", action="store_true")
    cap.add_argument("--region", type=str)
    cap.add_argument("--model", type=str)

    # analyze
    ana = sub.add_parser("analyze", help="分析已存在的圖片")
    ana.add_argument("--image", "-i", type=str, required=True)
    ana.add_argument("--prompt", "-p", type=str)
    ana.add_argument("--region", type=str)
    ana.add_argument("--model", type=str)

    args = parser.parse_args()
    if args.command == "init":
        cmd_init(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "capture":
        cmd_capture(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

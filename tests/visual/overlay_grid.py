#!/usr/bin/env python3
"""
在截圖上疊加座標網格線，幫助精確定位 UI 元素。

用法:
  python overlay_grid.py input.png                     # 輸出 input_grid.png
  python overlay_grid.py input.png -o output.png       # 指定輸出
  python overlay_grid.py input.png --spacing 100       # 每 100 邏輯像素一條線
  python overlay_grid.py input.png --retina             # Retina 2x 模式（預設）
  python overlay_grid.py input.png --no-retina          # 非 Retina 模式
  python overlay_grid.py input.png --origin 52,33       # 標註邏輯螢幕座標（視窗左上角）

網格特性:
  - 線寬 1px（Retina 下為 2px 圖片像素，視覺上仍為 1 邏輯像素）
  - 每條線旁標註邏輯座標數值
  - 主線（每 100px）用較深色 + 數字標註
  - 次線（每 50px）用較淡色，不標數字
  - 半透明，盡量不遮擋原圖內容
"""
import argparse
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def overlay_grid(image_path, output_path=None, spacing=100, retina=True,
                 origin=None, sub_spacing=50):
    """在圖片上疊加座標網格"""
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size
    scale = 2 if retina else 1

    # 建立透明 overlay
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 線條樣式
    major_color = (255, 0, 0, 90)    # 紅色半透明（主線）
    minor_color = (255, 0, 0, 40)    # 更淡（次線）
    text_color = (255, 0, 0, 180)    # 文字較清晰
    line_w = 1 if not retina else 1  # 圖片像素寬度（Retina 下 1px 圖片像素 = 0.5 邏輯像素）

    # 嘗試載入字型
    font_size = 18 if retina else 10
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", font_size)
    except (OSError, IOError):
        font = ImageFont.load_default()

    ox, oy = origin if origin else (0, 0)

    # 垂直線（x 軸）
    logical_x = 0
    while logical_x * scale <= w:
        px = logical_x * scale
        is_major = (logical_x % spacing == 0)
        color = major_color if is_major else minor_color
        draw.line([(px, 0), (px, h)], fill=color, width=line_w)
        if is_major and px < w - 30:
            label = str(logical_x + ox)
            draw.text((px + 3, 2), label, fill=text_color, font=font)
        logical_x += sub_spacing

    # 水平線（y 軸）
    logical_y = 0
    while logical_y * scale <= h:
        py = logical_y * scale
        is_major = (logical_y % spacing == 0)
        color = major_color if is_major else minor_color
        draw.line([(0, py), (w, py)], fill=color, width=line_w)
        if is_major and py < h - 15:
            label = str(logical_y + oy)
            draw.text((3, py + 2), label, fill=text_color, font=font)
        logical_y += sub_spacing

    # 合成
    result = Image.alpha_composite(img, overlay).convert("RGB")

    if not output_path:
        p = Path(image_path)
        output_path = p.parent / f"{p.stem}_grid{p.suffix}"

    result.save(str(output_path))
    print(f"✓ 網格圖已儲存: {output_path}")
    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="在截圖上疊加座標網格線")
    parser.add_argument("image", help="輸入圖片路徑")
    parser.add_argument("-o", "--output", help="輸出圖片路徑")
    parser.add_argument("--spacing", type=int, default=100, help="主線間距（邏輯像素，預設 100）")
    parser.add_argument("--sub-spacing", type=int, default=50, help="次線間距（邏輯像素，預設 50）")
    parser.add_argument("--retina", action="store_true", default=True, help="Retina 2x 模式（預設）")
    parser.add_argument("--no-retina", action="store_true", help="非 Retina 模式")
    parser.add_argument("--origin", type=str, default=None,
                        help="視窗左上角的邏輯螢幕座標，格式: x,y（如 52,33）")

    args = parser.parse_args()
    retina = not args.no_retina

    origin = None
    if args.origin:
        parts = args.origin.split(",")
        origin = (int(parts[0]), int(parts[1]))

    overlay_grid(args.image, args.output, args.spacing, retina, origin, args.sub_spacing)


if __name__ == "__main__":
    main()

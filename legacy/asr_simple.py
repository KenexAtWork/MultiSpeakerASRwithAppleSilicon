#!/usr/bin/env python3
"""
簡化版 ASR - 只做轉錄，不做說話者分離
用來測試是否是 pyannote.audio 造成的崩潰
"""
import os
import sys
import argparse

# M1 Mac 優化
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import mlx_whisper

def format_timestamp(seconds):
    """將秒數轉換為時間格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def transcribe_simple(video_file, output_file, language="zh"):
    """只做 ASR 轉錄，不做說話者分離"""
    
    if not os.path.exists(video_file):
        print(f"錯誤: 檔案不存在 - {video_file}")
        sys.exit(1)

    print(f"處理檔案: {video_file}")
    print(f"輸出檔案: {output_file}")
    print(f"語言: {language}")
    print("=" * 60)

    # ASR 轉錄
    print("執行 ASR 轉錄...")
    try:
        result = mlx_whisper.transcribe(
            video_file,
            path_or_hf_repo="mlx-community/whisper-medium-mlx",
            language=language,
            word_timestamps=True,
            verbose=False
        )
        print(f"✓ 偵測到的語言: {result.get('language', 'unknown')}")
    except Exception as e:
        print(f"錯誤: ASR 轉錄失敗 - {str(e)}")
        sys.exit(1)

    # 處理結果
    segments = result["segments"]
    print(f"✓ 共 {len(segments)} 個字幕段落")

    # 寫入檔案
    print(f"寫入文字檔案: {output_file}")
    with open(output_file, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments, 1):
            timestamp = f"{format_timestamp(segment['start'])} --> {format_timestamp(segment['end'])}"
            f.write(f"[{i}] {timestamp}\n")
            f.write(f"{segment['text'].strip()}\n\n")

    total_duration = segments[-1]['end'] if segments else 0
    print("=" * 60)
    print("✓ 處理完成！")
    print(f"✓ 共處理 {len(segments)} 個字幕段落")
    print(f"✓ 總時長: {format_timestamp(total_duration)}")
    print(f"✓ 輸出檔案: {output_file}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description='簡化版 ASR 轉錄（不含說話者分離）')
    parser.add_argument('--input', required=True, help='輸入影片檔案')
    parser.add_argument('--language', default='zh', help='語言代碼（預設: zh）。混合語言音訊請省略此參數以啟用自動偵測')
    parser.add_argument('--output', help='輸出檔案路徑')
    
    args = parser.parse_args()
    
    if args.output:
        output_file = args.output
    else:
        base_name = os.path.splitext(args.input)[0]
        output_file = f"{base_name}_simple.txt"
    
    transcribe_simple(args.input, output_file, args.language)

if __name__ == "__main__":
    main()

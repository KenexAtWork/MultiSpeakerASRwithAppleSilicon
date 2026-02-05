#!/usr/bin/env python3
"""
ASR with Speaker Diarization - 直接執行版本
不使用 subprocess，直接在主程序中執行說話者分離
"""
import os
import sys
import argparse
import tempfile
import subprocess
from pathlib import Path

# M1 Mac 優化
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"

# Monkey patch torch.load 在導入前
import torch
_original_load = torch.load
def _patched_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _original_load(*args, **kwargs)
torch.load = _patched_load

import mlx_whisper
from pyannote.audio import Pipeline

def format_timestamp(seconds):
    """將秒數轉換為時間格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def extract_audio_to_wav(video_file):
    """將影片檔案的音訊提取為 WAV 格式"""
    print("提取音訊為 WAV 格式...")
    
    temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    temp_wav_path = temp_wav.name
    temp_wav.close()
    
    try:
        cmd = [
            'ffmpeg',
            '-i', video_file,
            '-ar', '16000',
            '-ac', '1',
            '-y',
            temp_wav_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"警告：ffmpeg 提取音訊失敗")
            os.unlink(temp_wav_path)
            return None
        
        print(f"✓ 音訊已提取至臨時檔案")
        return temp_wav_path
        
    except FileNotFoundError:
        print("錯誤：找不到 ffmpeg，請先安裝：brew install ffmpeg")
        os.unlink(temp_wav_path)
        return None
    except Exception as e:
        print(f"提取音訊時發生錯誤：{str(e)}")
        if os.path.exists(temp_wav_path):
            os.unlink(temp_wav_path)
        return None

def transcribe_with_speakers(video_file, output_file, language="zh", hf_token=None, skip_diarization=False):
    """ASR 轉錄 + 說話者分離"""
    
    if not os.path.exists(video_file):
        print(f"錯誤: 檔案不存在 - {video_file}")
        sys.exit(1)

    print(f"處理檔案: {video_file}")
    print(f"輸出檔案: {output_file}")
    print(f"語言: {language}")
    print("=" * 60)

    # Step 1: ASR 轉錄
    print("[1/2] 執行 ASR 轉錄...")
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

    segments = result["segments"]
    print(f"✓ 共 {len(segments)} 個字幕段落")

    # Step 2: 說話者分離
    speaker_timeline = []
    temp_wav_path = None
    
    if not skip_diarization and hf_token:
        print("[2/2] 執行說話者分離...")
        
        # 提取音訊
        temp_wav_path = extract_audio_to_wav(video_file)
        
        if temp_wav_path:
            try:
                print("載入說話者分離模型...")
                torch.set_num_threads(1)
                
                pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    token=hf_token
                )
                
                if hasattr(pipeline, 'to'):
                    pipeline.to(torch.device("cpu"))
                
                print("執行說話者分離（這可能需要 10-20 分鐘）...")
                print("提示：處理時間約為影片長度的 0.5-1 倍")
                
                diarization_result = pipeline(temp_wav_path)
                
                # pyannote-audio 4.x 使用 speaker_diarization 屬性
                if hasattr(diarization_result, 'speaker_diarization'):
                    annotation = diarization_result.speaker_diarization
                    for segment, _, speaker in annotation.itertracks(yield_label=True):
                        speaker_timeline.append({
                            'start': float(segment.start),
                            'end': float(segment.end),
                            'speaker': speaker
                        })
                else:
                    raise Exception(f"無法從 {type(diarization_result)} 提取說話者資訊")
                
                num_speakers = len(set(sp['speaker'] for sp in speaker_timeline))
                print(f"✓ 偵測到 {num_speakers} 位說話者")
                
            except Exception as e:
                print(f"⚠ 說話者分離失敗: {str(e)}")
                speaker_timeline = []
            finally:
                # 清理臨時檔案
                if temp_wav_path and os.path.exists(temp_wav_path):
                    try:
                        os.unlink(temp_wav_path)
                        print("✓ 已清理臨時音訊檔案")
                    except:
                        pass
        else:
            print("⚠ 無法提取音訊，將不標記說話者")
    else:
        print("[2/2] 跳過說話者分離")

    # Step 3: 合併結果
    print("合併轉錄結果...")
    all_segments = []

    for i, segment in enumerate(segments, 1):
        speaker = "Unknown"
        
        if speaker_timeline:
            segment_mid = (segment['start'] + segment['end']) / 2
            for sp in speaker_timeline:
                if sp['start'] <= segment_mid <= sp['end']:
                    speaker = sp['speaker']
                    break

        all_segments.append({
            'index': i,
            'start': segment['start'],
            'end': segment['end'],
            'speaker': speaker,
            'text': segment['text'].strip()
        })

    # Step 4: 寫入檔案
    print(f"寫入文字檔案: {output_file}")
    with open(output_file, "w", encoding="utf-8") as f:
        for seg in all_segments:
            timestamp = f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}"
            f.write(f"[{seg['speaker']}] {timestamp}\n")
            f.write(f"{seg['text']}\n\n")

    # 統計
    total_duration = all_segments[-1]['end'] if all_segments else 0
    speakers = set(seg['speaker'] for seg in all_segments)

    print("=" * 60)
    print("✓ 處理完成！")
    print(f"✓ 共處理 {len(all_segments)} 個字幕段落")
    print(f"✓ 總時長: {format_timestamp(total_duration)}")
    print(f"✓ 偵測到的說話者: {', '.join(sorted(speakers))}")
    print(f"✓ 輸出檔案: {output_file}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(
        description='ASR 轉錄 + 說話者分離（直接執行版）',
        epilog="""
使用範例：
  # 只做 ASR 轉錄
  python asr_multi_speaker_v4.py --input all.mp4 --skip-diarization
  
  # ASR + 說話者分離
  python asr_multi_speaker_v4.py --input all.mp4 --hf-token YOUR_TOKEN
        """
    )
    
    parser.add_argument('--input', required=True, help='輸入影片檔案')
    parser.add_argument('--language', default='zh', help='語言代碼（預設: zh）。混合語言音訊請省略此參數以啟用自動偵測')
    parser.add_argument('--output', help='輸出檔案路徑')
    parser.add_argument('--hf-token', help='Hugging Face token（用於說話者分離）')
    parser.add_argument('--skip-diarization', action='store_true', help='跳過說話者分離')
    
    args = parser.parse_args()
    
    if args.output:
        output_file = args.output
    else:
        base_name = os.path.splitext(args.input)[0]
        output_file = f"{base_name}_transcription_v4.txt"
    
    transcribe_with_speakers(
        video_file=args.input,
        output_file=output_file,
        language=args.language,
        hf_token=args.hf_token,
        skip_diarization=args.skip_diarization
    )

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
ASR with Speaker Diarization - 加速版本
- 使用 MPS (Metal Performance Shaders) GPU 加速
- 增加執行緒數
- 使用更快的模型
"""
import os
import sys
import argparse
import tempfile
import subprocess
from pathlib import Path

# M1 Mac 優化 - 使用所有效能核心
os.environ["OMP_NUM_THREADS"] = "8"
os.environ["MKL_NUM_THREADS"] = "8"

# Monkey patch torch.load
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
        # 使用 ffmpeg 提取音訊並轉換為 pyannote 需要的格式
        # 注意：pyannote 需要 16kHz 單聲道，所以必須重新編碼
        cmd = [
            'ffmpeg',
            '-i', video_file,
            '-ar', '16000',      # 重新取樣到 16kHz（pyannote 需求）
            '-ac', '1',          # 轉換為單聲道（pyannote 需求）
            '-acodec', 'pcm_s16le',  # 使用 PCM 編碼（WAV 標準格式）
            '-y',
            temp_wav_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"警告：ffmpeg 提取音訊失敗")
            os.unlink(temp_wav_path)
            return None
        
        print(f"✓ 音訊已提取至臨時檔案（16kHz 單聲道 WAV）")
        return temp_wav_path
        
    except Exception as e:
        print(f"提取音訊時發生錯誤：{str(e)}")
        if os.path.exists(temp_wav_path):
            os.unlink(temp_wav_path)
        return None

def transcribe_with_speakers(video_file, output_file, language="zh", hf_token=None, skip_diarization=False, use_gpu=True):
    """ASR 轉錄 + 說話者分離（加速版）"""
    
    if not os.path.exists(video_file):
        print(f"錯誤: 檔案不存在 - {video_file}")
        sys.exit(1)

    print(f"處理檔案: {video_file}")
    print(f"輸出檔案: {output_file}")
    print(f"語言: {language}")
    print(f"GPU 加速: {'啟用 (MPS)' if use_gpu else '停用 (CPU)'}")
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
        print("[2/2] 執行說話者分離（加速版）...")
        
        # 提取音訊
        temp_wav_path = extract_audio_to_wav(video_file)
        
        if temp_wav_path:
            try:
                print("載入說話者分離模型...")
                
                # 設定執行緒數（使用所有效能核心）
                torch.set_num_threads(8)
                
                pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    token=hf_token
                )
                
                # 嘗試使用 MPS (Metal Performance Shaders) GPU
                if use_gpu and torch.backends.mps.is_available():
                    device = torch.device("mps")
                    print("✓ 使用 MPS GPU 加速")
                else:
                    device = torch.device("cpu")
                    print("✓ 使用 CPU 模式")
                
                if hasattr(pipeline, 'to'):
                    pipeline.to(device)
                
                print("執行說話者分離...")
                print("提示：使用 GPU 可加速 2-3 倍")
                
                diarization_result = pipeline(temp_wav_path)
                
                # 提取說話者資訊
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
        description='ASR 轉錄 + 說話者分離（加速版）',
        epilog="""
使用範例：
  # 使用 GPU 加速（推薦）
  python asr_multi_speaker_v5_fast.py --input all.mp4 --hf-token YOUR_TOKEN
  
  # 只用 CPU（較慢但更穩定）
  python asr_multi_speaker_v5_fast.py --input all.mp4 --hf-token YOUR_TOKEN --no-gpu
  
  # 只做 ASR 轉錄
  python asr_multi_speaker_v5_fast.py --input all.mp4 --skip-diarization
        """
    )
    
    parser.add_argument('--input', required=True, help='輸入影片檔案')
    parser.add_argument('--language', default='zh', help='語言代碼（預設: zh）。混合語言音訊請省略此參數以啟用自動偵測')
    parser.add_argument('--output', help='輸出檔案路徑')
    parser.add_argument('--hf-token', help='Hugging Face token（用於說話者分離）')
    parser.add_argument('--skip-diarization', action='store_true', help='跳過說話者分離')
    parser.add_argument('--no-gpu', action='store_true', help='停用 GPU 加速（使用 CPU）')
    
    args = parser.parse_args()
    
    if args.output:
        output_file = args.output
    else:
        base_name = os.path.splitext(args.input)[0]
        output_file = f"{base_name}_transcription_v5.txt"
    
    transcribe_with_speakers(
        video_file=args.input,
        output_file=output_file,
        language=args.language,
        hf_token=args.hf_token,
        skip_diarization=args.skip_diarization,
        use_gpu=not args.no_gpu
    )

if __name__ == "__main__":
    main()

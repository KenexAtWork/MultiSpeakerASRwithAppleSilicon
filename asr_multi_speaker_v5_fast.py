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
from datetime import datetime

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
from merge_srt import merge_segments as merge_adjacent_segments

def timestamp():
    """返回當前時間戳記"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def tprint(msg):
    """帶時間戳記的 print"""
    print(f"[{timestamp()}] {msg}")

def format_timestamp(seconds):
    """將秒數轉換為時間格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def format_timestamp_srt(seconds):
    """將秒數轉換為 SRT 時間格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def extract_audio_to_wav(video_file):
    """將影片檔案的音訊提取為 WAV 格式"""
    tprint("提取音訊為 WAV 格式...")
    
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
            tprint(f"警告：ffmpeg 提取音訊失敗")
            os.unlink(temp_wav_path)
            return None
        
        tprint(f"✓ 音訊已提取至臨時檔案（16kHz 單聲道 WAV）")
        return temp_wav_path
        
    except Exception as e:
        tprint(f"提取音訊時發生錯誤：{str(e)}")
        if os.path.exists(temp_wav_path):
            os.unlink(temp_wav_path)
        return None



def transcribe_with_speakers(video_file, output_file, language="zh", hf_token=None, skip_diarization=False, use_gpu=True, output_format="srt", model_size="medium"):
    """ASR 轉錄 + 說話者分離（加速版 + 記憶體優化）"""
    
    import time
    import gc
    
    # 打印開始時間
    tprint(f"========== 開始處理 ==========")
    start_time = time.time()
    stage_times = {}  # 記錄各階段時間
    
    if not os.path.exists(video_file):
        tprint(f"錯誤: 檔案不存在 - {video_file}")
        sys.exit(1)

    tprint(f"處理檔案: {video_file}")
    tprint(f"輸出檔案: {output_file}")
    tprint(f"語言: {language}")
    tprint(f"模型大小: {model_size}")
    tprint(f"GPU 加速: {'啟用 (MPS)' if use_gpu else '停用 (CPU)'}")
    tprint("=" * 60)

    # auto 語言偵測：傳 None 給 Whisper
    if language and language.lower() == "auto":
        language = None

    # Step 1: ASR 轉錄
    asr_start = time.time()
    model_map = {
        "tiny": "mlx-community/whisper-tiny-mlx",
        "base": "mlx-community/whisper-base-mlx",
        "small": "mlx-community/whisper-small-mlx",
        "medium": "mlx-community/whisper-medium-mlx",
        "large": "mlx-community/whisper-large-v3-mlx",
        "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    }
    model_path = model_map.get(model_size, model_map["medium"])
    
    tprint(f"[1/3] 執行 ASR 轉錄（模型: {model_size}）...")
    tprint(f"⏳ 載入 Whisper 模型（首次使用需下載，約 1.5 GB）...")
    tprint(f"   模型路徑: {model_path}")
    
    # 在獨立作用域中執行 ASR，確保變數被釋放
    segments = None
    try:
        result = mlx_whisper.transcribe(
            video_file,
            path_or_hf_repo=model_path,
            language=language,
            word_timestamps=True,
            verbose=False
        )
        tprint("✓ 模型載入完成，開始轉錄...")
        tprint(f"✓ 偵測到的語言: {result.get('language', 'unknown')}")
        
        # 立即複製需要的資料
        segments = result["segments"]
        tprint(f"✓ 共 {len(segments)} 個字幕段落")
        
        # 立即刪除 result
        del result
        
    except Exception as e:
        tprint(f"錯誤: ASR 轉錄失敗 - {str(e)}")
        sys.exit(1)
    
    # 強制記憶體清理
    gc.collect()
    gc.collect()
    gc.collect()  # 多次執行確保清理
    
    # 嘗試清理 MLX 快取（如果有的話）
    try:
        import mlx.core as mx
        mx.clear_cache()
        tprint("✓ 已清理 MLX 快取")
    except:
        pass
    
    tprint("✓ 已釋放 ASR 模型記憶體")
    
    # 給系統時間釋放記憶體
    tprint("⏳ 等待記憶體釋放...")
    time.sleep(1)
    
    # 記錄 ASR 階段時間
    asr_end = time.time()
    stage_times['asr'] = asr_end - asr_start

    # Step 2: 說話者分離
    diarization_start = time.time()
    speaker_timeline = []
    temp_wav_path = None
    
    if not skip_diarization and hf_token:
        tprint("[2/3] 執行說話者分離（加速版）...")
        
        # 提取音訊
        tprint("⏳ 提取音訊為 WAV 格式...")
        temp_wav_path = extract_audio_to_wav(video_file)
        
        if temp_wav_path:
            try:
                tprint("⏳ 載入說話者分離模型（首次使用需下載，約 200 MB）...")
                
                # 設定執行緒數（使用所有效能核心）
                torch.set_num_threads(8)
                
                pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    token=hf_token
                )
                tprint("✓ 模型載入完成")
                
                # 嘗試使用 MPS (Metal Performance Shaders) GPU
                tprint("⏳ 初始化 GPU/CPU 設備...")
                if use_gpu and torch.backends.mps.is_available():
                    device = torch.device("mps")
                    tprint("✓ 使用 MPS GPU 加速")
                else:
                    device = torch.device("cpu")
                    tprint("✓ 使用 CPU 模式")
                
                if hasattr(pipeline, 'to'):
                    pipeline.to(device)
                    tprint("✓ 模型已載入至設備")
                
                tprint("⏳ 執行說話者分離（這可能需要 1-2 分鐘）...")
                tprint("提示：使用 GPU 可加速 2-3 倍")
                
                # 自訂進度回報（取代 tqdm ProgressHook，確保 pipe 環境即時輸出）
                class StdoutProgressHook:
                    def __init__(self):
                        self._current_step = None
                        self._last_pct = -1
                    def __enter__(self):
                        return self
                    def __exit__(self, *args):
                        pass
                    def __call__(self, step_name, step_artifact, file=None, total=None, completed=None):
                        if step_name != self._current_step:
                            if self._current_step is not None:
                                print(flush=True)  # 換行結束上一步
                            self._current_step = step_name
                            self._last_pct = -1
                        if total is not None and completed is not None:
                            pct = int(completed / total * 100) if total > 0 else 0
                            # 每 5% 更新一次，避免頻繁 I/O 拖慢速度
                            if pct >= self._last_pct + 5 or completed == total:
                                self._last_pct = pct
                                bar_len = 30
                                filled = int(bar_len * completed / total) if total > 0 else 0
                                bar = '█' * filled + '─' * (bar_len - filled)
                                print(f"\r{step_name} {bar} {pct:3d}%", end='', flush=True)
                        return step_artifact

                with StdoutProgressHook() as hook:
                    diarization_result = pipeline(temp_wav_path, hook=hook)
                print(flush=True)  # 最後換行
                
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
                tprint(f"✓ 偵測到 {num_speakers} 位說話者")
                
                # 立即釋放說話者分離模型記憶體
                del pipeline
                del diarization_result
                
                # 強制記憶體清理
                import gc
                gc.collect()
                gc.collect()
                gc.collect()
                
                if use_gpu and torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                
                tprint("✓ 已釋放說話者分離模型記憶體")
                
            except Exception as e:
                tprint(f"⚠ 說話者分離失敗: {str(e)}")
                speaker_timeline = []
                # 確保即使失敗也清理記憶體
                import gc
                gc.collect()
            finally:
                # 清理臨時檔案
                if temp_wav_path and os.path.exists(temp_wav_path):
                    try:
                        os.unlink(temp_wav_path)
                        tprint("✓ 已清理臨時音訊檔案")
                    except:
                        pass
        else:
            tprint("⚠ 無法提取音訊，將不標記說話者")
    else:
        tprint("[2/3] 跳過說話者分離")
    
    # 記錄說話者分離階段時間
    diarization_end = time.time()
    stage_times['diarization'] = diarization_end - diarization_start

    # Step 3: 合併結果 + 合併相鄰同 speaker 段落
    tprint(f"[3/3] 合併轉錄結果（共 {len(segments)} 個段落）...")
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
    
    raw_count = len(all_segments)
    all_segments = merge_adjacent_segments(all_segments)
    tprint(f"✓ 合併完成: {raw_count} → {len(all_segments)} 段")

    # Step 4: 寫入檔案
    tprint(f"⏳ 寫入檔案: {output_file} (格式: {output_format.upper()})...")
    
    with open(output_file, "w", encoding="utf-8") as f:
        if output_format == "srt":
            # SRT 格式
            for seg in all_segments:
                f.write(f"{seg['index']}\n")
                timestamp = f"{format_timestamp_srt(seg['start'])} --> {format_timestamp_srt(seg['end'])}"
                f.write(f"{timestamp}\n")
                f.write(f"[{seg['speaker']}] {seg['text']}\n\n")
        else:
            # TXT 格式（原始格式）
            for seg in all_segments:
                timestamp = f"{format_timestamp(seg['start'])} --> {format_timestamp(seg['end'])}"
                f.write(f"[{seg['speaker']}] {timestamp}\n")
                f.write(f"{seg['text']}\n\n")
    
    tprint("✓ 檔案寫入完成")

    # 統計
    tprint("⏳ 計算統計資訊...")
    total_duration = all_segments[-1]['end'] if all_segments else 0
    speakers = set(seg['speaker'] for seg in all_segments)
    
    # 計算執行時間和處理速度
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # 計算處理速度倍率（處理時間 / 影片時長）
    if total_duration > 0:
        speed_ratio = elapsed_time / total_duration
        realtime_speed = 1 / speed_ratio
        
        # 計算各階段的處理速度
        asr_time = stage_times.get('asr', 0)
        diarization_time = stage_times.get('diarization', 0)
        
        asr_speed_ratio = asr_time / total_duration if total_duration > 0 else 0
        asr_realtime_speed = 1 / asr_speed_ratio if asr_speed_ratio > 0 else 0
        
        diarization_speed_ratio = diarization_time / total_duration if total_duration > 0 else 0
        diarization_realtime_speed = 1 / diarization_speed_ratio if diarization_speed_ratio > 0 else 0
    else:
        speed_ratio = 0
        realtime_speed = 0
        asr_speed_ratio = 0
        asr_realtime_speed = 0
        diarization_speed_ratio = 0
        diarization_realtime_speed = 0

    tprint("=" * 60)
    tprint("✓ 處理完成！")
    tprint("")
    tprint("📊 處理統計：")
    tprint(f"  • 影片時長: {format_timestamp(total_duration)}")
    tprint(f"  • 總處理時間: {int(elapsed_time // 60)} 分 {int(elapsed_time % 60)} 秒")
    tprint(f"  • 整體速度: {speed_ratio:.2f}x 處理時間 = {realtime_speed:.2f}x 即時速度" if speed_ratio > 0 else "  • 整體速度: N/A")
    tprint("")
    tprint("⏱️  各階段耗時與速度：")
    if asr_realtime_speed > 0:
        tprint(f"  • ASR 轉錄: {int(stage_times.get('asr', 0))} 秒 ({stage_times.get('asr', 0) / elapsed_time * 100:.1f}%) - {asr_realtime_speed:.2f}x 即時速度")
    else:
        tprint(f"  • ASR 轉錄: {int(stage_times.get('asr', 0))} 秒 ({stage_times.get('asr', 0) / elapsed_time * 100:.1f}%)")
    
    if diarization_realtime_speed > 0:
        tprint(f"  • 說話者分離: {int(stage_times.get('diarization', 0))} 秒 ({stage_times.get('diarization', 0) / elapsed_time * 100:.1f}%) - {diarization_realtime_speed:.2f}x 即時速度")
    else:
        tprint(f"  • 說話者分離: {int(stage_times.get('diarization', 0))} 秒 ({stage_times.get('diarization', 0) / elapsed_time * 100:.1f}%)")
    
    tprint(f"  • 其他處理: {int(elapsed_time - stage_times.get('asr', 0) - stage_times.get('diarization', 0))} 秒")
    tprint("")
    tprint(f"📝 輸出結果：")
    tprint(f"  • 字幕段落: {len(all_segments)} 個")
    tprint(f"  • 偵測說話者: {', '.join(sorted(speakers))}")
    tprint(f"  • 輸出檔案: {output_file}")
    tprint("=" * 60)

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
    parser.add_argument('--format', choices=['srt', 'txt'], default='srt', help='輸出格式（預設: srt）')
    parser.add_argument('--model', choices=['tiny', 'base', 'small', 'medium', 'large'], default='medium',
                        help='Whisper 模型大小（預設: medium）。記憶體不足時可用 small 或 base')
    parser.add_argument('--hf-token', help='Hugging Face token（用於說話者分離）')
    parser.add_argument('--skip-diarization', action='store_true', help='跳過說話者分離')
    parser.add_argument('--no-gpu', action='store_true', help='停用 GPU 加速（使用 CPU）')
    
    args = parser.parse_args()
    
    if args.output:
        output_file = args.output
    else:
        base_name = os.path.splitext(args.input)[0]
        ext = 'srt' if args.format == 'srt' else 'txt'
        output_file = f"{base_name}_transcription.{ext}"
    
    transcribe_with_speakers(
        video_file=args.input,
        output_file=output_file,
        language=args.language,
        hf_token=args.hf_token,
        skip_diarization=args.skip_diarization,
        use_gpu=not args.no_gpu,
        output_format=args.format,
        model_size=args.model
    )

if __name__ == "__main__":
    main()

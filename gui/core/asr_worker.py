"""
ASR Worker - 在背景執行緒中處理 ASR 轉錄
使用 subprocess 執行，完全隔離避免 Qt 線程衝突
"""
import os
import sys
import subprocess
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal


class ASRWorker(QThread):
    """ASR 處理 Worker"""
    
    # 信號
    progress = pyqtSignal(int)       # 進度 (0-100)
    stage_changed = pyqtSignal(str)  # 階段變更
    log_message = pyqtSignal(str)    # 日誌訊息（新增一行）
    log_replace = pyqtSignal(str)    # 日誌訊息（覆蓋最後一行，用於 tqdm 進度）
    finished = pyqtSignal(str)       # 完成 (輸出檔案路徑)
    error = pyqtSignal(str)          # 錯誤訊息
    
    def __init__(self, video_file, output_file, language="zh", 
                 model_size="medium", output_format="srt",
                 skip_diarization=False, use_gpu=True, hf_token=""):
        super().__init__()
        self.video_file = video_file
        self.output_file = output_file
        self.language = language
        self.model_size = model_size
        self.output_format = output_format
        self.skip_diarization = skip_diarization
        self.use_gpu = use_gpu
        self.hf_token = hf_token or os.environ.get('HF_TOKEN', '')
    
    def run(self):
        """執行 ASR 處理（透過 subprocess）"""
        try:
            # 檢查模型是否已下載
            self._check_and_notify_model_download()
            
            self.log_message.emit("=" * 60)
            self.log_message.emit("開始處理...")
            self.log_message.emit(f"輸入檔案: {self.video_file}")
            self.log_message.emit(f"輸出檔案: {self.output_file}")
            self.log_message.emit(f"語言: {self.language}")
            self.log_message.emit(f"模型: {self.model_size}")
            self.log_message.emit(f"輸出格式: {self.output_format}")
            self.log_message.emit(f"跳過說話者分離: {self.skip_diarization}")
            self.log_message.emit(f"使用 GPU: {self.use_gpu}")
            self.log_message.emit("=" * 60)
            
            self.stage_changed.emit("ASR 轉錄中...")
            self.progress.emit(10)
            
            # 找到 Python 執行檔和腳本路徑
            python_exe = sys.executable
            asr_dir = str(Path(__file__).parent.parent.parent)
            script = str(Path(asr_dir) / 'asr_multi_speaker_v5_fast.py')
            
            # 組裝命令
            cmd = [
                python_exe, script,
                '--input', self.video_file,
                '--output', self.output_file,
                '--language', self.language,
                '--format', self.output_format,
                '--model', self.model_size,
            ]
            if self.hf_token:
                cmd.extend(['--hf-token', self.hf_token])
            if self.skip_diarization:
                cmd.append('--skip-diarization')
            if not self.use_gpu:
                cmd.append('--no-gpu')
            
            # 設定環境變數
            env = os.environ.copy()
            if self.hf_token:
                env['HF_TOKEN'] = self.hf_token
            env['PYTHONUNBUFFERED'] = '1'
            
            # 使用 subprocess 執行
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=asr_dir,
            )
            
            # 用 TextIOWrapper 正確處理 UTF-8 多字節，newline='' 保留 \r
            import io
            stdout = io.TextIOWrapper(process.stdout, encoding='utf-8', errors='replace', newline='')
            
            buf = ""
            in_cr_mode = False
            while True:
                ch = stdout.read(1)
                if not ch:
                    break
                if ch == '\n':
                    line = buf.strip()
                    if line:
                        if in_cr_mode:
                            self.log_replace.emit(line)
                        else:
                            self.log_message.emit(line)
                        self._update_progress(line)
                    buf = ""
                    in_cr_mode = False
                elif ch == '\r':
                    line = buf.strip()
                    if line:
                        if in_cr_mode:
                            self.log_replace.emit(line)
                        else:
                            self.log_message.emit(line)
                            in_cr_mode = True
                        self._update_progress(line)
                    buf = ""
                else:
                    buf += ch
            
            if buf.strip():
                self.log_message.emit(buf.strip())
                self._update_progress(buf.strip())
            
            process.wait()
            
            if process.returncode == 0:
                self.progress.emit(100)
                self.stage_changed.emit("處理完成！")
                self.log_message.emit("=" * 60)
                self.log_message.emit(f"✓ 輸出檔案: {self.output_file}")
                self.log_message.emit("=" * 60)
                self.finished.emit(self.output_file)
            else:
                self.error.emit(f"處理失敗（exit code: {process.returncode}）")
            
        except Exception as e:
            import traceback
            error_msg = f"錯誤: {str(e)}\n\n{traceback.format_exc()}"
            self.log_message.emit(error_msg)
            self.error.emit(error_msg)
    
    def _update_progress(self, line):
        """根據輸出內容更新進度和階段"""
        if '載入 Whisper 模型' in line:
            self.stage_changed.emit("載入 ASR 模型...")
            self.progress.emit(15)
        elif '開始轉錄' in line:
            self.stage_changed.emit("ASR 轉錄中...")
            self.progress.emit(30)
        elif '執行說話者分離' in line:
            self.stage_changed.emit("說話者分離中...")
            self.progress.emit(60)
        elif '合併轉錄結果' in line:
            self.stage_changed.emit("合併結果...")
            self.progress.emit(85)
        elif '寫入檔案' in line:
            self.stage_changed.emit("寫入檔案...")
            self.progress.emit(90)
        elif '處理完成' in line:
            self.progress.emit(95)

    def _check_and_notify_model_download(self):
        """檢查模型是否需要下載，並在 GUI 中顯示提示"""
        from pathlib import Path
        
        # 檢查 Hugging Face 快取目錄
        hf_cache = Path.home() / '.cache' / 'huggingface' / 'hub'
        mlx_cache = Path.home() / '.cache' / 'mlx_whisper'
        
        # 檢查 Whisper 模型
        model_map = {
            "tiny": "whisper-tiny-mlx",
            "base": "whisper-base-mlx",
            "small": "whisper-small-mlx",
            "medium": "whisper-medium-mlx",
            "large": "whisper-large-v3-mlx"
        }
        whisper_model_name = model_map.get(self.model_size, "whisper-medium-mlx")
        whisper_exists = False
        
        if hf_cache.exists():
            for item in hf_cache.iterdir():
                if whisper_model_name in item.name:
                    whisper_exists = True
                    break
        
        if not whisper_exists and mlx_cache.exists():
            whisper_exists = mlx_cache.exists()
        
        # 檢查 Diarization 模型
        diarization_exists = False
        if not self.skip_diarization and hf_cache.exists():
            for item in hf_cache.iterdir():
                if 'speaker-diarization' in item.name:
                    diarization_exists = True
                    break
        
        # 顯示下載提示
        if not whisper_exists or (not self.skip_diarization and not diarization_exists):
            self.log_message.emit("=" * 60)
            self.log_message.emit("⚠️  首次使用偵測")
            self.log_message.emit("=" * 60)
            
            if not whisper_exists:
                model_sizes = {
                    "tiny": "約 100 MB",
                    "base": "約 150 MB",
                    "small": "約 500 MB",
                    "medium": "約 1.5 GB",
                    "large": "約 3 GB"
                }
                size = model_sizes.get(self.model_size, "約 1.5 GB")
                self.log_message.emit(f"📥 首次使用 Whisper {self.model_size} 模型")
                self.log_message.emit(f"   需要下載模型檔案：{size}")
                self.log_message.emit(f"   下載時間視網路速度而定（約 1-5 分鐘）")
            
            if not self.skip_diarization and not diarization_exists:
                self.log_message.emit(f"📥 首次使用說話者分離功能")
                self.log_message.emit(f"   需要下載模型檔案：約 200 MB")
                self.log_message.emit(f"   下載時間視網路速度而定（約 1-2 分鐘）")
            
            self.log_message.emit("")
            self.log_message.emit("💡 提示：")
            self.log_message.emit("   - 模型下載完成後會自動快取")
            self.log_message.emit("   - 之後使用將會很快（< 5 秒啟動）")
            self.log_message.emit("   - 下載期間請保持網路連線")
            self.log_message.emit("=" * 60)
            self.log_message.emit("")

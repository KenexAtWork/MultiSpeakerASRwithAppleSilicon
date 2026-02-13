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
    progress = pyqtSignal(int)  # 進度 (0-100)
    stage_changed = pyqtSignal(str)  # 階段變更
    log_message = pyqtSignal(str)  # 日誌訊息
    finished = pyqtSignal(str)  # 完成 (輸出檔案路徑)
    error = pyqtSignal(str)  # 錯誤訊息
    
    def __init__(self, video_file, output_file, language="zh", 
                 model_size="medium", output_format="srt",
                 skip_diarization=False, use_gpu=True):
        super().__init__()
        self.video_file = video_file
        self.output_file = output_file
        self.language = language
        self.model_size = model_size
        self.output_format = output_format
        self.skip_diarization = skip_diarization
        self.use_gpu = use_gpu
        
        # 取得 HF_TOKEN
        self.hf_token = os.environ.get('HF_TOKEN', '')
    
    def run(self):
        """執行 ASR 處理（透過 subprocess）"""
        try:
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
            if self.skip_diarization:
                cmd.append('--skip-diarization')
            if not self.use_gpu:
                cmd.append('--no-gpu')
            
            # 設定環境變數
            env = os.environ.copy()
            if self.hf_token:
                env['HF_TOKEN'] = self.hf_token
            # 強制 Python 不緩衝輸出
            env['PYTHONUNBUFFERED'] = '1'
            
            # 使用 subprocess 執行，逐行讀取輸出
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                cwd=asr_dir,
            )
            
            # 即時讀取輸出
            for line in process.stdout:
                line = line.rstrip('\n')
                if line:
                    self.log_message.emit(line)
                    # 根據輸出內容更新進度
                    self._update_progress(line)
            
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

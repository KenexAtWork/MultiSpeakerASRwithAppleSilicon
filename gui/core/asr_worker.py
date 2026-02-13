"""
ASR Worker - 在背景執行緒中處理 ASR 轉錄
"""
import os
import sys
import io
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

# 導入 ASR 模組（延遲導入以加快 GUI 啟動）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


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
        self.hf_token = os.environ.get('HF_TOKEN')
    
    def run(self):
        """執行 ASR 處理"""
        try:
            # 延遲導入以加快 GUI 啟動
            from asr_multi_speaker_v5_fast import transcribe_with_speakers
            
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
            
            # 階段 1: 準備
            self.stage_changed.emit("準備處理...")
            self.progress.emit(5)
            
            # 階段 2: ASR 轉錄
            self.stage_changed.emit("ASR 轉錄中...")
            self.progress.emit(10)
            
            # 捕獲標準輸出並轉發到 GUI
            output_buffer = io.StringIO()
            
            # 執行轉錄（stdout 會被捕獲）
            with redirect_stdout(output_buffer), redirect_stderr(output_buffer):
                transcribe_with_speakers(
                    video_file=self.video_file,
                    output_file=self.output_file,
                    language=self.language,
                    hf_token=self.hf_token,
                    skip_diarization=self.skip_diarization,
                    use_gpu=self.use_gpu,
                    output_format=self.output_format,
                    model_size=self.model_size
                )
            
            # 取得輸出並發送到 GUI
            output = output_buffer.getvalue()
            if output:
                for line in output.split('\n'):
                    if line.strip():
                        self.log_message.emit(line)
            
            self.progress.emit(100)
            self.stage_changed.emit("處理完成！")
            self.log_message.emit("=" * 60)
            self.log_message.emit(f"✓ 輸出檔案: {self.output_file}")
            self.log_message.emit("=" * 60)
            self.finished.emit(self.output_file)
            
        except Exception as e:
            import traceback
            error_msg = f"錯誤: {str(e)}\n\n詳細資訊:\n{traceback.format_exc()}"
            self.log_message.emit(error_msg)
            self.error.emit(error_msg)

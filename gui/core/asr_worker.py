"""
ASR Worker - 在背景執行緒中處理 ASR 轉錄
"""
import os
import sys
from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal

# 導入 ASR 模組
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from asr_multi_speaker_v5_fast import transcribe_with_speakers


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
        
        # 重定向 print 輸出
        self._setup_print_redirect()
    
    def _setup_print_redirect(self):
        """設定 print 重定向到信號"""
        import builtins
        original_print = builtins.print
        
        def custom_print(*args, **kwargs):
            # 將 print 內容轉為字串
            message = ' '.join(str(arg) for arg in args)
            
            # 發送到 GUI
            self.log_message.emit(message)
            
            # 也輸出到原始 stdout
            original_print(*args, **kwargs)
        
        builtins.print = custom_print
    
    def run(self):
        """執行 ASR 處理"""
        try:
            self.log_message.emit("=" * 60)
            self.log_message.emit("開始處理...")
            self.log_message.emit(f"輸入檔案: {self.video_file}")
            self.log_message.emit(f"輸出檔案: {self.output_file}")
            self.log_message.emit(f"語言: {self.language}")
            self.log_message.emit(f"模型: {self.model_size}")
            self.log_message.emit("=" * 60)
            
            # 階段 1: ASR 轉錄
            self.stage_changed.emit("載入模型...")
            self.progress.emit(10)
            
            self.stage_changed.emit("ASR 轉錄中...")
            self.progress.emit(20)
            
            # 執行轉錄
            # 注意：這裡需要修改 transcribe_with_speakers 來支援進度回調
            # 目前先簡單執行
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
            
            self.progress.emit(100)
            self.finished.emit(self.output_file)
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
            self.error.emit(error_msg)

"""
主視窗 UI
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QComboBox, QCheckBox, QTextEdit,
    QProgressBar, QFileDialog, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont
from pathlib import Path

from core.asr_worker import ASRWorker


class DropZone(QLabel):
    """支援拖放的區域"""
    filesDropped = pyqtSignal(list)
    
    def __init__(self, text=""):
        super().__init__(text)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 10px;
                padding: 40px;
                background-color: #f5f5f5;
                color: #666;
                font-size: 14px;
            }
            QLabel:hover {
                border-color: #4a90e2;
                background-color: #e8f4ff;
            }
        """)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("""
                QLabel {
                    border: 2px solid #4a90e2;
                    border-radius: 10px;
                    padding: 40px;
                    background-color: #e8f4ff;
                    color: #4a90e2;
                    font-size: 14px;
                }
            """)
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 10px;
                padding: 40px;
                background-color: #f5f5f5;
                color: #666;
                font-size: 14px;
            }
        """)
    
    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if Path(file_path).is_file():
                files.append(file_path)
        
        if files:
            self.filesDropped.emit(files)
        
        self.dragLeaveEvent(None)


class MainWindow(QMainWindow):
    """主視窗"""
    
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.worker = None
        self.init_ui()
    
    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("ASR Multi-Speaker Transcription")
        self.setMinimumSize(800, 700)
        
        # 主要 widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主要佈局
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 標題
        title = QLabel("ASR 多說話者轉錄")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # 拖放區域
        self.drop_zone = DropZone("拖放影片檔案到這裡\n或點擊下方按鈕選擇檔案")
        self.drop_zone.filesDropped.connect(self.on_files_dropped)
        layout.addWidget(self.drop_zone)
        
        # 檔案選擇按鈕
        btn_layout = QHBoxLayout()
        self.select_btn = QPushButton("選擇檔案...")
        self.select_btn.clicked.connect(self.select_file)
        self.select_btn.setMinimumHeight(40)
        btn_layout.addWidget(self.select_btn)
        layout.addLayout(btn_layout)
        
        # 當前檔案標籤
        self.file_label = QLabel("尚未選擇檔案")
        self.file_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.file_label)
        
        # 設定群組
        settings_group = QGroupBox("設定")
        settings_layout = QVBoxLayout()
        
        # 語言選擇
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("語言:"))
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "zh (中文)", "en (英文)", "ja (日文)", 
            "auto (自動偵測)"
        ])
        lang_layout.addWidget(self.language_combo)
        lang_layout.addStretch()
        settings_layout.addLayout(lang_layout)
        
        # 模型選擇
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型大小:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "tiny (~1-2 GB)", "base (~2-3 GB)", 
            "small (~3-4 GB)", "medium (~5-7 GB)", 
            "large (~8-10 GB)"
        ])
        self.model_combo.setCurrentIndex(3)  # 預設 medium
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        settings_layout.addLayout(model_layout)
        
        # 輸出格式
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("輸出格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["SRT", "TXT"])
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        settings_layout.addLayout(format_layout)
        
        # 選項
        self.skip_diarization_cb = QCheckBox("跳過說話者分離")
        settings_layout.addWidget(self.skip_diarization_cb)
        
        self.use_gpu_cb = QCheckBox("使用 GPU 加速 (MPS)")
        self.use_gpu_cb.setChecked(True)
        settings_layout.addWidget(self.use_gpu_cb)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # 開始按鈕
        self.start_btn = QPushButton("開始轉錄")
        self.start_btn.clicked.connect(self.start_transcription)
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #357abd;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        layout.addWidget(self.start_btn)
        
        # 進度條
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 當前階段標籤
        self.stage_label = QLabel("")
        self.stage_label.setStyleSheet("color: #4a90e2; font-weight: bold;")
        self.stage_label.setVisible(False)
        layout.addWidget(self.stage_label)
        
        # 日誌區域
        log_group = QGroupBox("處理日誌")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #f0f0f0;
                font-family: 'Monaco', 'Menlo', 'Courier New';
                font-size: 11px;
            }
        """)
        # 設定為純文字模式以避免 QTextCursor 問題
        self.log_text.setAcceptRichText(False)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # 底部按鈕
        bottom_layout = QHBoxLayout()
        self.open_folder_btn = QPushButton("開啟輸出資料夾")
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        self.open_folder_btn.setEnabled(False)
        bottom_layout.addWidget(self.open_folder_btn)
        bottom_layout.addStretch()
        layout.addLayout(bottom_layout)
    
    def select_file(self):
        """選擇檔案"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "選擇影片檔案",
            "",
            "影片檔案 (*.mp4 *.mov *.avi *.mkv *.m4a);;所有檔案 (*.*)"
        )
        
        if file_path:
            self.set_current_file(file_path)
    
    def on_files_dropped(self, files):
        """處理拖放的檔案"""
        if files:
            self.set_current_file(files[0])
    
    def set_current_file(self, file_path):
        """設定當前檔案"""
        self.current_file = file_path
        file_name = Path(file_path).name
        self.file_label.setText(f"已選擇: {file_name}")
        self.file_label.setStyleSheet("color: #4a90e2; font-weight: bold;")
        self.start_btn.setEnabled(True)
        self.drop_zone.setText(f"✓ {file_name}\n\n點擊「選擇檔案」更換")
    
    def start_transcription(self):
        """開始轉錄"""
        if not self.current_file:
            return
        
        # 取得設定
        language = self.language_combo.currentText().split()[0]
        model = self.model_combo.currentText().split()[0]
        output_format = self.format_combo.currentText().lower()
        skip_diarization = self.skip_diarization_cb.isChecked()
        use_gpu = self.use_gpu_cb.isChecked()
        
        # 產生輸出檔名
        input_path = Path(self.current_file)
        output_path = input_path.parent / f"{input_path.stem}_transcription.{output_format.lower()}"
        
        # 停用控制項
        self.start_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.stage_label.setVisible(True)
        self.log_text.clear()
        
        # 建立並啟動 worker
        self.worker = ASRWorker(
            video_file=self.current_file,
            output_file=str(output_path),
            language=language,
            model_size=model,
            output_format=output_format,
            skip_diarization=skip_diarization,
            use_gpu=use_gpu
        )
        
        self.worker.progress.connect(self.on_progress)
        self.worker.stage_changed.connect(self.on_stage_changed)
        self.worker.log_message.connect(self.on_log_message)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        
        self.worker.start()
    
    def on_progress(self, value):
        """更新進度"""
        self.progress_bar.setValue(value)
    
    def on_stage_changed(self, stage):
        """更新當前階段"""
        self.stage_label.setText(f"當前階段: {stage}")
    
    def on_log_message(self, message):
        """添加日誌訊息"""
        # 使用 insertPlainText 而不是 append 以避免 QTextCursor 問題
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(message + '\n')
        self.log_text.setTextCursor(cursor)
        # 自動捲動到底部
        self.log_text.ensureCursorVisible()
    
    def on_finished(self, output_file):
        """處理完成"""
        self.progress_bar.setValue(100)
        self.stage_label.setText("✓ 處理完成！")
        
        # 啟用控制項
        self.start_btn.setEnabled(True)
        self.select_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(True)
        
        # 顯示完成訊息
        QMessageBox.information(
            self,
            "處理完成",
            f"轉錄完成！\n\n輸出檔案:\n{output_file}"
        )
    
    def on_error(self, error_msg):
        """處理錯誤"""
        self.stage_label.setText("✗ 處理失敗")
        self.stage_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        
        # 啟用控制項
        self.start_btn.setEnabled(True)
        self.select_btn.setEnabled(True)
        
        # 顯示錯誤訊息
        QMessageBox.critical(
            self,
            "處理錯誤",
            f"處理過程中發生錯誤:\n\n{error_msg}"
        )
    
    def open_output_folder(self):
        """開啟輸出資料夾"""
        if self.current_file:
            import subprocess
            folder = str(Path(self.current_file).parent)
            subprocess.run(["open", folder])

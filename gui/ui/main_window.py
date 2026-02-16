"""
主視窗 UI
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QComboBox, QCheckBox, QListWidget,
    QProgressBar, QFileDialog, QGroupBox, QMessageBox,
    QScrollArea, QLineEdit, QListWidgetItem, QSlider,
    QTextEdit, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont, QColor
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from pathlib import Path
import os
import re
import boto3

from core.asr_worker import ASRWorker
from core.summary_worker import SummaryWorker, DEFAULT_PROMPT


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
        self.output_file = None
        self.srt_segments = []  # 解析後的 SRT 段落
        self.summary_worker = None
        self._init_player()
        self.init_ui()
    
    def _init_player(self):
        """初始化音訊播放器"""
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)
        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)
    
    def init_ui(self):
        """初始化 UI"""
        self.setWindowTitle("ASR Multi-Speaker Transcription")
        self.setMinimumSize(800, 700)
        
        # 主要 widget — 用 QScrollArea 包裝，視窗縮小時可捲動
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setCentralWidget(scroll_area)
        
        content_widget = QWidget()
        scroll_area.setWidget(content_widget)
        
        # 主要佈局
        layout = QVBoxLayout(content_widget)
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
        
        # 第一行：語言 + 模型 + 輸出格式
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("語言:"))
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "zh (中文)", "en (英文)", "ja (日文)", 
            "auto (自動偵測)"
        ])
        row1.addWidget(self.language_combo)
        row1.addSpacing(15)
        row1.addWidget(QLabel("模型:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "tiny (~1-2 GB)", "base (~2-3 GB)", 
            "small (~3-4 GB)", "medium (~5-7 GB)", 
            "large (~8-10 GB)"
        ])
        self.model_combo.setCurrentIndex(3)
        row1.addWidget(self.model_combo)
        row1.addSpacing(15)
        row1.addWidget(QLabel("格式:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["SRT", "TXT"])
        row1.addWidget(self.format_combo)
        row1.addStretch()
        settings_layout.addLayout(row1)
        
        # 第二行：checkbox + HF Token
        row2 = QHBoxLayout()
        self.skip_diarization_cb = QCheckBox("跳過說話者分離")
        row2.addWidget(self.skip_diarization_cb)
        self.use_gpu_cb = QCheckBox("GPU 加速")
        self.use_gpu_cb.setChecked(True)
        row2.addWidget(self.use_gpu_cb)
        row2.addSpacing(15)
        row2.addWidget(QLabel("HF Token:"))
        self.hf_token_input = QLineEdit()
        self.hf_token_input.setPlaceholderText("說話者分離需要")
        self.hf_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.hf_token_input.setText(os.environ.get('HF_TOKEN', ''))
        row2.addWidget(self.hf_token_input)
        self.toggle_token_btn = QPushButton("顯示")
        self.toggle_token_btn.setFixedWidth(50)
        self.toggle_token_btn.clicked.connect(self._toggle_token_visibility)
        row2.addWidget(self.toggle_token_btn)
        self.save_token_btn = QPushButton("儲存")
        self.save_token_btn.setFixedWidth(50)
        self.save_token_btn.clicked.connect(self._save_hf_token)
        row2.addWidget(self.save_token_btn)
        settings_layout.addLayout(row2)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # 開始按鈕 + 進度條（同一行）
        action_layout = QHBoxLayout()
        self.start_btn = QPushButton("開始轉錄")
        self.start_btn.clicked.connect(self.start_transcription)
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setFixedWidth(120)
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a90e2;
                color: white;
                font-size: 14px;
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
        action_layout.addWidget(self.start_btn)
        
        self.stage_label = QLabel("")
        self.stage_label.setStyleSheet("color: #4a90e2; font-weight: bold;")
        self.stage_label.setVisible(False)
        action_layout.addWidget(self.stage_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumWidth(200)
        action_layout.addWidget(self.progress_bar)
        
        layout.addLayout(action_layout)
        
        # 日誌區域
        log_group = QGroupBox("處理日誌")
        log_layout = QVBoxLayout()
        self.log_list = QListWidget()
        self.log_list.setMinimumHeight(300)
        self.log_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                color: #f0f0f0;
                font-family: 'Monaco', 'Menlo', 'Courier New';
                font-size: 11px;
                border: none;
            }
            QListWidget::item {
                padding: 1px 4px;
                border: none;
            }
        """)
        self.log_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.log_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        log_layout.addWidget(self.log_list)
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
        
        # === 轉錄結果 + 播放區域（轉錄完成後顯示）===
        self.result_group = QGroupBox("轉錄結果（雙擊編輯，選取後按播放試聽）")
        self.result_group.setVisible(False)
        result_layout = QVBoxLayout()
        
        # 播放控制列
        player_layout = QHBoxLayout()
        self.play_btn = QPushButton("▶ 播放")
        self.play_btn.setFixedWidth(80)
        self.play_btn.clicked.connect(self._toggle_play)
        player_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.clicked.connect(self._stop_play)
        player_layout.addWidget(self.stop_btn)
        
        self.player_time_label = QLabel("00:00 / 00:00")
        self.player_time_label.setStyleSheet("color: #666; font-family: 'Monaco', 'Menlo', monospace;")
        player_layout.addWidget(self.player_time_label)
        
        self.player_slider = QSlider(Qt.Orientation.Horizontal)
        self.player_slider.setRange(0, 0)
        self.player_slider.sliderMoved.connect(self._on_slider_moved)
        player_layout.addWidget(self.player_slider)
        
        result_layout.addLayout(player_layout)
        
        # 字幕列表
        self.subtitle_list = QListWidget()
        self.subtitle_list.setMinimumHeight(250)
        self.subtitle_list.setEditTriggers(QListWidget.EditTrigger.DoubleClicked)
        self.subtitle_list.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Monaco', 'Menlo', 'Courier New';
                font-size: 12px;
                border: none;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:selected {
                background-color: #264f78;
                color: #ffffff;
            }
            QListWidget::item:hover {
                background-color: #2a2d2e;
            }
        """)
        self.subtitle_list.itemClicked.connect(self._on_subtitle_clicked)
        self.subtitle_list.itemDoubleClicked.connect(self._on_subtitle_double_clicked)
        self.subtitle_list.itemChanged.connect(self._on_subtitle_edited)
        self._editing_subtitle = False  # 防止 itemChanged 迴圈
        result_layout.addWidget(self.subtitle_list)
        
        # 儲存按鈕列
        save_layout = QHBoxLayout()
        self.save_srt_btn = QPushButton("💾 儲存修改")
        self.save_srt_btn.clicked.connect(self._save_srt)
        self.save_srt_btn.setEnabled(False)
        self.save_srt_btn.setStyleSheet("""
            QPushButton { background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px; padding: 6px 16px; }
            QPushButton:hover { background-color: #219a52; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        save_layout.addWidget(self.save_srt_btn)
        self.edit_hint_label = QLabel("雙擊字幕可編輯，修改後點擊儲存")
        self.edit_hint_label.setStyleSheet("color: #888; font-size: 11px;")
        save_layout.addWidget(self.edit_hint_label)
        save_layout.addStretch()
        result_layout.addLayout(save_layout)
        
        self.result_group.setLayout(result_layout)
        layout.addWidget(self.result_group)
        
        # === 會議摘要區域 ===
        self.summary_group = QGroupBox("會議摘要（AWS Bedrock Claude）")
        self.summary_group.setVisible(False)
        summary_layout = QVBoxLayout()
        
        # Prompt 編輯區
        prompt_label = QLabel("Prompt（可自訂）:")
        prompt_label.setStyleSheet("font-weight: bold;")
        summary_layout.addWidget(prompt_label)
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlainText(DEFAULT_PROMPT)
        self.prompt_edit.setMaximumHeight(120)
        self.prompt_edit.setStyleSheet("""
            QTextEdit {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-family: 'Monaco', 'Menlo', 'Courier New';
                font-size: 11px;
                padding: 4px;
            }
        """)
        summary_layout.addWidget(self.prompt_edit)
        
        # 模型選擇 + 產生按鈕
        summary_action_layout = QHBoxLayout()
        summary_action_layout.addWidget(QLabel("模型:"))
        self.bedrock_model_combo = QComboBox()
        self.bedrock_model_combo.setMinimumWidth(300)
        self.bedrock_model_combo.setEditable(True)  # 允許手動輸入 profile ID
        summary_action_layout.addWidget(self.bedrock_model_combo)
        
        self.refresh_models_btn = QPushButton("🔄")
        self.refresh_models_btn.setFixedWidth(32)
        self.refresh_models_btn.setToolTip("重新載入可用模型")
        self.refresh_models_btn.clicked.connect(self._load_bedrock_models)
        summary_action_layout.addWidget(self.refresh_models_btn)
        
        summary_action_layout.addWidget(QLabel("Region:"))
        self.bedrock_region_combo = QComboBox()
        self.bedrock_region_combo.setFixedWidth(170)
        # Bedrock Claude 常用 regions
        self._bedrock_regions = [
            ("ap-northeast-1 (東京)", "ap-northeast-1"),
            ("us-east-1 (維吉尼亞)", "us-east-1"),
            ("us-west-2 (奧勒岡)", "us-west-2"),
            ("eu-west-1 (愛爾蘭)", "eu-west-1"),
            ("eu-central-1 (法蘭克福)", "eu-central-1"),
            ("ap-southeast-1 (新加坡)", "ap-southeast-1"),
            ("ap-southeast-2 (雪梨)", "ap-southeast-2"),
            ("ap-northeast-2 (首爾)", "ap-northeast-2"),
        ]
        for label, rid in self._bedrock_regions:
            self.bedrock_region_combo.addItem(label, rid)
        # 預設選 .env 儲存的 region，fallback 到 us-east-1
        saved_region, saved_model = self._load_bedrock_settings()
        target_region = saved_region or "us-east-1"
        for i, (_, rid) in enumerate(self._bedrock_regions):
            if rid == target_region:
                self.bedrock_region_combo.setCurrentIndex(i)
                break
        self._saved_bedrock_model = saved_model or "amazon.nova-2-lite-v1:0"
        self.bedrock_region_combo.currentIndexChanged.connect(self._on_region_changed)
        summary_action_layout.addWidget(self.bedrock_region_combo)
        
        self.refresh_models_btn = QPushButton("🔄")
        self.refresh_models_btn.setFixedWidth(32)
        self.refresh_models_btn.setToolTip("重新載入可用模型")
        self.refresh_models_btn.clicked.connect(self._load_bedrock_models)
        summary_action_layout.addWidget(self.refresh_models_btn)
        
        self.generate_summary_btn = QPushButton("🤖 產生摘要")
        self.generate_summary_btn.clicked.connect(self._generate_summary)
        self.generate_summary_btn.setStyleSheet("""
            QPushButton { background-color: #8e44ad; color: white; font-weight: bold; border-radius: 4px; padding: 6px 16px; }
            QPushButton:hover { background-color: #7d3c98; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        summary_action_layout.addWidget(self.generate_summary_btn)
        summary_action_layout.addStretch()
        summary_layout.addLayout(summary_action_layout)
        
        # 摘要狀態
        self.summary_status_label = QLabel("")
        self.summary_status_label.setStyleSheet("color: #8e44ad; font-weight: bold;")
        summary_layout.addWidget(self.summary_status_label)
        
        # 摘要結果
        self.summary_output = QTextEdit()
        self.summary_output.setReadOnly(True)
        self.summary_output.setMinimumHeight(250)
        self.summary_output.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Monaco', 'Menlo', 'Courier New';
                font-size: 12px;
                border: none;
                padding: 8px;
            }
        """)
        summary_layout.addWidget(self.summary_output)
        
        # 儲存摘要按鈕
        save_summary_layout = QHBoxLayout()
        self.save_summary_btn = QPushButton("💾 儲存摘要")
        self.save_summary_btn.clicked.connect(self._save_summary)
        self.save_summary_btn.setEnabled(False)
        save_summary_layout.addWidget(self.save_summary_btn)
        save_summary_layout.addStretch()
        summary_layout.addLayout(save_summary_layout)
        
        self.summary_group.setLayout(summary_layout)
        layout.addWidget(self.summary_group)
        
        # 載入上次的 ASR 設定
        self._load_asr_settings()
    
    def _toggle_token_visibility(self):
        """切換 token 顯示/隱藏"""
        if self.hf_token_input.echoMode() == QLineEdit.EchoMode.Password:
            self.hf_token_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_token_btn.setText("隱藏")
        else:
            self.hf_token_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_token_btn.setText("顯示")
    
    def _save_hf_token(self):
        """將 HF Token 儲存到 .env 檔案"""
        token = self.hf_token_input.text().strip()
        if not token:
            QMessageBox.warning(self, "警告", "請輸入 HF Token")
            return
        
        # 更新環境變數
        os.environ['HF_TOKEN'] = token
        
        # 寫入 .env 檔案
        env_path = Path(__file__).parent.parent.parent / '.env'
        
        if env_path.exists():
            content = env_path.read_text(encoding='utf-8')
            # 替換現有的 HF_TOKEN 行
            if re.search(r'^HF_TOKEN=', content, re.MULTILINE):
                content = re.sub(r'^HF_TOKEN=.*$', f'HF_TOKEN={token}', content, flags=re.MULTILINE)
            else:
                content = content.rstrip('\n') + f'\nHF_TOKEN={token}\n'
        else:
            content = (
                "# Hugging Face Token\n"
                "# 取得方式：https://huggingface.co/settings/tokens\n"
                "# 需要接受 pyannote/speaker-diarization-3.1 模型的使用條款\n"
                f"HF_TOKEN={token}\n"
            )
        
        env_path.write_text(content, encoding='utf-8')
        QMessageBox.information(self, "已儲存", "HF Token 已儲存至 .env 檔案")
    
    def _get_env_path(self):
        """取得 .env 檔案路徑"""
        return Path(__file__).parent.parent.parent / '.env'
    
    def _load_bedrock_settings(self):
        """從 .env 讀取上次使用的 Bedrock region 和 model"""
        region = self._read_env('BEDROCK_REGION')
        model = self._read_env('BEDROCK_MODEL')
        return region, model
    
    def _save_bedrock_settings(self, region, model_id):
        """將 Bedrock region 和 model 儲存到 .env"""
        self._write_env('BEDROCK_REGION', region)
        self._write_env('BEDROCK_MODEL', model_id)
    
    def _read_env(self, key):
        """從 .env 讀取指定 key 的值"""
        env_path = self._get_env_path()
        if env_path.exists():
            for line in env_path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if line.startswith(f'{key}='):
                    return line.split('=', 1)[1].strip()
        return None
    
    def _write_env(self, key, value):
        """將指定 key=value 寫入 .env（更新或新增）"""
        env_path = self._get_env_path()
        if env_path.exists():
            content = env_path.read_text(encoding='utf-8')
        else:
            content = ""
        if re.search(rf'^{key}=', content, re.MULTILINE):
            content = re.sub(rf'^{key}=.*', f'{key}={value}', content, flags=re.MULTILINE)
        else:
            content = content.rstrip('\n') + f'\n{key}={value}\n'
        env_path.write_text(content, encoding='utf-8')
    
    def _load_asr_settings(self):
        """從 .env 載入 ASR 設定並套用到 UI"""
        # Whisper 模型
        saved_model = self._read_env('ASR_MODEL')
        if saved_model:
            for i in range(self.model_combo.count()):
                if self.model_combo.itemText(i).startswith(saved_model):
                    self.model_combo.setCurrentIndex(i)
                    break
        # 語言
        saved_lang = self._read_env('ASR_LANGUAGE')
        if saved_lang:
            for i in range(self.language_combo.count()):
                if self.language_combo.itemText(i).startswith(saved_lang):
                    self.language_combo.setCurrentIndex(i)
                    break
        # 輸出格式
        saved_fmt = self._read_env('ASR_FORMAT')
        if saved_fmt:
            idx = self.format_combo.findText(saved_fmt, Qt.MatchFlag.MatchExactly)
            if idx >= 0:
                self.format_combo.setCurrentIndex(idx)
        # GPU
        saved_gpu = self._read_env('ASR_USE_GPU')
        if saved_gpu is not None:
            self.use_gpu_cb.setChecked(saved_gpu.lower() == 'true')
        # 跳過說話者分離
        saved_skip = self._read_env('ASR_SKIP_DIARIZATION')
        if saved_skip is not None:
            self.skip_diarization_cb.setChecked(saved_skip.lower() == 'true')
    
    def _save_asr_settings(self):
        """將目前 ASR 設定儲存到 .env"""
        model = self.model_combo.currentText().split()[0]
        language = self.language_combo.currentText().split()[0]
        fmt = self.format_combo.currentText()
        self._write_env('ASR_MODEL', model)
        self._write_env('ASR_LANGUAGE', language)
        self._write_env('ASR_FORMAT', fmt)
        self._write_env('ASR_USE_GPU', str(self.use_gpu_cb.isChecked()))
        self._write_env('ASR_SKIP_DIARIZATION', str(self.skip_diarization_cb.isChecked()))
    
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
        
        # 儲存 ASR 設定
        self._save_asr_settings()

        # 產生輸出檔名
        input_path = Path(self.current_file)
        output_path = input_path.parent / f"{input_path.stem}_transcription.{output_format.lower()}"

        # 停用控制項
        self.start_btn.setEnabled(False)
        self.select_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.stage_label.setVisible(True)
        self.log_list.clear()

        # 重置字幕/播放器/摘要狀態
        self.player.stop()
        self.srt_segments = []
        self.subtitle_list.clear()
        self.result_group.setVisible(False)
        self.summary_group.setVisible(False)
        self.summary_output.clear()
        self.summary_status_label.setText("")
        self.save_srt_btn.setEnabled(False)
        self.save_summary_btn.setEnabled(False)
        self.edit_hint_label.setText("雙擊字幕可編輯，修改後點擊儲存")
        self.edit_hint_label.setStyleSheet("color: #888; font-size: 11px;")

        # 建立並啟動 worker
        self.worker = ASRWorker(
            video_file=self.current_file,
            output_file=str(output_path),
            language=language,
            model_size=model,
            output_format=output_format,
            skip_diarization=skip_diarization,
            use_gpu=use_gpu,
            hf_token=self.hf_token_input.text().strip()
        )

        self.worker.progress.connect(self.on_progress)
        self.worker.stage_changed.connect(self.on_stage_changed)
        self.worker.log_message.connect(self.on_log_message)
        self.worker.log_replace.connect(self.on_log_replace)
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
        self.log_list.addItem(message)
        self.log_list.scrollToBottom()
    
    def on_log_replace(self, message):
        """覆蓋最後一行日誌（用於 tqdm 進度更新）"""
        count = self.log_list.count()
        if count > 0:
            self.log_list.item(count - 1).setText(message)
        else:
            self.log_list.addItem(message)
        self.log_list.scrollToBottom()
    
    def on_finished(self, output_file):
        """處理完成"""
        self.output_file = output_file
        self.progress_bar.setValue(100)
        self.stage_label.setText("✓ 處理完成！")
        
        # 啟用控制項
        self.start_btn.setEnabled(True)
        self.select_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(True)
        
        # 載入字幕結果
        if output_file.endswith('.srt'):
            self._load_subtitles(output_file)
            self.summary_group.setVisible(True)
            # 動態載入 Bedrock 模型列表（首次顯示時）
            if self.bedrock_model_combo.count() == 0:
                self._load_bedrock_models()
        
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
    
    # === SRT 解析 + 播放功能 ===
    
    def _parse_srt(self, srt_path):
        """解析 SRT 檔案，回傳段落列表"""
        segments = []
        try:
            content = Path(srt_path).read_text(encoding='utf-8')
            blocks = content.strip().split('\n\n')
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 3:
                    # 解析時間戳: 00:00:00,000 --> 00:00:02,500
                    time_match = re.match(
                        r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})',
                        lines[1]
                    )
                    if time_match:
                        g = time_match.groups()
                        start_ms = (int(g[0])*3600 + int(g[1])*60 + int(g[2])) * 1000 + int(g[3])
                        end_ms = (int(g[4])*3600 + int(g[5])*60 + int(g[6])) * 1000 + int(g[7])
                        text = '\n'.join(lines[2:])
                        segments.append({
                            'start_ms': start_ms,
                            'end_ms': end_ms,
                            'text': text,
                            'time_str': lines[1],
                        })
        except Exception as e:
            self.log_list.addItem(f"⚠ SRT 解析失敗: {e}")
        return segments
    
    def _load_subtitles(self, srt_path):
        """載入 SRT 並顯示在字幕列表"""
        self.srt_segments = self._parse_srt(srt_path)
        self.subtitle_list.clear()

        for seg in self.srt_segments:
            start_str = self._ms_to_time_str(seg['start_ms'])
            item = QListWidgetItem(f"[{start_str}] {seg['text']}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.subtitle_list.addItem(item)

        if self.srt_segments:
            self.result_group.setVisible(True)
            # 避免重複 connect
            try:
                self.player.durationChanged.disconnect(self._on_duration_changed)
            except TypeError:
                pass
            self.player.setSource(QUrl.fromLocalFile(self.current_file))
            self.player.durationChanged.connect(self._on_duration_changed)
    
    def _ms_to_time_str(self, ms):
        """毫秒轉 MM:SS"""
        total_sec = ms // 1000
        m = total_sec // 60
        s = total_sec % 60
        return f"{m:02d}:{s:02d}"
    
    def _on_subtitle_clicked(self, item):
        """單擊字幕行 → 只選取，不播放"""
        pass
    
    def _toggle_play(self):
        """播放/暫停切換。如果有選取字幕行，從該行時間點開始播放"""
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            # 如果有選取字幕行且目前是停止狀態，從該行開始播放
            row = self.subtitle_list.currentRow()
            if row >= 0 and row < len(self.srt_segments) and self.player.playbackState() == QMediaPlayer.PlaybackState.StoppedState:
                self.player.setPosition(self.srt_segments[row]['start_ms'])
            self.player.play()
    
    def _stop_play(self):
        """停止播放"""
        self.player.stop()
    
    def _on_slider_moved(self, position):
        """拖動進度條"""
        self.player.setPosition(position)
    
    def _on_duration_changed(self, duration):
        """媒體總時長更新"""
        self.player_slider.setRange(0, duration)
    
    def _on_player_position_changed(self, position):
        """播放位置更新 → 更新進度條和時間標籤，高亮當前字幕"""
        self.player_slider.setValue(position)
        
        # 更新時間標籤
        duration = self.player.duration()
        self.player_time_label.setText(
            f"{self._ms_to_time_str(position)} / {self._ms_to_time_str(duration)}"
        )
        
        # 高亮當前播放的字幕行
        for i, seg in enumerate(self.srt_segments):
            if seg['start_ms'] <= position < seg['end_ms']:
                if self.subtitle_list.currentRow() != i:
                    self.subtitle_list.setCurrentRow(i)
                    self.subtitle_list.scrollToItem(self.subtitle_list.item(i))
                break
    
    def _on_playback_state_changed(self, state):
        """播放狀態變更 → 更新按鈕文字"""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_btn.setText("⏸ 暫停")
        else:
            self.play_btn.setText("▶ 播放")
    
    # === 字幕編輯功能 ===
    
    def _on_subtitle_double_clicked(self, item):
        """雙擊字幕行 → editTriggers 已處理編輯，這裡標記狀態"""
        self._editing_subtitle = True
    
    def _on_subtitle_edited(self, item):
        """字幕編輯完成 → 更新 srt_segments 資料"""
        if not self._editing_subtitle:
            return
        self._editing_subtitle = False
        
        row = self.subtitle_list.row(item)
        if row < len(self.srt_segments):
            new_text = item.text()
            # 從顯示文字中提取實際字幕（去掉時間戳前綴 [MM:SS] ）
            match = re.match(r'^\[\d{2}:\d{2}\]\s*', new_text)
            if match:
                new_text = new_text[match.end():]
            self.srt_segments[row]['text'] = new_text
            self.save_srt_btn.setEnabled(True)
            self.edit_hint_label.setText("有未儲存的修改")
            self.edit_hint_label.setStyleSheet("color: #e67e22; font-size: 11px; font-weight: bold;")
            # 高亮已修改的行
            item.setBackground(QColor("#3d3522"))
            item.setForeground(QColor("#f0c040"))
    
    def _save_srt(self):
        """將修改後的字幕存回 SRT 檔案"""
        if not self.output_file or not self.srt_segments:
            return
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                for i, seg in enumerate(self.srt_segments, 1):
                    f.write(f"{i}\n")
                    f.write(f"{seg['time_str']}\n")
                    f.write(f"{seg['text']}\n\n")
            
            self.save_srt_btn.setEnabled(False)
            self.edit_hint_label.setText("✓ 已儲存")
            self.edit_hint_label.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
            # 清除所有行的修改高亮
            for i in range(self.subtitle_list.count()):
                it = self.subtitle_list.item(i)
                it.setBackground(QColor("transparent"))
                it.setForeground(QColor("#d4d4d4"))
            self.log_list.addItem(f"✓ 字幕已儲存至 {self.output_file}")
            self.log_list.scrollToBottom()
        except Exception as e:
            QMessageBox.critical(self, "儲存失敗", f"無法儲存字幕:\n{e}")

    # === 會議摘要功能 ===
    
    def _get_transcript_text(self):
        """從 srt_segments 組合出純文字轉錄內容"""
        lines = []
        for seg in self.srt_segments:
            lines.append(seg['text'])
        return '\n'.join(lines)
    
    def _generate_summary(self):
        """產生會議摘要"""
        if not self.srt_segments:
            QMessageBox.warning(self, "警告", "沒有轉錄結果可供摘要")
            return
        
        transcript = self._get_transcript_text()
        prompt_template = self.prompt_edit.toPlainText()
        # 優先從 itemData 取 inference profile ID，fallback 到顯示文字
        idx = self.bedrock_model_combo.currentIndex()
        model_id = None
        if idx >= 0:
            model_id = self.bedrock_model_combo.itemData(idx)
        if not model_id:
            model_id = self.bedrock_model_combo.currentText()
        region = self.bedrock_region_combo.currentData() or "us-east-1"
        
        # 儲存選擇到 .env
        self._save_bedrock_settings(region, model_id)
        
        self.generate_summary_btn.setEnabled(False)
        self.summary_status_label.setText("⏳ 產生摘要中...")
        self.summary_output.clear()
        self.log_list.addItem(f"📤 摘要模型: {model_id}")
        self.log_list.scrollToBottom()
        
        self.summary_worker = SummaryWorker(
            transcript=transcript,
            prompt_template=prompt_template,
            model_id=model_id,
            region=region
        )
        self.summary_worker.progress.connect(self._on_summary_progress)
        self.summary_worker.finished.connect(self._on_summary_finished)
        self.summary_worker.error.connect(self._on_summary_error)
        self.summary_worker.start()
    
    def _on_summary_progress(self, msg):
        """摘要進度更新"""
        self.summary_status_label.setText(msg)
    
    def _on_summary_finished(self, summary):
        """摘要完成"""
        self.summary_output.setPlainText(summary)
        self.summary_status_label.setText("✓ 摘要產生完成")
        self.generate_summary_btn.setEnabled(True)
        self.save_summary_btn.setEnabled(True)
    
    def _on_summary_error(self, error_msg):
        """摘要錯誤"""
        self.summary_status_label.setText("✗ 摘要產生失敗")
        self.summary_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        self.generate_summary_btn.setEnabled(True)
        QMessageBox.critical(self, "摘要錯誤", f"產生摘要時發生錯誤:\n\n{error_msg}")
    
    def _save_summary(self):
        """儲存摘要到檔案"""
        if not self.output_file:
            return
        
        summary_path = Path(self.output_file).with_suffix('.summary.md')
        try:
            summary_path.write_text(self.summary_output.toPlainText(), encoding='utf-8')
            self.log_list.addItem(f"✓ 摘要已儲存至 {summary_path}")
            self.log_list.scrollToBottom()
            QMessageBox.information(self, "已儲存", f"摘要已儲存至:\n{summary_path}")
        except Exception as e:
            QMessageBox.critical(self, "儲存失敗", f"無法儲存摘要:\n{e}")

    def _on_region_changed(self, index):
        """Region 切換時自動重新載入模型列表"""
        if index >= 0 and self.summary_group.isVisible():
            self._load_bedrock_models()

    def _load_bedrock_models(self):
        """從 Bedrock API 動態載入可用的 Claude inference profiles"""
        import threading

        self.refresh_models_btn.setEnabled(False)
        self.refresh_models_btn.setText("⏳")
        self.bedrock_model_combo.clear()
        self.bedrock_model_combo.addItem("載入中...")

        region = self.bedrock_region_combo.currentData() or "ap-northeast-1"

        def _fetch():
            try:
                session = boto3.Session()
                client = session.client("bedrock", region_name=region)

                profiles = []
                paginator = client.get_paginator('list_inference_profiles')
                for page in paginator.paginate():
                    for p in page.get('inferenceProfileSummaries', []):
                        pid = p.get('inferenceProfileId', '')
                        name = p.get('inferenceProfileName', pid)
                        # 保留 Claude / Anthropic 和 Amazon Nova 模型
                        if 'anthropic' in pid.lower() or 'claude' in name.lower() \
                                or 'nova' in pid.lower() or 'nova' in name.lower():
                            profiles.append((name, pid))

                # 排序：Opus > Sonnet > Haiku > Nova Pro > Nova Lite > Nova Micro
                def _sort_key(item):
                    n = item[0].lower()
                    if 'opus' in n:
                        return (0, n)
                    elif 'sonnet' in n:
                        return (1, n)
                    elif 'haiku' in n:
                        return (2, n)
                    elif 'nova' in n and 'pro' in n:
                        return (3, n)
                    elif 'nova' in n and 'lite' in n:
                        return (4, n)
                    elif 'nova' in n:
                        return (5, n)
                    return (6, n)

                profiles.sort(key=_sort_key)

                # 回到 UI 執行緒更新 combo box
                from PyQt6.QtCore import QMetaObject, Qt as QtNamespace, Q_ARG
                self._bedrock_profiles = profiles
                QMetaObject.invokeMethod(
                    self, "_apply_bedrock_models",
                    QtNamespace.ConnectionType.QueuedConnection
                )
            except Exception as e:
                self._bedrock_load_error = str(e)
                from PyQt6.QtCore import QMetaObject, Qt as QtNamespace
                QMetaObject.invokeMethod(
                    self, "_apply_bedrock_models_error",
                    QtNamespace.ConnectionType.QueuedConnection
                )

        threading.Thread(target=_fetch, daemon=True).start()

    @pyqtSlot()
    def _apply_bedrock_models(self):
        """在 UI 執行緒中套用載入的模型列表"""
        self.bedrock_model_combo.clear()
        profiles = getattr(self, '_bedrock_profiles', [])
        if profiles:
            for name, pid in profiles:
                self.bedrock_model_combo.addItem(f"{name}", pid)
            # 優先選上次使用的模型
            saved_model = getattr(self, '_saved_bedrock_model', '')
            selected = False
            if saved_model:
                for i in range(self.bedrock_model_combo.count()):
                    if self.bedrock_model_combo.itemData(i) == saved_model:
                        self.bedrock_model_combo.setCurrentIndex(i)
                        selected = True
                        break
            # fallback: 選第一個 nova-2-lite 或 sonnet
            if not selected:
                for i in range(self.bedrock_model_combo.count()):
                    pid = self.bedrock_model_combo.itemData(i) or ''
                    if 'nova-2-lite' in pid:
                        self.bedrock_model_combo.setCurrentIndex(i)
                        selected = True
                        break
            if not selected and self.bedrock_model_combo.count() > 0:
                self.bedrock_model_combo.setCurrentIndex(0)
        else:
            self._add_fallback_models()
        self.refresh_models_btn.setEnabled(True)
        self.refresh_models_btn.setText("🔄")

    @pyqtSlot()
    def _apply_bedrock_models_error(self):
        """載入模型失敗時使用 fallback"""
        error = getattr(self, '_bedrock_load_error', 'Unknown error')
        self.log_list.addItem(f"⚠ 載入 Bedrock 模型失敗: {error}，使用預設列表")
        self.log_list.scrollToBottom()
        self._add_fallback_models()
        self.refresh_models_btn.setEnabled(True)
        self.refresh_models_btn.setText("🔄")

    def _add_fallback_models(self):
        """API 失敗時的預設模型列表"""
        fallback = [
            ("Claude Sonnet 4 (APAC)", "apac.anthropic.claude-sonnet-4-20250514-v1:0"),
            ("Claude Sonnet 3.5 v2 (APAC)", "apac.anthropic.claude-3-5-sonnet-20241022-v2:0"),
            ("Claude Haiku 3 (APAC)", "apac.anthropic.claude-3-haiku-20240307-v1:0"),
            ("Amazon Nova Pro", "amazon.nova-pro-v1:0"),
            ("Amazon Nova Lite", "amazon.nova-lite-v1:0"),
            ("Amazon Nova Micro", "amazon.nova-micro-v1:0"),
        ]
        self.bedrock_model_combo.clear()
        for name, pid in fallback:
            self.bedrock_model_combo.addItem(name, pid)


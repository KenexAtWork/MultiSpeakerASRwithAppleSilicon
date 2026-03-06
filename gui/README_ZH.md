# ASR Multi-Speaker Transcription - GUI 版本

使用 PyQt6 建立的圖形界面版本。

## 功能特色

- ✅ 拖放檔案支援
- ✅ 即時處理進度顯示
- ✅ 處理日誌即時更新
- ✅ 支援多種語言和模型選擇
- ✅ 模型下載狀態標示（✅ 已下載 / ⬇ 未下載）
- ✅ 可選擇輸出格式（SRT/TXT）
- ✅ 背景處理，UI 不凍結
- ✅ 即時 ASR — 麥克風即時轉錄，支援 MLX Whisper、Qwen3-ASR、AWS Transcribe
- ✅ 系統音訊擷取 — 透過 BlackHole 錄製線上會議（Zoom、Teams 等）
- ✅ 雙重 ASR 精煉（錄音中漸進式 + 錄音後完整精煉）
- ✅ 轉送 VOD — 將即時錄音轉送至檔案轉錄進行說話者分離
- ✅ 即時筆記 — 錄音中透過 AWS Bedrock 自動摘要
- ✅ 字幕編輯、音訊播放、點擊跳轉
- ✅ AWS Bedrock 會議摘要

## 系統需求

- macOS（支援 Apple Silicon M1/M2/M3）
- Python 3.10（重要：PyQt6 目前不支援 Python 3.11+）
- 16GB RAM（建議）

## 安裝

### 快速開始（推薦）

```bash
# 1. 建立 Python 3.10 虛擬環境
python3.10 -m venv .venv

# 2. 啟動虛擬環境
source .venv/bin/activate

# 3. 安裝所有套件
pip install mlx-whisper pyannote-audio PyQt6

# 4. 設定 Hugging Face Token
cp .env.example .env
# 編輯 .env 並填入你的 HF_TOKEN

# 5. 啟動 GUI
./run_gui.sh
```

### 詳細安裝步驟

#### 方式 1：使用標準 venv（推薦）

```bash
# 確認 Python 版本（必須是 3.10）
python3.10 --version

# 建立虛擬環境
python3.10 -m venv .venv

# 啟動環境
source .venv/bin/activate

# 安裝套件
pip install mlx-whisper pyannote-audio PyQt6

# 啟動 GUI
./run_gui.sh
```

#### 方式 2：使用 Homebrew Python 3.10

如果系統沒有 Python 3.10：

```bash
# 安裝 Python 3.10
brew install python@3.10

# 建立虛擬環境
/opt/homebrew/bin/python3.10 -m venv .venv

# 啟動環境
source .venv/bin/activate

# 安裝套件
pip install mlx-whisper pyannote-audio PyQt6

# 啟動 GUI
./run_gui.sh
```

#### 重要提醒

- PyQt6 目前僅支援 Python 3.10，不支援 3.11 或更新版本
- 如果遇到 `ModuleNotFoundError: No module named 'PyQt6'`，請確認：
  1. 虛擬環境已正確啟動
  2. PyQt6 已安裝在虛擬環境中（不是系統 Python）
  3. Python 版本是 3.10

### 環境變數設定

確保已設定 `HF_TOKEN`：

```bash
# 複製範例檔案
cp .env.example .env

# 編輯 .env 並填入你的 token
# HF_TOKEN=your_huggingface_token_here
```

## 使用方式

### 啟動 GUI

```bash
# 從 gui 目錄啟動
cd gui
python main.py

# 或從 asr 目錄啟動
python gui/main.py
```

### 使用步驟

1. **選擇檔案**
   - 拖放影片檔案到視窗中
   - 或點擊「選擇檔案」按鈕

2. **設定參數**
   - 選擇語言（中文/英文/日文/自動）
   - 選擇模型大小（tiny/base/small/medium/large）
   - 選擇輸出格式（SRT/TXT）
   - 可選：跳過說話者分離
   - 可選：停用 GPU 加速

3. **開始處理**
   - 點擊「開始轉錄」按鈕
   - 觀察進度條和日誌輸出
   - 等待處理完成

4. **查看結果**
   - 處理完成後會顯示通知
   - 點擊「開啟輸出資料夾」查看結果

## 專案結構

```
gui/
├── main.py              # 主程式入口
├── ui/
│   ├── __init__.py
│   ├── main_window.py   # 主視窗 UI（檔案轉錄分頁）
│   └── realtime_panel.py # 即時 ASR 分頁
├── core/
│   ├── __init__.py
│   ├── asr_worker.py         # 背景 ASR 處理 Worker
│   ├── realtime_worker.py    # 即時麥克風轉錄 Worker
│   ├── refinement_worker.py  # 雙重精煉 Workers
│   ├── summary_worker.py     # AWS Bedrock 摘要 Worker
│   └── live_summary_worker.py # 錄音中即時摘要
├── utils/
│   └── __init__.py
├── resources/           # 資源檔案（圖示等）
├── requirements.txt     # Python 套件需求
└── README.md           # 本檔案
```

## 技術細節

### 架構

- **PyQt6**: 跨平台 GUI 框架
- **QThread**: 背景執行 ASR，避免 UI 凍結
- **Signal/Slot**: 更新進度和日誌
- **拖放支援**: QDragDrop 實作

### 關鍵組件

1. **MainWindow** (`ui/main_window.py`)
   - 檔案轉錄分頁 UI
   - 模型選擇含下載狀態標示
   - 字幕編輯、音訊播放、說話者對應
   - AWS Bedrock 摘要

2. **RealtimePanel** (`ui/realtime_panel.py`)
   - 麥克風即時轉錄
   - 多引擎支援（MLX Whisper、Qwen3-ASR、AWS Transcribe）
   - 透過 BlackHole 擷取系統音訊錄製線上會議
   - 雙重 ASR 精煉（漸進式 + 錄音後）
   - 轉送 VOD 進行說話者分離
   - 即時筆記自動摘要

3. **ASRWorker** (`core/asr_worker.py`)
   - 在背景執行緒中執行 ASR
   - 發送進度和日誌信號
   - 處理錯誤

4. **DropZone** (`ui/main_window.py`)
   - 自定義拖放區域
   - 支援拖放檔案

## 未來改進

- [ ] 批次處理多個檔案
- [ ] 儲存和載入設定
- [ ] 處理歷史記錄
- [ ] 更詳細的進度顯示（各階段進度）
- [ ] 支援取消處理
- [ ] 打包成 .app（使用 py2app）
- [ ] 支援更多輸出格式
- [ ] 預覽轉錄結果

## 打包成 macOS App

（待實作）

```bash
# 使用 py2app 打包
pip install py2app
python setup.py py2app
```

## 疑難排解

### 問題：找不到 asr_multi_speaker_v5_fast 模組

確保從正確的目錄啟動，或檢查 `sys.path` 設定。

### 問題：UI 凍結

確認 ASR 處理是在 QThread 中執行，而非主執行緒。

### 問題：無法拖放檔案

檢查 `setAcceptDrops(True)` 是否正確設定。

## 授權

MIT License

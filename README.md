# ASR Multi-Speaker Transcription

使用 MLX Whisper 和 pyannote.audio 進行語音轉錄和說話者分離的工具，針對 Apple Silicon (M1/M2/M3) Mac 優化。

## 功能特色

- ✅ 使用 MLX Whisper 進行高效能 ASR 轉錄（Apple Silicon 原生加速）
- ✅ 使用 pyannote.audio 進行說話者分離
- ✅ 支援 MPS (Metal Performance Shaders) GPU 加速
- ✅ 多執行緒優化，充分利用 M1/M2/M3 效能核心
- ✅ 自動處理影片音訊提取
- ✅ 支援多種語言（中文、英文、日文等）

## 系統需求

- macOS (Apple Silicon: M1/M2/M3)
- Python 3.10+
- ffmpeg
- Hugging Face 帳號（用於說話者分離）

## 安裝

### 1. 安裝系統依賴

```bash
# 安裝 Homebrew（如果還沒安裝）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安裝 ffmpeg
brew install ffmpeg

# 安裝 uv（Python 套件管理工具）
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### 2. 建立 Python 環境

```bash
cd asr

# 使用 uv 建立虛擬環境（使用 ARM64 原生 Python）
uv venv --python /opt/homebrew/bin/python3

# 啟動環境
source .venv/bin/activate

# 安裝 Python 套件
uv pip install mlx-whisper pyannote-audio
```

### 3. 設定 Hugging Face Token

說話者分離功能需要 Hugging Face token：

1. 前往 https://huggingface.co/settings/tokens 建立 token
2. 接受模型使用條款：
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
3. 設定環境變數：

```bash
export HF_TOKEN=your_huggingface_token_here
```

或複製 `.env.example` 為 `.env` 並填入 token。

**詳細申請教學：** [如何申請 Hugging Face Token](https://ithelp.ithome.com.tw/articles/10389679)

## 使用方式

### 方法 1：使用便捷腳本（推薦）

```bash
# 基本使用（自動產生輸出檔名）
./asr.sh video.mp4

# 指定輸出檔名
./asr.sh video.mp4 output.txt

# 指定語言
./asr.sh video.mp4 output.txt --language en

# 只做 ASR 轉錄（跳過說話者分離）
./asr.sh video.mp4 output.txt --skip-diarization

# 使用 CPU 而非 GPU
./asr.sh video.mp4 output.txt --no-gpu

# 自訂 HF token
./asr.sh video.mp4 output.txt --hf-token YOUR_TOKEN
```

### 方法 2：直接執行 Python 腳本

```bash
source .venv/bin/activate

python asr_multi_speaker_v5_fast.py \
  --input video.mp4 \
  --output output.txt \
  --language zh \
  --hf-token YOUR_TOKEN
```

## 支援的語言

- `zh`: 中文
- `en`: 英文
- `ja`: 日文
- `es`: 西班牙文
- `fr`: 法文
- `de`: 德文
- `it`: 義大利文
- `pt`: 葡萄牙文
- `ru`: 俄文
- `ko`: 韓文

### 語言混合支援

MLX Whisper 可以處理語言混合的音訊（如中英混雜），有兩種方式：

**方法 1：自動偵測（推薦用於混合語言）**
```bash
# 不指定 --language，讓 Whisper 自動偵測
./asr.sh video.mp4 output.txt
```

**方法 2：指定主要語言**
```bash
# 指定主要語言（如果音訊以中文為主）
./asr.sh video.mp4 output.txt --language zh
```

**注意：**
- 如果指定語言，Whisper 會用該語言模型處理整段音訊
- 對於中英混雜的音訊，建議不指定語言，讓它自動偵測
- 英文部分可能會被正確識別，也可能被轉成拼音（取決於比例）

## 效能

在 M1 Pro (8 核心 CPU, 14 核心 GPU) 上的測試結果：

| 影片長度 | 處理時間 | 加速比 |
|---------|---------|--------|
| 90 秒   | ~45 秒  | 2x     |
| 3 分鐘  | ~55 秒  | 3.3x   |
| 31 分鐘 | ~10 分鐘 | 3.1x   |

使用 GPU 加速比 CPU 快約 6 倍。

## 輸出格式

輸出為文字檔，格式如下：

```
[SPEAKER_00] 00:00:00,000 --> 00:00:02,500
請 SA Kevin 這邊來做說明

[SPEAKER_00] 00:00:02,500 --> 00:00:04,200
那我先把聲音交給 Kevin

[SPEAKER_01] 00:00:06,239 --> 00:00:06,639
好

[SPEAKER_01] 00:00:07,359 --> 00:00:09,960
各位 AW 長官還有各位同事大家好
```

## 疑難排解

### 問題：找不到 ffmpeg

```bash
brew install ffmpeg
```

### 問題：找不到 mlx 模組

確認使用 ARM64 原生 Python：

```bash
file $(which python)
# 應該顯示：Mach-O 64-bit executable arm64
```

如果是 x86_64，請重新建立環境：

```bash
uv venv --python /opt/homebrew/bin/python3
```

### 問題：說話者分離失敗

1. 確認已設定 HF_TOKEN
2. 確認已接受模型使用條款
3. 嘗試使用 `--no-gpu` 參數

### 問題：處理速度慢

1. 確認使用 GPU 加速（預設啟用）
2. 檢查 CPU 執行緒數設定（預設 8）
3. 關閉其他耗資源的應用程式

## 專案結構

```
asr/
├── asr.sh                          # 便捷執行腳本
├── asr_multi_speaker_v5_fast.py   # 主程式（GPU 加速版）
├── asr_multi_speaker_v4.py        # 舊版（CPU 版本）
├── asr_simple.py                  # 簡化版（只做 ASR）
├── pyproject.toml                 # Python 專案設定
├── .env.example                   # 環境變數範例
├── .gitignore                     # Git 忽略檔案
└── README.md                      # 本檔案
```

## 授權

MIT License

## 與 WhisperX 的比較

本專案與 [WhisperX](https://github.com/m-bain/whisperX) 都使用 pyannote.audio 進行說話人分離，但有以下關鍵差異：

| 特性 | 本專案 | WhisperX |
|------|--------|----------|
| **硬體優化** | Apple Silicon (MPS) | NVIDIA GPU (CUDA) |
| **時間戳精度** | ±0.1-0.5 秒 | ±0.01-0.05 秒（強制對齊） |
| **跨平台** | 僅 macOS (M1/M2/M3) | Linux, Windows, macOS |
| **處理速度** | 快（M1 原生） | 非常快（CUDA） |
| **功能** | ASR + 說話人分離 | ASR + 說話人分離 + 翻譯 + 批次 |
| **安裝** | 簡單 | 中等 |

**選擇本專案，如果你：**
- ✅ 使用 Apple Silicon Mac
- ✅ 想要最簡單的安裝和使用
- ✅ 在 Mac 上需要最快的處理速度

**選擇 WhisperX，如果你：**
- ✅ 使用 NVIDIA GPU
- ✅ 需要毫秒級時間戳精度
- ✅ 需要翻譯和批次處理功能

詳細比較請參考 [COMPARISON.md](COMPARISON.md)

## 致謝

- [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) - Apple Silicon 優化的 Whisper 實作
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) - 說話者分離模型
- [OpenAI Whisper](https://github.com/openai/whisper) - 原始 Whisper 模型

## 貢獻

歡迎提交 Issue 和 Pull Request！

## 更新日誌

### v5 (2025-02-05)
- ✨ 新增 MPS GPU 加速支援
- ⚡ 增加 CPU 執行緒數到 8
- 🚀 效能提升 6 倍

### v4 (2025-02-04)
- ✨ 支援 pyannote.audio 4.x API
- 🐛 修正 PyTorch 2.6+ weights_only 問題
- 🔧 針對 M1 Mac 優化

### v3 (2025-02-04)
- ✨ 使用 subprocess 隔離說話者分離
- 🐛 修正 segmentation fault 問題

### v2 (2025-02-04)
- ✨ 初始版本
- 🎯 支援多說話者分離

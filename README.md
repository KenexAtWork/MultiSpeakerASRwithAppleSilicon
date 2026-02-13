# ASR Multi-Speaker Transcription

使用 MLX Whisper 和 pyannote.audio 進行語音轉錄和說話者分離的工具，針對 Apple Silicon (M1/M2/M3) Mac 優化。

## 🎯 使用方式

### 圖形界面版本（推薦）

```bash
# 啟動 GUI 應用
./run_gui.sh
```

提供友善的圖形界面，支援拖放檔案、即時進度顯示等功能。詳見 [GUI 使用說明](gui/README.md)。

### 命令列版本

```bash
# 基本使用
./asr.sh video.mp4

# 指定模型大小
./asr.sh video.mp4 --model small
```

## 功能特色

- ✅ 使用 MLX Whisper 進行高效能 ASR 轉錄（Apple Silicon 原生加速）
- ✅ 使用 pyannote.audio 進行說話者分離
- ✅ 支援 MPS (Metal Performance Shaders) GPU 加速
- ✅ 多執行緒優化，充分利用 M1/M2/M3 效能核心
- ✅ 自動處理影片音訊提取
- ✅ 支援多種語言（中文、英文、日文等）
- ✅ 圖形界面版本（PyQt6）- 拖放檔案、即時進度、日誌顯示

## 系統需求

- macOS (Apple Silicon: M1/M2/M3)
- Python 3.10+
- ffmpeg
- Hugging Face 帳號（用於說話者分離）

## 安裝

### 方式一：從頭開始安裝

#### 1. 安裝系統依賴

```bash
# 安裝 Homebrew（如果還沒安裝）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安裝 ffmpeg
brew install ffmpeg

# 安裝 uv（Python 套件管理工具）
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

#### 2. Clone 專案並建立環境

```bash
# Clone 專案
git clone https://github.com/KenexAtWork/MultiSpeakerASRwithAppleSilicon.git
cd MultiSpeakerASRwithAppleSilicon

# 使用 uv 建立虛擬環境（使用 ARM64 原生 Python）
uv venv --python /opt/homebrew/bin/python3

# 啟動環境
source .venv/bin/activate

# 安裝 Python 套件
uv pip install mlx-whisper pyannote-audio

# （可選）安裝 GUI 版本所需套件
pip install PyQt6
```

#### 3. 設定 Hugging Face Token

說話者分離功能需要 Hugging Face token：

1. 前往 https://huggingface.co/settings/tokens 建立 token
2. 接受模型使用條款：
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
3. 設定 token（三種方式任選一種）：

**方式 A：使用 .env 檔案（推薦）**
```bash
# 複製範例檔案
cp .env.example .env

# 編輯 .env 並填入你的 token
# HF_TOKEN=your_huggingface_token_here
```

**方式 B：設定環境變數**
```bash
export HF_TOKEN=your_huggingface_token_here
```

**方式 C：執行時指定**
```bash
./asr.sh video.mp4 --hf-token your_huggingface_token_here
```

**詳細申請教學：** [如何申請 Hugging Face Token](https://ithelp.ithome.com.tw/articles/10389679)

### 方式二：快速安裝（已有 uv）

如果你已經安裝了 uv 和 ffmpeg：

```bash
git clone https://github.com/KenexAtWork/MultiSpeakerASRwithAppleSilicon.git
cd MultiSpeakerASRwithAppleSilicon
uv venv --python /opt/homebrew/bin/python3
source .venv/bin/activate
uv pip install mlx-whisper pyannote-audio
export HF_TOKEN=your_huggingface_token_here
```

## 首次使用注意事項

**⚠️ 第一次執行時會自動下載模型，需要較長時間和網路流量：**

1. **MLX Whisper 模型**（約 1.5 GB）
   - 模型：`mlx-community/whisper-medium-mlx`
   - 下載時間：視網速而定，通常需要 5-15 分鐘
   - 儲存位置：`~/.cache/huggingface/`

2. **Pyannote 說話者分離模型**（約 200 MB）
   - 模型：`pyannote/speaker-diarization-3.1` 和 `pyannote/segmentation-3.0`
   - 需要有效的 HF_TOKEN
   - 儲存位置：`~/.cache/torch/`

**總下載量：約 1.7 GB**

**建議：**
- 首次使用時確保網路連線穩定
- 用較短的測試影片（1-2 分鐘）進行首次測試
- 模型下載完成後，後續使用就不需要再下載了

## 使用方式

### 快速開始：使用範例影片

```bash
# 使用提供的範例影片測試
./asr.sh examples/sample-01.mp4

# 查看輸出結果
cat examples/sample-01_transcription.srt

# 或查看範例輸出（已預先處理好）
cat examples/sample-output/sample-01_transcription.srt
```

範例目錄包含：
- `sample-01.mp4` - 約 1 分鐘的多說話者對話影片
- `sample-output/` - 預先處理好的輸出結果和截圖

詳細說明請參考 [examples/README.md](examples/README.md)

### 方法 1：使用便捷腳本（推薦）

```bash
# 基本使用（自動產生輸出檔名，預設 SRT 格式）
./asr.sh video.mp4

# 指定輸出檔名
./asr.sh video.mp4 output.srt

# 輸出為 TXT 格式
./asr.sh video.mp4 output.txt --format txt

# 指定語言
./asr.sh video.mp4 output.srt --language en

# 選擇 Whisper 模型大小（預設：medium）
./asr.sh video.mp4 output.srt --model small   # 記憶體使用 ~3-4 GB
./asr.sh video.mp4 output.srt --model base    # 記憶體使用 ~2-3 GB
./asr.sh video.mp4 output.srt --model large   # 記憶體使用 ~8-10 GB

# 只做 ASR 轉錄（跳過說話者分離）
./asr.sh video.mp4 output.srt --skip-diarization

# 使用 CPU 而非 GPU
./asr.sh video.mp4 output.srt --no-gpu

# 自訂 HF token
./asr.sh video.mp4 output.srt --hf-token YOUR_TOKEN
```

### 方法 2：直接執行 Python 腳本

```bash
source .venv/bin/activate

# 輸出 SRT 格式（預設）
python asr_multi_speaker_v5_fast.py \
  --input video.mp4 \
  --output output.srt \
  --language zh \
  --hf-token YOUR_TOKEN

# 輸出 TXT 格式
python asr_multi_speaker_v5_fast.py \
  --input video.mp4 \
  --output output.txt \
  --format txt \
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

## 模型選擇

MLX Whisper 支援多種模型大小，可根據記憶體和準確度需求選擇：

| 模型 | 記憶體使用 | 準確度 | 速度 | 適用場景 |
|------|-----------|--------|------|---------|
| `tiny` | ~1-2 GB | ⭐⭐ | 最快 | 快速測試、草稿 |
| `base` | ~2-3 GB | ⭐⭐⭐ | 很快 | 簡單對話、記憶體受限 |
| `small` | ~3-4 GB | ⭐⭐⭐⭐ | 快 | 一般會議、推薦選擇 |
| `medium` | ~5-7 GB | ⭐⭐⭐⭐⭐ | 中等 | 預設值、高品質需求 |
| `large` | ~8-10 GB | ⭐⭐⭐⭐⭐ | 較慢 | 最高準確度需求 |

**使用範例：**
```bash
# 使用 small 模型（推薦用於 8GB 記憶體的 Mac）
./asr.sh video.mp4 --model small

# 使用 base 模型（最省記憶體）
./asr.sh video.mp4 --model base

# 使用 large 模型（最高準確度）
./asr.sh video.mp4 --model large
```

**選擇建議：**
- 8GB RAM Mac：推薦 `small` 或 `base`
- 16GB RAM Mac：推薦 `small` 或 `medium`（預設）
- 32GB+ RAM Mac：可使用 `large`
- 中英混合語音：建議至少使用 `small` 以上

## 效能

在 M1 Pro (8 核心 CPU, 14 核心 GPU) 上的測試結果：

| 影片長度 | 處理時間 | 加速比 |
|---------|---------|--------|
| 90 秒   | ~45 秒  | 2x     |
| 3 分鐘  | ~55 秒  | 3.3x   |
| 31 分鐘 | ~10 分鐘 | 3.1x   |

使用 GPU 加速比 CPU 快約 6 倍。

## 輸出格式

### SRT 格式（預設）

標準字幕格式，可直接用於影片播放器：

```
1
00:00:00,000 --> 00:00:02,500
[SPEAKER_00] 請 Peter 這邊來做說明

2
00:00:02,500 --> 00:00:04,200
[SPEAKER_00] 那我先把交給 Peter

3
00:00:06,239 --> 00:00:06,639
[SPEAKER_01] 好

4
00:00:07,359 --> 00:00:09,960
[SPEAKER_01] 各位同事大家好
```

### TXT 格式

純文字格式，適合閱讀和編輯：

```
[SPEAKER_00] 00:00:00,000 --> 00:00:02,500
請 Peter 這邊來做說明

[SPEAKER_00] 00:00:02,500 --> 00:00:04,200
那我先把交給 Peter

[SPEAKER_01] 00:00:06,239 --> 00:00:06,639
好

[SPEAKER_01] 00:00:07,359 --> 00:00:09,960
各位同事大家好
```

使用 `--format txt` 參數可切換為 TXT 格式。

## 疑難排解
[SPEAKER_00] 00:00:00,000 --> 00:00:02,500
請 Peter 這邊來做說明

[SPEAKER_00] 00:00:02,500 --> 00:00:04,200
那我先把交給 Peter

[SPEAKER_01] 00:00:06,239 --> 00:00:06,639
好

[SPEAKER_01] 00:00:07,359 --> 00:00:09,960
各位同事大家好
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
├── pyproject.toml                 # Python 專案設定
├── .env.example                   # 環境變數範例
├── .gitignore                     # Git 忽略檔案
├── README.md                      # 本檔案
├── COMPARISON.md                  # 與 WhisperX 的比較
├── LICENSE                        # MIT 授權
├── examples/                      # 範例檔案
│   ├── sample-01.mp4             # 範例影片
│   └── sample-output/            # 範例輸出結果
│       ├── sample-01_transcription.srt
│       └── *.png                 # 截圖
├── legacy/                        # 舊版本（參考用）
│   ├── asr_multi_speaker_v4.py   # CPU 版本
│   └── asr_simple.py             # 簡化版本
└── scripts/                       # 維護腳本
    └── cleanup_for_git.sh        # Git 清理腳本
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

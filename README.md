# ASR Multi-Speaker Transcription

🎙️ 使用 MLX Whisper 和 pyannote.audio 進行語音轉錄和說話者分離的工具，針對 Apple Silicon Mac 優化。

提供友善的圖形界面，支援拖放檔案、即時進度顯示、字幕編輯、AWS Bedrock 摘要等功能。

## 📸 功能展示

### 主界面 - 檔案選擇與參數設定
![主界面](screenshots/01-main-interface.png)
- 拖放檔案或點擊選擇
- 選擇 Whisper 模型大小
- 設定語言和輸出格式
- 啟用/停用說話者分離

### 轉錄結果 - 即時處理日誌與字幕編輯
![轉錄結果](screenshots/02-transcription-result.png)
- 即時顯示處理進度和日誌
- 自動識別說話者（SPEAKER_00, SPEAKER_01...）
- 內建字幕編輯器，雙擊可編輯
- 音訊播放器，點擊字幕跳轉

### AWS Bedrock 摘要功能
![AWS 摘要](screenshots/03-aws-summary.png)
- 使用 AWS Bedrock Claude 生成會議摘要
- 支援多個 AWS 區域
- 可自訂 Prompt
- 一鍵產生結構化摘要

## ✨ 主要特色

- 🖥️ **友善的圖形界面** - 拖放檔案、即時進度、字幕編輯
- ⚡ **Apple Silicon 優化** - 使用 MLX 和 MPS GPU 加速，處理速度快 6 倍
- 🎯 **說話者分離** - 自動識別不同說話者並標記
- 🌏 **多語言支援** - 支援中文、英文、日文等多種語言
- 📝 **字幕編輯** - 內建字幕編輯器，可即時修改並儲存
- 🎵 **音訊播放** - 同步播放音訊，點擊字幕跳轉
- 💾 **多種格式** - 輸出 SRT 或 TXT 格式
- 🤖 **AI 摘要** - 整合 AWS Bedrock，自動生成會議摘要

## 🚀 快速開始

### 方法一：自動安裝（推薦）

```bash
# 1. Clone 專案
git clone https://github.com/KenexAtWork/MultiSpeakerASRwithAppleSilicon.git
cd MultiSpeakerASRwithAppleSilicon

# 2. 執行安裝腳本
./install.sh

# 3. 編輯 .env 檔案，填入 Hugging Face Token
nano .env  # 或使用其他編輯器

# 4. 啟動 GUI
./run_gui.sh
```

### 方法二：手動安裝

```bash
# 1. 安裝系統依賴（如果還沒安裝）
brew install ffmpeg

# 2. 安裝 uv（Python 套件管理器，比 pip 快 10-100 倍）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Clone 專案
git clone https://github.com/KenexAtWork/MultiSpeakerASRwithAppleSilicon.git
cd MultiSpeakerASRwithAppleSilicon

# 4. 建立虛擬環境並安裝套件
uv venv --python 3.10
source .venv/bin/activate
uv pip install -e ".[all]"  # 安裝所有功能（GUI + AWS）

# 5. 設定環境變數
cp .env.example .env
nano .env  # 填入 HF_TOKEN
```

### 設定 Hugging Face Token

說話者分離功能需要 Hugging Face token：

1. 前往 https://huggingface.co/settings/tokens 建立 token
2. 接受模型使用條款：
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
3. 將 token 填入 `.env` 檔案：`HF_TOKEN=your_token_here`

**詳細申請教學：** [如何申請 Hugging Face Token](https://ithelp.ithome.com.tw/articles/10389679)

### 首次執行注意事項

⚠️ **首次執行會自動下載 AI 模型（約 1.7 GB）**

- Whisper 語音辨識模型：約 1.5 GB
- Speaker Diarization 模型：約 200 MB
- 下載時間：2-8 分鐘（視網路速度）
- 下載期間 GUI 可能看起來無回應，這是正常的
- 模型會自動快取，之後啟動很快（< 5 秒）

## 🎯 使用 GUI

### 基本流程

1. **選擇檔案** - 拖放影片/音訊檔案，或點擊「選擇檔案」按鈕
2. **設定參數** - 選擇 Whisper 模型、語言、輸出格式
3. **開始轉錄** - 點擊「開始轉錄」按鈕
4. **查看結果** - 轉錄完成後，字幕會顯示在下方
5. **編輯字幕** - 雙擊字幕可編輯，修改後點擊「儲存 SRT」
6. **播放音訊** - 點擊字幕可跳轉到對應時間點

### 參數說明

| 參數 | 說明 | 建議值 |
|------|------|--------|
| **Whisper 模型** | 影響準確度和速度 | `medium`（預設）或 `small` |
| **語言** | 音訊主要語言 | `auto`（自動偵測）或 `zh`（中文） |
| **輸出格式** | 字幕檔案格式 | `SRT`（標準字幕格式） |
| **說話者分離** | 是否識別不同說話者 | 勾選（預設） |
| **Region** | AWS 區域（摘要功能用） | `us-west-2` |

### 功能說明

- **拖放檔案** - 支援 mp4, m4a, mov, avi, mkv, wav, mp3 等格式
- **即時進度** - 顯示處理階段和進度百分比
- **日誌顯示** - 即時顯示處理過程和錯誤訊息
- **字幕編輯** - 雙擊字幕可編輯內容，支援多行文字
- **音訊播放** - 同步播放音訊，點擊字幕跳轉到對應時間
- **開啟資料夾** - 快速開啟輸出檔案所在資料夾

詳細使用說明請參考 [GUI 使用說明](gui/README.md)。

## 💻 系統需求

- macOS with Apple Silicon (M-series chips: M1, M2, M3, M4 或更新)
- Python 3.10+
- ffmpeg
- Hugging Face 帳號（用於說話者分離）
- 至少 8GB RAM（建議 16GB）

## 📖 範例與測試

專案包含範例影片和預先處理好的輸出結果：

```bash
# 使用範例影片測試
./run_gui.sh
# 然後拖放 examples/sample-01.mp4 到 GUI

# 或使用命令列測試
./scripts/asr.sh examples/sample-01.mp4

# 查看範例輸出
cat examples/sample-output/sample-01_transcription.srt
```

範例目錄包含：
- `sample-01.mp4` - 約 1 分鐘的多說話者對話影片
- `sample-output/` - 預先處理好的輸出結果和截圖

詳細說明請參考 [examples/README.md](examples/README.md)

## 🎨 模型選擇

MLX Whisper 支援多種模型大小，可根據記憶體和準確度需求選擇：

| 模型 | 記憶體使用 | 準確度 | 速度 | 適用場景 |
|------|-----------|--------|------|---------|
| `tiny` | ~1-2 GB | ⭐⭐ | 最快 | 快速測試、草稿 |
| `base` | ~2-3 GB | ⭐⭐⭐ | 很快 | 簡單對話、記憶體受限 |
| `small` | ~3-4 GB | ⭐⭐⭐⭐ | 快 | 一般會議、推薦選擇 |
| `medium` | ~5-7 GB | ⭐⭐⭐⭐⭐ | 中等 | 預設值、高品質需求 |
| `large` | ~8-10 GB | ⭐⭐⭐⭐⭐ | 較慢 | 最高準確度需求 |

**選擇建議：**
- 8GB RAM Mac：推薦 `small` 或 `base`
- 16GB RAM Mac：推薦 `small` 或 `medium`（預設）
- 32GB+ RAM Mac：可使用 `large`
- 中英混合語音：建議至少使用 `small` 以上

## 🌏 語言支援

支援多種語言，包括：

- `auto`: 自動偵測（推薦用於混合語言）
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

**語言混合支援：**
- 對於中英混雜的音訊，建議選擇 `auto`（自動偵測）
- 如果音訊以某種語言為主，可指定該語言
- Whisper 可以處理語言混合的音訊，但準確度取決於混合比例

## ⚡ 效能表現

在 M1 Pro (8 核心 CPU, 14 核心 GPU, 16GB RAM) 上的測試結果：

| 影片長度 | 處理時間 | 加速比 | 模型 |
|---------|---------|--------|------|
| 90 秒   | ~45 秒  | 2.0x   | medium |
| 3 分鐘  | ~55 秒  | 3.3x   | medium |
| 14 分鐘 | ~4.5 分鐘 | 3.1x | medium |
| 31 分鐘 | ~10 分鐘 | 3.1x   | medium |

**效能優化：**
- 使用 GPU 加速比 CPU 快約 6 倍
- 使用 `small` 模型可進一步提升速度（約 1.5 倍）
- 關閉說話者分離可節省約 30% 時間

## 📝 輸出格式

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
```

## 🔧 進階使用：命令列版本

如果你偏好使用命令列，或需要批次處理，可以使用命令列版本：

### 使用便捷腳本

```bash
# 基本使用（自動產生輸出檔名）
./scripts/asr.sh video.mp4

# 指定輸出檔名和格式
./scripts/asr.sh video.mp4 output.srt
./scripts/asr.sh video.mp4 output.txt --format txt

# 指定語言和模型
./scripts/asr.sh video.mp4 output.srt --language zh --model small

# 跳過說話者分離（更快）
./scripts/asr.sh video.mp4 output.srt --skip-diarization

# 使用 CPU（不使用 GPU）
./scripts/asr.sh video.mp4 output.srt --no-gpu
```

### 直接執行 Python 腳本

```bash
source .venv/bin/activate

python asr_multi_speaker_v5_fast.py \
  --input video.mp4 \
  --output output.srt \
  --language zh \
  --model medium \
  --hf-token YOUR_TOKEN
```

### 批次處理範例

```bash
# 處理資料夾中的所有影片
for video in videos/*.mp4; do
  ./scripts/asr.sh "$video"
done
```

## ❓ 疑難排解

### GUI 相關問題

**問題：GUI 無法啟動**
```bash
# 確認已安裝 PyQt6
source .venv/bin/activate
uv pip install PyQt6

# 檢查 Python 版本（需要 3.10+）
python --version
```

**問題：拖放檔案無反應**
- 確認檔案格式支援（mp4, m4a, mov, avi, mkv, wav, mp3）
- 檢查檔案路徑中是否有特殊字元
- 查看日誌視窗是否有錯誤訊息

**問題：音訊無法播放**
- 確認檔案路徑正確
- 檢查是否有中文或特殊字元（已支援，但可能需要重新選擇檔案）
- 查看日誌視窗的錯誤訊息

**問題：字幕編輯後無法儲存**
- 確認有寫入權限
- 檢查輸出路徑是否存在
- 嘗試手動指定輸出檔名

### 轉錄相關問題

**問題：找不到 ffmpeg**
```bash
brew install ffmpeg
```

**問題：找不到 mlx 模組**

確認使用 ARM64 原生 Python：

```bash
file $(which python)
# 應該顯示：Mach-O 64-bit executable arm64
```

如果是 x86_64，請重新建立環境：

```bash
uv venv --python 3.10
source .venv/bin/activate
uv pip install -e .
```

**問題：說話者分離失敗**

1. 確認已設定 HF_TOKEN（在 .env 檔案或 GUI 中）
2. 確認已接受模型使用條款：
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
3. 嘗試取消勾選「說話者分離」選項
4. 檢查網路連線（首次使用需下載模型）

**問題：處理速度慢**

1. 確認使用 GPU 加速（預設啟用）
2. 嘗試使用較小的模型（`small` 或 `base`）
3. 取消勾選「說話者分離」可節省約 30% 時間
4. 關閉其他耗資源的應用程式

**問題：記憶體不足**

1. 使用較小的模型：`small` (3-4 GB) 或 `base` (2-3 GB)
2. 取消勾選「說話者分離」
3. 關閉其他應用程式釋放記憶體
4. 考慮升級 RAM（建議 16GB）

**問題：轉錄結果不準確**

1. 嘗試使用較大的模型（`medium` 或 `large`）
2. 確認語言設定正確（或使用 `auto`）
3. 檢查音訊品質（背景噪音、音量）
4. 對於中英混合，使用 `auto` 語言設定

**問題：首次執行很慢**

第一次執行會下載模型（約 1.7 GB），需要 5-15 分鐘。模型下載完成後，後續使用就會很快。

### 測試相關問題

**問題：測試失敗**

```bash
# 執行測試診斷
cd asr
./run_tests.sh --fast --verbose

# 檢查環境
source .venv/bin/activate
python -c "import mlx_whisper; print('MLX OK')"
python -c "import PyQt6; print('PyQt6 OK')"
```

## 🧪 測試與開發

### 執行測試

```bash
# 快速測試（約 20 秒）
./run_tests.sh --fast

# 完整測試（約 60 秒）
./run_tests.sh

# 只執行特定測試
./run_tests.sh --test pipeline
./run_tests.sh --test merge

# 查看測試覆蓋率
cat tests/TEST_COVERAGE.md
```

詳細測試說明請參考 [tests/README.md](tests/README.md)

### CI/CD

專案使用 GitHub Actions 進行自動化測試：
- 每次 push 到 main/develop 分支時自動執行
- 測試時間約 16 秒
- 查看測試結果：https://github.com/KenexAtWork/MultiSpeakerASRwithAppleSilicon/actions

## 📁 專案結構

```
asr/
├── gui/                           # GUI 應用程式
│   ├── main.py                   # GUI 主程式
│   ├── ui/                       # UI 元件
│   │   └── main_window.py       # 主視窗
│   └── core/                     # 核心邏輯
│       ├── asr_worker.py        # ASR 處理執行緒
│       └── summary_worker.py    # 摘要生成執行緒
├── tests/                        # 自動化測試
│   ├── test_pipeline_e2e.py    # Pipeline 端到端測試
│   ├── test_merge_srt.py       # 合併邏輯測試
│   ├── test_gui_display.py     # GUI 顯示測試
│   ├── test_gui_processing.py  # GUI 處理測試
│   ├── test_gui_media_url.py   # GUI 媒體播放器測試
│   ├── test_srt_parser.py      # SRT 解析測試
│   ├── test_error_handling.py  # 錯誤處理測試
│   └── TEST_COVERAGE.md        # 測試覆蓋率文件
├── scripts/                      # 腳本工具
│   ├── asr.sh                   # 命令列便捷腳本
│   ├── asr_chunked.sh           # 分段處理腳本
│   ├── benchmark.sh             # 效能測試腳本
│   ├── ci_test.sh               # CI/CD 測試腳本
│   └── cleanup_for_git.sh       # Git 清理腳本
├── examples/                     # 範例檔案
│   ├── sample-01.mp4            # 範例影片
│   └── sample-output/           # 範例輸出結果
├── screenshots/                  # GUI 截圖
│   ├── 01-main-interface.png
│   ├── 02-transcription-result.png
│   └── 03-aws-summary.png
├── benchmark_results/            # 效能測試結果
├── asr_multi_speaker_v5_fast.py # 主程式（命令列版本）
├── merge_srt.py                 # SRT 合併模組
├── install.sh                   # 自動安裝腳本
├── run_gui.sh                   # GUI 啟動腳本
├── run_tests.sh                 # 測試執行腳本
├── pyproject.toml               # Python 專案設定
├── .env.example                 # 環境變數範例
├── .gitignore                   # Git 忽略檔案
└── README.md                    # 本檔案
```
├── COMPARISON.md                # 與 WhisperX 的比較
└── LICENSE                      # MIT 授權
```

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

### 開發流程

1. Fork 專案
2. 建立功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交變更 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 開啟 Pull Request

### 測試要求

提交 PR 前請確保：
- 所有測試通過 (`./run_tests.sh`)
- 新功能有對應的測試
- 程式碼符合專案風格

## 📊 與 WhisperX 的比較

本專案與 [WhisperX](https://github.com/m-bain/whisperX) 都使用 pyannote.audio 進行說話人分離，但有以下關鍵差異：

| 特性 | 本專案 | WhisperX |
|------|--------|----------|
| **硬體優化** | Apple Silicon (MPS) | NVIDIA GPU (CUDA) |
| **使用介面** | GUI + 命令列 | 命令列 |
| **時間戳精度** | ±0.1-0.5 秒 | ±0.01-0.05 秒（強制對齊） |
| **跨平台** | 僅 macOS (Apple Silicon) | Linux, Windows, macOS |
| **處理速度** | 快（M1 原生） | 非常快（CUDA） |
| **功能** | ASR + 說話人分離 + 字幕編輯 | ASR + 說話人分離 + 翻譯 + 批次 |
| **安裝** | 簡單 | 中等 |

**選擇本專案，如果你：**
- ✅ 使用 Apple Silicon Mac
- ✅ 想要友善的圖形界面
- ✅ 需要字幕編輯功能
- ✅ 在 Mac 上需要最快的處理速度

**選擇 WhisperX，如果你：**
- ✅ 使用 NVIDIA GPU
- ✅ 需要毫秒級時間戳精度
- ✅ 需要翻譯和批次處理功能

詳細比較請參考 [COMPARISON.md](COMPARISON.md)

## 📄 授權

MIT License - 詳見 [LICENSE](LICENSE) 檔案

## 🙏 致謝

- [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) - Apple Silicon 優化的 Whisper 實作
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) - 說話者分離模型
- [OpenAI Whisper](https://github.com/openai/whisper) - 原始 Whisper 模型
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI 框架

## 📝 更新日誌

### v5.1 (2026-02-23)
- ✨ 新增 PyQt6 圖形界面
- ✨ 支援字幕編輯和音訊播放
- ✨ 新增段落合併功能（相同說話者）
- ✨ 完整的自動化測試套件（54% 覆蓋率）
- ✨ GitHub Actions CI/CD 整合
- 🐛 修正中文檔名音訊播放問題
- 🐛 修正 language=auto 崩潰問題

### v5.0 (2025-02-05)
- ✨ 新增 MPS GPU 加速支援
- ⚡ 增加 CPU 執行緒數到 8
- 🚀 效能提升 6 倍

### v4.0 (2025-02-04)
- ✨ 支援 pyannote.audio 4.x API
- 🐛 修正 PyTorch 2.6+ weights_only 問題
- 🔧 針對 M1 Mac 優化

### v3.0 (2025-02-04)
- ✨ 使用 subprocess 隔離說話者分離
- 🐛 修正 segmentation fault 問題

### v2.0 (2025-02-04)
- ✨ 初始版本
- 🎯 支援多說話者分離

---

**專案維護者：** [@KenexAtWork](https://github.com/KenexAtWork)

**問題回報：** https://github.com/KenexAtWork/MultiSpeakerASRwithAppleSilicon/issues

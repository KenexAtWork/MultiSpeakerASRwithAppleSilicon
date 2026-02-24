# 分發指南

本文件說明如何打包和分發此專案給其他使用者。

## 打包方式

### 方法 1：使用打包腳本（推薦）

```bash
./scripts/package_for_distribution.sh
```

這會在上層目錄產生 `MultiSpeakerASR-YYYYMMDD.tar.gz` 檔案。

### 方法 2：手動打包

```bash
# 使用 git archive（最乾淨）
git archive --format=tar.gz --prefix=MultiSpeakerASR/ -o MultiSpeakerASR.tar.gz HEAD

# 或手動排除不需要的檔案
tar -czf MultiSpeakerASR.tar.gz \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='.env' \
  MultiSpeakerASRwithAppleSilicon/
```

## 接收者使用步驟

### 1. 解壓縮

```bash
tar -xzf MultiSpeakerASR-YYYYMMDD.tar.gz
cd MultiSpeakerASR-YYYYMMDD
```

### 2. 執行安裝

```bash
./install.sh
```

安裝腳本會自動：
- 檢查 Python 版本
- 安裝 uv（如果需要）
- 建立虛擬環境
- 安裝所有依賴
- 建立 .env 檔案

### 3. 設定環境變數

編輯 `.env` 檔案：

```bash
nano .env
```

填入必要資訊：
- `HF_TOKEN` - Hugging Face token（用於說話者分離）
- `AWS_REGION` - AWS 區域（用於摘要功能，可選）
- `AWS_PROFILE` - AWS profile（預設為 default）

### 4. 啟動 GUI

```bash
./run_gui.sh
```

## 打包內容

打包檔案包含：
- ✅ 所有原始碼
- ✅ 安裝腳本
- ✅ 文件和範例
- ✅ 測試檔案
- ❌ 不包含虛擬環境（.venv）
- ❌ 不包含快取檔案（__pycache__）
- ❌ 不包含環境變數（.env）
- ❌ 不包含 Git 歷史（.git）

## 系統需求

接收者需要：
- macOS with Apple Silicon (M1/M2/M3/M4 或更新)
- Python 3.10+（如果沒有，uv 會自動下載）
- 網路連線（用於下載依賴和 AI 模型）
- 至少 8GB RAM（建議 16GB）

## 首次執行

首次執行會自動下載 AI 模型：
- Whisper 模型：約 1.5 GB
- Speaker Diarization 模型：約 200 MB（如果使用）

下載時間視網路速度而定（約 2-8 分鐘）。

## 離線使用

如果需要完全離線使用：

1. 在有網路的機器上完整安裝並執行一次
2. 打包時包含快取目錄：
   ```bash
   tar -czf MultiSpeakerASR-with-models.tar.gz \
     MultiSpeakerASR/ \
     ~/.cache/huggingface/hub/models--mlx-community--whisper-medium-mlx \
     ~/.cache/huggingface/hub/models--pyannote--speaker-diarization-3.1
   ```
3. 在目標機器上解壓並恢復快取

## 疑難排解

### 權限問題

如果腳本無法執行：

```bash
chmod +x install.sh run_gui.sh run_tests.sh
chmod +x scripts/*.sh
```

### Python 版本問題

如果系統 Python 版本太舊，`install.sh` 會自動使用 uv 下載 Python 3.10。

### 依賴安裝失敗

確保有穩定的網路連線，然後重新執行：

```bash
./install.sh
```

## 更新

如果需要更新到新版本：

1. 從 GitHub 下載最新版本
2. 或使用新的打包檔案
3. 重新執行 `./install.sh`

## 支援

- GitHub: https://github.com/KenexAtWork/MultiSpeakerASRwithAppleSilicon
- Issues: https://github.com/KenexAtWork/MultiSpeakerASRwithAppleSilicon/issues

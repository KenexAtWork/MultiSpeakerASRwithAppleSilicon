# Git 設定指南

## 準備步驟

### 1. 清理不需要的檔案

```bash
cd ~/Utils/asr

# 刪除測試檔案和輸出
rm -f *.mp4 *.wav *.log test_*.txt
rm -f all_*_transcription*.txt
rm -f *_transcription*.txt

# 刪除舊版腳本
rm -f run.sh run_asr.sh run_with_env.sh run_arm64.sh
rm -f setup.sh setup_native_env.sh
rm -f quick_test.py test_diarization_api.py
rm -f asr_multi_speaker2.py asr_multi_speaker_v3.py

# 保留的檔案：
# - asr.sh (主要執行腳本)
# - asr_multi_speaker_v5_fast.py (最新版本)
# - asr_multi_speaker_v4.py (CPU 版本，作為參考)
# - asr_simple.py (簡化版，作為參考)
# - pyproject.toml
# - README.md
# - LICENSE
# - .gitignore
# - .env.example
```

### 2. 初始化 Git 倉庫

```bash
cd ~/Utils/asr

# 初始化 git
git init

# 添加檔案
git add .

# 第一次提交
git commit -m "Initial commit: ASR multi-speaker transcription tool

Features:
- MLX Whisper for ASR transcription
- pyannote.audio for speaker diarization
- MPS GPU acceleration for Apple Silicon
- Multi-threading optimization
- Support for multiple languages
"
```

### 3. 建立 GitHub 倉庫

1. 前往 https://github.com/new
2. 建立新倉庫（例如：`asr-multi-speaker`）
3. **不要**勾選 "Initialize this repository with a README"

### 4. 推送到 GitHub

```bash
# 設定遠端倉庫（替換成你的 GitHub 使用者名稱）
git remote add origin https://github.com/YOUR_USERNAME/asr-multi-speaker.git

# 推送
git branch -M main
git push -u origin main
```

## 後續更新

```bash
# 查看狀態
git status

# 添加變更
git add .

# 提交
git commit -m "描述你的變更"

# 推送
git push
```

## 注意事項

✅ `.gitignore` 已設定，以下檔案不會被提交：
- `.venv/` - 虛擬環境
- `*.mp4`, `*.wav` - 影片和音訊檔案
- `*_transcription*.txt` - 輸出檔案
- `*.log` - 日誌檔案
- `.env` - 環境變數（包含 token）

✅ 敏感資訊已移除：
- HF token 已從 `asr.sh` 移除
- 使用環境變數 `$HF_TOKEN` 替代
- 提供 `.env.example` 作為範例

## 檢查清單

在推送前，請確認：

- [ ] 已刪除所有測試檔案和輸出
- [ ] 已刪除所有 `.mp4`, `.wav` 檔案
- [ ] 已刪除舊版腳本
- [ ] `.gitignore` 已正確設定
- [ ] 沒有包含 HF token 或其他敏感資訊
- [ ] README.md 內容完整
- [ ] LICENSE 檔案存在

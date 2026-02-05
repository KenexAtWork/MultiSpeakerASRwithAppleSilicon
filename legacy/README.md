# Legacy Versions

這個目錄包含舊版本的腳本，保留作為參考用途。

## 檔案說明

- **asr_multi_speaker_v4.py** - CPU 版本（較慢）
  - 使用單執行緒
  - 不支援 GPU 加速
  - 處理速度約為 v5 的 1/6
  - 保留作為 CPU-only 環境的備用方案

- **asr_simple.py** - 簡化版本（僅 ASR，無說話者分離）
  - 用於測試和除錯
  - 不包含說話者分離功能

## 建議

**請使用主目錄的 `asr_multi_speaker_v5_fast.py`**，它提供：
- MPS GPU 加速
- 多執行緒支援
- 更快的處理速度
- 進度顯示
- SRT 格式輸出

如果你的環境不支援 GPU，可以使用 v5 的 `--no-gpu` 參數，它會自動切換到 CPU 模式。

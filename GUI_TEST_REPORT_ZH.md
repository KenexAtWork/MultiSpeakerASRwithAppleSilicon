# GUI 測試報告

## 測試環境
- Python: 3.10
- PyQt6: 6.10.2
- 測試日期: 2026-02-13
- 測試檔案: examples/sample-01.mp4 (59 秒影片)

## 測試項目

### ✅ 1. 套件安裝測試
- PyQt6 安裝成功
- mlx-whisper 已安裝
- pyannote-audio 已安裝
- 所有依賴套件正常

### ✅ 2. GUI 組件導入測試
- MainWindow 導入成功
- ASRWorker 導入成功
- 無語法錯誤

### ✅ 3. GUI 界面顯示測試
- 視窗正常顯示
- 視窗大小: 800x700
- 視窗標題正確
- 無渲染錯誤

### ✅ 4. ASR Worker 處理測試
- 成功載入 Whisper 模型 (medium)
- ASR 轉錄完成 (16 秒, 3.63x 即時速度)
- 說話者分離完成 (23 秒, 2.52x 即時速度)
- 總處理時間: 40 秒 (1.49x 即時速度)
- 輸出檔案生成成功
- 檔案大小: 2837 bytes
- 字幕段落: 39 個
- 偵測說話者: 2 位 (SPEAKER_00, SPEAKER_01)

### ✅ 5. 輸出格式驗證
- SRT 格式正確
- 時間碼格式正確
- 說話者標記正確
- 中文字幕正常顯示

## 測試結果

### 所有測試通過 ✅

GUI 應用程式可以正常運行，包括：
1. 界面顯示正常
2. 背景處理正常
3. ASR 轉錄功能正常
4. 說話者分離功能正常
5. 檔案輸出正常

## 已知問題

無

## 建議

1. 可以開始使用 GUI 進行實際測試
2. 建議使用 `./run_gui.sh` 啟動
3. 確保 `.env` 檔案中已設定 `HF_TOKEN`

## 啟動方式

```bash
cd ~/Utils/asr
./run_gui.sh
```

## 功能特色

- ✅ 拖放檔案支援
- ✅ 即時處理進度顯示
- ✅ 處理日誌即時更新
- ✅ 支援多種語言和模型選擇
- ✅ 可選擇輸出格式（SRT/TXT）
- ✅ 背景處理，UI 不凍結
- ✅ 支援 Apple Silicon GPU 加速

## 測試命令

如需重新測試：

```bash
# 測試 GUI 顯示
.venv/bin/python test_gui_display.py

# 測試 ASR 處理
.venv/bin/python test_gui_processing.py
```

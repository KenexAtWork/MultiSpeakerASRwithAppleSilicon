# 測試覆蓋範圍文件

本文件記錄 ASR Multi-Speaker 專案的自動化測試覆蓋範圍。

## 測試檔案總覽

| 測試檔案 | 測試類型 | 測試數量 | 狀態 |
|---------|---------|---------|------|
| `test_pipeline_e2e.py` | 端到端 | 11 | ✅ 已完成 |
| `test_merge_srt.py` | 單元 + 整合 | 12 + 整合 | ✅ 已完成 |
| `test_gui_media_url.py` | 單元 | 6 | ✅ 已完成 |

## 核心模組測試覆蓋

### 1. ASR Pipeline (`asr_multi_speaker_v5_fast.py`)

**已覆蓋功能：**
- ✅ 完整 ASR 轉錄流程（Whisper base/medium/large）
- ✅ 語言自動偵測（`language=auto`）
- ✅ 說話者分離（diarization）
- ✅ 跳過說話者分離模式
- ✅ SRT 輸出格式
- ✅ TXT 輸出格式
- ✅ 時間戳格式正確性
- ✅ 段落編號連續性
- ✅ 說話者標記（SPEAKER_00, SPEAKER_01, Unknown）
- ✅ 合併步驟整合（Step 3）
- ✅ 處理速度統計

**未覆蓋功能：**
- ⚠️ GPU vs CPU 模式差異驗證
- ⚠️ 記憶體使用量監控
- ⚠️ 不同音檔格式（m4a, mov, avi, mkv）
- ⚠️ 錯誤處理（檔案不存在、格式不支援、記憶體不足）
- ⚠️ 長時間音檔（>30分鐘）穩定性

**測試檔案：** `test_pipeline_e2e.py`

---

### 2. 合併模組 (`merge_srt.py`)

**已覆蓋功能：**
- ✅ 空輸入處理
- ✅ 單一段落處理
- ✅ 同 speaker 相鄰段落合併
- ✅ 不同 speaker 不合併
- ✅ Unknown speaker 不合併
- ✅ 間隔超過 `max_gap` 不合併
- ✅ 合併後超過 `max_duration` 限制
- ✅ 合併後超過 `max_chars` 限制
- ✅ 合併後 index 連續編號
- ✅ 時間戳有效性（start ≤ end，遞增）
- ✅ 文字不丟失驗證
- ✅ 整合測試（實際 SRT 檔案）

**未覆蓋功能：**
- ⚠️ 邊界條件（極短/極長段落）
- ⚠️ 特殊字元處理（emoji, 多語言混合）
- ⚠️ 效能測試（大量段落 >1000）

**測試檔案：** `test_merge_srt.py`

---

### 3. GUI 媒體播放器 (`gui/ui/main_window.py` - 播放器部分)

**已覆蓋功能：**
- ✅ 中文路徑 QUrl 轉換
- ✅ 空格路徑 QUrl 轉換
- ✅ 中英混合路徑處理
- ✅ 實際暫存檔案 round-trip
- ✅ QMediaPlayer 接受中文 URL
- ✅ 實際音檔載入（sample-01.mp4）

**未覆蓋功能：**
- ⚠️ 播放/暫停/停止按鈕互動
- ⚠️ 進度條拖動
- ⚠️ 字幕同步高亮
- ⚠️ 雙擊字幕跳轉播放
- ⚠️ 音量控制
- ⚠️ 播放錯誤處理

**測試檔案：** `test_gui_media_url.py`

---

## 未測試模組

### 4. GUI 主視窗 (`gui/ui/main_window.py`)

**未覆蓋功能：**
- ⚠️ 檔案拖放功能
- ⚠️ 檔案選擇對話框
- ⚠️ 設定儲存/載入（.env）
- ⚠️ HF Token 顯示/隱藏/儲存
- ⚠️ 開始轉錄按鈕
- ⚠️ 進度條更新
- ⚠️ 日誌顯示
- ⚠️ 字幕編輯功能（雙擊編輯、儲存）
- ⚠️ SRT 解析邏輯（`_parse_srt`）
- ⚠️ 開啟輸出資料夾

**建議測試方式：**
- 視覺自動化測試（已有工具：`tests/visual/snap.py`）
- 單元測試（模擬 Qt 事件）

---

### 5. GUI ASR Worker (`gui/core/asr_worker.py`)

**未覆蓋功能：**
- ⚠️ subprocess 執行流程
- ⚠️ 進度信號發送
- ⚠️ 階段變更信號
- ⚠️ 日誌訊息處理（新增行 vs 覆蓋行）
- ⚠️ 錯誤處理和信號
- ⚠️ 環境變數傳遞
- ⚠️ UTF-8 多字節處理

**建議測試方式：**
- 整合測試（模擬 subprocess 輸出）
- Mock QThread 信號

---

### 6. GUI 摘要 Worker (`gui/core/summary_worker.py`)

**未覆蓋功能：**
- ⚠️ AWS Bedrock 連線
- ⚠️ Converse API 呼叫
- ⚠️ Claude 模型回應解析
- ⚠️ Nova 模型回應解析
- ⚠️ 錯誤處理（網路錯誤、API 錯誤、權限錯誤）
- ⚠️ Prompt 模板替換
- ⚠️ 進度信號發送

**建議測試方式：**
- Mock boto3 client
- 整合測試（需 AWS 憑證）

---

### 7. 視覺測試工具 (`tests/visual/`)

**已實作但未整合：**
- ✅ macOS screencapture (`snap.py`)
- ✅ Bedrock 多模態分析 (`describe_screenshot.py`)
- ✅ 座標網格覆蓋 (`overlay_grid.py`)

**未覆蓋功能：**
- ⚠️ 完整 GUI 自動化測試流程（步驟 5-10 被座標精度問題阻擋）

---

## 測試執行指南

### 快速測試（跳過 diarization，~16秒）
```bash
cd asr
.venv/bin/python tests/test_pipeline_e2e.py --fast
```

### 完整測試（含 diarization，~50秒）
```bash
cd asr
.venv/bin/python tests/test_pipeline_e2e.py
```

### 合併功能測試
```bash
cd asr
# 單元測試
.venv/bin/python tests/test_merge_srt.py

# 整合測試（指定實際 SRT）
.venv/bin/python tests/test_merge_srt.py --srt benchmark_results/EVCNokia報價討論-20260211_whisper_medium_merged.srt
```

### GUI 媒體測試
```bash
cd asr
.venv/bin/python tests/test_gui_media_url.py
```

---

## 測試覆蓋率統計

| 模組類型 | 已測試 | 未測試 | 覆蓋率 |
|---------|-------|-------|-------|
| 核心 Pipeline | 10 項 | 5 項 | 67% |
| 合併邏輯 | 12 項 | 3 項 | 80% |
| GUI 播放器 | 6 項 | 6 項 | 50% |
| GUI 主視窗 | 0 項 | 10 項 | 0% |
| GUI Workers | 0 項 | 15 項 | 0% |
| **總計** | **28 項** | **39 項** | **42%** |

---

## 優先改善建議

### 高優先級（影響核心功能）
1. **GUI ASR Worker 測試** - 確保 subprocess 執行穩定
2. **SRT 解析邏輯測試** - 避免字幕顯示錯誤
3. **錯誤處理測試** - 提升使用者體驗

### 中優先級（提升可靠性）
4. **GUI 字幕編輯測試** - 驗證編輯/儲存功能
5. **Bedrock 摘要測試** - Mock API 呼叫
6. **設定儲存/載入測試** - 確保設定持久化

### 低優先級（錦上添花）
7. **視覺自動化測試** - 完整 GUI 流程驗證
8. **效能測試** - 長音檔、大量段落
9. **邊界條件測試** - 極端輸入情況

---

## 測試環境需求

- Python 3.10+
- PyQt6（GUI 測試）
- HF_TOKEN（diarization 測試）
- AWS 憑證（Bedrock 測試）
- macOS（視覺測試工具）
- 測試音檔：`examples/sample-01.mp4`（60秒，2 speakers）

---

## 更新記錄

- 2026-02-23: 初始版本，記錄現有測試覆蓋範圍

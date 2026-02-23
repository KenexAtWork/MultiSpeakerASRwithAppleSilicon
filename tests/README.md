# ASR 自動化測試

本目錄包含 ASR Multi-Speaker 專案的自動化測試。

## 測試覆蓋範圍

詳細的測試覆蓋範圍文件請參考：[TEST_COVERAGE.md](./TEST_COVERAGE.md)

## 快速開始

### 執行所有測試

```bash
cd asr

# 快速測試（跳過 diarization，約 20 秒）
.venv/bin/python tests/test_pipeline_e2e.py --fast
.venv/bin/python tests/test_merge_srt.py
.venv/bin/python tests/test_gui_media_url.py
.venv/bin/python tests/test_srt_parser.py
.venv/bin/python tests/test_error_handling.py

# 完整測試（含 diarization，約 60 秒）
.venv/bin/python tests/test_pipeline_e2e.py
```

### 個別測試說明

#### 1. Pipeline 端到端測試 (`test_pipeline_e2e.py`)

測試完整 ASR 轉錄流程，包含 Whisper ASR、說話者分離、段落合併。

```bash
# 快速模式（Whisper base，跳過 diarization）
.venv/bin/python tests/test_pipeline_e2e.py --fast

# 完整模式（Whisper base + diarization）
.venv/bin/python tests/test_pipeline_e2e.py

# 指定模型
.venv/bin/python tests/test_pipeline_e2e.py --model medium
```

**測試項目：**
- SRT 輸出檔案存在且非空
- SRT 格式正確（index、時間戳、文字）
- 時間戳遞增
- index 連續編號
- skip diarization 時全部標為 Unknown
- language=auto 不報錯
- TXT 格式輸出
- 合併步驟有效
- diarization 偵測到 ≥2 位說話者
- 合併步驟減少段落數
- Unknown 段落未被合併

#### 2. 合併功能測試 (`test_merge_srt.py`)

測試同 speaker 相鄰段落合併邏輯。

```bash
# 單元測試
.venv/bin/python tests/test_merge_srt.py

# 整合測試（指定實際 SRT 檔案）
.venv/bin/python tests/test_merge_srt.py --srt path/to/file.srt
```

**測試項目：**
- 空輸入處理
- 單一段落處理
- 同 speaker 合併
- 不同 speaker 不合併
- Unknown speaker 不合併
- 間隔限制（max_gap）
- 時長限制（max_duration）
- 字數限制（max_chars）
- index 連續編號
- 時間戳有效性
- 文字不丟失
- skip diarization 場景

#### 3. GUI 媒體播放器測試 (`test_gui_media_url.py`)

測試 QMediaPlayer 對中文/特殊字元檔名的支援。

```bash
.venv/bin/python tests/test_gui_media_url.py
```

**測試項目：**
- 中文路徑 QUrl 轉換
- 空格路徑 QUrl 轉換
- 中英混合路徑處理
- 實際暫存檔案 round-trip
- QMediaPlayer 接受中文 URL
- 實際音檔載入

#### 4. SRT 解析測試 (`test_srt_parser.py`)

測試 GUI 中的 SRT 解析邏輯。

```bash
.venv/bin/python tests/test_srt_parser.py
```

**測試項目：**
- 基本 SRT 格式解析
- 多行文字處理
- 時間戳轉換正確性
- 中文字元處理
- 空檔案處理
- 格式錯誤的時間戳
- 缺少文字內容
- 額外空行處理
- time_str 欄位保留
- 實際 SRT 檔案測試
- 特殊字元處理
- 零時長段落

#### 5. 錯誤處理測試 (`test_error_handling.py`)

測試 ASR Pipeline 在各種錯誤情況下的行為。

```bash
.venv/bin/python tests/test_error_handling.py
```

**測試項目：**
- 檔案不存在時應報錯
- 無效的模型名稱
- 無效的語言代碼
- 沒有 HF token 但要求 diarization
- 無效的輸出格式
- 輸出到唯讀目錄
- 損壞的影片檔案
- 空的影片檔案

## 測試環境需求

### 必要套件
```bash
# 已在 .venv 中安裝
pip install PyQt6 mlx-whisper pyannote.audio boto3
```

### 環境變數
```bash
# .env 檔案
HF_TOKEN=your_huggingface_token  # diarization 測試需要
```

### 測試資料
- `examples/sample-01.mp4` - 60秒測試音檔（2 speakers）
- 其他實際音檔可用於整合測試

## 測試結果範例

### 成功輸出
```
============================================================
ASR Pipeline 端到端測試 (model=base)
音檔: /path/to/asr/examples/sample-01.mp4
模式: 快速（無 diarization）
============================================================
  ✓ SRT 輸出檔案存在且非空
  ✓ SRT 格式正確（index、時間戳、文字）
  ✓ 時間戳遞增
  ✓ index 連續編號
  ✓ skip diarization 時全部標為 Unknown
  ✓ language=auto 不報錯
  ✓ TXT 格式輸出
  ✓ 合併步驟有生效（段落數合理）
  [basic] 16.2s

結果: 8 通過, 0 失敗
✓ 全部通過
```

## 持續整合

測試可整合到 CI/CD pipeline：

```bash
#!/bin/bash
# ci_test.sh

set -e

cd asr

# 快速測試（適合 PR 檢查）
.venv/bin/python tests/test_pipeline_e2e.py --fast
.venv/bin/python tests/test_merge_srt.py
.venv/bin/python tests/test_gui_media_url.py

echo "✓ 所有測試通過"
```

## 新增測試

### 測試檔案命名規範
- `test_*.py` - 測試檔案
- 放在 `tests/` 目錄下
- 使用 `assert` 進行驗證

### 測試函式命名規範
```python
def test_feature_description():
    """測試項目說明（會顯示在測試報告中）"""
    # 測試邏輯
    assert condition, "錯誤訊息"
```

### 更新測試覆蓋文件
新增測試後請更新 [TEST_COVERAGE.md](./TEST_COVERAGE.md)。

## 已知限制

1. **視覺測試未完成** - GUI 自動化測試工具已建立但未整合（座標精度問題）
2. **GUI Worker 未測試** - `asr_worker.py` 和 `summary_worker.py` 需要 Mock 測試
3. **錯誤處理未覆蓋** - 異常情況測試不足
4. **效能測試缺失** - 長音檔、大量段落的穩定性未驗證

詳見 [TEST_COVERAGE.md](./TEST_COVERAGE.md) 的「優先改善建議」章節。

## 問題回報

測試失敗時請提供：
1. 完整錯誤訊息
2. 測試命令
3. 環境資訊（Python 版本、OS、記憶體）
4. 測試音檔資訊（如適用）

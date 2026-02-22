# Visual UI Testing - 進度總結

## 目標
使用純視覺方案（screencapture + grid overlay + multimodal LLM）對 PyQt6 GUI 進行全自動黑盒 UI 測試。

## 已完成

### 工具建置
- `snap.py` — 整合截圖工具（全螢幕截圖 + grid overlay + Bedrock 分析 + JSON log）
- `overlay_grid.py` — 座標網格疊加（Retina 2x，50px/100px 間距）
- `describe_screenshot.py` — Bedrock multimodal 圖片分析
- `benchmark_vision.py` — 多模型比較工具
- `find_dropdown.py` — Accessibility API 元件定位（Swift）

### 模型評測
- Claude Sonnet 4.6：最佳，座標準確度最高，4.8s 延遲
- Claude Opus 4.6：接近，座標偏差 ~4px，4.9s 延遲
- Nova Pro v1：不適合，座標系統性偏差，文字幻覺嚴重

### ASR 流程（已完成）
1. ✅ 啟動 GUI，視窗定位 x=52, y=33, 800x728
2. ✅ 選擇 sample-01.mp4，GPU 加速 ON，medium model，speaker diarization ON
3. ✅ ASR 轉錄完成（100%）
4. ✅ 關閉完成對話框，確認字幕列表顯示

### 會議摘要流程（未完成）
5. ❌ 選擇 Region: us-west-2 — 卡在 dropdown 點擊
6. ⬜ 選擇 Model: Nova Pro
7. ⬜ 點擊「產生摘要」
8. ⬜ 滾動到底部，點擊「儲存摘要」
9. ⬜ 打印存檔第 5-10 行

## 核心問題：LLM 讀 grid 座標不準

### 現象
- Sonnet 4.6 報告 Region dropdown 三角形在 (578, 371) 或 (590, 369)
- 實際位置（Accessibility API 驗證）：(478, 395) size:(170x24)，三角形約在 (636, 407)
- 偏差達 50-100+ px，導致 cliclick 點擊無效

### 根因分析
- LLM 讀 grid 線上的數字時存在系統性偏差
- 沒有提供足夠的錨點資訊讓 LLM 交叉驗證

### 改進方向
- 將視窗精確邊界座標 (52,33)-(852,761) 作為錨點寫入 prompt
- 讓 LLM 用 grid 線 + 視窗邊界交叉驗證，提高定位精度
- 考慮更密的 grid（25px 間距）或在關鍵區域裁切放大

## 環境資訊
- macOS, M1 Pro, 16GB RAM
- 螢幕 3024x1964 Retina (邏輯 1512x982)
- Python 3.10, PyQt6, venv at `asr/.venv`
- Vision model: Claude Sonnet 4.6 (`us.anthropic.claude-sonnet-4-6`) via us-west-2
- 截圖工具: screencapture -x -C（含游標）
- 點擊工具: cliclick（邏輯座標）

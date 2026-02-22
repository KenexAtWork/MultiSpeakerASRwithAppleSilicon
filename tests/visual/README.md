# Visual UI Testing Tool

透過 macOS `screencapture` + AWS Bedrock Claude 進行 GUI 視覺驗證。

## 原理

1. 使用 macOS 原生 `screencapture` 指令截取視窗或螢幕
2. 將截圖透過 AWS Bedrock Converse API 送給 Claude（multimodal）
3. Claude 回傳 UI 的文字描述，可用於驗證佈局、按鈕數量、元素排列等

## 環境需求

- macOS（需在 System Settings → Privacy & Security → Screen & System Audio Recording 授權給 terminal app）
- AWS credentials（需有 Bedrock 存取權限）
- Python 3.10+ with `boto3`

## 使用方式

```bash
# 列出螢幕上所有視窗
python tests/visual/describe_screenshot.py --list

# 截取指定 App 的視窗並分析
python tests/visual/describe_screenshot.py --app Python --prompt "檢查會議摘要區塊有幾個🔄按鈕"

# 截取指定視窗 ID
python tests/visual/describe_screenshot.py --window-id 1234 --prompt "描述 UI 佈局"

# 截取全螢幕
python tests/visual/describe_screenshot.py --fullscreen --prompt "找到 ASR 視窗並描述"

# 分析已存在的圖片
python tests/visual/describe_screenshot.py --image path/to/screenshot.png --prompt "描述內容"

# 只截圖不分析
python tests/visual/describe_screenshot.py --app Python --capture-only

# 指定輸出檔名
python tests/visual/describe_screenshot.py --app Python -o my_test.png

# JSON 格式輸出（方便程式化處理）
python tests/visual/describe_screenshot.py --app Python --prompt "檢查按鈕" --json

# 指定 Bedrock region 和模型
python tests/visual/describe_screenshot.py --app Python --region us-east-1 --model us.anthropic.claude-sonnet-4-20250514-v1:0
```

## 在 Kiro 中使用

Kiro agent 可以透過以下流程進行 UI 視覺驗證：

```python
# 1. 啟動 GUI
controlBashProcess(action="start", command="source asr/.venv/bin/activate && python asr/gui/main.py")

# 2. 等待視窗出現
executeBash("sleep 5")

# 3. 截圖 + 分析
executeBash("python3 asr/tests/visual/describe_screenshot.py --app Python --prompt '檢查...'")
```

## 截圖存放

截圖自動存放在 `tests/visual/screenshots/` 目錄下，帶時間戳命名，已加入 `.gitignore`。

## 套用到其他專案

此工具不依賴 ASR 專案的任何程式碼，可直接複製 `tests/visual/` 目錄到其他專案使用。唯一需要調整的是 `--region` 和 `--model` 參數。

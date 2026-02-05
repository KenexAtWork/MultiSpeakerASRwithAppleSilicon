# Scripts

這個目錄包含維護和工具腳本。

## 檔案說明

- **cleanup_for_git.sh** - Git 清理腳本
  - 用於清理測試檔案和輸出
  - 在提交到 Git 之前使用
  - 已經執行過，保留作為參考

## 使用方式

```bash
# 清理測試檔案
cd ~/Utils/asr
./scripts/cleanup_for_git.sh
```

**注意：** 這個腳本會刪除所有測試影片、輸出檔案和日誌，請謹慎使用。

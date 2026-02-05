# 範例檔案

這個目錄包含範例影片和輸出結果，用於展示 ASR 多說話者轉錄工具的功能。

## 目錄結構

```
examples/
├── sample-01.mp4                              # 範例影片（約 1 分鐘）
└── sample-output/                             # 輸出結果
    ├── sample-01_transcription.srt           # SRT 字幕檔案
    ├── sample-screen-shot-01.png             # 輸出結果截圖 1
    └── sample-screen-shot-02.png             # 輸出結果截圖 2
```

## 檔案說明

### sample-01.mp4
- 範例影片檔案（720p）
- 包含多位說話者的對話
- 長度：約 1 分鐘
- 用於測試和展示工具功能

### sample-output/
包含處理後的輸出結果：

- **sample-01_transcription.srt** - 轉錄結果（SRT 格式）
  - 包含時間軸和說話者標記
  - 可直接用於影片播放器
  
- **sample-screen-shot-01.png** - 輸出結果截圖
  - 展示終端輸出的處理統計資訊
  
- **sample-screen-shot-02.png** - 字幕效果截圖
  - 展示 SRT 字幕在影片播放器中的效果

## 使用方式

```bash
# 處理範例影片
./asr.sh examples/sample-01.mp4

# 輸出將會是：examples/sample-01_transcription.srt
```

## 自己測試

你可以用這個範例影片來：
1. ✅ 測試環境是否正確設定
2. ✅ 驗證模型下載是否成功
3. ✅ 了解輸出格式（SRT 字幕）
4. ✅ 評估處理速度和品質
5. ✅ 查看說話者分離效果

## 預期結果

處理完成後，你應該會看到類似的輸出：

```
============================================================
✓ 處理完成！
✓ 共處理 XX 個字幕段落
✓ 影片時長: 00:01:00,000
✓ 處理時間: X 分 XX 秒
✓ 處理速度: X.XXx（X.XXx 即時速度）
✓ 偵測到的說話者: SPEAKER_00, SPEAKER_01
✓ 輸出檔案: examples/sample-01_transcription.srt
============================================================
```

## 注意事項

- 首次執行會下載模型（約 1.7 GB），需要 5-15 分鐘
- 需要設定 HF_TOKEN 才能使用說話者分離功能
- 處理時間取決於影片長度和硬體配置
- 在 M1/M2/M3 Mac 上使用 GPU 加速可獲得最佳效能

## 查看輸出結果

```bash
# 查看 SRT 字幕內容
cat examples/sample-output/sample-01_transcription.srt

# 或使用影片播放器（如 VLC）載入字幕
vlc examples/sample-01.mp4 --sub-file examples/sample-output/sample-01_transcription.srt
```

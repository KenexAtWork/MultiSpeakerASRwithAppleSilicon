# GUI Test Report

## Test Environment
- Python: 3.10
- PyQt6: 6.10.2
- Test Date: 2026-02-13
- Test File: examples/sample-01.mp4 (59-second video)

## Test Items

### ✅ 1. Package Installation Test
- PyQt6 installed successfully
- mlx-whisper installed
- pyannote-audio installed
- All dependency packages normal

### ✅ 2. GUI Component Import Test
- MainWindow imported successfully
- ASRWorker imported successfully
- No syntax errors

### ✅ 3. GUI Interface Display Test
- Window displays normally
- Window size: 800x700
- Window title correct
- No rendering errors

### ✅ 4. ASR Worker Processing Test
- Successfully loaded Whisper model (medium)
- ASR transcription completed (16 seconds, 3.63x realtime speed)
- Speaker diarization completed (23 seconds, 2.52x realtime speed)
- Total processing time: 40 seconds (1.49x realtime speed)
- Output file generated successfully
- File size: 2837 bytes
- Subtitle segments: 39
- Detected speakers: 2 (SPEAKER_00, SPEAKER_01)

### ✅ 5. Output Format Validation
- SRT format correct
- Timestamp format correct
- Speaker labels correct
- Chinese subtitles display normally

## Test Results

### All Tests Passed ✅

GUI application runs normally, including:
1. Interface displays normally
2. Background processing normal
3. ASR transcription function normal
4. Speaker diarization function normal
5. File output normal

## Known Issues

None

## Recommendations

1. Can start using GUI for actual testing
2. Recommend using `./run_gui.sh` to launch
3. Ensure `HF_TOKEN` is configured in `.env` file

## Launch Method

```bash
cd ~/Utils/asr
./run_gui.sh
```

## Feature Highlights

- ✅ Drag and drop file support
- ✅ Real-time processing progress display
- ✅ Real-time processing log updates
- ✅ Support for multiple languages and model selection
- ✅ Selectable output format (SRT/TXT)
- ✅ Background processing, UI doesn't freeze
- ✅ Support for Apple Silicon GPU acceleration

## Test Commands

To re-test:

```bash
# Test GUI display
.venv/bin/python test_gui_display.py

# Test ASR processing
.venv/bin/python test_gui_processing.py
```

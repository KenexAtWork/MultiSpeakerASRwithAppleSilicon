# Development Log — feature/realtime-asr

## Current Status (2026-03-04)

### Completed
- Realtime ASR feature with mic capture, VAD-based chunking, silence detection
- RealtimePanel UI: Start/Stop/Pause, VU meter, live transcript, Save TXT
- Tab-based main window (File Transcription / Realtime ASR)
- Hallucination filter (repetition, dedup, phantom phrases, single-char spam)
- Qwen3-ASR engine option (0.6B / 1.7B) alongside mlx-whisper
- Suppressed `pad_token_id` console warning spam (transformers logger → ERROR)
- Reduced `SILENCE_SPLIT_DURATION` from 0.6s to 0.4s for faster response feel
- Added opencc simplified→traditional Chinese auto-conversion for Qwen3-ASR output
- Added test suite `tests/test_qwen3_s2t.py`:
  - 5 unit tests (opencc logic, no model needed) — all passing
  - 3 integration tests (Qwen3-ASR + sample-01.mp4 + s2t verification) — pending execution

### Pending / Not Yet Tested
- **opencc s2t conversion**: Code added, unit tests pass, but not yet tested live on device
  - Need to install `opencc-python-reimplemented` and run realtime ASR to verify
  - Integration tests written (`tests/test_qwen3_s2t.py -k integration`) but not yet executed (requires model load)

### Known Behaviors
- Qwen3-ASR natively outputs simplified Chinese — opencc `s2t` converter handles conversion
- If opencc is not installed, output gracefully falls back to simplified Chinese
- Chunk duration: MIN=3s, MAX=10s, silence split=0.4s, silence threshold=0.01 RMS

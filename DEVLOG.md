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

### Pending / Not Yet Tested
- **opencc s2t conversion**: Code added but not yet tested on device. Need to:
  1. Install `opencc-python-reimplemented`
  2. Run realtime ASR with Qwen3-ASR engine and verify output is traditional Chinese
- **Automated test for s2t conversion**: User wants an automated test. Plan:
  - User will provide a test audio file (Chinese speech)
  - Build a test that runs Qwen3-ASR on the audio, checks output contains traditional Chinese characters
  - Could also unit-test the opencc conversion in isolation (no model needed)

### Known Behaviors
- Qwen3-ASR natively outputs simplified Chinese — opencc `s2t` converter handles conversion
- If opencc is not installed, output gracefully falls back to simplified Chinese
- Chunk duration: MIN=3s, MAX=10s, silence split=0.4s, silence threshold=0.01 RMS

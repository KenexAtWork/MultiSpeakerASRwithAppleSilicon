# Development Log — feature/realtime-asr

## Current Status (2026-03-05)

### Completed
- Realtime ASR feature with mic capture, VAD-based chunking, silence detection
- RealtimePanel UI: Start/Stop/Pause, VU meter, live transcript, Save TXT
- Tab-based main window (File Transcription / Realtime ASR)
- Hallucination filter (repetition, dedup, phantom phrases, single-char spam)
- Qwen3-ASR engine option (0.6B / 1.7B) alongside mlx-whisper
- Suppressed `pad_token_id` console warning spam (transformers logger → ERROR)
- Reduced `SILENCE_SPLIT_DURATION` from 0.6s to 0.4s for faster response feel
- Added opencc simplified→traditional Chinese auto-conversion for Qwen3-ASR output
- Live Summary (AWS Bedrock) — auto-summarize transcript periodically
- Speaker Name Mapping — assign real names to SPEAKER_XX labels
- Model loading state indicator (orange "Loading model..." button)
- Mic preview VU meter (live before recording starts)
- Device refresh with hardware re-scan for hot-plugged mics
- **Dual-Pass ASR (Refinement)**:
  - Incremental mode: re-transcribes ~30s segments in background with larger model while recording
  - Post-recording mode: re-transcribes full recording after stopping for high-quality output
  - New `gui/core/refinement_worker.py` with `IncrementalRefinementWorker` and `PostRecordingRefinementWorker`
  - `realtime_worker.py` now emits `raw_chunk` signal for refinement pipeline
  - UI: refinement settings group, refined transcript display, save refined output (TXT/SRT)
  - 17 unit tests in `tests/test_refinement.py` — all passing
- Test suite: `tests/test_qwen3_s2t.py`, `tests/test_live_summary.py`, `tests/test_speaker_mapping.py`, `tests/test_refinement.py`
- Integrated test runner `run_tests.sh` with all test targets

### Pending / Not Yet Tested
- **Dual-Pass ASR live test**: Unit tests pass, but not yet tested with actual mic input + model
  - Incremental mode needs live recording to verify segment timing and replacement
  - Post-recording mode needs a completed recording to verify full re-transcription
- **opencc s2t conversion**: Code added, unit tests pass, but not yet tested live on device

### Known Behaviors
- Qwen3-ASR natively outputs simplified Chinese — opencc `s2t` converter handles conversion
- If opencc is not installed, output gracefully falls back to simplified Chinese
- Chunk duration: MIN=3s, MAX=10s, silence split=0.4s, silence threshold=0.01 RMS

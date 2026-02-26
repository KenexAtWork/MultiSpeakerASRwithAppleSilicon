# ASR Automated Testing

This directory contains automated tests for the ASR Multi-Speaker project.

## Test Coverage

For detailed test coverage documentation, see: [TEST_COVERAGE.md](./TEST_COVERAGE.md)

## Quick Start

### Run All Tests with One Command

```bash
cd asr

# Fast mode (recommended, ~20 seconds)
./run_tests.sh --fast

# Full mode (with diarization, ~60 seconds)
./run_tests.sh

# Run specific test only
./run_tests.sh --test pipeline
./run_tests.sh --test merge

# Show verbose output
./run_tests.sh --fast --verbose

# View all options
./run_tests.sh --help
```

### Manually Run Individual Tests

```bash
cd asr

# Fast tests (skip diarization, ~20 seconds)
.venv/bin/python tests/test_pipeline_e2e.py --fast
.venv/bin/python tests/test_merge_srt.py
.venv/bin/python tests/test_gui_media_url.py
.venv/bin/python tests/test_srt_parser.py
.venv/bin/python tests/test_error_handling.py

# Full tests (with diarization, ~60 seconds)
.venv/bin/python tests/test_pipeline_e2e.py
```

### Individual Test Descriptions

#### 1. Pipeline End-to-End Test (`test_pipeline_e2e.py`)

Tests complete ASR transcription pipeline, including Whisper ASR, speaker diarization, segment merging.

```bash
# Fast mode (Whisper base, skip diarization)
.venv/bin/python tests/test_pipeline_e2e.py --fast

# Full mode (Whisper base + diarization)
.venv/bin/python tests/test_pipeline_e2e.py

# Specify model
.venv/bin/python tests/test_pipeline_e2e.py --model medium
```

**Test Items:**
- SRT output file exists and non-empty
- SRT format correct (index, timestamp, text)
- Timestamps increasing
- Index sequential numbering
- All marked as Unknown when skip diarization
- language=auto doesn't error
- TXT format output
- Merge step effective
- Diarization detects ≥2 speakers
- Merge step reduces segment count
- Unknown segments not merged

#### 2. Merge Function Test (`test_merge_srt.py`)

Tests same speaker adjacent segment merge logic.

```bash
# Unit test
.venv/bin/python tests/test_merge_srt.py

# Integration test (specify actual SRT file)
.venv/bin/python tests/test_merge_srt.py --srt path/to/file.srt
```

**Test Items:**
- Empty input handling
- Single segment handling
- Same speaker merging
- Different speaker no merge
- Unknown speaker no merge
- Gap limit (max_gap)
- Duration limit (max_duration)
- Character limit (max_chars)
- Index sequential numbering
- Timestamp validity
- Text not lost
- Skip diarization scenario

#### 3. GUI Media Player Test (`test_gui_media_url.py`)

Tests QMediaPlayer support for Chinese/special character filenames.

```bash
.venv/bin/python tests/test_gui_media_url.py
```

**Test Items:**
- Chinese path QUrl conversion
- Space path QUrl conversion
- Mixed Chinese-English path handling
- Actual temp file round-trip
- QMediaPlayer accepts Chinese URL
- Actual audio file loading

#### 4. SRT Parser Test (`test_srt_parser.py`)

Tests SRT parsing logic in GUI.

```bash
.venv/bin/python tests/test_srt_parser.py
```

**Test Items:**
- Basic SRT format parsing
- Multi-line text handling
- Timestamp conversion correctness
- Chinese character handling
- Empty file handling
- Malformed timestamps
- Missing text content
- Extra blank line handling
- time_str field preservation
- Actual SRT file testing
- Special character handling
- Zero duration segments

#### 5. Error Handling Test (`test_error_handling.py`)

Tests ASR Pipeline behavior in various error conditions.

```bash
.venv/bin/python tests/test_error_handling.py
```

**Test Items:**
- Should error when file doesn't exist
- Invalid model name
- Invalid language code
- No HF token but require diarization
- Invalid output format
- Output to read-only directory
- Corrupted video file
- Empty video file

## Test Environment Requirements

### Required Packages
```bash
# Already installed in .venv
pip install PyQt6 mlx-whisper pyannote.audio boto3
```

### Environment Variables
```bash
# .env file
HF_TOKEN=your_huggingface_token  # Required for diarization tests
```

### Test Data
- `examples/sample-01.mp4` - 60-second test audio (2 speakers)
- Other actual audio files can be used for integration testing

## Test Result Examples

### Success Output
```
============================================================
ASR Pipeline End-to-End Test (model=base)
Audio: /path/to/asr/examples/sample-01.mp4
Mode: Fast (no diarization)
============================================================
  ✓ SRT output file exists and non-empty
  ✓ SRT format correct (index, timestamp, text)
  ✓ Timestamps increasing
  ✓ Index sequential numbering
  ✓ All marked as Unknown when skip diarization
  ✓ language=auto doesn't error
  ✓ TXT format output
  ✓ Merge step effective (reasonable segment count)
  [basic] 16.2s

Result: 8 passed, 0 failed
✓ All passed
```

## Continuous Integration

### Local CI Testing

```bash
cd asr
./ci_test.sh
```

This script will:
- Check environment and dependencies
- Run all tests (fast mode)
- Generate test report
- Suitable for any CI/CD system

### GitHub Actions

Project includes `.github/workflows/tests.yml` configuration file, automatically runs tests when:
- Push to main or develop branch
- Create Pull Request

Need to configure `HF_TOKEN` secret in GitHub repository settings.

### Test Script Descriptions

| Script | Purpose | Execution Time |
|--------|---------|---------------|
| `run_tests.sh` | Local development testing, supports multiple options | 20-60 seconds |
| `ci_test.sh` | CI/CD automated testing, simplified output | ~20 seconds |
| `.github/workflows/tests.yml` | GitHub Actions configuration | ~20 seconds |

## Adding Tests

### Test File Naming Convention
- `test_*.py` - Test files
- Place in `tests/` directory
- Use `assert` for validation

### Test Function Naming Convention
```python
def test_feature_description():
    """Test item description (will be displayed in test report)"""
    # Test logic
    assert condition, "Error message"
```

### Update Test Coverage Documentation
After adding tests, please update [TEST_COVERAGE.md](./TEST_COVERAGE.md).

## Known Limitations

1. **Visual Testing Incomplete** - GUI automation testing tools built but not integrated (coordinate precision issues)
2. **GUI Worker Not Tested** - `asr_worker.py` and `summary_worker.py` need Mock testing
3. **Error Handling Not Covered** - Insufficient exception scenario testing
4. **Performance Testing Missing** - Long audio, large segment count stability not verified

See "Priority Improvement Recommendations" section in [TEST_COVERAGE.md](./TEST_COVERAGE.md).

## Issue Reporting

When tests fail, please provide:
1. Complete error message
2. Test command
3. Environment information (Python version, OS, memory)
4. Test audio file information (if applicable)

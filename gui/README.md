# ASR Multi-Speaker Transcription - GUI Version

Graphical interface version built with PyQt6.

## Features

- ✅ Drag and drop file support
- ✅ Real-time processing progress display
- ✅ Real-time processing log updates
- ✅ Support for multiple languages and model selection
- ✅ Model download status indicator (✅ downloaded / ⬇ not yet downloaded)
- ✅ Selectable output format (SRT/TXT)
- ✅ Background processing, UI doesn't freeze
- ✅ Realtime ASR — live microphone transcription with MLX Whisper, Qwen3-ASR, or AWS Transcribe
- ✅ System audio capture for online meetings (via BlackHole)
- ✅ Dual-pass ASR refinement (incremental + post-recording)
- ✅ Send to VOD — bridge realtime recording to File Transcription for speaker diarization
- ✅ Live Notes — auto-summarize transcript via AWS Bedrock during recording
- ✅ Subtitle editing with audio playback and click-to-jump
- ✅ AWS Bedrock meeting summarization

## System Requirements

- macOS (supports Apple Silicon M1/M2/M3)
- Python 3.10 (Important: PyQt6 currently doesn't support Python 3.11+)
- 16GB RAM (recommended)

## Installation

### Quick Start (Recommended)

```bash
# 1. Create Python 3.10 virtual environment
python3.10 -m venv .venv

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Install all packages
pip install mlx-whisper pyannote-audio PyQt6

# 4. Configure Hugging Face Token
cp .env.example .env
# Edit .env and add your HF_TOKEN

# 5. Launch GUI
./run_gui.sh
```

### Detailed Installation Steps

#### Method 1: Using Standard venv (Recommended)

```bash
# Check Python version (must be 3.10)
python3.10 --version

# Create virtual environment
python3.10 -m venv .venv

# Activate environment
source .venv/bin/activate

# Install packages
pip install mlx-whisper pyannote-audio PyQt6

# Launch GUI
./run_gui.sh
```

#### Method 2: Using Homebrew Python 3.10

If system doesn't have Python 3.10:

```bash
# Install Python 3.10
brew install python@3.10

# Create virtual environment
/opt/homebrew/bin/python3.10 -m venv .venv

# Activate environment
source .venv/bin/activate

# Install packages
pip install mlx-whisper pyannote-audio PyQt6

# Launch GUI
./run_gui.sh
```

#### Important Notes

- PyQt6 currently only supports Python 3.10, not 3.11 or newer
- If you encounter `ModuleNotFoundError: No module named 'PyQt6'`, check:
  1. Virtual environment is properly activated
  2. PyQt6 is installed in virtual environment (not system Python)
  3. Python version is 3.10

### Environment Variable Configuration

Ensure `HF_TOKEN` is configured:

```bash
# Copy example file
cp .env.example .env

# Edit .env and add your token
# HF_TOKEN=your_huggingface_token_here
```

## Usage

### Launch GUI

```bash
# Launch from gui directory
cd gui
python main.py

# Or launch from asr directory
python gui/main.py
```

### Usage Steps

1. **Select File**
   - Drag and drop video file into window
   - Or click "Select File" button

2. **Configure Parameters**
   - Select language (Chinese/English/Japanese/Auto)
   - Select model size (tiny/base/small/medium/large)
   - Select output format (SRT/TXT)
   - Optional: Skip speaker diarization
   - Optional: Disable GPU acceleration

3. **Start Processing**
   - Click "Start Transcription" button
   - Watch progress bar and log output
   - Wait for processing to complete

4. **View Results**
   - Notification appears when processing completes
   - Click "Open Output Folder" to view results

## Project Structure

```
gui/
├── main.py              # Main program entry
├── ui/
│   ├── __init__.py
│   ├── main_window.py   # Main window UI (File Transcription tab)
│   └── realtime_panel.py # Realtime ASR tab
├── core/
│   ├── __init__.py
│   ├── asr_worker.py    # Background ASR processing Worker
│   ├── realtime_worker.py    # Realtime mic transcription Worker
│   ├── refinement_worker.py  # Dual-pass refinement Workers
│   ├── summary_worker.py     # AWS Bedrock summary Worker
│   └── live_summary_worker.py # Live summary during recording
├── utils/
│   └── __init__.py
├── resources/           # Resource files (icons, etc.)
├── requirements.txt     # Python package requirements
└── README.md           # This file
```

## Technical Details

### Architecture

- **PyQt6**: Cross-platform GUI framework
- **QThread**: Background ASR execution, prevents UI freezing
- **Signal/Slot**: Update progress and logs
- **Drag and Drop**: QDragDrop implementation

### Key Components

1. **MainWindow** (`ui/main_window.py`)
   - File Transcription tab UI
   - Model selection with download status indicators
   - Subtitle editing, audio playback, speaker mapping
   - AWS Bedrock summarization

2. **RealtimePanel** (`ui/realtime_panel.py`)
   - Live microphone transcription
   - Multiple engine support (MLX Whisper, Qwen3-ASR, AWS Transcribe)
   - System audio capture via BlackHole for online meetings
   - Dual-pass refinement (incremental + post-recording)
   - Send to VOD bridge for speaker diarization
   - Live Notes auto-summary

3. **ASRWorker** (`core/asr_worker.py`)
   - Executes ASR in background thread
   - Sends progress and log signals
   - Handles errors

4. **DropZone** (`ui/main_window.py`)
   - Custom drag and drop area
   - Supports file drag and drop

## Future Improvements

- [ ] Batch processing of multiple files
- [ ] Save and load settings
- [ ] Processing history
- [ ] More detailed progress display (per-stage progress)
- [ ] Support for canceling processing
- [ ] Package as .app (using py2app)
- [ ] Support more output formats
- [ ] Preview transcription results

## Package as macOS App

(To be implemented)

```bash
# Package using py2app
pip install py2app
python setup.py py2app
```

## Troubleshooting

### Problem: Cannot find asr_multi_speaker_v5_fast module

Ensure launching from correct directory, or check `sys.path` configuration.

### Problem: UI freezes

Confirm ASR processing is executing in QThread, not main thread.

### Problem: Cannot drag and drop files

Check if `setAcceptDrops(True)` is properly configured.

## License

MIT License

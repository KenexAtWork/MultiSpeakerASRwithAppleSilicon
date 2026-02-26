# Distribution Guide

This document explains how to package and distribute this project to other users.

## Packaging Method

Use git archive for packaging (cleanest method):

```bash
git archive --format=tar.gz --prefix=MultiSpeakerASR/ -o MultiSpeakerASR.tar.gz HEAD
```

This creates a `MultiSpeakerASR.tar.gz` file containing all Git-tracked files, but excluding:
- `.git/` directory
- `.venv/` virtual environment
- `__pycache__/` cache
- `.env` environment variables
- Other files in `.gitignore`

## Recipient Usage Steps

### 1. Extract

```bash
tar -xzf MultiSpeakerASR.tar.gz
cd MultiSpeakerASR
```

### 2. Run Installation

```bash
./install.sh
```

The installation script will automatically:
- Check Python version
- Install uv (if needed)
- Create virtual environment
- Install all dependencies
- Create .env file

### 3. Configure Environment Variables

Edit the `.env` file:

```bash
nano .env
```

Fill in required information:
- `HF_TOKEN` - Hugging Face token (for speaker diarization)
- `AWS_REGION` - AWS region (for summarization, optional)
- `AWS_PROFILE` - AWS profile (defaults to default)

### 4. Launch GUI

```bash
./run_gui.sh
```

## Package Contents

The package includes:
- ✅ All source code
- ✅ Installation scripts
- ✅ Documentation and examples
- ✅ Test files
- ❌ Does not include virtual environment (.venv)
- ❌ Does not include cache files (__pycache__)
- ❌ Does not include environment variables (.env)
- ❌ Does not include Git history (.git)

## System Requirements

Recipients need:
- macOS with Apple Silicon (M1/M2/M3/M4 or newer)
- Python 3.10+ (if not available, uv will automatically download)
- Internet connection (for downloading dependencies and AI models)
- At least 8GB RAM (16GB recommended)

## First Run

First run will automatically download AI models:
- Whisper model: ~1.5 GB
- Speaker Diarization model: ~200 MB (if used)

Download time depends on network speed (~2-8 minutes).

## Offline Usage

For completely offline usage:

1. Complete installation and run once on a machine with internet
2. Package with cache directories:
   ```bash
   tar -czf MultiSpeakerASR-with-models.tar.gz \
     MultiSpeakerASR/ \
     ~/.cache/huggingface/hub/models--mlx-community--whisper-medium-mlx \
     ~/.cache/huggingface/hub/models--pyannote--speaker-diarization-3.1
   ```
3. Extract on target machine and restore cache

## Troubleshooting

### Permission Issues

If scripts cannot execute:

```bash
chmod +x install.sh run_gui.sh run_tests.sh
chmod +x scripts/*.sh
```

### Python Version Issues

If system Python version is too old, `install.sh` will automatically use uv to download Python 3.10.

### Dependency Installation Failure

Ensure stable internet connection, then re-run:

```bash
./install.sh
```

## Updates

To update to a new version:

1. Download latest version from GitHub
2. Or use new package file
3. Re-run `./install.sh`

## Support

- GitHub: https://github.com/KenexAtWork/MultiSpeakerASRwithAppleSilicon
- Issues: https://github.com/KenexAtWork/MultiSpeakerASRwithAppleSilicon/issues

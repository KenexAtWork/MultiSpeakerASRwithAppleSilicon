# Example Files

This directory contains sample videos and output results to demonstrate the ASR multi-speaker transcription tool's capabilities.

## Directory Structure

```
examples/
├── sample-01.mp4                              # Sample video (~1 minute)
└── sample-output/                             # Output results
    ├── sample-01_transcription.srt           # SRT subtitle file
    ├── sample-screen-shot-01.png             # Output result screenshot 1
    └── sample-screen-shot-02.png             # Output result screenshot 2
```

## File Descriptions

### sample-01.mp4
- Sample video file (720p)
- Contains multi-speaker conversation
- Length: ~1 minute
- Used for testing and demonstrating tool capabilities

### sample-output/
Contains processed output results:

- **sample-01_transcription.srt** - Transcription result (SRT format)
  - Includes timeline and speaker labels
  - Can be used directly in video players
  
- **sample-screen-shot-01.png** - Output result screenshot
  - Shows terminal output processing statistics
  
- **sample-screen-shot-02.png** - Subtitle effect screenshot
  - Shows SRT subtitles in video player

## Usage

```bash
# Process sample video
./asr.sh examples/sample-01.mp4

# Output will be: examples/sample-01_transcription.srt
```

## Test It Yourself

You can use this sample video to:
1. ✅ Test if environment is properly configured
2. ✅ Verify model download success
3. ✅ Understand output format (SRT subtitles)
4. ✅ Evaluate processing speed and quality
5. ✅ See speaker diarization effect

## Expected Results

After processing completes, you should see similar output:

```
============================================================
✓ Processing complete!
✓ Total XX subtitle segments processed
✓ Video duration: 00:01:00,000
✓ Processing time: X minutes XX seconds
✓ Processing speed: X.XXx (X.XXx realtime speed)
✓ Detected speakers: SPEAKER_00, SPEAKER_01
✓ Output file: examples/sample-01_transcription.srt
============================================================
```

## Notes

- First run will download models (~1.7 GB), takes 5-15 minutes
- Need to configure HF_TOKEN to use speaker diarization feature
- Processing time depends on video length and hardware configuration
- On M1/M2/M3 Mac, GPU acceleration provides best performance

## View Output Results

```bash
# View SRT subtitle content
cat examples/sample-output/sample-01_transcription.srt

# Or use video player (like VLC) to load subtitles
vlc examples/sample-01.mp4 --sub-file examples/sample-output/sample-01_transcription.srt
```

#!/usr/bin/env python3
"""
Tests for Qwen3-ASR simplified→traditional Chinese conversion.

Two test levels:
  1. Unit test: opencc conversion logic (no model needed, fast)
  2. Integration test: full Qwen3-ASR pipeline on sample audio (needs model + GPU)

Usage:
  # Unit tests only (fast, no model):
  python -m pytest tests/test_qwen3_s2t.py -k unit -v

  # Integration test (requires qwen-asr + opencc installed, loads model):
  python -m pytest tests/test_qwen3_s2t.py -k integration -v

  # All:
  python -m pytest tests/test_qwen3_s2t.py -v
"""
import os
import sys
import pytest
import numpy as np
from pathlib import Path

ASR_DIR = Path(__file__).resolve().parent.parent
SAMPLE_AUDIO = ASR_DIR / "examples" / "sample-01.mp4"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def has_traditional_chinese(text: str) -> bool:
    """Check if text contains characters commonly traditional-only.

    Uses a small set of traditional chars that differ from simplified.
    Not exhaustive, but good enough for a smoke test.
    """
    # Common traditional-only characters (no simplified equivalent that looks the same)
    traditional_markers = set(
        "國學說這個們來對點書還會從過問題後種讓開關實際經驗發現當認為應該"
        "閱讀裡頭與對於從來過說話時間問題點點點點點點點點點點點點點點點點"
    )
    # Simplified equivalents that should NOT appear if conversion worked
    simplified_markers = set("国学说这个们来对点书还会从过问题后种让开关实际经验发现当认为应该")

    trad_count = sum(1 for c in text if c in traditional_markers)
    simp_count = sum(1 for c in text if c in simplified_markers)

    return trad_count > 0 and trad_count > simp_count


def has_simplified_chinese(text: str) -> bool:
    """Check if text contains simplified-only characters."""
    simplified_only = set("国学说这个们来对还会从过问题后种让开关实际经验发现当认为应该")
    return any(c in simplified_only for c in text)


# ---------------------------------------------------------------------------
# Unit Tests (no model needed)
# ---------------------------------------------------------------------------

class TestOpenCCConversionUnit:
    """Unit tests for opencc s2t conversion logic."""

    @pytest.fixture
    def converter(self):
        opencc = pytest.importorskip("opencc", reason="opencc-python-reimplemented not installed")
        from opencc import OpenCC
        return OpenCC("s2t")

    def test_unit_basic_s2t(self, converter):
        """Basic simplified → traditional conversion."""
        simplified = "我们今天讨论阅读与理解之间的关系"
        result = converter.convert(simplified)
        assert "們" in result  # 们 → 們
        assert "討論" in result  # 讨论 → 討論
        assert "閱讀" in result  # 阅读 → 閱讀
        assert "關係" in result  # 关系 → 關係
        assert not has_simplified_chinese(result)

    def test_unit_already_traditional(self, converter):
        """Traditional input should pass through unchanged."""
        traditional = "我覺得閱讀跟理解中間有很大的落差"
        result = converter.convert(traditional)
        assert result == traditional

    def test_unit_english_passthrough(self, converter):
        """English text should not be affected."""
        english = "Hello world, this is a test."
        result = converter.convert(english)
        assert result == english

    def test_unit_mixed_content(self, converter):
        """Mixed Chinese/English should convert only Chinese parts."""
        mixed = "这个 project 的 README 说明了使用方法"
        result = converter.convert(mixed)
        assert "這個" in result
        assert "project" in result
        assert "說明" in result
        assert not has_simplified_chinese(result)

    def test_unit_empty_string(self, converter):
        """Empty string should return empty."""
        assert converter.convert("") == ""


# ---------------------------------------------------------------------------
# Integration Test (requires model + audio)
# ---------------------------------------------------------------------------

class TestQwen3ASRS2TIntegration:
    """Integration test: run Qwen3-ASR on real audio, verify traditional output."""

    @pytest.fixture(scope="class")
    def qwen3_model(self):
        """Load Qwen3-ASR model (shared across tests in this class)."""
        torch = pytest.importorskip("torch", reason="torch not installed")
        qwen_asr = pytest.importorskip("qwen_asr", reason="qwen-asr not installed")
        from qwen_asr import Qwen3ASRModel

        if torch.backends.mps.is_available():
            device, dtype = "mps", torch.float16
        elif torch.cuda.is_available():
            device, dtype = "cuda:0", torch.bfloat16
        else:
            device, dtype = "cpu", torch.float32

        model = Qwen3ASRModel.from_pretrained(
            "Qwen/Qwen3-ASR-0.6B",
            dtype=dtype,
            device_map=device,
            max_new_tokens=256,
        )
        return model

    @pytest.fixture(scope="class")
    def audio_array(self):
        """Extract first 30s of audio from sample-01.mp4 as numpy array."""
        if not SAMPLE_AUDIO.exists():
            pytest.skip(f"Sample audio not found: {SAMPLE_AUDIO}")

        librosa = pytest.importorskip("librosa", reason="librosa not installed")
        # Load first 30 seconds at 16kHz mono
        audio, sr = librosa.load(str(SAMPLE_AUDIO), sr=16000, mono=True, duration=30)
        return audio

    def test_integration_qwen3_raw_output_is_simplified(self, qwen3_model, audio_array):
        """Verify Qwen3-ASR raw output contains simplified Chinese (baseline)."""
        results = qwen3_model.transcribe(
            audio=[(audio_array, 16000)],
            language=["Chinese"],
        )
        assert results and results[0].text
        text = results[0].text.strip()
        assert len(text) > 10, f"Transcription too short: {text}"
        # Qwen3 should output simplified by default
        assert has_simplified_chinese(text), (
            f"Expected simplified Chinese in raw output, got: {text[:200]}"
        )

    def test_integration_s2t_converts_to_traditional(self, qwen3_model, audio_array):
        """Verify opencc converts Qwen3-ASR output to traditional Chinese."""
        opencc_mod = pytest.importorskip("opencc", reason="opencc not installed")
        from opencc import OpenCC
        converter = OpenCC("s2t")

        results = qwen3_model.transcribe(
            audio=[(audio_array, 16000)],
            language=["Chinese"],
        )
        assert results and results[0].text
        raw_text = results[0].text.strip()
        converted = converter.convert(raw_text)

        assert len(converted) > 10
        assert has_traditional_chinese(converted), (
            f"Expected traditional Chinese after conversion, got: {converted[:200]}"
        )
        assert not has_simplified_chinese(converted), (
            f"Found simplified chars after conversion: {converted[:200]}"
        )

    def test_integration_transcription_content_sanity(self, qwen3_model, audio_array):
        """Sanity check: transcription should contain topic-related words."""
        opencc_mod = pytest.importorskip("opencc", reason="opencc not installed")
        from opencc import OpenCC
        converter = OpenCC("s2t")

        results = qwen3_model.transcribe(
            audio=[(audio_array, 16000)],
            language=["Chinese"],
        )
        raw_text = results[0].text.strip()
        converted = converter.convert(raw_text)

        # The sample audio discusses reading comprehension (閱讀/理解)
        # Check that at least some relevant content appears
        topic_words = ["閱讀", "理解", "書", "看", "問"]
        found = [w for w in topic_words if w in converted]
        assert len(found) >= 2, (
            f"Expected topic words about reading/comprehension. "
            f"Found {found} in: {converted[:300]}"
        )

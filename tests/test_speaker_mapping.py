#!/usr/bin/env python3
"""
Tests for Speaker Name Mapping feature.

Unit tests verify the mapping logic without needing the full GUI.

Usage:
  python -m pytest tests/test_speaker_mapping.py -v
"""
import os
import sys
import re
import pytest

ASR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI_DIR = os.path.join(ASR_DIR, "gui")
for d in (ASR_DIR, GUI_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)


def apply_mapping(segments, mapping):
    """Standalone version of the mapping logic for testing."""
    changed = 0
    for seg in segments:
        original = seg['text']
        new_text = original
        for old_label, new_label in mapping.items():
            new_text = new_text.replace(old_label, new_label)
        if new_text != original:
            seg['text'] = new_text
            changed += 1
    return changed


def extract_speakers(segments):
    """Extract unique speaker labels from segments."""
    pattern = re.compile(r'\[SPEAKER_\d+\]')
    speakers = set()
    for seg in segments:
        speakers.update(pattern.findall(seg['text']))
    return sorted(speakers)


class TestSpeakerMapping:

    def _make_segments(self):
        return [
            {'start_ms': 0, 'end_ms': 2000, 'time_str': '00:00:00,000 --> 00:00:02,000',
             'text': '[SPEAKER_00] Hello everyone'},
            {'start_ms': 2000, 'end_ms': 5000, 'time_str': '00:00:02,000 --> 00:00:05,000',
             'text': '[SPEAKER_01] Good morning'},
            {'start_ms': 5000, 'end_ms': 8000, 'time_str': '00:00:05,000 --> 00:00:08,000',
             'text': '[SPEAKER_00] Let us begin the meeting'},
            {'start_ms': 8000, 'end_ms': 12000, 'time_str': '00:00:08,000 --> 00:00:12,000',
             'text': '[SPEAKER_02] I have a question'},
        ]

    def test_extract_speakers(self):
        segs = self._make_segments()
        speakers = extract_speakers(segs)
        assert speakers == ['[SPEAKER_00]', '[SPEAKER_01]', '[SPEAKER_02]']

    def test_basic_mapping(self):
        segs = self._make_segments()
        mapping = {
            '[SPEAKER_00]': '[Alice]',
            '[SPEAKER_01]': '[Bob]',
        }
        changed = apply_mapping(segs, mapping)
        assert changed == 3  # SPEAKER_00 appears twice, SPEAKER_01 once
        assert segs[0]['text'] == '[Alice] Hello everyone'
        assert segs[1]['text'] == '[Bob] Good morning'
        assert segs[2]['text'] == '[Alice] Let us begin the meeting'
        assert segs[3]['text'] == '[SPEAKER_02] I have a question'  # unchanged

    def test_empty_mapping(self):
        segs = self._make_segments()
        changed = apply_mapping(segs, {})
        assert changed == 0
        assert segs[0]['text'] == '[SPEAKER_00] Hello everyone'

    def test_no_speakers_in_text(self):
        segs = [{'start_ms': 0, 'end_ms': 1000,
                 'time_str': '00:00:00,000 --> 00:00:01,000',
                 'text': 'Just plain text without speakers'}]
        speakers = extract_speakers(segs)
        assert speakers == []

    def test_mapping_preserves_timestamps(self):
        segs = self._make_segments()
        original_times = [(s['start_ms'], s['end_ms'], s['time_str']) for s in segs]
        apply_mapping(segs, {'[SPEAKER_00]': '[Manager]'})
        for i, seg in enumerate(segs):
            assert seg['start_ms'] == original_times[i][0]
            assert seg['end_ms'] == original_times[i][1]
            assert seg['time_str'] == original_times[i][2]

    def test_chinese_speaker_names(self):
        segs = self._make_segments()
        mapping = {
            '[SPEAKER_00]': '[王經理]',
            '[SPEAKER_01]': '[李工程師]',
        }
        changed = apply_mapping(segs, mapping)
        assert changed == 3
        assert '[王經理]' in segs[0]['text']
        assert '[李工程師]' in segs[1]['text']

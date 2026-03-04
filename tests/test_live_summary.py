#!/usr/bin/env python3
"""
Tests for Live Summary feature.

Unit tests mock AWS Bedrock to verify:
  - LiveSummaryWorker signal flow
  - RealtimePanel summary trigger logic (segment count / timer)
  - Incremental summary (previous_summary passed correctly)

Usage:
  python -m pytest tests/test_live_summary.py -v
"""
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Ensure gui packages are importable
ASR_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUI_DIR = os.path.join(ASR_DIR, "gui")
for d in (ASR_DIR, GUI_DIR):
    if d not in sys.path:
        sys.path.insert(0, d)


class TestLiveSummaryWorker:
    """Unit tests for LiveSummaryWorker (mocked Bedrock)."""

    def test_worker_calls_bedrock_and_emits_summary(self):
        """Worker should call Bedrock converse and emit summary_updated."""
        from core.live_summary_worker import LiveSummaryWorker

        mock_response = {
            "output": {
                "message": {
                    "content": [{"text": "## 重點摘要\n- 討論了閱讀理解"}]
                }
            }
        }

        with patch("core.live_summary_worker.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.converse.return_value = mock_response
            mock_boto3.Session.return_value.region_name = "us-east-1"
            mock_boto3.Session.return_value.client.return_value = mock_client

            worker = LiveSummaryWorker(
                new_texts=["第一段文字", "第二段文字"],
                previous_summary="",
            )

            # Collect emitted signals
            results = {}
            worker.summary_updated.connect(lambda s: results.update({"summary": s}))
            worker.status.connect(lambda s: results.update({"status": s}))

            worker.run()  # run synchronously for testing

            assert "summary" in results
            assert "重點摘要" in results["summary"]
            assert mock_client.converse.call_count == 1

            # Verify the prompt contains our texts
            call_args = mock_client.converse.call_args
            prompt_text = call_args[1]["messages"][0]["content"][0]["text"]
            assert "第一段文字" in prompt_text
            assert "第二段文字" in prompt_text

    def test_worker_passes_previous_summary(self):
        """Worker should include previous summary in the prompt."""
        from core.live_summary_worker import LiveSummaryWorker

        mock_response = {
            "output": {
                "message": {
                    "content": [{"text": "updated summary"}]
                }
            }
        }

        with patch("core.live_summary_worker.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.converse.return_value = mock_response
            mock_boto3.Session.return_value.region_name = "us-east-1"
            mock_boto3.Session.return_value.client.return_value = mock_client

            prev = "## 之前的摘要\n- 重點一"
            worker = LiveSummaryWorker(
                new_texts=["新的文字"],
                previous_summary=prev,
            )
            worker.run()

            call_args = mock_client.converse.call_args
            prompt_text = call_args[1]["messages"][0]["content"][0]["text"]
            assert "之前的摘要" in prompt_text
            assert "新的文字" in prompt_text

    def test_worker_empty_texts_does_nothing(self):
        """Worker should not call Bedrock if texts are empty."""
        from core.live_summary_worker import LiveSummaryWorker

        with patch("core.live_summary_worker.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_boto3.Session.return_value.client.return_value = mock_client

            worker = LiveSummaryWorker(new_texts=[], previous_summary="")
            worker.run()

            mock_client.converse.assert_not_called()

    def test_worker_emits_error_on_exception(self):
        """Worker should emit error signal on Bedrock failure."""
        from core.live_summary_worker import LiveSummaryWorker

        with patch("core.live_summary_worker.boto3") as mock_boto3:
            mock_client = MagicMock()
            mock_client.converse.side_effect = Exception("Bedrock timeout")
            mock_boto3.Session.return_value.region_name = "us-east-1"
            mock_boto3.Session.return_value.client.return_value = mock_client

            worker = LiveSummaryWorker(
                new_texts=["some text"],
                previous_summary="",
            )

            errors = []
            worker.error.connect(lambda e: errors.append(e))
            worker.run()

            assert len(errors) == 1
            assert "Bedrock timeout" in errors[0]


class TestRealtimePanelSummaryTrigger:
    """Test summary trigger logic in RealtimePanel (no actual recording)."""

    @pytest.fixture
    def panel(self):
        """Create a RealtimePanel instance for testing."""
        pytest.importorskip("PyQt6", reason="PyQt6 not installed")
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        from ui.realtime_panel import RealtimePanel
        p = RealtimePanel()
        yield p
        p.cleanup()

    def test_pending_texts_accumulate(self, panel):
        """Transcript updates should accumulate in pending list."""
        panel._on_transcript("第一句")
        panel._on_transcript("第二句")
        assert len(panel._summary_pending_texts) == 2
        assert len(panel._session_texts) == 2

    def test_trigger_clears_pending(self, panel):
        """Triggering summary should clear pending texts."""
        panel._summary_pending_texts = ["a", "b", "c"]

        with patch("ui.realtime_panel.LiveSummaryWorker") as MockWorker:
            mock_instance = MagicMock()
            mock_instance.isRunning.return_value = False
            MockWorker.return_value = mock_instance

            panel._trigger_summary()

            assert len(panel._summary_pending_texts) == 0
            MockWorker.assert_called_once()
            # Verify texts were passed
            call_kwargs = MockWorker.call_args[1]
            assert call_kwargs["new_texts"] == ["a", "b", "c"]

    def test_no_trigger_when_empty(self, panel):
        """Should not trigger summary when no pending texts."""
        with patch("ui.realtime_panel.LiveSummaryWorker") as MockWorker:
            panel._trigger_summary()
            MockWorker.assert_not_called()

    def test_clear_resets_summary_state(self, panel):
        """Clear should reset all summary state."""
        panel._session_texts = ["a"]
        panel._summary_pending_texts = ["a"]
        panel._current_summary = "some summary"

        panel._clear_transcript()

        assert panel._session_texts == []
        assert panel._summary_pending_texts == []
        assert panel._current_summary == ""

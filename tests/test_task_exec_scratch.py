"""
Unit tests for task execution scratch write (proxy_server._write_task_exec_response_to_scratch).
Ensures agent responses are written to timestamped files in scratch.
"""

from pathlib import Path

import pytest

from src.servers.proxy_server import (
    SCRATCH_DIR,
    _write_task_exec_response_to_scratch,
)


class TestWriteTaskExecResponseToScratch:
    """Tests for _write_task_exec_response_to_scratch."""

    def test_writes_file_with_timestamp_and_status(self, tmp_path, monkeypatch):
        """Writing response creates a .txt file in scratch with date-time stamp and status."""
        monkeypatch.setattr("src.servers.proxy_server.SCRATCH_DIR", tmp_path)
        _write_task_exec_response_to_scratch(
            user_key="alice",
            task_id=1,
            status="awaiting_confirmation",
            message="I have finished the work for this task.",
        )
        files = list(tmp_path.glob("task_exec_*.txt"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "Task execution response" in content
        assert "Date-time:" in content
        assert "Status: awaiting_confirmation" in content
        assert "Task ID: 1" in content
        assert "I have finished the work for this task." in content
        assert files[0].name.startswith("task_exec_")
        assert "_alice_task1.txt" in files[0].name or "task1.txt" in files[0].name

    def test_filename_includes_sanitized_user_and_task(self, tmp_path, monkeypatch):
        """Filename includes sanitized user key and task id for uniqueness."""
        monkeypatch.setattr("src.servers.proxy_server.SCRATCH_DIR", tmp_path)
        _write_task_exec_response_to_scratch(
            user_key="user.with.dots",
            task_id=2,
            status="paused_awaiting_feedback",
            message="Need your input on X.",
        )
        files = list(tmp_path.glob("task_exec_*.txt"))
        assert len(files) == 1
        name = files[0].name
        assert "task_exec_" in name
        assert "task2" in name
        assert name.endswith(".txt")
        content = files[0].read_text(encoding="utf-8")
        assert "paused_awaiting_feedback" in content
        assert "Need your input on X." in content

    def test_writes_when_message_empty(self, tmp_path, monkeypatch):
        """Empty message still writes file with placeholder."""
        monkeypatch.setattr("src.servers.proxy_server.SCRATCH_DIR", tmp_path)
        _write_task_exec_response_to_scratch(
            user_key="bob",
            task_id=None,
            status="cancelled",
            message="",
        )
        files = list(tmp_path.glob("task_exec_*.txt"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "Status: cancelled" in content
        assert "(No response text)" in content

    def test_includes_summary_and_what_to_do(self, tmp_path, monkeypatch):
        """File includes SUMMARY and 'What you can do' so status is conclusive."""
        monkeypatch.setattr("src.servers.proxy_server.SCRATCH_DIR", tmp_path)
        _write_task_exec_response_to_scratch(
            user_key="alice",
            task_id=2,
            status="awaiting_confirmation",
            message="I have finished the work.",
        )
        files = list(tmp_path.glob("task_exec_*.txt"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "SUMMARY:" in content
        assert "Awaiting your confirmation" in content
        assert "What you can do:" in content
        assert "Confirm completion" in content

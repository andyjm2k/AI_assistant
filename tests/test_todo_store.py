"""
Unit tests for persistent todo store (src.servers.todo_store).
Covers load/save, add/update/delete/clear, sanitize_user_key, and atomic write.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.servers import todo_store as ts


class TestSanitizeUserKey:
    """Tests for sanitize_user_key."""

    def test_safe_key_unchanged(self):
        assert ts.sanitize_user_key("alice") == "alice"
        assert ts.sanitize_user_key("user_123") == "user_123"
        assert ts.sanitize_user_key("a.b-c") == "a.b-c"

    def test_unsafe_chars_replaced(self):
        assert ts.sanitize_user_key("a/b") == "a_b"
        assert " " not in ts.sanitize_user_key("a b")
        assert ts.sanitize_user_key("a@b") == "a_b"

    def test_empty_returns_default(self):
        assert ts.sanitize_user_key("") == "default"
        assert ts.sanitize_user_key("   ") == "default"

    def test_path_traversal_sanitized(self):
        out = ts.sanitize_user_key("../../../etc")
        assert "/" not in out
        assert "\\" not in out
        # Path separators removed so path cannot escape directory


class TestTodoStore:
    """Tests for load_tasks, save_tasks, add_task, update_task, delete_task, clear_tasks."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        with patch.object(ts, "TODO_DATA_DIR", tmp_path):
            yield tmp_path

    def test_load_tasks_missing_file_returns_empty(self, temp_dir):
        assert ts.load_tasks("nonexistent") == []

    def test_save_and_load_tasks(self, temp_dir):
        ts.save_tasks("user1", ["a", "b"])
        assert ts.load_tasks("user1") == ["a", "b"]
        meta = ts.load_tasks_with_meta("user1")
        assert meta["tasks"] == ["a", "b"]
        assert "updated_at" in meta or meta.get("updated_at") is not None

    def test_add_task(self, temp_dir):
        tasks = ts.add_task("u2", "first")
        assert tasks == ["first"]
        ts.add_task("u2", "second")
        assert ts.load_tasks("u2") == ["first", "second"]

    def test_update_task(self, temp_dir):
        ts.save_tasks("u3", ["a", "b", "c"])
        ts.update_task("u3", 2, "b_updated")
        assert ts.load_tasks("u3") == ["a", "b_updated", "c"]

    def test_update_task_invalid_id_raises(self, temp_dir):
        ts.save_tasks("u4", ["a"])
        with pytest.raises(ValueError, match="Invalid task ID"):
            ts.update_task("u4", 0, "x")
        with pytest.raises(ValueError, match="Invalid task ID"):
            ts.update_task("u4", 5, "x")

    def test_delete_task(self, temp_dir):
        ts.save_tasks("u5", ["a", "b", "c"])
        ts.delete_task("u5", 2)
        assert ts.load_tasks("u5") == ["a", "c"]

    def test_delete_task_invalid_id_raises(self, temp_dir):
        ts.save_tasks("u6", ["a"])
        with pytest.raises(ValueError, match="Invalid task ID"):
            ts.delete_task("u6", 2)

    def test_clear_tasks(self, temp_dir):
        ts.save_tasks("u7", ["x", "y"])
        out = ts.clear_tasks("u7")
        assert out == []
        assert ts.load_tasks("u7") == []

    def test_user_key_sanitized_in_path(self, temp_dir):
        ts.save_tasks("user/with/slash", ["one"])
        safe = ts.sanitize_user_key("user/with/slash")
        path = temp_dir / f"{safe}.json"
        assert path.exists()
        assert ts.load_tasks("user/with/slash") == ["one"]

    def test_scheduled_tasks_are_chronological(self, temp_dir):
        now = datetime.now(timezone.utc)
        ts.add_task("sched1", "unscheduled")
        ts.add_task("sched1", "later", scheduled_for=(now + timedelta(days=2)).isoformat())
        ts.add_task("sched1", "sooner", scheduled_for=(now + timedelta(days=1)).isoformat())
        meta = ts.load_tasks_with_meta("sched1")
        assert meta["tasks"][0] == "sooner"
        assert meta["tasks"][1] == "later"
        assert meta["tasks"][2] == "unscheduled"

    def test_complete_repeating_task_reschedules(self, temp_dir):
        start = datetime.now(timezone.utc) - timedelta(days=3)
        ts.add_task(
            "repeat1",
            "daily report",
            scheduled_for=start.isoformat(),
            recurrence={"frequency": "daily", "interval": 1},
        )
        result = ts.complete_task("repeat1", 1)
        assert result["rescheduled"] is True
        meta = ts.load_tasks_with_meta("repeat1")
        assert len(meta["tasks"]) == 1
        item = meta["task_items"][0]
        assert item["description"] == "daily report"
        assert item["next_run_at"] is not None
        next_run = datetime.fromisoformat(item["next_run_at"])
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)
        assert next_run.astimezone(timezone.utc) > datetime.now(timezone.utc)

    def test_complete_one_time_task_removes_task(self, temp_dir):
        ts.add_task("complete_once", "one-time")
        result = ts.complete_task("complete_once", 1)
        assert result["rescheduled"] is False
        assert ts.load_tasks("complete_once") == []

    def test_list_due_task_items_only_returns_due_scheduled(self, temp_dir):
        now = datetime.now(timezone.utc)
        ts.add_task("due1", "due task", scheduled_for=(now - timedelta(hours=1)).isoformat())
        ts.add_task("due1", "future task", scheduled_for=(now + timedelta(hours=3)).isoformat())
        ts.add_task("due1", "plain unscheduled")
        due_items = ts.list_due_task_items("due1")
        assert len(due_items) == 1
        assert due_items[0]["description"] == "due task"

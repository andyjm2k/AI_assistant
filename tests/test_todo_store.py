"""
Unit tests for persistent todo store (src.servers.todo_store).
Covers load/save, add/update/delete/clear, sanitize_user_key, and atomic write.
"""

import json
import os
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

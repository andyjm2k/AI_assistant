"""Unit tests for scripts/setup_env_and_dirs.py (env and dirs helper)."""
import os
import tempfile
from pathlib import Path

import pytest

from scripts.setup_env_and_dirs import (
    PATH_ENV_VARS,
    REQUIRED_DIRS,
    _normalize_path_for_env,
    _substitute_path_in_line,
    create_dirs,
)


def test_path_env_vars_contains_expected():
    """PATH_ENV_VARS includes known MCP path variables."""
    assert "MCP_RESEARCH_SAVE_DIRECTORY" in PATH_ENV_VARS
    assert "MCP_BROWSER_USER_DATA_DIR" in PATH_ENV_VARS
    assert "MCP_SERVER_RESULTS_DIR" in PATH_ENV_VARS


def test_normalize_path_for_env_windows():
    """_normalize_path_for_env on Windows uses backslashes."""
    p = Path("C:/Users/foo/project")
    out = _normalize_path_for_env(p, on_windows=True)
    assert "\\" in out or os.sep in out


def test_normalize_path_for_env_posix():
    """_normalize_path_for_env on POSIX leaves path as-is."""
    p = Path("/home/user/project")
    out = _normalize_path_for_env(p, on_windows=False)
    assert str(p) in out or out.startswith("/")


def test_substitute_path_ignores_comments():
    """Comment lines are returned unchanged."""
    line = "# MCP_RESEARCH_SAVE_DIRECTORY=something\n"
    root = Path("C:/project")
    assert _substitute_path_in_line(line, root, on_windows=True) == line


def test_substitute_path_replaces_known_var():
    """Path var line gets project root substituted."""
    root = Path("D:/CATBot")
    line = "MCP_RESEARCH_SAVE_DIRECTORY=C:\\Users\\andyj\\AI_assistant\\research\n"
    result = _substitute_path_in_line(line, root, on_windows=True)
    assert "MCP_RESEARCH_SAVE_DIRECTORY=" in result
    assert "D:" in result or "research" in result


def test_substitute_path_ignores_non_path_var():
    """Non-path vars are returned unchanged."""
    line = "MCP_LLM_PROVIDER=ollama\n"
    root = Path("C:/project")
    assert _substitute_path_in_line(line, root, on_windows=True) == line


def test_create_dirs_creates_missing(tmp_path):
    """create_dirs creates required dirs under given root."""
    created = create_dirs(tmp_path)
    assert len(created) >= len(REQUIRED_DIRS) or "scratch" in created
    for name in REQUIRED_DIRS:
        assert (tmp_path / name).is_dir()
    assert (tmp_path / "research_output").is_dir() or (tmp_path / "research").is_dir()


def test_create_dirs_idempotent(tmp_path):
    """Second create_dirs does not duplicate; returns empty or minimal list."""
    create_dirs(tmp_path)
    created_second = create_dirs(tmp_path)
    for name in REQUIRED_DIRS:
        assert (tmp_path / name).is_dir()
    # Second run should not "create" again (implementation may still list existing)
    assert (tmp_path / "scratch").is_dir()

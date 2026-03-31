"""Tests for scripts/start_mcp_browser_use_http_server.py."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from scripts import start_mcp_browser_use_http_server as launcher


def test_build_server_env_sets_repo_local_runtime_paths(monkeypatch):
    """Launcher env should pin uv/temp/download paths into the repo runtime dir."""
    scratch_root = Path.cwd() / "scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)
    tmp_path = scratch_root / f"test-browser-env-{next(tempfile._get_candidate_names())}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        monkeypatch.setattr(launcher, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(launcher, "RUNTIME_DIR", tmp_path / ".runtime")
        monkeypatch.setattr(launcher, "TEMP_DIR", tmp_path / ".runtime" / "tmp")
        monkeypatch.setattr(launcher, "UV_CACHE_DIR", tmp_path / ".runtime" / "uv-cache")
        monkeypatch.setattr(launcher, "BROWSER_DOWNLOADS_DIR", tmp_path / ".runtime" / "browser-use-downloads")

        env = launcher.build_server_env({"VIRTUAL_ENV": r"C:\parent\venv", "EXISTING": "1"})

        assert env["PYTHONUTF8"] == "1"
        assert env["PYTHONIOENCODING"] == "utf-8"
        assert env["UV_CACHE_DIR"] == str(tmp_path / ".runtime" / "uv-cache")
        assert env["TEMP"] == str(tmp_path / ".runtime" / "tmp")
        assert env["TMP"] == str(tmp_path / ".runtime" / "tmp")
        assert env["TMPDIR"] == str(tmp_path / ".runtime" / "tmp")
        assert env["MCP_BROWSER_DOWNLOADS_DIR"] == str(tmp_path / ".runtime" / "browser-use-downloads")
        assert env["CATBOT_BROWSER_USE_RUNTIME_DIR"] == str(tmp_path / ".runtime")
        assert env["CATBOT_PROJECT_ROOT"] == str(tmp_path)
        assert env["CATBOT_INSTALL_ROOT"] == str(tmp_path)
        assert "VIRTUAL_ENV" not in env
        assert (tmp_path / ".runtime" / "tmp").is_dir()
        assert (tmp_path / ".runtime" / "uv-cache").is_dir()
        assert (tmp_path / ".runtime" / "browser-use-downloads").is_dir()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_start_server_falls_back_when_uv_fails(monkeypatch, capsys):
    """Launcher should retry with the bundled venv when uv exits non-zero."""
    scratch_root = Path.cwd() / "scratch"
    scratch_root.mkdir(parents=True, exist_ok=True)
    tmp_path = scratch_root / f"test-browser-fallback-{next(tempfile._get_candidate_names())}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        monkeypatch.setattr(launcher, "PROJECT_ROOT", tmp_path)
        monkeypatch.setattr(launcher, "MCP_BROWSER_USE_DIR", tmp_path / "mcp-browser-use")
        monkeypatch.setattr(launcher, "RUNTIME_DIR", tmp_path / "mcp-browser-use" / ".runtime")
        monkeypatch.setattr(launcher, "TEMP_DIR", tmp_path / "mcp-browser-use" / ".runtime" / "tmp")
        monkeypatch.setattr(launcher, "UV_CACHE_DIR", tmp_path / "mcp-browser-use" / ".runtime" / "uv-cache")
        monkeypatch.setattr(
            launcher,
            "BROWSER_DOWNLOADS_DIR",
            tmp_path / "mcp-browser-use" / ".runtime" / "browser-use-downloads",
        )
        (tmp_path / "mcp-browser-use" / ".venv" / "Scripts").mkdir(parents=True)
        (tmp_path / "mcp-browser-use" / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")

        monkeypatch.setattr(launcher, "load_project_env", lambda _: None)

        calls: list[list[str]] = []

        def fake_run_command(command: list[str], env: dict[str, str]) -> int:
            calls.append(command)
            return 5 if command[:2] == ["uv", "run"] else 0

        monkeypatch.setattr(launcher, "run_command", fake_run_command)

        exit_code = launcher.start_server()
        captured = capsys.readouterr()

        assert exit_code == 0
        assert calls[0] == ["uv", "run", "mcp-server-browser-use", "server"]
        assert calls[1][0].endswith(str(Path(".venv") / "Scripts" / "python.exe"))
        assert "retrying with the bundled mcp-browser-use virtualenv" in captured.out
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)

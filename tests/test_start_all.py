"""Unit tests for scripts/start_all.py."""

import shutil
import tempfile
from pathlib import Path


def test_resolve_autogenstudio_command_prefers_env(monkeypatch):
    from scripts import start_all

    monkeypatch.setenv("AUTOGENSTUDIO_CMD", r"C:\studio\Scripts\autogenstudio.exe")
    monkeypatch.setattr(start_all.shutil, "which", lambda _: None)

    resolved = start_all._resolve_autogenstudio_command()

    assert resolved == r"C:\studio\Scripts\autogenstudio.exe"


def test_resolve_autogenstudio_command_uses_venv_executable(monkeypatch):
    from scripts import start_all

    root = Path.cwd() / f"setup-env-{next(tempfile._get_candidate_names())}"
    studio_exe = root / "venv" / "Scripts" / "autogenstudio.exe"
    studio_exe.parent.mkdir(parents=True, exist_ok=True)
    studio_exe.write_text("", encoding="utf-8")

    try:
        monkeypatch.delenv("AUTOGENSTUDIO_CMD", raising=False)
        monkeypatch.setattr(start_all, "PROJECT_ROOT", root)
        monkeypatch.setattr(start_all.shutil, "which", lambda _: None)

        resolved = start_all._resolve_autogenstudio_command()

        assert resolved == str(studio_exe)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_build_command_lines_skips_studio_when_unavailable():
    from scripts import start_all

    commands = start_all._build_command_lines(None)

    assert len(commands) == 6
    assert all("8084" not in command for command in commands)


def test_build_command_lines_includes_studio_when_available():
    from scripts import start_all

    commands = start_all._build_command_lines(r"C:\studio\Scripts\autogenstudio.exe")

    assert len(commands) == 7
    assert any("autogenstudio.exe" in command and "8084" in command for command in commands)

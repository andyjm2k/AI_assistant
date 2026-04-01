"""Unit tests for scripts/runtime_env.py."""

import shutil
import tempfile
from pathlib import Path


def test_resolve_venv_dir_prefers_explicit_python_over_inherited_virtual_env(monkeypatch):
    from scripts import runtime_env

    root = Path.cwd() / f"setup-env-{next(tempfile._get_candidate_names())}"
    project_venv = root / "venv" / "Scripts"
    inherited_venv = root / "inherited-venv" / "Scripts"
    explicit_venv = root / "custom-venv" / "Scripts"
    for scripts_dir in (project_venv, inherited_venv, explicit_venv):
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "python.exe").write_text("", encoding="utf-8")

    try:
        monkeypatch.setenv("VIRTUAL_ENV", str(inherited_venv.parent))

        resolved = runtime_env.resolve_venv_dir(root, str(explicit_venv / "python.exe"))

        assert resolved == explicit_venv.parent
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_build_script_env_replaces_inherited_virtual_env_with_resolved_python(monkeypatch):
    from scripts import runtime_env

    root = Path.cwd() / f"setup-env-{next(tempfile._get_candidate_names())}"
    inherited_venv = root / "inherited-venv" / "Scripts"
    explicit_venv = root / "custom-venv" / "Scripts"
    for scripts_dir in (inherited_venv, explicit_venv):
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "python.exe").write_text("", encoding="utf-8")

    try:
        monkeypatch.setenv("VIRTUAL_ENV", str(inherited_venv.parent))

        env = runtime_env.build_script_env(root, python_exe=str(explicit_venv / "python.exe"))

        assert env["CATBOT_VENV_PYTHON"] == str(explicit_venv / "python.exe")
        assert env["CATBOT_VENV_DIR"] == str(explicit_venv.parent)
        assert env["VIRTUAL_ENV"] == str(explicit_venv.parent)
        assert env["PYTHONUTF8"] == "1"
        assert env["PYTHONIOENCODING"] == "utf-8"
        assert env["PATH"].split(";")[0] == str(explicit_venv)
    finally:
        shutil.rmtree(root, ignore_errors=True)

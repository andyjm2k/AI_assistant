from types import SimpleNamespace
import secrets
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _scratch_env_dir():
    root = PROJECT_ROOT / "scratch" / f"optional-workflow-{secrets.token_hex(4)}"
    root.mkdir(parents=True, exist_ok=False)
    return root


def test_optional_workflow_installer_skips_default_autogen(monkeypatch):
    from scripts import install_optional_workflow_backend as installer

    root = _scratch_env_dir()
    try:
        env_file = root / ".env"
        env_file.write_text("WORKFLOW_FRAMEWORK=autogen\n", encoding="utf-8")
        monkeypatch.setattr(installer, "ENV_FILE", env_file)

        assert installer.main() == 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_optional_workflow_installer_installs_ag2_when_selected(monkeypatch):
    from scripts import install_optional_workflow_backend as installer

    root = _scratch_env_dir()
    try:
        env_file = root / ".env"
        env_file.write_text("WORKFLOW_FRAMEWORK=ag2\n", encoding="utf-8")
        calls = []
        availability = iter([(False, "missing"), (True, "AG2 import OK")])

        monkeypatch.setattr(installer, "ENV_FILE", env_file)
        monkeypatch.setattr(installer, "_ag2_available", lambda: next(availability))

        def fake_run(command, cwd=None):
            calls.append((command, cwd))
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(installer.subprocess, "run", fake_run)

        assert installer.main() == 0
        assert calls
        assert calls[0][0][-1] == "ag2[openai]"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_optional_workflow_installer_fails_when_ag2_install_fails(monkeypatch):
    from scripts import install_optional_workflow_backend as installer

    root = _scratch_env_dir()
    try:
        env_file = root / ".env"
        env_file.write_text("WORKFLOW_FRAMEWORK=ag2\n", encoding="utf-8")

        monkeypatch.setattr(installer, "ENV_FILE", env_file)
        monkeypatch.setattr(installer, "_ag2_available", lambda: (False, "missing"))
        monkeypatch.setattr(installer.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=7))

        assert installer.main() == 7
    finally:
        shutil.rmtree(root, ignore_errors=True)

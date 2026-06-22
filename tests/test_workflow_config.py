import pytest
import secrets
import shutil
from pathlib import Path


def _scratch_test_root() -> Path:
    root = Path.cwd() / "scratch" / f"workflow-config-test-{secrets.token_hex(4)}"
    root.mkdir(parents=True, exist_ok=False)
    return root


def test_workflow_framework_defaults_to_autogen():
    from src.workflows.config import get_workflow_framework

    assert get_workflow_framework({}) == "autogen"


def test_workflow_framework_accepts_allowed_values_case_insensitive():
    from src.workflows.config import get_workflow_framework

    assert get_workflow_framework({"WORKFLOW_FRAMEWORK": "AutoGen"}) == "autogen"
    assert get_workflow_framework({"WORKFLOW_FRAMEWORK": " AG2 "}) == "ag2"


def test_workflow_framework_reads_project_env_when_process_env_missing(monkeypatch):
    from src.workflows.config import get_workflow_framework

    root = _scratch_test_root()
    try:
        (root / ".env").write_text("WORKFLOW_FRAMEWORK=ag2\n", encoding="utf-8")
        monkeypatch.setenv("CATBOT_PROJECT_ROOT", str(root))
        monkeypatch.delenv("WORKFLOW_FRAMEWORK", raising=False)

        assert get_workflow_framework() == "ag2"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_workflow_framework_process_env_wins_over_project_env(monkeypatch):
    from src.workflows.config import get_workflow_framework

    root = _scratch_test_root()
    try:
        (root / ".env").write_text("WORKFLOW_FRAMEWORK=ag2\n", encoding="utf-8")
        monkeypatch.setenv("CATBOT_PROJECT_ROOT", str(root))
        monkeypatch.setenv("WORKFLOW_FRAMEWORK", "autogen")

        assert get_workflow_framework() == "autogen"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_workflow_framework_rejects_invalid_value():
    from src.workflows.config import WorkflowConfigError, get_workflow_framework

    with pytest.raises(WorkflowConfigError) as exc:
        get_workflow_framework({"WORKFLOW_FRAMEWORK": "crew"})
    assert "WORKFLOW_FRAMEWORK must be one of" in str(exc.value)

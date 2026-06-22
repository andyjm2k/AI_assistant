from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Optional


DEFAULT_WORKFLOW_FRAMEWORK = "autogen"
WORKFLOW_FRAMEWORKS = {"autogen", "ag2"}


class WorkflowConfigError(ValueError):
    """Raised when workflow backend configuration is invalid."""


def normalize_workflow_framework(value: Optional[str]) -> str:
    framework = (value or DEFAULT_WORKFLOW_FRAMEWORK).strip().lower()
    if not framework:
        framework = DEFAULT_WORKFLOW_FRAMEWORK
    if framework not in WORKFLOW_FRAMEWORKS:
        allowed = ", ".join(sorted(WORKFLOW_FRAMEWORKS))
        raise WorkflowConfigError(
            f"WORKFLOW_FRAMEWORK must be one of: {allowed}. Current value: {value!r}"
        )
    return framework


def _project_root() -> Path:
    for name in ("CATBOT_PROJECT_ROOT", "CATBOT_INSTALL_ROOT", "CATBOT_WORKSPACE"):
        raw = os.environ.get(name)
        if not raw:
            continue
        try:
            candidate = Path(raw).expanduser().resolve()
        except OSError:
            continue
        if (candidate / ".env").exists() or (candidate / "scripts").is_dir():
            return candidate
    return Path(__file__).resolve().parents[2]


def _read_workflow_framework_from_dotenv() -> Optional[str]:
    env_path = _project_root() / ".env"
    if not env_path.exists():
        return None
    try:
        lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    value: Optional[str] = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, raw_value = stripped.partition("=")
        if key.strip() == "WORKFLOW_FRAMEWORK":
            value = raw_value.strip().strip('"').strip("'")
    return value


def get_workflow_framework(env: Optional[Mapping[str, str]] = None) -> str:
    if env is not None:
        return normalize_workflow_framework(env.get("WORKFLOW_FRAMEWORK"))
    return normalize_workflow_framework(
        os.environ.get("WORKFLOW_FRAMEWORK") or _read_workflow_framework_from_dotenv()
    )

from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT_ROOT = SCRIPT_DIR.parent


def resolve_project_root() -> Path:
    """Resolve the CATBot install root from env overrides or this script location."""
    candidates = (
        os.environ.get("CATBOT_PROJECT_ROOT"),
        os.environ.get("CATBOT_INSTALL_ROOT"),
        os.environ.get("CATBOT_WORKSPACE"),
    )
    for raw in candidates:
        if not raw:
            continue
        candidate = Path(raw).expanduser().resolve()
        if (candidate / "scripts").is_dir():
            return candidate
    return DEFAULT_PROJECT_ROOT


def _venv_python_from_dir(venv_dir: Path) -> Path | None:
    for candidate in (venv_dir / "Scripts" / "python.exe", venv_dir / "bin" / "python"):
        if candidate.exists():
            return candidate
    return None


def _coerce_existing_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    try:
        candidate = Path(raw).expanduser().resolve()
    except OSError:
        return None
    if candidate.exists():
        return candidate
    return None


def resolve_venv_python(project_root: Path | None = None, base_env: dict[str, str] | None = None) -> str:
    """Resolve the preferred Python executable for CATBot scripts."""
    root = (project_root or resolve_project_root()).resolve()
    env = base_env or os.environ

    configured_python = _coerce_existing_path(env.get("CATBOT_VENV_PYTHON"))
    if configured_python:
        return str(configured_python)

    configured_venv = _coerce_existing_path(env.get("CATBOT_VENV_DIR") or env.get("VIRTUAL_ENV"))
    if configured_venv:
        venv_python = _venv_python_from_dir(configured_venv)
        if venv_python:
            return str(venv_python)

    current_python = _coerce_existing_path(sys.executable)
    if current_python and (sys.prefix != getattr(sys, "base_prefix", sys.prefix) or root in current_python.parents):
        return str(current_python)

    project_venv_python = _venv_python_from_dir(root / "venv")
    if project_venv_python:
        return str(project_venv_python)

    return "python"


def resolve_venv_dir(
    project_root: Path | None = None,
    python_exe: str | None = None,
    base_env: dict[str, str] | None = None,
) -> Path | None:
    """Resolve the active CATBot virtualenv directory when available."""
    root = (project_root or resolve_project_root()).resolve()
    env = base_env or os.environ

    python_path = _coerce_existing_path(python_exe or resolve_venv_python(root, env))
    if python_path:
        parent = python_path.parent
        if parent.name.lower() in {"scripts", "bin"}:
            return parent.parent

    for raw in (env.get("CATBOT_VENV_DIR"), env.get("VIRTUAL_ENV")):
        candidate = _coerce_existing_path(raw)
        if candidate and _venv_python_from_dir(candidate):
            return candidate

    project_venv = root / "venv"
    if _venv_python_from_dir(project_venv):
        return project_venv
    return None


def _prepend_env_path(existing: str | None, value: str) -> str:
    parts = [part for part in (value, *(existing or "").split(os.pathsep)) if part]
    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        normalized = os.path.normcase(os.path.normpath(part))
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(part)
    return os.pathsep.join(deduped)


def build_script_env(
    project_root: Path | None = None,
    base_env: dict[str, str] | None = None,
    python_exe: str | None = None,
    *,
    include_venv: bool = True,
) -> dict[str, str]:
    """Build a child-process environment with the resolved install root and script Python context."""
    root = (project_root or resolve_project_root()).resolve()
    env = dict(base_env or os.environ)
    resolved_python = python_exe or resolve_venv_python(root, env)
    resolved_venv_dir = resolve_venv_dir(root, resolved_python, {"CATBOT_VENV_PYTHON": resolved_python})

    env["CATBOT_PROJECT_ROOT"] = str(root)
    env["CATBOT_INSTALL_ROOT"] = str(root)
    env["CATBOT_WORKSPACE"] = str(root)
    env["CATBOT_VENV_PYTHON"] = resolved_python
    env["PYTHONPATH"] = _prepend_env_path(env.get("PYTHONPATH"), str(root))
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    if include_venv and resolved_venv_dir:
        env["CATBOT_VENV_DIR"] = str(resolved_venv_dir)
        env["VIRTUAL_ENV"] = str(resolved_venv_dir)
        scripts_dir = resolved_venv_dir / ("Scripts" if os.name == "nt" else "bin")
        if scripts_dir.exists():
            env["PATH"] = _prepend_env_path(env.get("PATH"), str(scripts_dir))

    return env

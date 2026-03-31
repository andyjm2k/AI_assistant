"""
Start all CATBot services in separate command windows.
Run from project root. Uses dynamic paths based on script location.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Project root = parent of scripts directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.runtime_env import build_script_env, resolve_project_root, resolve_venv_dir, resolve_venv_python

PROJECT_ROOT = resolve_project_root()


def _resolve_venv_python() -> str:
    return resolve_venv_python(PROJECT_ROOT)


VENV_PYTHON = _resolve_venv_python()


def _resolve_autogenstudio_command() -> str | None:
    configured = os.getenv("AUTOGENSTUDIO_CMD", "").strip()
    if configured:
        return configured

    venv_dir = resolve_venv_dir(PROJECT_ROOT, VENV_PYTHON)
    if venv_dir:
        venv_studio = venv_dir / "Scripts" / "autogenstudio.exe"
        if venv_studio.exists():
            return str(venv_studio)

    return shutil.which("autogenstudio")


def _build_child_env() -> dict[str, str]:
    return build_script_env(PROJECT_ROOT, python_exe=VENV_PYTHON)


def _launch_in_new_cmd(command_line: str, env: dict[str, str] | None = None) -> None:
    subprocess.Popen(
        ["cmd", "/c", "start", "", "cmd", "/k", command_line],
        cwd=str(PROJECT_ROOT),
        env=env or _build_child_env(),
    )


def _build_command_lines(studio_command: str | None) -> list[str]:
    commands = [
        f'cd /d "{PROJECT_ROOT}" && "{VENV_PYTHON}" -m src.servers.https_server',
        f'cd /d "{PROJECT_ROOT}" && "{VENV_PYTHON}" -m src.servers.proxy_server',
        f'cd /d "{PROJECT_ROOT}" && "{VENV_PYTHON}" -m src.servers.scheduled_task_poller',
        f'cd /d "{PROJECT_ROOT}" && "{VENV_PYTHON}" scripts/start_mcp_browser_use_http_server.py',
        f'cd /d "{PROJECT_ROOT}" && "{VENV_PYTHON}" scripts/start_mcp_browser_server.py',
        f'cd /d "{PROJECT_ROOT}" && "{VENV_PYTHON}" -m src.integrations.telegram_bot',
    ]
    if studio_command:
        commands.insert(
            3,
            f'cd /d "{PROJECT_ROOT}" && "{studio_command}" serve --team config/team-config.json --host 0.0.0.0 --port 8084',
        )
    return commands


def main() -> int:
    # Keep AutoGen Studio's JSON input in sync with the Python source of truth.
    child_env = _build_child_env()
    subprocess.run(
        [VENV_PYTHON, str(PROJECT_ROOT / "scripts" / "export_autogen_team_config.py")],
        cwd=str(PROJECT_ROOT),
        check=False,
        env=child_env,
    )

    studio_command = _resolve_autogenstudio_command()
    if not studio_command:
        print("AutoGen Studio not installed; skipping Studio UI on port 8084.")

    for command_line in _build_command_lines(studio_command):
        _launch_in_new_cmd(command_line, env=child_env)

    print("All processes have been started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

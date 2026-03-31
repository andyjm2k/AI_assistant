"""
Start all CATBot services in separate command windows.
Run from project root. Uses dynamic paths based on script location.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

# Project root = parent of scripts directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_venv_python() -> str:
    venv_python = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python)
    return "python"


VENV_PYTHON = _resolve_venv_python()


def _resolve_autogenstudio_command() -> str | None:
    configured = os.getenv("AUTOGENSTUDIO_CMD", "").strip()
    if configured:
        return configured

    venv_studio = PROJECT_ROOT / "venv" / "Scripts" / "autogenstudio.exe"
    if venv_studio.exists():
        return str(venv_studio)

    return shutil.which("autogenstudio")


def _launch_in_new_cmd(command_line: str) -> None:
    subprocess.Popen(
        ["cmd", "/c", "start", "", "cmd", "/k", command_line],
        cwd=str(PROJECT_ROOT),
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
    subprocess.run(
        [VENV_PYTHON, str(PROJECT_ROOT / "scripts" / "export_autogen_team_config.py")],
        cwd=str(PROJECT_ROOT),
        check=False,
    )

    studio_command = _resolve_autogenstudio_command()
    if not studio_command:
        print("AutoGen Studio not installed; skipping Studio UI on port 8084.")

    for command_line in _build_command_lines(studio_command):
        _launch_in_new_cmd(command_line)

    print("All processes have been started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

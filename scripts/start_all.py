"""
Start all CATBot services in separate command windows.
Run from project root. Uses dynamic paths based on script location.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Project root = parent of scripts directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.runtime_env import build_script_env, resolve_project_root, resolve_venv_dir, resolve_venv_python
from scripts.verify_install import check_workflow_backend

PROJECT_ROOT = resolve_project_root()
BASE_REQUIRED_PORTS = {8000, 8002, 5001, 8383}
STUDIO_PORT = 8084
STARTUP_VERIFY_TIMEOUT_SECONDS = 20.0


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


def _check_selected_workflow_backend() -> tuple[bool, str]:
    return check_workflow_backend(VENV_PYTHON)


def _launch_in_new_cmd(
    command: list[str],
    env: dict[str, str] | None = None,
    *,
    new_console: bool = True,
):
    creationflags = (
        getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        if new_console and os.name == "nt"
        else 0
    )
    return subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
        env=env or _build_child_env(),
        creationflags=creationflags,
    )


def _build_launch_specs(studio_command: str | None) -> list[tuple[str, list[str], bool]]:
    commands = [
        ([VENV_PYTHON, "-m", "src.servers.https_server"], True),
        ([VENV_PYTHON, "-m", "src.servers.proxy_server"], True),
        ([VENV_PYTHON, "-m", "src.servers.scheduled_task_poller"], True),
        ([VENV_PYTHON, "scripts/start_mcp_browser_use_http_server.py"], True),
        ([VENV_PYTHON, "scripts/start_mcp_browser_server.py"], True),
        ([VENV_PYTHON, "-m", "src.integrations.telegram_bot"], False),
    ]
    if studio_command:
        commands.insert(
            3,
            ([studio_command, "serve", "--team", "config/team-config.json", "--host", "0.0.0.0", "--port", "8084"], True),
        )
    return [
        (f'cd /d "{PROJECT_ROOT}" && {subprocess.list2cmdline(command)}', command, required)
        for command, required in commands
    ]


def _build_command_lines(studio_command: str | None) -> list[str]:
    return [display for display, _, _ in _build_launch_specs(studio_command)]


def _required_ports(studio_command: str | None) -> set[int]:
    ports = set(BASE_REQUIRED_PORTS)
    if studio_command:
        ports.add(STUDIO_PORT)
    return ports


def _listening_ports(ports: set[int]) -> set[int]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return set()

    listening: set[int] = set()
    line_pattern = re.compile(r"^\s*TCP\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s*$", re.IGNORECASE)
    for line in (result.stdout or "").splitlines():
        match = line_pattern.match(line)
        if not match or match.group(3).upper() != "LISTENING":
            continue
        try:
            local_port = int(match.group(1).rsplit(":", 1)[-1])
        except ValueError:
            continue
        if local_port in ports:
            listening.add(local_port)
    return listening


def _wait_for_required_ports(ports: set[int], timeout_seconds: float = STARTUP_VERIFY_TIMEOUT_SECONDS) -> set[int]:
    deadline = time.time() + timeout_seconds
    last_seen: set[int] = set()
    while time.time() < deadline:
        last_seen = _listening_ports(ports)
        missing = ports - last_seen
        if not missing:
            return set()
        time.sleep(1.0)
    return ports - last_seen


def main() -> int:
    workflow_ok, workflow_message = _check_selected_workflow_backend()
    if not workflow_ok:
        print("Selected workflow backend check failed:")
        print(f"  {workflow_message}")
        return 1
    print(f"Selected workflow backend OK: {workflow_message}")

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

    launched = []
    for display_command, command, required in _build_launch_specs(studio_command):
        launched.append((display_command, command, required, _launch_in_new_cmd(command, env=child_env)))

    time.sleep(2.0)
    relaunched = []
    for display_command, command, required, proc in launched:
        if proc.poll() is None:
            relaunched.append((display_command, required, proc))
            continue
        relaunched.append(
            (display_command, required, _launch_in_new_cmd(command, env=child_env, new_console=False))
        )

    time.sleep(2.0)
    failed = [command_line for command_line, required, proc in relaunched if required and proc.poll() is not None]
    optional_failed = [command_line for command_line, required, proc in relaunched if not required and proc.poll() is not None]
    if failed:
        print("One or more services exited immediately after launch:")
        for command_line in failed:
            print(f"  {command_line}")
        return 1

    missing_ports = _wait_for_required_ports(_required_ports(studio_command))
    if missing_ports:
        print(f"Timed out waiting for service ports: {sorted(missing_ports)}")
        return 1

    if optional_failed:
        print("Optional services that did not stay running:")
        for command_line in optional_failed:
            print(f"  {command_line}")

    print("All processes have been started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

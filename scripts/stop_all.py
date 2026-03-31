"""
Stop only CATBot services started by scripts/start_all.py.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set

# Project root = parent of scripts directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.runtime_env import resolve_project_root, resolve_venv_python

PROJECT_ROOT = resolve_project_root()
PROJECT_ROOT_STR = str(PROJECT_ROOT).lower()

# Signatures for commands launched by start_all.py
SERVICE_SIGNATURES = [
    "src.servers.https_server",
    "src.servers.proxy_server",
    "src.servers.scheduled_task_poller",
    "src.integrations.telegram_bot",
    "scripts/start_mcp_browser_use_http_server.py",
    "scripts\\start_mcp_browser_use_http_server.py",
    "scripts/start_mcp_browser_server.py",
    "scripts\\start_mcp_browser_server.py",
    "autogenstudio serve --team config/team-config.json",
    # Child process launched by start_mcp_browser_use_http_server.py
    "mcp-server-browser-use server",
]

# Known CATBot service ports used by start_all.py services.
SERVICE_PORTS = {8000, 8002, 5001, 8084, 8383}


def _run_powershell(script: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"PowerShell command failed (exit {result.returncode}): {stderr}")
    return (result.stdout or "").strip()


def _load_processes_with_cim() -> Dict[int, Dict[str, object]]:
    """Return process table keyed by PID from Win32_Process via PowerShell."""
    ps_script = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine | "
        "ConvertTo-Json -Depth 3"
    )
    raw = _run_powershell(ps_script)
    if not raw:
        return {}

    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed = [parsed]

    table: Dict[int, Dict[str, object]] = {}
    for proc in parsed:
        try:
            pid = int(proc.get("ProcessId"))
        except (TypeError, ValueError):
            continue
        table[pid] = {
            "parent": int(proc.get("ParentProcessId") or 0),
            "name": str(proc.get("Name") or ""),
            "cmd": str(proc.get("CommandLine") or ""),
        }
    return table


def _load_processes_with_get_process() -> Dict[int, Dict[str, object]]:
    """Fallback process table from Get-Process when CIM command-lines are unavailable."""
    ps_script = (
        "Get-Process | "
        "Select-Object Id,ProcessName,Path,MainWindowTitle | "
        "ConvertTo-Json -Depth 3"
    )
    raw = _run_powershell(ps_script)
    if not raw:
        return {}

    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed = [parsed]

    table: Dict[int, Dict[str, object]] = {}
    for proc in parsed:
        try:
            pid = int(proc.get("Id"))
        except (TypeError, ValueError):
            continue

        name = str(proc.get("ProcessName") or "")
        path = str(proc.get("Path") or "")
        title = str(proc.get("MainWindowTitle") or "")
        synthetic_cmd = f"{path} {title}".strip()

        table[pid] = {
            "parent": 0,  # Parent PID not available via this fallback
            "name": name,
            "cmd": synthetic_cmd,
            "path": path,
            "title": title,
        }
    return table


def _matches_service_command(command_line: str) -> bool:
    cmd = command_line.lower()
    if not cmd:
        return False

    in_project = PROJECT_ROOT_STR in cmd
    has_signature = any(signature in cmd for signature in SERVICE_SIGNATURES)

    # Require both project path and known command signature for safety,
    # except mcp-server-browser-use child process where project path may be absent.
    if "mcp-server-browser-use server" in cmd:
        return True
    return in_project and has_signature


def _collect_target_pids(processes: Dict[int, Dict[str, object]]) -> Set[int]:
    matched: Set[int] = set()
    for pid, proc in processes.items():
        cmd = str(proc.get("cmd") or "")
        if _matches_service_command(cmd):
            matched.add(pid)
    return matched


def _listening_pids_for_ports(ports: Set[int]) -> Set[int]:
    """Return process IDs listening on any of the provided TCP ports."""
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return set()

    matched: Set[int] = set()
    line_pattern = re.compile(r"^\s*TCP\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s*$", re.IGNORECASE)
    for line in (result.stdout or "").splitlines():
        m = line_pattern.match(line)
        if not m:
            continue
        local_address = m.group(1)
        state = m.group(3).upper()
        pid_text = m.group(4)
        if state != "LISTENING":
            continue

        # IPv4 and IPv6 forms are both handled by splitting on the final colon.
        try:
            local_port = int(local_address.rsplit(":", 1)[-1])
            pid = int(pid_text)
        except ValueError:
            continue

        if local_port in ports:
            matched.add(pid)
    return matched


def _collect_target_pids_fallback(processes: Dict[int, Dict[str, object]]) -> Set[int]:
    """
    Fallback targeting when full command lines are unavailable.

    Uses known service ports plus lightweight process metadata to catch
    CATBot services with minimal overreach.
    """
    matched: Set[int] = set()
    for pid in _listening_pids_for_ports(SERVICE_PORTS):
        proc = processes.get(pid, {})
        name = str(proc.get("name") or "").lower()
        path = str(proc.get("path") or "").lower()
        cmd = str(proc.get("cmd") or "").lower()
        if PROJECT_ROOT_STR in path or PROJECT_ROOT_STR in cmd or name in {"autogenstudio", "autogenstudio.exe"}:
            matched.add(pid)

    current_pid = os.getpid()
    venv_python = resolve_venv_python(PROJECT_ROOT).lower()

    for pid, proc in processes.items():
        name = str(proc.get("name") or "").lower()
        cmd = str(proc.get("cmd") or "")
        path = str(proc.get("path") or "").lower()

        if _matches_service_command(cmd):
            matched.add(pid)
            continue

        if name in {"autogenstudio", "autogenstudio.exe"}:
            matched.add(pid)
            continue

        # When the service stack is active, also stop python processes using this
        # project's venv interpreter to capture non-port services like poller/bot.
        if matched and pid != current_pid and name.startswith("python") and path == venv_python:
            matched.add(pid)

    return matched


def _root_targets(target_pids: Set[int], processes: Dict[int, Dict[str, object]]) -> List[int]:
    """Return target PIDs that do not have another target ancestor."""

    def has_target_ancestor(pid: int) -> bool:
        seen: Set[int] = set()
        current = int(processes.get(pid, {}).get("parent") or 0)
        while current and current not in seen:
            if current in target_pids:
                return True
            seen.add(current)
            current = int(processes.get(current, {}).get("parent") or 0)
        return False

    return sorted(pid for pid in target_pids if not has_target_ancestor(pid))


def _kill_process_tree(pid: int) -> bool:
    result = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _format_killed(pids: Iterable[int]) -> str:
    values = sorted(set(int(pid) for pid in pids))
    return ", ".join(str(pid) for pid in values)


def main() -> int:
    if sys.platform != "win32":
        print("stop_all.py currently supports Windows only.")
        return 1

    fallback_used = False
    try:
        processes = _load_processes_with_cim()
        target_pids = _collect_target_pids(processes)
    except Exception as cim_error:
        fallback_used = True
        try:
            processes = _load_processes_with_get_process()
            target_pids = _collect_target_pids_fallback(processes)
            print(f"Warning: limited process query mode enabled ({cim_error}).")
        except Exception as fallback_error:
            print(f"Error querying running processes: {fallback_error}")
            return 1

    if not target_pids:
        mode = " (fallback mode)" if fallback_used else ""
        print(f"No CATBot service processes found{mode}.")
        return 0

    roots = _root_targets(target_pids, processes)
    killed: List[int] = []

    for pid in roots:
        if _kill_process_tree(pid):
            killed.append(pid)

    if not killed:
        print("Found CATBot service processes, but failed to stop them.")
        return 1

    print(f"Stopped CATBot service process tree(s): {_format_killed(killed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
Restart CATBot services with retries and health verification.

Workflow:
1) Stop services using scripts/stop_all.py logic
2) Verify services are stopped
3) Start services using scripts/start_all.py
4) Verify services are healthy (proxy /monitor/summary + required ports + MCP health)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Set, Tuple
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.runtime_env import build_script_env, resolve_project_root, resolve_venv_dir, resolve_venv_python
from scripts.verify_install import check_workflow_backend

PROJECT_ROOT = resolve_project_root()
SCRIPTS_DIR = Path(__file__).resolve().parent
START_ALL_SCRIPT = SCRIPTS_DIR / "start_all.py"
VENV_PYTHON = resolve_venv_python(PROJECT_ROOT)

# Services started by scripts/start_all.py that expose ports.
BASE_REQUIRED_PORTS = {8000, 8002, 5001, 8383}
STUDIO_PORT = 8084
BASE_REQUIRED_SERVICE_SIGNATURES: Dict[str, Set[str]] = {
    "https_server": {"src.servers.https_server"},
    "proxy_server": {"src.servers.proxy_server"},
    "scheduled_task_poller": {"src.servers.scheduled_task_poller"},
    "telegram_bot": {"src.integrations.telegram_bot"},
    "mcp_browser_use_http_server": {
        "scripts/start_mcp_browser_use_http_server.py",
        "mcp-server-browser-use server",
        "mcp_server_browser_use.cli server",
    },
    "mcp_browser_server": {"scripts/start_mcp_browser_server.py"},
}
STUDIO_SERVICE_KEY = "autogen_studio"
STUDIO_SERVICE_SIGNATURES = {
    "serve --team config/team-config.json --host 0.0.0.0 --port 8084",
    "serve --team config/team-config.json",
}

STOP_VERIFY_TIMEOUT_SECONDS = 45.0
START_VERIFY_TIMEOUT_SECONDS = 120.0
START_ALL_LAUNCH_TIMEOUT_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 1.5

DEFAULT_STOP_ATTEMPTS = 3
DEFAULT_START_ATTEMPTS = 3

PROXY_MONITOR_SUMMARY_URLS = (
    "https://127.0.0.1:8002/monitor/summary",
    "http://127.0.0.1:8002/monitor/summary",
    "https://localhost:8002/monitor/summary",
    "http://localhost:8002/monitor/summary",
)
MCP_BROWSER_HEALTH_URLS = (
    "http://127.0.0.1:5001/api/health",
    "http://localhost:5001/api/health",
)


def _studio_available() -> bool:
    configured = (os.getenv("AUTOGENSTUDIO_CMD") or "").strip()
    if configured:
        return True

    venv_dir = resolve_venv_dir(PROJECT_ROOT, VENV_PYTHON)
    if venv_dir:
        venv_studio = venv_dir / "Scripts" / "autogenstudio.exe"
        if venv_studio.exists():
            return True

    return shutil.which("autogenstudio") is not None


def _check_selected_workflow_backend() -> Tuple[bool, str]:
    return check_workflow_backend(VENV_PYTHON)


def _required_ports() -> Set[int]:
    ports = set(BASE_REQUIRED_PORTS)
    if _studio_available():
        ports.add(STUDIO_PORT)
    return ports


def _required_service_signatures() -> Dict[str, Set[str]]:
    signatures = {
        service_name: set(service_signatures)
        for service_name, service_signatures in BASE_REQUIRED_SERVICE_SIGNATURES.items()
    }
    if _studio_available():
        signatures[STUDIO_SERVICE_KEY] = set(STUDIO_SERVICE_SIGNATURES)
    return signatures


def _log(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [restart_all] {message}", flush=True)


def _send_telegram_message(chat_id: Optional[str], text: str) -> None:
    if not chat_id:
        return
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        _log("TELEGRAM_BOT_TOKEN not set; skipping Telegram notification.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urlparse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    request = urlrequest.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(request, timeout=12) as response:
            response.read()
    except Exception as exc:
        _log(f"Failed to send Telegram notification: {exc}")


def _load_json_url(url: str, timeout_seconds: float = 4.0) -> Optional[dict]:
    request = urlrequest.Request(url, method="GET")
    context = None
    if url.startswith("https://"):
        context = ssl._create_unverified_context()
    try:
        with urlrequest.urlopen(request, timeout=timeout_seconds, context=context) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except (urlerror.URLError, TimeoutError, ValueError, OSError):
        return None


def _proxy_monitor_summary_ok() -> bool:
    for url in PROXY_MONITOR_SUMMARY_URLS:
        payload = _load_json_url(url)
        if isinstance(payload, dict) and "uptime_seconds" in payload:
            return True
    return False


def _mcp_browser_health_ok() -> bool:
    for url in MCP_BROWSER_HEALTH_URLS:
        payload = _load_json_url(url)
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status") or "").strip().lower()
        if status == "healthy":
            return True
    return False


def _listening_pids_by_port(ports: Set[int]) -> Dict[int, Set[int]]:
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {}

    by_port: Dict[int, Set[int]] = {port: set() for port in ports}
    line_pattern = re.compile(r"^\s*TCP\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s*$", re.IGNORECASE)
    for line in (result.stdout or "").splitlines():
        match = line_pattern.match(line)
        if not match:
            continue
        local_address = match.group(1)
        state = match.group(3).upper()
        pid_text = match.group(4)
        if state != "LISTENING":
            continue
        try:
            local_port = int(local_address.rsplit(":", 1)[-1])
            pid = int(pid_text)
        except ValueError:
            continue
        if local_port in by_port:
            by_port[local_port].add(pid)

    return {port: pids for port, pids in by_port.items() if pids}


def _force_kill_pids(pids: Set[int]) -> None:
    for pid in sorted(pids):
        if pid <= 0 or pid == os.getpid():
            continue
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
        )


def _wait_for_ports_down(timeout_seconds: float, required_ports: Set[int]) -> Tuple[bool, Dict[int, Set[int]]]:
    deadline = time.time() + timeout_seconds
    last_seen: Dict[int, Set[int]] = {}
    while time.time() < deadline:
        listening = _listening_pids_by_port(required_ports)
        if not listening:
            return True, listening
        last_seen = listening
        time.sleep(POLL_INTERVAL_SECONDS)
    return False, last_seen


def _wait_for_started_health(timeout_seconds: float, required_ports: Set[int]) -> Tuple[bool, str]:
    deadline = time.time() + timeout_seconds
    last_ports: Dict[int, Set[int]] = {}
    while time.time() < deadline:
        listening = _listening_pids_by_port(required_ports)
        last_ports = listening
        all_ports_up = required_ports.issubset(set(listening.keys()))
        proxy_ok = _proxy_monitor_summary_ok()
        mcp_ok = _mcp_browser_health_ok()
        if all_ports_up and proxy_ok and mcp_ok:
            return True, "all required checks passed"
        time.sleep(POLL_INTERVAL_SECONDS)

    missing_ports = sorted(required_ports - set(last_ports.keys()))
    details = []
    if missing_ports:
        details.append(f"missing ports: {missing_ports}")
    if not _proxy_monitor_summary_ok():
        details.append("proxy /monitor/summary unavailable")
    if not _mcp_browser_health_ok():
        details.append("mcp browser health check failed")
    if not details:
        details.append("startup verification timed out")
    return False, "; ".join(details)


def _run_start_all() -> Tuple[bool, str]:
    # Do not capture stdout/stderr here: start_all.py spawns long-lived child
    # console processes that may inherit pipe handles and prevent EOF.
    try:
        result = subprocess.run(
            [VENV_PYTHON, str(START_ALL_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            check=False,
            timeout=START_ALL_LAUNCH_TIMEOUT_SECONDS,
            env=build_script_env(PROJECT_ROOT, python_exe=VENV_PYTHON),
        )
        return result.returncode == 0, f"start_all rc={result.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"start_all launch timed out after {START_ALL_LAUNCH_TIMEOUT_SECONDS:.0f}s"


def _load_stop_all_module():
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    import stop_all  # type: ignore

    return stop_all


def _get_service_signature_hits(
    stop_all_module,
    required_service_signatures: Dict[str, Set[str]],
) -> Optional[Set[str]]:
    """
    Return matching service signatures found in process command lines.

    Returns None when command-line process inspection is unavailable.
    """
    try:
        processes = stop_all_module._load_processes_with_cim()
    except Exception:
        return None

    hits: Set[str] = set()
    for proc in processes.values():
        cmd = str(proc.get("cmd") or "").lower()
        if not cmd:
            continue
        normalized_cmd = re.sub(r"\s+", " ", cmd.replace("\\", "/")).strip()
        for service_name, signature_variants in required_service_signatures.items():
            if any(signature in normalized_cmd for signature in signature_variants):
                hits.add(service_name)
    return hits


def _stop_with_retries(
    stop_all_module,
    max_attempts: int,
    required_ports: Set[int],
    required_service_signatures: Dict[str, Set[str]],
) -> Tuple[bool, str]:
    for attempt in range(1, max_attempts + 1):
        _log(f"Stop attempt {attempt}/{max_attempts}")
        stop_rc = int(stop_all_module.main())
        stopped, remaining = _wait_for_ports_down(STOP_VERIFY_TIMEOUT_SECONDS, required_ports)
        signature_hits = _get_service_signature_hits(stop_all_module, required_service_signatures)
        signatures_stopped = signature_hits is None or len(signature_hits) == 0
        if stopped:
            if signatures_stopped:
                return True, f"stopped successfully (stop_all rc={stop_rc})"
            _log(f"Service signatures still detected after stop: {sorted(signature_hits)}")

        remaining_pids: Set[int] = set()
        for pids in remaining.values():
            remaining_pids.update(pids)
        if remaining_pids:
            _log(f"Self-heal: force-killing remaining listener PIDs: {sorted(remaining_pids)}")
            _force_kill_pids(remaining_pids)
            stopped_after_force, _ = _wait_for_ports_down(15.0, required_ports)
            signature_hits_after_force = _get_service_signature_hits(
                stop_all_module,
                required_service_signatures,
            )
            signatures_stopped_after_force = (
                signature_hits_after_force is None or len(signature_hits_after_force) == 0
            )
            if stopped_after_force and signatures_stopped_after_force:
                return True, f"stopped after forced cleanup (stop_all rc={stop_rc})"

        _log("Stop verification failed; retrying.")

    final_remaining = _listening_pids_by_port(required_ports)
    return False, f"ports still listening after retries: {final_remaining}"


def _start_with_retries(
    stop_all_module,
    max_attempts: int,
    required_ports: Set[int],
    required_service_signatures: Dict[str, Set[str]],
) -> Tuple[bool, str]:
    for attempt in range(1, max_attempts + 1):
        _log(f"Start attempt {attempt}/{max_attempts}")
        start_ok, start_output = _run_start_all()
        if not start_ok:
            _log(f"start_all.py exited non-zero. Output: {start_output or '(none)'}")

        healthy, detail = _wait_for_started_health(START_VERIFY_TIMEOUT_SECONDS, required_ports)
        signature_hits = _get_service_signature_hits(stop_all_module, required_service_signatures)
        signatures_ok = (
            signature_hits is None or set(required_service_signatures).issubset(signature_hits)
        )
        if healthy and signatures_ok:
            return True, "startup verification passed"
        if healthy and not signatures_ok:
            _log(
                "Health endpoints are up, but not all service signatures are visible yet: "
                f"{sorted(signature_hits or set())}"
            )

        _log(f"Startup verification failed: {detail}")
        if attempt < max_attempts:
            _log("Self-heal: stopping partially started services before retry.")
            _stop_with_retries(
                stop_all_module,
                max_attempts=1,
                required_ports=required_ports,
                required_service_signatures=required_service_signatures,
            )

    return False, "services failed to become healthy after retries"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restart CATBot services robustly.")
    parser.add_argument("--chat-id", help="Telegram chat ID for status notifications.")
    parser.add_argument("--requested-by", help="Telegram user ID that requested restart.")
    parser.add_argument("--stop-attempts", type=int, default=DEFAULT_STOP_ATTEMPTS)
    parser.add_argument("--start-attempts", type=int, default=DEFAULT_START_ATTEMPTS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if sys.platform != "win32":
        _log("This restart workflow currently supports Windows only.")
        return 1
    if not START_ALL_SCRIPT.exists():
        _log(f"Missing start script: {START_ALL_SCRIPT}")
        return 1

    chat_id = (args.chat_id or "").strip() or None
    requested_by = (args.requested_by or "").strip() or "unknown"
    stop_attempts = max(1, int(args.stop_attempts))
    start_attempts = max(1, int(args.start_attempts))
    required_ports = _required_ports()
    required_service_signatures = _required_service_signatures()

    _log(f"Restart requested by telegram user {requested_by}")
    if STUDIO_PORT not in required_ports:
        _log("AutoGen Studio not installed; restart health checks will skip port 8084.")

    workflow_ok, workflow_message = _check_selected_workflow_backend()
    if not workflow_ok:
        message = f"Restart failed before stop phase: selected workflow backend is not usable ({workflow_message})"
        _log(message)
        _send_telegram_message(chat_id, message)
        return 1
    _log(f"Selected workflow backend OK: {workflow_message}")

    _send_telegram_message(chat_id, "Restart requested. Stopping CATBot services now.")

    try:
        stop_all_module = _load_stop_all_module()
    except Exception as exc:
        message = f"Restart failed: could not load stop_all.py ({exc})"
        _log(message)
        _send_telegram_message(chat_id, message)
        return 1

    stopped, stop_detail = _stop_with_retries(
        stop_all_module,
        stop_attempts,
        required_ports,
        required_service_signatures,
    )
    if not stopped:
        message = f"Restart failed during stop phase: {stop_detail}"
        _log(message)
        _send_telegram_message(chat_id, message)
        return 1

    _log(f"Stop phase complete: {stop_detail}")
    _send_telegram_message(chat_id, "Stop phase complete. Starting CATBot services now.")

    started, start_detail = _start_with_retries(
        stop_all_module,
        start_attempts,
        required_ports,
        required_service_signatures,
    )
    if not started:
        message = f"Restart failed during start phase: {start_detail}"
        _log(message)
        _send_telegram_message(chat_id, message)
        return 1

    message = (
        "CATBot restart completed successfully.\n"
        "Checks passed: required service ports, proxy /monitor/summary, MCP browser health."
    )
    _log(start_detail)
    _send_telegram_message(chat_id, message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

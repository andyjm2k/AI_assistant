"""
Background poller for scheduled todo tasks.

This service periodically checks each authenticated user's due tasks and
triggers `/v1/todo/execute` for the first due task when no execution is active.
Execution state remains centralized in proxy_server.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import signal
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv as _load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    _load_dotenv = None


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_USERS_FILE = _PROJECT_ROOT / "config" / "auth_users.json"
DEFAULT_PROXY_BASE_URL = "https://localhost:8002"


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def create_service_jwt(username: str, secret: str, expires_in_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    ttl = max(60, int(expires_in_seconds))
    payload = {
        "sub": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def load_auth_usernames(users_file: Path) -> List[str]:
    if not users_file.exists():
        return []
    try:
        payload = json.loads(users_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    usernames = [k for k, v in payload.items() if isinstance(k, str) and isinstance(v, dict) and k.strip()]
    return sorted(set(usernames))


def select_due_task_id(todo_due_payload: Dict[str, Any]) -> Optional[int]:
    items = todo_due_payload.get("taskItems")
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_id = item.get("taskId")
        try:
            task_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if task_id >= 1:
            return task_id
    return None


def _extract_error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        for key in ("detail", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def _should_skip_tls_verify(base_url: str) -> bool:
    """Return True for local HTTPS endpoints where self-signed certs are common."""
    try:
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https":
            return False
        if host in {"localhost", "127.0.0.1", "::1"}:
            return True
        return host.endswith(".local")
    except Exception:
        return False


def _json_request(
    *,
    method: str,
    url: str,
    bearer_token: str,
    timeout_seconds: int,
    body: Optional[Dict[str, Any]] = None,
    skip_tls_verify: bool = False,
) -> Tuple[int, Dict[str, Any], str]:
    encoded_body: Optional[bytes] = None
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Accept": "application/json",
    }
    if body is not None:
        encoded_body = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url=url, method=method.upper(), headers=headers, data=encoded_body)
    try:
        open_kwargs: Dict[str, Any] = {"timeout": timeout_seconds}
        if skip_tls_verify:
            insecure_context = ssl.create_default_context()
            insecure_context.check_hostname = False
            insecure_context.verify_mode = ssl.CERT_NONE
            open_kwargs["context"] = insecure_context
        with urlopen(request, **open_kwargs) as response:
            status = int(getattr(response, "status", 200))
            raw = response.read().decode("utf-8", errors="replace").strip()
            if not raw:
                return status, {}, ""
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    return status, payload, ""
                return status, {"raw": payload}, ""
            except json.JSONDecodeError:
                return status, {"raw": raw}, ""
    except HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace").strip()
        payload: Dict[str, Any] = {}
        if raw_error:
            try:
                parsed = json.loads(raw_error)
                if isinstance(parsed, dict):
                    payload = parsed
                else:
                    payload = {"raw": parsed}
            except json.JSONDecodeError:
                payload = {"raw": raw_error}
        return int(exc.code), payload, raw_error
    except URLError as exc:
        return 0, {}, str(exc.reason)
    except Exception as exc:  # pragma: no cover - defensive fallback
        return 0, {}, str(exc)


@dataclass(frozen=True)
class PollerConfig:
    proxy_base_url: str
    users_file: Path
    interval_seconds: int
    timeout_seconds: int
    jwt_secret: str
    jwt_expiration_seconds: int
    run_once: bool


class ScheduledTaskPoller:
    def __init__(self, config: PollerConfig) -> None:
        self.config = config
        self._stop_requested = False

    def request_stop(self, *_args: Any) -> None:
        self._stop_requested = True

    def run(self) -> None:
        print(
            "[SCHED_POLLER] Starting with "
            f"proxy={self.config.proxy_base_url}, interval={self.config.interval_seconds}s, "
            f"users_file={self.config.users_file}",
            flush=True,
        )
        while not self._stop_requested:
            self.poll_once()
            if self.config.run_once:
                break
            self._sleep_with_stop(self.config.interval_seconds)
        print("[SCHED_POLLER] Stopped.", flush=True)

    def poll_once(self) -> None:
        usernames = load_auth_usernames(self.config.users_file)
        if not usernames:
            print(
                f"[SCHED_POLLER] No users found in {self.config.users_file}.",
                flush=True,
            )
            return

        for username in usernames:
            if self._stop_requested:
                return
            self._poll_user(username)

    def _poll_user(self, username: str) -> None:
        token = create_service_jwt(username, self.config.jwt_secret, self.config.jwt_expiration_seconds)
        skip_tls_verify = _should_skip_tls_verify(self.config.proxy_base_url)
        due_url = self._url("/v1/todo/due")
        due_status, due_payload, due_error = _json_request(
            method="GET",
            url=due_url,
            bearer_token=token,
            timeout_seconds=self.config.timeout_seconds,
            skip_tls_verify=skip_tls_verify,
        )
        if due_status != 200:
            message = _extract_error_message(due_payload, due_error or "request failed")
            print(
                f"[SCHED_POLLER] due-check failed user={username} status={due_status}: {message}",
                flush=True,
            )
            return

        task_id = select_due_task_id(due_payload)
        if task_id is None:
            return

        execute_url = self._url("/v1/todo/execute")
        exec_status, exec_payload, exec_error = _json_request(
            method="POST",
            url=execute_url,
            bearer_token=token,
            timeout_seconds=self.config.timeout_seconds,
            body={"taskId": task_id},
            skip_tls_verify=skip_tls_verify,
        )

        if exec_status == 200:
            print(
                f"[SCHED_POLLER] Started scheduled execution user={username} task_id={task_id}.",
                flush=True,
            )
            return
        if exec_status == 409:
            print(
                f"[SCHED_POLLER] Skipped user={username} task_id={task_id}: execution already active.",
                flush=True,
            )
            return

        message = _extract_error_message(exec_payload, exec_error or "request failed")
        print(
            f"[SCHED_POLLER] Failed to start execution user={username} task_id={task_id} "
            f"status={exec_status}: {message}",
            flush=True,
        )

    def _url(self, path: str) -> str:
        return f"{self.config.proxy_base_url.rstrip('/')}/{path.lstrip('/')}"

    def _sleep_with_stop(self, total_seconds: int) -> None:
        remaining = max(0, int(total_seconds))
        while remaining > 0 and not self._stop_requested:
            time.sleep(1)
            remaining -= 1


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _env_int(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    return max(minimum, value)


def _load_project_env_file() -> None:
    if _load_dotenv is None:
        return
    env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        _load_dotenv(env_path)


def load_config_from_env() -> PollerConfig:
    _load_project_env_file()
    return PollerConfig(
        proxy_base_url=os.getenv("SCHEDULED_TASK_POLLER_PROXY_URL", DEFAULT_PROXY_BASE_URL).strip() or DEFAULT_PROXY_BASE_URL,
        users_file=Path(os.getenv("SCHEDULED_TASK_POLLER_USERS_FILE", str(DEFAULT_USERS_FILE))).expanduser(),
        interval_seconds=_env_int("SCHEDULED_TASK_POLLER_INTERVAL_SECONDS", default=30, minimum=5),
        timeout_seconds=_env_int("SCHEDULED_TASK_POLLER_REQUEST_TIMEOUT_SECONDS", default=15, minimum=3),
        jwt_secret=os.getenv("JWT_SECRET", "change-this-secret-in-production"),
        jwt_expiration_seconds=_env_int("JWT_EXPIRATION_SECONDS", default=3600, minimum=60),
        run_once=_env_bool("SCHEDULED_TASK_POLLER_RUN_ONCE", default=False),
    )


def main() -> None:
    if not _env_bool("SCHEDULED_TASK_POLLER_ENABLED", default=True):
        print("[SCHED_POLLER] Disabled via SCHEDULED_TASK_POLLER_ENABLED.", flush=True)
        return

    poller = ScheduledTaskPoller(load_config_from_env())
    signal.signal(signal.SIGINT, poller.request_stop)
    signal.signal(signal.SIGTERM, poller.request_stop)
    poller.run()


if __name__ == "__main__":
    main()

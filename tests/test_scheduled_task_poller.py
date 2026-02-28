import base64
import json
import shutil
from pathlib import Path
from uuid import uuid4

from src.servers.scheduled_task_poller import (
    PollerConfig,
    ScheduledTaskPoller,
    create_service_jwt,
    load_auth_usernames,
    load_config_from_env,
    select_due_task_id,
)


def _base64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(f"{text}{padding}")


def _make_test_dir() -> Path:
    path = Path("scratch") / f"pytest_sched_poller_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def test_load_auth_usernames_returns_sorted_usernames():
    tmp_dir = _make_test_dir()
    try:
        users_file = tmp_dir / "auth_users.json"
        users_file.write_text(
            json.dumps(
                {
                    "zeta": {"salt": "a", "password_hash": "b"},
                    "alpha": {"salt": "c", "password_hash": "d"},
                    "": {"salt": "x", "password_hash": "y"},
                    "ignored": "not-a-record",
                }
            ),
            encoding="utf-8",
        )
        assert load_auth_usernames(users_file) == ["alpha", "zeta"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_select_due_task_id_reads_first_valid_due_item():
    payload = {
        "taskItems": [
            {"taskId": "bad"},
            {"taskId": 3, "isDue": True},
            {"taskId": 4, "isDue": True},
        ]
    }
    assert select_due_task_id(payload) == 3


def test_create_service_jwt_contains_subject():
    token = create_service_jwt("alice", "secret123", 900)
    parts = token.split(".")
    assert len(parts) == 3
    payload = json.loads(_base64url_decode(parts[1]).decode("utf-8"))
    assert payload["sub"] == "alice"
    assert payload["exp"] > payload["iat"]


def test_poller_poll_once_starts_execution_for_due_task(monkeypatch):
    tmp_dir = _make_test_dir()
    users_file = tmp_dir / "auth_users.json"
    users_file.write_text(json.dumps({"alice": {"salt": "x", "password_hash": "y"}}), encoding="utf-8")

    calls = []

    def fake_request(*, method, url, bearer_token, timeout_seconds, body=None, skip_tls_verify=False):
        calls.append(
            {
                "method": method,
                "url": url,
                "bearer_token": bearer_token,
                "timeout_seconds": timeout_seconds,
                "body": body,
                "skip_tls_verify": skip_tls_verify,
            }
        )
        if method == "GET" and url.endswith("/v1/todo/due"):
            return 200, {"taskItems": [{"taskId": 2}]}, ""
        if method == "POST" and url.endswith("/v1/todo/execute"):
            return 200, {"status": "executing"}, ""
        return 500, {"detail": "unexpected"}, "unexpected"

    monkeypatch.setattr("src.servers.scheduled_task_poller._json_request", fake_request)
    monkeypatch.setattr(
        "src.servers.scheduled_task_poller.create_service_jwt",
        lambda username, secret, expires: f"token-for-{username}",
    )

    poller = ScheduledTaskPoller(
        PollerConfig(
            proxy_base_url="http://127.0.0.1:8002",
            users_file=users_file,
            interval_seconds=30,
            timeout_seconds=7,
            jwt_secret="secret123",
            jwt_expiration_seconds=3600,
            run_once=True,
        )
    )
    try:
        poller.poll_once()
        assert len(calls) == 2
        assert calls[0]["method"] == "GET"
        assert calls[0]["url"].endswith("/v1/todo/due")
        assert calls[0]["skip_tls_verify"] is False
        assert calls[1]["method"] == "POST"
        assert calls[1]["url"].endswith("/v1/todo/execute")
        assert calls[1]["body"] == {"taskId": 2}
        assert calls[1]["skip_tls_verify"] is False
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_poller_poll_once_skips_tls_verify_for_local_https_proxy(monkeypatch):
    tmp_dir = _make_test_dir()
    users_file = tmp_dir / "auth_users.json"
    users_file.write_text(json.dumps({"alice": {"salt": "x", "password_hash": "y"}}), encoding="utf-8")

    calls = []

    def fake_request(*, method, url, bearer_token, timeout_seconds, body=None, skip_tls_verify=False):
        calls.append(skip_tls_verify)
        if method == "GET" and url.endswith("/v1/todo/due"):
            return 200, {"taskItems": [{"taskId": 2}]}, ""
        if method == "POST" and url.endswith("/v1/todo/execute"):
            return 200, {"status": "executing"}, ""
        return 500, {"detail": "unexpected"}, "unexpected"

    monkeypatch.setattr("src.servers.scheduled_task_poller._json_request", fake_request)
    monkeypatch.setattr(
        "src.servers.scheduled_task_poller.create_service_jwt",
        lambda username, secret, expires: f"token-for-{username}",
    )

    poller = ScheduledTaskPoller(
        PollerConfig(
            proxy_base_url="https://localhost:8002",
            users_file=users_file,
            interval_seconds=30,
            timeout_seconds=7,
            jwt_secret="secret123",
            jwt_expiration_seconds=3600,
            run_once=True,
        )
    )
    try:
        poller.poll_once()
        assert calls == [True, True]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_load_config_from_env_default_proxy_url_is_https_localhost(monkeypatch):
    monkeypatch.setattr("src.servers.scheduled_task_poller._load_project_env_file", lambda: None)
    monkeypatch.delenv("SCHEDULED_TASK_POLLER_PROXY_URL", raising=False)

    cfg = load_config_from_env()

    assert cfg.proxy_base_url == "https://localhost:8002"

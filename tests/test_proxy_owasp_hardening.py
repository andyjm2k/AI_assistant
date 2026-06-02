from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.servers import proxy_server as ps


def test_signup_disabled_after_bootstrap_without_invite(monkeypatch):
    monkeypatch.setattr(ps, "AUTH_ALLOW_PUBLIC_SIGNUP", False)
    monkeypatch.setattr(ps, "AUTH_BOOTSTRAP_FIRST_USER", True)
    monkeypatch.setattr(ps, "AUTH_SIGNUP_INVITE_CODE", "")
    monkeypatch.setattr(ps, "users_db", {"existing": {"created_at": "2026-01-01T00:00:00Z"}})

    request = ps.AuthSignupRequest(username="newuser", password="password123")

    assert ps._signup_allowed(request) is False


def test_signup_allows_valid_invite_code(monkeypatch):
    monkeypatch.setattr(ps, "AUTH_ALLOW_PUBLIC_SIGNUP", False)
    monkeypatch.setattr(ps, "AUTH_BOOTSTRAP_FIRST_USER", False)
    monkeypatch.setattr(ps, "AUTH_SIGNUP_INVITE_CODE", "invite-123")
    monkeypatch.setattr(ps, "users_db", {"existing": {"created_at": "2026-01-01T00:00:00Z"}})

    request = ps.AuthSignupRequest(username="newuser", password="password123", invite_code="invite-123")

    assert ps._signup_allowed(request) is True


def test_cors_blocks_unconfigured_public_origin():
    request = MagicMock()
    request.headers = {"origin": "https://attacker.example"}

    headers = ps.build_cors_headers(request)

    assert "Access-Control-Allow-Origin" not in headers


def test_cors_allows_local_origin():
    request = MagicMock()
    request.headers = {"origin": "http://127.0.0.1:8000"}

    headers = ps.build_cors_headers(request)

    assert headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:8000"


def test_outbound_url_policy_rejects_loopback(monkeypatch):
    monkeypatch.setattr(ps, "PROXY_OUTBOUND_ALLOW_PRIVATE", False)

    with pytest.raises(HTTPException) as exc_info:
        ps._validate_outbound_url("http://127.0.0.1:8000/private")

    assert exc_info.value.status_code == 400


def test_tool_log_rejects_non_loopback_without_auth():
    request = MagicMock()
    request.headers = {}
    request.client.host = "203.0.113.10"

    with pytest.raises(HTTPException):
        ps._require_internal_or_local_access(request, "tool invocation logging")


def test_public_monitor_still_available_to_loopback_testclient():
    with TestClient(ps.app) as client:
        response = client.get("/monitor/summary")

    assert response.status_code == 200

"""
Unit tests for proxy chat budget helpers.
"""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from src.servers import proxy_server


def test_normalize_chat_endpoint_appends_path():
    base = "http://localhost:1234/v1"
    assert proxy_server._normalize_chat_endpoint(base) == "http://localhost:1234/v1/chat/completions"
    already = "http://localhost:1234/v1/chat/completions"
    assert proxy_server._normalize_chat_endpoint(already) == already


def test_normalize_models_endpoint_replaces_chat_suffix():
    base = "http://localhost:1234/v1/chat/completions"
    assert proxy_server._normalize_models_endpoint(base) == "http://localhost:1234/v1/models"
    already = "http://localhost:1234/v1/models"
    assert proxy_server._normalize_models_endpoint(already) == already


def test_get_max_tokens_from_payload():
    assert proxy_server._get_max_tokens_from_payload({"max_tokens": 100}) == 100
    assert proxy_server._get_max_tokens_from_payload({"max_tokens": "200"}) == 200
    assert proxy_server._get_max_tokens_from_payload({"max_tokens": None}) == 0
    assert proxy_server._get_max_tokens_from_payload({"max_tokens": "bad"}) == 0


def test_resolve_mcp_llm_api_key_prefers_generic_override(monkeypatch):
    monkeypatch.setenv("MCP_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("MCP_LLM_API_KEY", "generic-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "provider-key")

    assert proxy_server._resolve_mcp_llm_api_key() == "generic-key"


def test_build_mcp_fallback_headers_uses_provider_key(monkeypatch):
    monkeypatch.setenv("MCP_LLM_PROVIDER", "openrouter")
    monkeypatch.delenv("MCP_LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "provider-key")

    headers = proxy_server._build_mcp_fallback_headers(
        {"Authorization": "Bearer primary-key", "OpenAI-Organization": "org-1"}
    )
    assert headers["Authorization"] == "Bearer provider-key"
    assert headers["OpenAI-Organization"] == "org-1"


def test_build_mcp_fallback_payload_overrides_model(monkeypatch):
    monkeypatch.setenv("MCP_LLM_MODEL_NAME", "fallback-model")

    payload = {"model": "primary-model", "messages": [{"role": "user", "content": "hi"}]}
    fallback_payload = proxy_server._build_mcp_fallback_payload(payload)

    assert fallback_payload["model"] == "fallback-model"
    assert payload["model"] == "primary-model"


@pytest.mark.asyncio
async def test_execute_tool_for_philosopher_errors_on_ambiguous_mcp_tool(monkeypatch):
    async def _fake_all_tools():
        return [
            {"name": "duplicate_tool", "server_id": "server_a"},
            {"name": "duplicate_tool", "server_id": "server_b"},
        ]

    monkeypatch.setattr(proxy_server, "MCP_AVAILABLE", True)
    monkeypatch.setattr(proxy_server, "get_all_available_tools", _fake_all_tools)

    out = await proxy_server.execute_tool_for_philosopher("duplicate_tool", {})
    assert "multiple servers" in out.lower()
    assert "server_id" in out


@pytest.mark.asyncio
async def test_execute_tool_for_philosopher_respects_explicit_server_id(monkeypatch):
    async def _fake_all_tools():
        return [
            {"name": "duplicate_tool", "server_id": "server_a"},
            {"name": "duplicate_tool", "server_id": "server_b"},
        ]

    fake_call_tool = AsyncMock(
        return_value={"result": {"content": [{"type": "text", "text": "ok-from-b"}]}}
    )
    monkeypatch.setattr(proxy_server, "MCP_AVAILABLE", True)
    monkeypatch.setattr(proxy_server, "get_all_available_tools", _fake_all_tools)
    monkeypatch.setattr(proxy_server, "call_tool", fake_call_tool)

    out = await proxy_server.execute_tool_for_philosopher(
        "duplicate_tool",
        {"server_id": "server_b", "x": 1},
    )
    assert out == "ok-from-b"

    assert fake_call_tool.await_count == 1
    call_args = fake_call_tool.call_args[0]
    assert call_args[0] == "server_b"
    request = call_args[1]
    assert request.parameters == {"x": 1}


def test_proxy_chat_completions_uses_server_key_for_trusted_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "https://trusted.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "server-key")

    async def fake_call(endpoint, headers, payload, timeout_seconds):
        assert endpoint == "https://trusted.example/v1/chat/completions"
        assert headers["Authorization"] == "Bearer server-key"
        return httpx.Response(200, json={"id": "chatcmpl-test", "choices": []})

    monkeypatch.setattr(proxy_server, "_call_chat_completion", fake_call)

    with TestClient(proxy_server.app) as client:
        response = client.post(
            "/v1/proxy/chat/completions",
            json={"model": "gpt-test", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-test"


def test_proxy_chat_completions_blank_bearer_uses_server_key_for_trusted_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "https://trusted.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "server-key")

    async def fake_call(endpoint, headers, payload, timeout_seconds):
        assert endpoint == "https://trusted.example/v1/chat/completions"
        assert headers["Authorization"] == "Bearer server-key"
        return httpx.Response(200, json={"id": "chatcmpl-test", "choices": []})

    monkeypatch.setattr(proxy_server, "_call_chat_completion", fake_call)

    with TestClient(proxy_server.app) as client:
        response = client.post(
            "/v1/proxy/chat/completions",
            headers={"Authorization": "Bearer"},
            json={"model": "gpt-test", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-test"


def test_proxy_chat_completions_rejects_untrusted_override_without_auth(monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "https://trusted.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "server-key")

    with TestClient(proxy_server.app) as client:
        response = client.post(
            "/v1/proxy/chat/completions?endpoint=https://evil.example/v1",
            json={"model": "gpt-test", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert response.status_code == 400
    assert "Endpoint override requires an Authorization header" in response.json()["detail"]


def test_proxy_chat_completions_untrusted_override_uses_caller_auth_without_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "https://trusted.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "server-key")
    captured = {}

    async def fake_call(endpoint, headers, payload, timeout_seconds):
        captured["endpoint"] = endpoint
        captured["headers"] = dict(headers)
        raise httpx.RequestError("boom", request=httpx.Request("POST", endpoint))

    fallback_mock = AsyncMock(return_value=(httpx.Response(200, json={"unexpected": True}), None))
    monkeypatch.setattr(proxy_server, "_call_chat_completion", fake_call)
    monkeypatch.setattr(proxy_server, "_attempt_mcp_chat_fallback", fallback_mock)

    with TestClient(proxy_server.app) as client:
        response = client.post(
            "/v1/proxy/chat/completions?endpoint=https://caller.example/v1",
            headers={"Authorization": "Bearer caller-key"},
            json={"model": "gpt-test", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert response.status_code == 503
    assert captured["endpoint"] == "https://caller.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer caller-key"
    assert fallback_mock.await_count == 0


def test_proxy_models_uses_server_key_for_trusted_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "https://trusted.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "server-key")
    captured = {}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.is_closed = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aclose(self):
            self.is_closed = True

        async def get(self, endpoint, headers=None):
            captured["endpoint"] = endpoint
            captured["headers"] = dict(headers or {})
            return httpx.Response(200, json={"data": []}, headers={"content-type": "application/json"})

    monkeypatch.setattr(proxy_server.httpx, "AsyncClient", FakeAsyncClient)

    with TestClient(proxy_server.app) as client:
        response = client.get("/v1/proxy/models")

    assert response.status_code == 200
    assert captured["endpoint"] == "https://trusted.example/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer server-key"


def test_proxy_models_blank_bearer_uses_server_key_for_trusted_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "https://trusted.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "server-key")
    captured = {}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.is_closed = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aclose(self):
            self.is_closed = True

        async def get(self, endpoint, headers=None):
            captured["endpoint"] = endpoint
            captured["headers"] = dict(headers or {})
            return httpx.Response(200, json={"data": []}, headers={"content-type": "application/json"})

    monkeypatch.setattr(proxy_server.httpx, "AsyncClient", FakeAsyncClient)

    with TestClient(proxy_server.app) as client:
        response = client.get("/v1/proxy/models", headers={"Authorization": "Bearer"})

    assert response.status_code == 200
    assert captured["endpoint"] == "https://trusted.example/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer server-key"


def test_proxy_models_returns_minimax_fallback_when_upstream_models_endpoint_fails(monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "https://api.minimax.io/v1")
    monkeypatch.setenv("MINIMAX_API_KEY", "minimax-key")

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            self.is_closed = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aclose(self):
            self.is_closed = True

        async def get(self, endpoint, headers=None):
            return httpx.Response(404, text="not found", headers={"content-type": "text/plain"})

    monkeypatch.setattr(proxy_server.httpx, "AsyncClient", FakeAsyncClient)

    with TestClient(proxy_server.app) as client:
        response = client.get("/v1/proxy/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["warning"].startswith("MiniMax does not currently expose a standard OpenAI-compatible /models response")
    model_ids = [entry["id"] for entry in payload["data"]]
    assert "MiniMax-M2.5" in model_ids
    assert "MiniMax-M2.7" in model_ids


def test_proxy_models_rejects_untrusted_override_without_auth(monkeypatch):
    monkeypatch.setenv("OPENAI_API_BASE", "https://trusted.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "server-key")

    with TestClient(proxy_server.app) as client:
        response = client.get("/v1/proxy/models?endpoint=https://evil.example/v1")

    assert response.status_code == 400
    assert "Endpoint override requires an Authorization header" in response.json()["detail"]

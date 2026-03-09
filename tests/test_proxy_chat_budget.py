"""
Unit tests for proxy chat budget helpers.
"""

from unittest.mock import AsyncMock

import pytest

from src.servers import proxy_server


def test_normalize_chat_endpoint_appends_path():
    base = "http://localhost:1234/v1"
    assert proxy_server._normalize_chat_endpoint(base) == "http://localhost:1234/v1/chat/completions"
    already = "http://localhost:1234/v1/chat/completions"
    assert proxy_server._normalize_chat_endpoint(already) == already


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

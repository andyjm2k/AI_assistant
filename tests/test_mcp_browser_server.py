"""Tests for src.servers.mcp_browser_server."""

from __future__ import annotations

from unittest.mock import patch


def _client():
    from src.servers import mcp_browser_server as server

    return server.app.test_client()


def test_browser_agent_requires_shared_secret(monkeypatch):
    from src.servers import mcp_browser_server as server

    monkeypatch.setenv("MCP_BROWSER_SERVER_SECRET", "bridge-secret")

    response = _client().post("/api/browser-agent", json={"task": "Open example.com"})

    assert response.status_code == 401
    assert response.get_json()["error"] == "Missing or invalid browser server shared secret."


def test_browser_agent_accepts_agent_secret(monkeypatch):
    from src.servers import mcp_browser_server as server

    monkeypatch.setenv("MCP_BROWSER_SERVER_SECRET", "bridge-secret")

    def fake_asyncio_run(coro):
        coro.close()
        return "done"

    with patch.object(server.asyncio, "run", side_effect=fake_asyncio_run):
        response = _client().post(
            "/api/browser-agent",
            json={"task": "Open example.com"},
            headers={"X-Agent-Secret": "bridge-secret"},
        )

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "result": "done"}


def test_browser_agent_returns_503_when_secret_not_configured(monkeypatch):
    monkeypatch.delenv("MCP_BROWSER_SERVER_SECRET", raising=False)
    monkeypatch.delenv("CATBOT_AGENT_SECRET", raising=False)
    monkeypatch.delenv("AUTOGEN_TEAM_SECRET", raising=False)

    response = _client().post("/api/browser-agent", json={"task": "Open example.com"})

    assert response.status_code == 503
    assert response.get_json()["error"] == "Browser server shared secret is not configured."


def test_main_binds_to_loopback_by_default(monkeypatch):
    from src.servers import mcp_browser_server as server

    captured = {}

    def fake_run(*, host, port, debug):
        captured["host"] = host
        captured["port"] = port
        captured["debug"] = debug

    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setenv("MCP_BROWSER_SERVER_SECRET", "bridge-secret")
    monkeypatch.setattr(server.app, "run", fake_run)

    server.main()

    assert captured == {
        "host": "127.0.0.1",
        "port": 5001,
        "debug": False,
    }

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.servers import proxy_server


def _memory_extract_payload():
    return {
        "messages": [
            {"role": "user", "content": "I live in Hobart."},
            {"role": "assistant", "content": "I will remember that."},
        ],
        "max_memories": 3,
        "conversation_id": "browser-conversation",
    }


def _authenticated_browser_headers(username="memory-browser-user"):
    proxy_server.users_db.setdefault(
        username,
        {"created_at": "2026-01-01T00:00:00Z"},
    )
    token = proxy_server.create_jwt({"sub": username})
    return {
        "Origin": "http://testserver",
        "X-Auth-Token": token,
    }


def test_memory_extract_accepts_authenticated_browser_request(monkeypatch):
    manager = type("MemoryManagerStub", (), {})()
    manager.extract_memories_from_conversation = AsyncMock(return_value=["memory-1"])
    monkeypatch.setattr(proxy_server, "MEMORY_AVAILABLE", True)
    monkeypatch.setattr(proxy_server, "memory_manager", manager)

    with TestClient(proxy_server.app) as client:
        response = client.post(
            "/v1/memory/extract",
            headers=_authenticated_browser_headers(),
            json=_memory_extract_payload(),
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "extracted": 1,
        "memory_ids": ["memory-1"],
    }
    manager.extract_memories_from_conversation.assert_awaited_once()
    assert manager.extract_memories_from_conversation.await_args.kwargs["namespace"] == "memory-browser-user"


def test_memory_extract_rejects_unauthenticated_cross_origin_request(monkeypatch):
    manager = type("MemoryManagerStub", (), {})()
    manager.extract_memories_from_conversation = AsyncMock(return_value=[])
    monkeypatch.setattr(proxy_server, "MEMORY_AVAILABLE", True)
    monkeypatch.setattr(proxy_server, "memory_manager", manager)

    with TestClient(proxy_server.app) as client:
        missing_auth = client.post(
            "/v1/memory/extract",
            headers={"Origin": "https://attacker.example"},
            json=_memory_extract_payload(),
        )
        bad_auth = client.post(
            "/v1/memory/extract",
            headers={
                "Origin": "https://attacker.example",
                "X-Auth-Token": "not-a-valid-jwt",
            },
            json=_memory_extract_payload(),
        )

    assert missing_auth.status_code == 401
    assert bad_auth.status_code == 401
    assert "Access-Control-Allow-Origin" not in missing_auth.headers
    assert "Access-Control-Allow-Origin" not in bad_auth.headers
    manager.extract_memories_from_conversation.assert_not_awaited()

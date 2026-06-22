from fastapi.testclient import TestClient
from unittest.mock import patch


def _client():
    from src.servers.proxy_server import app
    return TestClient(app)


def _auth_headers():
    from src.servers.proxy_server import create_jwt, users_db
    users_db.setdefault("config-user", {"created_at": "2026-01-01T00:00:00Z"})
    token = create_jwt({"sub": "config-user"})
    return {"Authorization": f"Bearer {token}"}


def test_client_config_prefers_tts_env(monkeypatch):
    client = _client()
    monkeypatch.setenv("TTS_ENDPOINT", "http://localhost:9000/v1")
    monkeypatch.setenv("TTS_MODEL", "custom-tts-model")
    monkeypatch.setenv("TTS_VOICE", "custom-voice")
    monkeypatch.setenv("TELEGRAM_TTS_MODEL", "telegram-model")
    monkeypatch.setenv("TELEGRAM_TTS_VOICE", "telegram-voice")

    response = client.get("/v1/client-config", headers=_auth_headers())
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ttsEndpoint"] == "http://localhost:9000/v1"
    assert data["ttsModel"] == "custom-tts-model"
    assert data["ttsVoice"] == "custom-voice"


def test_client_config_includes_safe_llm_proxy_defaults(monkeypatch):
    from src.servers import proxy_server

    client = _client()
    monkeypatch.setenv("OPENAI_API_BASE", "http://127.0.0.1:11434/v1")
    monkeypatch.setattr(proxy_server, "OPENAI_PROXY_ALLOW_PRIVATE", True)
    monkeypatch.setattr(proxy_server, "PROXY_OUTBOUND_ALLOW_PRIVATE", False)

    response = client.get("/v1/client-config", headers=_auth_headers())

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["llmEndpoint"] == "http://127.0.0.1:11434/v1"
    assert data["llmPrivateNetworksAllowed"] is True


def test_client_config_falls_back_to_telegram(monkeypatch):
    client = _client()
    monkeypatch.delenv("TTS_ENDPOINT", raising=False)
    monkeypatch.delenv("TTS_MODEL", raising=False)
    monkeypatch.delenv("TTS_VOICE", raising=False)
    monkeypatch.setenv("TELEGRAM_TTS_MODEL", "telegram-model")
    monkeypatch.setenv("TELEGRAM_TTS_VOICE", "telegram-voice")

    response = client.get("/v1/client-config", headers=_auth_headers())
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ttsEndpoint"] is None
    assert data["ttsModel"] == "telegram-model"
    assert data["ttsVoice"] == "telegram-voice"


def test_client_config_includes_soul_prompt():
    client = _client()

    with patch("src.servers.proxy_server._get_soul_prompt_text", return_value="Persona text"):
        response = client.get("/v1/client-config", headers=_auth_headers())

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["soulPrompt"] == "Persona text"

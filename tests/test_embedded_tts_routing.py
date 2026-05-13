from unittest.mock import patch

from fastapi.testclient import TestClient

import src.servers.proxy_server as proxy_server


def _client():
    return TestClient(proxy_server.app)


def test_embedded_audio_voices_returns_pocket_voice_catalog_for_pocket_model(monkeypatch):
    monkeypatch.setattr(proxy_server, "EMBEDDED_KITTEN_TTS_ENABLED", False)
    monkeypatch.setattr(proxy_server, "EMBEDDED_POCKET_TTS_ENABLED", True)
    monkeypatch.setattr(proxy_server, "EMBEDDED_POCKET_VOICES", ["alba", "marius"])
    monkeypatch.setattr(proxy_server, "EMBEDDED_POCKET_DEFAULT_VOICE", "alba")
    monkeypatch.setattr(proxy_server, "EMBEDDED_POCKET_VOICE_DIR", "")

    response = _client().get("/v1/audio/voices", params={"model": "pocket-tts-realtime"})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [item["id"] for item in payload["data"]] == ["alba", "marius"]


def test_embedded_audio_voices_includes_local_pocket_voice_files(monkeypatch, tmp_path):
    local_voice = tmp_path / "custom_voice.safetensors"
    local_voice.write_bytes(b"voice-state")
    monkeypatch.setattr(proxy_server, "EMBEDDED_KITTEN_TTS_ENABLED", False)
    monkeypatch.setattr(proxy_server, "EMBEDDED_POCKET_TTS_ENABLED", True)
    monkeypatch.setattr(proxy_server, "EMBEDDED_POCKET_VOICES", ["alba"])
    monkeypatch.setattr(proxy_server, "EMBEDDED_POCKET_DEFAULT_VOICE", "alba")
    monkeypatch.setattr(proxy_server, "EMBEDDED_POCKET_VOICE_DIR", str(tmp_path))

    response = _client().get("/v1/audio/voices", params={"model": "pocket-tts-realtime"})

    assert response.status_code == 200, response.text
    payload = response.json()
    voice_ids = [item["id"] for item in payload["data"]]
    assert "alba" in voice_ids
    assert str(local_voice.resolve()) in voice_ids
    local_entry = next(item for item in payload["data"] if item["id"] == str(local_voice.resolve()))
    assert local_entry["name"] == "custom_voice"


def test_embedded_pocket_voice_alias_maps_openai_voice_name():
    assert proxy_server._resolve_embedded_pocket_voice("alloy") == "alba"


def test_embedded_pocket_model_alias_resolves_to_packaged_variant(monkeypatch):
    monkeypatch.setattr(proxy_server, "EMBEDDED_POCKET_MODEL", "pocket-tts-realtime")
    monkeypatch.setattr(proxy_server, "EMBEDDED_POCKET_VARIANT", "b6369a24")

    assert proxy_server._normalize_embedded_pocket_model_name(None) == "b6369a24"
    assert proxy_server._normalize_embedded_pocket_model_name("pocket-tts") == "b6369a24"
    assert proxy_server._normalize_embedded_pocket_model_name("kyutai/pocket-tts") == "b6369a24"
    assert proxy_server._normalize_embedded_pocket_model_name("custom-local.yaml") == "custom-local.yaml"


def test_proxy_tts_voices_forwards_model_query_to_upstream():
    requested_urls = []

    class _Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"data": [{"id": "alba", "name": "alba"}]}

    class _AsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers=None):
            requested_urls.append(url)
            return _Response()

    with patch("src.servers.proxy_server.httpx.AsyncClient", _AsyncClient):
        response = _client().get(
            "/v1/proxy/tts/voices",
            params={"endpoint": "http://localhost:8002", "model": "pocket-tts-realtime"},
        )

    assert response.status_code == 200, response.text
    assert requested_urls
    assert requested_urls[0].endswith("/voices?model=pocket-tts-realtime")

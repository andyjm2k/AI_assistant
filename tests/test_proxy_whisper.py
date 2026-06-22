import base64
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.servers import proxy_server as ps


def _response(status_code: int) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    return response


def test_whisper_api_key_candidates_adds_openai_fallback(monkeypatch):
    monkeypatch.setenv("WHISPER_API_KEY", "stt-key")
    monkeypatch.setenv("OPENAI_API_KEY", "general-key")

    assert ps._whisper_api_key_candidates(
        "https://api.openai.com/v1/audio/transcriptions"
    ) == ["stt-key", "general-key"]


def test_whisper_api_key_candidates_does_not_leak_openai_key_to_custom_endpoint(monkeypatch):
    monkeypatch.setenv("WHISPER_API_KEY", "stt-key")
    monkeypatch.setenv("OPENAI_API_KEY", "general-key")

    assert ps._whisper_api_key_candidates(
        "https://stt.example.com/v1/audio/transcriptions"
    ) == ["stt-key"]


def test_whisper_api_key_candidates_uses_openrouter_key(monkeypatch):
    monkeypatch.setenv("WHISPER_API_KEY", "stt-key")
    monkeypatch.setenv("OPENAI_API_KEY", "general-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")

    assert ps._whisper_api_key_candidates(
        "https://openrouter.ai/api/v1/audio/transcriptions"
    ) == ["openrouter-key"]


def test_openrouter_stt_payload_encodes_telegram_ogg_and_normalizes_model():
    payload = ps._openrouter_stt_payload(
        {"file": ("voice_123.ogg", b"telegram-audio", "audio/ogg")},
        {"model": "whisper-1", "language": "en", "temperature": "0.2"},
    )

    assert payload == {
        "input_audio": {
            "data": base64.b64encode(b"telegram-audio").decode("ascii"),
            "format": "ogg",
        },
        "model": "openai/whisper-1",
        "language": "en",
        "temperature": 0.2,
    }


def test_openrouter_stt_payload_rejects_missing_audio_file():
    with pytest.raises(HTTPException) as exc_info:
        ps._openrouter_stt_payload({}, {"model": "whisper-1"})

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_post_whisper_request_retries_quota_failure_with_openai_key(monkeypatch):
    monkeypatch.setenv("WHISPER_API_KEY", "quota-key")
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-key")
    client = MagicMock()
    client.post = AsyncMock(side_effect=[_response(429), _response(200)])

    response = await ps._post_whisper_request(
        client,
        "https://api.openai.com/v1/audio/transcriptions",
        {"file": ("voice.ogg", b"audio", "audio/ogg")},
        {"model": "whisper-1"},
    )

    assert response.status_code == 200
    assert client.post.await_count == 2
    assert client.post.await_args_list[0].kwargs["headers"] == {
        "Authorization": "Bearer quota-key"
    }
    assert client.post.await_args_list[1].kwargs["headers"] == {
        "Authorization": "Bearer fallback-key"
    }


@pytest.mark.asyncio
async def test_post_whisper_request_does_not_retry_bad_audio(monkeypatch):
    monkeypatch.setenv("WHISPER_API_KEY", "stt-key")
    monkeypatch.setenv("OPENAI_API_KEY", "general-key")
    client = MagicMock()
    client.post = AsyncMock(return_value=_response(400))

    response = await ps._post_whisper_request(
        client,
        "https://api.openai.com/v1/audio/transcriptions",
        {"file": ("voice.ogg", b"invalid", "audio/ogg")},
        {"model": "whisper-1"},
    )

    assert response.status_code == 400
    client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_post_whisper_request_sends_openrouter_json(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    client = MagicMock()
    client.post = AsyncMock(return_value=_response(200))

    response = await ps._post_whisper_request(
        client,
        "https://openrouter.ai/api/v1/audio/transcriptions",
        {"file": ("voice.ogg", b"audio", "audio/ogg")},
        {"model": "whisper-1"},
    )

    assert response.status_code == 200
    client.post.assert_awaited_once()
    request_kwargs = client.post.await_args.kwargs
    assert "files" not in request_kwargs
    assert "data" not in request_kwargs
    assert request_kwargs["headers"] == {"Authorization": "Bearer openrouter-key"}
    assert request_kwargs["json"] == {
        "input_audio": {
            "data": base64.b64encode(b"audio").decode("ascii"),
            "format": "ogg",
        },
        "model": "openai/whisper-1",
    }

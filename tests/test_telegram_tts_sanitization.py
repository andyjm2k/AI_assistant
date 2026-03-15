from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.integrations.telegram_bot as telegram_bot


@pytest.fixture(autouse=True)
def reset_backend_http_client_cache():
    telegram_bot._backend_http_client = None
    yield
    telegram_bot._backend_http_client = None


def test_sanitize_tts_text_removes_bracketed_content_special_chars_and_emojis():
    raw = "Hello (meta info) [debug] world!!! \U0001F63A #$%^"
    assert telegram_bot._sanitize_tts_text(raw) == "Hello world!!!"


def test_sanitize_tts_text_handles_nested_brackets():
    raw = "Keep (outer (inner) text) done [x [y] z] now"
    assert telegram_bot._sanitize_tts_text(raw) == "Keep done now"


@pytest.mark.asyncio
async def test_call_backend_tts_sends_sanitized_payload_input():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"audio-bytes"
    mock_response.headers = {"content-type": "audio/mpeg"}

    with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        audio_bytes, content_type = await telegram_bot.call_backend_tts("Hi [note] there \U0001F63A !!!")

        assert audio_bytes == b"audio-bytes"
        assert content_type == "audio/mpeg"

        post_call = mock_client.post.call_args
        assert post_call.kwargs["json"]["input"] == "Hi there !!!"


@pytest.mark.asyncio
async def test_call_backend_tts_raises_when_sanitized_text_is_empty():
    with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
        with pytest.raises(RuntimeError, match="empty after sanitization"):
            await telegram_bot.call_backend_tts("\U0001F63A [debug] (meta) @#$%")

    mock_client_cls.assert_not_called()

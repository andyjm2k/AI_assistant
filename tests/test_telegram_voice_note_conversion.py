from unittest.mock import AsyncMock, patch

import pytest

import src.integrations.telegram_bot as telegram_bot


@pytest.mark.asyncio
async def test_ensure_voice_note_passthrough_for_existing_ogg_opus():
    audio = b"OggS" + b"\x00" * 32 + b"OpusHead"
    with patch("src.integrations.telegram_bot.asyncio.to_thread", new=AsyncMock()) as mock_to_thread:
        out_audio, out_type, was_converted = await telegram_bot._ensure_telegram_voice_note_audio(
            audio, "audio/ogg; codecs=opus"
        )
    assert out_audio == audio
    assert out_type == "audio/ogg; codecs=opus"
    assert was_converted is False
    mock_to_thread.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_voice_note_converts_non_opus_audio():
    original = b"fake-mp3-bytes"
    converted = b"OggS" + b"\x00" * 32 + b"OpusHead"
    with patch(
        "src.integrations.telegram_bot.asyncio.to_thread",
        new=AsyncMock(return_value=converted),
    ) as mock_to_thread:
        out_audio, out_type, was_converted = await telegram_bot._ensure_telegram_voice_note_audio(
            original, "audio/mpeg"
        )
    assert out_audio == converted
    assert out_type == "audio/ogg; codecs=opus"
    assert was_converted is True
    mock_to_thread.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_voice_note_falls_back_when_conversion_fails():
    original = b"fake-wav-bytes"
    with patch(
        "src.integrations.telegram_bot.asyncio.to_thread",
        new=AsyncMock(side_effect=RuntimeError("ffmpeg failed")),
    ) as mock_to_thread:
        out_audio, out_type, was_converted = await telegram_bot._ensure_telegram_voice_note_audio(
            original, "audio/wav"
        )
    assert out_audio == original
    assert out_type == "audio/wav"
    assert was_converted is False
    mock_to_thread.assert_awaited_once()

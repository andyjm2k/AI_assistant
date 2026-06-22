"""
Unit tests for Telegram bot integration (CATBot).
Covers: is_authorized, build_chat_url, validate_configuration, call_backend_chat,
clear_backend_history, _parse_admin_ids. Uses mocks; no real Telegram or API calls.
"""

import os
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

# Import after conftest adds project root to path
import src.integrations.telegram_bot as telegram_bot


@pytest.fixture(autouse=True)
def reset_backend_http_client_cache():
    telegram_bot._backend_http_client = None
    yield
    telegram_bot._backend_http_client = None


class TestParseAdminIds:
    """Tests for defensive ADMIN_IDS parsing."""

    def test_parse_admin_ids_skips_invalid_entries(self):
        """Invalid TELEGRAM_ADMIN_IDS entries (e.g. non-numeric) are skipped; valid IDs present."""
        with patch("src.integrations.telegram_bot.os.getenv") as m_getenv:
            m_getenv.side_effect = lambda k, d="": "123,abc,456" if k == "TELEGRAM_ADMIN_IDS" else d
            result = telegram_bot._parse_admin_ids()
        assert result == {123, 456}

    def test_parse_admin_ids_empty_returns_empty_set(self):
        """Empty or missing TELEGRAM_ADMIN_IDS returns empty set."""
        with patch("src.integrations.telegram_bot.os.getenv") as m_getenv:
            m_getenv.side_effect = lambda k, d="": "" if k == "TELEGRAM_ADMIN_IDS" else d
            result = telegram_bot._parse_admin_ids()
        assert result == set()


class TestParseChatTimeout:
    """Tests for TELEGRAM_CHAT_TIMEOUT parsing with hard cap."""

    def test_parse_chat_timeout_applies_hard_cap(self):
        with patch("src.integrations.telegram_bot.os.getenv") as m_getenv:
            def _getenv(key, default=""):
                if key == "TELEGRAM_CHAT_TIMEOUT":
                    return "1800"
                if key == "TELEGRAM_BOT_CHAT_TIMEOUT_HARD_CAP":
                    return "120"
                return default
            m_getenv.side_effect = _getenv
            assert telegram_bot._parse_chat_timeout() == 120.0


class TestIsAuthorized:
    """Tests for is_authorized when ALLOW_ALL_USERS and ADMIN_IDS are patched."""

    def test_authorized_when_allowed_all(self):
        """When ALLOW_ALL_USERS is True, any user_id is authorized."""
        with patch.object(telegram_bot, "ALLOW_ALL_USERS", True):
            assert telegram_bot.is_authorized(999) is True
            assert telegram_bot.is_authorized(123) is True

    def test_authorized_when_in_admin_ids(self):
        """When user_id is in ADMIN_IDS, user is authorized."""
        with patch.object(telegram_bot, "ALLOW_ALL_USERS", False), patch.object(
            telegram_bot, "ADMIN_IDS", {123, 456}
        ):
            assert telegram_bot.is_authorized(123) is True
            assert telegram_bot.is_authorized(456) is True

    def test_not_authorized_when_not_in_admin_ids(self):
        """When user_id is not in ADMIN_IDS and ALLOW_ALL is False, user is not authorized."""
        with patch.object(telegram_bot, "ALLOW_ALL_USERS", False), patch.object(
            telegram_bot, "ADMIN_IDS", {123}
        ):
            assert telegram_bot.is_authorized(999) is False

    def test_not_authorized_when_admin_ids_empty(self):
        """When ADMIN_IDS is empty and ALLOW_ALL is False, user is not authorized."""
        with patch.object(telegram_bot, "ALLOW_ALL_USERS", False), patch.object(
            telegram_bot, "ADMIN_IDS", set()
        ):
            assert telegram_bot.is_authorized(123) is False

    def test_allow_all_does_not_make_user_admin(self):
        with patch.object(telegram_bot, "ALLOW_ALL_USERS", True), patch.object(
            telegram_bot, "ADMIN_IDS", {123}
        ):
            assert telegram_bot.is_authorized(999) is True
            assert telegram_bot.is_admin_user(999) is False
            assert telegram_bot.is_admin_user(123) is True


class TestBuildChatUrl:
    """Tests for build_chat_url."""

    def test_relative_endpoint_returns_full_url(self):
        """Relative CHAT_ENDPOINT is appended to BACKEND_BASE_URL."""
        with patch.object(telegram_bot, "CHAT_ENDPOINT", "/v1/telegram/chat"), patch.object(
            telegram_bot, "BACKEND_BASE_URL", "http://localhost:8002"
        ):
            assert telegram_bot.build_chat_url() == "http://localhost:8002/v1/telegram/chat"

    def test_absolute_endpoint_returned_as_is(self):
        """Absolute URL CHAT_ENDPOINT is returned unchanged."""
        with patch.object(
            telegram_bot, "CHAT_ENDPOINT", "https://api.example.com/chat"
        ), patch.object(telegram_bot, "BACKEND_BASE_URL", "http://localhost:8002"):
            assert telegram_bot.build_chat_url() == "https://api.example.com/chat"


class TestValidateConfiguration:
    """Tests for validate_configuration."""

    def test_raises_when_token_missing(self):
        """validate_configuration raises RuntimeError when TELEGRAM_BOT_TOKEN is missing."""
        with patch.object(telegram_bot, "TELEGRAM_BOT_TOKEN", None):
            with pytest.raises(RuntimeError) as exc_info:
                telegram_bot.validate_configuration()
            assert "TELEGRAM_BOT_TOKEN" in str(exc_info.value)

    def test_raises_when_no_admin_ids_and_not_allow_all(self):
        """validate_configuration raises when ADMIN_IDS empty and ALLOW_ALL_USERS False."""
        with patch.object(telegram_bot, "TELEGRAM_BOT_TOKEN", "fake-token"), patch.object(
            telegram_bot, "ADMIN_IDS", set()
        ), patch.object(telegram_bot, "ALLOW_ALL_USERS", False):
            with pytest.raises(RuntimeError) as exc_info:
                telegram_bot.validate_configuration()
            assert "TELEGRAM_ADMIN_IDS" in str(exc_info.value) or "ALLOW_ALL" in str(exc_info.value)


class TestCallBackendChat:
    """Tests for call_backend_chat with mocked httpx."""

    @pytest.mark.asyncio
    async def test_returns_reply_on_success(self):
        """On 200 response with reply, call_backend_chat returns the reply text."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"reply": "Hello from CATBot"}
        mock_response.raise_for_status = MagicMock()

        with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await telegram_bot.call_backend_chat(123, "Hi")
            assert result == "Hello from CATBot"

    @pytest.mark.asyncio
    async def test_includes_attachments_in_backend_payload(self):
        """When attachments are provided, call_backend_chat forwards them unchanged to the backend."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"reply": "Hello from CATBot"}

        with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            attachments = [{"filename": "brief.txt", "content_base64": "aGVsbG8=", "mime_type": "text/plain"}]
            await telegram_bot.call_backend_chat(123, "Review this", attachments=attachments)

        payload = mock_client.post.await_args.kwargs["json"]
        assert payload["attachments"] == attachments

    @pytest.mark.asyncio
    async def test_raises_on_non_200(self):
        """On non-200 response, call_backend_chat raises RuntimeError."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError):
                await telegram_bot.call_backend_chat(123, "Hi")


class TestClearBackendHistory:
    """Tests for clear_backend_history with mocked httpx."""

    @pytest.mark.asyncio
    async def test_returns_true_on_200(self):
        """On 200 or 204, clear_backend_history returns True."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await telegram_bot.clear_backend_history(123)
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_on_non_2xx(self):
        """On status other than 200/204, clear_backend_history returns False."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await telegram_bot.clear_backend_history(123)
            assert result is False


class TestHandleAttachment:
    """Tests for Telegram document/photo attachment handling."""

    @pytest.mark.asyncio
    async def test_document_attachment_is_forwarded_to_backend(self):
        update = MagicMock()
        update.effective_chat.id = 456
        update.message.caption = "Please summarize this"
        update.message.photo = []
        update.message.chat.send_action = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.message.document = MagicMock(
            file_id="file-1",
            file_name="brief.txt",
            file_unique_id="unique-1",
            mime_type="text/plain",
        )
        context = MagicMock()
        tg_file = MagicMock()
        tg_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"hello"))
        context.bot.get_file = AsyncMock(return_value=tg_file)

        with patch("src.integrations.telegram_bot._authorize_or_reject", AsyncMock(return_value=123)), patch(
            "src.integrations.telegram_bot._reply_with_backend_answer",
            AsyncMock(),
        ) as mock_reply:
            await telegram_bot.handle_attachment(update, context)

        args = mock_reply.await_args.args
        assert args[3] == "Please summarize this"
        assert mock_reply.await_args.kwargs["attachments"][0]["filename"] == "brief.txt"
        assert mock_reply.await_args.kwargs["attachments"][0]["mime_type"] == "text/plain"
        assert mock_reply.await_args.kwargs["attachments"][0]["content_base64"] == "aGVsbG8="

    @pytest.mark.asyncio
    async def test_document_attachment_rejects_known_oversize_before_download(self):
        update = MagicMock()
        update.message.caption = "Please summarize this"
        update.message.photo = []
        update.message.chat.send_action = AsyncMock()
        update.message.reply_text = AsyncMock()
        update.message.document = MagicMock(
            file_id="file-oversize",
            file_name="large.txt",
            file_unique_id="unique-large",
            mime_type="text/plain",
            file_size=11,
        )
        context = MagicMock()
        context.bot.get_file = AsyncMock()

        with patch("src.integrations.telegram_bot._authorize_or_reject", AsyncMock(return_value=123)), patch.object(
            telegram_bot,
            "MAX_ATTACHMENT_BYTES",
            10,
        ):
            await telegram_bot.handle_attachment(update, context)

        context.bot.get_file.assert_not_called()
        update.message.reply_text.assert_awaited_once()
        assert "too large" in update.message.reply_text.await_args.args[0].lower()


class TestHandleVoice:
    """Tests for Telegram voice handling."""

    @pytest.mark.asyncio
    async def test_voice_in_disabled_returns_before_download(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.message.voice = MagicMock(file_id="voice-1", duration=1)
        update.message.audio = None
        context = MagicMock()
        context.bot.get_file = AsyncMock()

        with patch("src.integrations.telegram_bot._authorize_or_reject", AsyncMock(return_value=123)), patch.object(
            telegram_bot,
            "VOICE_IN_ENABLED",
            False,
        ):
            await telegram_bot.handle_voice(update, context)

        context.bot.get_file.assert_not_called()
        update.message.reply_text.assert_awaited_once_with("Voice transcription is disabled for this bot.")

    @pytest.mark.asyncio
    async def test_voice_rejects_known_oversize_before_download(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.message.voice = MagicMock(file_id="voice-1", duration=1, file_size=11)
        update.message.audio = None
        context = MagicMock()
        context.bot.get_file = AsyncMock()

        with patch("src.integrations.telegram_bot._authorize_or_reject", AsyncMock(return_value=123)), patch.object(
            telegram_bot,
            "MAX_ATTACHMENT_BYTES",
            10,
        ):
            await telegram_bot.handle_voice(update, context)

        context.bot.get_file.assert_not_called()
        update.message.reply_text.assert_awaited_once()
        assert "too large" in update.message.reply_text.await_args.args[0].lower()


class TestBackendHeaders:
    """Tests for _backend_headers (TELEGRAM_SECRET)."""

    def test_empty_when_secret_unset(self):
        """_backend_headers returns empty dict when TELEGRAM_SECRET is not set."""
        with patch.object(telegram_bot, "TELEGRAM_SECRET", None):
            assert telegram_bot._backend_headers() == {}

    def test_includes_x_telegram_secret_when_set(self):
        """_backend_headers includes X-Telegram-Secret when TELEGRAM_SECRET is set."""
        with patch.object(telegram_bot, "TELEGRAM_SECRET", "my-secret"):
            assert telegram_bot._backend_headers() == {"X-Telegram-Secret": "my-secret"}


class TestStatusPoller:
    """Tests for backend-driven status polling."""

    @pytest.mark.asyncio
    async def test_status_poller_sends_message_on_new_seq(self):
        """Status poller forwards status when seq advances."""
        bot = MagicMock()
        bot.send_message = AsyncMock()
        stop_event = asyncio.Event()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "found": True,
            "event": {"seq": 1, "state": "Working: test"},
        }

        with patch.object(telegram_bot, "STATUS_UPDATE_INTERVAL", 0.01):
            with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                task = asyncio.create_task(
                    telegram_bot._poll_status_updates(
                        bot,
                        chat_id=123,
                        stop_event=stop_event,
                        conversation_id="123",
                        request_id="req-1",
                    )
                )
                await asyncio.sleep(0.03)
                stop_event.set()
                await task

        assert bot.send_message.call_count >= 1

    @pytest.mark.asyncio
    async def test_status_poller_fetches_immediately_before_first_interval(self):
        """Status poller should emit the latest status without waiting for the first timeout window."""
        bot = MagicMock()
        bot.send_message = AsyncMock()
        stop_event = asyncio.Event()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "found": True,
            "event": {"seq": 1, "state": "On it. I'm looking for the best sources now."},
        }

        with patch.object(telegram_bot, "STATUS_UPDATE_INTERVAL", 30.0):
            with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                task = asyncio.create_task(
                    telegram_bot._poll_status_updates(
                        bot,
                        chat_id=123,
                        stop_event=stop_event,
                        conversation_id="123",
                        request_id="req-1",
                    )
                )
                await asyncio.sleep(0.01)
                stop_event.set()
                await task

        bot.send_message.assert_awaited_once_with(
            chat_id=123,
            text="On it. I'm looking for the best sources now.",
        )

    @pytest.mark.asyncio
    async def test_status_poller_skips_when_not_found(self):
        """Status poller does not send when backend returns found=false."""
        bot = MagicMock()
        bot.send_message = AsyncMock()
        stop_event = asyncio.Event()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"found": False}

        with patch.object(telegram_bot, "STATUS_UPDATE_INTERVAL", 0.01):
            with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client_cls.return_value = mock_client

                task = asyncio.create_task(
                    telegram_bot._poll_status_updates(
                        bot,
                        chat_id=123,
                        stop_event=stop_event,
                        conversation_id="123",
                        request_id="req-1",
                    )
                )
                await asyncio.sleep(0.03)
                stop_event.set()
                await task

        bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_status_poller_skips_duplicate_heartbeats(self):
        """Status poller suppresses repeated heartbeat states to avoid spam."""
        bot = MagicMock()
        bot.send_message = AsyncMock()
        stop_event = asyncio.Event()

        response_1 = MagicMock()
        response_1.status_code = 200
        response_1.json.return_value = {
            "found": True,
            "event": {"seq": 1, "state": "On it. I'm getting started now.", "type": "update"},
        }
        response_2 = MagicMock()
        response_2.status_code = 200
        response_2.json.return_value = {
            "found": True,
            "event": {"seq": 2, "state": "On it. I'm getting started now.", "type": "heartbeat"},
        }

        with patch.object(telegram_bot, "STATUS_UPDATE_INTERVAL", 0.01):
            with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=[response_1, response_2, response_2, response_2])
                mock_client_cls.return_value = mock_client

                task = asyncio.create_task(
                    telegram_bot._poll_status_updates(
                        bot,
                        chat_id=123,
                        stop_event=stop_event,
                        conversation_id="123",
                        request_id="req-1",
                    )
                )
                await asyncio.sleep(0.05)
                stop_event.set()
                await task

        sent_texts = [kwargs.get("text") for _, kwargs in bot.send_message.await_args_list]
        assert "On it. I'm getting started now." in sent_texts
        assert sent_texts.count("On it. I'm getting started now.") == 1

    @pytest.mark.asyncio
    async def test_status_poller_skips_duplicate_updates(self):
        """Status poller suppresses repeated update states, not just heartbeat repeats."""
        bot = MagicMock()
        bot.send_message = AsyncMock()
        stop_event = asyncio.Event()

        response_1 = MagicMock()
        response_1.status_code = 200
        response_1.json.return_value = {
            "found": True,
            "event": {"seq": 1, "state": "On it. I'm running that workflow now.", "type": "update"},
        }
        response_2 = MagicMock()
        response_2.status_code = 200
        response_2.json.return_value = {
            "found": True,
            "event": {"seq": 2, "state": "On it. I'm running that workflow now.", "type": "update"},
        }

        with patch.object(telegram_bot, "STATUS_UPDATE_INTERVAL", 0.01):
            with patch("src.integrations.telegram_bot.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(side_effect=[response_1, response_2, response_2, response_2])
                mock_client_cls.return_value = mock_client

                task = asyncio.create_task(
                    telegram_bot._poll_status_updates(
                        bot,
                        chat_id=123,
                        stop_event=stop_event,
                        conversation_id="123",
                        request_id="req-1",
                    )
                )
                await asyncio.sleep(0.05)
                stop_event.set()
                await task

        sent_texts = [kwargs.get("text") for _, kwargs in bot.send_message.await_args_list]
        assert sent_texts.count("On it. I'm running that workflow now.") == 1


class TestReplyWithBackendAnswer:
    """Regression tests for status-task cleanup in reply flow."""

    def test_split_telegram_text_reply_breaks_long_text_into_chunks(self):
        text = ("A" * 2500) + "\n" + ("B" * 2500)
        chunks = telegram_bot._split_telegram_text_reply(text, max_chars=4000)
        assert len(chunks) == 2
        assert "".join(chunks) == text
        assert all(len(chunk) <= 4000 for chunk in chunks)

    def test_should_send_voice_reply_skips_transient_planning_text(self):
        assert telegram_bot._should_send_voice_reply(
            "I have the search results. Now I will use those URLs to scrape the content from each one."
        ) is False
        assert telegram_bot._should_send_voice_reply("On it. I'm checking that now.") is False

    def test_should_send_voice_reply_allows_substantive_final_text(self):
        assert telegram_bot._should_send_voice_reply("Here is the scraped summary with the key findings.") is True

    @pytest.mark.asyncio
    async def test_repeated_calls_do_not_propagate_cancelled_error(self):
        """Cancelling status poller should not break subsequent Telegram replies."""
        message = MagicMock()
        message.chat = MagicMock()
        message.chat.send_action = AsyncMock()
        message.reply_text = AsyncMock()

        update = MagicMock()
        update.message = message
        update.effective_chat = MagicMock(id=123)

        context = MagicMock()
        context.bot = MagicMock()

        async def hanging_status_poller(*_args, **_kwargs):
            await asyncio.sleep(3600)

        with patch.object(telegram_bot, "_poll_status_updates", new=hanging_status_poller):
            with patch.object(telegram_bot, "call_backend_chat", new=AsyncMock(return_value="hello")) as mock_chat:
                with patch.object(telegram_bot, "VOICE_OUT_ENABLED", False):
                    await telegram_bot._reply_with_backend_answer(update, context, 123, "first")
                    await telegram_bot._reply_with_backend_answer(update, context, 123, "second")

        assert mock_chat.await_count == 2
        assert message.reply_text.await_count == 2

    @pytest.mark.asyncio
    async def test_voice_reply_is_skipped_for_transient_planning_text(self):
        message = MagicMock()
        message.chat = MagicMock()
        message.chat.send_action = AsyncMock()
        message.reply_text = AsyncMock()
        message.reply_voice = AsyncMock()
        message.reply_audio = AsyncMock()

        update = MagicMock()
        update.message = message
        update.effective_chat = MagicMock(id=123)

        context = MagicMock()
        context.bot = MagicMock()

        with patch.object(
            telegram_bot,
            "call_backend_chat",
            new=AsyncMock(return_value="I have the search results. Now I will use those URLs to scrape the content from each one."),
        ), patch.object(telegram_bot, "_poll_status_updates", new=AsyncMock()), patch.object(
            telegram_bot, "_stop_status_updates", new=AsyncMock()
        ) as mock_stop, patch.object(telegram_bot, "VOICE_OUT_ENABLED", True), patch.object(
            telegram_bot, "call_backend_tts", new=AsyncMock()
        ) as mock_tts:
            await telegram_bot._reply_with_backend_answer(update, context, 123, "search")

        message.reply_text.assert_awaited_once()
        mock_stop.assert_awaited_once()
        mock_tts.assert_not_awaited()
        message.reply_voice.assert_not_called()
        message.reply_audio.assert_not_called()

    @pytest.mark.asyncio
    async def test_voice_reply_runs_in_background_without_blocking_text_reply(self):
        message = MagicMock()
        message.chat = MagicMock()
        message.chat.send_action = AsyncMock()
        message.reply_text = AsyncMock()
        message.reply_voice = AsyncMock()
        message.reply_audio = AsyncMock()

        update = MagicMock()
        update.message = message
        update.effective_chat = MagicMock(id=123)

        context = MagicMock()
        context.bot = MagicMock()

        tts_started = asyncio.Event()
        release_tts = asyncio.Event()

        async def slow_tts(_text: str):
            tts_started.set()
            await release_tts.wait()
            return b"OggS\x00OpusHead", "audio/ogg; codecs=opus"

        with patch.object(
            telegram_bot,
            "call_backend_chat",
            new=AsyncMock(return_value="Here is the scraped summary with the key findings."),
        ), patch.object(telegram_bot, "_poll_status_updates", new=AsyncMock()), patch.object(
            telegram_bot, "_stop_status_updates", new=AsyncMock()
        ), patch.object(telegram_bot, "VOICE_OUT_ENABLED", True), patch.object(
            telegram_bot, "call_backend_tts", new=slow_tts
        ):
            await asyncio.wait_for(
                telegram_bot._reply_with_backend_answer(update, context, 123, "search"),
                timeout=0.1,
            )
            await asyncio.wait_for(tts_started.wait(), timeout=0.1)
            message.reply_voice.assert_not_awaited()
            release_tts.set()
            if telegram_bot._background_tasks:
                await asyncio.gather(*tuple(telegram_bot._background_tasks), return_exceptions=True)

        message.reply_text.assert_awaited_once_with("Here is the scraped summary with the key findings.")
        message.reply_voice.assert_awaited_once()
        message.reply_audio.assert_not_called()

    @pytest.mark.asyncio
    async def test_long_final_reply_is_sent_in_multiple_messages(self):
        message = MagicMock()
        message.chat = MagicMock()
        message.chat.send_action = AsyncMock()
        message.reply_text = AsyncMock()

        update = MagicMock()
        update.message = message
        update.effective_chat = MagicMock(id=123)

        context = MagicMock()
        context.bot = MagicMock()

        long_reply = ("A" * 2500) + "\n" + ("B" * 2500)

        with patch.object(
            telegram_bot,
            "call_backend_chat",
            new=AsyncMock(return_value=long_reply),
        ), patch.object(telegram_bot, "_poll_status_updates", new=AsyncMock()), patch.object(
            telegram_bot, "_stop_status_updates", new=AsyncMock()
        ), patch.object(telegram_bot, "VOICE_OUT_ENABLED", False):
            await telegram_bot._reply_with_backend_answer(update, context, 123, "search")

        sent_parts = [call.args[0] for call in message.reply_text.await_args_list]
        assert len(sent_parts) == 2
        assert "".join(sent_parts) == long_reply
        assert all(len(part) <= telegram_bot.TELEGRAM_TEXT_MESSAGE_LIMIT for part in sent_parts)

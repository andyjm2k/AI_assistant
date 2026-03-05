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
            "event": {"seq": 1, "state": "Working: contacting model", "type": "update"},
        }
        response_2 = MagicMock()
        response_2.status_code = 200
        response_2.json.return_value = {
            "found": True,
            "event": {"seq": 2, "state": "Working: contacting model", "type": "heartbeat"},
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
        assert "Working: contacting model" in sent_texts
        assert sent_texts.count("Working: contacting model") == 1


class TestReplyWithBackendAnswer:
    """Regression tests for status-task cleanup in reply flow."""

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

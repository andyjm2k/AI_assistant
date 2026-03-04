"""
Unit and API tests for proxy server Telegram endpoints.
Covers: POST /v1/telegram/chat (success, validation, api key, secret), DELETE /v1/telegram/chat/{id}.
Uses mocks for external OpenAI and memory; no real API calls.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _get_client():
    """Return TestClient for proxy_server app."""
    from src.servers.proxy_server import app
    return TestClient(app)


def _mock_openai_response(reply_text: str = "Mocked reply"):
    """Build a mock response body for OpenAI-compatible chat."""
    return {
        "choices": [{"message": {"content": reply_text}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


class TestTelegramChatEndpoint:
    """Tests for POST /v1/telegram/chat."""

    def test_missing_message_returns_400(self):
        """POST with empty or missing message returns 400."""
        client = _get_client()
        resp = client.post(
            "/v1/telegram/chat",
            json={"message": ""},
        )
        assert resp.status_code == 400
        assert "message" in (resp.json().get("detail") or resp.text).lower()

    def test_valid_request_returns_200_and_reply(self):
        """POST with valid message and mocked OpenAI returns 200 and reply in body."""
        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response("Hello from CATBot")

        def getenv(k, d=None):
            if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"):
                return "test-key"
            return os.environ.get(k, d) if d is not None else os.environ.get(k)

        with patch("src.servers.proxy_server.os.getenv", side_effect=getenv):
            with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                mock_client_instance = MagicMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_aclient.return_value = mock_client_instance

                resp = client.post(
                    "/v1/telegram/chat",
                    json={"message": "Hi", "conversation_id": "test-conv"},
                )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "Hello from CATBot"
        assert data.get("conversation_id") == "test-conv"

    def test_valid_request_handles_structured_content_reply(self):
        """POST should coerce list/dict content parts into plain text reply."""
        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "Hello from CATBot"},
                            {"type": "text", "text": "Second line"},
                        ]
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

        def getenv(k, d=None):
            if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"):
                return "test-key"
            return os.environ.get(k, d) if d is not None else os.environ.get(k)

        with patch("src.servers.proxy_server.os.getenv", side_effect=getenv):
            with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                mock_client_instance = MagicMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_aclient.return_value = mock_client_instance

                resp = client.post(
                    "/v1/telegram/chat",
                    json={"message": "Hi", "conversation_id": "structured-conv"},
                )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "Hello from CATBot\nSecond line"
        assert data.get("conversation_id") == "structured-conv"

    def test_no_api_key_returns_503(self):
        """POST when neither OPENAI_API_KEY nor MCP_LLM_OPENAI_API_KEY is set returns 503."""
        client = _get_client()
        with patch("src.servers.proxy_server.os.getenv") as m_getenv:
            m_getenv.side_effect = lambda k, d=None: None if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
            resp = client.post(
                "/v1/telegram/chat",
                json={"message": "Hi"},
            )
        assert resp.status_code == 503
        assert "OPENAI" in resp.text or "MCP_LLM" in resp.text


class TestTelegramClearEndpoint:
    """Tests for DELETE /v1/telegram/chat/{conversation_id}."""

    def test_clear_unknown_id_returns_200_cleared_false(self):
        """DELETE for unknown conversation_id returns 200 with cleared: false."""
        client = _get_client()
        resp = client.delete("/v1/telegram/chat/unknown-id-999")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("conversation_id") == "unknown-id-999"
        assert data.get("cleared") is False

    def test_clear_after_chat_returns_200_cleared_true(self):
        """After a chat with conversation_id, DELETE returns 200 with cleared: true."""
        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response("Hi")

        with patch("src.servers.proxy_server.os.getenv") as m_getenv:
            m_getenv.side_effect = lambda k, d=None: "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
            with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                mock_client_instance = MagicMock()
                mock_client_instance.post = AsyncMock(return_value=mock_response)
                mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                mock_aclient.return_value = mock_client_instance

                client.post(
                    "/v1/telegram/chat",
                    json={"message": "Hi", "conversation_id": "clear-me"},
                )
                resp = client.delete("/v1/telegram/chat/clear-me")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("cleared") is True


class TestTelegramSecret:
    """Tests for TELEGRAM_SECRET validation when set."""

    def test_when_secret_set_missing_header_returns_401(self):
        """When TELEGRAM_SECRET is set, request without secret returns 401."""
        client = _get_client()
        with patch("src.servers.proxy_server.TELEGRAM_SECRET", "my-secret"):
            resp = client.post(
                "/v1/telegram/chat",
                json={"message": "Hi"},
            )
        assert resp.status_code == 401
        assert "secret" in resp.text.lower() or "invalid" in resp.text.lower()

    def test_when_secret_set_correct_header_succeeds(self):
        """When TELEGRAM_SECRET is set, X-Telegram-Secret header allows request."""
        client = _get_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = _mock_openai_response("OK")

        with patch("src.servers.proxy_server.TELEGRAM_SECRET", "my-secret"):
            with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                m_getenv.side_effect = lambda k, d=None: "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                    mock_client_instance = MagicMock()
                    mock_client_instance.post = AsyncMock(return_value=mock_response)
                    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                    mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                    mock_aclient.return_value = mock_client_instance

                    resp = client.post(
                        "/v1/telegram/chat",
                        json={"message": "Hi"},
                        headers={"X-Telegram-Secret": "my-secret"},
                    )
        assert resp.status_code == 200

    def test_delete_when_secret_set_requires_header(self):
        """DELETE when TELEGRAM_SECRET is set requires X-Telegram-Secret."""
        client = _get_client()
        with patch("src.servers.proxy_server.TELEGRAM_SECRET", "my-secret"):
            resp = client.delete("/v1/telegram/chat/some-id")
        assert resp.status_code == 401


class TestTelegramToolsLoop:
    """Tests for Telegram tool loop when TELEGRAM_TOOLS_ENABLED is True."""

    def test_tool_loop_executes_native_tool_calls_and_returns_final_reply(self):
        """When LLM returns native message.tool_calls, proxy executes tools and returns final reply."""
        client = _get_client()
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "webSearch",
                                    "arguments": '{"query": "test query"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        final_response = "Here are the search results: [summary]."
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": final_response}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10},
        }
        post_calls = [mock_first, mock_second]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_second

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {"results": [{"title": "Test", "snippet": "Snippet"}]}
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-native-test"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == final_response
        assert data.get("conversation_id") == "tools-native-test"

    def test_tool_loop_executes_tool_and_returns_final_reply(self):
        """When LLM returns a tool call, proxy executes tool and sends result back; second LLM reply is returned."""
        client = _get_client()
        # First LLM response: tool call
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        # Second LLM response: natural language after seeing tool result
        final_response = "Here are the search results: [summary]."
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": final_response}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10},
        }
        post_calls = [mock_first, mock_second]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_second

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {"results": [{"title": "Test", "snippet": "Snippet"}]}
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-test"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Final reply should be the second LLM response (natural language)
        assert data.get("reply") == final_response
        assert data.get("conversation_id") == "tools-test"

    def test_tool_loop_handles_structured_followup_content(self):
        """Tool-loop follow-up content parts should be normalized to text instead of failing response validation."""
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "Here are the search results."},
                            {"type": "text", "text": "Summary line 2."},
                        ]
                    }
                }
            ],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10},
        }
        post_calls = [mock_first, mock_second]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_second

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {"results": [{"title": "Test", "snippet": "Snippet"}]}
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-structured-test"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "Here are the search results.\nSummary line 2."
        assert data.get("conversation_id") == "tools-structured-test"

    def test_tool_loop_keeps_mixed_final_reply_instead_of_error_fallback(self):
        """
        When follow-up text includes user-facing content plus incidental tool XML,
        the final reply should be delivered (with XML stripped), not replaced by
        the generic tool-error fallback.
        """
        client = _get_client()
        tool_response = '<tool>webSearch</tool>\n<parameters>{"query": "test query"}</parameters>'
        mixed_final = (
            "Here are the search results summary.\n"
            '<tool>webSearch</tool>\n<parameters>{"query":"next query"}</parameters>'
        )
        mock_first = MagicMock()
        mock_first.status_code = 200
        mock_first.json.return_value = {
            "choices": [{"message": {"content": tool_response}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20},
        }
        mock_second = MagicMock()
        mock_second.status_code = 200
        mock_second.json.return_value = {
            "choices": [{"message": {"content": mixed_final}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10},
        }
        post_calls = [mock_first, mock_second]

        def next_response(*args, **kwargs):
            return post_calls.pop(0) if post_calls else mock_second

        with patch("src.servers.proxy_server.TELEGRAM_TOOLS_ENABLED", True):
            try:
                from src.servers import proxy_server as ps
                if getattr(ps, "_telegram_tools", None) is None:
                    pytest.skip("telegram_tools module not available")
            except ImportError:
                pytest.skip("telegram_tools not importable")
            with patch("src.servers.proxy_server._do_proxy_search", new_callable=AsyncMock) as mock_search:
                mock_search.return_value = {"results": [{"title": "Test", "snippet": "Snippet"}]}
                with patch("src.servers.proxy_server.os.getenv") as m_getenv:
                    m_getenv.side_effect = lambda k, d=None: (
                        "test-key" if k in ("OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY") else os.environ.get(k, d)
                    )
                    with patch("src.servers.proxy_server.httpx.AsyncClient") as mock_aclient:
                        mock_client_instance = MagicMock()
                        mock_client_instance.post = AsyncMock(side_effect=next_response)
                        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
                        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
                        mock_aclient.return_value = mock_client_instance

                        resp = client.post(
                            "/v1/telegram/chat",
                            json={"message": "Search for test", "conversation_id": "tools-mixed-final"},
                        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("reply") == "Here are the search results summary."
        assert data.get("reply") != "I wasn't able to get that information just now. Please try again or rephrase your question."


class TestIsTodoListQuery:
    """Tests for _is_todo_list_query (skip memory injection for todo-list requests)."""

    def test_todo_list_phrases_return_true(self):
        """Phrases asking for current todo list return True."""
        from src.servers.proxy_server import _is_todo_list_query
        assert _is_todo_list_query("What's on my todo list?") is True
        assert _is_todo_list_query("Show my tasks") is True
        assert _is_todo_list_query("list my tasks") is True
        assert _is_todo_list_query("my todo list") is True
        assert _is_todo_list_query("what are my tasks") is True
        assert _is_todo_list_query("what is due today?") is True
        assert _is_todo_list_query("show overdue tasks") is True

    def test_unrelated_queries_return_false(self):
        """Unrelated messages return False."""
        from src.servers.proxy_server import _is_todo_list_query
        assert _is_todo_list_query("What's the weather?") is False
        assert _is_todo_list_query("Search for AI news") is False
        assert _is_todo_list_query("") is False


class TestAutoMemorySearchHelpers:
    """Tests for Telegram auto-memory relevance helper logic."""

    def test_is_memory_context_question_true_for_opinion_prompt(self):
        from src.servers.proxy_server import _is_memory_context_question
        assert _is_memory_context_question("What do you think about Rust for backend APIs?") is True

    def test_is_memory_context_question_false_for_action_prompt(self):
        from src.servers.proxy_server import _is_memory_context_question
        assert _is_memory_context_question("Search for information about Rust web frameworks") is False

    def test_filter_high_relevance_memories_drops_low_confidence_set(self):
        from src.servers.proxy_server import _filter_high_relevance_memories
        memories = [
            {"text": "A", "similarity": 0.60},
            {"text": "B", "similarity": 0.58},
        ]
        assert _filter_high_relevance_memories(memories) == []

    def test_filter_high_relevance_memories_keeps_close_top_hits(self):
        from src.servers.proxy_server import _filter_high_relevance_memories
        memories = [
            {"text": "Top", "similarity": 0.83},
            {"text": "Close", "similarity": 0.78},
            {"text": "Far", "similarity": 0.62},
        ]
        out = _filter_high_relevance_memories(memories)
        assert [m["text"] for m in out] == ["Top", "Close"]


class TestResolveTodoUserForTelegram:
    """Tests for _resolve_todo_user_for_telegram (Telegram -> app username linking)."""

    def test_linked_user_id_returns_app_username(self):
        """When links file maps Telegram user_id to username, resolver returns username."""
        from src.servers import proxy_server as ps
        links_content = '{"6644154165": "andyjm2k"}'
        with patch.object(ps, "TELEGRAM_USER_LINKS_FILE") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = links_content
            out = ps._resolve_todo_user_for_telegram("6644154165", "6644154165")
        assert out == "andyjm2k"

    def test_no_link_returns_conversation_id(self):
        """When no mapping exists, resolver returns conversation_id (or user_id)."""
        from src.servers import proxy_server as ps
        with patch.object(ps, "TELEGRAM_USER_LINKS_FILE") as mock_path:
            mock_path.exists.return_value = False
            out = ps._resolve_todo_user_for_telegram("6644154165", "6644154165")
        assert out == "6644154165"

    def test_user_id_normalized_to_string(self):
        """user_id sent as number is normalized to string for lookup."""
        from src.servers import proxy_server as ps
        links_content = '{"6644154165": "andyjm2k"}'
        with patch.object(ps, "TELEGRAM_USER_LINKS_FILE") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = links_content
            # Simulate Pydantic/JSON giving int
            out = ps._resolve_todo_user_for_telegram("6644154165", 6644154165)
        assert out == "andyjm2k"


class TestTelegramTaskExecutionNotifications:
    """Tests for Telegram notification helpers used by task execution completion flow."""

    def test_resolve_telegram_chat_ids_for_todo_user_reverses_links(self):
        from src.servers import proxy_server as ps
        links_content = '{"6644154165": "andyjm2k", "-100123": "andyjm2k", "group_alpha": "andyjm2k"}'
        with patch.object(ps, "TELEGRAM_USER_LINKS_FILE") as mock_path:
            mock_path.exists.return_value = True
            mock_path.read_text.return_value = links_content
            out = ps._resolve_telegram_chat_ids_for_todo_user("andyjm2k")
        assert out == ["6644154165", "-100123"]

    def test_task_execution_register_telegram_target_adds_chat_id_once(self):
        from src.servers import proxy_server as ps
        user_key = "notify-user-1"
        ps.task_execution_state[user_key] = {"task_id": 1, "status": "executing", "telegram_chat_ids": ["111"]}
        try:
            ok1 = ps._task_execution_register_telegram_target(user_key, "222")
            ok2 = ps._task_execution_register_telegram_target(user_key, "222")
            assert ok1 is True
            assert ok2 is True
            state = ps._get_task_run_state(user_key, 1)
            assert state is not None
            assert state["telegram_chat_ids"] == ["111", "222"]
        finally:
            ps.task_execution_state.pop(user_key, None)

    @pytest.mark.asyncio
    async def test_run_task_loop_background_notifies_on_scheduled_completion(self):
        from src.servers import proxy_server as ps

        class _Executor:
            async def run_loop(self):
                return (ps.STATUS_AWAITING_CONFIRMATION, "Execution complete.")

        user_key = "notify-user-2"
        executor = _Executor()
        ps.task_execution_state[user_key] = {
            "task_id": 3,
            "status": ps.STATUS_EXECUTING,
            "executor": executor,
            "message": None,
            "task_description": "Scheduled task demo",
            "is_scheduled": True,
            "telegram_chat_ids": ["6644154165"],
        }
        try:
            with patch.object(ps, "_write_task_exec_response_to_scratch") as mock_write:
                with patch.object(ps, "_send_telegram_bot_message", new=AsyncMock(return_value=True)) as mock_send:
                    with patch.object(ps, "_todo_store") as mock_store:
                        mock_store.complete_task.return_value = {
                            "rescheduled": True,
                            "next_run_at": "2026-03-02T09:00:00+00:00",
                        }
                        await ps._run_task_loop_background(user_key, 3, executor)
            assert user_key not in ps.task_execution_state
            mock_store.complete_task.assert_called_once_with(user_key, 3)
            mock_write.assert_called_once()
            mock_send.assert_awaited_once()
        finally:
            ps.task_execution_state.pop(user_key, None)

    @pytest.mark.asyncio
    async def test_run_task_loop_background_records_learning_outcome(self):
        from src.servers import proxy_server as ps

        class _Executor:
            async def run_loop(self):
                return (ps.STATUS_AWAITING_CONFIRMATION, "I have finished the work for this task.")

            def get_run_diagnostics(self):
                return {
                    "iterations": 2,
                    "max_iterations": 20,
                    "elapsed_seconds": 1.5,
                    "tool_usage_counts": {"write_file": 1},
                    "tool_success_count": 1,
                    "tool_failure_count": 0,
                    "tool_error_messages": [],
                    "last_error": None,
                }

        user_key = "learning-user-1"
        executor = _Executor()
        ps.task_execution_state[user_key] = {
            "task_id": 2,
            "status": ps.STATUS_EXECUTING,
            "executor": executor,
            "message": None,
            "task_description": "Write summary file",
            "is_scheduled": False,
            "telegram_chat_ids": [],
        }
        mock_memory_manager = MagicMock()
        mock_memory_manager.record_task_outcome = AsyncMock(return_value={"outcome": "success"})
        try:
            with patch.object(ps, "MEMORY_AVAILABLE", True):
                with patch.object(ps, "memory_manager", mock_memory_manager):
                    with patch.object(ps, "_write_task_exec_response_to_scratch"):
                        with patch.object(ps, "_maybe_notify_telegram_task_completion", new=AsyncMock(return_value=None)):
                            await ps._run_task_loop_background(user_key, 2, executor)
            mock_memory_manager.record_task_outcome.assert_awaited_once()
            kwargs = mock_memory_manager.record_task_outcome.await_args.kwargs
            assert kwargs.get("task_description") == "Write summary file"
            assert kwargs.get("status") == ps.STATUS_AWAITING_CONFIRMATION
        finally:
            ps.task_execution_state.pop(user_key, None)

    @pytest.mark.asyncio
    async def test_run_task_loop_background_clears_unscheduled_terminal_state(self):
        from src.servers import proxy_server as ps

        class _Executor:
            async def run_loop(self):
                return (ps.STATUS_AWAITING_CONFIRMATION, "Finished run.")

        user_key = "terminal-clear-user"
        executor = _Executor()
        ps.task_execution_state[user_key] = {
            "task_id": 4,
            "status": ps.STATUS_EXECUTING,
            "executor": executor,
            "message": None,
            "task_description": "Terminal clear test",
            "is_scheduled": False,
            "telegram_chat_ids": [],
        }
        try:
            with patch.object(ps, "_write_task_exec_response_to_scratch"):
                with patch.object(ps, "_maybe_notify_telegram_task_completion", new=AsyncMock(return_value=None)):
                    await ps._run_task_loop_background(user_key, 4, executor)
            assert user_key not in ps.task_execution_state
        finally:
            ps.task_execution_state.pop(user_key, None)

    def test_task_execute_cancel_marks_state_cancelled_immediately(self):
        from src.servers import proxy_server as ps

        class _Executor:
            def __init__(self):
                self.cancelled = False

            def request_cancel(self):
                self.cancelled = True

        user_key = "cancel-now-user"
        executor = _Executor()
        ps.task_execution_state[user_key] = {
            "task_id": 9,
            "status": ps.STATUS_EXECUTING,
            "executor": executor,
            "message": None,
        }
        try:
            ok, msg, cancelled_task_id = ps._task_execute_cancel(user_key)
            assert ok is True
            assert "Cancellation requested" in msg
            assert cancelled_task_id == 9
            assert executor.cancelled is True
            state = ps._get_task_run_state(user_key, 9)
            assert state is not None
            assert state["status"] == ps.STATUS_CANCELLED
        finally:
            ps.task_execution_state.pop(user_key, None)

    def test_task_execution_status_clears_terminal_state(self):
        from src.servers import proxy_server as ps

        user_key = "status-clear-user"
        ps.task_execution_state[user_key] = {
            "task_id": 2,
            "status": ps.STATUS_CANCELLED,
            "message": "Cancellation requested.",
        }
        out = ps._task_execution_status(user_key)
        assert out is None
        assert user_key not in ps.task_execution_state

    def test_task_execution_status_lists_multiple_active_task_ids(self):
        from src.servers import proxy_server as ps

        user_key = "status-multi-user"
        ps.task_execution_state[user_key] = {
            "runs": {
                2: {"task_id": 2, "status": ps.STATUS_EXECUTING, "message": "Running task 2"},
                4: {"task_id": 4, "status": ps.STATUS_PAUSED_AWAITING_FEEDBACK, "message": "Need input"},
            }
        }
        try:
            out = ps._task_execution_status(user_key)
            assert out is not None
            assert out.get("status") == "multiple"
            assert out.get("task_ids") == [2, 4]
        finally:
            ps.task_execution_state.pop(user_key, None)

    def test_task_execute_cancel_requires_task_id_when_multiple_active(self):
        from src.servers import proxy_server as ps

        class _Executor:
            def request_cancel(self):
                return None

        user_key = "cancel-multi-user"
        ps.task_execution_state[user_key] = {
            "runs": {
                1: {"task_id": 1, "status": ps.STATUS_EXECUTING, "executor": _Executor()},
                2: {"task_id": 2, "status": ps.STATUS_EXECUTING, "executor": _Executor()},
            }
        }
        try:
            ok, msg, cancelled_task_id = ps._task_execute_cancel(user_key)
            assert ok is False
            assert cancelled_task_id is None
            assert "Multiple active tasks" in msg
        finally:
            ps.task_execution_state.pop(user_key, None)


class TestTelegramFileSendSecurity:
    """Tests for Telegram scratch-file sending preconditions."""

    @pytest.mark.asyncio
    async def test_send_telegram_file_internal_does_not_require_proxy_auth(self, monkeypatch):
        """send file helper should proceed without proxy auth checks and validate next requirements."""
        from src.servers import proxy_server as ps
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        out = await ps._send_telegram_file_internal(
            chat_id="123456",
            filename="report.txt",
        )
        assert out.get("success") is False
        assert "telegram_bot_token is not configured" in out.get("message", "").lower()


class TestPhilosopherFileTools:
    """Tests for file manipulation tools in philosopher mode (get_all_available_tools + execute_tool_for_philosopher)."""

    @pytest.mark.asyncio
    async def test_file_tools_included_when_file_ops_available(self):
        """When FILE_OPS_AVAILABLE is True, get_all_available_tools includes read_file, write_file, list_files, delete_file."""
        from src.servers import proxy_server as ps
        with patch.object(ps, "MCP_AVAILABLE", False):
            tools = await ps.get_all_available_tools()
        names = [t.get("name") for t in tools]
        assert "read_file" in names
        assert "write_file" in names
        assert "list_files" in names
        assert "delete_file" in names

    @pytest.mark.asyncio
    async def test_overlapping_filesystem_skill_tools_filtered_from_llm_tool_list(self):
        """Skill framework filesystem file tools should be hidden when built-in file tools are available."""
        from src.servers import proxy_server as ps

        raw_tools = [
            {"name": "filesystem.list_files", "description": "list"},
            {"name": "filesystem.read_text", "description": "read"},
            {"name": "filesystem.write_text", "description": "write"},
            {"name": "core.ping", "description": "ping"},
        ]
        with patch.object(ps, "FILE_OPS_AVAILABLE", True):
            filtered = ps._filter_overlapping_file_skill_tools(raw_tools, openai_schema=False)
        names = [item.get("name") for item in filtered]
        assert "core.ping" in names
        assert "filesystem.list_files" not in names
        assert "filesystem.read_text" not in names
        assert "filesystem.write_text" not in names

    @pytest.mark.asyncio
    async def test_execute_list_files_returns_string(self):
        """execute_tool_for_philosopher list_files returns a string (empty workspace or file list)."""
        from src.servers import proxy_server as ps
        result = await ps.execute_tool_for_philosopher("list_files", {})
        assert isinstance(result, str)
        assert "scratch" in result.lower() or "empty" in result.lower() or "Files" in result

    @pytest.mark.asyncio
    async def test_execute_list_files_truncates_when_limit_set(self, monkeypatch):
        """execute_tool_for_philosopher list_files should cap rendered rows for large directories."""
        from src.servers import proxy_server as ps
        monkeypatch.setenv("LIST_FILES_TOOL_MAX_ENTRIES", "3")

        fake_result = {
            "success": True,
            "files": [
                {"name": "images", "type": "directory"},
                {"name": "a.txt", "size": 1},
                {"name": "b.txt", "size": 2},
                {"name": "c.txt", "size": 3},
                {"name": "d.txt", "size": 4},
            ],
        }

        with patch.object(ps, "_list_files_internal", new=AsyncMock(return_value=fake_result)):
            result = await ps.execute_tool_for_philosopher("list_files", {})
        assert isinstance(result, str)
        assert "images/ [dir]" in result
        assert "a.txt (1 bytes)" in result
        assert "b.txt (2 bytes)" in result
        assert "... and 2 more files." in result
        assert "c.txt (3 bytes)" not in result
        assert "d.txt (4 bytes)" not in result

    @pytest.mark.asyncio
    async def test_execute_list_files_forwards_path_and_recursive(self):
        """execute_tool_for_philosopher list_files forwards path/recursive to backend list helper."""
        from src.servers import proxy_server as ps

        fake_result = {
            "success": True,
            "files": [{"name": "images/a.png", "size": 10}],
        }

        with patch.object(ps, "_list_files_internal", new=AsyncMock(return_value=fake_result)) as mock_list:
            result = await ps.execute_tool_for_philosopher(
                "list_files",
                {"path": "images", "recursive": "true"},
            )
        mock_list.assert_awaited_once_with(path="images", recursive=True)
        assert isinstance(result, str)
        assert "images/a.png (10 bytes)" in result

    @pytest.mark.asyncio
    async def test_run_workflow_tool_included_when_autogen_available(self):
        """When AUTOGEN_AVAILABLE is True, get_all_available_tools includes runWorkflow."""
        from src.servers import proxy_server as ps
        with patch.object(ps, "MCP_AVAILABLE", False):
            tools = await ps.get_all_available_tools()
        names = [t.get("name") for t in tools]
        if getattr(ps, "AUTOGEN_AVAILABLE", False):
            assert "runWorkflow" in names
        # If AutoGen not available, runWorkflow may be absent; test just ensures no crash

    @pytest.mark.asyncio
    async def test_execute_run_workflow_requires_content_prompt(self):
        """execute_tool_for_philosopher runWorkflow without contentPrompt returns error message."""
        from src.servers import proxy_server as ps
        result = await ps.execute_tool_for_philosopher("runWorkflow", {})
        assert isinstance(result, str)
        assert "contentPrompt" in result or "required" in result.lower()

    @pytest.mark.asyncio
    async def test_run_deep_research_tool_included_when_browser_use_configured(self):
        """When MCP_BROWSER_USE_HTTP_URL is set, get_all_available_tools includes run_deep_research."""
        from src.servers import proxy_server as ps
        with patch.object(ps, "MCP_AVAILABLE", False):
            with patch.object(ps, "MCP_BROWSER_USE_HTTP_URL", "http://127.0.0.1:8383/mcp"):
                tools = await ps.get_all_available_tools()
        names = [t.get("name") for t in tools]
        assert "run_deep_research" in names

    @pytest.mark.asyncio
    async def test_execute_run_deep_research_requires_research_task(self):
        """execute_tool_for_philosopher run_deep_research without research_task returns error."""
        from src.servers import proxy_server as ps
        result = await ps.execute_tool_for_philosopher("run_deep_research", {})
        assert isinstance(result, str)
        assert "research_task" in result or "researchTask" in result or "required" in result.lower()


class TestProxyFetchUrls:
    """Tests for POST /v1/proxy/fetch with optional urls (scrape-with-retry)."""

    def test_fetch_with_urls_tries_until_success(self):
        """POST with urls list tries each URL until one succeeds."""
        from src.servers import proxy_server as ps
        client = _get_client()
        call_log = []

        async def mock_fetch(url, **kwargs):
            call_log.append(url)
            if "fail" in url:
                raise Exception("404 Not Found")
            return {"content": "Content from " + url}

        with patch.object(ps, "_do_proxy_fetch", new=AsyncMock(side_effect=mock_fetch)):
            resp = client.post(
                "/v1/proxy/fetch",
                json={"urls": ["https://fail.first/page", "https://ok.second/page"]},
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data.get("content") == "Content from https://ok.second/page"
        assert len(call_log) == 2

    def test_fetch_with_urls_retries_on_http_exception(self):
        """POST with urls retries on HTTPException failures from _do_proxy_fetch."""
        from src.servers import proxy_server as ps
        client = _get_client()

        async def mock_fetch(url, **kwargs):
            if "fail" in url:
                raise ps.HTTPException(status_code=500, detail="temporary failure")
            return {"content": "Content from " + url}

        with patch.object(ps, "_do_proxy_fetch", new=AsyncMock(side_effect=mock_fetch)):
            resp = client.post(
                "/v1/proxy/fetch",
                json={"urls": ["https://fail.first/page", "https://ok.second/page"]},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json().get("content") == "Content from https://ok.second/page"

    def test_fetch_with_single_url_unchanged(self):
        """POST with single url still works (backward compatible)."""
        from src.servers import proxy_server as ps
        client = _get_client()
        with patch.object(ps, "_do_proxy_fetch", new=AsyncMock(return_value={"content": "Hello"})):
            resp = client.post("/v1/proxy/fetch", json={"url": "https://example.com"})
        assert resp.status_code == 200
        assert resp.json().get("content") == "Hello"

    def test_fetch_forwards_dynamic_render_parameters(self):
        """POST /v1/proxy/fetch forwards JS-render parameters to _do_proxy_fetch."""
        from src.servers import proxy_server as ps
        client = _get_client()
        with patch.object(ps, "_do_proxy_fetch", new=AsyncMock(return_value={"content": "Hello"})) as mock_fetch:
            resp = client.post(
                "/v1/proxy/fetch",
                json={
                    "url": "https://example.com",
                    "crawl": False,
                    "max_pages": 1,
                    "max_depth": 0,
                    "render_js": True,
                    "render_engine": "playwright",
                    "wait_for_selector": ".status-table",
                    "js_wait_ms": 3500,
                },
            )
        assert resp.status_code == 200, resp.text
        mock_fetch.assert_awaited_once_with(
            "https://example.com",
            crawl=False,
            max_pages=1,
            max_depth=0,
            render_js=True,
            render_engine="playwright",
            wait_for_selector=".status-table",
            js_wait_ms=3500,
        )

    def test_fetch_no_url_no_urls_returns_400(self):
        """POST without url or urls returns 400."""
        client = _get_client()
        resp = client.post("/v1/proxy/fetch", json={})
        assert resp.status_code == 400

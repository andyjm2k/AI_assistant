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

    def test_unrelated_queries_return_false(self):
        """Unrelated messages return False."""
        from src.servers.proxy_server import _is_todo_list_query
        assert _is_todo_list_query("What's the weather?") is False
        assert _is_todo_list_query("Search for AI news") is False
        assert _is_todo_list_query("") is False


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
    async def test_execute_list_files_returns_string(self):
        """execute_tool_for_philosopher list_files returns a string (empty workspace or file list)."""
        from src.servers import proxy_server as ps
        result = await ps.execute_tool_for_philosopher("list_files", {})
        assert isinstance(result, str)
        assert "scratch" in result.lower() or "empty" in result.lower() or "Files" in result

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

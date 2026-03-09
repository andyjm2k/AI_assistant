"""
Unit tests for Telegram tool parsing and execution (src.servers.telegram_tools).
Covers parse_telegram_tool_response (XML, JSON, code-block stripping) and execute_telegram_tool (key tools with mocks).
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.servers import telegram_tools as tg


class TestParseTelegramToolResponse:
    """Tests for parse_telegram_tool_response."""

    def test_valid_xml_returns_name_and_arguments(self):
        """Valid <tool>...</tool><parameters>...</parameters> at top-level returns dict with name and arguments."""
        content = '<tool>webSearch</tool>\n<parameters>\n{"query": "AI news"}\n</parameters>'
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "webSearch"
        assert json.loads(out["arguments"]) == {"query": "AI news"}

    def test_xml_with_leading_text_still_parsed(self):
        """Parser is lenient: tool call is extracted even with leading text (so we can execute it)."""
        content = 'Here is my answer: <tool>webSearch</tool>\n<parameters>{"query": "x"}</parameters>'
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "webSearch"

    def test_xml_with_trailing_text_still_parsed(self):
        """Parser is lenient: tool call is extracted even with trailing text."""
        content = '<tool>webSearch</tool>\n<parameters>{"query": "x"}</parameters> Hope that helps!'
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "webSearch"

    def test_fenced_code_block_containing_tool_ignored(self):
        """Tool tags inside fenced code blocks are stripped and not parsed as real tool call."""
        content = (
            '```\n<tool>webSearch</tool>\n<parameters>{"query": "example"}</parameters>\n```\n'
            '<tool>calculate</tool>\n<parameters>{"expression": "1+1"}</parameters>'
        )
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "calculate"
        assert json.loads(out["arguments"]) == {"expression": "1+1"}

    def test_json_action_content_prompt_returns_run_workflow(self):
        """JSON with action and contentPrompt returns runWorkflow tool."""
        content = '{"action": "runWorkflow", "contentPrompt": "build a todo app"}'
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "runWorkflow"
        assert json.loads(out["arguments"]) == {"contentPrompt": "build a todo app"}

    def test_json_name_arguments_returns_tool(self):
        """JSON with name and arguments (OpenAI-style) returns tool."""
        content = '{"name": "readFile", "arguments": {"filename": "notes.txt"}}'
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "readFile"
        args = json.loads(out["arguments"]) if isinstance(out["arguments"], str) else out["arguments"]
        assert args == {"filename": "notes.txt"}

    def test_empty_content_returns_none(self):
        """Empty or None content returns None."""
        assert tg.parse_telegram_tool_response("") is None
        assert tg.parse_telegram_tool_response(None) is None

    def test_no_tool_tags_returns_none(self):
        """Plain text with no tool format returns None."""
        assert tg.parse_telegram_tool_response("Just a normal reply.") is None


class TestReplyLooksLikeToolCall:
    """Tests for reply_looks_like_tool_call (used to avoid sending raw XML to the user)."""

    def test_raw_tool_xml_returns_true(self):
        """Content containing <tool> and <parameters> is detected as raw tool call."""
        content = '<tool>scrapeWebsite</tool>\n<parameters>{"url": "https://example.com"}</parameters>'
        assert tg.reply_looks_like_tool_call(content) is True

    def test_plain_text_returns_false(self):
        """Normal reply text returns False."""
        assert tg.reply_looks_like_tool_call("Here is the weather for Sydney.") is False

    def test_empty_or_none_returns_false(self):
        """Empty string or None returns False."""
        assert tg.reply_looks_like_tool_call("") is False
        assert tg.reply_looks_like_tool_call(None) is False

    def test_only_tool_tag_returns_false(self):
        """Content with only <tool> (no <parameters>) returns False."""
        assert tg.reply_looks_like_tool_call("<tool>webSearch</tool>") is False

    def test_only_parameters_returns_false(self):
        """Content with only <parameters> (no <tool>) returns False."""
        assert tg.reply_looks_like_tool_call('<parameters>{"q": "x"}</parameters>') is False

    def test_mixed_text_and_tool_xml_returns_false(self):
        """Mixed natural language + tool XML should not be treated as raw tool call."""
        content = (
            "Final answer: done.\n\n"
            '<tool>webSearch</tool>\n<parameters>{"query":"x"}</parameters>'
        )
        assert tg.reply_looks_like_tool_call(content) is False


class TestStripToolCallMarkup:
    """Tests for stripping embedded tool XML from mixed replies."""

    def test_strip_tool_call_markup_preserves_user_text(self):
        content = (
            "Here is the final response.\n"
            '<tool>webSearch</tool>\n<parameters>{"query":"x"}</parameters>\n'
            "Anything else?"
        )
        out = tg.strip_tool_call_markup(content)
        assert "<tool>" not in out
        assert "<parameters>" not in out
        assert "Here is the final response." in out
        assert "Anything else?" in out


class TestToolResultLooksLikeError:
    """Tests for tool_result_looks_like_error (friendly fallback when tool fails)."""

    def test_500_message_returns_true(self):
        """Message containing 500: is treated as error."""
        assert tg.tool_result_looks_like_error("500: Failed to fetch content: Client error '404 Not Found'") is True

    def test_404_in_message_returns_true(self):
        """Message containing 404 is treated as error."""
        assert tg.tool_result_looks_like_error("Client error '404 Not Found' for url 'https://bom.gov.au/...'") is True

    def test_failed_to_fetch_returns_true(self):
        """Message containing 'failed to fetch' is treated as error."""
        assert tg.tool_result_looks_like_error("Failed to fetch content: timeout") is True

    def test_plain_result_returns_false(self):
        """Normal tool result text returns False."""
        assert tg.tool_result_looks_like_error("Fetched content (snippet):\nToday's weather is fine.") is False

    def test_empty_or_none_returns_false(self):
        """Empty or None returns False."""
        assert tg.tool_result_looks_like_error("") is False
        assert tg.tool_result_looks_like_error(None) is False


class TestExecuteTelegramTool:
    """Tests for execute_telegram_tool (async) with mocked dependencies."""

    @pytest.mark.asyncio
    async def test_manage_todo_list_requires_persistent_store(self):
        """manageTodoList without todo_user_key returns failure (old in-memory path disabled)."""
        ctx = {"conversation_id": "cid1", "memory_cache_store": {}}
        r = await tg.execute_telegram_tool("manageTodoList", {"action": "add", "taskDescription": "Buy milk"}, ctx)
        assert r.get("success") is False
        assert "not available" in r.get("message", "").lower() or "persistent" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_manage_todo_list_add_and_list_with_persistent_store(self):
        """manageTodoList with todo_user_key and todo_store module uses persistent store."""
        mock_store = MagicMock()
        mock_store.load_tasks.return_value = []
        ctx = {
            "conversation_id": "cid1",
            "todo_user_key": "user1",
            "memory_cache_store": {},
        }
        with patch.object(tg, "_todo_store_module", mock_store):
            r1 = await tg.execute_telegram_tool(
                "manageTodoList", {"action": "add", "taskDescription": "Buy milk"}, ctx
            )
        assert r1.get("success") is True
        assert "Added task" in r1.get("message", "")
        mock_store.add_task.assert_called_once()
        add_call_args, add_call_kwargs = mock_store.add_task.call_args
        assert add_call_args[:2] == ("user1", "Buy milk")
        assert add_call_kwargs == {"scheduled_for": None, "recurrence": None}
        # List: load_tasks returns the task
        mock_store.load_tasks.return_value = ["Buy milk"]
        with patch.object(tg, "_todo_store_module", mock_store):
            r2 = await tg.execute_telegram_tool("manageTodoList", {"action": "list"}, ctx)
        assert r2.get("success") is True
        assert "Buy milk" in r2.get("message", "")

    @pytest.mark.asyncio
    async def test_manage_todo_list_add_with_schedule_and_recurrence(self):
        """manageTodoList add passes scheduledFor and recurrence to todo_store."""
        mock_store = MagicMock()
        mock_store.load_tasks.return_value = []
        ctx = {"conversation_id": "cid1", "todo_user_key": "user1", "memory_cache_store": {}}
        args = {
            "action": "add",
            "taskDescription": "Water plants",
            "scheduledFor": "2026-03-01T09:00:00+00:00",
            "recurrence": {"frequency": "weekly", "interval": 1},
        }
        with patch.object(tg, "_todo_store_module", mock_store):
            out = await tg.execute_telegram_tool("manageTodoList", args, ctx)
        assert out.get("success") is True
        mock_store.add_task.assert_called_once_with(
            "user1",
            "Water plants",
            scheduled_for="2026-03-01T09:00:00+00:00",
            recurrence={"frequency": "weekly", "interval": 1},
        )

    @pytest.mark.asyncio
    async def test_manage_todo_list_due_uses_due_loader_and_keeps_task_number(self):
        """manageTodoList action=due should use due loader and preserve original task numbering."""
        mock_store = MagicMock()
        mock_store.load_tasks_with_meta.return_value = {
            "tasks": ["Task A", "Task B"],
            "task_items": [
                {"id": "a", "task_id": 1, "description": "Task A"},
                {"id": "b", "task_id": 2, "description": "Task B", "next_run_at": "2026-03-01T09:00:00+00:00"},
            ],
        }
        mock_store.list_due_task_items.return_value = [
            {"id": "b", "task_id": 2, "description": "Task B", "next_run_at": "2026-03-01T09:00:00+00:00"}
        ]
        ctx = {"conversation_id": "cid1", "todo_user_key": "user1", "memory_cache_store": {}}
        with patch.object(tg, "_todo_store_module", mock_store):
            out = await tg.execute_telegram_tool("manageTodoList", {"action": "due"}, ctx)
        assert out.get("success") is True
        assert "due tasks" in out.get("message", "").lower()
        assert "2. Task B" in out.get("message", "")

    @pytest.mark.asyncio
    async def test_manage_todo_list_complete_rescheduled_message(self):
        """manageTodoList complete reports reschedule when complete_task returns rescheduled=True."""
        mock_store = MagicMock()
        mock_store.load_tasks.return_value = ["Pay rent"]
        mock_store.complete_task.return_value = {"rescheduled": True, "next_run_at": "2026-03-01T09:00:00+00:00"}
        ctx = {"conversation_id": "cid1", "todo_user_key": "user1", "memory_cache_store": {}}
        with patch.object(tg, "_todo_store_module", mock_store):
            out = await tg.execute_telegram_tool("manageTodoList", {"action": "complete", "taskId": 1}, ctx)
        assert out.get("success") is True
        assert "rescheduled" in out.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_execute_todo_task_requires_task_id(self):
        """executeTodoTask without taskId returns failure."""
        ctx = {"conversation_id": "c1", "todo_user_key": "u1", "task_execute_start": None}
        r = await tg.execute_telegram_tool("executeTodoTask", {}, ctx)
        assert r.get("success") is False
        assert "Task ID" in r.get("message", "")

    @pytest.mark.asyncio
    async def test_execute_todo_task_calls_start_when_available(self):
        """executeTodoTask with task_execute_start in context calls it."""
        async def mock_start(user_key, task_id, prompt_override):
            return ("executing", "Task execution started. Ask me for status or to cancel.")
        ctx = {"conversation_id": "c1", "todo_user_key": "u1", "task_execute_start": mock_start}
        r = await tg.execute_telegram_tool("executeTodoTask", {"taskId": 1}, ctx)
        assert r.get("success") is True
        assert r.get("status") == "executing"
        assert "started" in r.get("message", "").lower() or "status" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_execute_todo_task_registers_telegram_target_when_callback_present(self):
        """executeTodoTask calls task_execution_register_telegram_target when provided in context."""
        async def mock_start(user_key, task_id, prompt_override):
            return ("executing", "Task execution started.")
        mock_register = MagicMock(return_value=True)
        ctx = {
            "conversation_id": "c1",
            "user_id": "123456789",
            "todo_user_key": "u1",
            "task_execute_start": mock_start,
            "task_execution_register_telegram_target": mock_register,
        }
        r = await tg.execute_telegram_tool("executeTodoTask", {"taskId": 1}, ctx)
        assert r.get("success") is True
        mock_register.assert_called_once_with("u1", "123456789", 1)

    @pytest.mark.asyncio
    async def test_cancel_todo_execution_no_cancel_fn_returns_unavailable(self):
        """cancelTodoExecution when task_execute_cancel not in context returns unavailable."""
        ctx = {"conversation_id": "c1", "todo_user_key": "u1"}
        r = await tg.execute_telegram_tool("cancelTodoExecution", {}, ctx)
        assert r.get("success") is False
        assert "not available" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_cancel_todo_execution_calls_cancel_fn(self):
        """cancelTodoExecution with task_execute_cancel in context calls it and returns message."""
        def mock_cancel(user_key):
            return (True, "Cancellation requested. The task will stop after the current step.")
        ctx = {"conversation_id": "c1", "todo_user_key": "u1", "task_execute_cancel": mock_cancel}
        r = await tg.execute_telegram_tool("cancelTodoExecution", {}, ctx)
        assert r.get("success") is True
        assert "Cancellation" in r.get("message", "") or "stop" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_run_codex_cli_calls_backend(self):
        """runCodexCli uses do_codex and returns summary file info."""
        async def mock_codex(prompt, timeout_seconds=None):
            return {
                "success": True,
                "summaryFile": "codex_run_2026-01-01_00-00-00_abcd.txt",
                "exitCode": 0,
                "timedOut": False,
            }
        ctx = {"conversation_id": "c1", "todo_user_key": "u1", "do_codex": mock_codex}
        r = await tg.execute_telegram_tool("runCodexCli", {"prompt": "do it"}, ctx)
        assert r.get("success") is True
        assert "Summary file" in r.get("message", "")

    @pytest.mark.asyncio
    async def test_get_todo_execution_status_no_status_fn_returns_message(self):
        """getTodoExecutionStatus when task_execution_status not in context returns no status."""
        ctx = {"conversation_id": "c1", "todo_user_key": "u1"}
        r = await tg.execute_telegram_tool("getTodoExecutionStatus", {}, ctx)
        assert r.get("success") is True
        assert r.get("data") is None

    @pytest.mark.asyncio
    async def test_get_todo_execution_status_returns_state_when_running(self):
        """getTodoExecutionStatus with status fn returns current state when running."""
        def mock_status(user_key):
            return {"status": "executing", "task_id": 1, "message": "Working on it."}
        ctx = {"conversation_id": "c1", "todo_user_key": "u1", "task_execution_status": mock_status}
        r = await tg.execute_telegram_tool("getTodoExecutionStatus", {}, ctx)
        assert r.get("success") is True
        assert r.get("data") == {"status": "executing", "task_id": 1, "message": "Working on it."}

    @pytest.mark.asyncio
    async def test_manage_memory_cache_add_and_list(self):
        """manageMemoryCache add returns success; list with pre-populated store returns items."""
        ctx = {"conversation_id": "cid1", "todo_store": {}, "memory_cache_store": {}}
        r1 = await tg.execute_telegram_tool(
            "manageMemoryCache", {"action": "add", "memDescription": "User likes cats"}, ctx
        )
        assert r1.get("success") is True
        ctx["memory_cache_store"]["cid1"] = ["User likes cats"]
        r2 = await tg.execute_telegram_tool("manageMemoryCache", {"action": "list"}, ctx)
        assert r2.get("success") is True
        assert "cats" in r2.get("message", "")

    @pytest.mark.asyncio
    async def test_store_memory_rejects_transient_operational_state(self):
        """storeMemory should refuse task/list/status snapshots when manager exposes guard."""
        mm = MagicMock()
        mm.should_store_as_conversational_memory = MagicMock(return_value=False)
        mm.store_memory = AsyncMock(return_value="mem_x")
        ctx = {"memory_manager": mm}

        out = await tg.execute_telegram_tool(
            "storeMemory",
            {"text": "Todo list: 1. buy milk"},
            ctx,
        )
        assert out.get("success") is False
        assert "transient" in out.get("message", "").lower()
        mm.store_memory.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_memory_allows_durable_memory_text(self):
        """storeMemory should pass durable text through to memory manager."""
        mm = MagicMock()
        mm.should_store_as_conversational_memory = MagicMock(return_value=True)
        mm.store_memory = AsyncMock(return_value="mem_123")
        ctx = {"memory_manager": mm}

        out = await tg.execute_telegram_tool(
            "storeMemory",
            {"text": "User prefers dark mode", "category": "preference"},
            ctx,
        )
        assert out.get("success") is True
        mm.store_memory.assert_awaited_once_with(
            text="User prefers dark mode",
            category="preference",
            source="telegram",
        )

    @pytest.mark.asyncio
    async def test_navigate_to_url_returns_message_with_link(self):
        """navigateToUrl returns message with URL (no actual navigation in Telegram)."""
        ctx = {}
        r = await tg.execute_telegram_tool("navigateToUrl", {"url": "https://example.com"}, ctx)
        assert r.get("success") is True
        assert "https://example.com" in r.get("message", "")
        assert "browser" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_calculate_safe_expression(self):
        """calculate evaluates safe math expression."""
        ctx = {}
        r = await tg.execute_telegram_tool("calculate", {"expression": "2 + 3 * 4"}, ctx)
        assert r.get("success") is True
        assert r.get("message") == "14" or "14" in r.get("message", "")

    @pytest.mark.asyncio
    async def test_calculate_invalid_returns_failure(self):
        """calculate with invalid or unsafe expression returns failure."""
        ctx = {}
        r = await tg.execute_telegram_tool("calculate", {"expression": "os.system('x')"}, ctx)
        assert r.get("success") is False

    @pytest.mark.asyncio
    async def test_scrape_website_single_url_success(self):
        """scrapeWebsite with single url calls do_fetch and returns content."""
        async def fake_fetch(u):
            return {"content": "Hello from page"}

        ctx = {"do_fetch": fake_fetch}
        r = await tg.execute_telegram_tool("scrapeWebsite", {"url": "https://example.com"}, ctx)
        assert r.get("success") is True
        assert "Hello from page" in r.get("message", "")

    @pytest.mark.asyncio
    async def test_scrape_website_forwards_dynamic_render_args(self):
        """scrapeWebsite should pass dynamic rendering options to do_fetch when provided."""
        observed = {}

        async def fake_fetch(u, **kwargs):
            observed["url"] = u
            observed["kwargs"] = kwargs
            return {"content": "Dynamic content"}

        ctx = {"do_fetch": fake_fetch}
        r = await tg.execute_telegram_tool(
            "scrapeWebsite",
            {
                "url": "https://example.com",
                "render_js": True,
                "render_engine": "playwright",
                "wait_for_selector": ".status-table",
                "js_wait_ms": 3200,
            },
            ctx,
        )
        assert r.get("success") is True
        assert observed["url"] == "https://example.com"
        assert observed["kwargs"] == {
            "render_js": True,
            "render_engine": "playwright",
            "wait_for_selector": ".status-table",
            "js_wait_ms": 3200,
        }

    @pytest.mark.asyncio
    async def test_scrape_website_urls_retry_second_succeeds(self):
        """scrapeWebsite with urls list tries each until one succeeds (scrape-with-retry)."""
        call_count = 0

        async def fake_fetch(u):
            nonlocal call_count
            call_count += 1
            if "fail" in u:
                raise Exception("404 Not Found")
            return {"content": "Success from " + u}

        ctx = {"do_fetch": fake_fetch}
        r = await tg.execute_telegram_tool(
            "scrapeWebsite",
            {"urls": ["https://fail.first/page", "https://ok.second/page"]},
            ctx,
        )
        assert r.get("success") is True
        assert "Success from https://ok.second/page" in r.get("message", "")
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_scrape_website_urls_all_fail_returns_last_error(self):
        """scrapeWebsite with urls list returns last error when all fail."""
        async def fake_fetch(u):
            raise Exception("500 Server Error")

        ctx = {"do_fetch": fake_fetch}
        r = await tg.execute_telegram_tool(
            "scrapeWebsite",
            {"urls": ["https://a.com", "https://b.com"]},
            ctx,
        )
        assert r.get("success") is False
        assert "500 Server Error" in r.get("message", "")

    @pytest.mark.asyncio
    async def test_scrape_website_no_url_or_urls_returns_failure(self):
        """scrapeWebsite without url or urls returns failure."""
        ctx = {"do_fetch": AsyncMock(return_value={"content": "x"})}
        r = await tg.execute_telegram_tool("scrapeWebsite", {}, ctx)
        assert r.get("success") is False
        assert "required" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_web_search_calls_do_search(self):
        """webSearch calls do_search from context and returns result message."""
        mock_results = {"results": [{"title": "A", "snippet": "B", "url": "https://a.com"}]}

        async def fake_search(q):
            return mock_results

        ctx = {"do_search": fake_search}
        r = await tg.execute_telegram_tool("webSearch", {"query": "test query"}, ctx)
        assert r.get("success") is True
        assert "A" in r.get("message", "") or "B" in r.get("message", "")
        assert "https://a.com" in r.get("message", "")

    @pytest.mark.asyncio
    async def test_web_search_no_do_search_returns_unavailable(self):
        """webSearch when do_search not in context returns unavailable message."""
        r = await tg.execute_telegram_tool("webSearch", {"query": "x"}, {})
        assert r.get("success") is False
        assert "not available" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_list_files_limits_output_rows(self, monkeypatch):
        """listFiles should cap rendered rows and append an overflow indicator."""
        monkeypatch.setenv("LIST_FILES_TOOL_MAX_ENTRIES", "3")

        async def fake_list_internal():
            return {
                "success": True,
                "files": [
                    {"name": "images", "type": "directory"},
                    {"name": "a.txt"},
                    {"name": "b.txt"},
                    {"name": "c.txt"},
                    {"name": "d.txt"},
                    {"name": "e.txt"},
                ],
            }

        ctx = {"conversation_id": "cid1", "list_files_internal": fake_list_internal}
        r = await tg.execute_telegram_tool("listFiles", {}, ctx)
        assert r.get("success") is True
        message = r.get("message", "")
        assert "- images/ [dir]" in message
        assert "- a.txt" in message
        assert "- b.txt" in message
        assert "- ... and 3 more files." in message
        assert "- c.txt" not in message
        assert "- d.txt" not in message
        assert "- e.txt" not in message

    @pytest.mark.asyncio
    async def test_list_files_returns_no_files_when_empty(self):
        """listFiles returns 'No files.' when no files are present."""
        async def fake_list_internal():
            return {"success": True, "files": []}

        ctx = {"conversation_id": "cid1", "list_files_internal": fake_list_internal}
        r = await tg.execute_telegram_tool("listFiles", {}, ctx)
        assert r.get("success") is True
        assert r.get("message") == "No files."

    @pytest.mark.asyncio
    async def test_list_files_supports_path_and_recursive_arguments(self):
        """listFiles forwards optional path/recursive arguments to backend list callback."""
        observed = {}

        async def fake_list_internal(path="", recursive=False):
            observed["path"] = path
            observed["recursive"] = recursive
            return {"success": True, "files": [{"name": "images/a.png"}]}

        ctx = {"conversation_id": "cid1", "list_files_internal": fake_list_internal}
        r = await tg.execute_telegram_tool(
            "listFiles",
            {"path": "images", "recursive": "true"},
            ctx,
        )
        assert r.get("success") is True
        assert observed == {"path": "images", "recursive": True}
        assert "images/a.png" in r.get("message", "")

    @pytest.mark.asyncio
    async def test_list_files_path_requires_backend_support(self):
        """listFiles returns a clear error if custom backend callback cannot accept path/recursive args."""
        async def fake_list_internal():
            return {"success": True, "files": [{"name": "a.txt"}]}

        ctx = {"conversation_id": "cid1", "list_files_internal": fake_list_internal}
        r = await tg.execute_telegram_tool("listFiles", {"path": "images"}, ctx)
        assert r.get("success") is False
        assert "does not support path or recursive" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_list_files_snake_case_alias_routes_to_camel_case(self):
        """list_files alias should resolve to listFiles behavior."""
        observed = {}

        async def fake_list_internal(path="", recursive=False):
            observed["path"] = path
            observed["recursive"] = recursive
            return {"success": True, "files": [{"name": "images/a.png"}]}

        ctx = {"conversation_id": "cid1", "list_files_internal": fake_list_internal}
        r = await tg.execute_telegram_tool("list_files", {"path": "images", "recursive": True}, ctx)
        assert r.get("success") is True
        assert observed == {"path": "images", "recursive": True}
        assert "images/a.png" in r.get("message", "")

    @pytest.mark.asyncio
    async def test_save_to_file_alias_routes_to_write_file(self):
        """saveToFile alias should execute writeFile path for backward compatibility."""
        observed = {}

        async def fake_write_internal(filename, content, fmt):
            observed["filename"] = filename
            observed["content"] = content
            observed["fmt"] = fmt
            return {"success": True, "message": "Write OK."}

        ctx = {"conversation_id": "cid1", "write_file_internal": fake_write_internal}
        r = await tg.execute_telegram_tool(
            "saveToFile",
            {"filename": "notes.txt", "content": "hello"},
            ctx,
        )
        assert r.get("success") is True
        assert observed == {"filename": "notes.txt", "content": "hello", "fmt": "txt"}

    @pytest.mark.asyncio
    async def test_send_telegram_file_requires_sender_callback(self):
        """sendTelegramFile fails when backend sender is unavailable."""
        ctx = {"conversation_id": "cid1"}
        r = await tg.execute_telegram_tool("sendTelegramFile", {"filename": "report.txt"}, ctx)
        assert r.get("success") is False
        assert "not available" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_send_telegram_file_requires_filename(self):
        """sendTelegramFile requires filename parameter."""
        async def fake_sender(filename, caption=None):
            return {"success": True, "message": f"Sent {filename}"}

        ctx = {"conversation_id": "cid1", "send_telegram_file_internal": fake_sender}
        r = await tg.execute_telegram_tool("sendTelegramFile", {}, ctx)
        assert r.get("success") is False
        assert "filename is required" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_send_telegram_file_calls_sender(self):
        """sendTelegramFile passes filename and caption to backend sender and returns success."""
        observed = {}

        async def fake_sender(filename, caption=None):
            observed["filename"] = filename
            observed["caption"] = caption
            return {"success": True, "message": "Sent summary.docx to Telegram."}

        ctx = {"conversation_id": "cid1", "send_telegram_file_internal": fake_sender}
        r = await tg.execute_telegram_tool(
            "sendTelegramFile",
            {"filename": "summary.docx", "caption": "Here is your file"},
            ctx,
        )
        assert r.get("success") is True
        assert observed == {"filename": "summary.docx", "caption": "Here is your file"}
        assert "sent" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_send_telegram_file_propagates_sender_failure(self):
        """sendTelegramFile returns sender failure message when backend send fails."""
        async def fake_sender(filename, caption=None):
            return {"success": False, "message": "File not found: missing.txt"}

        ctx = {"conversation_id": "cid1", "send_telegram_file_internal": fake_sender}
        r = await tg.execute_telegram_tool("sendTelegramFile", {"filename": "missing.txt"}, ctx)
        assert r.get("success") is False
        assert "file not found" in r.get("message", "").lower()


    @pytest.mark.asyncio
    async def test_weather_info_calls_do_weather(self):
        """weatherInfo calls do_weather and returns summary."""
        async def fake_weather(**kwargs):
            return {"summary": "Weather for Sydney: 22C", "resolved_location": "Sydney"}

        ctx = {"do_weather": fake_weather, "user_id": "tg-user-1"}
        r = await tg.execute_telegram_tool("weatherInfo", {"location": "Sydney", "requestType": "summary"}, ctx)
        assert r.get("success") is True
        assert "Sydney" in r.get("message", "")

    @pytest.mark.asyncio
    async def test_weather_info_unavailable_without_callback(self):
        """weatherInfo returns not available when callback missing."""
        r = await tg.execute_telegram_tool("weatherInfo", {"location": "Sydney"}, {})
        assert r.get("success") is False
        assert "not available" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_weather_info_invalid_request_type_defaults_summary(self):
        """weatherInfo should normalize invalid requestType values safely."""
        observed = {}

        async def fake_weather(**kwargs):
            observed.update(kwargs)
            return {"summary": "Weather for Sydney: 22C", "resolved_location": "Sydney"}

        ctx = {"do_weather": fake_weather, "user_id": "tg-user-1"}
        r = await tg.execute_telegram_tool("weatherInfo", {"location": "Sydney", "requestType": 123}, ctx)
        assert r.get("success") is True
        assert observed.get("detail") == "summary"

    @pytest.mark.asyncio
    async def test_health_check_calls_backend_and_returns_message(self):
        """health_check alias should route to healthCheck and return backend summary."""
        async def fake_health(_args=None):
            return {
                "success": True,
                "message": "Browser-use status: healthy. Running tasks: 2. Uptime: 44.2s.",
                "result": {"status": "healthy", "running_tasks": 2},
            }

        ctx = {"do_browser_health_check": fake_health}
        r = await tg.execute_telegram_tool("health_check", {}, ctx)
        assert r.get("success") is True
        assert "running tasks" in r.get("message", "").lower()
        assert isinstance(r.get("data"), dict)

    @pytest.mark.asyncio
    async def test_health_check_unavailable_without_callback(self):
        """healthCheck should fail clearly when backend callback is not provided."""
        r = await tg.execute_telegram_tool("healthCheck", {}, {})
        assert r.get("success") is False
        assert "not available" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_pdf_to_power_point_returns_web_only_message(self):
        """pdfToPowerPoint returns message directing user to web interface."""
        r = await tg.execute_telegram_tool("pdfToPowerPoint", {"title": "T", "filename": "f.pptx"}, {})
        assert r.get("success") is True
        assert "web" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_failure(self):
        """Unknown tool name returns success False and message."""
        r = await tg.execute_telegram_tool("unknownTool", {}, {})
        assert r.get("success") is False
        assert "Unknown" in r.get("message", "")

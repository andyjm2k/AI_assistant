"""
Unit tests for Telegram tool parsing and execution (src.servers.telegram_tools).
Covers parse_telegram_tool_response (XML, JSON, code-block stripping) and execute_telegram_tool (key tools with mocks).
"""

import json
import base64
import uuid
from pathlib import Path
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

    def test_markdown_to_slides_aliases_map_to_native_create_slides_tool(self):
        expected = "createSlidesPresentation"
        assert tg._canonicalize_telegram_tool_name("slides_create_presentation_from_markdown") == expected
        assert tg._canonicalize_telegram_tool_name("markdown_to_slides") == expected
        assert tg._canonicalize_telegram_tool_name("markdownToSlides") == expected
        assert tg._canonicalize_telegram_tool_name("googleworkspace_cli.slides_create_presentation_from_markdown") == expected
        assert tg._canonicalize_telegram_tool_name("google_slides.create_outline_from_markdown") == expected

    def test_tool_xml_wrapped_in_think_still_parsed(self):
        """Tool call parsing should still work even if model wraps text in <think> blocks."""
        content = (
            "<think>I'll call a tool now.</think>\n"
            '<tool>webSearch</tool>\n<parameters>{"query":"x"}</parameters>'
        )
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "webSearch"
        assert json.loads(out["arguments"]) == {"query": "x"}

    def test_parser_uses_matching_tool_block_instead_of_stray_tool_tag(self):
        """A stray earlier tool tag should not steal parameters from the real matched block."""
        content = (
            "Example only: <tool>webSearch</tool>\n"
            'Real call: <tool>scrapeWebsite</tool>\n<parameters>{"url":"https://example.com"}</parameters>'
        )
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "scrapeWebsite"
        assert json.loads(out["arguments"]) == {"url": "https://example.com"}

    def test_xml_with_single_quoted_parameters_is_salvaged(self):
        """Parser should accept Python-style dict literals that some OpenAI-compatible models emit."""
        content = "<tool>webSearch</tool>\n<parameters>{'query': 'MiniMax coupons'}</parameters>"
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "webSearch"
        assert json.loads(out["arguments"]) == {"query": "MiniMax coupons"}

    def test_xml_with_extra_text_inside_parameters_uses_balanced_json_object(self):
        """Parser should recover the leading JSON object even if the model appends stray prose inside <parameters>."""
        content = (
            "<tool>scrapeWebsite</tool>\n"
            "<parameters>{\"url\": \"https://example.com\"}\nUse that page.</parameters>"
        )
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "scrapeWebsite"
        assert json.loads(out["arguments"]) == {"url": "https://example.com"}

    def test_xml_with_js_style_object_literal_is_salvaged(self):
        """Parser should recover simple JS object literals with bare keys."""
        content = (
            "<tool>runBrowserAgent</tool>\n"
            '<parameters>{task: "Check the page", url: "https://example.com"}</parameters>'
        )
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "runBrowserAgent"
        assert json.loads(out["arguments"]) == {
            "task": "Check the page",
            "url": "https://example.com",
        }

    def test_xml_with_nested_parameter_tags_is_salvaged(self):
        """Parser should accept models that emit XML child tags inside <parameters> instead of JSON."""
        content = (
            "<tool>runBrowserAgent</tool>\n"
            "<parameters><task>Check the page</task><url>https://example.com</url></parameters>"
        )
        out = tg.parse_telegram_tool_response(content)
        assert out is not None
        assert out.get("name") == "runBrowserAgent"
        assert json.loads(out["arguments"]) == {
            "task": "Check the page",
            "url": "https://example.com",
        }


class TestStripThinkMarkup:
    """Tests for stripping <think>...</think> blocks from assistant text."""

    def test_strip_think_markup_removes_reasoning_block(self):
        content = "Before\n<think>private reasoning</think>\nAfter"
        out = tg.strip_think_markup(content)
        assert "private reasoning" not in out
        assert "Before" in out
        assert "After" in out


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

    def test_tool_xml_wrapped_in_think_is_still_detected(self):
        """Raw tool XML wrapped in <think> should still be detected as tool-call-only output."""
        content = (
            "<think>internal</think>\n"
            '<tool>scrapeWebsite</tool>\n<parameters>{"url":"https://example.com"}</parameters>'
        )
        assert tg.reply_looks_like_tool_call(content) is True


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

    def test_strip_tool_call_markup_removes_think_blocks(self):
        content = (
            "<think>private chain-of-thought</think>\n"
            "Visible reply."
        )
        out = tg.strip_tool_call_markup(content)
        assert "chain-of-thought" not in out
        assert out == "Visible reply."


class TestReplyLooksLikeToolPlanning:
    """Tests for planning chatter detection in mixed text + tool XML replies."""

    def test_planning_reply_returns_true(self):
        content = "I have the URLs and will now scrape them for more detail."
        assert tg.reply_looks_like_tool_planning(content) is True

    def test_final_answer_returns_false(self):
        content = "Here is the scraped summary with the key details you asked for."
        assert tg.reply_looks_like_tool_planning(content) is False


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
    async def test_dynamic_skill_tool_uses_structured_data_when_message_is_ok(self):
        """Dynamic skill results should surface useful payload text instead of generic 'OK'."""

        async def mock_skill_executor(name, arguments):
            return {
                "success": True,
                "message": "OK",
                "data": {
                    "response": {
                        "parsed_json": {"messages": [{"id": "m1"}]},
                    }
                },
            }

        ctx = {"conversation_id": "cid1", "memory_cache_store": {}, "execute_skill_tool": mock_skill_executor}
        out = await tg.execute_telegram_tool("googleworkspace_cli.run_readonly_command", {"service": "gmail"}, ctx)
        assert out.get("success") is True
        assert "messages" in out.get("message", "")
        assert "m1" in out.get("message", "")

    @pytest.mark.asyncio
    async def test_googleworkspace_cli_skill_name_alias_maps_to_run_readonly_command(self):
        """Skill-name alias should execute the primary googleworkspace_cli tool."""

        captured = {}

        async def mock_skill_executor(name, arguments):
            captured["name"] = name
            captured["arguments"] = arguments
            return {"success": True, "message": "OK", "data": {"response": {"parsed_json": {"ok": True}}}}

        ctx = {"conversation_id": "cid1", "memory_cache_store": {}, "execute_skill_tool": mock_skill_executor}
        out = await tg.execute_telegram_tool("googleworkspace_cli", {"service": "gmail", "action": "list"}, ctx)
        assert out.get("success") is True
        assert captured.get("name") == "googleworkspace_cli.gmail_list_unread"

    @pytest.mark.asyncio
    async def test_dynamic_skill_tool_formats_gmail_message_summaries(self):
        """When gmail_message_summaries are present, output should be human-readable."""

        async def mock_skill_executor(name, arguments):
            return {
                "success": True,
                "message": "OK",
                "data": {
                    "gmail_message_summaries": [
                        {
                            "id": "msg_1",
                            "from": "Alice <alice@example.com>",
                            "subject": "Status update",
                            "date": "Mon, 9 Mar 2026",
                            "snippet": "Quick update on the rollout.",
                        }
                    ]
                },
            }

        ctx = {"conversation_id": "cid1", "memory_cache_store": {}, "execute_skill_tool": mock_skill_executor}
        out = await tg.execute_telegram_tool("googleworkspace_cli.run_readonly_command", {"service": "gmail"}, ctx)
        assert out.get("success") is True
        assert "Latest emails:" in out.get("message", "")
        assert "Status update" in out.get("message", "")
        assert "alice@example.com" in out.get("message", "")
        assert "ID: msg_1" in out.get("message", "")

    @pytest.mark.asyncio
    async def test_dynamic_skill_tool_formats_up_to_ten_gmail_message_summaries(self):
        """Gmail summary rendering should not truncate a 10-message page to 5 items."""

        async def mock_skill_executor(name, arguments):
            return {
                "success": True,
                "message": "OK",
                "data": {
                    "max_results": 10,
                    "gmail_message_summaries": [
                        {
                            "id": f"msg_{index}",
                            "from": f"Sender {index} <sender{index}@example.com>",
                            "subject": f"Subject {index}",
                            "date": f"Mon, {index:02d} Mar 2026",
                            "snippet": f"Preview {index}",
                        }
                        for index in range(1, 11)
                    ],
                },
            }

        ctx = {"conversation_id": "cid1", "memory_cache_store": {}, "execute_skill_tool": mock_skill_executor}
        out = await tg.execute_telegram_tool("googleworkspace_cli.gmail_list_all", {"max_results": 10}, ctx)

        assert out.get("success") is True
        message = out.get("message", "")
        assert "1. Subject 1" in message
        assert "5. Subject 5" in message
        assert "10. Subject 10" in message
        assert "ID: msg_10" in message

    @pytest.mark.asyncio
    async def test_dynamic_skill_tool_formats_gmail_summaries_without_unknown_placeholders(self):
        """When sender/subject are missing, render a clean fallback without unknown placeholders."""

        async def mock_skill_executor(name, arguments):
            return {
                "success": True,
                "message": "OK",
                "data": {
                    "gmail_message_summaries": [
                        {
                            "snippet": "Newsletter preview text from marketing team",
                        }
                    ]
                },
            }

        ctx = {"conversation_id": "cid1", "memory_cache_store": {}, "execute_skill_tool": mock_skill_executor}
        out = await tg.execute_telegram_tool("googleworkspace_cli.run_readonly_command", {"service": "gmail"}, ctx)
        assert out.get("success") is True
        msg = out.get("message", "")
        assert "Latest emails:" in msg
        assert "(unknown sender)" not in msg
        assert "(no subject)" not in msg

    @pytest.mark.asyncio
    async def test_dynamic_skill_tool_formats_gmail_message_get_details_recursively(self):
        """Nested Gmail headers/body should be rendered as details, not raw JSON."""

        body_encoded = base64.urlsafe_b64encode(b"Hello from the decoded body").decode("utf-8").rstrip("=")

        async def mock_skill_executor(name, arguments):
            return {
                "success": True,
                "message": "OK",
                "data": {
                    "response": {
                        "parsed_json": {
                            "id": "m42",
                            "threadId": "t42",
                            "snippet": "Hello from snippet",
                            "labelIds": ["INBOX", "UNREAD"],
                            "payload": {
                                "parts": [
                                    {
                                        "mimeType": "multipart/alternative",
                                        "parts": [
                                            {
                                                "mimeType": "text/plain",
                                                "body": {"data": body_encoded},
                                            }
                                        ],
                                        "headers": [
                                            {"name": "From", "value": "Carol <carol@example.com>"},
                                            {"name": "To", "value": "me@example.com"},
                                            {"name": "Subject", "value": "Nested hello"},
                                            {"name": "Date", "value": "Mon, 9 Mar 2026"},
                                        ],
                                    }
                                ]
                            },
                        }
                    }
                },
            }

        ctx = {"conversation_id": "cid1", "memory_cache_store": {}, "execute_skill_tool": mock_skill_executor}
        out = await tg.execute_telegram_tool("googleworkspace_cli.run_readonly_command", {"service": "gmail"}, ctx)
        assert out.get("success") is True
        msg = out.get("message", "")
        assert "Email ID: m42" in msg
        assert "From: Carol <carol@example.com>" in msg
        assert "To: me@example.com" in msg
        assert "Subject: Nested hello" in msg
        assert "Snippet: Hello from snippet" in msg
        assert "Body: Hello from the decoded body" in msg

    @pytest.mark.asyncio
    async def test_dynamic_skill_tool_caches_gmail_summary_ids_for_followups(self):
        """List results should cache summary IDs so follow-up detail requests can resolve by index."""

        async def mock_skill_executor(name, arguments):
            return {
                "success": True,
                "message": "OK",
                "data": {
                    "gmail_message_summaries": [
                        {"id": "id_a", "subject": "A"},
                        {"id": "id_b", "subject": "B"},
                    ]
                },
            }

        memory_cache_store = {}
        ctx = {
            "conversation_id": "cid1",
            "memory_cache_store": memory_cache_store,
            "execute_skill_tool": mock_skill_executor,
        }
        out = await tg.execute_telegram_tool(
            "googleworkspace_cli.run_readonly_command",
            {"service": "gmail", "resource": "messages", "action": "list"},
            ctx,
        )
        assert out.get("success") is True
        gmail_state = memory_cache_store.get("__gmail_tool_state__", {}).get("cid1", {})
        assert gmail_state.get("last_message_ids") == ["id_a", "id_b"]

    @pytest.mark.asyncio
    async def test_dynamic_skill_tool_resolves_numeric_gmail_detail_reference(self):
        """A detail request with id='1' should resolve to the first cached Gmail message ID."""

        captured = {}

        async def mock_skill_executor(name, arguments):
            captured["args"] = arguments
            return {
                "success": True,
                "message": "OK",
                "data": {
                    "response": {
                        "parsed_json": {
                            "id": "id_a",
                            "payload": {"headers": [{"name": "Subject", "value": "Resolved"}]},
                        }
                    }
                },
            }

        memory_cache_store = {"__gmail_tool_state__": {"cid1": {"last_message_ids": ["id_a", "id_b"]}}}
        ctx = {
            "conversation_id": "cid1",
            "memory_cache_store": memory_cache_store,
            "execute_skill_tool": mock_skill_executor,
        }
        out = await tg.execute_telegram_tool(
            "googleworkspace_cli.run_readonly_command",
            {
                "service": "gmail",
                "resource": "messages",
                "action": "get",
                "params": {"id": "1"},
            },
            ctx,
        )
        assert out.get("success") is True
        assert captured["args"]["params"]["id"] == "id_a"
        assert captured["args"]["params"]["userId"] == "me"

    @pytest.mark.asyncio
    async def test_dynamic_skill_tool_formats_wrapped_gmail_message_payload(self):
        """Wrapped payloads like {'message': {...}} should still render readable email details."""

        async def mock_skill_executor(name, arguments):
            return {
                "success": True,
                "message": "OK",
                "data": {
                    "response": {
                        "parsed_json": {
                            "message": {
                                "id": "m_wrap",
                                "threadId": "t_wrap",
                                "snippet": "Wrapped snippet",
                                "payload": {
                                    "headers": [
                                        {"name": "From", "value": "Wrapped <wrap@example.com>"},
                                        {"name": "Subject", "value": "Wrapped subject"},
                                    ]
                                },
                            }
                        }
                    }
                },
            }

        ctx = {"conversation_id": "cid1", "memory_cache_store": {}, "execute_skill_tool": mock_skill_executor}
        out = await tg.execute_telegram_tool("googleworkspace_cli.run_readonly_command", {"service": "gmail"}, ctx)
        assert out.get("success") is True
        msg = out.get("message", "")
        assert "Email ID: m_wrap" in msg
        assert "Subject: Wrapped subject" in msg
        assert "From: Wrapped <wrap@example.com>" in msg

    @pytest.mark.asyncio
    async def test_dynamic_skill_tool_parses_noisy_json_stdout_for_gmail_details(self):
        """When parsed_json is missing but stdout contains noisy JSON, extract and summarize it."""

        async def mock_skill_executor(name, arguments):
            noisy = (
                "debug: running command\n"
                '{"id":"m_stdout","threadId":"t_stdout","snippet":"From stdout",'
                '"payload":{"headers":[{"name":"Subject","value":"Stdout subject"},'
                '{"name":"From","value":"Stdout <stdout@example.com>"}]}}'
            )
            return {
                "success": True,
                "message": "OK",
                "data": {"response": {"parsed_json": None, "stdout": noisy}},
            }

        ctx = {"conversation_id": "cid1", "memory_cache_store": {}, "execute_skill_tool": mock_skill_executor}
        out = await tg.execute_telegram_tool("googleworkspace_cli.run_readonly_command", {"service": "gmail"}, ctx)
        assert out.get("success") is True
        msg = out.get("message", "")
        assert "Email ID: m_stdout" in msg
        assert "Subject: Stdout subject" in msg
        assert "From: Stdout <stdout@example.com>" in msg
        assert "{" not in msg

    @pytest.mark.asyncio
    async def test_dynamic_skill_tool_reports_when_no_inline_body_or_snippet(self):
        """If no snippet/body exists, include a clear body-not-found line instead of vague emptiness."""

        async def mock_skill_executor(name, arguments):
            return {
                "success": True,
                "message": "OK",
                "data": {
                    "response": {
                        "parsed_json": {
                            "id": "m_no_body",
                            "payload": {
                                "headers": [
                                    {"name": "From", "value": "NoBody <nobody@example.com>"},
                                    {"name": "Subject", "value": "Attachment only"},
                                ]
                            },
                        }
                    }
                },
            }

        ctx = {"conversation_id": "cid1", "memory_cache_store": {}, "execute_skill_tool": mock_skill_executor}
        out = await tg.execute_telegram_tool("googleworkspace_cli.run_readonly_command", {"service": "gmail"}, ctx)
        assert out.get("success") is True
        msg = out.get("message", "")
        assert "Subject: Attachment only" in msg
        assert "Body: (no inline text body found in this message)" in msg

    @pytest.mark.asyncio
    async def test_dynamic_skill_tool_renders_html_body_content_when_plain_text_missing(self):
        """HTML-only body parts should be rendered into readable text."""

        html_body = base64.urlsafe_b64encode(b"<p>Hello <b>HTML</b> only</p>").decode("utf-8").rstrip("=")

        async def mock_skill_executor(name, arguments):
            return {
                "success": True,
                "message": "OK",
                "data": {
                    "response": {
                        "parsed_json": {
                            "id": "m_html_only",
                            "payload": {
                                "parts": [
                                    {
                                        "mimeType": "text/html",
                                        "body": {"data": html_body},
                                    }
                                ],
                                "headers": [
                                    {"name": "Subject", "value": "HTML only"},
                                ],
                            },
                        }
                    }
                },
            }

        ctx = {"conversation_id": "cid1", "memory_cache_store": {}, "execute_skill_tool": mock_skill_executor}
        out = await tg.execute_telegram_tool("googleworkspace_cli.run_readonly_command", {"service": "gmail"}, ctx)
        assert out.get("success") is True
        msg = out.get("message", "")
        assert "Subject: HTML only" in msg
        assert "Body: Hello HTML only" in msg

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
    async def test_manage_memory_cache_accepts_prompt_documented_aliases(self):
        """manageMemoryCache should accept memoryId/memoryDescription aliases documented in the Telegram prompt."""
        ctx = {"conversation_id": "cid1", "todo_store": {}, "memory_cache_store": {"cid1": ["old note"]}}

        add_result = await tg.execute_telegram_tool(
            "manageMemoryCache",
            {"action": "add", "memoryDescription": "new note"},
            ctx,
        )
        assert add_result.get("success") is True

        update_result = await tg.execute_telegram_tool(
            "manageMemoryCache",
            {"action": "update", "memoryId": 1, "memoryDescription": "updated old note"},
            ctx,
        )
        assert update_result.get("success") is True

        delete_result = await tg.execute_telegram_tool(
            "manageMemoryCache",
            {"action": "delete", "memoryId": 2},
            ctx,
        )
        assert delete_result.get("success") is True
        assert ctx["memory_cache_store"]["cid1"] == ["updated old note"]

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
    async def test_fetch_news_defaults_to_csv_and_writes_via_backend(self, monkeypatch):
        """fetchNews should write CSV content to scratch when Telegram uses the backend writer."""
        from src.servers import proxy_server as ps

        scratch_dir = Path("scratch") / f"telegram-fetch-news-{uuid.uuid4().hex}"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(ps, "SCRATCH_DIR", scratch_dir)
        try:
            async def fake_news(query):
                assert query == "climate policy"
                return {
                    "articles": [
                        {"title": "Policy, Update", "url": "https://example.com/policy"},
                    ]
                }

            ctx = {"do_news": fake_news, "write_file_internal": ps._write_file_internal}
            r = await tg.execute_telegram_tool("fetchNews", {"searchTerm": "climate policy"}, ctx)

            assert r.get("success") is True
            assert "news.csv" in r.get("message", "")
            written = scratch_dir / "news.csv"
            assert written.exists()
            assert written.read_text(encoding="utf-8") == (
                'Title,URL\n"Policy  Update","https://example.com/policy"'
            )
        finally:
            written = scratch_dir / "news.csv"
            if written.exists():
                written.unlink()
            if scratch_dir.exists():
                scratch_dir.rmdir()

    @pytest.mark.asyncio
    async def test_fetch_news_appends_csv_extension_when_missing(self):
        """fetchNews should normalize extension-less filenames to .csv for Telegram writes."""
        observed = {}

        async def fake_news(query):
            observed["query"] = query
            return {"articles": [{"title": "A", "url": "https://example.com/a"}]}

        async def fake_write_internal(filename, content, fmt):
            observed["filename"] = filename
            observed["content"] = content
            observed["fmt"] = fmt
            return {"success": True, "message": "Write OK."}

        ctx = {"do_news": fake_news, "write_file_internal": fake_write_internal}
        r = await tg.execute_telegram_tool(
            "fetchNews",
            {"searchTerm": "ai agents", "filename": "headlines"},
            ctx,
        )

        assert r.get("success") is True
        assert observed["query"] == "ai agents"
        assert observed["filename"] == "headlines.csv"
        assert observed["fmt"] == "csv"
        assert observed["content"].startswith("Title,URL\n")

    @pytest.mark.asyncio
    async def test_list_files_limits_output_rows(self, monkeypatch):
        """listFiles should cap rendered rows and append an overflow indicator."""
        monkeypatch.setenv("LIST_FILES_TOOL_MAX_ENTRIES", "3")

        async def fake_list_internal(path="", recursive=False, offset=0, max_entries=None):
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
        assert "- ... and 3 more files in this page." in message
        assert "- ... more files available. Continue with offset=3." in message
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
    async def test_list_files_supports_path_recursive_and_pagination_arguments(self):
        """listFiles forwards optional path/recursive/pagination arguments to backend list callback."""
        observed = {}

        async def fake_list_internal(path="", recursive=False, offset=0, max_entries=None):
            observed["path"] = path
            observed["recursive"] = recursive
            observed["offset"] = offset
            observed["max_entries"] = max_entries
            return {"success": True, "files": [{"name": "images/a.png"}]}

        ctx = {"conversation_id": "cid1", "list_files_internal": fake_list_internal}
        r = await tg.execute_telegram_tool(
            "listFiles",
            {"path": "images", "recursive": "true", "offset": 4, "max_entries": 7},
            ctx,
        )
        assert r.get("success") is True
        assert observed == {"path": "images", "recursive": True, "offset": 4, "max_entries": 7}
        assert "images/a.png" in r.get("message", "")

    @pytest.mark.asyncio
    async def test_list_files_path_requires_backend_support(self):
        """listFiles returns a clear error if custom backend callback cannot accept path/recursive args."""
        async def fake_list_internal():
            return {"success": True, "files": [{"name": "a.txt"}]}

        ctx = {"conversation_id": "cid1", "list_files_internal": fake_list_internal}
        r = await tg.execute_telegram_tool("listFiles", {"path": "images"}, ctx)
        assert r.get("success") is False
        assert "does not support path" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_list_files_snake_case_alias_routes_to_camel_case(self):
        """list_files alias should resolve to listFiles behavior."""
        observed = {}

        async def fake_list_internal(path="", recursive=False, offset=0, max_entries=None):
            observed["path"] = path
            observed["recursive"] = recursive
            observed["offset"] = offset
            observed["max_entries"] = max_entries
            return {"success": True, "files": [{"name": "images/a.png"}]}

        ctx = {"conversation_id": "cid1", "list_files_internal": fake_list_internal}
        r = await tg.execute_telegram_tool("list_files", {"path": "images", "recursive": True}, ctx)
        assert r.get("success") is True
        assert observed == {
            "path": "images",
            "recursive": True,
            "offset": 0,
            "max_entries": tg._get_list_files_tool_max_entries(),
        }
        assert "images/a.png" in r.get("message", "")

    @pytest.mark.asyncio
    async def test_search_files_alias_routes_to_search_files_behavior(self):
        """search_files alias should resolve to searchFiles behavior."""
        observed = {}

        async def fake_search_internal(query, **kwargs):
            observed["query"] = query
            observed.update(kwargs)
            return {
                "success": True,
                "matches": [
                    {
                        "relative_path": "docs/notes.txt",
                        "match_types": ["content"],
                        "line_number": 2,
                        "excerpt": "...alpha...",
                    }
                ],
            }

        ctx = {"conversation_id": "cid1", "search_files_internal": fake_search_internal}
        r = await tg.execute_telegram_tool(
            "search_files",
            {"query": "alpha", "path": "docs", "recursive": False, "max_results": 5},
            ctx,
        )
        assert r.get("success") is True
        assert observed == {
            "query": "alpha",
            "path": "docs",
            "recursive": False,
            "offset": 0,
            "max_results": 5,
            "case_sensitive": False,
            "filename_only": False,
        }
        assert "docs/notes.txt" in r.get("message", "")

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
    async def test_run_deep_research_propagates_backend_failure(self):
        """runDeepResearch should preserve backend success=False instead of forcing success=True."""
        async def fake_research(_args):
            return {"success": False, "message": "Deep research already running"}

        ctx = {"do_deep_research": fake_research}
        r = await tg.execute_telegram_tool("runDeepResearch", {"researchTask": "x"}, ctx)
        assert r.get("success") is False
        assert "already running" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_run_browser_agent_propagates_backend_failure(self):
        """runBrowserAgent should preserve backend success=False instead of forcing success=True."""
        async def fake_browser(_args):
            return {"success": False, "message": "Browser backend unavailable"}

        ctx = {"do_browser_agent": fake_browser}
        r = await tg.execute_telegram_tool("runBrowserAgent", {"task": "x"}, ctx)
        assert r.get("success") is False
        assert "unavailable" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_run_browser_agent_uses_result_when_message_missing(self):
        """runBrowserAgent should surface backend result text when message is omitted."""
        async def fake_browser(_args):
            return {"success": True, "result": "Found the required page and extracted the answer."}

        ctx = {"do_browser_agent": fake_browser}
        r = await tg.execute_telegram_tool("runBrowserAgent", {"task": "x"}, ctx)
        assert r.get("success") is True
        assert "extracted the answer" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_run_deep_research_uses_report_when_message_missing(self):
        """runDeepResearch should surface backend report text when message is omitted."""
        async def fake_research(_args):
            return {"success": True, "report": "Research summary with explicit final findings."}

        ctx = {"do_deep_research": fake_research}
        r = await tg.execute_telegram_tool("runDeepResearch", {"researchTask": "x"}, ctx)
        assert r.get("success") is True
        assert "explicit final findings" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_pdf_to_power_point_returns_web_only_message(self):
        """pdfToPowerPoint returns message directing user to web interface."""
        r = await tg.execute_telegram_tool("pdfToPowerPoint", {"title": "T", "filename": "f.pptx"}, {})
        assert r.get("success") is True
        assert "web" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_create_slides_presentation_uses_internal_backend(self):
        captured: Dict[str, Any] = {}

        async def fake_create(args):
            captured["args"] = args
            return {
                "success": True,
                "message": "Created Google Slides deck 'PermitFlow AI'.",
                "data": {"presentation_url": "https://docs.google.com/presentation/d/pres_1/edit"},
            }

        r = await tg.execute_telegram_tool(
            "createSlidesPresentation",
            {"prompt": "Create investor slides", "title": "PermitFlow AI"},
            {"create_telegram_slides_internal": fake_create},
        )
        assert r.get("success") is True
        assert captured["args"] == {"prompt": "Create investor slides", "title": "PermitFlow AI"}
        assert "permitflow ai" in r.get("message", "").lower()
        assert r.get("data", {}).get("presentation_url", "").endswith("/edit")

    @pytest.mark.asyncio
    async def test_create_slides_presentation_requires_backend_callback(self):
        r = await tg.execute_telegram_tool("createSlidesPresentation", {"prompt": "x"}, {})
        assert r.get("success") is False
        assert "not available" in r.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_failure(self):
        """Unknown tool name returns success False and message."""
        r = await tg.execute_telegram_tool("unknownTool", {}, {})
        assert r.get("success") is False
        assert "Unknown" in r.get("message", "")

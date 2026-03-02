"""
Unit tests for task execution (src.features.task_execution).
Covers TodoTaskExecutor.request_cancel and run_loop behaviour when cancel is requested.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.features.task_execution import (
    STATUS_CANCELLED,
    STATUS_AWAITING_CONFIRMATION,
    TodoTaskExecutor,
)


class TestTodoTaskExecutorCancel:
    """Tests for cancel support in TodoTaskExecutor."""

    def test_request_cancel_sets_flag(self):
        """request_cancel() sets _cancel_requested so run_loop can exit."""
        executor = TodoTaskExecutor(
            api_key="test-key",
            task_id=1,
            task_description="Test task",
            get_tools_func=None,
        )
        assert executor._cancel_requested is False
        executor.request_cancel()
        assert executor._cancel_requested is True

    @pytest.mark.asyncio
    async def test_run_loop_returns_cancelled_when_cancel_requested_before_iteration(self):
        """When _cancel_requested is True at start of first iteration, run_loop returns STATUS_CANCELLED."""
        executor = TodoTaskExecutor(
            api_key="test-key",
            task_id=1,
            task_description="Test",
            get_tools_func=AsyncMock(return_value=[]),
        )
        executor.request_cancel()
        status, message = await executor.run_loop()
        assert status == STATUS_CANCELLED
        assert "cancelled" in message.lower() or "cancel" in message.lower()

    @pytest.mark.asyncio
    async def test_run_loop_returns_cancelled_when_cancel_requested_during_loop(self):
        """When request_cancel is called during an iteration (e.g. from mock), next iteration returns CANCELLED."""
        executor = TodoTaskExecutor(
            api_key="test-key",
            task_id=1,
            task_description="Test",
            get_tools_func=AsyncMock(return_value=[]),
        )

        async def mock_llm_then_cancel(*args, **kwargs):
            # After first call, request cancel so next iteration exits
            executor.request_cancel()
            return {"content": "Working on it.", "tool_calls": None}

        with patch.object(executor, "_call_llm", side_effect=mock_llm_then_cancel):
            status, message = await executor.run_loop()
        assert status == STATUS_CANCELLED

    @pytest.mark.asyncio
    async def test_run_loop_returns_awaiting_confirmation_when_done_phrase_in_content(self):
        """When LLM returns content with done phrase, run_loop returns STATUS_AWAITING_CONFIRMATION."""
        executor = TodoTaskExecutor(
            api_key="test-key",
            task_id=1,
            task_description="Test",
            get_tools_func=AsyncMock(return_value=[]),
        )

        async def mock_llm_done(*args, **kwargs):
            return {"content": "I have finished the work for this task. Here is the summary.", "tool_calls": None}

        with patch.object(executor, "_call_llm", side_effect=mock_llm_done):
            status, message = await executor.run_loop()
        assert status == STATUS_AWAITING_CONFIRMATION
        assert "finished" in message.lower() or "task" in message.lower()


@pytest.mark.asyncio
async def test_ensure_token_budget_summarizes_when_over_limit(monkeypatch):
    monkeypatch.setenv("MAX_TOKEN_LIMIT", "50")
    executor = TodoTaskExecutor(
        api_key="test-key",
        task_id=1,
        task_description="Test",
        get_tools_func=AsyncMock(return_value=[]),
    )
    long_messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "x" * 500},
        {"role": "assistant", "content": "y" * 500},
        {"role": "user", "content": "z" * 500},
    ]
    summarized = [
        {"role": "system", "content": "system"},
        {"role": "system", "content": "Summary of previous context:\nsummary"},
        {"role": "user", "content": "tail"},
    ]
    executor._summarize_messages_for_budget = AsyncMock(return_value=summarized)
    result = await executor._ensure_token_budget(long_messages, max_tokens=2000)
    assert result == summarized
    assert executor._summarize_messages_for_budget.called


def test_initial_messages_include_experience_guidance():
    executor = TodoTaskExecutor(
        api_key="test-key",
        task_id=3,
        task_description="Prepare deployment notes",
        get_tools_func=AsyncMock(return_value=[]),
        experience_guidance="Experience hints from similar tasks:\n- Repeat: write output files.",
    )
    system_messages = [m.get("content", "") for m in executor.messages if m.get("role") == "system"]
    assert any("Experience guidance from similar past tasks" in msg for msg in system_messages)


@pytest.mark.asyncio
async def test_run_diagnostics_capture_tool_failures():
    executor = TodoTaskExecutor(
        api_key="test-key",
        task_id=9,
        task_description="Test tool diagnostics",
        tool_executor=AsyncMock(side_effect=RuntimeError("tool blew up")),
        get_tools_func=AsyncMock(
            return_value=[
                {
                    "name": "dummy_tool",
                    "description": "Dummy tool for tests",
                    "inputSchema": {"type": "object", "properties": {}},
                }
            ]
        ),
    )

    responses = [
        {
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "dummy_tool", "arguments": "{}"},
                }
            ],
        },
        {
            "content": "I have finished the work for this task.",
            "tool_calls": None,
        },
    ]

    async def _mock_llm(*args, **kwargs):
        return responses.pop(0)

    with patch.object(executor, "_call_llm", side_effect=_mock_llm):
        status, _ = await executor.run_loop()

    assert status == STATUS_AWAITING_CONFIRMATION
    diagnostics = executor.get_run_diagnostics()
    assert diagnostics["tool_failure_count"] == 1
    assert diagnostics["tool_success_count"] == 0
    assert "dummy_tool" in diagnostics["tool_usage_counts"]

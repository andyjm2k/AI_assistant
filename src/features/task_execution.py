"""
Task Execution: run a bounded LLM+tools loop to work on a todo task.
Human-in-the-loop: task is never auto-removed; user must confirm completion.
Supports pause for feedback and resume.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

import httpx

from src.utils.token_budget import (
    estimate_tokens_from_messages,
    format_messages_for_summary,
    get_max_token_limit,
    get_chars_per_token,
    is_context_limit_error,
)


# Status values for execution state
STATUS_EXECUTING = "executing"
STATUS_PAUSED_AWAITING_FEEDBACK = "paused_awaiting_feedback"
STATUS_AWAITING_CONFIRMATION = "awaiting_confirmation"
STATUS_CANCELLED = "cancelled"

# Phrases in LLM content that trigger pause or done (case-insensitive)
PAUSE_PHRASES = [
    "need feedback", "need your input", "need more context", "[pause]", "pause for feedback",
    "need clarification", "need your decision", "waiting for input", "need direction",
]
DONE_PHRASES = [
    "task complete", "task is complete", "i have finished", "[done]", "awaiting your confirmation",
    "i'm done", "i am done", "finished the work", "work is complete", "task is done",
    "i have finished the work for this task",
    "completed the task", "task has been completed", "i've completed", "i have completed the task",
]


class TodoTaskExecutor:
    """
    Runs a bounded loop of LLM + tool calls to work toward completing a todo task.
    Never removes the task; caller must confirm completion.
    """

    def __init__(
        self,
        api_key: str,
        task_id: int,
        task_description: str,
        prompt_override: Optional[str] = None,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        max_iterations: int = 20,
        tool_executor: Optional[Any] = None,
        get_tools_func: Optional[Any] = None,
        experience_guidance: Optional[str] = None,
    ):
        self.api_key = api_key
        self.api_base = (api_base or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.task_id = task_id
        self.task_description = task_description
        self.prompt_override = (prompt_override or "").strip() or None
        self.experience_guidance = (experience_guidance or "").strip() or None
        self.max_iterations = max(max_iterations, 1)
        self.tool_executor = tool_executor
        self.get_tools_func = get_tools_func
        self.messages: List[Dict[str, Any]] = []
        self.iteration_count = 0
        self._available_tools: Optional[List[Dict]] = None
        # Flag set by request_cancel(); run_loop checks it each iteration to exit cleanly
        self._cancel_requested = False
        self._max_token_limit = get_max_token_limit()
        self.last_error: Optional[str] = None
        self._run_started_at = time.time()
        self.tool_usage_counts: Dict[str, int] = {}
        self.tool_error_messages: List[str] = []
        self.tool_success_count = 0
        self.tool_failure_count = 0
        self._build_initial_messages()

    def _estimate_total_tokens(self, messages: List[Dict[str, Any]], max_tokens: int) -> int:
        return estimate_tokens_from_messages(messages) + max_tokens

    async def _summarize_messages_for_budget(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int,
    ) -> List[Dict[str, Any]]:
        if not messages:
            return messages

        system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
        remainder = messages[1:] if system_msg else messages[:]
        if len(remainder) <= 4:
            return messages

        keep_tail_options = [8, 6, 4, 2]
        summary_text = ""
        summary_source = remainder

        for keep_tail in keep_tail_options:
            if len(remainder) <= keep_tail:
                continue
            head = remainder[:-keep_tail]
            tail = remainder[-keep_tail:]

            summary_source_text = format_messages_for_summary(head, max_chars=40000)
            if not summary_source_text.strip():
                break

            summary_prompt = (
                "Summarize the prior conversation so the task can continue with full context. "
                "Include key requirements, decisions, file paths, commands run, tool outputs, errors, "
                "and remaining TODOs. Keep it concise and structured."
            )
            summary_messages = [
                {
                    "role": "system",
                    "content": "You are a summarization assistant. Summarize accurately and concisely.",
                },
                {
                    "role": "user",
                    "content": f"{summary_prompt}\n\nConversation:\n{summary_source_text}",
                },
            ]

            try:
                summary_response = await self._call_llm(
                    summary_messages,
                    tools=None,
                    max_tokens=800,
                    temperature=0.2,
                    allow_summarize=False,
                )
                if summary_response and summary_response.get("content"):
                    summary_text = summary_response.get("content").strip()
            except Exception:
                summary_text = ""

            if not summary_text:
                summary_text = summary_source_text[-2000:] if summary_source_text else ""

            new_messages: List[Dict[str, Any]] = []
            if system_msg:
                new_messages.append(system_msg)
            new_messages.append(
                {
                    "role": "system",
                    "content": f"Summary of previous context:\n{summary_text}",
                }
            )
            new_messages.extend(tail)

            if self._estimate_total_tokens(new_messages, max_tokens) <= self._max_token_limit:
                return new_messages

        return messages

    async def _ensure_token_budget(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int,
    ) -> List[Dict[str, Any]]:
        if self._estimate_total_tokens(messages, max_tokens) <= self._max_token_limit:
            return messages
        summarized = await self._summarize_messages_for_budget(messages, max_tokens=max_tokens)
        return summarized

    def _truncate_middle(self, text: str, max_chars: int) -> str:
        if not text or max_chars <= 0 or len(text) <= max_chars:
            return text
        keep_head = max_chars // 2
        keep_tail = max_chars - keep_head
        removed = len(text) - max_chars
        return f"{text[:keep_head]}\n\n...[truncated {removed} chars]...\n\n{text[-keep_tail:]}"

    def _force_trim_messages(self, messages: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
        if not messages:
            return messages
        chars_per_token = get_chars_per_token()
        max_total_chars = max(2000, (self._max_token_limit - max_tokens) * chars_per_token)
        max_per_message = min(20000, max_total_chars)

        trimmed: List[Dict[str, Any]] = []
        for msg in messages:
            new_msg = dict(msg)
            content = new_msg.get("content")
            if isinstance(content, list):
                try:
                    content = json.dumps(content, ensure_ascii=False)
                except (TypeError, ValueError):
                    content = str(content)
            if isinstance(content, str) and len(content) > max_per_message:
                new_msg["content"] = self._truncate_middle(content, max_per_message)
            trimmed.append(new_msg)

        def total_chars(msgs: List[Dict[str, Any]]) -> int:
            total = 0
            for m in msgs:
                c = m.get("content")
                if c is None:
                    continue
                if isinstance(c, list):
                    try:
                        c = json.dumps(c, ensure_ascii=False)
                    except (TypeError, ValueError):
                        c = str(c)
                total += len(str(c))
            return total

        if total_chars(trimmed) <= max_total_chars:
            return trimmed

        system_msg = trimmed[0] if trimmed and trimmed[0].get("role") == "system" else None
        tail_keep = 6
        tail = trimmed[-tail_keep:] if len(trimmed) > tail_keep else trimmed[:]
        head = []
        if system_msg:
            head.append(system_msg)
        compact = head + tail if head else tail

        for m in compact:
            if m is system_msg:
                continue
            if m.get("content") is None:
                continue
            content = m.get("content")
            if isinstance(content, str) and len(content) > max_per_message:
                m["content"] = self._truncate_middle(content, max_per_message)

        if total_chars(compact) <= max_total_chars:
            return compact

        # Last resort: drop older messages (keep system + last 4)
        tail_keep = 4
        tail = trimmed[-tail_keep:] if len(trimmed) > tail_keep else trimmed[:]
        return [system_msg] + tail if system_msg else tail

    def _build_initial_messages(self) -> None:
        goal = self.prompt_override or self.task_description
        system = (
            "You are helping complete a todo task. Use all available tools (search, files, etc.) to make progress. "
            "When you need a decision or more context from the user, say so clearly (e.g. 'I need your input' or 'need feedback') and we will pause for their input. "
            "When you have finished the work for this task, include the phrase 'I have finished the work for this task' so the system can record completion and wait for user confirmation. "
            "Never claim the task is deleted or removed—only the user can confirm completion. "
            "Tool selection: For CATBot codebase changes or new tool capabilities, prefer runCodexCli with a clear prompt. "
            "For other coding tasks (building apps, generating code, creating scripts), prefer runWorkflow with a clear contentPrompt rather than writing code manually with write_file. "
            "For web tasks that need browser actions (navigate, click, fill forms, automate a site), use run_browser_agent with an instruction. "
            "For in-depth research (compare sources, gather information across many pages, produce a research report), use run_deep_research with a research_task. "
            "Before finishing: always write the final output (report, summary, code, or results) to a file using the write_file tool so the user has a persistent copy; then say you have finished the work for this task."
        )
        self.messages = [{"role": "system", "content": system}]
        if self.experience_guidance:
            self.messages.append(
                {
                    "role": "system",
                    "content": (
                        "Experience guidance from similar past tasks. Use this as hints, but adapt to the current task:\n"
                        f"{self.experience_guidance}"
                    ),
                }
            )
        self.messages.append(
            {
                "role": "user",
                "content": (
                    f"Todo task (id {self.task_id}): {self.task_description}\n\n"
                    f"Goal for this run: {goal}\n\n"
                    "Please work on this task. Use tools as needed."
                ),
            }
        )

    def _looks_like_tool_error_result(self, result: Any) -> bool:
        """Best-effort classifier for tool-call failures."""
        if isinstance(result, dict):
            if result.get("success") is False:
                return True
            msg = str(result.get("message") or "").strip().lower()
            if msg.startswith("error") or "exception" in msg:
                return True
            return False
        text = str(result or "").strip().lower()
        if not text:
            return False
        return (
            text.startswith("error:")
            or "traceback" in text
            or '"success": false' in text
            or "'success': false" in text
        )

    def _record_tool_usage(self, tool_name: str, result: Any, errored: bool = False) -> None:
        name = str(tool_name or "unknown")
        self.tool_usage_counts[name] = self.tool_usage_counts.get(name, 0) + 1
        is_error = errored or self._looks_like_tool_error_result(result)
        if is_error:
            self.tool_failure_count += 1
            summary = str(result or "tool error")
            if len(summary) > 240:
                summary = summary[:237] + "..."
            self.tool_error_messages.append(f"{name}: {summary}")
            self.tool_error_messages = self.tool_error_messages[-10:]
        else:
            self.tool_success_count += 1

    async def _get_tools(self) -> List[Dict]:
        if self._available_tools is not None:
            return self._available_tools
        if not self.get_tools_func:
            return []
        try:
            raw = await self.get_tools_func()
            openai_tools = []
            for t in raw:
                name = t.get("name")
                if not name:
                    continue
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": t.get("description", ""),
                        "parameters": t.get("inputSchema", {}),
                    },
                })
            self._available_tools = openai_tools
            return openai_tools
        except Exception as e:
            print(f"[TASK_EXEC] Error getting tools: {e}")
            return []

    async def _call_llm(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.6,
        max_tokens: int = 2000,
        allow_summarize: bool = True,
        _retry_on_context_error: bool = True,
    ) -> Optional[Dict]:
        url = f"{self.api_base}/chat/completions"
        final_messages = messages
        if allow_summarize:
            final_messages = await self._ensure_token_budget(messages, max_tokens=max_tokens)
            if messages is self.messages and final_messages is not messages:
                self.messages = final_messages
        payload = {"model": self.model, "messages": final_messages, "temperature": temperature, "max_tokens": max_tokens}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        org = os.getenv("OPENAI_ORG_ID") or os.getenv("OPENAI_ORGANIZATION")
        if org:
            headers["OpenAI-Organization"] = org
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(url, headers=headers, json=payload)
            if r.status_code != 200:
                error_text = r.text[:500]
                print(f"[TASK_EXEC] LLM error {r.status_code}: {error_text}")
                self.last_error = f"LLM error {r.status_code}: {error_text}"
                if allow_summarize and _retry_on_context_error and is_context_limit_error(r.status_code, error_text):
                    summarized = await self._ensure_token_budget(messages, max_tokens=max_tokens)
                    if summarized is not messages:
                        if messages is self.messages:
                            self.messages = summarized
                        retry = await self._call_llm(
                            summarized,
                            tools=tools,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            allow_summarize=False,
                            _retry_on_context_error=False,
                        )
                        if retry:
                            return retry
                    # Force-trim if summarization/estimation didn't reduce enough
                    forced = self._force_trim_messages(summarized, max_tokens=max_tokens)
                    if forced is not summarized:
                        if messages is self.messages:
                            self.messages = forced
                        return await self._call_llm(
                            forced,
                            tools=tools,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            allow_summarize=False,
                            _retry_on_context_error=False,
                        )
                return None
            data = r.json()
            choices = data.get("choices", [])
            if not choices:
                return None
            msg = choices[0].get("message", {})
            return {"content": msg.get("content"), "tool_calls": msg.get("tool_calls")}
        except Exception as e:
            print(f"[TASK_EXEC] LLM request failed: {e}")
            self.last_error = f"LLM request failed: {e}"
            return None

    def _check_pause_or_done(self, content: str) -> Optional[str]:
        """Check assistant content for pause or done. Prefer DONE over PAUSE when both might match."""
        if not content:
            return None
        lower = content.lower()
        # Check done first so completion is detected even if message also asks for confirmation
        for phrase in DONE_PHRASES:
            if phrase in lower:
                return STATUS_AWAITING_CONFIRMATION
        for phrase in PAUSE_PHRASES:
            if phrase in lower:
                return STATUS_PAUSED_AWAITING_FEEDBACK
        return None

    async def run_loop(self) -> tuple:
        """
        Run iterations until max or pause or done. Returns (status, message).
        """
        tools = await self._get_tools()
        last_message = ""
        while self.iteration_count < self.max_iterations:
            # Check for user-requested cancel at each iteration so we can exit cleanly
            if self._cancel_requested:
                print(f"[TASK_EXEC] Cancel requested (iteration {self.iteration_count})")
                return (STATUS_CANCELLED, last_message or "Cancelled by user.")
            self.iteration_count += 1
            llm_response = await self._call_llm(self.messages, tools=tools if tools else None)
            if not llm_response:
                return (STATUS_AWAITING_CONFIRMATION, last_message or self.last_error or "Execution stopped (no response).")
            content = (llm_response.get("content") or "").strip()
            tool_calls = llm_response.get("tool_calls")
            # Check content for done/pause even when there are tool_calls (model may say "I'm done" and still emit a final tool call)
            if content:
                status = self._check_pause_or_done(content)
                if status:
                    # Append only content so we don't leave unexecuted tool_calls in history
                    self.messages.append({"role": "assistant", "content": content})
                    print(f"[TASK_EXEC] Detected {status} in assistant message (iteration {self.iteration_count})")
                    return (status, content)
            if tool_calls and self.tool_executor:
                self.messages.append({
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": tool_calls,
                })
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name")
                    raw_args = fn.get("arguments", "{}")
                    args = raw_args
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    # Log raw arguments when empty or when write_file lacks filename (debug LLM tool-call issues)
                    if not args or (name == "write_file" and not (args.get("filename") or args.get("content"))):
                        print(f"[TASK_EXEC] Tool {name!r} raw arguments: {raw_args!r}", flush=True)
                    try:
                        result = await self.tool_executor(name, args)
                        self._record_tool_usage(name, result, errored=False)
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id"),
                            "content": str(result),
                        })
                    except Exception as e:
                        self._record_tool_usage(name, str(e), errored=True)
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id"),
                            "content": f"Error: {e}",
                        })
                last_message = content or last_message
                continue
            self.messages.append({"role": "assistant", "content": content or "(No content)"})
            last_message = content
            if content:
                status = self._check_pause_or_done(content)
                if status:
                    print(f"[TASK_EXEC] Detected {status} in assistant message (iteration {self.iteration_count})")
                    return (status, last_message)
            if self.iteration_count >= self.max_iterations:
                print(f"[TASK_EXEC] Reached max iterations ({self.max_iterations}), returning awaiting_confirmation")
                return (STATUS_AWAITING_CONFIRMATION, last_message or f"Reached max iterations ({self.max_iterations}).")
        return (STATUS_AWAITING_CONFIRMATION, last_message or "Done.")

    def add_user_message(self, text: str) -> None:
        self.messages.append({"role": "user", "content": (text or "").strip()})

    def request_cancel(self) -> None:
        """Request that run_loop exit at the next iteration boundary (soft cancel)."""
        self._cancel_requested = True

    def get_run_diagnostics(self) -> Dict[str, Any]:
        """Return diagnostics that can be used for experience-based learning."""
        elapsed_seconds = max(0.0, time.time() - self._run_started_at)
        return {
            "task_id": self.task_id,
            "task_description": self.task_description,
            "iterations": self.iteration_count,
            "max_iterations": self.max_iterations,
            "elapsed_seconds": elapsed_seconds,
            "tool_usage_counts": dict(self.tool_usage_counts),
            "tools_used": list(self.tool_usage_counts.keys()),
            "tool_success_count": self.tool_success_count,
            "tool_failure_count": self.tool_failure_count,
            "tool_error_messages": list(self.tool_error_messages),
            "last_error": self.last_error,
        }

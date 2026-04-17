"""
Task Execution: run a bounded LLM+tools loop to work on a todo task.
Human-in-the-loop: task is never auto-removed; user must confirm completion.
Supports pause for feedback and resume.
"""

import inspect
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.utils.token_budget import (
    estimate_tokens_from_messages,
    format_messages_for_summary,
    get_max_token_limit,
    get_chars_per_token,
    is_context_limit_error,
)
from src.utils.openai_compat import (
    is_minimax_chat_request,
    normalize_chat_completion_message,
    prepare_openai_compatible_chat_payload,
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
_GENERIC_DONE_MESSAGE_MAX_CHARS = 140
_GENERIC_DONE_PHRASES = tuple(
    sorted(
        {
            phrase.strip().lower().strip(" .!?:;")
            for phrase in DONE_PHRASES
            if isinstance(phrase, str) and phrase.strip()
        }
        | {"done"}
    )
)

_NO_KEY_LLM_PROVIDERS = frozenset({"ollama", "bedrock"})
_MCP_PROVIDER_API_KEY_ENV_CANDIDATES: Dict[str, List[str]] = {
    "openai": ["OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"],
    "minimax": [
        "MINIMAX_API_KEY",
        "MCP_LLM_MINIMAX_API_KEY",
        "MCP_LLM_OPENAI_API_KEY",
        "OPENAI_API_KEY",
    ],
    "anthropic": ["ANTHROPIC_API_KEY", "MCP_LLM_ANTHROPIC_API_KEY"],
    "google": ["GEMINI_API_KEY", "GOOGLE_API_KEY", "MCP_LLM_GOOGLE_API_KEY"],
    "azure_openai": ["AZURE_OPENAI_API_KEY", "MCP_LLM_AZURE_OPENAI_API_KEY"],
    "groq": ["GROQ_API_KEY", "MCP_LLM_GROQ_API_KEY"],
    "deepseek": ["DEEPSEEK_API_KEY", "MCP_LLM_DEEPSEEK_API_KEY"],
    "cerebras": ["CEREBRAS_API_KEY", "MCP_LLM_CEREBRAS_API_KEY"],
    "browser_use": ["BROWSER_USE_API_KEY", "MCP_LLM_BROWSER_USE_API_KEY"],
    "openrouter": [
        "OPENROUTER_API_KEY",
        "MCP_LLM_OPENROUTER_API_KEY",
        "MCP_LLM_OPENAI_API_KEY",
        "OPENAI_API_KEY",
    ],
    "vercel": ["VERCEL_API_KEY", "MCP_LLM_VERCEL_API_KEY"],
}

def _normalize_chat_endpoint(endpoint: str) -> str:
    if not endpoint:
        return ""
    if endpoint.endswith("/chat/completions"):
        return endpoint
    return endpoint.rstrip("/") + "/chat/completions"


def _first_non_empty_env(var_names: List[str]) -> Optional[str]:
    for var_name in var_names:
        value = os.getenv(var_name)
        if value and value.strip():
            return value.strip()
    return None


def _get_mcp_llm_provider() -> str:
    return (os.getenv("MCP_LLM_PROVIDER") or "").strip().lower()


def _get_mcp_llm_chat_endpoint() -> Optional[str]:
    base = (os.getenv("MCP_LLM_BASE_URL") or "").strip()
    if not base:
        return None
    return _normalize_chat_endpoint(base)


def _get_mcp_llm_model_name() -> Optional[str]:
    model_name = (os.getenv("MCP_LLM_MODEL_NAME") or "").strip()
    return model_name or None


def _resolve_mcp_llm_api_key(provider: Optional[str] = None) -> Optional[str]:
    normalized_provider = (provider or _get_mcp_llm_provider() or "").strip().lower()
    candidates: List[str] = ["MCP_LLM_API_KEY"]
    candidates.extend(_MCP_PROVIDER_API_KEY_ENV_CANDIDATES.get(normalized_provider, []))

    if normalized_provider:
        candidates.append(f"MCP_LLM_{normalized_provider.upper()}_API_KEY")
    else:
        # OpenAI-compatible default fallback for generic/unspecified provider.
        candidates.extend(["MCP_LLM_OPENAI_API_KEY", "OPENAI_API_KEY"])

    api_key = _first_non_empty_env(candidates)
    if api_key:
        return api_key
    if normalized_provider in _NO_KEY_LLM_PROVIDERS:
        return None
    return None


def _build_mcp_fallback_headers(primary_headers: Dict[str, str]) -> Dict[str, str]:
    headers: Dict[str, str] = {"Content-Type": "application/json"}

    for header_name in ("OpenAI-Organization", "OpenAI-Project", "HTTP-Referer", "X-Title"):
        header_value = primary_headers.get(header_name)
        if header_value:
            headers[header_name] = header_value

    provider = _get_mcp_llm_provider()
    api_key = _resolve_mcp_llm_api_key(provider)
    inherited_auth = (primary_headers.get("Authorization") or "").strip()

    if provider == "azure_openai":
        if api_key:
            headers["api-key"] = api_key
        elif inherited_auth.lower().startswith("bearer "):
            inherited_token = inherited_auth[7:].strip()
            if inherited_token:
                headers["api-key"] = inherited_token
        return headers

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif inherited_auth:
        headers["Authorization"] = inherited_auth
    return headers


def _build_mcp_fallback_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    fallback_payload = dict(payload)
    fallback_model = _get_mcp_llm_model_name()
    if fallback_model:
        fallback_payload["model"] = fallback_model
    return fallback_payload


def _extract_llm_error_text(response: httpx.Response) -> str:
    detail = (response.text or "").strip()
    try:
        payload = response.json()
    except ValueError:
        return detail
    if isinstance(payload, dict):
        message = payload.get("error")
        if isinstance(message, dict):
            detail = str(message.get("message") or detail)
        else:
            detail = str(payload.get("message") or payload.get("detail") or message or detail)
    return detail


def _normalize_completion_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _completion_message_is_generic_done(text: str) -> bool:
    normalized = _normalize_completion_text(text)
    if not normalized:
        return False
    if len(normalized) > _GENERIC_DONE_MESSAGE_MAX_CHARS:
        return False
    stripped = normalized.strip(" .!?:;")
    if stripped in _GENERIC_DONE_PHRASES:
        return True
    return any(phrase in normalized for phrase in DONE_PHRASES)


def _select_completion_message(content: str, last_tool_result: str) -> str:
    body = str(content or "").strip()
    tool_text = str(last_tool_result or "").strip()
    if tool_text and (not body or _completion_message_is_generic_done(body)):
        return tool_text
    return body


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
        progress_callback: Optional[Any] = None,
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
        self.progress_callback = progress_callback
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

    async def _emit_progress(self, event: str, **payload: Any) -> None:
        if not self.progress_callback:
            return
        try:
            maybe_awaitable = self.progress_callback(event, payload)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        except Exception as e:
            print(f"[TASK_EXEC] Progress callback error: {e}", flush=True)

    def _estimate_total_tokens(self, messages: List[Dict[str, Any]], max_tokens: int) -> int:
        return estimate_tokens_from_messages(messages) + max_tokens

    async def _post_chat_completion(
        self,
        endpoint: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        timeout_seconds: float = 60.0,
    ) -> httpx.Response:
        prepared_payload = prepare_openai_compatible_chat_payload(
            payload,
            api_base=endpoint,
            model=payload.get("model"),
        )
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            return await client.post(endpoint, headers=headers, json=prepared_payload)

    async def _attempt_mcp_fallback(
        self,
        primary_headers: Dict[str, str],
        payload: Dict[str, Any],
        source_label: str,
        timeout_seconds: float = 60.0,
    ) -> Tuple[Optional[httpx.Response], Optional[str]]:
        fallback_endpoint = _get_mcp_llm_chat_endpoint()
        if not fallback_endpoint:
            return None, "MCP_LLM_BASE_URL is not configured"

        fallback_payload = _build_mcp_fallback_payload(payload)
        fallback_headers = _build_mcp_fallback_headers(primary_headers)
        fallback_model = fallback_payload.get("model", "")
        fallback_provider = _get_mcp_llm_provider() or "openai-compatible"
        print(
            f"[TASK_EXEC][LLM_FALLBACK] {source_label}: trying provider={fallback_provider}, "
            f"model={fallback_model}, endpoint={fallback_endpoint}",
            flush=True,
        )
        try:
            response = await self._post_chat_completion(
                fallback_endpoint,
                fallback_headers,
                fallback_payload,
                timeout_seconds=timeout_seconds,
            )
            print(
                f"[TASK_EXEC][LLM_FALLBACK] {source_label}: status={response.status_code}",
                flush=True,
            )
            return response, None
        except httpx.RequestError as exc:
            err = str(exc)
            print(f"[TASK_EXEC][LLM_FALLBACK] {source_label}: request error: {err}", flush=True)
            return None, err

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
            "Response rules: when another tool is needed, call the tool immediately instead of narrating the next step. "
            "Do not say you will use a tool later; either emit the tool call now or give a substantive progress update/result. "
            "Do not ask the user to repeat filenames, URLs, search results, or prior tool output already available in the conversation. "
            "Tool selection: For CATBot codebase changes or new tool capabilities, prefer runCodexCli with a clear prompt. "
            "For other coding tasks (building apps, generating code, creating scripts), prefer runWorkflow with a clear contentPrompt rather than writing code manually with filesystem.write_text. "
            "For web tasks that need browser actions (navigate, click, fill forms, automate a site), use run_browser_agent with an instruction. "
            "For in-depth research (compare sources, gather information across many pages, produce a research report), use run_deep_research with a research_task. "
            "Before finishing: always write the final output (report, summary, code, or results) to a file using the filesystem.write_text tool so the user has a persistent copy; then say you have finished the work for this task."
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
        project = os.getenv("OPENAI_PROJECT_ID")
        if project:
            headers["OpenAI-Project"] = project
        try:
            response = await self._post_chat_completion(
                url,
                headers,
                payload,
                timeout_seconds=60.0,
            )
        except httpx.RequestError as e:
            print(f"[TASK_EXEC] LLM request failed: {e}")
            fallback_response, fallback_error = await self._attempt_mcp_fallback(
                primary_headers=headers,
                payload=payload,
                source_label="task_exec_primary_request_error",
                timeout_seconds=60.0,
            )
            if fallback_response is None:
                self.last_error = (
                    f"LLM request failed: {e}. "
                    f"Fallback error: {fallback_error or 'not configured'}"
                )
                return None
            response = fallback_response
        except Exception as e:
            print(f"[TASK_EXEC] LLM request failed: {e}")
            self.last_error = f"LLM request failed: {e}"
            return None

        if response.status_code != 200:
            error_text = _extract_llm_error_text(response)[:500]
            print(f"[TASK_EXEC] LLM error {response.status_code}: {error_text}")
            self.last_error = f"LLM error {response.status_code}: {error_text}"
            if allow_summarize and _retry_on_context_error and is_context_limit_error(response.status_code, error_text):
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
                    retry = await self._call_llm(
                        forced,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        allow_summarize=False,
                        _retry_on_context_error=False,
                    )
                    if retry:
                        return retry

            fallback_response, fallback_error = await self._attempt_mcp_fallback(
                primary_headers=headers,
                payload=payload,
                source_label="task_exec_primary_non_200",
                timeout_seconds=60.0,
            )
            if fallback_response is None:
                if fallback_error:
                    self.last_error = (
                        f"{self.last_error}. Fallback error: {fallback_error}"
                    )
                return None
            if fallback_response.status_code != 200:
                fallback_error_text = _extract_llm_error_text(fallback_response)[:500]
                self.last_error = (
                    f"{self.last_error}. Fallback LLM error {fallback_response.status_code}: "
                    f"{fallback_error_text}"
                )
                return None
            response = fallback_response

        try:
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return None
            normalized = normalize_chat_completion_message(
                choices[0].get("message", {}),
                preserve_reasoning_details=is_minimax_chat_request(url, self.model),
            )
            return normalized
        except Exception as e:
            print(f"[TASK_EXEC] Failed to parse LLM response: {e}")
            self.last_error = f"Failed to parse LLM response: {e}"
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
        last_successful_tool_result = ""
        await self._emit_progress(
            "workflow_start",
            task_id=self.task_id,
            workflow_name=self.task_description,
            phase="preparation",
            message=f"Starting task execution for task {self.task_id}.",
            current_step=self.iteration_count,
            total_steps=self.max_iterations,
        )
        while self.iteration_count < self.max_iterations:
            # Check for user-requested cancel at each iteration so we can exit cleanly
            if self._cancel_requested:
                print(f"[TASK_EXEC] Cancel requested (iteration {self.iteration_count})")
                await self._emit_progress(
                    "cancel_requested",
                    task_id=self.task_id,
                    workflow_name=self.task_description,
                    phase="cancelled",
                    message=f"Cancellation requested for task {self.task_id}.",
                    current_step=self.iteration_count,
                    total_steps=self.max_iterations,
                )
                return (STATUS_CANCELLED, last_message or "Cancelled by user.")
            self.iteration_count += 1
            await self._emit_progress(
                "iteration_start",
                task_id=self.task_id,
                workflow_name=self.task_description,
                phase="executing",
                message=f"Running task step {self.iteration_count} of {self.max_iterations}.",
                current_step=self.iteration_count,
                total_steps=self.max_iterations,
            )
            llm_response = await self._call_llm(self.messages, tools=tools if tools else None)
            if not llm_response:
                await self._emit_progress(
                    "llm_no_response",
                    task_id=self.task_id,
                    workflow_name=self.task_description,
                    phase="awaiting_confirmation",
                    message="Task execution stopped because the model returned no response.",
                    current_step=self.iteration_count,
                    total_steps=self.max_iterations,
                )
                return (STATUS_AWAITING_CONFIRMATION, last_message or self.last_error or "Execution stopped (no response).")
            content = (llm_response.get("content") or "").strip()
            tool_calls = llm_response.get("tool_calls")
            pending_status: Optional[str] = None
            # If the model returns done/pause text with tool_calls, execute tool_calls first
            # so final side effects (e.g. filesystem.write_text) are not skipped.
            if content:
                status = self._check_pause_or_done(content)
                if status and not tool_calls:
                    final_message = _select_completion_message(content, last_successful_tool_result)
                    self.messages.append(
                        llm_response.get("message") or {"role": "assistant", "content": content}
                    )
                    print(f"[TASK_EXEC] Detected {status} in assistant message (iteration {self.iteration_count})")
                    await self._emit_progress(
                        "status_detected",
                        task_id=self.task_id,
                        workflow_name=self.task_description,
                        phase=status,
                        message=final_message or content,
                        current_step=self.iteration_count,
                        total_steps=self.max_iterations,
                    )
                    return (status, final_message or content)
                pending_status = status
            if tool_calls and self.tool_executor:
                await self._emit_progress(
                    "tool_calls",
                    task_id=self.task_id,
                    workflow_name=self.task_description,
                    phase="executing",
                    message=f"Executing {len(tool_calls)} tool call(s) in step {self.iteration_count}.",
                    current_step=self.iteration_count,
                    total_steps=self.max_iterations,
                    tool_call_count=len(tool_calls),
                )
                self.messages.append(
                    llm_response.get("message") or {
                        "role": "assistant",
                        "content": content or None,
                        "tool_calls": tool_calls,
                    }
                )
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
                    # Log raw arguments when empty or when file-write calls lack a target path.
                    if not args or (
                        name in {"write_file", "filesystem.write_text"}
                        and not (args.get("filename") or args.get("path") or args.get("content"))
                    ):
                        print(f"[TASK_EXEC] Tool {name!r} raw arguments: {raw_args!r}", flush=True)
                    try:
                        result = await self.tool_executor(name, args)
                        self._record_tool_usage(name, result, errored=False)
                        result_text = str(result).strip()
                        if result_text:
                            last_successful_tool_result = result_text
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
                if pending_status:
                    final_message = _select_completion_message(last_message or content or "", last_successful_tool_result)
                    print(
                        f"[TASK_EXEC] Detected {pending_status} in assistant message after tool execution "
                        f"(iteration {self.iteration_count})"
                    )
                    await self._emit_progress(
                        "status_detected_after_tools",
                        task_id=self.task_id,
                        workflow_name=self.task_description,
                        phase=pending_status,
                        message=final_message or last_message or content or "",
                        current_step=self.iteration_count,
                        total_steps=self.max_iterations,
                    )
                    return (pending_status, final_message or last_message or content or "")
                continue
            self.messages.append({"role": "assistant", "content": content or "(No content)"})
            last_message = content
            if content:
                status = self._check_pause_or_done(content)
                if status:
                    final_message = _select_completion_message(last_message, last_successful_tool_result)
                    print(f"[TASK_EXEC] Detected {status} in assistant message (iteration {self.iteration_count})")
                    await self._emit_progress(
                        "status_detected",
                        task_id=self.task_id,
                        workflow_name=self.task_description,
                        phase=status,
                        message=final_message or last_message,
                        current_step=self.iteration_count,
                        total_steps=self.max_iterations,
                    )
                    return (status, final_message or last_message)
            if self.iteration_count >= self.max_iterations:
                print(f"[TASK_EXEC] Reached max iterations ({self.max_iterations}), returning awaiting_confirmation")
                await self._emit_progress(
                    "max_iterations_reached",
                    task_id=self.task_id,
                    workflow_name=self.task_description,
                    phase="awaiting_confirmation",
                    message=f"Reached max iterations ({self.max_iterations}).",
                    current_step=self.iteration_count,
                    total_steps=self.max_iterations,
                )
                return (STATUS_AWAITING_CONFIRMATION, last_message or f"Reached max iterations ({self.max_iterations}).")
        await self._emit_progress(
            "workflow_complete",
            task_id=self.task_id,
            workflow_name=self.task_description,
            phase="awaiting_confirmation",
            message=last_message or "Done.",
            current_step=self.iteration_count,
            total_steps=self.max_iterations,
        )
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

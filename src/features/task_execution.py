"""
Task Execution: run a bounded LLM+tools loop to work on a todo task.
Human-in-the-loop: task is never auto-removed; user must confirm completion.
Supports pause for feedback and resume.
"""

import json
import os
from typing import Any, Dict, List, Optional

import httpx


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
    ):
        self.api_key = api_key
        self.api_base = (api_base or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.task_id = task_id
        self.task_description = task_description
        self.prompt_override = (prompt_override or "").strip() or None
        self.max_iterations = max(max_iterations, 1)
        self.tool_executor = tool_executor
        self.get_tools_func = get_tools_func
        self.messages: List[Dict[str, Any]] = []
        self.iteration_count = 0
        self._available_tools: Optional[List[Dict]] = None
        # Flag set by request_cancel(); run_loop checks it each iteration to exit cleanly
        self._cancel_requested = False
        self._build_initial_messages()

    def _build_initial_messages(self) -> None:
        goal = self.prompt_override or self.task_description
        system = (
            "You are helping complete a todo task. Use all available tools (search, files, etc.) to make progress. "
            "When you need a decision or more context from the user, say so clearly (e.g. 'I need your input' or 'need feedback') and we will pause for their input. "
            "When you have finished the work for this task, include the phrase 'I have finished the work for this task' so the system can record completion and wait for user confirmation. "
            "Never claim the task is deleted or removed—only the user can confirm completion. "
            "Tool selection: For coding tasks (building apps, generating code, creating scripts), prefer runWorkflow with a clear contentPrompt rather than writing code manually with write_file. "
            "For web tasks that need browser actions (navigate, click, fill forms, automate a site), use run_browser_agent with an instruction. "
            "For in-depth research (compare sources, gather information across many pages, produce a research report), use run_deep_research with a research_task. "
            "Before finishing: always write the final output (report, summary, code, or results) to a file using the write_file tool so the user has a persistent copy; then say you have finished the work for this task."
        )
        self.messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Todo task (id {self.task_id}): {self.task_description}\n\nGoal for this run: {goal}\n\nPlease work on this task. Use tools as needed."},
        ]

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

    async def _call_llm(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Optional[Dict]:
        url = f"{self.api_base}/chat/completions"
        payload = {"model": self.model, "messages": messages, "temperature": 0.6, "max_tokens": 2000}
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
                print(f"[TASK_EXEC] LLM error {r.status_code}: {r.text[:200]}")
                return None
            data = r.json()
            choices = data.get("choices", [])
            if not choices:
                return None
            msg = choices[0].get("message", {})
            return {"content": msg.get("content"), "tool_calls": msg.get("tool_calls")}
        except Exception as e:
            print(f"[TASK_EXEC] LLM request failed: {e}")
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
                return (STATUS_AWAITING_CONFIRMATION, last_message or "Execution stopped (no response).")
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
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id"),
                            "content": str(result),
                        })
                    except Exception as e:
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

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from .types import WorkflowAvailability, WorkflowMessage, WorkflowRunResult


class AutoGenWorkflowRunner:
    framework = "autogen"

    def __init__(
        self,
        run_callback: Callable[[str], Awaitable[Dict[str, Any]]],
        *,
        available: bool = True,
        unavailable_message: str = "AutoGen backend is not available.",
    ) -> None:
        self._run_callback = run_callback
        self._available = available
        self._unavailable_message = unavailable_message

    def available(self) -> WorkflowAvailability:
        if self._available:
            return WorkflowAvailability(True, self.framework, "AutoGen backend available.")
        return WorkflowAvailability(False, self.framework, self._unavailable_message)

    def load(self) -> object:
        return self

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def run(self, input_text: str) -> WorkflowRunResult:
        payload = await self._run_callback(input_text)
        messages = [
            WorkflowMessage(
                source=str(item.get("source") or "unknown"),
                content=str(item.get("content") or ""),
            )
            for item in payload.get("messages", [])
            if isinstance(item, dict)
        ]
        return WorkflowRunResult(
            framework=self.framework,
            output=str(payload.get("output") or payload.get("response") or ""),
            summary=str(payload.get("summary") or payload.get("output") or payload.get("response") or ""),
            messages=messages,
            log_file=payload.get("log_file"),
            log_content=str(payload.get("log_content") or ""),
            metadata={"message_count": payload.get("message_count", len(messages))},
        )

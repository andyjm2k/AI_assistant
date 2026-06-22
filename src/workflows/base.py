from __future__ import annotations

from typing import Protocol

from .types import WorkflowAvailability, WorkflowRunResult


class WorkflowRunner(Protocol):
    framework: str

    def available(self) -> WorkflowAvailability:
        ...

    def load(self) -> object:
        ...

    async def start(self) -> None:
        ...

    async def stop(self) -> None:
        ...

    async def run(self, input_text: str) -> WorkflowRunResult:
        ...

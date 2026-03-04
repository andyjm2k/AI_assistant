"""Execution engine for registered CATBot skills and tools."""

from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .exceptions import SkillFrameworkError, ToolExecutionError
from .models import SkillContext, ToolExecutionResult
from .registry import SkillRegistry

PreExecuteHook = Callable[[str, Dict[str, Any], SkillContext], Optional[Awaitable[None]]]
PostExecuteHook = Callable[
    [str, Dict[str, Any], SkillContext, ToolExecutionResult], Optional[Awaitable[None]]
]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class SkillExecutor:
    """Execute tools from a registry with consistent result shape."""

    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry
        self._pre_hooks: List[PreExecuteHook] = []
        self._post_hooks: List[PostExecuteHook] = []

    def add_pre_hook(self, hook: PreExecuteHook) -> None:
        self._pre_hooks.append(hook)

    def add_post_hook(self, hook: PostExecuteHook) -> None:
        self._post_hooks.append(hook)

    async def execute(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[SkillContext] = None,
        raise_errors: bool = False,
    ) -> ToolExecutionResult:
        args = arguments or {}
        ctx = context or SkillContext()

        try:
            resolved = self.registry.resolve_tool(tool_name)
            qualified_name = resolved.qualified_name

            for hook in self._pre_hooks:
                await _maybe_await(hook(qualified_name, args, ctx))

            raw_result = await _maybe_await(resolved.tool.run(args, ctx))
            if isinstance(raw_result, ToolExecutionResult):
                result = raw_result
                if not result.tool_name:
                    result.tool_name = qualified_name
            else:
                result = ToolExecutionResult(
                    success=True,
                    message="OK",
                    data=raw_result,
                    tool_name=qualified_name,
                )
        except SkillFrameworkError:
            if raise_errors:
                raise
            result = ToolExecutionResult(
                success=False,
                message=f"Framework error while executing '{tool_name}'.",
                error_code="framework_error",
                tool_name=tool_name,
            )
        except Exception as exc:
            if raise_errors:
                raise ToolExecutionError(
                    f"Tool '{tool_name}' execution failed: {exc}"
                ) from exc
            result = ToolExecutionResult(
                success=False,
                message=str(exc),
                error_code="execution_error",
                tool_name=tool_name,
            )

        for hook in self._post_hooks:
            await _maybe_await(hook(result.tool_name or tool_name, args, ctx, result))
        return result

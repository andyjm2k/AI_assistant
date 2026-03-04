"""Base classes for CATBot skills and tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Sequence

from .exceptions import SkillValidationError
from .models import SkillContext, SkillSpec, ToolSpec


class BaseTool(ABC):
    """Base class for all tools."""

    name: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = {"type": "object", "properties": {}}
    tags: List[str] = []

    def validate(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise SkillValidationError("Tool must define a non-empty string 'name'.")
        if "." in self.name:
            raise SkillValidationError(f"Tool name '{self.name}' cannot contain '.'.")
        if not isinstance(self.input_schema, dict):
            raise SkillValidationError(
                f"Tool '{self.name}' input_schema must be a dictionary."
            )

    def get_spec(self, skill_name: str) -> ToolSpec:
        self.validate()
        return ToolSpec(
            skill_name=skill_name,
            name=self.name,
            description=self.description or "",
            input_schema=self.input_schema or {"type": "object", "properties": {}},
            tags=list(self.tags or []),
        )

    @abstractmethod
    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Any:
        """Execute tool logic and return structured output."""


class BaseSkill(ABC):
    """Base class for a modular skill."""

    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    tags: List[str] = []

    def __init__(self) -> None:
        self._tools_cache: List[BaseTool] | None = None

    @abstractmethod
    def create_tools(self) -> Sequence[BaseTool]:
        """Create tool instances provided by this skill."""

    def get_tools(self) -> List[BaseTool]:
        if self._tools_cache is None:
            self._tools_cache = list(self.create_tools() or [])
        return self._tools_cache

    def validate(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise SkillValidationError("Skill must define a non-empty string 'name'.")
        if "." in self.name:
            raise SkillValidationError(f"Skill name '{self.name}' cannot contain '.'.")
        seen: set[str] = set()
        for tool in self.get_tools():
            tool.validate()
            if tool.name in seen:
                raise SkillValidationError(
                    f"Duplicate tool name '{tool.name}' in skill '{self.name}'."
                )
            seen.add(tool.name)

    def get_spec(self) -> SkillSpec:
        self.validate()
        return SkillSpec(
            name=self.name,
            description=self.description or "",
            version=self.version or "1.0.0",
            tags=list(self.tags or []),
            tool_names=[tool.name for tool in self.get_tools()],
        )


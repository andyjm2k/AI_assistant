"""Registration and lookup for CATBot skills and tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .base import BaseSkill, BaseTool
from .exceptions import (
    AmbiguousToolError,
    SkillNotFoundError,
    SkillRegistrationError,
    ToolNotFoundError,
)
from .models import SkillSpec, ToolSpec


@dataclass(frozen=True)
class ResolvedTool:
    """Resolved tool object with metadata."""

    qualified_name: str
    tool: BaseTool
    spec: ToolSpec


class SkillRegistry:
    """Central registry for modular skills and their tools."""

    def __init__(self) -> None:
        self._skills: Dict[str, BaseSkill] = {}
        self._skill_specs: Dict[str, SkillSpec] = {}
        self._tools: Dict[str, BaseTool] = {}
        self._tool_specs: Dict[str, ToolSpec] = {}
        self._aliases: Dict[str, str] = {}
        self._ambiguous_aliases: set[str] = set()

    def register_skill(self, skill: BaseSkill, replace: bool = False) -> SkillSpec:
        """Register a skill and all its tools."""
        skill.validate()
        name = skill.name
        if name in self._skills and not replace:
            raise SkillRegistrationError(f"Skill '{name}' is already registered.")
        if replace and name in self._skills:
            self.unregister_skill(name)

        skill_spec = skill.get_spec()

        # Validate tool collisions before mutating registry state.
        pending_specs: List[ToolSpec] = [tool.get_spec(name) for tool in skill.get_tools()]
        for spec in pending_specs:
            if spec.qualified_name in self._tools:
                raise SkillRegistrationError(
                    f"Tool '{spec.qualified_name}' is already registered."
                )

        self._skills[name] = skill
        self._skill_specs[name] = skill_spec

        for tool, spec in zip(skill.get_tools(), pending_specs):
            self._tools[spec.qualified_name] = tool
            self._tool_specs[spec.qualified_name] = spec

            alias = spec.name
            if alias in self._ambiguous_aliases:
                continue
            if alias in self._aliases and self._aliases[alias] != spec.qualified_name:
                self._ambiguous_aliases.add(alias)
                self._aliases.pop(alias, None)
            else:
                self._aliases[alias] = spec.qualified_name

        return skill_spec

    def unregister_skill(self, skill_name: str) -> None:
        """Remove a skill and all of its tools."""
        skill = self._skills.pop(skill_name, None)
        if skill is None:
            raise SkillNotFoundError(f"Skill '{skill_name}' is not registered.")
        self._skill_specs.pop(skill_name, None)

        prefix = f"{skill_name}."
        removed_specs: List[ToolSpec] = []
        for qualified_name in list(self._tools.keys()):
            if qualified_name.startswith(prefix):
                self._tools.pop(qualified_name, None)
                spec = self._tool_specs.pop(qualified_name, None)
                if spec is not None:
                    removed_specs.append(spec)

        # Rebuild alias map to keep behavior deterministic.
        if removed_specs:
            self._rebuild_aliases()

    def _rebuild_aliases(self) -> None:
        self._aliases.clear()
        self._ambiguous_aliases.clear()
        for spec in self.list_tool_specs():
            alias = spec.name
            if alias in self._ambiguous_aliases:
                continue
            current = self._aliases.get(alias)
            if current and current != spec.qualified_name:
                self._ambiguous_aliases.add(alias)
                self._aliases.pop(alias, None)
            else:
                self._aliases[alias] = spec.qualified_name

    def list_skill_specs(self) -> List[SkillSpec]:
        return sorted(self._skill_specs.values(), key=lambda s: s.name)

    def list_tool_specs(self) -> List[ToolSpec]:
        return sorted(self._tool_specs.values(), key=lambda t: t.qualified_name)

    def get_skill(self, skill_name: str) -> BaseSkill:
        skill = self._skills.get(skill_name)
        if not skill:
            raise SkillNotFoundError(f"Skill '{skill_name}' is not registered.")
        return skill

    def resolve_tool(self, tool_name: str) -> ResolvedTool:
        """Resolve either a qualified name (skill.tool) or a unique alias (tool)."""
        if "." in tool_name:
            qualified_name = tool_name
        else:
            if tool_name in self._ambiguous_aliases:
                raise AmbiguousToolError(
                    f"Tool alias '{tool_name}' is ambiguous. Use a qualified name."
                )
            qualified_name = self._aliases.get(tool_name, "")

        tool = self._tools.get(qualified_name)
        spec = self._tool_specs.get(qualified_name)
        if tool is None or spec is None:
            raise ToolNotFoundError(f"Tool '{tool_name}' is not registered.")
        return ResolvedTool(qualified_name=qualified_name, tool=tool, spec=spec)

    def list_openai_tools(self, qualified_names: bool = True) -> List[Dict]:
        """Return registered tools formatted for OpenAI tool-calling APIs."""
        tools: List[Dict] = []
        for spec in self.list_tool_specs():
            entry = {
                "type": "function",
                "function": {
                    "name": spec.qualified_name if qualified_names else spec.name,
                    "description": spec.description,
                    "parameters": spec.input_schema
                    or {"type": "object", "properties": {}},
                },
            }
            tools.append(entry)
        return tools

    def list_mcp_tools(self, qualified_names: bool = True) -> List[Dict]:
        """Return registered tools in MCP-like shape (name/description/inputSchema)."""
        tools: List[Dict] = []
        for spec in self.list_tool_specs():
            tools.append(
                {
                    "name": spec.qualified_name if qualified_names else spec.name,
                    "description": spec.description,
                    "inputSchema": spec.input_schema
                    or {"type": "object", "properties": {}},
                }
            )
        return tools

    def snapshot(self) -> Dict[str, List[str]]:
        """Return a simple immutable-style view of registry names."""
        return {
            "skills": [s.name for s in self.list_skill_specs()],
            "tools": [t.qualified_name for t in self.list_tool_specs()],
        }

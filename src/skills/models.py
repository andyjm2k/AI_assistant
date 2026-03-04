"""Core data models for CATBot skills and tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ToolSpec:
    """Metadata for a registered tool."""

    skill_name: str
    name: str
    description: str = ""
    input_schema: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return f"{self.skill_name}.{self.name}"

    def to_openai_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.qualified_name,
                "description": self.description,
                "parameters": self.input_schema or {"type": "object", "properties": {}},
            },
        }


@dataclass(frozen=True)
class SkillSpec:
    """Metadata for a registered skill."""

    name: str
    description: str = ""
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    tool_names: List[str] = field(default_factory=list)


@dataclass
class SkillContext:
    """Execution context shared with tools."""

    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    scratch_dir: Optional[Path] = None
    services: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_service(self, name: str, default: Any = None) -> Any:
        return self.services.get(name, default)

    def set_service(self, name: str, service: Any) -> None:
        self.services[name] = service


@dataclass
class ToolExecutionResult:
    """Normalized result returned by skill tool execution."""

    success: bool
    message: str = ""
    data: Any = None
    error_code: Optional[str] = None
    tool_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "success": self.success,
            "message": self.message,
            "data": self.data,
        }
        if self.error_code:
            out["error_code"] = self.error_code
        if self.tool_name:
            out["tool_name"] = self.tool_name
        return out


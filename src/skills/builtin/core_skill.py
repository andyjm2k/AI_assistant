"""Built-in core utility skill."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Sequence

from src.skills.base import BaseSkill, BaseTool
from src.skills.models import SkillContext


class PingTool(BaseTool):
    name = "ping"
    description = "Health check tool that returns server time."
    input_schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        return {
            "pong": True,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo a text payload for testing tool loops."
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to echo."},
        },
        "required": ["text"],
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        return {"text": str(arguments.get("text", ""))}


class CoreSkill(BaseSkill):
    name = "core"
    description = "Core utility tools for diagnostics and tool-loop validation."
    version = "1.0.0"
    tags = ["core", "health"]

    def create_tools(self) -> Sequence[BaseTool]:
        return [PingTool(), EchoTool()]


def create_skill() -> BaseSkill:
    return CoreSkill()


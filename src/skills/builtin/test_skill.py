"""Comprehensive example skill used to validate framework behavior."""

from __future__ import annotations

from string import Template
from typing import Any, Dict, Sequence

from src.skills.base import BaseSkill, BaseTool
from src.skills.exceptions import SkillValidationError
from src.skills.models import SkillContext


class AnalyzeTextTool(BaseTool):
    name = "analyze_text"
    description = "Return basic text analytics for debugging tool-call flows."
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to analyze."},
        },
        "required": ["text"],
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        text = str(arguments.get("text", ""))
        words = [token for token in text.strip().split() if token]
        lines = text.splitlines() if text else []
        return {
            "characters": len(text),
            "words": len(words),
            "lines": len(lines),
            "preview": text[:120],
        }


class RenderTemplateTool(BaseTool):
    name = "render_template"
    description = "Render a string.Template payload with provided key/value variables."
    input_schema = {
        "type": "object",
        "properties": {
            "template": {
                "type": "string",
                "description": "Template string using $name placeholder format.",
            },
            "variables": {
                "type": "object",
                "description": "Template variable mapping.",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["template", "variables"],
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        template_text = str(arguments.get("template", ""))
        variables = arguments.get("variables", {})
        if not isinstance(variables, dict):
            raise SkillValidationError("'variables' must be an object.")

        casted = {str(k): str(v) for k, v in variables.items()}
        rendered = Template(template_text).safe_substitute(casted)
        return {
            "rendered": rendered,
            "variables_used": sorted(casted.keys()),
        }


class ContextSnapshotTool(BaseTool):
    name = "context_snapshot"
    description = "Return selected execution context details for diagnostics."
    input_schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        return {
            "conversation_id": context.conversation_id,
            "user_id": context.user_id,
            "scratch_dir": str(context.scratch_dir) if context.scratch_dir else None,
            "metadata_keys": sorted(context.metadata.keys()),
            "service_names": sorted(context.services.keys()),
        }


class TestSkill(BaseSkill):
    name = "testkit"
    description = "Reference skill demonstrating schemas, templating, and context access."
    version = "1.0.0"
    tags = ["example", "reference", "test"]

    def create_tools(self) -> Sequence[BaseTool]:
        return [AnalyzeTextTool(), RenderTemplateTool(), ContextSnapshotTool()]


def create_skill() -> BaseSkill:
    return TestSkill()

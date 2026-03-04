"""CATBot modular skills framework."""

from .base import BaseSkill, BaseTool
from .bootstrap import create_default_skill_manager
from .exceptions import (
    AmbiguousToolError,
    SkillFrameworkError,
    SkillNotFoundError,
    SkillPackageError,
    SkillRegistrationError,
    SkillValidationError,
    ToolExecutionError,
    ToolNotFoundError,
)
from .executor import SkillExecutor
from .loader import SkillManifest, SkillManifestLoader
from .manager import SkillManager
from .models import SkillContext, SkillSpec, ToolExecutionResult, ToolSpec
from .package import SkillPackageExportResult, SkillPackageImportResult, SkillPackageManager
from .registry import SkillRegistry

__all__ = [
    "BaseSkill",
    "BaseTool",
    "create_default_skill_manager",
    "SkillContext",
    "SkillExecutor",
    "SkillFrameworkError",
    "SkillManifest",
    "SkillManifestLoader",
    "SkillManager",
    "SkillNotFoundError",
    "SkillPackageError",
    "SkillPackageExportResult",
    "SkillPackageImportResult",
    "SkillPackageManager",
    "SkillRegistrationError",
    "SkillRegistry",
    "SkillSpec",
    "SkillValidationError",
    "ToolExecutionError",
    "ToolExecutionResult",
    "ToolNotFoundError",
    "ToolSpec",
    "AmbiguousToolError",
]

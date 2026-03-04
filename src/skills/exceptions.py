"""Exceptions used by the CATBot skill framework."""

from __future__ import annotations


class SkillFrameworkError(Exception):
    """Base exception for framework-level errors."""


class SkillValidationError(SkillFrameworkError):
    """Raised when a skill or tool definition is invalid."""


class SkillRegistrationError(SkillFrameworkError):
    """Raised when registration/unregistration fails."""


class SkillNotFoundError(SkillFrameworkError):
    """Raised when a skill is not found."""


class ToolNotFoundError(SkillFrameworkError):
    """Raised when a tool is not found."""


class AmbiguousToolError(SkillFrameworkError):
    """Raised when an unqualified tool name maps to multiple tools."""


class ToolExecutionError(SkillFrameworkError):
    """Raised when tool execution fails."""


class SkillPackageError(SkillFrameworkError):
    """Raised when exporting or importing .catbotskill packages fails."""

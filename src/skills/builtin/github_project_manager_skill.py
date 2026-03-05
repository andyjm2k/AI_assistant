"""Compatibility shim for the GitHub project manager skill."""

from src.skills.github.skill import (  # noqa: F401
    GitHubProjectManagerSkill,
    create_skill,
    _load_integration_service_class,
)

__all__ = [
    "GitHubProjectManagerSkill",
    "create_skill",
    "_load_integration_service_class",
]

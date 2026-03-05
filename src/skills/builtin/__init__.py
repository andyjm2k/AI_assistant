"""Built-in CATBot skills."""

from .core_skill import CoreSkill, create_skill as create_core_skill
from .filesystem_skill import FilesystemSkill, create_skill as create_filesystem_skill
from .github_project_manager_skill import (
    GitHubProjectManagerSkill,
    create_skill as create_github_project_manager_skill,
)
from .google_slides_skill import GoogleSlidesSkill, create_skill as create_google_slides_skill
from .image_generation_skill import ImageGenerationSkill, create_skill as create_image_generation_skill
from .test_skill import TestSkill, create_skill as create_test_skill

__all__ = [
    "CoreSkill",
    "FilesystemSkill",
    "GitHubProjectManagerSkill",
    "GoogleSlidesSkill",
    "ImageGenerationSkill",
    "TestSkill",
    "create_core_skill",
    "create_filesystem_skill",
    "create_github_project_manager_skill",
    "create_google_slides_skill",
    "create_image_generation_skill",
    "create_test_skill",
]

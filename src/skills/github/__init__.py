"""GitHub integration module for CATBot source control and version management."""

from .config import GitHubIntegrationConfig
from .github_api import GitHubApiClient
from .git_service import GitService
from .service import GitHubIntegrationService
from .skill import GitHubProjectManagerSkill, create_skill
from .version_manager import VersionManager

__all__ = [
    "GitHubIntegrationConfig",
    "GitHubApiClient",
    "GitService",
    "GitHubIntegrationService",
    "GitHubProjectManagerSkill",
    "VersionManager",
    "create_skill",
]

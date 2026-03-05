"""Configuration model for GitHub integration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitHubIntegrationConfig:
    """Runtime config loaded from environment variables."""

    workspace: Path
    github_token: str | None = None
    github_owner: str | None = None
    github_repo: str | None = None
    github_api_base: str = "https://api.github.com"
    default_branch: str = "main"
    git_author_name: str = "CATBot"
    git_author_email: str = "catbot@users.noreply.github.com"
    remote_name: str = "origin"
    version_file: str = "VERSION"

    @classmethod
    def from_env(cls, workspace: str | Path | None = None) -> "GitHubIntegrationConfig":
        resolved_workspace = Path(workspace or os.getenv("CATBOT_WORKSPACE", ".")).resolve()
        return cls(
            workspace=resolved_workspace,
            github_token=os.getenv("GITHUB_TOKEN"),
            github_owner=os.getenv("GITHUB_OWNER"),
            github_repo=os.getenv("GITHUB_REPO"),
            github_api_base=os.getenv("GITHUB_API_BASE", "https://api.github.com"),
            default_branch=os.getenv("GITHUB_DEFAULT_BRANCH", "main"),
            git_author_name=os.getenv("GIT_AUTHOR_NAME", "CATBot"),
            git_author_email=os.getenv("GIT_AUTHOR_EMAIL", "catbot@users.noreply.github.com"),
            remote_name=os.getenv("GIT_REMOTE_NAME", "origin"),
            version_file=os.getenv("VERSION_FILE", "VERSION"),
        )

    @property
    def has_github_credentials(self) -> bool:
        return bool(self.github_token and self.github_owner and self.github_repo)


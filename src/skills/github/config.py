"""Configuration model for GitHub integration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _normalize_repository_slug(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip().replace("\\", "/").strip("/")
    if not value:
        return None
    if value.count("/") != 1:
        return None
    owner, repo = value.split("/", 1)
    owner = owner.strip()
    repo = repo.strip()
    if not owner or not repo:
        return None
    return f"{owner}/{repo}"


def _parse_protected_branches(raw: str | None) -> tuple[str, ...]:
    value = (raw or "").strip()
    if not value:
        return ("main", "master")
    branches = tuple(
        branch.strip()
        for branch in value.split(",")
        if branch.strip()
    )
    return branches or ("main", "master")


def _parse_csv_patterns(raw: str | None, defaults: tuple[str, ...]) -> tuple[str, ...]:
    value = (raw or "").strip()
    if not value:
        return defaults
    patterns = tuple(item.strip() for item in value.split(",") if item.strip())
    return patterns or defaults


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
    enforce_branch_pr_flow: bool = True
    protected_branches: tuple[str, ...] = ("main", "master")
    required_repository: str | None = None
    enforce_sensitive_path_guard: bool = True
    blocked_path_patterns: tuple[str, ...] = (
        ".env",
        ".env.*",
        "*.pem",
        "*.key",
        "*.p12",
        "*.pfx",
        "*.jks",
        "*.pkcs12",
        "id_rsa",
        "id_rsa.*",
        "id_ed25519",
        "id_ed25519.*",
        "certs/*",
        "config/*.env",
        "config/*.env.*",
        "config/*.json",
        "config/**/*.json",
        "config/*secret*",
        "config/*credentials*",
        "config/*private*",
    )
    sensitive_path_allowlist_patterns: tuple[str, ...] = (
        "*.example",
        "*.sample",
        "*.template",
        "*.dist",
    )

    @classmethod
    def from_env(cls, workspace: str | Path | None = None) -> "GitHubIntegrationConfig":
        resolved_workspace = Path(workspace or os.getenv("CATBOT_WORKSPACE", ".")).resolve()
        owner = os.getenv("GITHUB_OWNER")
        repo = os.getenv("GITHUB_REPO")
        explicit_repo_slug = _normalize_repository_slug(os.getenv("GITHUB_REPOSITORY"))
        if explicit_repo_slug and (not owner or not repo):
            owner, repo = explicit_repo_slug.split("/", 1)
        required_repository = _normalize_repository_slug(
            os.getenv("GITHUB_TARGET_REPOSITORY")
            or explicit_repo_slug
            or (f"{owner}/{repo}" if owner and repo else None)
        )
        return cls(
            workspace=resolved_workspace,
            github_token=os.getenv("GITHUB_TOKEN"),
            github_owner=owner,
            github_repo=repo,
            github_api_base=os.getenv("GITHUB_API_BASE", "https://api.github.com"),
            default_branch=os.getenv("GITHUB_DEFAULT_BRANCH", "main"),
            git_author_name=os.getenv("GIT_AUTHOR_NAME", "CATBot"),
            git_author_email=os.getenv("GIT_AUTHOR_EMAIL", "catbot@users.noreply.github.com"),
            remote_name=os.getenv("GIT_REMOTE_NAME", "origin"),
            version_file=os.getenv("VERSION_FILE", "VERSION"),
            enforce_branch_pr_flow=_parse_bool_env("GITHUB_ENFORCE_BRANCH_PR_FLOW", True),
            protected_branches=_parse_protected_branches(os.getenv("GITHUB_PROTECTED_BRANCHES")),
            required_repository=required_repository,
            enforce_sensitive_path_guard=_parse_bool_env("GITHUB_ENFORCE_SENSITIVE_PATH_GUARD", True),
            blocked_path_patterns=_parse_csv_patterns(
                os.getenv("GITHUB_BLOCKED_PATH_PATTERNS"),
                cls.blocked_path_patterns,
            ),
            sensitive_path_allowlist_patterns=_parse_csv_patterns(
                os.getenv("GITHUB_SENSITIVE_PATH_ALLOWLIST"),
                cls.sensitive_path_allowlist_patterns,
            ),
        )

    @property
    def has_github_credentials(self) -> bool:
        return bool(self.github_token and self.github_owner and self.github_repo)

    @property
    def repository_slug(self) -> str | None:
        if self.github_owner and self.github_repo:
            return f"{self.github_owner}/{self.github_repo}"
        return None

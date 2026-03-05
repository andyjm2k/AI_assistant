"""High-level GitHub integration service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import GitHubIntegrationConfig
from .errors import GitCommandError, GitIntegrationError
from .github_api import GitHubApiClient
from .git_service import GitService
from .models import BumpLevel, VersionedCommit
from .version_manager import VersionManager


class GitHubIntegrationService:
    """Coordinates git operations, semantic versioning, and GitHub API calls."""

    def __init__(
        self,
        config: GitHubIntegrationConfig,
        *,
        git_service: GitService | None = None,
        version_manager: VersionManager | None = None,
        github_client: GitHubApiClient | None = None,
    ) -> None:
        self.config = config
        self.git = git_service or GitService(config.workspace)
        self.versions = version_manager or VersionManager(config.workspace, config.version_file)
        if github_client is not None:
            self.github = github_client
        elif config.has_github_credentials:
            self.github = GitHubApiClient(
                token=str(config.github_token),
                owner=str(config.github_owner),
                repo=str(config.github_repo),
                api_base=config.github_api_base,
            )
        else:
            self.github = None

    @classmethod
    def from_env(cls, workspace: str | Path | None = None) -> "GitHubIntegrationService":
        return cls(GitHubIntegrationConfig.from_env(workspace))

    def _resolve_remote(self, remote_name: str | None) -> str:
        value = (remote_name or self.config.remote_name).strip()
        if not value:
            raise GitIntegrationError("Remote name cannot be empty.")
        return value

    def _resolved_branch(self, branch: str | None) -> str:
        return (branch or self.git.current_branch()).strip()

    def initialize_repository(self, remote_url: str | None = None) -> dict[str, Any]:
        if not self.git.is_repository():
            self.git.init(default_branch=self.config.default_branch)
        self.git.set_identity(self.config.git_author_name, self.config.git_author_email)
        current = self.git.current_branch()
        if current != self.config.default_branch:
            try:
                self.git.checkout(self.config.default_branch, create=False)
            except GitCommandError:
                self.git.checkout(self.config.default_branch, create=True)
        version = self.versions.ensure_exists()
        if remote_url:
            self.git.remote_add_or_set(self.config.remote_name, remote_url)
        return {
            "workspace": str(self.config.workspace),
            "branch": self.git.current_branch(),
            "version": version,
            "remote_name": self.config.remote_name if remote_url else None,
        }

    def status(self) -> dict[str, Any]:
        version = self.versions.ensure_exists()
        git_status = self.git.status()
        return {
            "version": version,
            "branch": git_status.branch,
            "ahead_by": git_status.ahead_by,
            "behind_by": git_status.behind_by,
            "staged": git_status.staged,
            "changed": git_status.changed,
            "untracked": git_status.untracked,
        }

    def fetch(self, remote_name: str | None = None) -> dict[str, Any]:
        remote = self._resolve_remote(remote_name)
        self.git.fetch(remote)
        status = self.git.status()
        return {
            "remote": remote,
            "branch": status.branch,
            "ahead_by": status.ahead_by,
            "behind_by": status.behind_by,
        }

    def pull(
        self,
        *,
        remote_name: str | None = None,
        branch: str | None = None,
        rebase: bool = False,
    ) -> dict[str, Any]:
        remote = self._resolve_remote(remote_name)
        target_branch = branch or None
        self.git.pull(remote, target_branch, rebase=rebase)
        status = self.git.status()
        return {
            "remote": remote,
            "branch": status.branch,
            "ahead_by": status.ahead_by,
            "behind_by": status.behind_by,
            "rebase": bool(rebase),
        }

    def push(
        self,
        *,
        remote_name: str | None = None,
        branch: str | None = None,
        set_upstream: bool = False,
        tags: bool = False,
    ) -> dict[str, Any]:
        remote = self._resolve_remote(remote_name)
        target_branch = self._resolved_branch(branch)
        self.git.push(remote, target_branch, set_upstream=set_upstream, tags=tags)
        return {
            "remote": remote,
            "branch": target_branch,
            "set_upstream": bool(set_upstream),
            "tags": bool(tags),
        }

    def sync(
        self,
        *,
        remote_name: str | None = None,
        branch: str | None = None,
        rebase: bool = False,
        set_upstream: bool = False,
        tags: bool = False,
    ) -> dict[str, Any]:
        pull_result = self.pull(remote_name=remote_name, branch=branch, rebase=rebase)
        push_result = self.push(
            remote_name=remote_name,
            branch=branch or pull_result.get("branch"),
            set_upstream=set_upstream,
            tags=tags,
        )
        return {"pull": pull_result, "push": push_result}

    def create_branch(
        self,
        branch: str,
        *,
        from_ref: str | None = None,
        push: bool = False,
        set_upstream: bool = True,
        remote_name: str | None = None,
    ) -> dict[str, Any]:
        target_branch = branch.strip()
        if not target_branch:
            raise GitIntegrationError("Branch name cannot be empty.")
        self.git.checkout(target_branch, create=True, from_ref=from_ref)
        result: dict[str, Any] = {
            "branch": self.git.current_branch(),
            "created_from": from_ref,
        }
        if push:
            remote = self._resolve_remote(remote_name)
            self.git.push(remote, target_branch, set_upstream=set_upstream)
            result["push"] = {
                "remote": remote,
                "set_upstream": bool(set_upstream),
            }
        return result

    def checkout_branch(self, branch: str) -> dict[str, Any]:
        target_branch = branch.strip()
        if not target_branch:
            raise GitIntegrationError("Branch name cannot be empty.")
        self.git.checkout(target_branch, create=False)
        status = self.git.status()
        return {
            "branch": status.branch,
            "ahead_by": status.ahead_by,
            "behind_by": status.behind_by,
        }

    def bump_version(self, bump: BumpLevel) -> dict[str, Any]:
        version_change = self.versions.bump(bump)
        return {
            "previous": version_change.previous,
            "current": version_change.current,
            "bump": version_change.bump,
            "version_file": str(self.versions.version_path),
        }

    def commit_versioned_change(
        self,
        message: str,
        *,
        bump: BumpLevel = "patch",
        tag_prefix: str = "v",
        push: bool = False,
    ) -> VersionedCommit:
        version_change = self.versions.bump(bump)
        self.git.add()
        final_message = f"{message} ({tag_prefix}{version_change.current})"
        commit = self.git.commit(final_message)
        tag_name = f"{tag_prefix}{version_change.current}"
        self.git.tag(tag_name, message=f"Release {tag_name}")
        if push:
            self.git.push(self.config.remote_name, commit.branch, set_upstream=True)
            self.git.push(self.config.remote_name, tags=True)
        return VersionedCommit(commit=commit, tag=tag_name, version=version_change)

    def create_pull_request(self, title: str, head: str, body: str = "", base: str | None = None) -> dict[str, Any]:
        if not self.github:
            raise GitIntegrationError("GitHub API client not configured. Set GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO.")
        return self.github.create_pull_request(
            title=title,
            head=head,
            base=base or self.config.default_branch,
            body=body,
        )

    def list_pull_requests(
        self,
        *,
        state: str = "open",
        sort: str = "created",
        direction: str = "desc",
        per_page: int = 30,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        if not self.github:
            raise GitIntegrationError("GitHub API client not configured. Set GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO.")
        normalized_state = state.strip().lower() or "open"
        if normalized_state not in {"open", "closed", "all"}:
            raise GitIntegrationError("Pull request state must be one of: open, closed, all.")
        return self.github.list_pull_requests(
            state=normalized_state,
            sort=sort,
            direction=direction,
            per_page=per_page,
            page=page,
        )

    def repository_info(self, *, include_rate_limit: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "workspace": str(self.config.workspace),
            "default_branch": self.config.default_branch,
            "remote_name": self.config.remote_name,
            "has_github_client": self.github is not None,
        }
        if not self.github:
            return payload
        repository = self.github.get_repository()
        payload["repository"] = {
            "id": repository.get("id"),
            "name": repository.get("name"),
            "full_name": repository.get("full_name"),
            "private": repository.get("private"),
            "default_branch": repository.get("default_branch"),
            "html_url": repository.get("html_url"),
            "clone_url": repository.get("clone_url"),
        }
        if include_rate_limit:
            rate_limit = self.github.get_rate_limit()
            core = rate_limit.get("resources", {}).get("core", {})
            payload["rate_limit"] = {
                "limit": core.get("limit"),
                "remaining": core.get("remaining"),
                "reset": core.get("reset"),
            }
        return payload

    def publish_release(
        self,
        title: str | None = None,
        notes: str = "",
        *,
        bump: BumpLevel = "patch",
        prerelease: bool = False,
        push: bool = True,
    ) -> dict[str, Any]:
        if not self.github:
            raise GitIntegrationError("GitHub API client not configured. Set GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO.")
        versioned_commit = self.commit_versioned_change(
            message=title or "Automated release",
            bump=bump,
            tag_prefix="v",
            push=push,
        )
        release = self.github.create_release(
            tag_name=versioned_commit.tag,
            name=title or versioned_commit.tag,
            body=notes,
            prerelease=prerelease,
            draft=False,
            target_commitish=versioned_commit.commit.branch,
        )
        return {
            "release_id": release.get("id"),
            "html_url": release.get("html_url"),
            "tag": versioned_commit.tag,
            "version": versioned_commit.version.current,
            "commit": versioned_commit.commit.commit_hash,
        }

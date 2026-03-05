from __future__ import annotations

from pathlib import Path

import pytest

from src.skills.github.config import GitHubIntegrationConfig
from src.skills.github.errors import GitIntegrationError
from src.skills.github.models import CommitResult, GitStatus, VersionChange
from src.skills.github.service import GitHubIntegrationService


class FakeGitService:
    def __init__(self) -> None:
        self.add_called = False
        self.commit_messages: list[str] = []
        self.tags: list[str] = []
        self.push_calls: list[tuple[str, str | None, bool, bool]] = []
        self.pull_calls: list[tuple[str, str | None, bool]] = []
        self.fetch_calls: list[str] = []
        self.checkout_calls: list[tuple[str, bool, str | None]] = []

    def add(self) -> None:
        self.add_called = True

    def commit(self, message: str) -> CommitResult:
        self.commit_messages.append(message)
        return CommitResult(commit_hash="abc123", branch="main", message=message)

    def tag(self, tag_name: str, message: str | None = None, annotated: bool = True, force: bool = False) -> None:
        self.tags.append(tag_name)

    def push(self, remote_name: str, branch: str | None = None, set_upstream: bool = False, tags: bool = False) -> None:
        self.push_calls.append((remote_name, branch, set_upstream, tags))

    def status(self) -> GitStatus:
        return GitStatus(branch="main", ahead_by=0, behind_by=0, staged=[], changed=[], untracked=[])

    def is_repository(self) -> bool:
        return True

    def fetch(self, remote_name: str = "origin") -> None:
        self.fetch_calls.append(remote_name)

    def pull(self, remote_name: str = "origin", branch: str | None = None, rebase: bool = False) -> None:
        self.pull_calls.append((remote_name, branch, rebase))

    def set_identity(self, name: str, email: str) -> None:
        return None

    def current_branch(self) -> str:
        return "main"

    def checkout(self, branch: str, create: bool = False, from_ref: str | None = None) -> None:
        self.checkout_calls.append((branch, create, from_ref))


class FakeGitHubClient:
    def get_repository(self) -> dict[str, object]:
        return {
            "id": 99,
            "name": "CATBot",
            "full_name": "owner/CATBot",
            "private": False,
            "default_branch": "main",
            "html_url": "https://github.com/owner/CATBot",
            "clone_url": "https://github.com/owner/CATBot.git",
        }

    def get_rate_limit(self) -> dict[str, object]:
        return {"resources": {"core": {"limit": 5000, "remaining": 4999, "reset": 1700000000}}}

    def list_pull_requests(self, **kwargs: object) -> list[dict[str, object]]:
        return [{"number": 1, "title": "Test PR", "kwargs": kwargs}]


class FakeVersionManager:
    version_path = Path("VERSION")

    def ensure_exists(self) -> str:
        return "1.0.0"

    def bump(self, bump: str) -> VersionChange:
        return VersionChange(previous="1.0.0", current="1.0.1", bump="patch")


def test_commit_versioned_change_flow() -> None:
    config = GitHubIntegrationConfig(workspace=Path("."), default_branch="main", remote_name="origin")
    fake_git = FakeGitService()
    fake_versions = FakeVersionManager()
    service = GitHubIntegrationService(config, git_service=fake_git, version_manager=fake_versions, github_client=None)

    result = service.commit_versioned_change("chore: sync", bump="patch", push=True)

    assert fake_git.add_called
    assert fake_git.commit_messages == ["chore: sync (v1.0.1)"]
    assert fake_git.tags == ["v1.0.1"]
    assert len(fake_git.push_calls) == 2
    assert result.tag == "v1.0.1"
    assert result.version.current == "1.0.1"


def test_status_reports_version_and_git_state() -> None:
    config = GitHubIntegrationConfig(workspace=Path("."))
    fake_git = FakeGitService()
    fake_versions = FakeVersionManager()
    service = GitHubIntegrationService(config, git_service=fake_git, version_manager=fake_versions, github_client=None)

    status = service.status()

    assert status["version"] == "1.0.0"
    assert status["branch"] == "main"
    assert status["untracked"] == []


def test_fetch_pull_push_sync_and_branch_helpers() -> None:
    config = GitHubIntegrationConfig(workspace=Path("."), remote_name="origin")
    fake_git = FakeGitService()
    fake_versions = FakeVersionManager()
    service = GitHubIntegrationService(config, git_service=fake_git, version_manager=fake_versions, github_client=None)

    fetch_result = service.fetch()
    pull_result = service.pull(branch="main", rebase=True)
    push_result = service.push(branch="main", set_upstream=True, tags=True)
    sync_result = service.sync(branch="main", set_upstream=True)
    branch_result = service.create_branch("feature/test", from_ref="main", push=True, set_upstream=True)
    checkout_result = service.checkout_branch("main")

    assert fetch_result["remote"] == "origin"
    assert pull_result["rebase"] is True
    assert push_result["tags"] is True
    assert sync_result["pull"]["remote"] == "origin"
    assert sync_result["push"]["branch"] == "main"
    assert branch_result["branch"] == "main"
    assert checkout_result["branch"] == "main"
    assert ("origin", "main", True, False) in fake_git.push_calls
    assert ("feature/test", True, "main") in fake_git.checkout_calls


def test_repository_info_and_pull_request_listing() -> None:
    config = GitHubIntegrationConfig(workspace=Path("."), remote_name="origin", github_owner="owner", github_repo="CATBot")
    fake_git = FakeGitService()
    fake_versions = FakeVersionManager()
    fake_github = FakeGitHubClient()
    service = GitHubIntegrationService(
        config,
        git_service=fake_git,
        version_manager=fake_versions,
        github_client=fake_github,
    )

    repo = service.repository_info(include_rate_limit=True)
    pulls = service.list_pull_requests(state="open", per_page=10, page=2)

    assert repo["repository"]["full_name"] == "owner/CATBot"
    assert repo["rate_limit"]["remaining"] == 4999
    assert pulls and pulls[0]["number"] == 1


def test_list_pull_requests_rejects_invalid_state() -> None:
    config = GitHubIntegrationConfig(workspace=Path("."), github_owner="owner", github_repo="CATBot")
    service = GitHubIntegrationService(
        config,
        git_service=FakeGitService(),
        version_manager=FakeVersionManager(),
        github_client=FakeGitHubClient(),
    )

    with pytest.raises(GitIntegrationError):
        service.list_pull_requests(state="invalid")

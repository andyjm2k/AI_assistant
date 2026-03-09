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
        self.branch = "main"
        self.staged: list[str] = []
        self.changed: list[str] = []
        self.untracked: list[str] = []
        self.pr_diff_files: list[str] = []

    def add(self) -> None:
        self.add_called = True

    def commit(self, message: str) -> CommitResult:
        self.commit_messages.append(message)
        return CommitResult(commit_hash="abc123", branch=self.branch, message=message)

    def tag(self, tag_name: str, message: str | None = None, annotated: bool = True, force: bool = False) -> None:
        self.tags.append(tag_name)

    def push(self, remote_name: str, branch: str | None = None, set_upstream: bool = False, tags: bool = False) -> None:
        self.push_calls.append((remote_name, branch, set_upstream, tags))

    def status(self) -> GitStatus:
        return GitStatus(
            branch=self.branch,
            ahead_by=0,
            behind_by=0,
            staged=list(self.staged),
            changed=list(self.changed),
            untracked=list(self.untracked),
        )

    def is_repository(self) -> bool:
        return True

    def fetch(self, remote_name: str = "origin") -> None:
        self.fetch_calls.append(remote_name)

    def pull(self, remote_name: str = "origin", branch: str | None = None, rebase: bool = False) -> None:
        self.pull_calls.append((remote_name, branch, rebase))

    def set_identity(self, name: str, email: str) -> None:
        return None

    def current_branch(self) -> str:
        return self.branch

    def checkout(self, branch: str, create: bool = False, from_ref: str | None = None) -> None:
        self.checkout_calls.append((branch, create, from_ref))
        self.branch = branch

    def diff_name_only(self, base_ref: str, head_ref: str) -> list[str]:
        return list(self.pr_diff_files)


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

    def create_pull_request(self, **kwargs: object) -> dict[str, object]:
        return {"number": 123, "title": kwargs.get("title"), "head": kwargs.get("head"), "base": kwargs.get("base")}


class FakeVersionManager:
    version_path = Path("VERSION")

    def ensure_exists(self) -> str:
        return "1.0.0"

    def bump(self, bump: str) -> VersionChange:
        return VersionChange(previous="1.0.0", current="1.0.1", bump="patch")


def test_commit_versioned_change_flow() -> None:
    config = GitHubIntegrationConfig(
        workspace=Path("."),
        default_branch="main",
        remote_name="origin",
        github_owner="owner",
        github_repo="CATBot",
        required_repository="owner/CATBot",
    )
    fake_git = FakeGitService()
    fake_git.branch = "feature/release-prep"
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
    config = GitHubIntegrationConfig(
        workspace=Path("."),
        remote_name="origin",
        github_owner="owner",
        github_repo="CATBot",
        required_repository="owner/CATBot",
    )
    fake_git = FakeGitService()
    fake_git.branch = "feature/current"
    fake_versions = FakeVersionManager()
    service = GitHubIntegrationService(config, git_service=fake_git, version_manager=fake_versions, github_client=None)

    fetch_result = service.fetch()
    pull_result = service.pull(branch="feature/current", rebase=True)
    push_result = service.push(branch="feature/current", set_upstream=True, tags=True)
    sync_result = service.sync(branch="feature/current", set_upstream=True)
    branch_result = service.create_branch("feature/test", from_ref="main", push=True, set_upstream=True)
    checkout_result = service.checkout_branch("main")

    assert fetch_result["remote"] == "origin"
    assert pull_result["rebase"] is True
    assert push_result["tags"] is True
    assert sync_result["pull"]["remote"] == "origin"
    assert sync_result["push"]["branch"] == "feature/current"
    assert branch_result["branch"] == "feature/test"
    assert checkout_result["branch"] == "main"
    assert ("origin", "feature/current", True, False) in fake_git.push_calls
    assert ("feature/test", True, "main") in fake_git.checkout_calls


def test_push_rejects_protected_branch() -> None:
    config = GitHubIntegrationConfig(
        workspace=Path("."),
        github_owner="owner",
        github_repo="CATBot",
        required_repository="owner/CATBot",
        default_branch="main",
    )
    service = GitHubIntegrationService(
        config,
        git_service=FakeGitService(),
        version_manager=FakeVersionManager(),
        github_client=None,
    )

    with pytest.raises(GitIntegrationError):
        service.push(branch="main")


def test_commit_versioned_change_rejects_protected_branch() -> None:
    config = GitHubIntegrationConfig(
        workspace=Path("."),
        github_owner="owner",
        github_repo="CATBot",
        required_repository="owner/CATBot",
        default_branch="main",
    )
    service = GitHubIntegrationService(
        config,
        git_service=FakeGitService(),
        version_manager=FakeVersionManager(),
        github_client=None,
    )

    with pytest.raises(GitIntegrationError):
        service.commit_versioned_change("chore: direct-main-change", bump="patch", push=False)


def test_push_rejects_sensitive_paths_pending() -> None:
    config = GitHubIntegrationConfig(
        workspace=Path("."),
        github_owner="owner",
        github_repo="CATBot",
        required_repository="owner/CATBot",
    )
    fake_git = FakeGitService()
    fake_git.branch = "feature/safe"
    fake_git.changed = ["config/prod.env"]
    service = GitHubIntegrationService(
        config,
        git_service=fake_git,
        version_manager=FakeVersionManager(),
        github_client=None,
    )

    with pytest.raises(GitIntegrationError):
        service.push(branch="feature/safe")


def test_create_pull_request_rejects_sensitive_paths_in_pr_diff() -> None:
    config = GitHubIntegrationConfig(
        workspace=Path("."),
        github_owner="owner",
        github_repo="CATBot",
        required_repository="owner/CATBot",
    )
    fake_git = FakeGitService()
    fake_git.pr_diff_files = ["config/prod.env"]
    service = GitHubIntegrationService(
        config,
        git_service=fake_git,
        version_manager=FakeVersionManager(),
        github_client=FakeGitHubClient(),
    )

    with pytest.raises(GitIntegrationError):
        service.create_pull_request("Test PR", head="feature/new", base="main", body="")


def test_push_rejects_sensitive_config_json_pending() -> None:
    config = GitHubIntegrationConfig(
        workspace=Path("."),
        github_owner="owner",
        github_repo="CATBot",
        required_repository="owner/CATBot",
    )
    fake_git = FakeGitService()
    fake_git.branch = "feature/safe"
    fake_git.changed = ["config/team-config.json"]
    service = GitHubIntegrationService(
        config,
        git_service=fake_git,
        version_manager=FakeVersionManager(),
        github_client=None,
    )

    with pytest.raises(GitIntegrationError):
        service.push(branch="feature/safe")


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

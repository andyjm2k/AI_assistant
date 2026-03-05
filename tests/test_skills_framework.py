"""Tests for CATBot modular skills framework."""

from __future__ import annotations

import base64
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.skills import BaseSkill, BaseTool, SkillContext, SkillManager


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo test tool."
    input_schema = {"type": "object", "properties": {"text": {"type": "string"}}}

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        return {"text": str(arguments.get("text", ""))}


class AnotherEchoTool(BaseTool):
    name = "echo"
    description = "Second echo tool to force alias ambiguity."
    input_schema = {"type": "object", "properties": {"text": {"type": "string"}}}

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        return {"text": f"secondary:{arguments.get('text', '')}"}


class AlphaSkill(BaseSkill):
    name = "alpha"
    description = "alpha"

    def create_tools(self) -> Sequence[BaseTool]:
        return [EchoTool()]


class BetaSkill(BaseSkill):
    name = "beta"
    description = "beta"

    def create_tools(self) -> Sequence[BaseTool]:
        return [AnotherEchoTool()]


def test_manifest_loading_discovers_builtin_skills() -> None:
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    names = [spec.name for spec in manager.list_skills()]
    assert "core" in names
    assert "filesystem" in names
    assert "GitHubProjectManager" in names
    assert "google_slides" in names
    assert "image_generation" in names
    assert "testkit" in names

    tool_names = [spec.qualified_name for spec in manager.list_tools()]
    assert "core.ping" in tool_names
    assert "core.echo" in tool_names
    assert "filesystem.list_files" in tool_names
    assert "GitHubProjectManager.status" in tool_names
    assert "GitHubProjectManager.fetch" in tool_names
    assert "GitHubProjectManager.sync" in tool_names
    assert "GitHubProjectManager.list_pull_requests" in tool_names
    assert "google_slides.create_outline" in tool_names
    assert "google_slides.create_outline_from_markdown" in tool_names
    assert "google_slides.build_batch_update_requests" in tool_names
    assert "image_generation.generate_image" in tool_names
    assert "testkit.context_snapshot" in tool_names

    mcp_tools = manager.mcp_tools()
    assert any(t.get("name") == "core.ping" for t in mcp_tools)


@pytest.mark.asyncio
async def test_execute_core_ping_tool() -> None:
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    result = await manager.execute_tool("core.ping", {})
    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data.get("pong") is True


@pytest.mark.asyncio
async def test_filesystem_write_and_read_roundtrip() -> None:
    temp_base = _create_workspace_temp_dir()
    try:
        manager = SkillManager()
        manager.load_manifests("src/skills/manifests")
        manager.load_manifests(
            _create_temp_filesystem_manifest_dir(temp_base, root=temp_base / "root"),
            replace=True,
        )

        write_result = await manager.execute_tool(
            "filesystem.write_text",
            {"path": "notes/test.txt", "content": "hello"},
        )
        assert write_result.success is True

        read_result = await manager.execute_tool("filesystem.read_text", {"path": "notes/test.txt"})
        assert read_result.success is True
        assert read_result.data["content"] == "hello"
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


@pytest.mark.asyncio
async def test_filesystem_list_files_supports_recursive_subdirectories() -> None:
    temp_base = _create_workspace_temp_dir()
    try:
        root = temp_base / "root"
        (root / "nested" / "deeper").mkdir(parents=True, exist_ok=True)
        (root / "top.txt").write_text("top", encoding="utf-8")
        (root / "nested" / "child.txt").write_text("child", encoding="utf-8")
        (root / "nested" / "deeper" / "leaf.txt").write_text("leaf", encoding="utf-8")

        manager = SkillManager()
        manager.load_manifests(
            _create_temp_filesystem_manifest_dir(temp_base, root=root),
            replace=True,
        )

        non_recursive = await manager.execute_tool("filesystem.list_files", {})
        assert non_recursive.success is True
        non_recursive_paths = {
            str(item.get("relative_path"))
            for item in (non_recursive.data or {}).get("items", [])
            if isinstance(item, dict)
        }
        assert "top.txt" in non_recursive_paths
        assert "nested/child.txt" not in non_recursive_paths

        recursive = await manager.execute_tool("filesystem.list_files", {"recursive": True})
        assert recursive.success is True
        recursive_paths = {
            str(item.get("relative_path"))
            for item in (recursive.data or {}).get("items", [])
            if isinstance(item, dict)
        }
        assert "top.txt" in recursive_paths
        assert "nested/child.txt" in recursive_paths
        assert "nested/deeper/leaf.txt" in recursive_paths
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


@pytest.mark.asyncio
async def test_filesystem_list_files_accepts_scratch_prefixed_path() -> None:
    temp_base = _create_workspace_temp_dir()
    try:
        root = temp_base / "scratch"
        (root / "images").mkdir(parents=True, exist_ok=True)
        (root / "images" / "one.png").write_text("png", encoding="utf-8")

        manager = SkillManager()
        manager.load_manifests(
            _create_temp_filesystem_manifest_dir(temp_base, root=root),
            replace=True,
        )

        unix_style = await manager.execute_tool("filesystem.list_files", {"path": "scratch/images"})
        windows_style = await manager.execute_tool("filesystem.list_files", {"path": r"scratch\images"})

        assert unix_style.success is True
        assert windows_style.success is True

        unix_paths = {
            str(item.get("relative_path"))
            for item in (unix_style.data or {}).get("items", [])
            if isinstance(item, dict)
        }
        windows_paths = {
            str(item.get("relative_path"))
            for item in (windows_style.data or {}).get("items", [])
            if isinstance(item, dict)
        }
        assert "images/one.png" in unix_paths
        assert "images/one.png" in windows_paths
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


@pytest.mark.asyncio
async def test_filesystem_blocks_path_traversal() -> None:
    temp_base = _create_workspace_temp_dir()
    try:
        manager = SkillManager()
        manager.load_manifests(
            _create_temp_filesystem_manifest_dir(temp_base, root=temp_base / "root"),
            replace=True,
        )
        result = await manager.execute_tool(
            "filesystem.read_text",
            {"path": "../outside.txt"},
        )
        assert result.success is False
        assert result.error_code == "framework_error"
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


@pytest.mark.asyncio
async def test_ambiguous_unqualified_tool_name_returns_framework_error() -> None:
    manager = SkillManager()
    manager.register_skill(AlphaSkill())
    manager.register_skill(BetaSkill())
    result = await manager.execute_tool("echo", {"text": "hello"})
    assert result.success is False
    assert result.error_code == "framework_error"


@pytest.mark.asyncio
async def test_image_generation_writes_output_file(monkeypatch: pytest.MonkeyPatch) -> None:
    temp_base = _create_workspace_temp_dir()
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    image_bytes = b"fake-png-bytes"
    image_data_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("utf-8")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "img-test-id",
        "provider": "openrouter",
        "choices": [
            {
                "message": {
                    "content": "Generated image",
                    "images": [{"image_url": {"url": image_data_url}}],
                }
            }
        ],
        "usage": {"total_tokens": 5},
    }

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    try:
        with patch("src.skills.builtin.image_generation_skill.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await manager.execute_tool(
                "image_generation.generate_image",
                {"prompt": "A cat astronaut in watercolor", "output_dir": "generated"},
                context=SkillContext(scratch_dir=temp_base),
            )
            post_call = mock_client.post.call_args
            assert post_call is not None
            called_url = post_call.args[0]
            payload = post_call.kwargs["json"]
            assert called_url.endswith("/chat/completions")
            assert payload["model"] == "bytedance-seed/seedream-4.5"
            assert payload["modalities"] == ["image"]
            assert payload["messages"][0]["content"] == "A cat astronaut in watercolor"

        assert result.success is True
        assert result.data["model"] == "bytedance-seed/seedream-4.5"
        assert result.data["image_count"] == 1
        image_item = result.data["images"][0]
        assert image_item["mime_type"] == "image/png"
        assert image_item["relative_path"].startswith("generated/")
        assert Path(image_item["path"]).exists()
        assert Path(image_item["path"]).read_bytes() == image_bytes
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


@pytest.mark.asyncio
async def test_image_generation_requires_openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("openai_api_key", raising=False)
    monkeypatch.delenv("MCP_LLM_OPENAI_API_KEY", raising=False)

    result = await manager.execute_tool(
        "image_generation.generate_image",
        {"prompt": "test prompt"},
    )

    assert result.success is False
    assert result.error_code == "framework_error"


@pytest.mark.asyncio
async def test_google_slides_create_outline_returns_requested_slide_count() -> None:
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool(
        "google_slides.create_outline",
        {
            "topic": "Q3 Product Roadmap",
            "audience": "Executive team",
            "slide_count": 8,
            "objective": "Approve milestone and staffing plan",
        },
    )

    assert result.success is True
    assert result.data["slide_count"] == 8
    assert len(result.data["slides"]) == 8
    assert result.data["slides"][0]["title"] == "Q3 Product Roadmap"


@pytest.mark.asyncio
async def test_google_slides_build_batch_update_requests_generates_payload() -> None:
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool(
        "google_slides.build_batch_update_requests",
        {
            "presentation_id": "test-presentation-id",
            "slides": [
                {"title": "Overview", "bullets": ["Goal", "Scope"]},
                {"title": "Plan", "bullets": ["Milestone 1", "Milestone 2"]},
            ],
        },
    )

    assert result.success is True
    assert result.data["presentation_id"] == "test-presentation-id"
    assert result.data["slide_count"] == 2
    assert result.data["request_count"] == 6
    assert result.data["requests"][0]["createSlide"]["objectId"] == "slide_1"
    assert result.data["requests"][1]["insertText"]["objectId"] == "title_1"


@pytest.mark.asyncio
async def test_google_slides_create_outline_from_markdown_attaches_matching_scratch_images() -> None:
    temp_base = _create_workspace_temp_dir()
    try:
        images_dir = temp_base / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "overview-metrics.png").write_bytes(b"overview")
        (images_dir / "execution-timeline.png").write_bytes(b"timeline")

        manager = SkillManager.from_manifest_directory("src/skills/manifests")
        markdown = (
            "# Q3 Product Roadmap\n\n"
            "## Overview Metrics\n"
            "- Revenue trend\n\n"
            "## Execution Timeline\n"
            "- Key milestones\n"
        )
        result = await manager.execute_tool(
            "google_slides.create_outline_from_markdown",
            {
                "markdown": markdown,
                "attach_scratch_images": True,
                "image_dir": "images",
                "image_match_mode": "title",
            },
            context=SkillContext(scratch_dir=temp_base),
        )

        assert result.success is True
        assert result.data["slide_count"] == 3
        slides = result.data["slides"]
        overview = next(item for item in slides if item["title"] == "Overview Metrics")
        timeline = next(item for item in slides if item["title"] == "Execution Timeline")
        assert overview["images"][0]["path"] == "images/overview-metrics.png"
        assert timeline["images"][0]["path"] == "images/execution-timeline.png"
        assert result.data["auto_attached_images"] == 2
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


@pytest.mark.asyncio
async def test_google_slides_build_batch_update_requests_includes_image_requests_from_scratch_paths() -> None:
    temp_base = _create_workspace_temp_dir()
    try:
        images_dir = temp_base / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / "overview.png").write_bytes(b"overview")

        manager = SkillManager.from_manifest_directory("src/skills/manifests")
        result = await manager.execute_tool(
            "google_slides.build_batch_update_requests",
            {
                "presentation_id": "test-presentation-id",
                "image_url_prefix": "https://cdn.example.com/decks",
                "slides": [
                    {
                        "title": "Overview",
                        "bullets": ["Goal"],
                        "images": [{"path": "images/overview.png", "alt": "Overview chart"}],
                    }
                ],
            },
            context=SkillContext(scratch_dir=temp_base),
        )

        assert result.success is True
        assert result.data["slide_count"] == 1
        assert result.data["image_request_count"] == 1
        assert result.data["request_count"] == 4
        image_request = next(
            req["createImage"] for req in result.data["requests"] if "createImage" in req
        )
        assert image_request["objectId"] == "image_1_1"
        assert image_request["url"] == "https://cdn.example.com/decks/images/overview.png"
        assert result.data["skipped_images"] == []
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


@pytest.mark.asyncio
async def test_github_project_manager_status_and_bump_with_mock_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.github import skill as gpm_skill

    class FakeGitHubIntegrationService:
        def __init__(self, workspace: Path) -> None:
            self.workspace = Path(workspace).resolve()

        @classmethod
        def from_env(
            cls, workspace: str | Path | None = None
        ) -> "FakeGitHubIntegrationService":
            return cls(Path(workspace or "."))

        def status(self) -> dict[str, Any]:
            return {
                "version": "1.2.3",
                "branch": "main",
                "ahead_by": 0,
                "behind_by": 0,
                "staged": [],
                "changed": [],
                "untracked": [],
            }

        def bump_version(self, bump: str) -> dict[str, Any]:
            return {
                "previous": "1.2.3",
                "current": "1.2.4" if bump == "patch" else "1.3.0",
                "bump": bump,
                "workspace": str(self.workspace),
            }

    monkeypatch.setattr(
        gpm_skill,
        "_load_integration_service_class",
        lambda: FakeGitHubIntegrationService,
    )
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    status_result = await manager.execute_tool("GitHubProjectManager.status", {"workspace": "."})
    assert status_result.success is True
    assert status_result.data["status"]["branch"] == "main"
    assert status_result.data["status"]["version"] == "1.2.3"

    bump_result = await manager.execute_tool(
        "GitHubProjectManager.bump_version",
        {"workspace": ".", "bump": "patch"},
    )
    assert bump_result.success is True
    assert bump_result.data["version"]["previous"] == "1.2.3"
    assert bump_result.data["version"]["current"] == "1.2.4"


@pytest.mark.asyncio
async def test_github_project_manager_extended_tools_with_mock_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.github import skill as gpm_skill

    class FakeGitHubIntegrationService:
        def __init__(self, workspace: Path) -> None:
            self.workspace = Path(workspace).resolve()

        @classmethod
        def from_env(
            cls, workspace: str | Path | None = None
        ) -> "FakeGitHubIntegrationService":
            return cls(Path(workspace or "."))

        def fetch(self, remote_name: str | None = None) -> dict[str, Any]:
            return {"remote": remote_name or "origin", "branch": "main", "ahead_by": 0, "behind_by": 0}

        def pull(
            self,
            *,
            remote_name: str | None = None,
            branch: str | None = None,
            rebase: bool = False,
        ) -> dict[str, Any]:
            return {
                "remote": remote_name or "origin",
                "branch": branch or "main",
                "ahead_by": 0,
                "behind_by": 0,
                "rebase": rebase,
            }

        def push(
            self,
            *,
            remote_name: str | None = None,
            branch: str | None = None,
            set_upstream: bool = False,
            tags: bool = False,
        ) -> dict[str, Any]:
            return {
                "remote": remote_name or "origin",
                "branch": branch or "main",
                "set_upstream": set_upstream,
                "tags": tags,
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
            return {
                "pull": {"remote": remote_name or "origin", "branch": branch or "main", "rebase": rebase},
                "push": {"remote": remote_name or "origin", "branch": branch or "main", "set_upstream": set_upstream, "tags": tags},
            }

        def create_branch(
            self,
            branch: str,
            *,
            from_ref: str | None = None,
            push: bool = False,
            set_upstream: bool = True,
            remote_name: str | None = None,
        ) -> dict[str, Any]:
            return {
                "branch": branch,
                "created_from": from_ref,
                "push": {
                    "remote": remote_name or "origin",
                    "set_upstream": set_upstream,
                }
                if push
                else None,
            }

        def checkout_branch(self, branch: str) -> dict[str, Any]:
            return {"branch": branch, "ahead_by": 0, "behind_by": 0}

        def list_pull_requests(
            self,
            *,
            state: str = "open",
            sort: str = "created",
            direction: str = "desc",
            per_page: int = 30,
            page: int = 1,
        ) -> list[dict[str, Any]]:
            return [
                {
                    "number": 10,
                    "title": "Example",
                    "state": state,
                    "sort": sort,
                    "direction": direction,
                    "per_page": per_page,
                    "page": page,
                }
            ]

        def repository_info(self, *, include_rate_limit: bool = False) -> dict[str, Any]:
            payload: dict[str, Any] = {"full_name": "owner/CATBot", "has_rate_limit": include_rate_limit}
            if include_rate_limit:
                payload["rate_limit"] = {"remaining": 100}
            return payload

    monkeypatch.setattr(
        gpm_skill,
        "_load_integration_service_class",
        lambda: FakeGitHubIntegrationService,
    )
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    fetch_result = await manager.execute_tool("GitHubProjectManager.fetch", {"workspace": "."})
    pull_result = await manager.execute_tool("GitHubProjectManager.pull", {"workspace": ".", "rebase": True})
    push_result = await manager.execute_tool(
        "GitHubProjectManager.push",
        {"workspace": ".", "branch": "feature/test", "set_upstream": True, "tags": True},
    )
    sync_result = await manager.execute_tool("GitHubProjectManager.sync", {"workspace": ".", "branch": "main"})
    branch_result = await manager.execute_tool(
        "GitHubProjectManager.create_branch",
        {"workspace": ".", "branch": "feature/new", "from_ref": "main", "push": True},
    )
    checkout_result = await manager.execute_tool(
        "GitHubProjectManager.checkout_branch",
        {"workspace": ".", "branch": "main"},
    )
    list_pr_result = await manager.execute_tool(
        "GitHubProjectManager.list_pull_requests",
        {"workspace": ".", "state": "open", "per_page": 10, "page": 2},
    )
    repo_result = await manager.execute_tool(
        "GitHubProjectManager.repository_info",
        {"workspace": ".", "include_rate_limit": True},
    )

    assert fetch_result.success is True
    assert pull_result.success is True
    assert pull_result.data["pull"]["rebase"] is True
    assert push_result.success is True
    assert push_result.data["push"]["set_upstream"] is True
    assert sync_result.success is True
    assert sync_result.data["sync"]["pull"]["branch"] == "main"
    assert branch_result.success is True
    assert branch_result.data["branch"]["branch"] == "feature/new"
    assert checkout_result.success is True
    assert checkout_result.data["checkout"]["branch"] == "main"
    assert list_pr_result.success is True
    assert list_pr_result.data["pull_requests"][0]["page"] == 2
    assert repo_result.success is True
    assert repo_result.data["repository"]["rate_limit"]["remaining"] == 100


def _create_temp_filesystem_manifest_dir(base: Path, root: Path) -> Path:
    manifest_dir = base / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "filesystem.skill.json"
    manifest_path.write_text(
        (
            "{\n"
            '  "name": "filesystem",\n'
            '  "module": "src.skills.builtin.filesystem_skill:create_skill",\n'
            '  "settings": {\n'
            f'    "root_dir": "{str(root).replace("\\", "/")}"\n'
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    return manifest_dir


def _create_workspace_temp_dir() -> Path:
    base = Path("scratch") / f"skills-test-{uuid.uuid4().hex}"
    base.mkdir(parents=True, exist_ok=True)
    return base

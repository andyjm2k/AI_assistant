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
    assert "image_generation" in names
    assert "testkit" in names

    tool_names = [spec.qualified_name for spec in manager.list_tools()]
    assert "core.ping" in tool_names
    assert "core.echo" in tool_names
    assert "filesystem.list_files" in tool_names
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

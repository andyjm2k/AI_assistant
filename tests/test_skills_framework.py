"""Tests for CATBot modular skills framework."""

from __future__ import annotations

import base64
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.skills import BaseSkill, BaseTool, SkillContext, SkillManager, SkillValidationError


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
    assert "googleworkspace_cli" in names
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
    assert "googleworkspace_cli.check_cli" in tool_names
    assert "googleworkspace_cli.check_auth" in tool_names
    assert "googleworkspace_cli.gmail_list_unread" in tool_names
    assert "googleworkspace_cli.gmail_get_message" in tool_names
    assert "googleworkspace_cli.gmail_compose_draft" in tool_names
    assert "googleworkspace_cli.gmail_send_message" in tool_names
    assert "googleworkspace_cli.gmail_mark_read" in tool_names
    assert "googleworkspace_cli.list_available_commands" in tool_names
    assert "googleworkspace_cli.run_readonly_command" in tool_names
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
async def test_googleworkspace_cli_check_cli_returns_version_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 7,
            "stdout": "gws 0.8.0\n",
            "stderr": "",
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool("googleworkspace_cli.check_cli", {})

    assert result.success is True
    assert result.data["available"] is True
    assert result.data["version"] == "gws 0.8.0"


@pytest.mark.asyncio
async def test_googleworkspace_cli_run_readonly_command_serializes_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    temp_base = _create_workspace_temp_dir()
    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        captured["timeout_seconds"] = timeout_seconds
        captured["cwd"] = str(cwd) if cwd is not None else None
        captured["env_overrides"] = dict(env_overrides or {})
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 12,
            "stdout": '{"files":[{"id":"abc123"}]}',
            "stderr": "",
            "parsed_json": {"files": [{"id": "abc123"}]},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    try:
        result = await manager.execute_tool(
            "googleworkspace_cli.run_readonly_command",
            {
                "service": "drive",
                "resource": "files",
                "action": "list",
                "params": {"pageSize": 5, "q": "name contains 'Q1'"},
                "dry_run": True,
            },
            context=SkillContext(scratch_dir=temp_base),
        )
        assert result.success is True
        assert captured["args"][:4] == ["gws", "drive", "files", "list"]
        assert "--params" in captured["args"]
        params_index = captured["args"].index("--params")
        params_payload = json.loads(captured["args"][params_index + 1])
        assert params_payload == {"pageSize": 5, "q": "name contains 'Q1'"}
        assert "--dry-run" in captured["args"]
        assert captured["env_overrides"].get("GOOGLE_WORKSPACE_CLI_CONFIG_DIR")
        assert result.data["response"]["parsed_json"]["files"][0]["id"] == "abc123"
    finally:
        shutil.rmtree(temp_base, ignore_errors=True)


@pytest.mark.asyncio
async def test_googleworkspace_cli_list_available_commands_parses_help(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 8,
            "stdout": (
                "Google Workspace CLI\n\n"
                "Commands:\n"
                "  files      Manage Drive files\n"
                "  permissions  Manage file permissions\n"
                "Options:\n"
                "  -h, --help   Show help\n"
            ),
            "stderr": "",
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool(
        "googleworkspace_cli.list_available_commands",
        {"service": "drive"},
    )
    assert result.success is True
    assert captured["args"] == ["gws", "drive", "--help"]
    assert result.data["scope"] == "drive"
    assert result.data["command_names"] == ["files", "permissions"]
    assert result.data["command_count"] == 2
    assert "response" not in result.data


@pytest.mark.asyncio
async def test_googleworkspace_cli_allows_create_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 9,
            "stdout": '{"presentationId":"pres_123"}',
            "stderr": "",
            "parsed_json": {"presentationId": "pres_123"},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "slides",
            "resource": "presentations",
            "action": "create",
            "json_payload": {"title": "Q2 Review"},
        },
    )
    assert result.success is True
    assert captured["args"][:4] == ["gws", "slides", "presentations", "create"]
    assert "--json" in captured["args"]
    assert result.data["response"]["parsed_json"]["presentationId"] == "pres_123"


@pytest.mark.asyncio
async def test_googleworkspace_cli_normalizes_gmail_compose_payload_for_draft_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 10,
            "stdout": '{"id":"draft_1"}',
            "stderr": "",
            "parsed_json": {"id": "draft_1"},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "resource": "drafts",
            "action": "create",
            "json_payload": {
                "to": "bob@example.com",
                "subject": "Test draft",
                "body": "Hello Bob",
            },
        },
    )
    assert result.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "drafts", "create"]
    assert "--json" in captured["args"]
    payload = json.loads(captured["args"][captured["args"].index("--json") + 1])
    assert isinstance(payload.get("message"), dict)
    raw_text = str(payload["message"].get("raw") or "")
    assert raw_text


@pytest.mark.asyncio
async def test_googleworkspace_cli_normalizes_gmail_compose_payload_for_message_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 9,
            "stdout": '{"id":"msg_sent"}',
            "stderr": "",
            "parsed_json": {"id": "msg_sent"},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "resource": "messages",
            "action": "send",
            "json_payload": {
                "to": ["bob@example.com"],
                "subject": "Hello",
                "text": "Body text",
            },
        },
    )
    assert result.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "messages", "send"]
    assert "--json" in captured["args"]
    payload = json.loads(captured["args"][captured["args"].index("--json") + 1])
    assert "raw" in payload
    assert isinstance(payload["raw"], str) and len(payload["raw"]) > 20


@pytest.mark.asyncio
async def test_googleworkspace_cli_gmail_list_unread_tool_builds_expected_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 9,
            "stdout": '{"messages":[]}',
            "stderr": "",
            "parsed_json": {"messages": []},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    result = await manager.execute_tool(
        "googleworkspace_cli.gmail_list_unread",
        {"max_results": 5, "query": "from:billing@example.com"},
    )
    assert result.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "messages", "list"]
    params_payload = json.loads(captured["args"][captured["args"].index("--params") + 1])
    assert params_payload["userId"] == "me"
    assert params_payload["maxResults"] == 5
    assert "in:inbox is:unread" in params_payload["q"]
    assert "from:billing@example.com" in params_payload["q"]


@pytest.mark.asyncio
async def test_googleworkspace_cli_gmail_get_message_tool_defaults_to_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 8,
            "stdout": '{"id":"m1"}',
            "stderr": "",
            "parsed_json": {"id": "m1"},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    result = await manager.execute_tool(
        "googleworkspace_cli.gmail_get_message",
        {"message_id": "m1"},
    )
    assert result.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "messages", "get"]
    params_payload = json.loads(captured["args"][captured["args"].index("--params") + 1])
    assert params_payload["userId"] == "me"
    assert params_payload["id"] == "m1"
    assert params_payload["format"] == "full"


@pytest.mark.asyncio
async def test_googleworkspace_cli_gmail_compose_draft_tool_builds_raw_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 11,
            "stdout": '{"id":"draft_1"}',
            "stderr": "",
            "parsed_json": {"id": "draft_1"},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    result = await manager.execute_tool(
        "googleworkspace_cli.gmail_compose_draft",
        {
            "to": "bob@example.com",
            "subject": "Draft subject",
            "body_text": "Draft body",
        },
    )
    assert result.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "drafts", "create"]
    params_payload = json.loads(captured["args"][captured["args"].index("--params") + 1])
    assert params_payload["userId"] == "me"
    json_payload = json.loads(captured["args"][captured["args"].index("--json") + 1])
    raw_text = str((json_payload.get("message") or {}).get("raw") or "")
    assert raw_text
    padded = raw_text + ("=" * (-len(raw_text) % 4))
    decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
    assert "Draft subject" in decoded
    assert "Draft body" in decoded


@pytest.mark.asyncio
async def test_googleworkspace_cli_gmail_send_message_tool_builds_raw_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 10,
            "stdout": '{"id":"msg_1"}',
            "stderr": "",
            "parsed_json": {"id": "msg_1"},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    result = await manager.execute_tool(
        "googleworkspace_cli.gmail_send_message",
        {
            "to": "alice@example.com",
            "subject": "Send subject",
            "body_text": "Send body",
        },
    )
    assert result.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "messages", "send"]
    params_payload = json.loads(captured["args"][captured["args"].index("--params") + 1])
    assert params_payload["userId"] == "me"
    json_payload = json.loads(captured["args"][captured["args"].index("--json") + 1])
    raw_text = str(json_payload.get("raw") or "")
    assert raw_text
    padded = raw_text + ("=" * (-len(raw_text) % 4))
    decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
    assert "Send subject" in decoded
    assert "Send body" in decoded


@pytest.mark.asyncio
async def test_googleworkspace_cli_gmail_mark_read_tool_calls_modify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 8,
            "stdout": '{"id":"m1","labelIds":["INBOX"]}',
            "stderr": "",
            "parsed_json": {"id": "m1", "labelIds": ["INBOX"]},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    result = await manager.execute_tool(
        "googleworkspace_cli.gmail_mark_read",
        {"message_id": "m1"},
    )
    assert result.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "messages", "modify"]
    params_payload = json.loads(captured["args"][captured["args"].index("--params") + 1])
    assert params_payload["userId"] == "me"
    assert params_payload["id"] == "m1"
    json_payload = json.loads(captured["args"][captured["args"].index("--json") + 1])
    assert json_payload["removeLabelIds"] == ["UNREAD"]


@pytest.mark.asyncio
async def test_googleworkspace_cli_normalizes_legacy_gmail_draft_payload_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 12,
            "stdout": '{"id":"draft_legacy_1"}',
            "stderr": "",
            "parsed_json": {"id": "draft_legacy_1"},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "resource": "drafts",
            "action": "create",
            "json_payload": {
                "draft": {
                    "message": {
                        "payload": {
                            "headers": [
                                {"name": "To", "value": "bob@example.com"},
                                {"name": "Subject", "value": "Legacy draft"},
                            ],
                            "body": {"data": "I want to draft a test email"},
                        }
                    }
                }
            },
        },
    )
    assert result.success is True
    payload = json.loads(captured["args"][captured["args"].index("--json") + 1])
    assert isinstance(payload.get("message"), dict)
    raw_text = str(payload["message"].get("raw") or "")
    assert raw_text
    padded = raw_text + ("=" * (-len(raw_text) % 4))
    decoded = base64.urlsafe_b64decode(padded).decode("utf-8", errors="ignore")
    assert "I want to draft a test email" in decoded
    assert "Subject: Legacy draft" in decoded
    assert "To: bob@example.com" in decoded


@pytest.mark.asyncio
async def test_googleworkspace_cli_check_auth_requires_active_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 11,
            "stdout": json.dumps(
                {
                    "auth_method": "none",
                    "credential_source": "none",
                    "encrypted_credentials_exists": False,
                    "plain_credentials_exists": False,
                    "has_refresh_token": False,
                }
            ),
            "stderr": "",
            "parsed_json": {
                "auth_method": "none",
                "credential_source": "none",
                "encrypted_credentials_exists": False,
                "plain_credentials_exists": False,
                "has_refresh_token": False,
            },
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool("googleworkspace_cli.check_auth", {})
    assert result.success is False
    assert result.error_code == "execution_error"
    assert "no active credentials" in str(result.message).lower()


@pytest.mark.asyncio
async def test_googleworkspace_cli_run_readonly_command_supports_nested_and_helper_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 10,
            "stdout": "{}",
            "stderr": "",
            "parsed_json": {},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    nested = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "resource": "users/messages",
            "action": "list",
            "params": {"userId": "me", "maxResults": 5},
        },
    )
    assert nested.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "messages", "list"]

    shorthand = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "resource": "messages",
            "action": "list",
            "params": {"userId": "me", "maxResults": 1},
        },
    )
    assert shorthand.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "messages", "list"]

    action_shorthand = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "action": "messages list",
            "params": {"userId": "me", "maxResults": 3},
        },
    )
    assert action_shorthand.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "messages", "list"]

    default_resource = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "action": "list",
            "params": {"maxResults": 2},
        },
    )
    assert default_resource.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "messages", "list"]
    assert "--params" in captured["args"]
    params_index = captured["args"].index("--params")
    params_payload = json.loads(captured["args"][params_index + 1])
    assert params_payload["userId"] == "me"
    assert params_payload["maxResults"] == 2

    implicit_defaults = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "action": "list",
        },
    )
    assert implicit_defaults.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "messages", "list"]
    assert "--params" in captured["args"]
    params_index = captured["args"].index("--params")
    params_payload = json.loads(captured["args"][params_index + 1])
    assert params_payload["userId"] == "me"
    assert params_payload["maxResults"] == 10

    helper = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "action": "+triage",
        },
    )
    assert helper.success is True
    assert captured["args"][:3] == ["gws", "gmail", "+triage"]


@pytest.mark.asyncio
async def test_googleworkspace_cli_enriches_gmail_list_with_message_summaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    calls: list[list[str]] = []

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        command = list(args)
        calls.append(command)
        if command[:5] == ["gws", "gmail", "users", "messages", "list"]:
            return {
                "command": command,
                "returncode": 0,
                "duration_ms": 8,
                "stdout": '{"messages":[{"id":"m1","threadId":"t1"}]}',
                "stderr": "",
                "parsed_json": {"messages": [{"id": "m1", "threadId": "t1"}]},
            }
        if command[:5] == ["gws", "gmail", "users", "messages", "get"]:
            return {
                "command": command,
                "returncode": 0,
                "duration_ms": 7,
                "stdout": (
                    '{"id":"m1","threadId":"t1","snippet":"Preview text",'
                    '"payload":{"headers":[{"name":"From","value":"Alice <alice@example.com>"},'
                    '{"name":"Subject","value":"Status update"},{"name":"Date","value":"Mon, 9 Mar 2026"}]},'
                    '"labelIds":["INBOX","UNREAD"]}'
                ),
                "stderr": "",
                "parsed_json": {
                    "id": "m1",
                    "threadId": "t1",
                    "snippet": "Preview text",
                    "payload": {
                        "headers": [
                            {"name": "From", "value": "Alice <alice@example.com>"},
                            {"name": "Subject", "value": "Status update"},
                            {"name": "Date", "value": "Mon, 9 Mar 2026"},
                        ]
                    },
                    "labelIds": ["INBOX", "UNREAD"],
                },
            }
        return {"command": command, "returncode": 0, "duration_ms": 6, "stdout": "{}", "stderr": "", "parsed_json": {}}

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "resource": "messages",
            "action": "list",
            "params": {"maxResults": 1},
        },
    )
    assert result.success is True
    summaries = (result.data or {}).get("gmail_message_summaries")
    assert isinstance(summaries, list) and len(summaries) == 1
    assert summaries[0]["subject"] == "Status update"
    assert summaries[0]["from"] == "Alice <alice@example.com>"
    assert summaries[0]["snippet"] == "Preview text"
    assert any(call[:5] == ["gws", "gmail", "users", "messages", "get"] for call in calls)


@pytest.mark.asyncio
async def test_googleworkspace_cli_gmail_summary_falls_back_to_full_format_for_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    calls: list[list[str]] = []

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        command = list(args)
        calls.append(command)
        if command[:5] == ["gws", "gmail", "users", "messages", "list"]:
            return {
                "command": command,
                "returncode": 0,
                "duration_ms": 8,
                "stdout": '{"messages":[{"id":"m2","threadId":"t2"}]}',
                "stderr": "",
                "parsed_json": {"messages": [{"id": "m2", "threadId": "t2"}]},
            }
        if command[:5] == ["gws", "gmail", "users", "messages", "get"]:
            params_payload = json.loads(command[command.index("--params") + 1])
            if params_payload.get("format") == "metadata":
                # Simulate metadata response without useful headers.
                return {
                    "command": command,
                    "returncode": 0,
                    "duration_ms": 7,
                    "stdout": '{"id":"m2","threadId":"t2","payload":{"headers":[]},"snippet":"Fallback preview"}',
                    "stderr": "",
                    "parsed_json": {
                        "id": "m2",
                        "threadId": "t2",
                        "payload": {"headers": []},
                        "snippet": "Fallback preview",
                    },
                }
            # full format fallback returns headers
            return {
                "command": command,
                "returncode": 0,
                "duration_ms": 7,
                "stdout": (
                    '{"id":"m2","threadId":"t2","snippet":"Fallback preview",'
                    '"payload":{"headers":[{"name":"Sender","value":"Bob <bob@example.com>"},'
                    '{"name":"Subject","value":"Invoice ready"},{"name":"Date","value":"Mon, 9 Mar 2026"}]}}'
                ),
                "stderr": "",
                "parsed_json": {
                    "id": "m2",
                    "threadId": "t2",
                    "snippet": "Fallback preview",
                    "payload": {
                        "headers": [
                            {"name": "Sender", "value": "Bob <bob@example.com>"},
                            {"name": "Subject", "value": "Invoice ready"},
                            {"name": "Date", "value": "Mon, 9 Mar 2026"},
                        ]
                    },
                },
            }
        return {"command": command, "returncode": 0, "duration_ms": 6, "stdout": "{}", "stderr": "", "parsed_json": {}}

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "resource": "messages",
            "action": "list",
            "params": {"maxResults": 1},
        },
    )
    assert result.success is True
    summaries = (result.data or {}).get("gmail_message_summaries")
    assert isinstance(summaries, list) and len(summaries) == 1
    assert summaries[0]["subject"] == "Invoice ready"
    assert summaries[0]["from"] == "Bob <bob@example.com>"
    assert summaries[0]["snippet"] == "Fallback preview"
    get_calls = [call for call in calls if call[:5] == ["gws", "gmail", "users", "messages", "get"]]
    assert len(get_calls) >= 2


@pytest.mark.asyncio
async def test_googleworkspace_cli_list_available_commands_normalizes_gmail_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 6,
            "stdout": "Commands:\n  list  List messages\n",
            "stderr": "",
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool(
        "googleworkspace_cli.list_available_commands",
        {"service": "gmail", "resource": "messages"},
    )
    assert result.success is True
    assert captured["args"] == ["gws", "gmail", "users", "messages", "--help"]


@pytest.mark.asyncio
async def test_googleworkspace_cli_defaults_gmail_message_get_to_full_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.skills.builtin import googleworkspace_cli_skill as gws_skill

    captured: Dict[str, Any] = {}

    async def fake_run_gws_command(
        args: Sequence[str],
        *,
        timeout_seconds: float,
        cwd: Path | None = None,
        env_overrides: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        captured["args"] = list(args)
        return {
            "command": list(args),
            "returncode": 0,
            "duration_ms": 6,
            "stdout": '{"id":"m_full"}',
            "stderr": "",
            "parsed_json": {"id": "m_full"},
        }

    monkeypatch.setattr(gws_skill, "_run_gws_command", fake_run_gws_command)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    result = await manager.execute_tool(
        "googleworkspace_cli.run_readonly_command",
        {
            "service": "gmail",
            "resource": "messages",
            "action": "get",
            "params": {"id": "abc123"},
        },
    )
    assert result.success is True
    assert captured["args"][:5] == ["gws", "gmail", "users", "messages", "get"]
    params_payload = json.loads(captured["args"][captured["args"].index("--params") + 1])
    assert params_payload["id"] == "abc123"
    assert params_payload["userId"] == "me"
    assert params_payload["format"] == "full"


@pytest.mark.asyncio
async def test_googleworkspace_cli_blocks_mutating_actions() -> None:
    manager = SkillManager.from_manifest_directory("src/skills/manifests")

    with pytest.raises(SkillValidationError, match="Destructive actions are blocked"):
        await manager.execute_tool(
            "googleworkspace_cli.run_readonly_command",
            {
                "service": "drive",
                "resource": "files",
                "action": "delete",
            },
            raise_errors=True,
        )


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

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.skills import SkillContext, SkillManager


@pytest.mark.asyncio
async def test_telegram_admin_notify_admin_sends_to_first_configured_admin() -> None:
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    sender = AsyncMock(return_value=True)
    context = SkillContext(
        services={
            "telegram_admin_chat_ids": ["111", "222"],
            "telegram_send_message": sender,
        }
    )

    result = await manager.execute_tool(
        "telegram_admin.notify_admin",
        {"message": "Build completed."},
        context=context,
    )

    assert result.success is True
    assert result.data["delivered_chat_ids"] == ["111"]
    assert result.data["delivery_mode"] == "message"
    sender.assert_awaited_once_with("111", "Build completed.")


@pytest.mark.asyncio
async def test_telegram_admin_notify_admin_can_broadcast_to_all_admins() -> None:
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    sender = AsyncMock(return_value=True)
    context = SkillContext(
        services={
            "telegram_admin_chat_ids": ["111", "222"],
            "telegram_send_message": sender,
        }
    )

    result = await manager.execute_tool(
        "telegram_admin.notify_admin",
        {"message": "Deployment finished.", "send_to_all_admins": True},
        context=context,
    )

    assert result.success is True
    assert result.data["delivered_chat_ids"] == ["111", "222"]
    assert result.data["delivery_mode"] == "message"
    assert sender.await_count == 2


@pytest.mark.asyncio
async def test_telegram_admin_notify_admin_sends_file_to_first_configured_admin(
) -> None:
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    sender = AsyncMock(return_value=True)
    scratch_dir = Path("scratch") / f"skills-telegram-admin-{uuid4().hex}"
    try:
        report_path = scratch_dir / "reports" / "build.txt"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("build ok", encoding="utf-8")
        context = SkillContext(
            scratch_dir=scratch_dir,
            services={
                "telegram_admin_chat_ids": ["111", "222"],
                "telegram_send_file": sender,
            },
        )

        result = await manager.execute_tool(
            "telegram_admin.notify_admin",
            {"filePath": "reports/build.txt"},
            context=context,
        )

        assert result.success is True
        assert result.data["delivery_mode"] == "file"
        assert result.data["delivered_chat_ids"] == ["111"]
        assert result.data["file_path"] == "reports/build.txt"
        sender.assert_awaited_once_with("111", "reports/build.txt")
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_telegram_admin_notify_admin_prioritizes_file_over_message(
) -> None:
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    message_sender = AsyncMock(return_value=True)
    file_sender = AsyncMock(return_value=True)
    scratch_dir = Path("scratch") / f"skills-telegram-admin-{uuid4().hex}"
    try:
        report_path = scratch_dir / "reports" / "deploy.txt"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("deploy ok", encoding="utf-8")
        context = SkillContext(
            scratch_dir=scratch_dir,
            services={
                "telegram_admin_chat_ids": ["111"],
                "telegram_send_message": message_sender,
                "telegram_send_file": file_sender,
            },
        )

        result = await manager.execute_tool(
            "telegram_admin.notify_admin",
            {"message": "Ignore this text.", "filePath": "reports/deploy.txt"},
            context=context,
        )

        assert result.success is True
        assert result.data["delivery_mode"] == "file"
        file_sender.assert_awaited_once_with("111", "reports/deploy.txt")
        message_sender.assert_not_awaited()
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_telegram_admin_notify_admin_requires_configured_admin_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TELEGRAM_ADMIN_IDS", raising=False)
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    sender = AsyncMock(return_value=True)
    context = SkillContext(services={"telegram_send_message": sender})

    result = await manager.execute_tool(
        "telegram_admin.notify_admin",
        {"message": "Hello"},
        context=context,
    )

    assert result.success is False
    assert "No Telegram admin IDs are configured" in result.message


@pytest.mark.asyncio
async def test_telegram_admin_notify_admin_requires_message_or_file_path() -> None:
    manager = SkillManager.from_manifest_directory("src/skills/manifests")
    context = SkillContext(services={"telegram_admin_chat_ids": ["111"]})

    result = await manager.execute_tool(
        "telegram_admin.notify_admin",
        {},
        context=context,
    )

    assert result.success is False
    assert "Either message or filePath is required." in result.message

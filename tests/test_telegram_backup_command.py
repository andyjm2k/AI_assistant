from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.integrations.telegram_bot as telegram_bot


@pytest.mark.asyncio
async def test_help_command_includes_backup() -> None:
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()

    await telegram_bot.help_command(update, MagicMock())

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.await_args.args[0]
    assert "/backup - create a ZIP backup in C:\\Users\\pc\\CATBot\\backups" in text


@pytest.mark.asyncio
async def test_backup_bot_command_starts_worker() -> None:
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 555

    with patch(
        "src.integrations.telegram_bot._authorize_or_reject",
        new=AsyncMock(return_value=123),
    ), patch("src.integrations.telegram_bot._spawn_backup_worker") as mock_spawn:
        await telegram_bot.backup_bot_command(update, MagicMock())

    mock_spawn.assert_called_once_with(chat_id=555, requested_by=123)
    update.message.reply_text.assert_awaited_once_with(
        "Backup workflow started. I will post the archive path in this chat when it completes."
    )


@pytest.mark.asyncio
async def test_backup_bot_command_reports_launch_failure() -> None:
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 555

    with patch(
        "src.integrations.telegram_bot._authorize_or_reject",
        new=AsyncMock(return_value=123),
    ), patch(
        "src.integrations.telegram_bot._spawn_backup_worker",
        side_effect=RuntimeError("boom"),
    ):
        await telegram_bot.backup_bot_command(update, MagicMock())

    update.message.reply_text.assert_awaited_once_with(
        "Failed to start backup workflow. Check server logs."
    )

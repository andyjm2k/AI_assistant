"""Built-in skill for proactive Telegram admin notifications."""

from __future__ import annotations

from collections.abc import Iterable
import inspect
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
from typing import Any, Dict, List, Sequence

import httpx

from src.skills.base import BaseSkill, BaseTool
from src.skills.exceptions import SkillValidationError
from src.skills.models import SkillContext, ToolExecutionResult

_TELEGRAM_CHAT_ID_RE = re.compile(r"^-?\d+$")
_TELEGRAM_TEXT_LIMIT = 4000


def _normalize_relative_path_input(relative_path: str) -> str:
    normalized = str(relative_path or "").strip()
    if not normalized:
        return normalized
    normalized = normalized.replace("\\", "/")
    lowered = normalized.lower()
    if lowered == "scratch":
        return "."
    if lowered.startswith("scratch/"):
        trimmed = normalized[len("scratch/") :]
        return trimmed or "."
    return normalized


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return default


def _parse_admin_chat_ids(raw_value: Any) -> List[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        candidates: Iterable[Any] = raw_value.split(",")
    elif isinstance(raw_value, Iterable):
        candidates = raw_value
    else:
        candidates = [raw_value]

    seen: set[str] = set()
    parsed: List[str] = []
    for item in candidates:
        chat_id = str(item or "").strip()
        if not chat_id or not _TELEGRAM_CHAT_ID_RE.fullmatch(chat_id) or chat_id in seen:
            continue
        seen.add(chat_id)
        parsed.append(chat_id)
    return parsed


def _split_telegram_text(text: str, max_chars: int = _TELEGRAM_TEXT_LIMIT) -> List[str]:
    normalized = str(text or "")
    if not normalized:
        return [""]
    if max_chars < 1:
        max_chars = _TELEGRAM_TEXT_LIMIT

    chunks: List[str] = []
    remaining = normalized
    while len(remaining) > max_chars:
        split_at = remaining.rfind("\n", 0, max_chars + 1)
        if split_at > 0:
            split_at += 1
        else:
            split_at = remaining.rfind(" ", 0, max_chars + 1)
            if split_at > 0:
                split_at += 1
        if split_at <= 0:
            split_at = max_chars
        chunk = remaining[:split_at]
        if not chunk:
            chunk = remaining[:max_chars]
            split_at = len(chunk)
        chunks.append(chunk)
        remaining = remaining[split_at:]
    if remaining:
        chunks.append(remaining)
    return chunks or [normalized]


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _send_via_bot_api(chat_id: str, text: str) -> bool:
    token = str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise SkillValidationError("TELEGRAM_BOT_TOKEN is not configured.")

    response: httpx.Response
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )

    if response.status_code != 200:
        detail = response.text[:500].strip()
        raise RuntimeError(
            f"Telegram sendMessage failed ({response.status_code}) for chat_id={chat_id}: {detail}"
        )

    payload = response.json()
    if not payload.get("ok"):
        detail = str(payload.get("description") or "Telegram sendMessage returned ok=false.").strip()
        raise RuntimeError(f"Telegram sendMessage failed for chat_id={chat_id}: {detail}")
    return True


async def _send_file_via_bot_api(chat_id: str, file_path: Path) -> bool:
    token = str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise SkillValidationError("TELEGRAM_BOT_TOKEN is not configured.")

    mime_type, _ = mimetypes.guess_type(str(file_path))
    response: httpx.Response
    async with httpx.AsyncClient(timeout=30.0) as client:
        with file_path.open("rb") as file_handle:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": chat_id},
                files={
                    "document": (
                        file_path.name,
                        file_handle,
                        mime_type or "application/octet-stream",
                    )
                },
            )

    if response.status_code != 200:
        detail = response.text[:500].strip()
        raise RuntimeError(
            f"Telegram sendDocument failed ({response.status_code}) for chat_id={chat_id}: {detail}"
        )

    payload = response.json()
    if not payload.get("ok"):
        detail = str(payload.get("description") or "Telegram sendDocument returned ok=false.").strip()
        raise RuntimeError(f"Telegram sendDocument failed for chat_id={chat_id}: {detail}")
    return True


async def _resolve_admin_chat_ids(context: SkillContext) -> List[str]:
    service_value = context.get_service("telegram_admin_chat_ids")
    if callable(service_value):
        service_value = await _maybe_await(service_value())
    parsed = _parse_admin_chat_ids(service_value)
    if parsed:
        return parsed
    return _parse_admin_chat_ids(os.getenv("TELEGRAM_ADMIN_IDS"))


def _resolve_scratch_file_path(context: SkillContext, relative_path: str) -> tuple[str, Path]:
    normalized = _normalize_relative_path_input(relative_path)
    if not normalized or normalized == ".":
        raise SkillValidationError("filePath is required when sending a file.")
    if (
        Path(normalized).is_absolute()
        or normalized.startswith("/")
        or bool(re.match(r"^[A-Za-z]:/", normalized))
    ):
        raise SkillValidationError("filePath must be relative to the scratch directory.")
    if ".." in PurePosixPath(normalized).parts:
        raise SkillValidationError("filePath must stay within the scratch directory.")

    scratch_root = (context.scratch_dir or Path("./scratch")).resolve()
    candidate = (scratch_root / normalized).resolve()
    try:
        candidate.relative_to(scratch_root)
    except ValueError as exc:
        raise SkillValidationError("filePath must stay within the scratch directory.") from exc
    if not candidate.exists() or not candidate.is_file():
        raise SkillValidationError(f"Scratch file not found: {normalized}")
    return normalized, candidate


async def _send_telegram_message(
    context: SkillContext,
    *,
    chat_id: str,
    text: str,
) -> bool:
    sender = context.get_service("telegram_send_message")
    if callable(sender):
        result = await _maybe_await(sender(chat_id, text))
        if isinstance(result, dict):
            return bool(result.get("success"))
        return bool(result)
    return await _send_via_bot_api(chat_id, text)


async def _send_telegram_file(
    context: SkillContext,
    *,
    chat_id: str,
    logical_path: str,
    resolved_path: Path,
) -> bool:
    sender = context.get_service("telegram_send_file")
    if callable(sender):
        result = await _maybe_await(sender(chat_id, logical_path))
        if isinstance(result, dict):
            return bool(result.get("success"))
        return bool(result)
    return await _send_file_via_bot_api(chat_id, resolved_path)


class NotifyAdminTool(BaseTool):
    name = "notify_admin"
    description = (
        "Send a proactive Telegram notification to the configured Telegram admin user. "
        "Provide `message` for text delivery or `filePath` for a scratch-relative file; "
        "if both are provided, the file is sent. By default this targets the first configured admin id."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "Optional message text to deliver to the configured Telegram admin chat.",
            },
            "filePath": {
                "type": "string",
                "description": (
                    "Optional path to a file under the scratch directory. "
                    "When provided, that file is sent to the admin chat instead of the message text."
                ),
            },
            "send_to_all_admins": {
                "type": "boolean",
                "default": False,
                "description": "When true, send the message or file to every configured Telegram admin id.",
            },
        },
        "anyOf": [{"required": ["message"]}, {"required": ["filePath"]}],
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> ToolExecutionResult | Dict[str, Any]:
        try:
            message = str(arguments.get("message", "")).strip()
            file_path_input = str(
                arguments.get("filePath", arguments.get("file_path", "")) or ""
            ).strip()
            if not message and not file_path_input:
                raise SkillValidationError("Either message or filePath is required.")

            admin_chat_ids = await _resolve_admin_chat_ids(context)
            if not admin_chat_ids:
                raise SkillValidationError(
                    "No Telegram admin IDs are configured. Set TELEGRAM_ADMIN_IDS for the Telegram integration."
                )

            send_to_all = _coerce_bool(arguments.get("send_to_all_admins", False), default=False)
            target_chat_ids = admin_chat_ids if send_to_all else admin_chat_ids[:1]
            delivered_chat_ids: List[str] = []
            failures: List[Dict[str, str]] = []

            if file_path_input:
                normalized_file_path, resolved_file_path = _resolve_scratch_file_path(context, file_path_input)

                for chat_id in target_chat_ids:
                    try:
                        sent = await _send_telegram_file(
                            context,
                            chat_id=chat_id,
                            logical_path=normalized_file_path,
                            resolved_path=resolved_file_path,
                        )
                        if not sent:
                            raise RuntimeError("Telegram file sender returned an unsuccessful result.")
                        delivered_chat_ids.append(chat_id)
                    except Exception as exc:
                        failures.append({"chat_id": chat_id, "error": str(exc)})

                if not delivered_chat_ids:
                    return ToolExecutionResult(
                        success=False,
                        message="Failed to send a Telegram file to the configured admin chat.",
                        data={
                            "target_chat_ids": target_chat_ids,
                            "failures": failures,
                            "file_path": normalized_file_path,
                        },
                        error_code="delivery_failed",
                    )

                result = {
                    "sent": True,
                    "delivery_mode": "file",
                    "target_chat_ids": target_chat_ids,
                    "delivered_chat_ids": delivered_chat_ids,
                    "requested_target_count": len(target_chat_ids),
                    "delivered_target_count": len(delivered_chat_ids),
                    "file_path": normalized_file_path,
                    "filename": resolved_file_path.name,
                }
            else:
                chunks = _split_telegram_text(message)

                for chat_id in target_chat_ids:
                    try:
                        for chunk in chunks:
                            sent = await _send_telegram_message(context, chat_id=chat_id, text=chunk)
                            if not sent:
                                raise RuntimeError("Telegram sender returned an unsuccessful result.")
                        delivered_chat_ids.append(chat_id)
                    except Exception as exc:
                        failures.append({"chat_id": chat_id, "error": str(exc)})

                if not delivered_chat_ids:
                    return ToolExecutionResult(
                        success=False,
                        message="Failed to send a Telegram message to the configured admin chat.",
                        data={
                            "target_chat_ids": target_chat_ids,
                            "failures": failures,
                            "message_chunk_count": len(chunks),
                        },
                        error_code="delivery_failed",
                    )

                result = {
                    "sent": True,
                    "delivery_mode": "message",
                    "target_chat_ids": target_chat_ids,
                    "delivered_chat_ids": delivered_chat_ids,
                    "requested_target_count": len(target_chat_ids),
                    "delivered_target_count": len(delivered_chat_ids),
                    "message_chunk_count": len(chunks),
                }
            if failures:
                result["failures"] = failures
                result["warning"] = f"Delivery failed for {len(failures)} admin chat(s)."
            return result
        except SkillValidationError as exc:
            return ToolExecutionResult(
                success=False,
                message=str(exc),
                error_code="validation_error",
            )


class TelegramAdminSkill(BaseSkill):
    name = "telegram_admin"
    description = "Proactive Telegram notifications and scratch-file delivery for the configured CATBot admin user."
    version = "1.1.0"
    tags = ["telegram", "notifications", "admin"]

    def create_tools(self) -> Sequence[BaseTool]:
        return [NotifyAdminTool()]


def create_skill() -> BaseSkill:
    return TelegramAdminSkill()

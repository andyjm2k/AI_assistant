"""Built-in Google Workspace CLI (gws) wrapper skill."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from src.skills.base import BaseSkill, BaseTool
from src.skills.exceptions import SkillValidationError
from src.skills.models import SkillContext

_COMMAND_TOKEN_RE = re.compile(r"^[A-Za-z0-9+][A-Za-z0-9+._-]{0,63}$")
_COMMAND_PATH_SPLIT_RE = re.compile(r"[\\/\s]+")
_DEFAULT_TIMEOUT_SECONDS = 30.0
_MAX_TIMEOUT_SECONDS = 180.0
_MAX_OUTPUT_CHARS = 50_000
_BLOCKED_ACTION_PREFIXES = (
    "delete",
    "trash",
    "untrash",
    "remove",
    "revoke",
)
_GWS_CONFIG_MARKERS = (
    "client_secret.json",
    "credentials.enc",
    "credentials.json",
    "token_cache.json",
    ".encryption_key",
)
_GMAIL_USER_SCOPED_RESOURCES = {
    "drafts",
    "history",
    "labels",
    "messages",
    "settings",
    "threads",
}


def _truncate_text(value: str, *, max_chars: int = _MAX_OUTPUT_CHARS) -> tuple[str, bool]:
    text = str(value or "")
    if len(text) <= max_chars:
        return text, False
    overflow = len(text) - max_chars
    suffix = f"\n...[truncated {overflow} chars]"
    keep = max(max_chars - len(suffix), 0)
    return f"{text[:keep]}{suffix}", True


def _parse_json_if_possible(raw: str) -> Any:
    text = str(raw or "").strip()
    if not text:
        return None
    if not (text.startswith("{") or text.startswith("[")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _coerce_timeout_seconds(value: Any, *, default: float = _DEFAULT_TIMEOUT_SECONDS) -> float:
    try:
        parsed = float(default if value is None else value)
    except (TypeError, ValueError):
        parsed = default
    return max(5.0, min(parsed, _MAX_TIMEOUT_SECONDS))


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


def _parse_command_segments(
    value: Any,
    *,
    key: str,
    allow_empty: bool = False,
    split_dots: bool = False,
) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        if allow_empty:
            return []
        raise SkillValidationError(f"'{key}' is required.")

    tokens: list[str] = []
    for chunk in _COMMAND_PATH_SPLIT_RE.split(raw):
        if not chunk:
            continue
        segments = chunk.split(".") if split_dots else [chunk]
        for segment in segments:
            token = str(segment).strip()
            if not token:
                continue
            if not _COMMAND_TOKEN_RE.fullmatch(token):
                raise SkillValidationError(
                    f"'{key}' contains unsupported characters. Use letters, numbers, plus, dot, underscore, or hyphen only."
                )
            tokens.append(token)

    if not tokens and not allow_empty:
        raise SkillValidationError(f"'{key}' is required.")
    return tokens


def _looks_like_gws_config_dir(path: Path) -> bool:
    try:
        if not path.exists() or not path.is_dir():
            return False
        return any((path / marker).exists() for marker in _GWS_CONFIG_MARKERS)
    except OSError:
        return False


def _candidate_home_dirs(working_dir: Optional[Path]) -> list[Path]:
    homes: list[Path] = []
    seen: set[str] = set()

    def _add(path_value: Optional[str]) -> None:
        if not path_value:
            return
        try:
            resolved = Path(path_value).expanduser().resolve()
        except OSError:
            return
        key = str(resolved).lower()
        if key in seen:
            return
        seen.add(key)
        homes.append(resolved)

    _add(os.environ.get("USERPROFILE"))
    _add(os.environ.get("HOME"))

    home_drive = str(os.environ.get("HOMEDRIVE", "")).strip()
    home_path = str(os.environ.get("HOMEPATH", "")).strip()
    if home_drive and home_path:
        _add(f"{home_drive}{home_path}")

    for candidate_path in (working_dir, Path.cwd()):
        if candidate_path is None:
            continue
        try:
            parts = list(candidate_path.resolve().parts)
        except OSError:
            continue
        lowered = [part.lower() for part in parts]
        if "users" not in lowered:
            continue
        users_index = lowered.index("users")
        if users_index + 1 >= len(parts):
            continue
        _add(str(Path(*parts[: users_index + 2])))

    return homes


def _resolve_gws_config_dir(working_dir: Optional[Path]) -> Path:
    explicit_dir = str(os.environ.get("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", "")).strip()
    if explicit_dir:
        return Path(explicit_dir).expanduser().resolve()

    for home_dir in _candidate_home_dirs(working_dir):
        candidate = home_dir / ".config" / "gws"
        if _looks_like_gws_config_dir(candidate):
            return candidate

    base_dir = (working_dir or Path.cwd()).resolve()
    fallback = base_dir / ".gws-config"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _build_gws_env_overrides(working_dir: Optional[Path]) -> Dict[str, str]:
    config_dir = _resolve_gws_config_dir(working_dir)
    env: Dict[str, str] = {
        "GOOGLE_WORKSPACE_CLI_CONFIG_DIR": str(config_dir),
    }

    if config_dir.parent.name == ".config":
        env["XDG_CONFIG_HOME"] = str(config_dir.parent)
        home_dir = config_dir.parent.parent
        env["HOME"] = str(home_dir)
        env["USERPROFILE"] = str(home_dir)

    if not str(os.environ.get("SSL_CERT_FILE", "")).strip():
        try:
            import certifi  # type: ignore

            cert_file = str(certifi.where()).strip()
            if cert_file:
                env["SSL_CERT_FILE"] = cert_file
        except Exception:
            pass

    return env


def _resolve_gws_executable(requested: str, working_dir: Optional[Path]) -> str:
    token = str(requested or "").strip()
    if not token:
        return "gws"

    lowered = token.lower()
    if lowered not in {"gws", "gws.cmd", "gws.exe", "gws.ps1"}:
        return token

    candidates: list[str] = []
    seen: set[str] = set()

    def _add(path_value: Optional[str]) -> None:
        value = str(path_value or "").strip()
        if not value:
            return
        key = value.lower()
        if key in seen:
            return
        seen.add(key)
        candidates.append(value)

    _add(os.environ.get("GOOGLE_WORKSPACE_CLI_BIN"))
    _add(token)

    appdata = str(os.environ.get("APPDATA", "")).strip()
    if appdata:
        _add(str(Path(appdata) / "npm" / "gws.cmd"))
    local_appdata = str(os.environ.get("LOCALAPPDATA", "")).strip()
    if local_appdata:
        _add(str(Path(local_appdata) / "npm" / "gws.cmd"))

    for home_dir in _candidate_home_dirs(working_dir):
        _add(str(home_dir / "AppData" / "Roaming" / "npm" / "gws.cmd"))

    for candidate in candidates:
        if candidate == token:
            continue
        try:
            path = Path(candidate).expanduser().resolve()
        except OSError:
            continue
        if path.is_file():
            return str(path)
    return token


def _normalize_gmail_resource_segments(service: str, resource_segments: Sequence[str]) -> list[str]:
    if str(service).strip().lower() != "gmail":
        return list(resource_segments)
    if not resource_segments:
        return list(resource_segments)
    first = str(resource_segments[0]).strip().lower()
    if first in _GMAIL_USER_SCOPED_RESOURCES:
        return ["users", *list(resource_segments)]
    return list(resource_segments)


def _normalize_gmail_command_shape(
    service: str,
    resource_segments: Sequence[str],
    action_segments: Sequence[str],
) -> tuple[list[str], list[str]]:
    service_name = str(service or "").strip().lower()
    resource = [str(segment).strip() for segment in resource_segments if str(segment).strip()]
    action = [str(segment).strip() for segment in action_segments if str(segment).strip()]

    if service_name != "gmail":
        return resource, action

    # Accept shorthand action paths like "messages list" by promoting the first
    # action segment into resource when resource is omitted.
    if not resource and action:
        first_action = action[0].lower()
        if first_action in _GMAIL_USER_SCOPED_RESOURCES:
            resource = [first_action]
            action = action[1:] or ["list"]
        elif first_action in {"list", "get", "read", "search"}:
            # For Gmail requests with omitted resource, default to messages.
            resource = ["messages"]

    normalized_resource = _normalize_gmail_resource_segments(service, resource)
    return normalized_resource, action


def _ensure_gmail_user_id_param(
    service: str,
    resource_segments: Sequence[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    if str(service or "").strip().lower() != "gmail":
        return params
    if not resource_segments:
        return params
    if str(resource_segments[0] or "").strip().lower() != "users":
        return params

    existing_keys = {str(key).strip().lower() for key in params.keys()}
    if "userid" in existing_keys:
        return params

    updated = dict(params)
    updated["userId"] = "me"
    return updated


def _ensure_gmail_list_limit(
    service: str,
    action_segments: Sequence[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    if str(service or "").strip().lower() != "gmail":
        return params
    if not action_segments:
        return params
    if str(action_segments[0] or "").strip().lower() != "list":
        return params

    existing_keys = {str(key).strip().lower() for key in params.keys()}
    if "maxresults" in existing_keys:
        return params

    updated = dict(params)
    updated["maxResults"] = 10
    return updated


def _ensure_gmail_message_get_format(
    service: str,
    resource_segments: Sequence[str],
    action_segments: Sequence[str],
    params: Dict[str, Any],
) -> Dict[str, Any]:
    if str(service or "").strip().lower() != "gmail":
        return params
    if not action_segments:
        return params
    action = str(action_segments[0] or "").strip().lower()
    if action not in {"get", "read"}:
        return params

    normalized_resource = [str(part).strip().lower() for part in resource_segments if str(part).strip()]
    if normalized_resource[:2] != ["users", "messages"]:
        return params

    existing_keys = {str(key).strip().lower() for key in params.keys()}
    if "format" in existing_keys:
        return params

    updated = dict(params)
    updated["format"] = "full"
    return updated


def _extract_primary_error(result: Dict[str, Any]) -> str:
    stderr = str(result.get("stderr", "")).strip()
    if stderr:
        return stderr
    stdout = str(result.get("stdout", "")).strip()
    if stdout:
        return stdout
    return "No output returned by gws."


def _is_gmail_messages_list_request(
    service: str,
    resource_segments: Sequence[str],
    action_segments: Sequence[str],
) -> bool:
    if str(service or "").strip().lower() != "gmail":
        return False
    if not action_segments:
        return False
    if str(action_segments[0] or "").strip().lower() != "list":
        return False
    normalized_resource = [str(part).strip().lower() for part in resource_segments if str(part).strip()]
    return normalized_resource[:2] == ["users", "messages"]


def _extract_gmail_message_ids(payload: Any, *, max_items: int = 3) -> list[str]:
    if not isinstance(payload, dict):
        return []
    raw_messages = payload.get("messages")
    if not isinstance(raw_messages, list):
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        message_id = str(item.get("id") or "").strip()
        if not message_id or message_id in seen:
            continue
        seen.add(message_id)
        ids.append(message_id)
        if len(ids) >= max_items:
            break
    return ids


def _extract_gmail_headers_map(payload: Any) -> Dict[str, str]:
    headers_map: Dict[str, str] = {}
    if not isinstance(payload, dict):
        return headers_map

    header_lists: list[list[Dict[str, Any]]] = []

    def _walk(node: Any, depth: int = 0) -> None:
        if depth > 7:
            return
        if isinstance(node, list):
            if node and all(isinstance(item, dict) and "value" in item for item in node):
                if any("name" in item for item in node):
                    header_lists.append(node)  # plausible RFC-style header list
            for item in node:
                _walk(item, depth + 1)
            return
        if isinstance(node, dict):
            for value in node.values():
                _walk(value, depth + 1)

    _walk(payload)

    for raw_headers in header_lists:
        for entry in raw_headers:
            name = str(entry.get("name") or "").strip().lower()
            value = str(entry.get("value") or "").strip()
            if name and value and name not in headers_map:
                headers_map[name] = value
    return headers_map


def _coerce_email_recipient_header(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        parts: list[str] = []
        for item in value:
            text = _coerce_email_recipient_header(item)
            if text:
                parts.append(text)
        return ", ".join(parts)
    if isinstance(value, dict):
        email_addr = str(value.get("email") or value.get("address") or "").strip()
        name = str(value.get("name") or "").strip()
        if name and email_addr:
            return f"{name} <{email_addr}>"
        return email_addr or name
    return str(value).strip()


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for item in value:
            parts.extend(_coerce_string_list(item))
        return parts
    if isinstance(value, dict):
        text = _coerce_email_recipient_header(value)
        return [text] if text else []
    text = str(value).strip()
    return [text] if text else []


def _has_non_empty_payload_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _looks_like_gmail_compose_payload(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
        return False
    compose_keys = {
        "to",
        "cc",
        "bcc",
        "subject",
        "body",
        "text",
        "html",
        "from",
        "reply_to",
        "replyTo",
    }
    return any(key in payload for key in compose_keys)


def _extract_legacy_gmail_compose_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    compose_payload: Dict[str, Any] = {}
    header_map = _extract_gmail_headers_map(payload)
    header_field_map = {
        "to": "to",
        "cc": "cc",
        "bcc": "bcc",
        "subject": "subject",
        "from": "from",
        "reply-to": "reply_to",
    }
    for header_name, target_field in header_field_map.items():
        header_value = header_map.get(header_name)
        if header_value and target_field not in compose_payload:
            compose_payload[target_field] = header_value

    seen_nodes: set[int] = set()
    pending_nodes: list[Dict[str, Any]] = [payload]
    compose_fields = (
        "to",
        "cc",
        "bcc",
        "subject",
        "body",
        "text",
        "html",
        "from",
        "reply_to",
        "replyTo",
        "recipient",
    )
    while pending_nodes:
        node = pending_nodes.pop(0)
        node_id = id(node)
        if node_id in seen_nodes:
            continue
        seen_nodes.add(node_id)

        thread_id = str(node.get("threadId") or "").strip()
        if thread_id and "threadId" not in compose_payload:
            compose_payload["threadId"] = thread_id

        for field in compose_fields:
            if field in compose_payload:
                continue
            value = node.get(field)
            if _has_non_empty_payload_value(value):
                compose_payload[field] = value

        body_obj = node.get("body")
        if isinstance(body_obj, dict) and "text" not in compose_payload and "body" not in compose_payload:
            body_data = body_obj.get("data")
            if isinstance(body_data, str) and body_data.strip():
                compose_payload["text"] = body_data.strip()

        for child_key in ("draft", "message", "payload"):
            child_node = node.get(child_key)
            if isinstance(child_node, dict):
                pending_nodes.append(child_node)

    content_fields = ("to", "cc", "bcc", "subject", "body", "text", "html", "from", "reply_to", "replyTo", "recipient")
    if not any(_has_non_empty_payload_value(compose_payload.get(field)) for field in content_fields):
        return None
    return compose_payload


def _build_gmail_raw_message(payload: Dict[str, Any]) -> str:
    message = EmailMessage(policy=SMTP)

    from_value = _coerce_email_recipient_header(payload.get("from"))
    to_value = _coerce_email_recipient_header(payload.get("to") or payload.get("recipient"))
    cc_value = _coerce_email_recipient_header(payload.get("cc"))
    bcc_value = _coerce_email_recipient_header(payload.get("bcc"))
    reply_to_value = _coerce_email_recipient_header(payload.get("replyTo") or payload.get("reply_to"))
    subject_value = str(payload.get("subject") or "").strip()

    if from_value:
        message["From"] = from_value
    if to_value:
        message["To"] = to_value
    if cc_value:
        message["Cc"] = cc_value
    if bcc_value:
        message["Bcc"] = bcc_value
    if reply_to_value:
        message["Reply-To"] = reply_to_value
    if subject_value:
        message["Subject"] = subject_value

    text_body = str(payload.get("text") or payload.get("body") or "").strip()
    html_body = str(payload.get("html") or "").strip()

    if html_body and text_body:
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")
    elif html_body:
        message.set_content(" ")
        message.add_alternative(html_body, subtype="html")
    else:
        message.set_content(text_body or "")

    raw_bytes = message.as_bytes()
    return base64.urlsafe_b64encode(raw_bytes).decode("utf-8").rstrip("=")


def _normalize_gmail_write_payload(
    service: str,
    resource_segments: Sequence[str],
    action_segments: Sequence[str],
    json_payload: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(json_payload, dict):
        return json_payload
    if str(service or "").strip().lower() != "gmail":
        return json_payload
    if not action_segments:
        return json_payload

    action = str(action_segments[0] or "").strip().lower()
    if action not in {"create", "send", "insert", "import"}:
        return json_payload

    resource_tail = str(resource_segments[-1] or "").strip().lower() if resource_segments else ""
    payload = dict(json_payload)

    # Some agents wrap draft payloads as {"draft":{"message":{"raw":"..."}}}.
    if resource_tail == "drafts" and action == "create":
        draft_obj = payload.get("draft")
        if isinstance(draft_obj, dict):
            nested_message = draft_obj.get("message")
            if isinstance(nested_message, dict) and str(nested_message.get("raw") or "").strip():
                return {"message": nested_message}

    # For message send/insert/import, unwrap {"message": {...}} if provided.
    if resource_tail == "messages" and isinstance(payload.get("message"), dict):
        if "raw" in payload.get("message", {}):
            payload = dict(payload["message"])

    thread_id = str(payload.get("threadId") or "").strip() or None

    # Already valid raw payload shape.
    if resource_tail == "drafts" and action == "create":
        message_obj = payload.get("message")
        if isinstance(message_obj, dict) and str(message_obj.get("raw") or "").strip():
            return payload
    elif str(payload.get("raw") or "").strip():
        return payload

    compose_payload: Optional[Dict[str, Any]]
    if _looks_like_gmail_compose_payload(payload):
        compose_payload = payload
    else:
        compose_payload = _extract_legacy_gmail_compose_payload(payload)
    if not compose_payload:
        return payload

    thread_id = str(compose_payload.get("threadId") or payload.get("threadId") or "").strip() or None
    raw_value = _build_gmail_raw_message(compose_payload)
    if resource_tail == "drafts" and action == "create":
        message_obj: Dict[str, Any] = {"raw": raw_value}
        if thread_id:
            message_obj["threadId"] = thread_id
        return {"message": message_obj}

    normalized: Dict[str, Any] = {"raw": raw_value}
    if thread_id:
        normalized["threadId"] = thread_id
    return normalized


async def _fetch_gmail_message_summaries(
    message_ids: Sequence[str],
    *,
    cwd: Path,
    env_overrides: Dict[str, str],
    timeout_seconds: float,
) -> list[Dict[str, Any]]:
    if not message_ids:
        return []
    per_call_timeout = max(5.0, min(12.0, timeout_seconds / 3.0))
    headers_request = ["From", "Subject", "Date", "Sender", "Reply-To", "Return-Path"]

    async def _fetch_message_payload(message_id: str, *, format_value: str) -> Optional[Dict[str, Any]]:
        params = {
            "userId": "me",
            "id": str(message_id),
            "format": format_value,
        }
        if format_value == "metadata":
            params["metadataHeaders"] = headers_request
        command = [
            "gws",
            "gmail",
            "users",
            "messages",
            "get",
            "--params",
            json.dumps(params, separators=(",", ":"), ensure_ascii=False),
        ]
        result = await _run_gws_command(
            command,
            timeout_seconds=per_call_timeout,
            cwd=cwd,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            return None
        payload = result.get("parsed_json")
        if not isinstance(payload, dict):
            parsed = _parse_json_if_possible(str(result.get("stdout", "")))
            payload = parsed if isinstance(parsed, dict) else {}
        return payload if payload else None

    async def _fetch_one(message_id: str) -> Optional[Dict[str, Any]]:
        payload = await _fetch_message_payload(message_id, format_value="metadata")
        if not payload:
            return None

        headers_map = _extract_gmail_headers_map(payload)
        from_value = (
            headers_map.get("from")
            or headers_map.get("sender")
            or headers_map.get("reply-to")
            or headers_map.get("return-path")
            or ""
        )
        subject_value = headers_map.get("subject") or ""

        # Some responses omit metadata headers; retry with full format.
        if not from_value and not subject_value:
            full_payload = await _fetch_message_payload(message_id, format_value="full")
            if full_payload:
                payload = full_payload
                headers_map = _extract_gmail_headers_map(payload)
                from_value = (
                    headers_map.get("from")
                    or headers_map.get("sender")
                    or headers_map.get("reply-to")
                    or headers_map.get("return-path")
                    or ""
                )
                subject_value = headers_map.get("subject") or ""

        summary: Dict[str, Any] = {
            "id": str(payload.get("id") or message_id),
        }
        thread_id = str(payload.get("threadId") or "").strip()
        if thread_id:
            summary["threadId"] = thread_id
        if from_value:
            summary["from"] = from_value
        if subject_value:
            summary["subject"] = subject_value
        date_value = headers_map.get("date") or ""
        if date_value:
            summary["date"] = date_value
        snippet_value = str(payload.get("snippet") or "").strip()
        if snippet_value:
            summary["snippet"] = snippet_value
        labels = payload.get("labelIds")
        if isinstance(labels, list):
            clean_labels = [str(item).strip() for item in labels if str(item).strip()]
            if clean_labels:
                summary["labelIds"] = clean_labels
        return summary

    tasks = [_fetch_one(message_id) for message_id in message_ids]
    fetched = await asyncio.gather(*tasks, return_exceptions=True)
    summaries: list[Dict[str, Any]] = []
    for item in fetched:
        if isinstance(item, Exception) or item is None:
            continue
        summaries.append(item)
    return summaries


def _extract_help_commands(help_text: str) -> list[Dict[str, str]]:
    lines = str(help_text or "").splitlines()
    commands: list[Dict[str, str]] = []
    seen: set[str] = set()
    in_commands_section = False

    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if lowered in {"commands:", "available commands:"}:
            in_commands_section = True
            continue

        if in_commands_section and lowered in {
            "options:",
            "flags:",
            "arguments:",
            "examples:",
            "global options:",
            "global flags:",
        }:
            break

        if not in_commands_section:
            continue
        if not stripped:
            continue

        match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]{0,63})\s{2,}(.+?)\s*$", line)
        if not match:
            continue

        name = match.group(1)
        if name in seen:
            continue
        seen.add(name)
        commands.append({"name": name, "description": match.group(2)})

    return commands


def _extract_calendar_datetime_value(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        for key in ("dateTime", "date", "value"):
            text = str(value.get(key) or "").strip()
            if text:
                return text
        return None
    text = str(value or "").strip()
    return text or None


def _looks_like_calendar_event(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if "start" in payload or "end" in payload:
        return True
    event_hint_keys = {"summary", "htmlLink", "status", "attendees", "organizer"}
    return "id" in payload and any(key in payload for key in event_hint_keys)


def _extract_calendar_event_summaries(payload: Any, *, max_items: int = 100) -> list[Dict[str, Any]]:
    summaries: list[Dict[str, Any]] = []
    seen: set[str] = set()

    def _walk(node: Any, context: Dict[str, str], depth: int = 0) -> None:
        if depth > 8 or len(summaries) >= max_items:
            return

        if isinstance(node, list):
            for item in node:
                _walk(item, context, depth + 1)
            return

        if not isinstance(node, dict):
            return

        next_context = dict(context)
        calendar_id = str(node.get("calendarId") or node.get("calendar_id") or "").strip()
        if calendar_id:
            next_context["calendar_id"] = calendar_id
        calendar_name = str(
            node.get("calendarSummary")
            or node.get("calendarName")
            or node.get("calendar")
            or node.get("calendar_summary")
            or ""
        ).strip()
        if calendar_name:
            next_context["calendar_name"] = calendar_name

        if _looks_like_calendar_event(node):
            event_id = str(node.get("id") or node.get("eventId") or "").strip()
            start_value = _extract_calendar_datetime_value(node.get("start"))
            end_value = _extract_calendar_datetime_value(node.get("end"))
            summary = str(node.get("summary") or node.get("title") or "").strip()
            dedupe_key = event_id or f"{summary}|{start_value}|{end_value}"
            if dedupe_key and dedupe_key not in seen:
                seen.add(dedupe_key)
                item: Dict[str, Any] = {
                    "id": event_id or None,
                    "summary": summary or None,
                    "status": str(node.get("status") or "").strip() or None,
                    "start": start_value,
                    "end": end_value,
                    "location": str(node.get("location") or "").strip() or None,
                    "html_link": str(node.get("htmlLink") or "").strip() or None,
                }
                if next_context.get("calendar_id"):
                    item["calendar_id"] = next_context["calendar_id"]
                if next_context.get("calendar_name"):
                    item["calendar_name"] = next_context["calendar_name"]
                summaries.append(item)

        for value in node.values():
            _walk(value, next_context, depth + 1)

    _walk(payload, {})
    return summaries


def _validate_allowed_action(action_segments: Sequence[str]) -> None:
    for action in action_segments:
        normalized = re.sub(r"[^a-z]", "", str(action).lower())
        if any(normalized.startswith(prefix) for prefix in _BLOCKED_ACTION_PREFIXES):
            raise SkillValidationError(
                "Destructive actions are blocked in this skill version. "
                "Allowed examples include list/get/search/read/create."
            )


async def _run_gws_command(
    args: Sequence[str],
    *,
    timeout_seconds: float,
    cwd: Optional[Path] = None,
    env_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    command = [str(part) for part in args if str(part).strip()]
    if not command:
        raise SkillValidationError("No gws command was provided.")

    cwd_path: Optional[Path] = None
    if cwd is not None:
        cwd_path = Path(cwd).resolve()
        cwd_path.mkdir(parents=True, exist_ok=True)

    command[0] = _resolve_gws_executable(command[0], cwd_path)

    env: Optional[Dict[str, str]] = None
    if env_overrides:
        env = os.environ.copy()
        for key, value in env_overrides.items():
            if not key:
                continue
            value_text = str(value).strip()
            if value_text:
                env[str(key)] = value_text

    loop = asyncio.get_running_loop()
    started = loop.time()

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd_path) if cwd_path is not None else None,
            env=env,
        )
    except FileNotFoundError as exc:
        raise SkillValidationError(
            "Google Workspace CLI `gws` is not installed or is not on PATH. "
            "Install with: npm install -g @googleworkspace/cli"
        ) from exc

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise RuntimeError(f"gws command timed out after {int(timeout_seconds)} seconds.") from exc

    duration_ms = int((loop.time() - started) * 1000)
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    stdout, stdout_truncated = _truncate_text(stdout)
    stderr, stderr_truncated = _truncate_text(stderr)

    result: Dict[str, Any] = {
        "command": command,
        "returncode": int(process.returncode or 0),
        "duration_ms": duration_ms,
        "stdout": stdout,
        "stderr": stderr,
    }
    if stdout_truncated or stderr_truncated:
        result["truncated_output"] = True

    parsed_json = _parse_json_if_possible(stdout)
    if parsed_json is not None:
        result["parsed_json"] = parsed_json
    return result


class CheckCliTool(BaseTool):
    name = "check_cli"
    description = "Verify that Google Workspace CLI (gws) is installed and report version output."
    input_schema = {
        "type": "object",
        "properties": {
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": 20,
                "description": "Timeout for the gws command execution.",
            }
        },
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"), default=20.0)
        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            ["gws", "--version"],
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws --version failed: {_extract_primary_error(result)}")

        version_line = next(
            (line.strip() for line in str(result.get("stdout", "")).splitlines() if line.strip()),
            "",
        )
        return {
            "available": True,
            "version": version_line or None,
            "response": result,
        }


class CheckAuthTool(BaseTool):
    name = "check_auth"
    description = "Run `gws auth status` and return authentication status output."
    input_schema = {
        "type": "object",
        "properties": {
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": 30,
                "description": "Timeout for the gws command execution.",
            }
        },
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"), default=30.0)
        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            ["gws", "auth", "status"],
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(
                "gws auth status failed. Run `gws auth setup` and `gws auth login` first. "
                f"Details: {_extract_primary_error(result)}"
            )

        status_payload = result.get("parsed_json")
        if not isinstance(status_payload, dict):
            parsed = _parse_json_if_possible(str(result.get("stdout", "")))
            status_payload = parsed if isinstance(parsed, dict) else {}

        credential_source = str(status_payload.get("credential_source", "")).strip().lower()
        auth_method = str(status_payload.get("auth_method", "")).strip().lower()
        has_any_credentials = bool(status_payload.get("has_refresh_token")) or bool(
            status_payload.get("encrypted_credentials_exists")
        ) or bool(status_payload.get("plain_credentials_exists"))
        is_authenticated = has_any_credentials or credential_source not in {"", "none"} or auth_method not in {"", "none"}

        if not is_authenticated:
            raise RuntimeError(
                "gws auth status reported no active credentials. "
                "Run `gws auth login` in the same environment used by CATBot, or set "
                "`GOOGLE_WORKSPACE_CLI_CONFIG_DIR` to your authenticated gws config directory."
            )

        return {
            "authenticated": is_authenticated,
            "auth_status": status_payload or None,
            "response": result,
        }


class GmailListUnreadTool(BaseTool):
    name = "gmail_list_unread"
    description = (
        "List unread inbox emails with human-friendly sender/subject/date/snippet summaries. "
        "Preferred tool for requests like 'show unread emails'."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 25,
                "default": 10,
                "description": "Number of unread messages to fetch.",
            },
            "query": {
                "type": "string",
                "description": (
                    "Optional extra Gmail query terms appended to `in:inbox is:unread` "
                    "(for example: `from:billing@example.com`)."
                ),
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": _DEFAULT_TIMEOUT_SECONDS,
                "description": "Timeout for gws command execution.",
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        try:
            max_results = int(arguments.get("max_results", 10))
        except (TypeError, ValueError):
            max_results = 10
        max_results = max(1, min(max_results, 25))
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))
        extra_query = str(arguments.get("query") or "").strip()
        query = "in:inbox is:unread"
        if extra_query:
            query = f"{query} {extra_query}"

        params = {"userId": "me", "q": query, "maxResults": max_results}
        command = [
            "gws",
            "gmail",
            "users",
            "messages",
            "list",
            "--params",
            json.dumps(params, separators=(",", ":"), ensure_ascii=False),
        ]
        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            command,
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws command failed: {_extract_primary_error(result)}")

        gmail_message_summaries: list[Dict[str, Any]] = []
        parsed_payload = result.get("parsed_json")
        if isinstance(parsed_payload, dict):
            message_ids = _extract_gmail_message_ids(parsed_payload, max_items=max_results)
            if message_ids:
                try:
                    gmail_message_summaries = await _fetch_gmail_message_summaries(
                        message_ids,
                        cwd=working_dir,
                        env_overrides=env_overrides,
                        timeout_seconds=timeout_seconds,
                    )
                except Exception:
                    gmail_message_summaries = []

        payload: Dict[str, Any] = {
            "query": query,
            "max_results": max_results,
            "response": result,
        }
        if gmail_message_summaries:
            payload["gmail_message_summaries"] = gmail_message_summaries
        return payload


class GmailGetMessageTool(BaseTool):
    name = "gmail_get_message"
    description = (
        "Fetch a single Gmail message by ID. "
        "Use this for requests like 'show full content of email ID ...'."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "message_id": {
                "type": "string",
                "description": "Gmail message ID.",
            },
            "format": {
                "type": "string",
                "enum": ["full", "metadata", "minimal", "raw"],
                "default": "full",
                "description": "Gmail messages.get format. Defaults to full.",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": _DEFAULT_TIMEOUT_SECONDS,
                "description": "Timeout for gws command execution.",
            },
        },
        "required": ["message_id"],
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        message_id = str(arguments.get("message_id") or "").strip()
        if not message_id:
            raise SkillValidationError("'message_id' is required.")
        format_value = str(arguments.get("format") or "full").strip().lower() or "full"
        if format_value not in {"full", "metadata", "minimal", "raw"}:
            raise SkillValidationError("'format' must be one of: full, metadata, minimal, raw.")
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))

        params: Dict[str, Any] = {"userId": "me", "id": message_id, "format": format_value}
        if format_value == "metadata":
            params["metadataHeaders"] = ["From", "To", "Subject", "Date", "Cc", "Bcc", "Reply-To", "Sender", "Return-Path"]
        command = [
            "gws",
            "gmail",
            "users",
            "messages",
            "get",
            "--params",
            json.dumps(params, separators=(",", ":"), ensure_ascii=False),
        ]
        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            command,
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws command failed: {_extract_primary_error(result)}")
        return {
            "message_id": message_id,
            "format": format_value,
            "response": result,
        }


class GmailComposeDraftTool(BaseTool):
    name = "gmail_compose_draft"
    description = (
        "Create a Gmail draft from explicit fields (to, subject, body_text). "
        "Preferred tool for composing drafts."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "to": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ],
                "description": "Primary recipient(s).",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line.",
            },
            "body_text": {
                "type": "string",
                "description": "Plain-text body content.",
            },
            "cc": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ],
                "description": "Optional CC recipient(s).",
            },
            "bcc": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ],
                "description": "Optional BCC recipient(s).",
            },
            "from": {
                "type": "string",
                "description": "Optional From header override (if account permits).",
            },
            "reply_to": {
                "type": "string",
                "description": "Optional Reply-To header.",
            },
            "thread_id": {
                "type": "string",
                "description": "Optional thread ID to attach this draft to an existing thread.",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": _DEFAULT_TIMEOUT_SECONDS,
                "description": "Timeout for gws command execution.",
            },
        },
        "required": ["to", "body_text"],
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        to_value = _coerce_email_recipient_header(arguments.get("to"))
        if not to_value:
            raise SkillValidationError("'to' is required.")
        body_text = str(arguments.get("body_text") or "").strip()
        if not body_text:
            raise SkillValidationError("'body_text' is required.")
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))

        compose_payload: Dict[str, Any] = {
            "to": arguments.get("to"),
            "subject": str(arguments.get("subject") or "").strip(),
            "text": body_text,
            "cc": arguments.get("cc"),
            "bcc": arguments.get("bcc"),
            "from": arguments.get("from"),
            "reply_to": arguments.get("reply_to"),
        }
        thread_id = str(arguments.get("thread_id") or "").strip()
        if thread_id:
            compose_payload["threadId"] = thread_id

        raw_value = _build_gmail_raw_message(compose_payload)
        message_obj: Dict[str, Any] = {"raw": raw_value}
        if thread_id:
            message_obj["threadId"] = thread_id

        params = {"userId": "me"}
        command = [
            "gws",
            "gmail",
            "users",
            "drafts",
            "create",
            "--params",
            json.dumps(params, separators=(",", ":"), ensure_ascii=False),
            "--json",
            json.dumps({"message": message_obj}, separators=(",", ":"), ensure_ascii=False),
        ]
        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            command,
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws command failed: {_extract_primary_error(result)}")
        return {
            "response": result,
        }


class GmailSendMessageTool(BaseTool):
    name = "gmail_send_message"
    description = (
        "Send a Gmail message immediately from explicit fields (to, subject, body_text). "
        "Preferred tool for sending composed messages."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "to": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ],
                "description": "Primary recipient(s).",
            },
            "subject": {
                "type": "string",
                "description": "Email subject line.",
            },
            "body_text": {
                "type": "string",
                "description": "Plain-text body content.",
            },
            "cc": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ],
                "description": "Optional CC recipient(s).",
            },
            "bcc": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ],
                "description": "Optional BCC recipient(s).",
            },
            "from": {
                "type": "string",
                "description": "Optional From header override (if account permits).",
            },
            "reply_to": {
                "type": "string",
                "description": "Optional Reply-To header.",
            },
            "thread_id": {
                "type": "string",
                "description": "Optional thread ID to attach the sent message to an existing thread.",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": _DEFAULT_TIMEOUT_SECONDS,
                "description": "Timeout for gws command execution.",
            },
        },
        "required": ["to", "body_text"],
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        to_value = _coerce_email_recipient_header(arguments.get("to"))
        if not to_value:
            raise SkillValidationError("'to' is required.")
        body_text = str(arguments.get("body_text") or "").strip()
        if not body_text:
            raise SkillValidationError("'body_text' is required.")
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))

        compose_payload: Dict[str, Any] = {
            "to": arguments.get("to"),
            "subject": str(arguments.get("subject") or "").strip(),
            "text": body_text,
            "cc": arguments.get("cc"),
            "bcc": arguments.get("bcc"),
            "from": arguments.get("from"),
            "reply_to": arguments.get("reply_to"),
        }
        thread_id = str(arguments.get("thread_id") or "").strip()
        if thread_id:
            compose_payload["threadId"] = thread_id

        raw_value = _build_gmail_raw_message(compose_payload)
        json_payload: Dict[str, Any] = {"raw": raw_value}
        if thread_id:
            json_payload["threadId"] = thread_id

        params = {"userId": "me"}
        command = [
            "gws",
            "gmail",
            "users",
            "messages",
            "send",
            "--params",
            json.dumps(params, separators=(",", ":"), ensure_ascii=False),
            "--json",
            json.dumps(json_payload, separators=(",", ":"), ensure_ascii=False),
        ]
        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            command,
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws command failed: {_extract_primary_error(result)}")
        return {
            "response": result,
        }


class GmailMarkReadTool(BaseTool):
    name = "gmail_mark_read"
    description = "Mark a Gmail message as read by removing the UNREAD label from a specific message ID."
    input_schema = {
        "type": "object",
        "properties": {
            "message_id": {
                "type": "string",
                "description": "Gmail message ID to mark as read.",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": _DEFAULT_TIMEOUT_SECONDS,
                "description": "Timeout for gws command execution.",
            },
        },
        "required": ["message_id"],
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        message_id = str(arguments.get("message_id") or "").strip()
        if not message_id:
            raise SkillValidationError("'message_id' is required.")
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))

        params = {"userId": "me", "id": message_id}
        json_payload = {"removeLabelIds": ["UNREAD"]}
        command = [
            "gws",
            "gmail",
            "users",
            "messages",
            "modify",
            "--params",
            json.dumps(params, separators=(",", ":"), ensure_ascii=False),
            "--json",
            json.dumps(json_payload, separators=(",", ":"), ensure_ascii=False),
        ]
        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            command,
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws command failed: {_extract_primary_error(result)}")
        return {
            "message_id": message_id,
            "response": result,
        }


class CalendarCreateEventTool(BaseTool):
    name = "calendar_create_event"
    description = (
        "Create a Google Calendar event from explicit fields like summary, start time, end time, "
        "location, description, and attendees."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Event title.",
            },
            "start_time": {
                "type": "string",
                "description": "RFC3339/ISO 8601 start timestamp, for example 2026-03-12T09:00:00+11:00.",
            },
            "end_time": {
                "type": "string",
                "description": "RFC3339/ISO 8601 end timestamp.",
            },
            "calendar_id": {
                "type": "string",
                "default": "primary",
                "description": "Calendar ID to create the event on. Defaults to primary.",
            },
            "location": {
                "type": "string",
                "description": "Optional event location.",
            },
            "description": {
                "type": "string",
                "description": "Optional event description/body.",
            },
            "attendees": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "array", "items": {"type": "string"}},
                ],
                "description": "Optional attendee email or list of attendee emails.",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": _DEFAULT_TIMEOUT_SECONDS,
                "description": "Timeout for gws command execution.",
            },
        },
        "required": ["summary", "start_time", "end_time"],
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        summary = str(arguments.get("summary") or "").strip()
        start_time = str(arguments.get("start_time") or "").strip()
        end_time = str(arguments.get("end_time") or "").strip()
        if not summary:
            raise SkillValidationError("'summary' is required.")
        if not start_time:
            raise SkillValidationError("'start_time' is required.")
        if not end_time:
            raise SkillValidationError("'end_time' is required.")

        calendar_id = str(arguments.get("calendar_id") or "primary").strip() or "primary"
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))
        attendees = _coerce_string_list(arguments.get("attendees"))

        command = [
            "gws",
            "calendar",
            "+insert",
            "--calendar",
            calendar_id,
            "--summary",
            summary,
            "--start",
            start_time,
            "--end",
            end_time,
        ]
        location = str(arguments.get("location") or "").strip()
        if location:
            command.extend(["--location", location])
        description = str(arguments.get("description") or "").strip()
        if description:
            command.extend(["--description", description])
        for attendee in attendees:
            command.extend(["--attendee", attendee])

        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            command,
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws command failed: {_extract_primary_error(result)}")
        return {
            "calendar_id": calendar_id,
            "summary": summary,
            "start_time": start_time,
            "end_time": end_time,
            "response": result,
        }


class CalendarCancelEventTool(BaseTool):
    name = "calendar_cancel_event"
    description = "Cancel/delete a Google Calendar event by event ID."
    input_schema = {
        "type": "object",
        "properties": {
            "event_id": {
                "type": "string",
                "description": "Google Calendar event ID to cancel.",
            },
            "calendar_id": {
                "type": "string",
                "default": "primary",
                "description": "Calendar ID containing the event. Defaults to primary.",
            },
            "send_updates": {
                "type": "string",
                "enum": ["all", "externalOnly", "none"],
                "description": "Optional Google Calendar sendUpdates mode.",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": _DEFAULT_TIMEOUT_SECONDS,
                "description": "Timeout for gws command execution.",
            },
        },
        "required": ["event_id"],
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        event_id = str(arguments.get("event_id") or "").strip()
        if not event_id:
            raise SkillValidationError("'event_id' is required.")

        calendar_id = str(arguments.get("calendar_id") or "primary").strip() or "primary"
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))
        params: Dict[str, Any] = {"calendarId": calendar_id, "eventId": event_id}
        send_updates = str(arguments.get("send_updates") or "").strip()
        if send_updates:
            params["sendUpdates"] = send_updates

        command = [
            "gws",
            "calendar",
            "events",
            "delete",
            "--params",
            json.dumps(params, separators=(",", ":"), ensure_ascii=False),
        ]

        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            command,
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws command failed: {_extract_primary_error(result)}")
        return {
            "calendar_id": calendar_id,
            "event_id": event_id,
            "response": result,
        }


class CalendarListTodayTool(BaseTool):
    name = "calendar_list_today"
    description = "Show today's Google Calendar events, optionally filtered to a specific calendar name or ID."
    input_schema = {
        "type": "object",
        "properties": {
            "calendar": {
                "type": "string",
                "description": "Optional calendar name or ID filter.",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": _DEFAULT_TIMEOUT_SECONDS,
                "description": "Timeout for gws command execution.",
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))
        calendar = str(arguments.get("calendar") or "").strip()

        command = ["gws", "calendar", "+agenda", "--today"]
        if calendar:
            command.extend(["--calendar", calendar])

        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            command,
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws command failed: {_extract_primary_error(result)}")

        payload: Dict[str, Any] = {
            "scope": "today",
            "calendar": calendar or None,
            "response": result,
        }
        event_summaries = _extract_calendar_event_summaries(result.get("parsed_json"))
        if event_summaries:
            payload["calendar_event_summaries"] = event_summaries
        return payload


class CalendarListWeekTool(BaseTool):
    name = "calendar_list_week"
    description = "Show this week's Google Calendar events, optionally filtered to a specific calendar name or ID."
    input_schema = {
        "type": "object",
        "properties": {
            "calendar": {
                "type": "string",
                "description": "Optional calendar name or ID filter.",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": _DEFAULT_TIMEOUT_SECONDS,
                "description": "Timeout for gws command execution.",
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))
        calendar = str(arguments.get("calendar") or "").strip()

        command = ["gws", "calendar", "+agenda", "--week"]
        if calendar:
            command.extend(["--calendar", calendar])

        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            command,
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws command failed: {_extract_primary_error(result)}")

        payload: Dict[str, Any] = {
            "scope": "week",
            "calendar": calendar or None,
            "response": result,
        }
        event_summaries = _extract_calendar_event_summaries(result.get("parsed_json"))
        if event_summaries:
            payload["calendar_event_summaries"] = event_summaries
        return payload


class RunReadonlyCommandTool(BaseTool):
    name = "run_readonly_command"
    description = (
        "Advanced fallback: execute a non-destructive gws command as "
        "`gws <service> [resource path] <action path> [--params JSON] [--json JSON] [--dry-run]`."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "gws service name (for example: drive, gmail, calendar).",
            },
            "resource": {
                "type": "string",
                "description": (
                    "Optional gws resource path (for example: files or users/messages). "
                    "Nested paths can use spaces, slash, or dot separators."
                ),
            },
            "action": {
                "type": "string",
                "description": (
                    "Non-destructive action path (for example: list, get, search, read, create, +triage). "
                    "Multiple segments can be separated by spaces, slash, or dot."
                ),
            },
            "params": {
                "type": "object",
                "description": "Optional object passed to gws via --params as JSON.",
                "additionalProperties": True,
            },
            "json_payload": {
                "type": "object",
                "description": "Optional object passed to gws via --json.",
                "additionalProperties": True,
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "Append --dry-run to preview request execution.",
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": _DEFAULT_TIMEOUT_SECONDS,
                "description": "Timeout for the gws command execution.",
            },
        },
        "required": ["service", "action"],
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        service_segments = _parse_command_segments(arguments.get("service"), key="service")
        if len(service_segments) != 1:
            raise SkillValidationError("'service' must be a single command token.")
        service = service_segments[0]

        resource_segments = _parse_command_segments(
            arguments.get("resource"),
            key="resource",
            allow_empty=True,
            split_dots=True,
        )
        action_segments = _parse_command_segments(
            arguments.get("action"),
            key="action",
            split_dots=True,
        )
        normalized_resource_segments, action_segments = _normalize_gmail_command_shape(
            service,
            resource_segments,
            action_segments,
        )
        _validate_allowed_action(action_segments)

        params = arguments.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise SkillValidationError("'params' must be an object when provided.")
        params = _ensure_gmail_user_id_param(service, normalized_resource_segments, params)
        params = _ensure_gmail_list_limit(service, action_segments, params)
        params = _ensure_gmail_message_get_format(
            service,
            normalized_resource_segments,
            action_segments,
            params,
        )

        json_payload = arguments.get("json_payload")
        if json_payload is not None and not isinstance(json_payload, dict):
            raise SkillValidationError("'json_payload' must be an object when provided.")
        json_payload = _normalize_gmail_write_payload(
            service,
            normalized_resource_segments,
            action_segments,
            json_payload,
        )

        dry_run = _coerce_bool(arguments.get("dry_run"), default=False)
        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"))

        command = ["gws", service, *normalized_resource_segments, *action_segments]
        if params:
            command.extend(
                [
                    "--params",
                    json.dumps(params, separators=(",", ":"), ensure_ascii=False),
                ]
            )
        if json_payload is not None:
            command.extend(
                [
                    "--json",
                    json.dumps(json_payload, separators=(",", ":"), ensure_ascii=False),
                ]
            )
        if dry_run:
            command.append("--dry-run")

        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            command,
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws command failed: {_extract_primary_error(result)}")

        gmail_message_summaries: list[Dict[str, Any]] = []
        parsed_payload = result.get("parsed_json")
        if (
            _is_gmail_messages_list_request(service, normalized_resource_segments, action_segments)
            and isinstance(parsed_payload, dict)
        ):
            message_ids = _extract_gmail_message_ids(parsed_payload, max_items=3)
            if message_ids:
                try:
                    gmail_message_summaries = await _fetch_gmail_message_summaries(
                        message_ids,
                        cwd=working_dir,
                        env_overrides=env_overrides,
                        timeout_seconds=timeout_seconds,
                    )
                except Exception:
                    gmail_message_summaries = []

        response_payload = {
            "service": service,
            "resource": " ".join(normalized_resource_segments) if normalized_resource_segments else None,
            "resource_segments": normalized_resource_segments,
            "action": " ".join(action_segments),
            "action_segments": action_segments,
            "dry_run": dry_run,
            "response": result,
        }
        if gmail_message_summaries:
            response_payload["gmail_message_summaries"] = gmail_message_summaries
        return response_payload


class ListAvailableCommandsTool(BaseTool):
    name = "list_available_commands"
    description = (
        "Discover available gws subcommands from help output. "
        "Use with no args for top-level commands, or pass service/resource for scoped help."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Optional gws service scope (for example: drive).",
            },
            "resource": {
                "type": "string",
                "description": (
                    "Optional gws resource scope (for example: files or users/messages). "
                    "Requires service."
                ),
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 5,
                "maximum": _MAX_TIMEOUT_SECONDS,
                "default": 20,
                "description": "Timeout for the gws help command execution.",
            },
            "include_raw_output": {
                "type": "boolean",
                "default": False,
                "description": "Include full raw command output when true.",
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        service_raw = arguments.get("service")
        resource_raw = arguments.get("resource")
        service = str(service_raw or "").strip()
        resource = str(resource_raw or "").strip()
        service_segments = _parse_command_segments(service, key="service", allow_empty=True)
        if len(service_segments) > 1:
            raise SkillValidationError("'service' must be a single command token.")
        service_token = service_segments[0] if service_segments else ""
        resource_segments = _parse_command_segments(
            resource,
            key="resource",
            allow_empty=True,
            split_dots=True,
        )
        normalized_resource_segments = _normalize_gmail_resource_segments(service_token, resource_segments)

        if normalized_resource_segments and not service_token:
            raise SkillValidationError("'service' is required when 'resource' is provided.")

        timeout_seconds = _coerce_timeout_seconds(arguments.get("timeout_seconds"), default=20.0)
        include_raw_output = _coerce_bool(arguments.get("include_raw_output"), default=False)

        command = ["gws"]
        if service_token:
            command.append(service_token)
        if normalized_resource_segments:
            command.extend(normalized_resource_segments)
        command.append("--help")

        working_dir = (context.scratch_dir or self.default_root_dir).resolve()
        env_overrides = _build_gws_env_overrides(working_dir)
        result = await _run_gws_command(
            command,
            timeout_seconds=timeout_seconds,
            cwd=working_dir,
            env_overrides=env_overrides,
        )
        if int(result.get("returncode", 1)) != 0:
            raise RuntimeError(f"gws help command failed: {_extract_primary_error(result)}")

        commands = _extract_help_commands(str(result.get("stdout", "")))
        names = [item["name"] for item in commands]
        scope = "root"
        if service_token and normalized_resource_segments:
            scope = f"{service_token}.{'.'.join(normalized_resource_segments)}"
        elif service_token:
            scope = service_token

        payload: Dict[str, Any] = {
            "scope": scope,
            "service": service_token or None,
            "resource": " ".join(normalized_resource_segments) if normalized_resource_segments else None,
            "resource_segments": normalized_resource_segments,
            "commands": commands,
            "command_names": names,
            "command_count": len(commands),
            "invoked_command": command,
        }
        if include_raw_output:
            payload["response"] = result
        return payload


class GoogleWorkspaceCliSkill(BaseSkill):
    name = "googleworkspace_cli"
    description = (
        "Google Workspace CLI wrappers with dedicated Gmail tools for common tasks "
        "(list unread, get message, compose draft, send, mark read), dedicated Calendar tools "
        "(create event, cancel event, list today, list week), plus an advanced generic command runner."
    )
    version = "1.1.0"
    tags = ["googleworkspace", "cli", "gws"]

    def __init__(self, root_dir: str = "./scratch") -> None:
        super().__init__()
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def create_tools(self) -> Sequence[BaseTool]:
        return [
            CheckCliTool(default_root_dir=self.root_dir),
            CheckAuthTool(default_root_dir=self.root_dir),
            GmailListUnreadTool(default_root_dir=self.root_dir),
            GmailGetMessageTool(default_root_dir=self.root_dir),
            GmailComposeDraftTool(default_root_dir=self.root_dir),
            GmailSendMessageTool(default_root_dir=self.root_dir),
            GmailMarkReadTool(default_root_dir=self.root_dir),
            CalendarCreateEventTool(default_root_dir=self.root_dir),
            CalendarCancelEventTool(default_root_dir=self.root_dir),
            CalendarListTodayTool(default_root_dir=self.root_dir),
            CalendarListWeekTool(default_root_dir=self.root_dir),
            ListAvailableCommandsTool(default_root_dir=self.root_dir),
            RunReadonlyCommandTool(default_root_dir=self.root_dir),
        ]


def create_skill(root_dir: str = "./scratch") -> BaseSkill:
    return GoogleWorkspaceCliSkill(root_dir=root_dir)

import json
import math
import os
import re
from typing import Any, Dict, List

DEFAULT_MAX_TOKEN_LIMIT = 256000
DEFAULT_CHARS_PER_TOKEN = 4


def _safe_int(value: str, fallback: int) -> int:
    try:
        parsed = int(value)
        return parsed
    except (TypeError, ValueError):
        return fallback


def get_max_token_limit() -> int:
    raw = os.getenv("MAX_TOKEN_LIMIT", "").strip()
    limit = _safe_int(raw, DEFAULT_MAX_TOKEN_LIMIT)
    return max(1000, limit)


def get_chars_per_token() -> int:
    raw = os.getenv("TOKEN_ESTIMATE_CHARS_PER_TOKEN", "").strip()
    value = _safe_int(raw, DEFAULT_CHARS_PER_TOKEN)
    return max(1, value)


def estimate_tokens_from_text(text: str) -> int:
    if not text:
        return 0
    chars_per_token = get_chars_per_token()
    return int(math.ceil(len(text) / chars_per_token))


def estimate_tokens_from_messages(messages: List[Dict[str, Any]]) -> int:
    total = 0
    for msg in messages:
        try:
            serialized = json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            serialized = str(msg)
        total += estimate_tokens_from_text(serialized)
        total += 4  # small per-message overhead
    return total


def is_context_limit_error(status_code: int, error_text: str) -> bool:
    if status_code not in {400, 413, 422}:
        return False
    text = (error_text or "").lower()
    patterns = (
        "context length",
        "maximum context",
        "context window",
        "too many tokens",
        "token limit",
        "max tokens",
        "context size",
    )
    return any(p in text for p in patterns)


def format_messages_for_summary(messages: List[Dict[str, Any]], max_chars: int = 40000) -> str:
    parts: List[str] = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content")
        if content is None:
            continue
        if isinstance(content, list):
            try:
                content_text = json.dumps(content, ensure_ascii=False)
            except (TypeError, ValueError):
                content_text = str(content)
        else:
            content_text = str(content)
        parts.append(f"{role.upper()}: {content_text}")
    joined = "\n".join(parts)
    if len(joined) > max_chars:
        joined = joined[-max_chars:]
    return joined

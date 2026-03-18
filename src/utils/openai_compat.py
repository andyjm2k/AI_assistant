from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


_THINK_BLOCK_PATTERN = re.compile(r"<think\b[^>]*>[\s\S]*?</think>", re.IGNORECASE)
_MINIMAX_MODEL_PATTERN = re.compile(r"\bminimax\b|^MiniMax-", re.IGNORECASE)


def strip_think_markup(content: Any) -> str:
    """Remove Minimax/Qwen-style reasoning tags from user-visible text."""
    if not isinstance(content, str):
        return ""
    cleaned = _THINK_BLOCK_PATTERN.sub(" ", content)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def coerce_message_text(content: Any) -> str:
    """Normalize OpenAI-compatible message content into plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    parts.append(text)
                continue
            if not isinstance(item, dict):
                continue
            candidate = item.get("text")
            if isinstance(candidate, dict):
                candidate = candidate.get("value") or candidate.get("content")
            if not isinstance(candidate, str):
                candidate = item.get("content") or item.get("output_text")
            if isinstance(candidate, str):
                text = candidate.strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()
    if isinstance(content, dict):
        candidate = content.get("text")
        if isinstance(candidate, dict):
            candidate = candidate.get("value") or candidate.get("content")
        if not isinstance(candidate, str):
            candidate = content.get("content") or content.get("output_text")
        if isinstance(candidate, str):
            return candidate.strip()
    return str(content).strip()


def is_minimax_api_base(api_base: Optional[str]) -> bool:
    if not api_base:
        return False
    try:
        hostname = (urlparse(str(api_base)).hostname or "").lower()
    except Exception:
        return False
    return hostname.endswith("minimax.io") or hostname.endswith("minimaxi.com")


def is_minimax_model(model: Optional[str]) -> bool:
    if not model:
        return False
    return bool(_MINIMAX_MODEL_PATTERN.search(str(model).strip()))


def is_minimax_chat_request(api_base: Optional[str], model: Optional[str]) -> bool:
    return is_minimax_api_base(api_base) or is_minimax_model(model)


def preferred_api_key_env_names(
    api_base: Optional[str],
    model: Optional[str],
    *,
    default_candidates: Optional[List[str]] = None,
) -> List[str]:
    candidates: List[str] = []
    if is_minimax_chat_request(api_base, model):
        candidates.extend(
            [
                "MINIMAX_API_KEY",
                "MCP_LLM_MINIMAX_API_KEY",
                "OPENAI_API_KEY",
                "MCP_LLM_OPENAI_API_KEY",
            ]
        )
    else:
        candidates.extend(default_candidates or ["OPENAI_API_KEY", "MCP_LLM_OPENAI_API_KEY"])
    return candidates


def normalize_temperature_for_minimax(temperature: Any) -> Any:
    try:
        parsed = float(temperature)
    except (TypeError, ValueError):
        return temperature
    if parsed <= 0:
        return 0.01
    if parsed > 1:
        return 1.0
    return parsed


def prepare_openai_compatible_chat_payload(
    payload: Dict[str, Any],
    *,
    api_base: Optional[str],
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Apply provider-specific OpenAI-compatible request fixes."""
    prepared = dict(payload)
    request_model = str(prepared.get("model") or model or "").strip()
    if not is_minimax_chat_request(api_base, request_model):
        return prepared

    if "temperature" in prepared:
        prepared["temperature"] = normalize_temperature_for_minimax(prepared.get("temperature"))

    extra_body = prepared.get("extra_body")
    if isinstance(extra_body, dict):
        extra_body = dict(extra_body)
    else:
        extra_body = {}
    extra_body.setdefault("reasoning_split", True)
    prepared["extra_body"] = extra_body
    return prepared


def build_assistant_history_message(
    message: Any,
    *,
    preserve_reasoning_details: bool,
) -> Dict[str, Any]:
    """Keep only safe assistant-message fields when reusing model output in history."""
    if not isinstance(message, dict):
        content = coerce_message_text(message)
        return {"role": "assistant", "content": content}

    history_message: Dict[str, Any] = {"role": str(message.get("role") or "assistant")}
    for key in ("content", "tool_calls", "name", "function_call", "refusal"):
        value = message.get(key)
        if value is not None:
            history_message[key] = value
    if preserve_reasoning_details and message.get("reasoning_details") is not None:
        history_message["reasoning_details"] = message.get("reasoning_details")
    return history_message


def normalize_chat_completion_message(
    message: Any,
    *,
    preserve_reasoning_details: bool,
) -> Dict[str, Any]:
    history_message = build_assistant_history_message(
        message,
        preserve_reasoning_details=preserve_reasoning_details,
    )
    tool_calls = history_message.get("tool_calls")
    if not isinstance(tool_calls, list):
        tool_calls = None
    raw_content = coerce_message_text(history_message.get("content"))
    return {
        "message": history_message,
        "raw_content": raw_content,
        "content": strip_think_markup(raw_content),
        "tool_calls": tool_calls,
    }

"""Built-in image generation skill backed by OpenRouter."""

from __future__ import annotations

import base64
import binascii
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import httpx

from src.skills.base import BaseSkill, BaseTool
from src.skills.exceptions import SkillValidationError
from src.skills.models import SkillContext

DEFAULT_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "bytedance-seed/seedream-4.5"


def _resolve_api_key() -> Optional[str]:
    return (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("openai_api_key")
        or os.getenv("MCP_LLM_OPENAI_API_KEY")
    )


def _resolve_output_dir(root_dir: Path, output_dir: str) -> Path:
    raw = (output_dir or "").strip()
    if not raw:
        raise SkillValidationError("output_dir must not be empty when provided.")
    if Path(raw).is_absolute():
        raise SkillValidationError("Absolute output_dir paths are not allowed.")
    candidate = (root_dir / raw).resolve()
    root_resolved = root_dir.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise SkillValidationError("output_dir path traversal is not allowed.") from exc
    return candidate


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text[:500]

    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if message:
            return str(message)
    if isinstance(error, str):
        return error
    return str(payload)[:500]


def _decode_image_payload(url: str) -> Tuple[str, Optional[bytes]]:
    if not url.startswith("data:"):
        return "", None
    if "," not in url:
        raise SkillValidationError("Invalid data URL returned by provider.")

    header, encoded = url.split(",", 1)
    mime_type = "image/png"
    if header.startswith("data:"):
        mime_part = header[5:].split(";")[0].strip()
        if mime_part:
            mime_type = mime_part

    try:
        return mime_type, base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SkillValidationError("Failed to decode image bytes from provider response.") from exc


def _extension_for_mime(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
    }.get(mime_type.lower(), ".bin")


def _timestamp_slug() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y%m%dT%H%M%S%fZ")


class GenerateImageTool(BaseTool):
    name = "generate_image"
    description = (
        "Generate image output via OpenRouter Seedream 4.5 "
        "(bytedance-seed/seedream-4.5)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "Prompt text for image generation."},
            "model": {
                "type": "string",
                "default": DEFAULT_OPENROUTER_MODEL,
                "description": "OpenRouter model id. Defaults to bytedance-seed/seedream-4.5.",
            },
            "aspect_ratio": {
                "type": "string",
                "description": "Optional OpenRouter image_config.aspect_ratio value.",
            },
            "image_size": {
                "type": "string",
                "description": "Optional OpenRouter image_config.image_size value.",
            },
            "output_dir": {
                "type": "string",
                "default": "images",
                "description": "Relative output directory under scratch root.",
            },
            "save_to_disk": {
                "type": "boolean",
                "default": True,
                "description": "When true, decodes data URLs and writes images to disk.",
            },
            "include_data_urls": {
                "type": "boolean",
                "default": False,
                "description": "Include raw image data URLs in response payload.",
            },
            "timeout_seconds": {
                "type": "number",
                "default": 120,
                "minimum": 5,
                "maximum": 600,
                "description": "Request timeout in seconds.",
            },
        },
        "required": ["prompt"],
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir.resolve()
        self.default_root_dir.mkdir(parents=True, exist_ok=True)

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        prompt = str(arguments.get("prompt", "")).strip()
        if not prompt:
            raise SkillValidationError("prompt is required.")

        api_key = _resolve_api_key()
        if not api_key:
            raise SkillValidationError("OPENAI_API_KEY is not configured.")

        model = str(arguments.get("model", DEFAULT_OPENROUTER_MODEL)).strip()
        if not model:
            model = DEFAULT_OPENROUTER_MODEL

        timeout_seconds = float(arguments.get("timeout_seconds", 120) or 120)
        timeout_seconds = max(5.0, min(timeout_seconds, 600.0))

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image"],
            "stream": False,
        }

        image_config: Dict[str, str] = {}
        aspect_ratio = str(arguments.get("aspect_ratio", "")).strip()
        if aspect_ratio:
            image_config["aspect_ratio"] = aspect_ratio
        image_size = str(arguments.get("image_size", "")).strip()
        if image_size:
            image_config["image_size"] = image_size
        if image_config:
            payload["image_config"] = image_config

        openrouter_base = (os.getenv("OPENROUTER_API_BASE") or DEFAULT_OPENROUTER_BASE).strip()
        endpoint = f"{openrouter_base.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        referer = (os.getenv("OPENROUTER_HTTP_REFERER") or os.getenv("OPENROUTER_REFERER") or "").strip()
        if referer:
            headers["HTTP-Referer"] = referer
        title = (os.getenv("OPENROUTER_X_TITLE") or "CATBot").strip()
        if title:
            headers["X-Title"] = title

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(endpoint, headers=headers, json=payload)

        if response.status_code != 200:
            message = _extract_error_message(response)
            raise RuntimeError(f"OpenRouter request failed ({response.status_code}): {message}")

        data = response.json()
        choices = data.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        images = message.get("images") or []
        if not images:
            raise RuntimeError("OpenRouter response did not contain image outputs.")

        scratch_root = (context.scratch_dir or self.default_root_dir).resolve()
        save_to_disk = bool(arguments.get("save_to_disk", True))
        include_data_urls = bool(arguments.get("include_data_urls", False))
        output_dir_raw = str(arguments.get("output_dir", "images"))
        output_dir = _resolve_output_dir(scratch_root, output_dir_raw)
        if save_to_disk:
            output_dir.mkdir(parents=True, exist_ok=True)

        output_items = []
        for index, image in enumerate(images, start=1):
            image_url = ((image or {}).get("image_url") or {}).get("url")
            if not image_url:
                continue

            item: Dict[str, Any] = {"index": index}
            mime_type, image_bytes = _decode_image_payload(image_url)
            if mime_type:
                item["mime_type"] = mime_type

            if save_to_disk and image_bytes is not None:
                file_name = f"generated_{_timestamp_slug()}_{index}{_extension_for_mime(mime_type)}"
                file_path = output_dir / file_name
                file_path.write_bytes(image_bytes)
                item["path"] = str(file_path)
                item["relative_path"] = str(file_path.relative_to(scratch_root)).replace("\\", "/")
                item["size_bytes"] = len(image_bytes)
            elif image_bytes is None:
                item["url"] = image_url

            if include_data_urls:
                item["data_url"] = image_url
            output_items.append(item)

        if not output_items:
            raise RuntimeError("OpenRouter returned images but no usable image_url entries were found.")

        return {
            "model": model,
            "prompt": prompt,
            "images": output_items,
            "image_count": len(output_items),
            "output_dir": str(output_dir) if save_to_disk else None,
            "assistant_text": message.get("content"),
            "usage": data.get("usage"),
            "provider": data.get("provider"),
            "id": data.get("id"),
        }


class ImageGenerationSkill(BaseSkill):
    name = "image_generation"
    description = "OpenRouter image generation tools using Seedream 4.5."
    version = "1.0.0"
    tags = ["image", "openrouter", "generation"]

    def __init__(self, root_dir: str = "./scratch") -> None:
        super().__init__()
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def create_tools(self) -> Sequence[BaseTool]:
        return [GenerateImageTool(default_root_dir=self.root_dir)]


def create_skill(root_dir: str = "./scratch") -> BaseSkill:
    return ImageGenerationSkill(root_dir=root_dir)

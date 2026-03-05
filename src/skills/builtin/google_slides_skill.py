"""Built-in Google Slides planning, markdown parsing, and request-building skill."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import quote

from src.skills.base import BaseSkill, BaseTool
from src.skills.exceptions import SkillValidationError
from src.skills.models import SkillContext

_MIN_SLIDE_COUNT = 3
_MAX_SLIDE_COUNT = 50
_SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]|(?:\d+[.)]))\s+(.+?)\s*$")
_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


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


def _coerce_slide_count(value: Any, default: int = 10) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = default
    return max(_MIN_SLIDE_COUNT, min(count, _MAX_SLIDE_COUNT))


def _coerce_positive_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


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


def _resolve_safe_scratch_path(scratch_root: Path, relative_path: str) -> Path:
    raw = _normalize_relative_path_input(relative_path)
    if not raw:
        raise SkillValidationError("Path is required.")
    if Path(raw).is_absolute() or raw.startswith("/") or bool(re.match(r"^[A-Za-z]:/", raw)):
        raise SkillValidationError("Absolute paths are not allowed.")
    if ".." in PurePosixPath(raw).parts:
        raise SkillValidationError("Path traversal is not allowed.")
    candidate = (scratch_root / raw).resolve()
    root_resolved = scratch_root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise SkillValidationError("Path traversal is not allowed.") from exc
    return candidate


def _as_clean_lines(raw_value: Any) -> List[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        candidates = raw_value.splitlines()
    elif isinstance(raw_value, list):
        candidates = [str(item) for item in raw_value]
    else:
        raise SkillValidationError("bullets must be a string or array of strings.")

    lines: List[str] = []
    for item in candidates:
        text = str(item).strip()
        if text:
            lines.append(text)
    return lines


def _looks_like_url(value: str) -> bool:
    return bool(re.match(r"^(?:https?|data):", str(value or "").strip(), flags=re.IGNORECASE))


def _as_image_entries(raw_images: Any) -> List[Dict[str, str]]:
    if raw_images is None:
        return []
    if isinstance(raw_images, (str, dict)):
        candidates = [raw_images]
    elif isinstance(raw_images, list):
        candidates = list(raw_images)
    else:
        raise SkillValidationError("images must be a string, object, or array.")

    images: List[Dict[str, str]] = []
    for index, item in enumerate(candidates, start=1):
        if isinstance(item, str):
            value = item.strip()
            if not value:
                continue
            if _looks_like_url(value):
                images.append({"url": value})
            else:
                images.append({"path": _normalize_relative_path_input(value)})
            continue

        if not isinstance(item, dict):
            raise SkillValidationError(
                f"images[{index}] must be a string or object with path/url fields."
            )

        path_value = str(item.get("path", "")).strip()
        url_value = str(item.get("url", "")).strip()
        alt_value = str(item.get("alt", "")).strip()
        if not path_value and not url_value:
            raise SkillValidationError(
                f"images[{index}] must include at least one of 'path' or 'url'."
            )

        image_entry: Dict[str, str] = {}
        if path_value:
            image_entry["path"] = _normalize_relative_path_input(path_value)
        if url_value:
            image_entry["url"] = url_value
        if alt_value:
            image_entry["alt"] = alt_value
        images.append(image_entry)

    return images


def _safe_object_id(prefix: str, index: int) -> str:
    raw = f"{prefix}_{index}"
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", raw).strip("_")
    if not cleaned:
        cleaned = f"{prefix}_{index}"
    if not cleaned[0].isalpha():
        cleaned = f"id_{cleaned}"
    return cleaned[:50]


def _normalize_slide_entries(raw_slides: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_slides, list) or not raw_slides:
        raise SkillValidationError("slides must be a non-empty array.")

    slides: List[Dict[str, Any]] = []
    for idx, raw_slide in enumerate(raw_slides, start=1):
        if not isinstance(raw_slide, dict):
            raise SkillValidationError(f"slides[{idx}] must be an object.")
        title = str(raw_slide.get("title", "")).strip()
        if not title:
            raise SkillValidationError(f"slides[{idx}] is missing a non-empty title.")
        bullets = _as_clean_lines(raw_slide.get("bullets"))
        images = _as_image_entries(raw_slide.get("images"))
        slides.append({"title": title, "bullets": bullets, "images": images})
    return slides


def _clean_markdown_image_target(target: str) -> str:
    text = str(target or "").strip().strip("<>").strip()
    if not text:
        return ""
    # Strip optional trailing markdown image title: path "title text".
    if " " in text and '"' in text:
        text = text.split(" ", 1)[0]
    return text.strip()


def _coerce_markdown_image_entry(
    raw_target: str,
    *,
    alt: str,
    scratch_root: Path,
    source_dir: Optional[Path],
) -> Optional[Dict[str, str]]:
    target = _clean_markdown_image_target(raw_target)
    if not target:
        return None
    if _looks_like_url(target):
        entry: Dict[str, str] = {"url": target}
        if alt:
            entry["alt"] = alt
        return entry

    normalized = _normalize_relative_path_input(target)
    entry = {"path": normalized}
    if source_dir is not None:
        try:
            resolved = (source_dir / normalized).resolve()
            rel = resolved.relative_to(scratch_root.resolve())
            entry["path"] = str(rel).replace("\\", "/")
        except Exception:
            pass
    if alt:
        entry["alt"] = alt
    return entry


def _tokenize_for_match(value: str) -> List[str]:
    cleaned = re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())
    return [token for token in cleaned.split() if token]


def _list_scratch_images(scratch_root: Path, image_dir: str) -> List[str]:
    target_dir = _resolve_safe_scratch_path(scratch_root, image_dir)
    if not target_dir.exists() or not target_dir.is_dir():
        return []

    root_resolved = scratch_root.resolve()
    images: List[str] = []
    for item in sorted(target_dir.rglob("*")):
        if not item.is_file():
            continue
        if item.suffix.lower() not in _SUPPORTED_IMAGE_EXTENSIONS:
            continue
        try:
            rel = item.resolve().relative_to(root_resolved)
        except ValueError:
            continue
        images.append(str(rel).replace("\\", "/"))
    return images


def _attach_scratch_images_to_slides(
    slides: List[Dict[str, Any]],
    image_relative_paths: List[str],
    *,
    max_images_per_slide: int,
    match_mode: str,
) -> int:
    if max_images_per_slide <= 0 or not image_relative_paths:
        return 0

    used_paths: set[str] = set()
    auto_attached = 0
    ordered_paths = sorted(image_relative_paths)

    for slide in slides:
        images = _as_image_entries(slide.get("images"))
        slide["images"] = images
        remaining_slots = max_images_per_slide - len(images)
        if remaining_slots <= 0:
            continue

        selected: List[str] = []
        if match_mode == "sequential":
            for candidate in ordered_paths:
                if candidate in used_paths:
                    continue
                selected.append(candidate)
                if len(selected) >= remaining_slots:
                    break
        else:
            title_tokens = set(_tokenize_for_match(slide.get("title", "")))
            title_slug = "_".join(_tokenize_for_match(slide.get("title", "")))
            scored: List[tuple[int, str]] = []
            for candidate in ordered_paths:
                if candidate in used_paths:
                    continue
                stem = Path(candidate).stem
                stem_tokens = set(_tokenize_for_match(stem))
                stem_slug = "_".join(_tokenize_for_match(stem))
                score = len(title_tokens.intersection(stem_tokens)) * 3
                if title_slug and stem_slug and (title_slug in stem_slug or stem_slug in title_slug):
                    score += 2
                if score > 0:
                    scored.append((score, candidate))

            scored.sort(key=lambda item: (-item[0], item[1]))
            selected = [candidate for _, candidate in scored[:remaining_slots]]

        for rel_path in selected:
            images.append({"path": rel_path, "alt": slide.get("title", "")})
            used_paths.add(rel_path)
            auto_attached += 1

    return auto_attached


def _parse_markdown_to_slides(
    markdown_text: str,
    *,
    fallback_title: str,
    scratch_root: Path,
    source_dir: Optional[Path],
) -> List[Dict[str, Any]]:
    slides: List[Dict[str, Any]] = []
    current_slide: Optional[Dict[str, Any]] = None
    paragraph_lines: List[str] = []

    def ensure_current_slide() -> Dict[str, Any]:
        nonlocal current_slide
        if current_slide is None:
            current_slide = {"title": fallback_title, "bullets": [], "images": []}
        return current_slide

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        paragraph_text = " ".join(part.strip() for part in paragraph_lines if part.strip()).strip()
        paragraph_lines.clear()
        if paragraph_text:
            ensure_current_slide()["bullets"].append(paragraph_text)

    def start_new_slide(title: str) -> None:
        nonlocal current_slide
        flush_paragraph()
        if current_slide is not None:
            slides.append(current_slide)
        current_slide = {"title": title or fallback_title, "bullets": [], "images": []}

    for raw_line in str(markdown_text or "").splitlines():
        line = raw_line.rstrip()
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            start_new_slide(str(heading_match.group(2)).strip())
            continue

        if not line.strip():
            flush_paragraph()
            continue

        image_matches = list(_MARKDOWN_IMAGE_RE.finditer(line))
        if image_matches:
            slide = ensure_current_slide()
            for image_match in image_matches:
                alt = str(image_match.group(1)).strip()
                target = str(image_match.group(2)).strip()
                entry = _coerce_markdown_image_entry(
                    target,
                    alt=alt,
                    scratch_root=scratch_root,
                    source_dir=source_dir,
                )
                if entry:
                    slide["images"].append(entry)
            line = _MARKDOWN_IMAGE_RE.sub("", line).strip()
            if not line:
                continue

        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            flush_paragraph()
            ensure_current_slide()["bullets"].append(str(bullet_match.group(1)).strip())
            continue

        paragraph_lines.append(line.strip())

    flush_paragraph()
    if current_slide is not None:
        slides.append(current_slide)

    normalized: List[Dict[str, Any]] = []
    for raw_slide in slides:
        title = str(raw_slide.get("title", "")).strip() or fallback_title
        bullets = _as_clean_lines(raw_slide.get("bullets"))
        images = _as_image_entries(raw_slide.get("images"))
        if title or bullets or images:
            normalized.append({"title": title, "bullets": bullets, "images": images})

    if normalized:
        return normalized

    fallback_text = str(markdown_text or "").strip()
    bullets = []
    if fallback_text:
        first_line = fallback_text.splitlines()[0].strip()
        if first_line and first_line.lower() != fallback_title.lower():
            bullets.append(first_line)
    return [{"title": fallback_title, "bullets": bullets, "images": []}]


def _to_public_image_url(
    image: Dict[str, str],
    *,
    image_url_prefix: str,
    scratch_root: Path,
) -> Optional[str]:
    explicit_url = str(image.get("url", "")).strip()
    if explicit_url and _looks_like_url(explicit_url):
        return explicit_url

    path_value = str(image.get("path", "")).strip()
    if not path_value:
        return None
    if not image_url_prefix:
        return None

    safe_path = _resolve_safe_scratch_path(scratch_root, path_value)
    relative = str(safe_path.relative_to(scratch_root.resolve())).replace("\\", "/")
    encoded = quote(relative, safe="/-._~")
    return f"{image_url_prefix.rstrip('/')}/{encoded.lstrip('/')}"


class CreateOutlineTool(BaseTool):
    name = "create_outline"
    description = "Generate a practical presentation outline for Google Slides."
    input_schema = {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Primary topic for the deck."},
            "audience": {
                "type": "string",
                "default": "General audience",
                "description": "Target audience for tone and framing.",
            },
            "objective": {
                "type": "string",
                "default": "",
                "description": "Desired decision or outcome from the presentation.",
            },
            "slide_count": {
                "type": "integer",
                "default": 10,
                "minimum": _MIN_SLIDE_COUNT,
                "maximum": _MAX_SLIDE_COUNT,
                "description": "Total number of slides to generate.",
            },
            "tone": {
                "type": "string",
                "default": "clear and actionable",
                "description": "Writing tone for notes and bullets.",
            },
            "include_agenda": {
                "type": "boolean",
                "default": True,
                "description": "Include an agenda slide near the start of the deck.",
            },
            "include_summary": {
                "type": "boolean",
                "default": True,
                "description": "Reserve the final slide for summary and next steps.",
            },
        },
        "required": ["topic"],
        "additionalProperties": False,
    }

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        topic = str(arguments.get("topic", "")).strip()
        if not topic:
            raise SkillValidationError("topic is required.")

        audience = str(arguments.get("audience", "General audience")).strip() or "General audience"
        objective = str(arguments.get("objective", "")).strip()
        tone = str(arguments.get("tone", "clear and actionable")).strip() or "clear and actionable"
        slide_count = _coerce_slide_count(arguments.get("slide_count", 10), default=10)
        include_agenda = _coerce_bool(arguments.get("include_agenda", True), default=True)
        include_summary = _coerce_bool(arguments.get("include_summary", True), default=True)

        slides: List[Dict[str, Any]] = [
            {
                "title": topic,
                "bullets": [
                    f"Audience: {audience}",
                    f"Objective: {objective or 'Align on goals and required decisions'}",
                ],
                "speaker_notes": f"Open with context and set expectations in a {tone} tone.",
            }
        ]

        if include_agenda and len(slides) < slide_count:
            slides.append(
                {
                    "title": "Agenda",
                    "bullets": [
                        "Current state and constraints",
                        "Recommended approach",
                        "Execution plan and timeline",
                        "Risks, decisions, and next steps",
                    ],
                    "speaker_notes": "Preview structure so stakeholders can follow the decision path.",
                }
            )

        templates = [
            (
                "Current State",
                [
                    f"What is happening in {topic} right now",
                    "Primary metrics and trend summary",
                    "Immediate constraints we must work within",
                ],
            ),
            (
                "Problem Framing",
                [
                    "Why this matters now",
                    "What happens if no action is taken",
                    "Decision criteria for success",
                ],
            ),
            (
                "Recommended Strategy",
                [
                    "Core proposal and rationale",
                    "Alternatives considered and tradeoffs",
                    "Resource assumptions and dependencies",
                ],
            ),
            (
                "Execution Plan",
                [
                    "Phase breakdown and owners",
                    "Timeline with critical milestones",
                    "How progress will be reported",
                ],
            ),
            (
                "Risks And Mitigations",
                [
                    "Top operational and delivery risks",
                    "Mitigation actions and fallback options",
                    "Open questions requiring leadership input",
                ],
            ),
            (
                "Ask And Decision",
                [
                    "Decision requested from stakeholders",
                    "Budget or staffing required",
                    "Immediate next action after approval",
                ],
            ),
        ]

        reserved_for_summary = 1 if include_summary else 0
        template_index = 0
        while len(slides) < (slide_count - reserved_for_summary):
            title, bullets = templates[template_index % len(templates)]
            slides.append(
                {
                    "title": title,
                    "bullets": bullets,
                    "speaker_notes": f"Keep this section concise and {tone}.",
                }
            )
            template_index += 1

        if include_summary and len(slides) < slide_count:
            slides.append(
                {
                    "title": "Summary And Next Steps",
                    "bullets": [
                        "What we agreed today",
                        "Actions by owner and due date",
                        "Follow-up meeting and success check",
                    ],
                    "speaker_notes": "Close with decisions and accountability.",
                }
            )

        slides = slides[:slide_count]
        for idx, slide in enumerate(slides, start=1):
            slide["index"] = idx

        return {
            "topic": topic,
            "audience": audience,
            "objective": objective,
            "tone": tone,
            "slide_count": len(slides),
            "slides": slides,
        }


class BuildBatchUpdateRequestsTool(BaseTool):
    name = "build_batch_update_requests"
    description = (
        "Build Google Slides API batchUpdate requests from slide title/bullet inputs, "
        "including optional image create requests."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "presentation_id": {
                "type": "string",
                "description": "Target Google Slides presentation id.",
            },
            "slides": {
                "type": "array",
                "description": "Ordered slide specs with title and optional bullet lines.",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "bullets": {
                            "type": ["array", "string"],
                            "items": {"type": "string"},
                        },
                        "images": {
                            "type": ["array", "string", "object"],
                            "description": (
                                "Optional image references per slide. Each entry may be a URL string, "
                                "scratch-relative path string (for example images/chart.png), or "
                                "an object with path/url/alt."
                            ),
                        },
                    },
                    "required": ["title"],
                    "additionalProperties": False,
                },
            },
            "image_url_prefix": {
                "type": "string",
                "description": (
                    "Optional public base URL used to convert scratch-relative image paths "
                    "into createImage URLs."
                ),
            },
            "include_image_requests": {
                "type": "boolean",
                "default": True,
                "description": "When true, emit createImage requests for slide image inputs.",
            },
        },
        "required": ["presentation_id", "slides"],
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        presentation_id = str(arguments.get("presentation_id", "")).strip()
        if not presentation_id:
            raise SkillValidationError("presentation_id is required.")

        slides = _normalize_slide_entries(arguments.get("slides"))
        include_image_requests = _coerce_bool(
            arguments.get("include_image_requests", True), default=True
        )
        image_url_prefix = str(arguments.get("image_url_prefix", "")).strip()
        scratch_root = (context.scratch_dir or self.default_root_dir).resolve()
        requests: List[Dict[str, Any]] = []
        slide_objects: List[Dict[str, str]] = []
        image_objects: List[Dict[str, str]] = []
        skipped_images: List[Dict[str, str]] = []
        image_request_count = 0

        for index, slide in enumerate(slides, start=1):
            slide_id = _safe_object_id("slide", index)
            title_id = _safe_object_id("title", index)
            body_id = _safe_object_id("body", index)

            requests.append(
                {
                    "createSlide": {
                        "objectId": slide_id,
                        "slideLayoutReference": {"predefinedLayout": "TITLE_AND_BODY"},
                        "placeholderIdMappings": [
                            {
                                "layoutPlaceholder": {"type": "TITLE", "index": 0},
                                "objectId": title_id,
                            },
                            {
                                "layoutPlaceholder": {"type": "BODY", "index": 0},
                                "objectId": body_id,
                            },
                        ],
                    }
                }
            )
            requests.append(
                {
                    "insertText": {
                        "objectId": title_id,
                        "insertionIndex": 0,
                        "text": slide["title"],
                    }
                }
            )

            if slide["bullets"]:
                body_text = "\n".join(f"- {line}" for line in slide["bullets"])
                requests.append(
                    {
                        "insertText": {
                            "objectId": body_id,
                            "insertionIndex": 0,
                            "text": body_text,
                        }
                    }
                )

            image_ids: List[str] = []
            if include_image_requests and slide["images"]:
                for image_index, image in enumerate(slide["images"], start=1):
                    try:
                        image_url = _to_public_image_url(
                            image,
                            image_url_prefix=image_url_prefix,
                            scratch_root=scratch_root,
                        )
                    except SkillValidationError:
                        image_url = None
                    if not image_url:
                        skipped_images.append(
                            {
                                "slide_index": str(index),
                                "title": slide["title"],
                                "path": str(image.get("path", "")),
                                "url": str(image.get("url", "")),
                                "reason": (
                                    "No usable image URL. Provide images[].url or image_url_prefix "
                                    "for scratch-relative image paths."
                                ),
                            }
                        )
                        continue

                    image_id = _safe_object_id(f"image_{index}", image_index)
                    image_ids.append(image_id)
                    requests.append(
                        {
                            "createImage": {
                                "objectId": image_id,
                                "url": image_url,
                                "elementProperties": {
                                    "pageObjectId": slide_id,
                                    "size": {
                                        "height": {"magnitude": 240, "unit": "PT"},
                                        "width": {"magnitude": 360, "unit": "PT"},
                                    },
                                    "transform": {
                                        "scaleX": 1,
                                        "scaleY": 1,
                                        "translateX": 60,
                                        "translateY": 160,
                                        "unit": "PT",
                                    },
                                },
                            }
                        }
                    )
                    image_objects.append(
                        {
                            "slide_id": slide_id,
                            "image_id": image_id,
                            "title": slide["title"],
                            "url": image_url,
                            "path": str(image.get("path", "")),
                            "alt": str(image.get("alt", "")),
                        }
                    )
                    image_request_count += 1

            slide_objects.append(
                {
                    "slide_id": slide_id,
                    "title_id": title_id,
                    "body_id": body_id,
                    "title": slide["title"],
                    "image_count": str(len(image_ids)),
                }
            )

        return {
            "presentation_id": presentation_id,
            "slide_count": len(slides),
            "request_count": len(requests),
            "image_request_count": image_request_count,
            "requests": requests,
            "objects": slide_objects,
            "image_objects": image_objects,
            "skipped_images": skipped_images,
        }


class CreateOutlineFromMarkdownTool(BaseTool):
    name = "create_outline_from_markdown"
    description = (
        "Generate slide title/bullet/image entries from markdown text or a markdown file "
        "in the scratch workspace."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "markdown": {
                "type": "string",
                "description": "Inline markdown content to transform into slides.",
            },
            "markdown_path": {
                "type": "string",
                "description": (
                    "Path to a markdown file under scratch (for example notes/deck.md "
                    "or scratch/notes/deck.md)."
                ),
            },
            "max_slides": {
                "type": "integer",
                "default": _MAX_SLIDE_COUNT,
                "minimum": 1,
                "maximum": _MAX_SLIDE_COUNT,
                "description": "Upper bound on generated slide count.",
            },
            "attach_scratch_images": {
                "type": "boolean",
                "default": True,
                "description": "When true, auto-match images from scratch/images to slides.",
            },
            "image_dir": {
                "type": "string",
                "default": "images",
                "description": "Scratch-relative image directory to scan for auto-attachment.",
            },
            "image_match_mode": {
                "type": "string",
                "default": "title",
                "enum": ["title", "sequential"],
                "description": "Auto-image matching strategy for scratch image scanning.",
            },
            "max_images_per_slide": {
                "type": "integer",
                "default": 1,
                "minimum": 0,
                "maximum": 4,
                "description": "Maximum auto-attached images per slide.",
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, default_root_dir: Path) -> None:
        self.default_root_dir = default_root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        markdown = str(arguments.get("markdown", "") or "")
        markdown_path_raw = str(arguments.get("markdown_path", "")).strip()
        if not markdown.strip() and not markdown_path_raw:
            raise SkillValidationError("Provide either markdown or markdown_path.")

        scratch_root = (context.scratch_dir or self.default_root_dir).resolve()
        source_path: Optional[Path] = None
        source_dir: Optional[Path] = None
        if markdown_path_raw:
            source_path = _resolve_safe_scratch_path(scratch_root, markdown_path_raw)
            if not source_path.exists():
                raise SkillValidationError(f"markdown_path does not exist: {markdown_path_raw}")
            if not source_path.is_file():
                raise SkillValidationError(f"markdown_path is not a file: {markdown_path_raw}")
            markdown = source_path.read_text(encoding="utf-8")
            source_dir = source_path.parent

        fallback_title = "Untitled Presentation"
        if source_path is not None:
            fallback_title = source_path.stem.replace("_", " ").strip() or fallback_title

        slides = _parse_markdown_to_slides(
            markdown,
            fallback_title=fallback_title,
            scratch_root=scratch_root,
            source_dir=source_dir,
        )

        max_slides = _coerce_positive_int(
            arguments.get("max_slides", _MAX_SLIDE_COUNT),
            default=_MAX_SLIDE_COUNT,
            minimum=1,
            maximum=_MAX_SLIDE_COUNT,
        )
        slides = slides[:max_slides]

        attach_scratch_images = _coerce_bool(
            arguments.get("attach_scratch_images", True),
            default=True,
        )
        image_dir = str(arguments.get("image_dir", "images") or "images").strip() or "images"
        image_match_mode = str(arguments.get("image_match_mode", "title") or "title").strip().lower()
        if image_match_mode not in {"title", "sequential"}:
            raise SkillValidationError("image_match_mode must be either 'title' or 'sequential'.")
        max_images_per_slide = _coerce_positive_int(
            arguments.get("max_images_per_slide", 1),
            default=1,
            minimum=0,
            maximum=4,
        )

        available_images: List[str] = []
        auto_attached_images = 0
        if attach_scratch_images and max_images_per_slide > 0:
            available_images = _list_scratch_images(scratch_root, image_dir)
            auto_attached_images = _attach_scratch_images_to_slides(
                slides,
                available_images,
                max_images_per_slide=max_images_per_slide,
                match_mode=image_match_mode,
            )

        for idx, slide in enumerate(slides, start=1):
            slide["index"] = idx

        return {
            "source": "markdown_path" if source_path is not None else "markdown",
            "markdown_path": (
                str(source_path.relative_to(scratch_root)).replace("\\", "/")
                if source_path is not None
                else None
            ),
            "slide_count": len(slides),
            "slides": slides,
            "auto_attached_images": auto_attached_images,
            "scratch_image_count": len(available_images),
        }


class GoogleSlidesSkill(BaseSkill):
    name = "google_slides"
    description = "Google Slides planning, markdown conversion, and request-building tools."
    version = "1.1.0"
    tags = ["google", "slides", "presentation"]

    def __init__(self, root_dir: str = "./scratch") -> None:
        super().__init__()
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def create_tools(self) -> Sequence[BaseTool]:
        return [
            CreateOutlineTool(),
            CreateOutlineFromMarkdownTool(default_root_dir=self.root_dir),
            BuildBatchUpdateRequestsTool(default_root_dir=self.root_dir),
        ]


def create_skill(root_dir: str = "./scratch") -> BaseSkill:
    return GoogleSlidesSkill(root_dir=root_dir)

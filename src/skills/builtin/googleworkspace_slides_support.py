"""Shared markdown-to-slides helpers used by the Google Workspace CLI skill."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from src.skills.exceptions import SkillValidationError

_MAX_SLIDE_COUNT = 50
_SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*(?:[-*+]|(?:\d+[.)]))\s+(.+?)\s*$")
_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_TITLE_BOX_X_PT = 36
_TITLE_BOX_Y_PT = 24
_TITLE_BOX_WIDTH_PT = 648
_TITLE_BOX_HEIGHT_PT = 48
_BODY_BOX_X_PT = 48
_BODY_BOX_Y_PT = 96
_BODY_BOX_HEIGHT_PT = 252
_BODY_BOX_WIDTH_PT = 624
_BODY_BOX_WIDTH_WITH_IMAGE_PT = 312
_IMAGE_BOX_X_PT = 396
_IMAGE_BOX_Y_PT = 120
_IMAGE_BOX_WIDTH_PT = 276
_IMAGE_BOX_HEIGHT_PT = 228


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


def _build_batch_update_payload(
    presentation_id: str,
    raw_slides: Any,
    *,
    include_image_requests: bool,
    image_url_prefix: str,
    scratch_root: Path,
) -> Dict[str, Any]:
    normalized_presentation_id = str(presentation_id or "").strip()
    if not normalized_presentation_id:
        raise SkillValidationError("presentation_id is required.")

    slides = _normalize_slide_entries(raw_slides)
    requests: List[Dict[str, Any]] = []
    slide_objects: List[Dict[str, str]] = []
    image_objects: List[Dict[str, str]] = []
    skipped_images: List[Dict[str, str]] = []
    image_request_count = 0

    for index, slide in enumerate(slides, start=1):
        slide_id = _safe_object_id("slide", index)
        title_id = _safe_object_id("title", index)
        body_id = _safe_object_id("body", index)
        reserve_image_space = include_image_requests and bool(slide["images"])
        body_box_width = (
            _BODY_BOX_WIDTH_WITH_IMAGE_PT if reserve_image_space else _BODY_BOX_WIDTH_PT
        )

        requests.append(
            {
                "createSlide": {
                    "objectId": slide_id,
                    "slideLayoutReference": {"predefinedLayout": "BLANK"},
                }
            }
        )
        requests.append(
            {
                "createShape": {
                    "objectId": title_id,
                    "shapeType": "TEXT_BOX",
                    "elementProperties": {
                        "pageObjectId": slide_id,
                        "size": {
                            "height": {"magnitude": _TITLE_BOX_HEIGHT_PT, "unit": "PT"},
                            "width": {"magnitude": _TITLE_BOX_WIDTH_PT, "unit": "PT"},
                        },
                        "transform": {
                            "scaleX": 1,
                            "scaleY": 1,
                            "translateX": _TITLE_BOX_X_PT,
                            "translateY": _TITLE_BOX_Y_PT,
                            "unit": "PT",
                        },
                    },
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
        requests.append(
            {
                "updateTextStyle": {
                    "objectId": title_id,
                    "textRange": {"type": "ALL"},
                    "style": {
                        "fontSize": {"magnitude": 24, "unit": "PT"},
                        "bold": True,
                    },
                    "fields": "fontSize,bold",
                }
            }
        )

        if slide["bullets"]:
            requests.append(
                {
                    "createShape": {
                        "objectId": body_id,
                        "shapeType": "TEXT_BOX",
                        "elementProperties": {
                            "pageObjectId": slide_id,
                            "size": {
                                "height": {"magnitude": _BODY_BOX_HEIGHT_PT, "unit": "PT"},
                                "width": {"magnitude": body_box_width, "unit": "PT"},
                            },
                            "transform": {
                                "scaleX": 1,
                                "scaleY": 1,
                                "translateX": _BODY_BOX_X_PT,
                                "translateY": _BODY_BOX_Y_PT,
                                "unit": "PT",
                            },
                        },
                    }
                }
            )
            body_text = "\n".join(slide["bullets"])
            requests.append(
                {
                    "insertText": {
                        "objectId": body_id,
                        "insertionIndex": 0,
                        "text": body_text,
                    }
                }
            )
            requests.append(
                {
                    "createParagraphBullets": {
                        "objectId": body_id,
                        "textRange": {"type": "ALL"},
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
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
                                    "height": {"magnitude": _IMAGE_BOX_HEIGHT_PT, "unit": "PT"},
                                    "width": {"magnitude": _IMAGE_BOX_WIDTH_PT, "unit": "PT"},
                                },
                                "transform": {
                                    "scaleX": 1,
                                    "scaleY": 1,
                                    "translateX": (
                                        _IMAGE_BOX_X_PT if reserve_image_space else _BODY_BOX_X_PT
                                    ),
                                    "translateY": _IMAGE_BOX_Y_PT,
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
        "presentation_id": normalized_presentation_id,
        "slide_count": len(slides),
        "request_count": len(requests),
        "image_request_count": image_request_count,
        "requests": requests,
        "objects": slide_objects,
        "image_objects": image_objects,
        "skipped_images": skipped_images,
    }


def _clean_markdown_image_target(target: str) -> str:
    text = str(target or "").strip().strip("<>").strip()
    if not text:
        return ""
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
    if not path_value or not image_url_prefix:
        return None

    safe_path = _resolve_safe_scratch_path(scratch_root, path_value)
    relative = str(safe_path.relative_to(scratch_root.resolve())).replace("\\", "/")
    encoded = quote(relative, safe="/-._~")
    return f"{image_url_prefix.rstrip('/')}/{encoded.lstrip('/')}"

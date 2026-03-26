"""Built-in filesystem skill with root-path sandboxing."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional, Sequence, Set

from src.skills.base import BaseSkill, BaseTool
from src.skills.exceptions import SkillValidationError
from src.skills.models import SkillContext
from src.utils.file_readers import read_png_file, read_supported_file_text

TEXT_FILE_EXTENSIONS = {".txt", ".md", ".csv", ".py", ".js", ".html"}
DOCUMENT_TEXT_EXTENSIONS = {".docx", ".xlsx", ".xls", ".pdf"}
IMAGE_FILE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
READABLE_TEXT_EXTENSIONS = TEXT_FILE_EXTENSIONS | DOCUMENT_TEXT_EXTENSIONS


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


def _argument_text(arguments: Dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = arguments.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def _resolve_safe_path(root_dir: Path, relative_path: str) -> Path:
    raw = _normalize_relative_path_input(relative_path)
    if not raw:
        raise SkillValidationError("Path is required.")
    if Path(raw).is_absolute() or raw.startswith("/") or bool(re.match(r"^[A-Za-z]:/", raw)):
        raise SkillValidationError("Absolute paths are not allowed.")
    if ".." in PurePosixPath(raw).parts:
        raise SkillValidationError("Path traversal is not allowed.")
    candidate = (root_dir / raw).resolve()
    root_resolved = root_dir.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise SkillValidationError("Path traversal is not allowed.") from exc
    return candidate


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


def _coerce_bounded_int(
    value: Any,
    *,
    default: int,
    minimum: int = 0,
    maximum: int | None = None,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if maximum is not None:
        parsed = min(parsed, maximum)
    return max(minimum, parsed)


def _coerce_optional_bounded_int(
    value: Any,
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if maximum is not None:
        parsed = min(parsed, maximum)
    return max(minimum, parsed)


def _read_text_with_fallback(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _truncate_middle(text: str, max_chars: Optional[int]) -> tuple[str, bool]:
    if max_chars is None or max_chars < 1 or len(text) <= max_chars:
        return text, False
    if max_chars < 80:
        return text[:max_chars], True
    head = max_chars // 2
    tail = max_chars - head
    removed = len(text) - max_chars
    return (
        f"{text[:head]}\n\n...[truncated {removed} chars]...\n\n{text[-tail:]}",
        True,
    )


def _slice_text_content(
    content: str,
    *,
    start_line: Optional[int],
    end_line: Optional[int],
    max_chars: Optional[int],
    include_line_numbers: bool,
) -> Dict[str, Any]:
    lines = content.splitlines()
    total_lines = len(lines)
    excerpt_start_line = 1 if total_lines > 0 else 0
    excerpt_end_line = total_lines
    line_filtered = False

    rendered_lines = lines
    if start_line is not None or end_line is not None:
        start_index = max(0, (start_line or 1) - 1)
        resolved_end_line = end_line
        if resolved_end_line is not None and start_line is not None and resolved_end_line < start_line:
            resolved_end_line = start_line
        end_index = total_lines if resolved_end_line is None else min(total_lines, resolved_end_line)
        rendered_lines = lines[start_index:end_index]
        excerpt_start_line = start_index + 1 if rendered_lines else 0
        excerpt_end_line = start_index + len(rendered_lines) if rendered_lines else 0
        line_filtered = True

    if include_line_numbers and rendered_lines:
        base_line = excerpt_start_line
        rendered = "\n".join(
            f"{base_line + index}: {line}" for index, line in enumerate(rendered_lines)
        )
    else:
        rendered = "\n".join(rendered_lines)

    truncated_content, truncated = _truncate_middle(rendered, max_chars)
    return {
        "content": truncated_content,
        "total_lines": total_lines,
        "excerpt_start_line": excerpt_start_line,
        "excerpt_end_line": excerpt_end_line,
        "line_filtered": line_filtered,
        "truncated": truncated,
    }


def _first_content_match(content: str, query: str, *, case_sensitive: bool) -> Optional[Dict[str, Any]]:
    if not query:
        return None
    haystack = content if case_sensitive else content.lower()
    needle = query if case_sensitive else query.lower()
    index = haystack.find(needle)
    if index < 0:
        return None
    line_number = content.count("\n", 0, index) + 1
    start = max(0, index - 90)
    end = min(len(content), index + len(query) + 140)
    excerpt = content[start:end].replace("\r", " ").replace("\n", " ").strip()
    if start > 0:
        excerpt = "..." + excerpt
    if end < len(content):
        excerpt = excerpt + "..."
    return {
        "line_number": line_number,
        "excerpt": excerpt,
        "match_count": haystack.count(needle),
    }


class ListFilesTool(BaseTool):
    name = "list_files"
    description = (
        "List files and directories in the configured root. "
        "Use this first when you need to discover candidate paths before reading or writing."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Optional relative directory path. Aliases like directory or subdir are also accepted.",
            },
            "recursive": {
                "type": "boolean",
                "default": False,
                "description": "When true, include nested files/directories under the selected path.",
            },
            "offset": {
                "type": "integer",
                "minimum": 0,
                "default": 0,
                "description": "Optional zero-based row offset for pagination.",
            },
            "max_entries": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "default": 100,
                "description": "Maximum number of rows to return.",
            },
        },
        "additionalProperties": False,
    }

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        subpath = _normalize_relative_path_input(
            _argument_text(arguments, "path", "directory", "subdir", default="")
        )
        target = self.root_dir if not subpath else _resolve_safe_path(self.root_dir, subpath)
        if not target.exists():
            raise SkillValidationError(f"Path does not exist: {subpath or '.'}")
        if not target.is_dir():
            raise SkillValidationError(f"Path is not a directory: {subpath}")

        recursive = _coerce_bool(arguments.get("recursive", False), default=False)
        offset_raw = arguments.get("offset", 0)
        try:
            offset = _coerce_bounded_int(offset_raw, default=0, minimum=0)
        except (TypeError, ValueError) as exc:
            raise SkillValidationError("offset must be an integer.") from exc
        max_entries_raw = arguments.get("max_entries", 100)
        try:
            max_entries = _coerce_bounded_int(max_entries_raw, default=100, minimum=1, maximum=500)
        except (TypeError, ValueError) as exc:
            raise SkillValidationError("max_entries must be an integer.") from exc

        entries = []
        skipped_count = 0
        root_resolved = self.root_dir.resolve()
        pending_dirs = [target]
        seen_dirs: Set[Path] = set()

        while pending_dirs:
            current_dir = pending_dirs.pop()
            try:
                current_resolved = current_dir.resolve()
                current_resolved.relative_to(root_resolved)
            except (OSError, RuntimeError, ValueError):
                skipped_count += 1
                continue
            if current_resolved in seen_dirs:
                continue
            seen_dirs.add(current_resolved)

            try:
                children = list(current_dir.iterdir())
            except OSError:
                skipped_count += 1
                continue

            for item in children:
                try:
                    if item.is_symlink():
                        skipped_count += 1
                        continue

                    item_resolved = item.resolve()
                    item_resolved.relative_to(root_resolved)

                    if item.is_dir():
                        item_type = "directory"
                        size_bytes = None
                        if recursive:
                            pending_dirs.append(item)
                    elif item.is_file():
                        item_type = "file"
                        size_bytes = item.stat().st_size
                    else:
                        continue
                except (OSError, RuntimeError, ValueError):
                    skipped_count += 1
                    continue

                entries.append(
                    {
                        "name": item.name,
                        "relative_path": str(item.relative_to(self.root_dir)).replace("\\", "/"),
                        "type": item_type,
                        "size_bytes": size_bytes,
                    }
                )

            if not recursive:
                break

        entries.sort(key=lambda item: (item.get("type") != "directory", str(item.get("relative_path", "")).lower()))
        total_count = len(entries)
        limited_items = entries[offset:offset + max_entries]
        remaining_count = max(0, total_count - (offset + len(limited_items)))
        directory_count = sum(1 for item in entries if item.get("type") == "directory")
        file_count = total_count - directory_count
        return {
            "items": limited_items,
            "root": str(self.root_dir),
            "path": subpath or ".",
            "recursive": recursive,
            "count": total_count,
            "directory_count": directory_count,
            "file_count": file_count,
            "returned_count": len(limited_items),
            "total_count": total_count,
            "remaining_count": remaining_count,
            "offset": offset,
            "max_entries": max_entries,
            "has_more": remaining_count > 0,
            "next_offset": (offset + len(limited_items)) if remaining_count > 0 else None,
            "skipped_count": skipped_count,
        }


class ReadTextTool(BaseTool):
    name = "read_text"
    description = (
        "Read supported file content from a file inside the configured root. "
        "Supports text, Office documents, PDFs, and basic image metadata with partial reads for text-like formats."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative file path. Aliases like filename or file are also accepted.",
            },
            "start_line": {
                "type": "integer",
                "minimum": 1,
                "description": "Optional 1-based start line for partial reads.",
            },
            "end_line": {
                "type": "integer",
                "minimum": 1,
                "description": "Optional 1-based inclusive end line for partial reads.",
            },
            "max_chars": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50000,
                "description": "Optional character cap for the returned content.",
            },
            "include_line_numbers": {
                "type": "boolean",
                "default": False,
                "description": "When true, prefix returned lines with 1-based line numbers.",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        path_value = _argument_text(arguments, "path", "filename", "file")
        path = _resolve_safe_path(self.root_dir, path_value)
        if not path.exists():
            raise SkillValidationError(f"File does not exist: {path_value}")
        if not path.is_file():
            raise SkillValidationError("Path is not a file.")
        suffix = path.suffix.lower()
        start_line = _coerce_optional_bounded_int(arguments.get("start_line"), minimum=1)
        end_line = _coerce_optional_bounded_int(arguments.get("end_line"), minimum=1)
        max_chars = _coerce_optional_bounded_int(arguments.get("max_chars"), minimum=1, maximum=50000)
        include_line_numbers = _coerce_bool(arguments.get("include_line_numbers", False), default=False)
        relative_path = str(path.relative_to(self.root_dir)).replace("\\", "/")

        if suffix in READABLE_TEXT_EXTENSIONS:
            full_content, content_type = read_supported_file_text(path, TEXT_FILE_EXTENSIONS)
            excerpt = _slice_text_content(
                full_content,
                start_line=start_line,
                end_line=end_line,
                max_chars=max_chars,
                include_line_numbers=include_line_numbers,
            )
            return {
                "path": relative_path,
                "content": excerpt["content"],
                "type": content_type,
                "size_bytes": path.stat().st_size,
                "total_lines": excerpt["total_lines"],
                "excerpt_start_line": excerpt["excerpt_start_line"],
                "excerpt_end_line": excerpt["excerpt_end_line"],
                "truncated": excerpt["truncated"],
                "line_filtered": excerpt["line_filtered"],
            }

        if suffix in IMAGE_FILE_EXTENSIONS:
            image_data = read_png_file(path)
            return {
                "path": relative_path,
                "content": str(image_data.get("description") or "Image file"),
                "type": "image",
                "size_bytes": path.stat().st_size,
                "total_lines": 0,
                "excerpt_start_line": 0,
                "excerpt_end_line": 0,
                "truncated": False,
                "line_filtered": False,
                "image_data": image_data,
            }

        raise SkillValidationError(f"Unsupported file type for filesystem.read_text: {suffix or '(none)'}")


class WriteTextTool(BaseTool):
    name = "write_text"
    description = (
        "Write UTF-8 text content to a file inside the configured root. "
        "Creates parent directories automatically and can append instead of overwrite."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative file path. Aliases like filename or file are also accepted.",
            },
            "content": {
                "type": "string",
                "description": "Text content to write. Aliases like text or body are also accepted.",
            },
            "append": {
                "type": "boolean",
                "default": False,
                "description": "Append to an existing file when true.",
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        path = _resolve_safe_path(
            self.root_dir,
            _argument_text(arguments, "path", "filename", "file"),
        )
        content = str(
            arguments.get("content", arguments.get("text", arguments.get("body", "")))
        )
        append = _coerce_bool(arguments.get("append", False), default=False)

        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with path.open(mode, encoding="utf-8", newline="") as f:
            f.write(content)
        return {
            "path": str(path.relative_to(self.root_dir)).replace("\\", "/"),
            "bytes_written": len(content.encode("utf-8")),
            "appended": append,
            "size_bytes": path.stat().st_size,
        }


class SearchFilesTool(BaseTool):
    name = "search_files"
    description = (
        "Search file names and supported text-readable file contents inside the configured root. "
        "Use this when you know the topic but not which file contains it."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Text to search for in file names and text file contents. Aliases like text or pattern are also accepted.",
            },
            "path": {
                "type": "string",
                "description": "Optional relative directory path. Aliases like directory or subdir are also accepted.",
            },
            "recursive": {
                "type": "boolean",
                "default": True,
                "description": "When true, search nested folders below path.",
            },
            "case_sensitive": {
                "type": "boolean",
                "default": False,
                "description": "When true, preserve case when matching.",
            },
            "filename_only": {
                "type": "boolean",
                "default": False,
                "description": "When true, search file names only and skip file contents.",
            },
            "offset": {
                "type": "integer",
                "minimum": 0,
                "default": 0,
                "description": "Optional zero-based result offset for pagination.",
            },
            "max_results": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "default": 20,
                "description": "Maximum number of matching files to return.",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        query = _argument_text(arguments, "query", "text", "pattern")
        if not query:
            raise SkillValidationError("query is required.")
        subpath = _normalize_relative_path_input(
            _argument_text(arguments, "path", "directory", "subdir", default="")
        )
        target = self.root_dir if not subpath else _resolve_safe_path(self.root_dir, subpath)
        if not target.exists():
            raise SkillValidationError(f"Path does not exist: {subpath or '.'}")
        if not target.is_dir():
            raise SkillValidationError(f"Path is not a directory: {subpath}")

        recursive = _coerce_bool(arguments.get("recursive", True), default=True)
        case_sensitive = _coerce_bool(arguments.get("case_sensitive", False), default=False)
        filename_only = _coerce_bool(arguments.get("filename_only", False), default=False)
        offset = _coerce_bounded_int(arguments.get("offset", 0), default=0, minimum=0)
        max_results = _coerce_bounded_int(
            arguments.get("max_results", 20),
            default=20,
            minimum=1,
            maximum=200,
        )

        pending_dirs = [target]
        seen_dirs: Set[Path] = set()
        root_resolved = self.root_dir.resolve()
        matches = []
        searched_file_count = 0
        skipped_count = 0

        while pending_dirs:
            current_dir = pending_dirs.pop()
            try:
                current_resolved = current_dir.resolve()
                current_resolved.relative_to(root_resolved)
            except (OSError, RuntimeError, ValueError):
                skipped_count += 1
                continue
            if current_resolved in seen_dirs:
                continue
            seen_dirs.add(current_resolved)

            try:
                children = sorted(current_dir.iterdir(), key=lambda item: item.name.lower())
            except OSError:
                skipped_count += 1
                continue

            for item in children:
                try:
                    if item.is_symlink():
                        skipped_count += 1
                        continue
                    item_resolved = item.resolve()
                    item_resolved.relative_to(root_resolved)
                except (OSError, RuntimeError, ValueError):
                    skipped_count += 1
                    continue

                try:
                    if item.is_dir():
                        if recursive:
                            pending_dirs.append(item)
                        continue
                    if not item.is_file():
                        continue
                except OSError:
                    skipped_count += 1
                    continue

                searched_file_count += 1
                relative_path = str(item.relative_to(self.root_dir)).replace("\\", "/")
                path_haystack = relative_path if case_sensitive else relative_path.lower()
                query_haystack = query if case_sensitive else query.lower()
                filename_match = query_haystack in path_haystack
                content_match = None

                if not filename_only and item.suffix.lower() in READABLE_TEXT_EXTENSIONS:
                    try:
                        content_match = _first_content_match(
                            read_supported_file_text(item, TEXT_FILE_EXTENSIONS)[0],
                            query,
                            case_sensitive=case_sensitive,
                        )
                    except Exception:
                        skipped_count += 1
                        continue

                if not filename_match and not content_match:
                    continue

                matches.append(
                    {
                        "relative_path": relative_path,
                        "name": item.name,
                        "size_bytes": item.stat().st_size,
                        "match_types": [
                            label
                            for label, matched in (("filename", filename_match), ("content", bool(content_match)))
                            if matched
                        ],
                        "line_number": content_match.get("line_number") if content_match else None,
                        "excerpt": content_match.get("excerpt") if content_match else "",
                        "match_count": content_match.get("match_count", 1) if content_match else 1,
                    }
                )

            if not recursive:
                break

        matches.sort(
            key=lambda item: (
                "filename" not in item.get("match_types", []),
                -int(item.get("match_count", 0) or 0),
                str(item.get("relative_path", "")).lower(),
            )
        )
        total_matches = len(matches)
        limited_items = matches[offset:offset + max_results]
        remaining_count = max(0, total_matches - (offset + len(limited_items)))
        return {
            "items": limited_items,
            "query": query,
            "path": subpath or ".",
            "recursive": recursive,
            "case_sensitive": case_sensitive,
            "filename_only": filename_only,
            "searched_file_count": searched_file_count,
            "total_matches": total_matches,
            "returned_count": len(limited_items),
            "remaining_count": remaining_count,
            "offset": offset,
            "max_results": max_results,
            "has_more": remaining_count > 0,
            "next_offset": (offset + len(limited_items)) if remaining_count > 0 else None,
            "skipped_count": skipped_count,
        }


class FilesystemSkill(BaseSkill):
    name = "filesystem"
    description = "Root-sandboxed file tools for listing, reading, writing, and searching files."
    version = "1.3.0"
    tags = ["filesystem", "io"]

    def __init__(self, root_dir: str = "./scratch") -> None:
        super().__init__()
        self.root_dir = Path(root_dir).resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def create_tools(self) -> Sequence[BaseTool]:
        return [
            ListFilesTool(self.root_dir),
            ReadTextTool(self.root_dir),
            WriteTextTool(self.root_dir),
            SearchFilesTool(self.root_dir),
        ]


def create_skill(root_dir: str = "./scratch") -> BaseSkill:
    return FilesystemSkill(root_dir=root_dir)

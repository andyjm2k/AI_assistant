"""Built-in filesystem skill with root-path sandboxing."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Sequence, Set

from src.skills.base import BaseSkill, BaseTool
from src.skills.exceptions import SkillValidationError
from src.skills.models import SkillContext


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


class ListFilesTool(BaseTool):
    name = "list_files"
    description = "List files in the configured skill root directory, with optional recursive traversal."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Optional relative directory path."},
            "recursive": {
                "type": "boolean",
                "default": False,
                "description": "When true, include nested files/directories under the selected path.",
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
        subpath = _normalize_relative_path_input(str(arguments.get("path", "")))
        target = self.root_dir if not subpath else _resolve_safe_path(self.root_dir, subpath)
        if not target.exists():
            raise SkillValidationError(f"Path does not exist: {subpath or '.'}")
        if not target.is_dir():
            raise SkillValidationError(f"Path is not a directory: {subpath}")

        recursive = _coerce_bool(arguments.get("recursive", False), default=False)
        max_entries_raw = arguments.get("max_entries", 100)
        try:
            max_entries = int(max_entries_raw or 100)
        except (TypeError, ValueError) as exc:
            raise SkillValidationError("max_entries must be an integer.") from exc
        max_entries = max(1, min(max_entries, 500))

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
        limited_items = entries[:max_entries]
        return {
            "items": limited_items,
            "root": str(self.root_dir),
            "path": subpath or ".",
            "recursive": recursive,
            "count": len(limited_items),
            "total_count": total_count,
            "skipped_count": skipped_count,
        }


class ReadTextTool(BaseTool):
    name = "read_text"
    description = "Read UTF-8 text content from a file inside the configured root."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path."},
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    async def run(self, arguments: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        path = _resolve_safe_path(self.root_dir, str(arguments.get("path", "")))
        if not path.exists():
            raise SkillValidationError(f"File does not exist: {arguments.get('path', '')}")
        if not path.is_file():
            raise SkillValidationError("Path is not a file.")
        content = path.read_text(encoding="utf-8")
        return {
            "path": str(path.relative_to(self.root_dir)).replace("\\", "/"),
            "content": content,
            "size_bytes": len(content.encode("utf-8")),
        }


class WriteTextTool(BaseTool):
    name = "write_text"
    description = "Write UTF-8 text content to a file inside the configured root."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path."},
            "content": {"type": "string", "description": "Text content to write."},
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
        path = _resolve_safe_path(self.root_dir, str(arguments.get("path", "")))
        content = str(arguments.get("content", ""))
        append = bool(arguments.get("append", False))

        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with path.open(mode, encoding="utf-8", newline="") as f:
            f.write(content)
        return {
            "path": str(path.relative_to(self.root_dir)).replace("\\", "/"),
            "bytes_written": len(content.encode("utf-8")),
            "appended": append,
        }


class FilesystemSkill(BaseSkill):
    name = "filesystem"
    description = "Root-sandboxed text file tools for listing, reading, and writing files."
    version = "1.1.0"
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
        ]


def create_skill(root_dir: str = "./scratch") -> BaseSkill:
    return FilesystemSkill(root_dir=root_dir)

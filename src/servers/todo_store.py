"""
Persistent todo list storage per user. One JSON file per user under todo_data/.
All user keys are sanitized to prevent path traversal; writes are atomic.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# Project root: this file is src/servers/todo_store.py -> parent.parent = project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# Default storage directory for todo files (configurable via env)
TODO_DATA_DIR = Path(os.getenv("TODO_DATA_PATH", str(_PROJECT_ROOT / "todo_data")))

# Allowed characters for user key in filename; replace any other with underscore
_USER_KEY_SAFE_RE = re.compile(r"[^a-zA-Z0-9_.-]")


def sanitize_user_key(user_key: str) -> str:
    """
    Sanitize user key for safe use as filename component. Prevents path traversal.
    Only [a-zA-Z0-9_.-] are kept; all other characters replaced with '_'.
    Empty or only-unsafe keys become 'default'.
    """
    if not user_key or not user_key.strip():
        return "default"
    # Remove path separators and any path-like components
    key = user_key.strip().replace("/", "_").replace("\\", "_")
    key = _USER_KEY_SAFE_RE.sub("_", key)
    # Collapse multiple underscores and strip
    key = re.sub(r"_+", "_", key).strip("_")
    return key if key else "default"


def _get_file_path(user_key: str) -> Path:
    """Return the Path for the todo JSON file for the given (sanitized) user key."""
    safe = sanitize_user_key(user_key)
    return TODO_DATA_DIR / f"{safe}.json"


def _ensure_dir() -> None:
    """Ensure the todo data directory exists."""
    TODO_DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_tasks(user_key: str) -> List[str]:
    """
    Load the list of tasks for the given user key. Returns empty list if file missing or invalid.
    """
    meta = load_tasks_with_meta(user_key)
    return meta["tasks"]


def load_tasks_with_meta(user_key: str) -> dict:
    """
    Load tasks and updated_at for the given user key. Returns {"tasks": [], "updated_at": None} if missing/invalid.
    """
    path = _get_file_path(user_key)
    if not path.exists():
        return {"tasks": [], "updated_at": None}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            return {"tasks": [], "updated_at": data.get("updated_at")}
        return {
            "tasks": [str(t) for t in tasks],
            "updated_at": data.get("updated_at"),
        }
    except (json.JSONDecodeError, OSError):
        return {"tasks": [], "updated_at": None}


def save_tasks(user_key: str, tasks: List[str]) -> None:
    """
    Save the list of tasks for the given user key. Uses atomic write (temp file then rename).
    """
    _ensure_dir()
    path = _get_file_path(user_key)
    # Write to temp file in same directory so rename is atomic on same filesystem
    temp_path = path.with_suffix(path.suffix + ".tmp")
    data = {
        "tasks": list(tasks),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    temp_path.write_text(raw, encoding="utf-8")
    temp_path.replace(path)


def add_task(user_key: str, task_description: str) -> List[str]:
    """Append a task and save. Returns the updated list of tasks."""
    tasks = load_tasks(user_key)
    tasks.append(task_description.strip())
    save_tasks(user_key, tasks)
    return tasks


def update_task(user_key: str, task_id: int, task_description: str) -> List[str]:
    """
    Update task at 1-based index task_id. Raises ValueError if task_id out of range.
    Returns the updated list of tasks.
    """
    tasks = load_tasks(user_key)
    if task_id < 1 or task_id > len(tasks):
        raise ValueError("Invalid task ID")
    tasks[task_id - 1] = task_description.strip()
    save_tasks(user_key, tasks)
    return tasks


def delete_task(user_key: str, task_id: int) -> List[str]:
    """
    Remove task at 1-based index task_id. Raises ValueError if task_id out of range.
    Returns the updated list of tasks.
    """
    tasks = load_tasks(user_key)
    if task_id < 1 or task_id > len(tasks):
        raise ValueError("Invalid task ID")
    tasks.pop(task_id - 1)
    save_tasks(user_key, tasks)
    return tasks


def clear_tasks(user_key: str) -> List[str]:
    """Clear all tasks for the user. Returns empty list."""
    save_tasks(user_key, [])
    return []

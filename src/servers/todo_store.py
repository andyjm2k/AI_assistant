"""
Persistent todo + scheduler storage per user.

Storage format is backward compatible with legacy {"tasks": ["..."]} files while
supporting structured scheduled and recurring task items.
"""

import calendar
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Project root: this file is src/servers/todo_store.py -> parent.parent = project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# Default storage directory for todo files (configurable via env)
TODO_DATA_DIR = Path(os.getenv("TODO_DATA_PATH", str(_PROJECT_ROOT / "todo_data")))

# Allowed characters for user key in filename; replace any other with underscore
_USER_KEY_SAFE_RE = re.compile(r"[^a-zA-Z0-9_.-]")
_TASK_SCHEMA_VERSION = 2
_REPEAT_FREQUENCIES = {"hourly", "daily", "weekly", "monthly", "yearly"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("Invalid ISO datetime format.") from exc
    else:
        raise ValueError("Datetime must be an ISO-8601 string.")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_schedule_datetime(value: Any) -> Optional[str]:
    dt = _parse_datetime(value)
    return _iso_utc(dt) if dt else None


def _normalize_recurrence(recurrence: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if recurrence is None:
        return None
    if not isinstance(recurrence, dict):
        raise ValueError("recurrence must be an object.")
    frequency = str(recurrence.get("frequency", "")).strip().lower()
    if not frequency:
        raise ValueError("recurrence.frequency is required.")
    if frequency not in _REPEAT_FREQUENCIES:
        supported = ", ".join(sorted(_REPEAT_FREQUENCIES))
        raise ValueError(f"Unsupported recurrence frequency. Use one of: {supported}.")
    interval_raw = recurrence.get("interval", 1)
    try:
        interval = int(interval_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("recurrence.interval must be an integer.") from exc
    if interval < 1:
        raise ValueError("recurrence.interval must be >= 1.")
    if interval > 10000:
        raise ValueError("recurrence.interval is too large.")
    return {"frequency": frequency, "interval": interval}


def _add_months(dt: datetime, months: int) -> datetime:
    month0 = (dt.month - 1) + months
    year = dt.year + (month0 // 12)
    month = (month0 % 12) + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _next_occurrence(anchor: datetime, recurrence: Dict[str, Any]) -> datetime:
    frequency = recurrence["frequency"]
    interval = recurrence["interval"]
    if frequency == "hourly":
        return anchor + timedelta(hours=interval)
    if frequency == "daily":
        return anchor + timedelta(days=interval)
    if frequency == "weekly":
        return anchor + timedelta(weeks=interval)
    if frequency == "monthly":
        return _add_months(anchor, interval)
    if frequency == "yearly":
        return _add_months(anchor, interval * 12)
    raise ValueError("Unsupported recurrence frequency.")


def _advance_after(anchor: datetime, recurrence: Dict[str, Any], after: datetime) -> datetime:
    current = anchor
    for _ in range(10000):
        if current > after:
            return current
        current = _next_occurrence(current, recurrence)
    raise ValueError("Could not compute next recurrence (too many iterations).")


def _sort_key(item: Dict[str, Any]) -> tuple:
    next_run = _parse_datetime(item.get("next_run_at"))
    created = _parse_datetime(item.get("created_at")) or datetime.max.replace(tzinfo=timezone.utc)
    desc = str(item.get("description", "")).lower()
    if next_run is None:
        return (1, datetime.max.replace(tzinfo=timezone.utc), created, desc)
    return (0, next_run, created, desc)


def _ordered_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(items, key=_sort_key)


def _build_task_item(
    description: str,
    *,
    scheduled_for: Optional[str] = None,
    next_run_at: Optional[str] = None,
    recurrence: Optional[Dict[str, Any]] = None,
    created_at: Optional[str] = None,
    updated_at: Optional[str] = None,
    last_completed_at: Optional[str] = None,
    task_uid: Optional[str] = None,
) -> Dict[str, Any]:
    if not description or not description.strip():
        raise ValueError("Task description cannot be empty.")
    now_iso = _iso_utc(_utc_now())
    normalized_schedule = _normalize_schedule_datetime(scheduled_for) if scheduled_for is not None else None
    normalized_recurrence = _normalize_recurrence(recurrence)
    normalized_next = _normalize_schedule_datetime(next_run_at) if next_run_at is not None else normalized_schedule
    if normalized_recurrence and normalized_next is None:
        normalized_next = now_iso
    return {
        "id": task_uid or uuid.uuid4().hex,
        "description": description.strip(),
        "scheduled_for": normalized_schedule,
        "next_run_at": normalized_next,
        "recurrence": normalized_recurrence,
        "created_at": _normalize_schedule_datetime(created_at) if created_at is not None else now_iso,
        "updated_at": _normalize_schedule_datetime(updated_at) if updated_at is not None else now_iso,
        "last_completed_at": _normalize_schedule_datetime(last_completed_at) if last_completed_at is not None else None,
    }


def _normalize_loaded_item(raw_item: Any, *, fallback_updated_at: Optional[str], ordinal: int) -> Optional[Dict[str, Any]]:
    fallback_dt = _parse_datetime(fallback_updated_at) or _utc_now()
    fallback_iso = _iso_utc(fallback_dt + timedelta(microseconds=ordinal))
    if isinstance(raw_item, str):
        return _build_task_item(raw_item, created_at=fallback_iso, updated_at=fallback_iso)
    if not isinstance(raw_item, dict):
        return None
    description = str(raw_item.get("description", "")).strip()
    if not description:
        # Backward-compat key
        description = str(raw_item.get("taskDescription", "")).strip()
    if not description:
        return None
    recurrence = raw_item.get("recurrence")
    return _build_task_item(
        description,
        scheduled_for=raw_item.get("scheduled_for", raw_item.get("scheduledFor")),
        next_run_at=raw_item.get("next_run_at", raw_item.get("nextRunAt")),
        recurrence=recurrence if isinstance(recurrence, dict) else None,
        created_at=raw_item.get("created_at", raw_item.get("createdAt", fallback_iso)),
        updated_at=raw_item.get("updated_at", raw_item.get("updatedAt", fallback_iso)),
        last_completed_at=raw_item.get("last_completed_at", raw_item.get("lastCompletedAt")),
        task_uid=str(raw_item.get("id") or raw_item.get("task_id") or uuid.uuid4().hex),
    )


def _load_items_with_meta(user_key: str) -> Dict[str, Any]:
    path = _get_file_path(user_key)
    if not path.exists():
        return {"task_items": [], "updated_at": None}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return {"task_items": [], "updated_at": None}

    if not isinstance(data, dict):
        return {"task_items": [], "updated_at": None}

    updated_at = data.get("updated_at")
    raw_items = data.get("task_items")
    if not isinstance(raw_items, list):
        raw_items = data.get("tasks")
    if not isinstance(raw_items, list):
        raw_items = []

    items: List[Dict[str, Any]] = []
    for idx, raw_item in enumerate(raw_items):
        item = _normalize_loaded_item(raw_item, fallback_updated_at=updated_at, ordinal=idx)
        if item:
            items.append(item)
    return {"task_items": items, "updated_at": updated_at}


def _save_items(user_key: str, items: List[Dict[str, Any]]) -> None:
    _ensure_dir()
    path = _get_file_path(user_key)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    now_iso = _iso_utc(_utc_now())
    ordered = _ordered_items(items)
    data = {
        "version": _TASK_SCHEMA_VERSION,
        # Legacy field preserved for compatibility with old clients.
        "tasks": [item["description"] for item in ordered],
        "task_items": items,
        "updated_at": now_iso,
    }
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    temp_path.write_text(raw, encoding="utf-8")
    temp_path.replace(path)


def _task_item_for_index(items: List[Dict[str, Any]], task_id: int) -> Dict[str, Any]:
    ordered = _ordered_items(items)
    if task_id < 1 or task_id > len(ordered):
        raise ValueError("Invalid task ID")
    target_id = ordered[task_id - 1]["id"]
    for item in items:
        if item.get("id") == target_id:
            return item
    raise ValueError("Invalid task ID")


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
    Load ordered task descriptions for the given user key.
    Scheduled tasks are returned in chronological order, followed by unscheduled tasks.
    """
    meta = load_tasks_with_meta(user_key)
    return meta["tasks"]


def load_tasks_with_meta(user_key: str) -> dict:
    """
    Load ordered tasks and metadata for the given user key.
    Returns {"tasks": [], "task_items": [], "updated_at": None} when missing/invalid.
    """
    loaded = _load_items_with_meta(user_key)
    ordered = _ordered_items(loaded["task_items"])
    return {
        "tasks": [str(item.get("description", "")) for item in ordered],
        "task_items": ordered,
        "updated_at": loaded.get("updated_at"),
    }


def save_tasks(user_key: str, tasks: List[str]) -> None:
    """
    Save tasks for the given user key using scheduler-aware schema.
    Accepts legacy list[str] and preserves task order.
    """
    now = _utc_now()
    items: List[Dict[str, Any]] = []
    for idx, task in enumerate(tasks):
        if isinstance(task, dict):
            normalized = _normalize_loaded_item(task, fallback_updated_at=_iso_utc(now), ordinal=idx)
            if normalized:
                items.append(normalized)
            continue
        text = str(task).strip()
        if not text:
            continue
        created = _iso_utc(now + timedelta(microseconds=idx))
        items.append(_build_task_item(text, created_at=created, updated_at=created))
    _save_items(user_key, items)


def add_task(
    user_key: str,
    task_description: str,
    scheduled_for: Optional[str] = None,
    recurrence: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Append a task (optionally scheduled/repeating) and return ordered descriptions."""
    desc = (task_description or "").strip()
    if not desc:
        raise ValueError("Task description is required.")
    loaded = _load_items_with_meta(user_key)
    items = loaded["task_items"]
    item = _build_task_item(desc, scheduled_for=scheduled_for, recurrence=recurrence)
    items.append(item)
    _save_items(user_key, items)
    return load_tasks(user_key)


def update_task(
    user_key: str,
    task_id: int,
    task_description: Optional[str] = None,
    *,
    scheduled_for: Optional[str] = None,
    recurrence: Optional[Dict[str, Any]] = None,
    clear_schedule: bool = False,
    clear_recurrence: bool = False,
) -> List[str]:
    """
    Update task at 1-based index task_id.
    Supports description updates plus schedule/recurrence edits.
    Raises ValueError if task_id out of range or payload invalid.
    """
    loaded = _load_items_with_meta(user_key)
    items = loaded["task_items"]
    target = _task_item_for_index(items, task_id)

    did_change = False
    now_iso = _iso_utc(_utc_now())

    if task_description is not None:
        desc = task_description.strip()
        if not desc:
            raise ValueError("Task description is required.")
        target["description"] = desc
        did_change = True

    if clear_recurrence:
        target["recurrence"] = None
        did_change = True
    elif recurrence is not None:
        target["recurrence"] = _normalize_recurrence(recurrence)
        did_change = True

    if clear_schedule:
        target["scheduled_for"] = None
        if not target.get("recurrence"):
            target["next_run_at"] = None
        did_change = True
    elif scheduled_for is not None:
        normalized_schedule = _normalize_schedule_datetime(scheduled_for)
        target["scheduled_for"] = normalized_schedule
        target["next_run_at"] = normalized_schedule
        did_change = True

    # Coherency rules when recurrence exists.
    if target.get("recurrence") and not target.get("next_run_at"):
        target["next_run_at"] = target.get("scheduled_for") or now_iso
        did_change = True

    if not target.get("recurrence") and target.get("scheduled_for") and not target.get("next_run_at"):
        target["next_run_at"] = target.get("scheduled_for")
        did_change = True

    if not did_change:
        raise ValueError("No update fields provided.")

    target["updated_at"] = now_iso
    _save_items(user_key, items)
    return load_tasks(user_key)


def delete_task(user_key: str, task_id: int) -> List[str]:
    """
    Remove task at 1-based index task_id. Raises ValueError if task_id out of range.
    Returns the updated ordered list of task descriptions.
    """
    loaded = _load_items_with_meta(user_key)
    items = loaded["task_items"]
    target = _task_item_for_index(items, task_id)
    items[:] = [item for item in items if item.get("id") != target.get("id")]
    _save_items(user_key, items)
    return load_tasks(user_key)


def complete_task(user_key: str, task_id: int) -> Dict[str, Any]:
    """
    Complete task at 1-based index task_id.
    - One-time tasks are removed.
    - Repeating tasks are advanced to their next run time.
    Returns scheduler metadata including whether it was rescheduled.
    """
    loaded = _load_items_with_meta(user_key)
    items = loaded["task_items"]
    target = _task_item_for_index(items, task_id)
    recurrence = target.get("recurrence")
    now = _utc_now()
    now_iso = _iso_utc(now)

    if isinstance(recurrence, dict):
        normalized_recurrence = _normalize_recurrence(recurrence)
        anchor = (
            _parse_datetime(target.get("next_run_at"))
            or _parse_datetime(target.get("scheduled_for"))
            or now
        )
        next_run = _advance_after(_next_occurrence(anchor, normalized_recurrence), normalized_recurrence, now)
        target["recurrence"] = normalized_recurrence
        target["last_completed_at"] = now_iso
        target["next_run_at"] = _iso_utc(next_run)
        target["updated_at"] = now_iso
        _save_items(user_key, items)
        meta = load_tasks_with_meta(user_key)
        return {
            "rescheduled": True,
            "next_run_at": target["next_run_at"],
            "tasks": meta["tasks"],
            "task_items": meta["task_items"],
            "updated_at": meta.get("updated_at"),
        }

    items[:] = [item for item in items if item.get("id") != target.get("id")]
    _save_items(user_key, items)
    meta = load_tasks_with_meta(user_key)
    return {
        "rescheduled": False,
        "next_run_at": None,
        "tasks": meta["tasks"],
        "task_items": meta["task_items"],
        "updated_at": meta.get("updated_at"),
    }


def list_due_task_items(user_key: str, as_of: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return scheduled tasks that are due at or before as_of (UTC now by default).
    Unscheduled tasks are excluded.
    """
    cutoff = _parse_datetime(as_of) if as_of is not None else _utc_now()
    due: List[Dict[str, Any]] = []
    for item in load_tasks_with_meta(user_key).get("task_items", []):
        next_run = _parse_datetime(item.get("next_run_at"))
        if next_run is not None and next_run <= cutoff:
            due.append(item)
    return due


def clear_tasks(user_key: str) -> List[str]:
    """Clear all tasks for the user. Returns empty list."""
    _save_items(user_key, [])
    return []

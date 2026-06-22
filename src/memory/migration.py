"""Audit, backup, and idempotent migration from the legacy memory files."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import TaskRunRecord
from .personal_memory_service import PersonalMemoryService
from .repository import MemoryRepository
from .task_learning_service import TaskLearningService


LEGACY_FILES = (
    "embeddings.npy",
    "metadata.json",
    "config.json",
    "task_learning_events.jsonl",
)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup_legacy_memory(
    storage_path: str,
    backup_root: str = "./backups",
) -> Dict[str, Any]:
    source = Path(storage_path).resolve()
    destination = Path(backup_root).resolve() / f"memory-legacy-{_timestamp()}"
    destination.mkdir(parents=True, exist_ok=False)
    manifest: Dict[str, Any] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source),
        "destination": str(destination),
        "files": {},
    }
    for name in LEGACY_FILES:
        path = source / name
        if not path.exists():
            continue
        target = destination / name
        shutil.copy2(path, target)
        manifest["files"][name] = {
            "size": target.stat().st_size,
            "sha256": _sha256(target),
        }
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def load_legacy_metadata(storage_path: str) -> List[Dict[str, Any]]:
    path = Path(storage_path) / "metadata.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    memories = data.get("memories") if isinstance(data, dict) else []
    return [item for item in memories if isinstance(item, dict)]


def load_legacy_task_events(storage_path: str) -> List[Dict[str, Any]]:
    path = Path(storage_path) / "task_learning_events.jsonl"
    if not path.exists():
        return []
    events = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    return events


def audit_legacy_memory(storage_path: str) -> Dict[str, Any]:
    memories = load_legacy_metadata(storage_path)
    events = load_legacy_task_events(storage_path)
    categories = Counter(str(item.get("category") or "") for item in memories)
    sources = Counter(str(item.get("source") or "") for item in memories)
    normalized = Counter(
        " ".join(str(item.get("text") or "").lower().split())
        for item in memories
        if str(item.get("text") or "").strip()
    )
    task_count = sum(
        1
        for item in memories
        if str(item.get("category") or "") in {"task_experience", "task_learning"}
        or str(item.get("memory_type") or "") in {"task_experience", "task_learning"}
    )
    return {
        "memory_count": len(memories),
        "personal_candidate_count": len(memories) - task_count,
        "task_vector_count": task_count,
        "task_event_count": len(events),
        "categories": dict(categories),
        "sources": dict(sources),
        "unscoped_memory_count": sum(1 for item in memories if not item.get("user_key")),
        "exact_duplicate_groups": sum(1 for count in normalized.values() if count > 1),
        "exact_duplicate_extra_records": sum(count - 1 for count in normalized.values() if count > 1),
    }


class LegacyMemoryMigrator:
    def __init__(
        self,
        repository: MemoryRepository,
        personal_memory: PersonalMemoryService,
        task_learning: TaskLearningService,
    ):
        self.repository = repository
        self.personal_memory = personal_memory
        self.task_learning = task_learning

    @staticmethod
    def _legacy_run_id(event: Dict[str, Any], index: int) -> str:
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        existing = str(metadata.get("run_id") or event.get("run_id") or "").strip()
        if existing:
            return existing
        payload = json.dumps(
            {
                "timestamp": event.get("timestamp"),
                "task_description": event.get("task_description"),
                "status": event.get("status"),
                "index": index,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return f"legacy-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"

    async def migrate(
        self,
        storage_path: str,
        *,
        legacy_owner: Optional[str] = None,
    ) -> Dict[str, Any]:
        memories = load_legacy_metadata(storage_path)
        events = load_legacy_task_events(storage_path)
        report = {
            "personal_imported": 0,
            "personal_unchanged": 0,
            "personal_quarantined": 0,
            "task_runs_imported": 0,
            "task_runs_updated": 0,
            "task_vectors_ignored": 0,
            "errors": [],
        }

        for item in memories:
            category = str(item.get("category") or "").strip().lower()
            memory_type = str(item.get("memory_type") or "").strip().lower()
            if category in {"task_experience", "task_learning"} or memory_type in {
                "task_experience",
                "task_learning",
            }:
                report["task_vectors_ignored"] += 1
                continue
            owner = str(item.get("user_key") or legacy_owner or "").strip()
            if not owner:
                quarantined = self.repository.quarantine_legacy(
                    "memory",
                    item.get("id"),
                    "missing_owner",
                    item,
                )
                if quarantined:
                    report["personal_quarantined"] += 1
                continue
            try:
                record, action = await self.personal_memory.store(
                    namespace=owner,
                    text=str(item.get("text") or ""),
                    kind=category or "profile_fact",
                    source="legacy_import",
                    source_ref=str(item.get("id") or ""),
                    confidence=float(item.get("confidence") or 0.7),
                    importance=float(item.get("importance") or 0.5),
                    metadata={
                        "legacy_id": item.get("id"),
                        "legacy_source": item.get("source"),
                        "legacy_timestamp": item.get("timestamp"),
                    },
                )
                if action == "unchanged":
                    report["personal_unchanged"] += 1
                else:
                    report["personal_imported"] += 1
            except Exception as exc:
                quarantined = self.repository.quarantine_legacy(
                    "memory",
                    item.get("id"),
                    f"import_error:{type(exc).__name__}",
                    item,
                )
                if quarantined:
                    report["personal_quarantined"] += 1
                report["errors"].append(f"memory {item.get('id')}: {exc}")

        for index, event in enumerate(events):
            metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
            owner = str(metadata.get("user_key") or event.get("user_key") or "").strip()
            if not owner:
                self.repository.quarantine_legacy(
                    "task_event",
                    None,
                    "missing_owner",
                    event,
                )
                continue
            status = str(event.get("status") or "")
            outcome = self.task_learning.normalize_outcome(status)
            description = str(event.get("task_description") or "").strip()
            if not description:
                self.repository.quarantine_legacy(
                    "task_event",
                    None,
                    "missing_task_description",
                    event,
                )
                continue
            run = TaskRunRecord(
                run_id=self._legacy_run_id(event, index),
                namespace=owner,
                task_id=str(metadata.get("task_id")) if metadata.get("task_id") is not None else None,
                task_fingerprint=self.task_learning.fingerprint(description),
                task_description=description,
                status=status,
                confirmed_outcome=outcome,
                summary=str(event.get("summary") or ""),
                error=str(event.get("error") or ""),
                tool_usage=[str(value) for value in event.get("tool_names") or []],
                source_phase=str(metadata.get("source_phase") or "legacy_import"),
                metadata={"legacy_event": True, **metadata},
                finished_at=str(event.get("timestamp") or "") if outcome else None,
                recorded_at=str(event.get("timestamp") or "") or datetime.now(timezone.utc).isoformat(),
            )
            _, created = self.repository.upsert_task_run(run)
            report["task_runs_imported" if created else "task_runs_updated"] += 1
        return report

"""Persistence contract for memory services."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

from .models import (
    EmbeddingRecord,
    MemoryRecord,
    RetrievalCandidate,
    TaskLessonRecord,
    TaskRunRecord,
)


class MemoryRepository(Protocol):
    database_path: Path

    def upsert_memory(
        self,
        memory: MemoryRecord,
        embedding: Optional[EmbeddingRecord] = None,
    ) -> Tuple[MemoryRecord, str]:
        ...

    def set_memory_embedding(self, memory_id: str, embedding: EmbeddingRecord) -> None:
        ...

    def mark_embedding_failed(self, memory_id: str, error: str) -> None:
        ...

    def get_memory(self, namespace: str, memory_id: str) -> Optional[MemoryRecord]:
        ...

    def list_memories(
        self,
        namespace: str,
        kinds: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
        status: str = "active",
    ) -> List[MemoryRecord]:
        ...

    def count_memories(self, namespace: str, kinds: Optional[Sequence[str]] = None) -> int:
        ...

    def delete_memory(self, namespace: str, memory_id: str) -> bool:
        ...

    def semantic_candidates(
        self,
        namespace: str,
        kinds: Sequence[str],
    ) -> List[RetrievalCandidate]:
        ...

    def lexical_candidates(
        self,
        namespace: str,
        query: str,
        kinds: Sequence[str],
        limit: int,
    ) -> List[RetrievalCandidate]:
        ...

    def claim_extraction(
        self,
        idempotency_key: str,
        namespace: str,
        conversation_id: Optional[str],
        user_message_id: Optional[str],
        assistant_message_id: Optional[str],
        extractor_model: str,
        extractor_version: str,
    ) -> bool:
        ...

    def finish_extraction(
        self,
        idempotency_key: str,
        status: str,
        candidate_count: int,
        accepted_count: int,
        error: Optional[str] = None,
        *,
        namespace: str,
    ) -> None:
        ...

    def upsert_task_run(self, run: TaskRunRecord) -> Tuple[TaskRunRecord, bool]:
        ...

    def list_task_runs(
        self,
        namespace: str,
        limit: int = 50,
        outcome: Optional[str] = None,
    ) -> List[TaskRunRecord]:
        ...

    def upsert_task_lesson(self, lesson: TaskLessonRecord) -> TaskLessonRecord:
        ...

    def list_task_lessons(
        self,
        namespace: str,
        task_fingerprint: Optional[str] = None,
        limit: int = 50,
    ) -> List[TaskLessonRecord]:
        ...

    def delete_task_lesson(self, namespace: str, lesson_id: str) -> bool:
        ...

    def increment_metric(self, name: str, amount: int = 1) -> None:
        ...

    def metrics(self) -> Dict[str, int]:
        ...

    def list_namespaces(self) -> List[str]:
        ...

    def backup(self, destination: Path) -> Path:
        ...

    def export_namespace(self, namespace: str) -> Dict[str, Any]:
        ...

    def clear_namespace(self, namespace: str, include_task_data: bool = True) -> Dict[str, int]:
        ...

    def quarantine_legacy(
        self,
        source_type: str,
        legacy_id: Optional[str],
        reason: str,
        payload: Dict[str, Any],
    ) -> bool:
        ...

"""Typed records shared by the CATBot memory services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


PERSONAL_MEMORY_KINDS = {
    "profile_fact",
    "preference",
    "habit",
    "need",
    "relationship",
}
CONVERSATION_MEMORY_KINDS = PERSONAL_MEMORY_KINDS | {"episodic"}
PHILOSOPHER_MEMORY_KINDS = CONVERSATION_MEMORY_KINDS | {"philosopher_contemplation"}
ALL_MEMORY_KINDS = PHILOSOPHER_MEMORY_KINDS

LEGACY_KIND_MAP = {
    "fact": "profile_fact",
    "general": "profile_fact",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_namespace(namespace: str) -> str:
    value = str(namespace or "").strip()
    if not value:
        raise ValueError("Memory namespace is required")
    if len(value) > 200:
        raise ValueError("Memory namespace is too long")
    return value


def normalize_kind(kind: Optional[str]) -> str:
    value = str(kind or "profile_fact").strip().lower()
    value = LEGACY_KIND_MAP.get(value, value)
    if value not in ALL_MEMORY_KINDS:
        raise ValueError(f"Unsupported memory kind: {value}")
    return value


@dataclass
class EmbeddingRecord:
    provider: str
    model: str
    dimension: int
    embedding_version: str
    vector: List[float]
    created_at: str = field(default_factory=utc_now)


@dataclass
class MemoryRecord:
    id: str
    namespace: str
    kind: str
    text: str
    normalized_text: str
    content_hash: str
    subject: str = "user"
    memory_key: Optional[str] = None
    confidence: float = 0.8
    importance: float = 0.5
    source: str = "unknown"
    source_ref: Optional[str] = None
    conversation_id: Optional[str] = None
    turn_id: Optional[str] = None
    status: str = "active"
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    last_accessed_at: Optional[str] = None
    version: int = 1
    embedding_status: str = "pending"
    embedding_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, similarity: Optional[float] = None) -> Dict[str, Any]:
        data: Dict[str, Any] = dict(self.metadata)
        data.update(
            {
                "id": self.id,
                "namespace": self.namespace,
                "kind": self.kind,
                "category": self.kind,
                "text": self.text,
                "subject": self.subject,
                "memory_key": self.memory_key,
                "confidence": self.confidence,
                "importance": self.importance,
                "source": self.source,
                "source_ref": self.source_ref,
                "conversation_id": self.conversation_id,
                "turn_id": self.turn_id,
                "status": self.status,
                "valid_from": self.valid_from,
                "valid_to": self.valid_to,
                "expires_at": self.expires_at,
                "timestamp": self.created_at,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "version": self.version,
                "embedding_status": self.embedding_status,
            }
        )
        if similarity is not None:
            data["similarity"] = float(similarity)
        return data


@dataclass
class RetrievalCandidate:
    memory: MemoryRecord
    embedding: Optional[List[float]] = None
    embedding_provider: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_version: Optional[str] = None
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    final_score: float = 0.0


@dataclass
class TaskRunRecord:
    run_id: str
    namespace: str
    task_id: Optional[str]
    task_fingerprint: str
    task_description: str
    status: str
    confirmed_outcome: Optional[str]
    summary: str
    error: str
    tool_usage: List[str]
    source_phase: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    recorded_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "namespace": self.namespace,
            "task_id": self.task_id,
            "task_fingerprint": self.task_fingerprint,
            "task_description": self.task_description,
            "status": self.status,
            "confirmed_outcome": self.confirmed_outcome,
            "outcome": self.confirmed_outcome or "pending",
            "summary": self.summary,
            "error": self.error,
            "tool_usage": list(self.tool_usage),
            "source_phase": self.source_phase,
            "metadata": dict(self.metadata),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "recorded_at": self.recorded_at,
        }


@dataclass
class TaskLessonRecord:
    id: str
    namespace: str
    task_fingerprint: str
    lesson_key: str
    text: str
    recommendation: str
    preconditions: str
    evidence_count: int
    success_count: int
    failure_count: int
    confidence: float
    source_run_ids: List[str]
    tool_names: List[str]
    status: str = "active"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    embedding: Optional[EmbeddingRecord] = None

    def to_dict(self, similarity: Optional[float] = None) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "namespace": self.namespace,
            "task_fingerprint": self.task_fingerprint,
            "lesson_key": self.lesson_key,
            "text": self.text,
            "recommendation": self.recommendation,
            "preconditions": self.preconditions,
            "evidence_count": self.evidence_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "confidence": self.confidence,
            "source_run_ids": list(self.source_run_ids),
            "tool_names": list(self.tool_names),
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "category": "task_lesson",
            "memory_type": "task_lesson",
        }
        if similarity is not None:
            data["similarity"] = float(similarity)
        return data

"""Durable personal and episodic memory write lifecycle."""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .embedding_provider import EmbeddingProvider
from .models import MemoryRecord, normalize_kind, normalize_namespace, utc_now
from .repository import MemoryRepository


class PersonalMemoryService:
    def __init__(self, repository: MemoryRepository, embedding_provider: EmbeddingProvider):
        self.repository = repository
        self.embedding_provider = embedding_provider

    @staticmethod
    def normalize_text(text: str) -> str:
        return " ".join(str(text or "").strip().lower().split())

    @staticmethod
    def content_hash(normalized_text: str) -> str:
        return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

    @staticmethod
    def _clamp(value: Any, default: float) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        return max(0.0, min(1.0, number))

    @staticmethod
    def derive_memory_key(text: str, kind: str, provided: Optional[str] = None) -> Optional[str]:
        if provided:
            key = re.sub(r"[^a-z0-9_.-]+", "_", str(provided).strip().lower()).strip("_")
            return key[:120] or None
        lower = str(text or "").lower()
        patterns = (
            ("home_location", r"\b(?:i live|i am based|my home|my location)\b"),
            ("timezone", r"\b(?:my timezone|time zone)\b"),
            ("preferred_name", r"\b(?:call me|my name is|i go by)\b"),
            ("pronouns", r"\b(?:my pronouns|pronouns are)\b"),
            ("response_style", r"\b(?:prefer|like).{0,40}\b(?:answers?|responses?)\b"),
        )
        for key, pattern in patterns:
            if re.search(pattern, lower):
                return key
        if kind == "preference":
            topic = re.search(r"\bprefer(?:s|red)?\s+(.{3,60})", lower)
            if topic:
                normalized = re.sub(r"[^a-z0-9]+", "_", topic.group(1)).strip("_")
                return f"preference_{normalized[:60]}" if normalized else None
        return None

    async def store(
        self,
        *,
        namespace: str,
        text: str,
        kind: Optional[str] = None,
        subject: str = "user",
        memory_key: Optional[str] = None,
        confidence: float = 0.8,
        importance: float = 0.5,
        source: str = "explicit",
        source_ref: Optional[str] = None,
        conversation_id: Optional[str] = None,
        turn_id: Optional[str] = None,
        expires_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[MemoryRecord, str]:
        namespace = normalize_namespace(namespace)
        value = str(text or "").strip()
        if not value:
            raise ValueError("Memory text is required")
        if len(value) > 12000:
            raise ValueError("Memory text exceeds the 12000 character limit")
        normalized_kind = normalize_kind(kind)
        normalized_text = self.normalize_text(value)
        now = utc_now()
        record = MemoryRecord(
            id=f"mem_{uuid.uuid4().hex}",
            namespace=namespace,
            kind=normalized_kind,
            subject=str(subject or "user").strip()[:200] or "user",
            memory_key=self.derive_memory_key(value, normalized_kind, memory_key),
            text=value,
            normalized_text=normalized_text,
            content_hash=self.content_hash(normalized_text),
            confidence=self._clamp(confidence, 0.8),
            importance=self._clamp(importance, 0.5),
            source=str(source or "unknown").strip()[:100] or "unknown",
            source_ref=str(source_ref).strip()[:300] if source_ref else None,
            conversation_id=str(conversation_id).strip()[:200] if conversation_id else None,
            turn_id=str(turn_id).strip()[:200] if turn_id else None,
            valid_from=now,
            expires_at=expires_at,
            metadata=dict(metadata or {}),
        )
        stored, action = self.repository.upsert_memory(record)
        if action == "unchanged" and stored.embedding_status == "ready":
            return stored, action
        try:
            embedding = await self.embedding_provider.embed(stored.text)
            self.repository.set_memory_embedding(stored.id, embedding)
            stored.embedding_status = "ready"
            stored.embedding_error = None
        except Exception as exc:
            self.repository.mark_embedding_failed(stored.id, str(exc))
            stored.embedding_status = "failed"
            stored.embedding_error = str(exc)
        return stored, action

    def get(self, namespace: str, memory_id: str) -> Optional[MemoryRecord]:
        return self.repository.get_memory(namespace, memory_id)

    def list(
        self,
        namespace: str,
        kinds: Optional[Sequence[str]] = None,
        limit: Optional[int] = None,
    ) -> List[MemoryRecord]:
        normalized_kinds = [normalize_kind(kind) for kind in kinds] if kinds else None
        return self.repository.list_memories(namespace, normalized_kinds, limit)

    def delete(self, namespace: str, memory_id: str) -> bool:
        return self.repository.delete_memory(namespace, memory_id)

    def count(self, namespace: str, kinds: Optional[Sequence[str]] = None) -> int:
        normalized_kinds = [normalize_kind(kind) for kind in kinds] if kinds else None
        return self.repository.count_memories(namespace, normalized_kinds)

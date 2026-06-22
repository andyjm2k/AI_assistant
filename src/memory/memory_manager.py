"""Thin caller-facing facade over CATBot's typed memory services."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Sequence

from .context_builder import MemoryContextBuilder
from .embedding_provider import EmbeddingProvider
from .embeddings_client import EmbeddingsClient
from .extraction_service import ExtractionService
from .memory_extractor import MemoryExtractor
from .models import CONVERSATION_MEMORY_KINDS, normalize_kind, normalize_namespace
from .personal_memory_service import PersonalMemoryService
from .repository import MemoryRepository
from .retrieval_service import RetrievalService
from .sqlite_repository import SQLiteMemoryRepository
from .task_learning_service import TaskLearningService


class MemoryManager:
    """Stable API used by the proxy, Telegram, philosopher mode, and tools."""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        embeddings_client: Optional[EmbeddingsClient] = None,
        memory_extractor: Optional[MemoryExtractor] = None,
        repository: Optional[MemoryRepository] = None,
        default_namespace: Optional[str] = None,
    ):
        self.storage_path = storage_path or os.getenv("MEMORY_STORAGE_PATH", "./memory_data")
        self.default_namespace = (
            default_namespace
            or os.getenv("MEMORY_DEFAULT_NAMESPACE")
            or "legacy-local"
        ).strip()
        self.search_limit = int(os.getenv("MEMORY_SEARCH_LIMIT", "5"))
        self.similarity_threshold = float(os.getenv("MEMORY_SIMILARITY_THRESHOLD", "0.7"))
        self.auto_extract = os.getenv("MEMORY_AUTO_EXTRACT", "true").lower() == "true"
        self._task_learning_categories = {"task_experience", "task_learning", "task_lesson"}
        self._operational_state_pattern = re.compile(
            r"\b(todo|to-?do|task list|my tasks?|due tasks?|overdue tasks?|task execution|"
            r"task outcome memory|experience hints from similar tasks|repeat for similar tasks|"
            r"avoid for similar tasks|execution status|status update|awaiting confirmation|"
            r"paused awaiting feedback|pending tasks?|completed tasks?|cancelled tasks?|"
            r"task id|current state|list state|working:|done:|failed:)\b",
            re.IGNORECASE,
        )
        self._operational_list_pattern = re.compile(
            r"(?:^|\n)\s*(?:[-*]|\d+\.)\s+(?:task|todo|to-?do|due|overdue|pending|"
            r"completed|cancelled|in progress|status)\b",
            re.IGNORECASE,
        )

        self.embeddings_client = embeddings_client or EmbeddingsClient()
        if memory_extractor is not None:
            self.memory_extractor = memory_extractor
        else:
            try:
                self.memory_extractor = MemoryExtractor()
            except Exception:
                self.memory_extractor = None

        self.repository = repository or SQLiteMemoryRepository(self.storage_path)
        self.embedding_provider = EmbeddingProvider(self.embeddings_client)
        self.personal_memory = PersonalMemoryService(self.repository, self.embedding_provider)
        self.retrieval = RetrievalService(self.repository, self.embedding_provider)
        self.extraction = ExtractionService(
            self.repository,
            self.personal_memory,
            self.memory_extractor,
        )
        self.task_learning = TaskLearningService(self.repository, self.embedding_provider)
        self.context_builder = MemoryContextBuilder()

    def close(self) -> None:
        close = getattr(self.repository, "close", None)
        if callable(close):
            close()

    def _namespace(
        self,
        namespace: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        candidate = namespace or str((metadata or {}).get("user_key") or "").strip()
        return normalize_namespace(candidate or self.default_namespace)

    async def store_memory(
        self,
        text: str,
        category: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict] = None,
        *,
        namespace: Optional[str] = None,
        kind: Optional[str] = None,
        subject: str = "user",
        memory_key: Optional[str] = None,
        source_ref: Optional[str] = None,
        conversation_id: Optional[str] = None,
        turn_id: Optional[str] = None,
        confidence: float = 0.8,
        importance: float = 0.5,
    ) -> str:
        record, _ = await self.personal_memory.store(
            namespace=self._namespace(namespace, metadata),
            text=text,
            kind=kind or category,
            subject=subject,
            memory_key=memory_key or str((metadata or {}).get("memory_key") or "").strip() or None,
            confidence=confidence,
            importance=importance,
            source=source or "unknown",
            source_ref=source_ref,
            conversation_id=conversation_id,
            turn_id=turn_id,
            metadata=metadata,
        )
        return record.id

    async def search_memories(
        self,
        query: str,
        limit: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        category: Optional[str] = None,
        *,
        namespace: Optional[str] = None,
        purpose: str = "conversation",
        kinds: Optional[Sequence[str]] = None,
    ) -> List[Dict]:
        requested_kinds = list(kinds or [])
        if category:
            requested_kinds.append(category)
        return await self.retrieval.search(
            namespace=self._namespace(namespace),
            query=query,
            purpose=purpose,
            kinds=requested_kinds or None,
            limit=self.search_limit if limit is None else max(0, int(limit)),
            similarity_threshold=(
                self.similarity_threshold
                if similarity_threshold is None
                else float(similarity_threshold)
            ),
        )

    def get_memory(self, memory_id: str, *, namespace: Optional[str] = None) -> Optional[Dict]:
        record = self.personal_memory.get(self._namespace(namespace), memory_id)
        return record.to_dict() if record else None

    def get_memories_by_category(
        self,
        category: str,
        *,
        namespace: Optional[str] = None,
    ) -> List[Dict]:
        records = self.personal_memory.list(
            self._namespace(namespace),
            kinds=[normalize_kind(category)],
        )
        return [record.to_dict() for record in records]

    def delete_memory(self, memory_id: str, *, namespace: Optional[str] = None) -> bool:
        return self.personal_memory.delete(self._namespace(namespace), memory_id)

    def list_memories(
        self,
        limit: Optional[int] = None,
        *,
        namespace: Optional[str] = None,
        kinds: Optional[Sequence[str]] = None,
    ) -> List[Dict]:
        records = self.personal_memory.list(self._namespace(namespace), kinds=kinds, limit=limit)
        return [record.to_dict() for record in records]

    def count(
        self,
        *,
        namespace: Optional[str] = None,
        kinds: Optional[Sequence[str]] = None,
    ) -> int:
        return self.personal_memory.count(self._namespace(namespace), kinds=kinds)

    async def extract_memories_from_conversation(
        self,
        messages: List[Dict[str, Any]],
        max_memories: int = 3,
        *,
        namespace: Optional[str] = None,
        conversation_id: Optional[str] = None,
        user_message_id: Optional[str] = None,
        assistant_message_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> List[str]:
        if not self.auto_extract:
            return []
        return await self.extraction.extract(
            namespace=self._namespace(namespace),
            messages=messages,
            max_memories=max_memories,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            idempotency_key=idempotency_key,
        )

    def is_operational_memory_text(self, text: str) -> bool:
        normalized = " ".join(str(text or "").split())
        return bool(
            normalized
            and (
                self._operational_state_pattern.search(normalized)
                or self._operational_list_pattern.search(normalized)
            )
        )

    def should_store_as_conversational_memory(
        self,
        *,
        text: str,
        category: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        category_value = str(category or "").strip().lower()
        memory_type = str((metadata or {}).get("memory_type") or "").strip().lower()
        if category_value in self._task_learning_categories:
            return False
        if memory_type in self._task_learning_categories:
            return False
        if str(source or "").strip().lower() in {"task_execution", "task_scheduler", "status_system"}:
            return False
        return not self.is_operational_memory_text(text)

    def filter_memories_for_conversation_context(
        self,
        memories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        output = []
        for memory in memories or []:
            kind = str(memory.get("kind") or memory.get("category") or "").strip().lower()
            if kind == "fact":
                kind = "profile_fact"
            if kind not in CONVERSATION_MEMORY_KINDS:
                continue
            if self.should_store_as_conversational_memory(
                text=str(memory.get("text") or ""),
                category=kind,
                source=memory.get("source"),
                metadata=memory,
            ):
                output.append(memory)
        return output

    async def build_context(
        self,
        *,
        namespace: str,
        query: str,
        purpose: str = "conversation",
        max_items: int = 4,
        max_tokens: int = 500,
    ) -> Dict[str, Any]:
        memories = await self.search_memories(
            query=query,
            namespace=namespace,
            purpose=purpose,
            limit=max(max_items * 3, 8),
            similarity_threshold=float(
                os.getenv("MEMORY_AUTO_SEARCH_CANDIDATE_THRESHOLD", "0.45")
            ),
        )
        context, included = self.context_builder.build(
            memories,
            max_items=max_items,
            max_tokens=max_tokens,
        )
        return {"context": context, "memories": included, "count": len(included)}

    async def record_task_outcome(
        self,
        *,
        task_description: str,
        status: str,
        message: Optional[str] = None,
        summary: Optional[str] = None,
        error: Optional[str] = None,
        tool_names: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source: str = "task_execution",
        namespace: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        extra = dict(metadata or {})
        return await self.task_learning.record_outcome(
            namespace=self._namespace(namespace, extra),
            run_id=run_id or extra.get("run_id"),
            task_id=extra.get("task_id"),
            task_description=task_description,
            status=status,
            summary=summary or message or "",
            error=error or "",
            tool_names=tool_names,
            source_phase=str(extra.get("source_phase") or source),
            metadata=extra,
        )

    def list_task_learning_events(
        self,
        limit: int = 50,
        outcome: Optional[str] = None,
        *,
        namespace: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        runs = self.repository.list_task_runs(
            self._namespace(namespace),
            limit=limit,
            outcome=outcome,
        )
        return [run.to_dict() for run in runs]

    async def get_task_learning_context(
        self,
        task_description: str,
        limit: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        *,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        lessons = await self.task_learning.search_lessons(
            self._namespace(namespace),
            task_description,
            limit=limit if limit is not None else 6,
            similarity_threshold=similarity_threshold or 0.45,
        )
        return {
            "task_description": task_description,
            "successes": [lesson for lesson in lessons if lesson.get("success_count", 0) > 0],
            "failures": [lesson for lesson in lessons if lesson.get("failure_count", 0) > 0],
            "notes": [],
            "all": lessons,
        }

    async def build_task_execution_guidance(
        self,
        task_description: str,
        limit: int = 6,
        *,
        namespace: Optional[str] = None,
    ) -> str:
        return await self.task_learning.build_guidance(
            self._namespace(namespace),
            task_description,
            limit=limit,
        )

    def metrics(self) -> Dict[str, int]:
        return self.repository.metrics()

    def list_task_lessons(
        self,
        *,
        namespace: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        return [
            lesson.to_dict()
            for lesson in self.repository.list_task_lessons(
                self._namespace(namespace),
                limit=max(0, min(500, int(limit))),
            )
        ]

    async def rebuild_embeddings(self, namespace: Optional[str] = None) -> Dict[str, int]:
        namespaces = [self._namespace(namespace)] if namespace else self.repository.list_namespaces()
        rebuilt = 0
        failed = 0
        for current_namespace in namespaces:
            for record in self.repository.list_memories(current_namespace, status="active"):
                try:
                    embedding = await self.embedding_provider.embed(record.text)
                    self.repository.set_memory_embedding(record.id, embedding)
                    rebuilt += 1
                except Exception as exc:
                    self.repository.mark_embedding_failed(record.id, str(exc))
                    failed += 1
        return {"rebuilt": rebuilt, "failed": failed}

    def export_namespace(self, namespace: str) -> Dict[str, Any]:
        return self.repository.export_namespace(namespace)

    def clear_namespace(self, namespace: str, include_task_data: bool = True) -> Dict[str, int]:
        return self.repository.clear_namespace(namespace, include_task_data=include_task_data)

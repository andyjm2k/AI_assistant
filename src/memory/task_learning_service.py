"""Run-based task learning with aggregated, evidence-backed lessons."""

from __future__ import annotations

import hashlib
import re
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .embedding_provider import EmbeddingProvider
from .models import (
    TaskLessonRecord,
    TaskRunRecord,
    normalize_namespace,
    utc_now,
)
from .repository import MemoryRepository


class TaskLearningService:
    FINAL_SUCCESS = {"success", "completed", "confirmed_complete"}
    FINAL_FAILURE = {"failed", "failure", "error"}

    def __init__(self, repository: MemoryRepository, embedding_provider: EmbeddingProvider):
        self.repository = repository
        self.embedding_provider = embedding_provider

    @staticmethod
    def _clean(value: Any, max_chars: int = 1000) -> str:
        text = " ".join(str(value or "").strip().split())
        return text if len(text) <= max_chars else text[: max_chars - 3].rstrip() + "..."

    @classmethod
    def normalize_outcome(cls, status: str) -> Optional[str]:
        value = str(status or "").strip().lower()
        if value in cls.FINAL_SUCCESS:
            return "success"
        if value in cls.FINAL_FAILURE:
            return "failure"
        if value == "cancelled":
            return "cancelled"
        if value == "paused_awaiting_feedback":
            return "paused"
        return None

    @classmethod
    def fingerprint(cls, task_description: str) -> str:
        normalized = re.sub(r"\b\d+\b", "#", cls._clean(task_description, 500).lower())
        normalized = re.sub(r"[^a-z0-9#]+", " ", normalized)
        normalized = " ".join(normalized.split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]

    @classmethod
    def fallback_run_id(
        cls,
        namespace: str,
        task_id: Optional[Any],
        task_description: str,
        source_phase: str,
    ) -> str:
        payload = "|".join(
            [
                namespace,
                str(task_id or ""),
                cls._clean(task_description, 500),
                str(source_phase or ""),
            ]
        )
        return f"legacy-{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"

    async def record_outcome(
        self,
        *,
        namespace: str,
        run_id: Optional[str],
        task_id: Optional[Any],
        task_description: str,
        status: str,
        summary: str = "",
        error: str = "",
        tool_names: Optional[Sequence[str]] = None,
        source_phase: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        recorded_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        namespace = normalize_namespace(namespace)
        task_text = self._clean(task_description, 1000)
        if not task_text:
            raise ValueError("Task description is required")
        stable_run_id = self._clean(run_id, 200) or self.fallback_run_id(
            namespace,
            task_id,
            task_text,
            source_phase,
        )
        outcome = self.normalize_outcome(status)
        tools = list(dict.fromkeys(self._clean(tool, 100) for tool in (tool_names or []) if tool))
        now = recorded_at or utc_now()
        run = TaskRunRecord(
            run_id=stable_run_id,
            namespace=namespace,
            task_id=str(task_id) if task_id is not None else None,
            task_fingerprint=self.fingerprint(task_text),
            task_description=task_text,
            status=self._clean(status, 100),
            confirmed_outcome=outcome,
            summary=self._clean(summary, 2000),
            error=self._clean(error, 1200),
            tool_usage=tools,
            source_phase=self._clean(source_phase, 100),
            metadata=dict(metadata or {}),
            finished_at=now if outcome else None,
            recorded_at=now,
        )
        stored, created = self.repository.upsert_task_run(run)
        lesson = None
        if stored.confirmed_outcome in {"success", "failure", "cancelled"}:
            lesson = await self._aggregate_lesson(namespace, stored.task_fingerprint)
        return {
            "outcome": stored.confirmed_outcome or "pending",
            "run": stored.to_dict(),
            "created": created,
            "lesson": lesson.to_dict() if lesson else None,
            "memory_ids": [],
        }

    async def _aggregate_lesson(
        self,
        namespace: str,
        task_fingerprint: str,
    ) -> Optional[TaskLessonRecord]:
        runs = [
            run
            for run in self.repository.list_task_runs(namespace, limit=1000)
            if run.task_fingerprint == task_fingerprint and run.confirmed_outcome
        ]
        if not runs:
            return None
        successes = [run for run in runs if run.confirmed_outcome == "success"]
        failures = [
            run for run in runs if run.confirmed_outcome in {"failure", "cancelled"}
        ]
        tool_counter = Counter(tool for run in successes for tool in run.tool_usage)
        common_tools = [name for name, _ in tool_counter.most_common(5)]
        if successes and common_tools:
            recommendation = f"Use the proven tool sequence for this task family: {', '.join(common_tools)}."
        elif successes:
            recommendation = "Reuse the execution approach from the confirmed successful runs."
        elif failures:
            recommendation = "Review the recorded failure before retrying and change the execution approach."
        else:
            return None
        latest_failure = next((run.error or run.summary for run in failures if run.error or run.summary), "")
        preconditions = (
            f"Known failure to handle: {self._clean(latest_failure, 300)}"
            if latest_failure
            else ""
        )
        evidence_count = len(runs)
        majority = max(len(successes), len(failures))
        evidence_factor = min(0.25, evidence_count * 0.05)
        confidence = min(0.95, 0.5 + evidence_factor + (majority / evidence_count) * 0.2)
        text = recommendation
        if preconditions:
            text = f"{recommendation} {preconditions}"
        existing = self.repository.list_task_lessons(
            namespace,
            task_fingerprint=task_fingerprint,
            limit=10,
        )
        lesson_id = existing[0].id if existing else f"lesson_{uuid.uuid4().hex}"
        created_at = existing[0].created_at if existing else utc_now()
        embedding = None
        try:
            embedding = await self.embedding_provider.embed(text)
        except Exception:
            self.repository.increment_metric("task_lesson_embedding_failure")
        lesson = TaskLessonRecord(
            id=lesson_id,
            namespace=namespace,
            task_fingerprint=task_fingerprint,
            lesson_key="procedure",
            text=text,
            recommendation=recommendation,
            preconditions=preconditions,
            evidence_count=evidence_count,
            success_count=len(successes),
            failure_count=len(failures),
            confidence=confidence,
            source_run_ids=[run.run_id for run in runs],
            tool_names=common_tools,
            created_at=created_at,
            updated_at=utc_now(),
            embedding=embedding,
        )
        return self.repository.upsert_task_lesson(lesson)

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        a = np.asarray(left, dtype=np.float32)
        b = np.asarray(right, dtype=np.float32)
        if a.shape != b.shape or a.ndim != 1:
            return 0.0
        norm = float(np.linalg.norm(a) * np.linalg.norm(b))
        return float(np.dot(a, b) / norm) if norm > 0 else 0.0

    async def search_lessons(
        self,
        namespace: str,
        task_description: str,
        limit: int = 6,
        similarity_threshold: float = 0.45,
    ) -> List[Dict[str, Any]]:
        namespace = normalize_namespace(namespace)
        lessons = self.repository.list_task_lessons(namespace, limit=1000)
        if not lessons:
            return []
        query_embedding = None
        try:
            query_embedding = await self.embedding_provider.embed(task_description)
        except Exception:
            pass
        query_tokens = set(re.findall(r"[a-z0-9]+", task_description.lower()))
        ranked: List[Tuple[float, TaskLessonRecord]] = []
        for lesson in lessons:
            semantic = 0.0
            if (
                query_embedding
                and lesson.embedding
                and lesson.embedding.provider == query_embedding.provider
                and lesson.embedding.model == query_embedding.model
                and lesson.embedding.embedding_version == query_embedding.embedding_version
            ):
                semantic = self._cosine(query_embedding.vector, lesson.embedding.vector)
            lesson_tokens = set(re.findall(r"[a-z0-9]+", lesson.text.lower()))
            lexical = (
                len(query_tokens & lesson_tokens) / max(1, len(query_tokens))
                if query_tokens
                else 0.0
            )
            score = semantic * 0.75 + lexical * 0.15 + lesson.confidence * 0.10
            if semantic >= similarity_threshold or lexical > 0:
                ranked.append((score, lesson))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [lesson.to_dict(similarity=score) for score, lesson in ranked[: max(0, int(limit))]]

    async def build_guidance(
        self,
        namespace: str,
        task_description: str,
        limit: int = 4,
    ) -> str:
        lessons = await self.search_lessons(namespace, task_description, limit=limit)
        if not lessons:
            return ""
        lines = ["Evidence-backed guidance from prior confirmed task runs:"]
        for lesson in lessons:
            lines.append(
                f"- {lesson['recommendation']} "
                f"(confidence {lesson['confidence']:.2f}, evidence {lesson['evidence_count']}, "
                f"runs {', '.join(lesson['source_run_ids'][:5])})"
            )
            if lesson.get("preconditions"):
                lines.append(f"  Guardrail: {lesson['preconditions']}")
        return "\n".join(lines)

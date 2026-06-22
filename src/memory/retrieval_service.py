"""Namespace-first hybrid lexical and semantic retrieval."""

from __future__ import annotations

import math
import time
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

from .embedding_provider import EmbeddingProvider
from .models import (
    CONVERSATION_MEMORY_KINDS,
    PHILOSOPHER_MEMORY_KINDS,
    RetrievalCandidate,
    normalize_kind,
    normalize_namespace,
)
from .repository import MemoryRepository


PURPOSE_KINDS = {
    "conversation": CONVERSATION_MEMORY_KINDS,
    "personal": CONVERSATION_MEMORY_KINDS,
    "philosopher": PHILOSOPHER_MEMORY_KINDS,
}


class RetrievalService:
    def __init__(self, repository: MemoryRepository, embedding_provider: EmbeddingProvider):
        self.repository = repository
        self.embedding_provider = embedding_provider

    @staticmethod
    def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
        a = np.asarray(left, dtype=np.float32)
        b = np.asarray(right, dtype=np.float32)
        if a.shape != b.shape or a.ndim != 1:
            return 0.0
        left_norm = float(np.linalg.norm(a))
        right_norm = float(np.linalg.norm(b))
        if left_norm <= 0 or right_norm <= 0:
            return 0.0
        return float(np.dot(a, b) / (left_norm * right_norm))

    @staticmethod
    def allowed_kinds(
        purpose: str = "conversation",
        kinds: Optional[Sequence[str]] = None,
    ) -> List[str]:
        if kinds:
            return sorted({normalize_kind(kind) for kind in kinds})
        value = str(purpose or "conversation").strip().lower()
        if value not in PURPOSE_KINDS:
            raise ValueError(f"Unsupported memory retrieval purpose: {value}")
        return sorted(PURPOSE_KINDS[value])

    @staticmethod
    def _age_boost(created_at: str) -> float:
        try:
            from datetime import datetime, timezone

            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
            return max(0.0, 0.04 * math.exp(-age_days / 180.0))
        except Exception:
            return 0.0

    @staticmethod
    def _merge_candidate(
        combined: Dict[str, RetrievalCandidate],
        candidate: RetrievalCandidate,
    ) -> RetrievalCandidate:
        existing = combined.get(candidate.memory.id)
        if existing is None:
            combined[candidate.memory.id] = candidate
            return candidate
        if candidate.embedding is not None:
            existing.embedding = candidate.embedding
            existing.embedding_provider = candidate.embedding_provider
            existing.embedding_model = candidate.embedding_model
            existing.embedding_version = candidate.embedding_version
        existing.lexical_score = max(existing.lexical_score, candidate.lexical_score)
        existing.semantic_score = max(existing.semantic_score, candidate.semantic_score)
        return existing

    def _diversify(
        self,
        candidates: List[RetrievalCandidate],
        limit: int,
        lambda_weight: float = 0.78,
    ) -> List[RetrievalCandidate]:
        if len(candidates) <= limit:
            return candidates
        selected: List[RetrievalCandidate] = []
        remaining = list(candidates)
        while remaining and len(selected) < limit:
            if not selected:
                selected.append(remaining.pop(0))
                continue
            best_index = 0
            best_score = float("-inf")
            for index, candidate in enumerate(remaining):
                redundancy = 0.0
                if candidate.embedding:
                    redundancy = max(
                        (
                            self._cosine(candidate.embedding, chosen.embedding)
                            for chosen in selected
                            if chosen.embedding
                        ),
                        default=0.0,
                    )
                score = lambda_weight * candidate.final_score - (1.0 - lambda_weight) * redundancy
                if score > best_score:
                    best_score = score
                    best_index = index
            selected.append(remaining.pop(best_index))
        return selected

    async def search(
        self,
        *,
        namespace: str,
        query: str,
        purpose: str = "conversation",
        kinds: Optional[Sequence[str]] = None,
        limit: int = 5,
        similarity_threshold: float = 0.55,
    ) -> List[Dict]:
        namespace = normalize_namespace(namespace)
        text = str(query or "").strip()
        if not text:
            return []
        safe_limit = max(0, min(50, int(limit)))
        if safe_limit == 0:
            return []
        allowed = self.allowed_kinds(purpose, kinds)
        started = time.perf_counter()
        lexical = self.repository.lexical_candidates(
            namespace,
            text,
            allowed,
            max(20, safe_limit * 8),
        )
        semantic = self.repository.semantic_candidates(namespace, allowed)
        query_embedding = None
        if semantic:
            try:
                query_embedding = await self.embedding_provider.embed(text)
            except Exception:
                self.repository.increment_metric("retrieval_embedding_failure")

        compatible_semantic: List[RetrievalCandidate] = []
        if query_embedding:
            for candidate in semantic:
                if (
                    candidate.embedding_provider != query_embedding.provider
                    or candidate.embedding_model != query_embedding.model
                    or candidate.embedding_version != query_embedding.embedding_version
                    or not candidate.embedding
                    or len(candidate.embedding) != query_embedding.dimension
                ):
                    continue
                candidate.semantic_score = self._cosine(
                    query_embedding.vector,
                    candidate.embedding,
                )
                compatible_semantic.append(candidate)
            compatible_semantic.sort(key=lambda item: item.semantic_score, reverse=True)

        combined: Dict[str, RetrievalCandidate] = {}
        for rank, candidate in enumerate(lexical, start=1):
            target = self._merge_candidate(combined, candidate)
            target.lexical_score = max(target.lexical_score, 1.0 / (60.0 + rank))
        for rank, candidate in enumerate(compatible_semantic, start=1):
            target = self._merge_candidate(combined, candidate)
            if candidate.semantic_score >= float(similarity_threshold):
                target.semantic_score = candidate.semantic_score
                target.final_score += 1.0 / (60.0 + rank)

        lexical_ids = {candidate.memory.id for candidate in lexical}
        ranked: List[RetrievalCandidate] = []
        seen_text = set()
        for candidate in combined.values():
            if (
                candidate.memory.id not in lexical_ids
                and candidate.semantic_score < float(similarity_threshold)
            ):
                continue
            normalized = candidate.memory.normalized_text
            if normalized in seen_text:
                continue
            seen_text.add(normalized)
            semantic_component = max(0.0, candidate.semantic_score) * 0.62
            lexical_component = min(1.0, candidate.lexical_score * 60.0) * 0.20
            confidence_component = candidate.memory.confidence * 0.08
            importance_component = candidate.memory.importance * 0.06
            candidate.final_score += (
                semantic_component
                + lexical_component
                + confidence_component
                + importance_component
                + self._age_boost(candidate.memory.created_at)
            )
            ranked.append(candidate)
        ranked.sort(key=lambda item: item.final_score, reverse=True)
        selected = self._diversify(ranked, safe_limit)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        self.repository.increment_metric("retrieval_requests")
        self.repository.increment_metric("retrieval_candidates", len(combined))
        self.repository.increment_metric("retrieval_results", len(selected))
        self.repository.increment_metric("retrieval_latency_ms_total", elapsed_ms)
        output: List[Dict] = []
        for candidate in selected:
            score = candidate.semantic_score if candidate.semantic_score > 0 else candidate.final_score
            item = candidate.memory.to_dict(similarity=score)
            item["retrieval_score"] = candidate.final_score
            item["lexical_score"] = candidate.lexical_score
            item["semantic_score"] = candidate.semantic_score
            output.append(item)
        return output

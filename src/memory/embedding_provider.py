"""Embedding provider with explicit model identity."""

from __future__ import annotations

import asyncio
import math
import os
from urllib.parse import urlparse
from typing import List, Optional

from .embeddings_client import EmbeddingsClient
from .models import EmbeddingRecord


class EmbeddingProvider:
    def __init__(
        self,
        client: Optional[EmbeddingsClient] = None,
        embedding_version: Optional[str] = None,
    ):
        self.client = client or EmbeddingsClient()
        self.embedding_version = (
            embedding_version
            or os.getenv("MEMORY_EMBEDDING_VERSION")
            or "v1"
        ).strip()
        parsed = urlparse(str(getattr(self.client, "api_base", "") or ""))
        self.provider = (parsed.hostname or "local").lower()
        self.model = str(getattr(self.client, "model", "") or "unknown").strip()
        self.max_attempts = max(
            1,
            min(5, int(os.getenv("MEMORY_EMBEDDING_MAX_ATTEMPTS", "2"))),
        )

    def _record(self, vector: List[float]) -> EmbeddingRecord:
        if not vector:
            raise ValueError("Embedding provider returned an empty vector")
        clean = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in clean):
            raise ValueError("Embedding provider returned a non-finite vector")
        norm = math.sqrt(sum(value * value for value in clean))
        if norm <= 0:
            raise ValueError("Embedding provider returned a zero vector")
        normalized = [value / norm for value in clean]
        return EmbeddingRecord(
            provider=self.provider,
            model=self.model,
            dimension=len(normalized),
            embedding_version=self.embedding_version,
            vector=normalized,
        )

    async def embed(self, text: str) -> EmbeddingRecord:
        value = str(text or "").strip()
        if not value:
            raise ValueError("Text is required for embedding")
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                vector = await self.client.get_embedding(value)
                return self._record(vector)
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    await asyncio.sleep(0.15 * attempt)
        raise RuntimeError(f"Embedding failed after {self.max_attempts} attempt(s): {last_error}")

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingRecord]:
        values = [str(text or "").strip() for text in texts]
        if not values or any(not value for value in values):
            raise ValueError("Non-empty texts are required for batch embedding")
        batch_method = getattr(self.client, "get_embeddings_batch", None)
        if callable(batch_method):
            last_error = None
            for attempt in range(1, self.max_attempts + 1):
                try:
                    vectors = await batch_method(values)
                    return [self._record(vector) for vector in vectors]
                except Exception as exc:
                    last_error = exc
                    if attempt < self.max_attempts:
                        await asyncio.sleep(0.15 * attempt)
            raise RuntimeError(
                f"Batch embedding failed after {self.max_attempts} attempt(s): {last_error}"
            )
        return [await self.embed(value) for value in values]

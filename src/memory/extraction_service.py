"""Idempotent, evidence-backed automatic memory extraction."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional

from .memory_extractor import MemoryExtractor
from .models import normalize_kind, normalize_namespace
from .personal_memory_service import PersonalMemoryService
from .repository import MemoryRepository


class ExtractionService:
    def __init__(
        self,
        repository: MemoryRepository,
        personal_memory: PersonalMemoryService,
        extractor: Optional[MemoryExtractor],
    ):
        self.repository = repository
        self.personal_memory = personal_memory
        self.extractor = extractor
        self.extractor_version = (
            os.getenv("MEMORY_EXTRACTOR_VERSION") or "schema-v2"
        ).strip()
        self.min_user_messages = int(os.getenv("MEMORY_EXTRACT_MIN_USER_MESSAGES", "2"))
        self.min_user_chars = int(os.getenv("MEMORY_EXTRACT_MIN_USER_CHARS", "80"))
        self.allowed_confidence = {
            item.strip().lower()
            for item in os.getenv("MEMORY_EXTRACT_ALLOWED_CONFIDENCE", "high").split(",")
            if item.strip()
        } or {"high"}

    @staticmethod
    def _message_content(message: Dict[str, Any]) -> str:
        return str(message.get("content") or "").strip()

    def idempotency_key(
        self,
        *,
        namespace: str,
        messages: List[Dict[str, Any]],
        conversation_id: Optional[str],
        user_message_id: Optional[str],
        assistant_message_id: Optional[str],
    ) -> str:
        payload = {
            "namespace": namespace,
            "conversation_id": conversation_id or "",
            "user_message_id": user_message_id or "",
            "assistant_message_id": assistant_message_id or "",
            "extractor_version": self.extractor_version,
            "messages": [
                {
                    "role": str(message.get("role") or ""),
                    "content": self._message_content(message),
                }
                for message in messages
            ],
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _evidence_supported(evidence: str, user_text: str) -> bool:
        quote = " ".join(str(evidence or "").strip().lower().split())
        source = " ".join(str(user_text or "").strip().lower().split())
        return bool(quote and len(quote) >= 4 and quote in source)

    async def extract(
        self,
        *,
        namespace: str,
        messages: List[Dict[str, Any]],
        max_memories: int = 3,
        conversation_id: Optional[str] = None,
        user_message_id: Optional[str] = None,
        assistant_message_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> List[str]:
        namespace = normalize_namespace(namespace)
        if self.extractor is None:
            return []
        user_messages = [
            self._message_content(message)
            for message in messages
            if str(message.get("role") or "").lower() == "user"
            and self._message_content(message)
        ]
        user_text = "\n".join(user_messages)
        if len(user_messages) < self.min_user_messages or len(user_text) < self.min_user_chars:
            return []
        key = idempotency_key or self.idempotency_key(
            namespace=namespace,
            messages=messages,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
        )
        model = str(getattr(self.extractor, "model", "") or "unknown")
        if not self.repository.claim_extraction(
            key,
            namespace,
            conversation_id,
            user_message_id,
            assistant_message_id,
            model,
            self.extractor_version,
        ):
            return []

        candidates: List[Dict[str, Any]] = []
        stored_ids: List[str] = []
        try:
            candidates = await self.extractor.extract_memories(
                messages=messages,
                max_memories=max(0, min(10, int(max_memories))),
            )
            for candidate in candidates:
                confidence_label = str(candidate.get("confidence") or "").strip().lower()
                if confidence_label not in self.allowed_confidence:
                    continue
                evidence = str(candidate.get("evidence_quote") or "").strip()
                if not self._evidence_supported(evidence, user_text):
                    self.repository.increment_metric("extraction_rejected_evidence")
                    continue
                text = str(candidate.get("text") or "").strip()
                if not text:
                    continue
                try:
                    kind = normalize_kind(candidate.get("kind") or candidate.get("category"))
                except ValueError:
                    self.repository.increment_metric("extraction_rejected_kind")
                    continue
                record, _ = await self.personal_memory.store(
                    namespace=namespace,
                    text=text,
                    kind=kind,
                    subject=str(candidate.get("subject") or "user"),
                    memory_key=candidate.get("memory_key"),
                    confidence=0.95 if confidence_label == "high" else 0.7,
                    importance=0.6,
                    source="conversation",
                    source_ref=key,
                    conversation_id=conversation_id,
                    turn_id=assistant_message_id or user_message_id,
                    metadata={
                        "value": candidate.get("value"),
                        "evidence_quote": evidence,
                        "extractor_model": model,
                        "extractor_version": self.extractor_version,
                    },
                )
                stored_ids.append(record.id)
            self.repository.finish_extraction(
                key,
                "completed",
                len(candidates),
                len(stored_ids),
                namespace=namespace,
            )
            return stored_ids
        except Exception as exc:
            self.repository.finish_extraction(
                key,
                "failed",
                len(candidates),
                len(stored_ids),
                str(exc),
                namespace=namespace,
            )
            raise

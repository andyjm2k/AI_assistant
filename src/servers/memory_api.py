"""Authenticated, namespace-scoped memory API."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


class MemoryStoreRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    kind: Optional[str] = None
    category: Optional[str] = None
    subject: str = Field(default="user", max_length=200)
    memory_key: Optional[str] = Field(default=None, max_length=120)
    source: Optional[str] = Field(default="explicit", max_length=100)
    source_ref: Optional[str] = Field(default=None, max_length=300)
    conversation_id: Optional[str] = Field(default=None, max_length=200)
    turn_id: Optional[str] = Field(default=None, max_length=200)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=12000)
    purpose: str = Field(default="conversation", max_length=40)
    kinds: Optional[List[str]] = None
    category: Optional[str] = None
    limit: int = Field(default=5, ge=0, le=50)
    similarity_threshold: float = Field(default=0.55, ge=-1.0, le=1.0)


class MemoryContextRequest(BaseModel):
    query: str = Field(min_length=1, max_length=12000)
    purpose: str = Field(default="conversation", max_length=40)
    conversation_id: Optional[str] = Field(default=None, max_length=200)
    max_items: int = Field(default=4, ge=0, le=20)
    max_tokens: int = Field(default=500, ge=64, le=4000)


class MemoryExtractRequest(BaseModel):
    messages: List[Dict[str, Any]]
    max_memories: int = Field(default=3, ge=0, le=10)
    conversation_id: Optional[str] = Field(default=None, max_length=200)
    user_message_id: Optional[str] = Field(default=None, max_length=200)
    assistant_message_id: Optional[str] = Field(default=None, max_length=200)
    idempotency_key: Optional[str] = Field(default=None, min_length=16, max_length=200)


class MemoryLearningContextRequest(BaseModel):
    task_description: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=6, ge=0, le=20)
    similarity_threshold: float = Field(default=0.45, ge=-1.0, le=1.0)


class MemoryClearRequest(BaseModel):
    confirm: bool = False
    include_task_data: bool = True


class MemoryResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


def _namespace(current_user: Dict[str, Any]) -> str:
    username = str((current_user or {}).get("username") or "").strip()
    if not username:
        raise HTTPException(status_code=401, detail="Authenticated user has no namespace")
    return username


def _validated_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if metadata is None:
        return None
    encoded = json.dumps(metadata, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > 32768:
        raise HTTPException(status_code=400, detail="Memory metadata exceeds 32768 bytes")
    return metadata


def _validate_extraction_messages(messages: List[Dict[str, Any]]) -> None:
    if len(messages) > 50:
        raise HTTPException(status_code=400, detail="Memory extraction accepts at most 50 messages")
    total_chars = 0
    for message in messages:
        content = message.get("content")
        if not isinstance(content, str):
            raise HTTPException(
                status_code=400,
                detail="Memory extraction message content must be text",
            )
        if len(content) > 12000:
            raise HTTPException(
                status_code=400,
                detail="Memory extraction message exceeds 12000 characters",
            )
        total_chars += len(content)
    if total_chars > 100000:
        raise HTTPException(
            status_code=400,
            detail="Memory extraction payload exceeds 100000 characters",
        )


def create_memory_router(
    *,
    manager_provider: Callable[[], Any],
    auth_dependency: Callable[..., Dict[str, Any]],
) -> APIRouter:
    router = APIRouter(prefix="/v1/memory", tags=["memory"])

    def manager() -> Any:
        value = manager_provider()
        if value is None:
            raise HTTPException(status_code=503, detail="Memory system is not available")
        return value

    @router.post("/store", response_model=MemoryResponse)
    async def store_memory(
        request: MemoryStoreRequest,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        namespace = _namespace(current_user)
        try:
            memory_id = await service.store_memory(
                text=request.text,
                kind=request.kind or request.category,
                source="explicit",
                metadata=_validated_metadata(request.metadata),
                namespace=namespace,
                subject=request.subject,
                memory_key=request.memory_key,
                source_ref=request.source_ref,
                conversation_id=request.conversation_id,
                turn_id=request.turn_id,
                confidence=request.confidence,
                importance=request.importance,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return MemoryResponse(
            success=True,
            message="Memory stored",
            data={"memory_id": memory_id},
        )

    @router.post("/search", response_model=MemoryResponse)
    async def search_memories(
        request: MemorySearchRequest,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        kinds = list(request.kinds or [])
        if len(kinds) > 20:
            raise HTTPException(status_code=400, detail="Memory search accepts at most 20 kinds")
        if request.category:
            kinds.append(request.category)
        try:
            memories = await service.search_memories(
                query=request.query,
                purpose=request.purpose,
                kinds=kinds or None,
                limit=request.limit,
                similarity_threshold=request.similarity_threshold,
                namespace=_namespace(current_user),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return MemoryResponse(
            success=True,
            message=f"Found {len(memories)} memories",
            data={"memories": memories, "count": len(memories)},
        )

    @router.post("/context", response_model=MemoryResponse)
    async def memory_context(
        request: MemoryContextRequest,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        try:
            result = await service.build_context(
                namespace=_namespace(current_user),
                query=request.query,
                purpose=request.purpose,
                max_items=request.max_items,
                max_tokens=request.max_tokens,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return MemoryResponse(
            success=True,
            message=f"Built context from {result['count']} memories",
            data=result,
        )

    @router.post("/extract", response_model=MemoryResponse)
    async def extract_memories(
        request: MemoryExtractRequest,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        _validate_extraction_messages(request.messages)
        memory_ids = await service.extract_memories_from_conversation(
            messages=request.messages,
            max_memories=request.max_memories,
            namespace=_namespace(current_user),
            conversation_id=request.conversation_id,
            user_message_id=request.user_message_id,
            assistant_message_id=request.assistant_message_id,
            idempotency_key=request.idempotency_key,
        )
        return MemoryResponse(
            success=True,
            message=f"Extracted {len(memory_ids)} memories",
            data={"extracted": len(memory_ids), "memory_ids": memory_ids},
        )

    @router.get("/list", response_model=MemoryResponse)
    async def list_memories(
        limit: Optional[int] = None,
        kind: Optional[str] = None,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        safe_limit = None if limit is None else max(0, min(500, int(limit)))
        try:
            memories = service.list_memories(
                limit=safe_limit,
                namespace=_namespace(current_user),
                kinds=[kind] if kind else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        total = service.count(namespace=_namespace(current_user))
        return MemoryResponse(
            success=True,
            message=f"Retrieved {len(memories)} memories",
            data={"memories": memories, "count": len(memories), "total": total},
        )

    @router.get("/learning/events", response_model=MemoryResponse)
    async def learning_events(
        limit: int = 50,
        outcome: Optional[str] = None,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        events = service.list_task_learning_events(
            limit=max(0, min(500, int(limit))),
            outcome=outcome,
            namespace=_namespace(current_user),
        )
        return MemoryResponse(
            success=True,
            message=f"Retrieved {len(events)} task runs",
            data={"events": events, "count": len(events)},
        )

    @router.post("/learning/context", response_model=MemoryResponse)
    async def learning_context(
        request: MemoryLearningContextRequest,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        namespace = _namespace(current_user)
        context = await service.get_task_learning_context(
            request.task_description,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            namespace=namespace,
        )
        guidance = await service.build_task_execution_guidance(
            request.task_description,
            limit=request.limit,
            namespace=namespace,
        )
        return MemoryResponse(
            success=True,
            message="Retrieved task learning context",
            data={"context": context, "guidance": guidance},
        )

    @router.delete("/learning/lessons/{lesson_id}", response_model=MemoryResponse)
    async def delete_lesson(
        lesson_id: str,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        if not service.task_learning:
            raise HTTPException(status_code=503, detail="Task learning is unavailable")
        deleted = service.repository.delete_task_lesson(_namespace(current_user), lesson_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Task lesson not found")
        return MemoryResponse(success=True, message="Task lesson deleted", data={"lesson_id": lesson_id})

    @router.get("/learning/lessons", response_model=MemoryResponse)
    async def list_lessons(
        limit: int = 50,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        lessons = service.list_task_lessons(
            namespace=_namespace(current_user),
            limit=max(0, min(500, int(limit))),
        )
        return MemoryResponse(
            success=True,
            message=f"Retrieved {len(lessons)} task lessons",
            data={"lessons": lessons, "count": len(lessons)},
        )

    @router.get("/export", response_model=MemoryResponse)
    async def export_memory(
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        data = service.export_namespace(_namespace(current_user))
        return MemoryResponse(success=True, message="Memory exported", data=data)

    @router.post("/clear", response_model=MemoryResponse)
    async def clear_memory(
        request: MemoryClearRequest,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        if request.confirm is not True:
            raise HTTPException(status_code=400, detail="Set confirm=true to clear memory")
        service = manager()
        counts = service.clear_namespace(
            _namespace(current_user),
            include_task_data=request.include_task_data,
        )
        return MemoryResponse(success=True, message="Memory cleared", data={"deleted": counts})

    @router.get("/status", response_model=MemoryResponse)
    async def memory_status(
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        namespace = _namespace(current_user)
        return MemoryResponse(
            success=True,
            message="Memory system is available",
            data={
                "available": True,
                "backend": "sqlite",
                "memory_count": service.count(namespace=namespace),
            },
        )

    @router.get("/{memory_id}", response_model=MemoryResponse)
    async def get_memory(
        memory_id: str,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        memory = service.get_memory(memory_id, namespace=_namespace(current_user))
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        return MemoryResponse(success=True, message="Memory retrieved", data={"memory": memory})

    @router.delete("/{memory_id}", response_model=MemoryResponse)
    async def delete_memory(
        memory_id: str,
        current_user: Dict[str, Any] = Depends(auth_dependency),
    ):
        service = manager()
        deleted = service.delete_memory(memory_id, namespace=_namespace(current_user))
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory not found")
        return MemoryResponse(
            success=True,
            message="Memory deleted",
            data={"memory_id": memory_id},
        )

    return router

"""
High-level memory manager for storing and retrieving user information.
Handles automatic memory extraction and explicit memory storage.
"""

import json
import os
import re
from pathlib import Path
from threading import Lock
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

from .embeddings_client import EmbeddingsClient
from .vector_store import VectorStore
from .memory_extractor import MemoryExtractor


class MemoryManager:
    """
    High-level interface for memory operations.
    Manages embeddings generation, storage, and retrieval.
    """

    def __init__(
        self,
        storage_path: Optional[str] = None,
        embeddings_client: Optional[EmbeddingsClient] = None,
        vector_store: Optional[VectorStore] = None,
        memory_extractor: Optional[MemoryExtractor] = None,
    ):
        """
        Initialize memory manager.

        Args:
            storage_path: Path for storing memory data (defaults to ./memory_data)
            embeddings_client: Optional pre-configured embeddings client
            vector_store: Optional pre-configured vector store
            memory_extractor: Optional pre-configured memory extractor
        """
        # Get storage path from environment or use default
        self.storage_path = storage_path or os.getenv("MEMORY_STORAGE_PATH", "./memory_data")
        
        # Initialize embeddings client if not provided
        # This may fail if embeddings API is not configured, but we'll catch that during use
        try:
            self.embeddings_client = embeddings_client or EmbeddingsClient()
        except Exception as e:
            raise Exception(f"Failed to initialize embeddings client: {e}. Check EMBEDDINGS_API_BASE and EMBEDDINGS_MODEL configuration.")
        
        # Initialize vector store if not provided
        try:
            self.vector_store = vector_store or VectorStore(storage_path=self.storage_path)
        except Exception as e:
            raise Exception(f"Failed to initialize vector store: {e}")
        
        # Initialize memory extractor if not provided
        # This is optional and may not have API key configured
        try:
            self.memory_extractor = memory_extractor or MemoryExtractor()
        except Exception as e:
            # Memory extractor is optional, just log a warning
            print(f"Warning: Failed to initialize memory extractor: {e}")
            self.memory_extractor = None
        
        # Get configuration from environment
        self.search_limit = int(os.getenv("MEMORY_SEARCH_LIMIT", "5"))
        self.similarity_threshold = float(os.getenv("MEMORY_SIMILARITY_THRESHOLD", "0.7"))
        self.auto_extract = os.getenv("MEMORY_AUTO_EXTRACT", "true").lower() == "true"
        # Pre-filter: skip extraction unless conversation has enough substance
        self.extract_min_user_messages = int(os.getenv("MEMORY_EXTRACT_MIN_USER_MESSAGES", "2"))
        self.extract_min_user_chars = int(os.getenv("MEMORY_EXTRACT_MIN_USER_CHARS", "80"))
        self.extract_min_memory_words = int(os.getenv("MEMORY_EXTRACT_MIN_MEMORY_WORDS", "4"))
        self.extract_min_memory_chars = int(os.getenv("MEMORY_EXTRACT_MIN_MEMORY_CHARS", "18"))
        self.extract_dedup_similarity_threshold = float(
            os.getenv("MEMORY_EXTRACT_DEDUP_SIMILARITY_THRESHOLD", "0.9")
        )
        confidence_csv = os.getenv("MEMORY_EXTRACT_ALLOWED_CONFIDENCE", "high")
        self.extract_allowed_confidence = {
            c.strip().lower() for c in confidence_csv.split(",") if c.strip()
        } or {"high"}

        self._durable_categories = {"preference", "habit", "fact", "need", "relationship"}
        self._ephemeral_pattern = re.compile(
            r"\b(today|tonight|yesterday|this morning|this afternoon|this evening|"
            r"right now|currently|at the moment|just now)\b",
            re.IGNORECASE,
        )
        self._smalltalk_pattern = re.compile(
            r"^(thanks|thank you|ok|okay|sure|got it|sounds good)[.! ]*$",
            re.IGNORECASE,
        )
        self._command_like_pattern = re.compile(
            r"^(search|find|look up|open|run|execute|write|create|send|fetch)\b",
            re.IGNORECASE,
        )
        self._operational_state_pattern = re.compile(
            r"\b(todo|to-?do|task list|my tasks?|due tasks?|overdue tasks?|task execution|"
            r"task outcome memory|experience hints from similar tasks|repeat for similar tasks|"
            r"avoid for similar tasks|"
            r"execution status|status update|awaiting confirmation|paused awaiting feedback|"
            r"pending tasks?|completed tasks?|cancelled tasks?|task id|current state|"
            r"list state|working:|done:|failed:)\b",
            re.IGNORECASE,
        )
        self._operational_list_pattern = re.compile(
            r"(?:^|\n)\s*(?:[-*]|\d+\.)\s+(?:task|todo|to-?do|due|overdue|pending|"
            r"completed|cancelled|in progress|status)\b",
            re.IGNORECASE,
        )
        self._task_learning_categories = {"task_experience", "task_learning"}
        blocked_category_csv = os.getenv(
            "MEMORY_CONTEXT_BLOCKED_CATEGORIES",
            "task_experience,task_learning",
        )
        self._context_blocked_categories = {
            c.strip().lower() for c in blocked_category_csv.split(",") if c.strip()
        } or set(self._task_learning_categories)
        blocked_source_csv = os.getenv(
            "MEMORY_CONTEXT_BLOCKED_SOURCES",
            "task_execution,task_scheduler,status_system",
        )
        self._context_blocked_sources = {
            s.strip().lower() for s in blocked_source_csv.split(",") if s.strip()
        }
        self.task_learning_enabled = os.getenv("MEMORY_TASK_LEARNING_ENABLED", "true").lower() == "true"
        self.task_learning_search_limit = max(
            1, min(20, int(os.getenv("MEMORY_TASK_LEARNING_SEARCH_LIMIT", "6")))
        )
        self.task_learning_similarity_threshold = max(
            0.0, min(1.0, float(os.getenv("MEMORY_TASK_LEARNING_SIMILARITY_THRESHOLD", "0.55")))
        )
        self.task_learning_events_file = Path(self.storage_path) / "task_learning_events.jsonl"
        self._task_learning_lock = Lock()
        self._ensure_task_learning_store()

    async def store_memory(
        self,
        text: str,
        category: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Store a memory by generating embedding and saving to vector store.

        Args:
            text: Text content to remember
            category: Category of memory (e.g., "preference", "habit", "fact")
            source: Source of memory (e.g., "conversation", "explicit")
            metadata: Additional metadata to store

        Returns:
            Memory ID of the stored memory
        """
        text = (text or "").strip()
        if not text:
            raise ValueError("Memory text is required")

        # Generate embedding for the text
        embedding = await self.embeddings_client.get_embedding(text)
        
        # Add memory to vector store
        memory_id = self.vector_store.add_embedding(
            embedding=embedding,
            text=text,
            category=category or "general",
            source=source or "unknown",
            metadata=metadata,
        )
        
        return memory_id

    async def search_memories(
        self,
        query: str,
        limit: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        category: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search for relevant memories by query text.

        Args:
            query: Search query text
            limit: Maximum number of results (defaults to configured limit)
            similarity_threshold: Minimum similarity score (defaults to configured threshold)
            category: Optional category filter

        Returns:
            List of memory dictionaries with similarity scores
        """
        # Use configured defaults if not specified
        # Check for None explicitly to allow 0 and 0.0 as valid values
        if limit is None:
            limit = self.search_limit
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = self.search_limit
        if similarity_threshold is None:
            similarity_threshold = self.similarity_threshold
        try:
            similarity_threshold = float(similarity_threshold)
        except (TypeError, ValueError):
            similarity_threshold = self.similarity_threshold
        
        # Generate embedding for query
        query_embedding = await self.embeddings_client.get_embedding(query)
        
        # Search vector store
        results = self.vector_store.search(
            query_embedding=query_embedding,
            limit=limit,
            similarity_threshold=similarity_threshold,
            category=category,
        )
        
        # Log search results for debugging
        if results:
            print(f"Memory search: Found {len(results)} results for query '{query[:50]}...' (threshold: {similarity_threshold})")
        else:
            print(f"Memory search: No results for query '{query[:50]}...' (threshold: {similarity_threshold}, total memories: {self.vector_store.count()})")
        
        return results

    def get_memory(self, memory_id: str) -> Optional[Dict]:
        """
        Get a memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            Memory metadata dict or None if not found
        """
        return self.vector_store.get_memory(memory_id)

    def get_memories_by_category(self, category: str) -> List[Dict]:
        """
        Get all memories in a specific category.

        Args:
            category: Category name

        Returns:
            List of memory metadata dicts
        """
        return self.vector_store.get_memories_by_category(category)

    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory by ID.

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deleted, False if not found
        """
        return self.vector_store.delete_memory(memory_id)

    def list_memories(self, limit: Optional[int] = None) -> List[Dict]:
        """
        List all memories, optionally limited.

        Args:
            limit: Maximum number of memories to return

        Returns:
            List of memory metadata dicts, sorted by timestamp (newest first)
        """
        return self.vector_store.list_memories(limit=limit)

    def count(self) -> int:
        """Get total number of stored memories."""
        return self.vector_store.count()

    async def extract_memories_from_conversation(
        self,
        messages: List[Dict[str, str]],
        max_memories: int = 3,
    ) -> List[str]:
        """
        Extract important information from a conversation using LLM.

        Args:
            messages: List of conversation messages (role/content format)
            max_memories: Maximum number of memories to extract

        Returns:
            List of memory IDs for extracted memories
        """
        # Check if memory extractor is available
        if self.memory_extractor is None:
            print("Warning: Memory extractor is not available. Cannot extract memories from conversation.")
            return []
        
        # Pre-filter: skip extraction if conversation lacks substance (saves LLM calls)
        user_messages = [m for m in messages if (m.get("role") or "").lower() == "user"]
        user_content_len = sum(len((m.get("content") or "").strip()) for m in user_messages)
        if len(user_messages) < self.extract_min_user_messages:
            return []
        if user_content_len < self.extract_min_user_chars:
            return []
        
        # Extract memories using memory extractor
        extracted = await self.memory_extractor.extract_memories(
            messages=messages,
            max_memories=max_memories,
        )

        # Store each extracted memory
        memory_ids = []
        seen_normalized = set()
        for mem in extracted:
            confidence = (mem.get("confidence") or "").strip().lower()
            if confidence not in self.extract_allowed_confidence:
                continue

            raw_text = (mem.get("text") or "").strip()
            if not self._is_high_value_memory_text(raw_text):
                continue

            normalized = self._normalize_memory_text(raw_text)
            if normalized in seen_normalized:
                continue

            category = (mem.get("category") or "").strip().lower()
            if category not in self._durable_categories:
                continue
            source = (mem.get("source") or "conversation").strip()
            if not self.should_store_as_conversational_memory(
                text=raw_text,
                category=category,
                source=source,
                metadata=mem,
            ):
                continue

            if await self._memory_already_exists(raw_text):
                continue

            memory_id = await self.store_memory(
                text=raw_text,
                category=category,
                source=source,
            )
            memory_ids.append(memory_id)
            seen_normalized.add(normalized)

        return memory_ids

    def _normalize_memory_text(self, text: str) -> str:
        """Normalize memory text for duplicate detection."""
        return " ".join((text or "").strip().lower().split())

    def _is_high_value_memory_text(self, text: str) -> bool:
        """Heuristic quality gate to avoid storing low-value extraction output."""
        if not text:
            return False
        if len(text) < self.extract_min_memory_chars:
            return False
        if len(text.split()) < self.extract_min_memory_words:
            return False
        if text.endswith("?"):
            return False
        if self._smalltalk_pattern.search(text):
            return False
        if self._ephemeral_pattern.search(text):
            return False
        if self._command_like_pattern.search(text):
            return False
        if self.is_operational_memory_text(text):
            return False
        return True

    def is_operational_memory_text(self, text: str) -> bool:
        """Return True when text looks like transient task/list/runtime state."""
        if not text:
            return False
        normalized = " ".join(str(text).split())
        if not normalized:
            return False
        if self._operational_state_pattern.search(normalized):
            return True
        if self._operational_list_pattern.search(normalized):
            return True
        return False

    def should_store_as_conversational_memory(
        self,
        *,
        text: str,
        category: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Gate conversational memory storage to durable, non-operational content."""
        category_norm = (category or "").strip().lower()
        source_norm = (source or "").strip().lower()
        memory_type = str((metadata or {}).get("memory_type") or "").strip().lower()
        if category_norm in self._task_learning_categories:
            return False
        if memory_type in self._task_learning_categories:
            return False
        if source_norm in self._context_blocked_sources:
            return False
        if self.is_operational_memory_text(text):
            return False
        return True

    def filter_memories_for_conversation_context(
        self,
        memories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Drop operational/task-state memories before injecting context into chat."""
        filtered: List[Dict[str, Any]] = []
        for mem in memories or []:
            if not isinstance(mem, dict):
                continue
            category = (mem.get("category") or "").strip().lower()
            source = (mem.get("source") or "").strip().lower()
            memory_type = str(mem.get("memory_type") or "").strip().lower()
            text = str(mem.get("text") or "")

            if category in self._context_blocked_categories:
                continue
            if memory_type in self._context_blocked_categories:
                continue
            if source in self._context_blocked_sources:
                continue
            if not self.should_store_as_conversational_memory(
                text=text,
                category=category or None,
                source=source or None,
                metadata=mem,
            ):
                continue
            filtered.append(mem)
        return filtered

    async def _memory_already_exists(self, text: str) -> bool:
        """Return True when memory text is already stored (exact or semantic duplicate)."""
        normalized = self._normalize_memory_text(text)

        # Fast exact normalized check against existing metadata.
        for existing in self.vector_store.metadata.values():
            existing_text = self._normalize_memory_text(existing.get("text", ""))
            if existing_text == normalized:
                return True

        # Semantic near-duplicate check.
        try:
            near = await self.search_memories(
                query=text,
                limit=1,
                similarity_threshold=self.extract_dedup_similarity_threshold,
            )
            if near:
                return True
        except Exception:
            # Best-effort check only; never block extraction on duplicate check failures.
            return False

        return False

    def _ensure_task_learning_store(self) -> None:
        """Ensure task learning event file exists."""
        try:
            self.task_learning_events_file.parent.mkdir(parents=True, exist_ok=True)
            if not self.task_learning_events_file.exists():
                self.task_learning_events_file.write_text("", encoding="utf-8")
        except Exception as e:
            print(f"Warning: Failed to initialize task learning store: {e}")

    def _sanitize_learning_text(self, text: Optional[str], max_chars: int = 700) -> str:
        """Normalize and truncate free-form text for stable storage."""
        normalized = " ".join((text or "").strip().split())
        if len(normalized) <= max_chars:
            return normalized
        return normalized[: max_chars - 3].rstrip() + "..."

    def _merge_extra_metadata(
        self,
        base: Dict[str, Any],
        extra: Optional[Dict[str, Any]],
        protected_keys: Optional[set[str]] = None,
    ) -> Dict[str, Any]:
        """Merge caller metadata without allowing it to replace internal learning fields."""
        merged = dict(base)
        if not extra:
            return merged
        protected = set(protected_keys or set(base.keys()))
        ignored: List[str] = []
        for key, value in extra.items():
            if key in protected:
                ignored.append(str(key))
                continue
            merged[key] = value
        if ignored:
            merged["ignored_metadata_keys"] = sorted(set(ignored))
        return merged

    def _normalize_task_outcome(self, status: Optional[str], message: Optional[str]) -> str:
        """Map raw execution status to normalized outcome buckets."""
        raw_status = (status or "").strip().lower()
        msg = (message or "").strip().lower()

        if raw_status in {"success", "completed", "confirmed_complete"}:
            return "success"
        if raw_status in {"failed", "failure", "error"}:
            return "failure"
        if raw_status == "cancelled":
            return "cancelled"
        if raw_status == "paused_awaiting_feedback":
            return "paused"
        if raw_status == "awaiting_confirmation":
            failure_markers = ("no response", "error", "failed", "exception", "stopped unexpectedly")
            if any(marker in msg for marker in failure_markers):
                return "failure"
            return "success"
        return "unknown"

    def _derive_task_learning_points(
        self,
        *,
        outcome: str,
        summary: str,
        error: str,
        tool_names: List[str],
    ) -> List[str]:
        """Generate concise learning points from an execution outcome."""
        points: List[str] = []
        unique_tools = [tool for tool in dict.fromkeys(tool_names) if tool]

        if outcome == "success":
            if unique_tools:
                points.append(
                    f"Successful pattern: use tools {', '.join(unique_tools[:5])} for similar tasks."
                )
            if summary:
                points.append(f"What worked: {summary}")
        elif outcome == "failure":
            if error:
                points.append(f"Failure trigger to avoid: {error}")
            if not unique_tools:
                points.append("Task stalled without tool usage; choose tools earlier.")
            if summary:
                points.append(f"Failure context: {summary}")
        elif outcome == "paused":
            points.append("Ask clarifying questions early when requirements are ambiguous.")
            if summary:
                points.append(f"Pause context: {summary}")
        elif outcome == "cancelled":
            points.append("Execution was cancelled before completion; checkpoint progress early.")
        else:
            if summary:
                points.append(f"Execution notes: {summary}")
            if error:
                points.append(f"Observed issue: {error}")

        deduped: List[str] = []
        seen = set()
        for point in points:
            cleaned = self._sanitize_learning_text(point, max_chars=280)
            key = cleaned.lower()
            if not cleaned or key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
            if len(deduped) >= 3:
                break
        return deduped

    def _append_task_learning_event(self, event: Dict[str, Any]) -> None:
        """Append a raw task-learning event to JSONL."""
        self._ensure_task_learning_store()
        try:
            with self._task_learning_lock:
                with self.task_learning_events_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Warning: Failed to append task learning event: {e}")

    def list_task_learning_events(
        self,
        limit: int = 50,
        outcome: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List recent task-learning events from JSONL (newest first)."""
        if limit <= 0:
            return []
        if not self.task_learning_events_file.exists():
            return []

        normalized_outcome = (outcome or "").strip().lower()
        events: List[Dict[str, Any]] = []
        try:
            with self.task_learning_events_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if normalized_outcome and (event.get("outcome") or "").strip().lower() != normalized_outcome:
                        continue
                    events.append(event)
        except Exception as e:
            print(f"Warning: Failed to read task learning events: {e}")
            return []

        events = events[-limit:]
        events.reverse()
        return events

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
    ) -> Dict[str, Any]:
        """
        Record task execution outcome as both raw event and searchable experience memories.

        Returns:
            Dict with outcome, event, and stored memory IDs (if task learning is enabled).
        """
        task_text = self._sanitize_learning_text(task_description, max_chars=500)
        summary_text = self._sanitize_learning_text(summary or message or "", max_chars=700)
        error_text = self._sanitize_learning_text(error or "", max_chars=500)
        normalized_tools = [self._sanitize_learning_text(t, max_chars=80) for t in (tool_names or []) if t]
        outcome = self._normalize_task_outcome(status=status, message=summary_text or error_text)
        learning_points = self._derive_task_learning_points(
            outcome=outcome,
            summary=summary_text,
            error=error_text,
            tool_names=normalized_tools,
        )

        now = datetime.now(timezone.utc).isoformat()
        event = {
            "timestamp": now,
            "task_description": task_text,
            "status": status,
            "outcome": outcome,
            "summary": summary_text,
            "error": error_text,
            "tool_names": normalized_tools,
            "learning_points": learning_points,
            "source": source,
        }
        if metadata:
            event["metadata"] = metadata
        self._append_task_learning_event(event)

        memory_ids: List[str] = []
        if not self.task_learning_enabled:
            return {"outcome": outcome, "event": event, "memory_ids": memory_ids}
        if not task_text:
            return {"outcome": outcome, "event": event, "memory_ids": memory_ids}

        experience_text = (
            f"Task outcome memory. Task: {task_text}. Outcome: {outcome}. "
            f"Status: {status}. Summary: {summary_text or 'No summary provided.'}. "
            f"Learnings: {'; '.join(learning_points) if learning_points else 'No clear learning extracted.'}"
        )
        experience_metadata: Dict[str, Any] = {
            "memory_type": "task_experience",
            "task_description": task_text,
            "status": status,
            "outcome": outcome,
            "summary": summary_text,
            "error": error_text,
            "tool_names": normalized_tools,
            "learning_points": learning_points,
            "event_timestamp": now,
        }
        experience_metadata = self._merge_extra_metadata(experience_metadata, metadata)

        try:
            memory_ids.append(
                await self.store_memory(
                    text=experience_text,
                    category="task_experience",
                    source=source,
                    metadata=experience_metadata,
                )
            )
            for idx, point in enumerate(learning_points[:2], start=1):
                prefix = "Repeat" if outcome == "success" else "Avoid" if outcome == "failure" else "Note"
                learning_text = (
                    f"{prefix} for similar tasks: {point} "
                    f"(task: {task_text})"
                )
                learning_metadata: Dict[str, Any] = {
                    "memory_type": "task_learning",
                    "task_description": task_text,
                    "status": status,
                    "outcome": outcome,
                    "tool_names": normalized_tools,
                    "learning_point": point,
                    "learning_rank": idx,
                    "event_timestamp": now,
                }
                learning_metadata = self._merge_extra_metadata(learning_metadata, metadata)
                memory_ids.append(
                    await self.store_memory(
                        text=learning_text,
                        category="task_learning",
                        source=source,
                        metadata=learning_metadata,
                    )
                )
        except Exception as e:
            print(f"Warning: Failed to persist task outcome memories: {e}")

        return {"outcome": outcome, "event": event, "memory_ids": memory_ids}

    async def get_task_learning_context(
        self,
        task_description: str,
        limit: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Retrieve relevant success/failure learnings for a task description."""
        query = self._sanitize_learning_text(task_description, max_chars=500)
        if not query:
            return {"task_description": "", "successes": [], "failures": [], "notes": [], "all": []}

        use_limit = limit if limit is not None else self.task_learning_search_limit
        use_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else self.task_learning_similarity_threshold
        )

        try:
            results = await self.search_memories(
                query=f"Task execution learnings for: {query}",
                limit=use_limit,
                similarity_threshold=use_threshold,
                category=None,
            )
        except Exception:
            results = []

        relevant: List[Dict[str, Any]] = []
        for mem in results:
            category = (mem.get("category") or "").strip().lower()
            memory_type = (mem.get("memory_type") or "").strip().lower()
            if category not in {"task_experience", "task_learning"} and memory_type not in {
                "task_experience",
                "task_learning",
            }:
                continue
            relevant.append(mem)

        successes: List[Dict[str, Any]] = []
        failures: List[Dict[str, Any]] = []
        notes: List[Dict[str, Any]] = []
        for mem in relevant:
            outcome = (mem.get("outcome") or "").strip().lower()
            if outcome == "success":
                successes.append(mem)
            elif outcome in {"failure", "cancelled"}:
                failures.append(mem)
            else:
                notes.append(mem)

        return {
            "task_description": query,
            "successes": successes,
            "failures": failures,
            "notes": notes,
            "all": relevant,
        }

    async def build_task_execution_guidance(
        self,
        task_description: str,
        limit: int = 6,
    ) -> str:
        """Build a concise guidance block from prior task-execution experiences."""
        context = await self.get_task_learning_context(task_description=task_description, limit=limit)
        successes = context.get("successes", [])
        failures = context.get("failures", [])

        if not successes and not failures:
            return ""

        lines = ["Experience hints from similar tasks:"]
        seen_lines = set()
        for mem in successes:
            text = self._format_learning_memory_for_guidance(mem)
            if text:
                key = f"repeat:{text.lower()}"
                if key not in seen_lines:
                    seen_lines.add(key)
                    lines.append(f"- Repeat: {text}")
            if len([line for line in lines if line.startswith("- Repeat:")]) >= 2:
                break
        for mem in failures:
            text = self._format_learning_memory_for_guidance(mem)
            if text:
                key = f"avoid:{text.lower()}"
                if key not in seen_lines:
                    seen_lines.add(key)
                    lines.append(f"- Avoid: {text}")
            if len([line for line in lines if line.startswith("- Avoid:")]) >= 2:
                break

        return "\n".join(lines)

    def _format_learning_memory_for_guidance(self, memory: Dict[str, Any]) -> str:
        """Prefer distilled learning points over raw task-outcome prose."""
        point = self._sanitize_learning_text(memory.get("learning_point"), max_chars=220)
        if point:
            return point

        points = memory.get("learning_points")
        if isinstance(points, list):
            for item in points:
                text = self._sanitize_learning_text(str(item), max_chars=220)
                if text:
                    return text

        text = self._sanitize_learning_text(memory.get("text", ""), max_chars=220)
        prefixes = (
            "Repeat for similar tasks:",
            "Avoid for similar tasks:",
            "Note for similar tasks:",
            "Task outcome memory.",
        )
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        return text


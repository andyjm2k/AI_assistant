"""
High-level memory manager for storing and retrieving user information.
Handles automatic memory extraction and explicit memory storage.
"""

import os
import re
from typing import List, Dict, Optional
from datetime import datetime

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
        if similarity_threshold is None:
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

            if await self._memory_already_exists(raw_text):
                continue

            memory_id = await self.store_memory(
                text=raw_text,
                category=category,
                source=mem.get("source", "conversation"),
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
        return True

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


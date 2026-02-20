"""
High-level memory manager for storing and retrieving user information.
Handles automatic memory extraction and explicit memory storage.
"""

import os
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
        for mem in extracted:
            # Only store high or medium confidence memories
            if mem.get("confidence", "low") in ["high"]:
                memory_id = await self.store_memory(
                    text=mem.get("text", ""),
                    category=mem.get("category", "general"),
                    source=mem.get("source", "conversation"),
                )
                memory_ids.append(memory_id)
        
        return memory_ids


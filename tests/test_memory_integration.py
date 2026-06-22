"""
Integration tests for the memory system.
Tests the full flow from embedding generation to storage and retrieval.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from src.memory import MemoryManager, EmbeddingsClient


class TestMemoryIntegration:
    """Integration test suite for memory system."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def mock_embeddings_client(self):
        """Create a mock embeddings client that returns consistent embeddings."""
        client = EmbeddingsClient.__new__(EmbeddingsClient)
        
        # Mock the get_embedding method to return deterministic embeddings
        async def mock_get_embedding(text):
            # Simple hash-based embedding for testing
            import hashlib
            hash_obj = hashlib.md5(text.encode())
            # Generate 5-dimensional embedding from hash
            hash_bytes = hash_obj.digest()
            embedding = [float(b) / 255.0 for b in hash_bytes[:5]]
            # Normalize
            import math
            norm = math.sqrt(sum(x * x for x in embedding))
            if norm > 0:
                embedding = [x / norm for x in embedding]
            return embedding
        
        client.get_embedding = mock_get_embedding
        return client

    @pytest.fixture
    def memory_manager(self, temp_dir, mock_embeddings_client):
        """Create a test memory manager."""
        manager = MemoryManager(
            storage_path=temp_dir,
            embeddings_client=mock_embeddings_client,
        )
        yield manager
        manager.close()

    @pytest.mark.asyncio
    async def test_store_and_retrieve_memory(self, memory_manager):
        """Test storing and retrieving a memory."""
        # Store a memory
        memory_id = await memory_manager.store_memory(
            text="User prefers dark mode interfaces",
            category="preference",
            source="conversation",
        )
        
        # Verify memory ID is generated
        assert memory_id.startswith("mem_")
        
        # Retrieve the memory
        memory = memory_manager.get_memory(memory_id)
        
        # Verify content
        assert memory is not None
        assert memory["text"] == "User prefers dark mode interfaces"
        assert memory["category"] == "preference"

    @pytest.mark.asyncio
    async def test_search_memories(self, memory_manager):
        """Test searching for memories."""
        # Store multiple memories
        await memory_manager.store_memory(
            text="User prefers dark mode",
            category="preference",
        )
        await memory_manager.store_memory(
            text="User works late nights",
            category="habit",
        )
        await memory_manager.store_memory(
            text="User lives in New York",
            category="fact",
        )
        
        # Search for preferences
        results = await memory_manager.search_memories(
            query="user preferences",
            limit=5,
            similarity_threshold=0.0,  # Low threshold for testing
        )
        
        # Verify results
        assert len(results) > 0
        # At least one result should be about preferences
        preference_results = [r for r in results if r.get("category") == "preference"]
        assert len(preference_results) > 0

    @pytest.mark.asyncio
    async def test_list_and_delete_memories(self, memory_manager):
        """Test listing and deleting memories."""
        # Store memories
        memory_id1 = await memory_manager.store_memory(
            text="Memory 1",
            category="profile_fact",
        )
        memory_id2 = await memory_manager.store_memory(
            text="Memory 2",
            category="profile_fact",
        )
        
        # List all memories
        memories = memory_manager.list_memories()
        assert len(memories) >= 2
        
        # Delete one memory
        deleted = memory_manager.delete_memory(memory_id1)
        assert deleted is True
        
        # Verify it's gone
        memory = memory_manager.get_memory(memory_id1)
        assert memory is None
        
        # Verify the other still exists
        memory = memory_manager.get_memory(memory_id2)
        assert memory is not None

    @pytest.mark.asyncio
    async def test_persistence(self, temp_dir, mock_embeddings_client):
        """Test that memories persist across manager instances."""
        # Create first manager and store memory
        manager1 = MemoryManager(
            storage_path=temp_dir,
            embeddings_client=mock_embeddings_client,
        )
        manager2 = None
        try:
            memory_id = await manager1.store_memory(
                text="Persistent memory",
                category="profile_fact",
            )

            # Create second manager and verify memory persists
            manager2 = MemoryManager(
                storage_path=temp_dir,
                embeddings_client=mock_embeddings_client,
            )

            memory = manager2.get_memory(memory_id)
            assert memory is not None
            assert memory["text"] == "Persistent memory"
        finally:
            manager1.close()
            if manager2 is not None:
                manager2.close()

    @pytest.mark.asyncio
    async def test_category_filtering(self, memory_manager):
        """Test filtering memories by category."""
        # Store memories in different categories
        await memory_manager.store_memory(
            text="Preference memory",
            category="preference",
        )
        await memory_manager.store_memory(
            text="Habit memory",
            category="habit",
        )
        
        # Get memories by category
        preferences = memory_manager.get_memories_by_category("preference")
        habits = memory_manager.get_memories_by_category("habit")
        
        # Verify filtering
        assert len(preferences) > 0
        assert len(habits) > 0
        assert all(m["category"] == "preference" for m in preferences)
        assert all(m["category"] == "habit" for m in habits)


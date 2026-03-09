"""
Unit tests for VectorStore.
Tests vector storage, search, and metadata management.
"""

import pytest
import numpy as np
import json
import tempfile
import shutil
from pathlib import Path
import uuid
from src.memory.vector_store import VectorStore


class TestVectorStore:
    """Test suite for VectorStore."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = tempfile.mkdtemp()
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def vector_store(self, temp_dir):
        """Create a test vector store."""
        return VectorStore(storage_path=temp_dir)

    def test_add_embedding(self, vector_store):
        """Test adding an embedding to the store."""
        # Add first embedding
        embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        memory_id = vector_store.add_embedding(
            embedding=embedding,
            text="Test memory",
            category="test",
            source="test",
        )
        
        # Verify memory ID is generated
        assert memory_id.startswith("mem_")
        assert len(memory_id) > 4
        
        # Verify embedding is stored
        assert len(vector_store.embeddings) == 1
        assert vector_store.embeddings.shape[1] == 5
        
        # Verify metadata is stored
        assert memory_id in vector_store.metadata
        assert vector_store.metadata[memory_id]["text"] == "Test memory"
        assert vector_store.metadata[memory_id]["category"] == "test"

    def test_add_multiple_embeddings(self, vector_store):
        """Test adding multiple embeddings."""
        # Add first embedding
        embedding1 = [0.1, 0.2, 0.3]
        memory_id1 = vector_store.add_embedding(
            embedding=embedding1,
            text="Memory 1",
        )
        
        # Add second embedding
        embedding2 = [0.4, 0.5, 0.6]
        memory_id2 = vector_store.add_embedding(
            embedding=embedding2,
            text="Memory 2",
        )
        
        # Verify both are stored
        assert len(vector_store.embeddings) == 2
        assert len(vector_store.metadata) == 2
        assert memory_id1 != memory_id2

    def test_add_embedding_dimension_mismatch(self, vector_store):
        """Test that dimension mismatch raises error."""
        # Add first embedding
        embedding1 = [0.1, 0.2, 0.3]
        vector_store.add_embedding(embedding=embedding1, text="Memory 1")
        
        # Try to add embedding with different dimension
        embedding2 = [0.4, 0.5]  # Different dimension
        with pytest.raises(ValueError) as exc_info:
            vector_store.add_embedding(embedding=embedding2, text="Memory 2")
        
        assert "dimension mismatch" in str(exc_info.value).lower()

    def test_search_similar(self, vector_store):
        """Test similarity search."""
        # Add some embeddings
        vector_store.add_embedding(
            embedding=[1.0, 0.0, 0.0],
            text="Memory about X",
            category="test",
        )
        vector_store.add_embedding(
            embedding=[0.0, 1.0, 0.0],
            text="Memory about Y",
            category="test",
        )
        vector_store.add_embedding(
            embedding=[0.0, 0.0, 1.0],
            text="Memory about Z",
            category="other",
        )
        
        # Search with query similar to first embedding
        query_embedding = [0.9, 0.1, 0.0]  # Similar to [1.0, 0.0, 0.0]
        results = vector_store.search(
            query_embedding=query_embedding,
            limit=2,
            similarity_threshold=0.5,
        )
        
        # Verify results
        assert len(results) > 0
        assert results[0]["text"] == "Memory about X"
        assert "similarity" in results[0]

    def test_search_with_category_filter(self, vector_store):
        """Test search with category filter."""
        # Add embeddings with different categories
        vector_store.add_embedding(
            embedding=[1.0, 0.0],
            text="Test memory 1",
            category="preference",
        )
        vector_store.add_embedding(
            embedding=[0.0, 1.0],
            text="Test memory 2",
            category="habit",
        )
        
        # Search with category filter
        query_embedding = [0.9, 0.1]
        results = vector_store.search(
            query_embedding=query_embedding,
            limit=10,
            category="preference",
        )
        
        # Verify all results are in the specified category
        assert len(results) > 0
        for result in results:
            assert result["category"] == "preference"

    def test_get_memory(self, vector_store):
        """Test retrieving a memory by ID."""
        # Add a memory
        memory_id = vector_store.add_embedding(
            embedding=[0.1, 0.2, 0.3],
            text="Test memory",
        )
        
        # Retrieve it
        memory = vector_store.get_memory(memory_id)
        
        # Verify
        assert memory is not None
        assert memory["text"] == "Test memory"
        assert memory["id"] == memory_id

    def test_get_memory_not_found(self, vector_store):
        """Test retrieving a non-existent memory."""
        memory = vector_store.get_memory("nonexistent")
        assert memory is None

    def test_delete_memory(self, vector_store):
        """Test deleting a memory."""
        # Add a memory
        memory_id = vector_store.add_embedding(
            embedding=[0.1, 0.2, 0.3],
            text="Test memory",
        )
        
        # Verify it exists
        assert memory_id in vector_store.metadata
        assert len(vector_store.embeddings) == 1
        
        # Delete it
        deleted = vector_store.delete_memory(memory_id)
        
        # Verify deletion
        assert deleted is True
        assert memory_id not in vector_store.metadata
        assert len(vector_store.embeddings) == 0

    def test_delete_last_memory_removes_embeddings_file(self):
        """Deleting the final memory should remove persisted embeddings.npy."""
        temp_dir = Path(f"vector_store_delete_test_{uuid.uuid4().hex}")
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            vector_store = VectorStore(storage_path=str(temp_dir))
            memory_id = vector_store.add_embedding(
                embedding=[0.1, 0.2, 0.3],
                text="Final memory",
            )
            assert vector_store.embeddings_file.exists()

            deleted = vector_store.delete_memory(memory_id)
            assert deleted is True
            assert vector_store.count() == 0
            assert not vector_store.embeddings_file.exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_list_memories(self, vector_store):
        """Test listing all memories."""
        # Add multiple memories
        vector_store.add_embedding(embedding=[0.1, 0.2], text="Memory 1")
        vector_store.add_embedding(embedding=[0.3, 0.4], text="Memory 2")
        vector_store.add_embedding(embedding=[0.5, 0.6], text="Memory 3")
        
        # List all
        memories = vector_store.list_memories()
        
        # Verify
        assert len(memories) == 3
        
        # Test with limit
        limited = vector_store.list_memories(limit=2)
        assert len(limited) == 2

    def test_persistence(self, temp_dir):
        """Test that data persists across store instances."""
        # Create first store and add data
        store1 = VectorStore(storage_path=temp_dir)
        memory_id = store1.add_embedding(
            embedding=[0.1, 0.2, 0.3],
            text="Persistent memory",
        )
        
        # Create second store and verify data is loaded
        store2 = VectorStore(storage_path=temp_dir)
        assert store2.count() == 1
        assert memory_id in store2.metadata
        assert store2.get_memory(memory_id)["text"] == "Persistent memory"

    def test_count(self, vector_store):
        """Test counting memories."""
        # Initially empty
        assert vector_store.count() == 0
        
        # Add memories
        vector_store.add_embedding(embedding=[0.1, 0.2], text="Memory 1")
        vector_store.add_embedding(embedding=[0.3, 0.4], text="Memory 2")
        
        # Verify count
        assert vector_store.count() == 2


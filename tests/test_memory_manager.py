"""
Unit tests for MemoryManager.
Tests high-level memory operations.
"""

import pytest
import shutil
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from src.memory.memory_manager import MemoryManager
from src.memory.embeddings_client import EmbeddingsClient
from src.memory.vector_store import VectorStore
from src.memory.memory_extractor import MemoryExtractor


class TestMemoryManager:
    """Test suite for MemoryManager."""

    @pytest.fixture
    def mock_embeddings_client(self):
        """Create a mock embeddings client."""
        client = AsyncMock(spec=EmbeddingsClient)
        client.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4, 0.5])
        return client

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        store = MagicMock(spec=VectorStore)
        store.metadata = {}
        store.add_embedding = MagicMock(return_value="mem_test123")
        store.search = MagicMock(return_value=[])
        store.get_memory = MagicMock(return_value=None)
        store.get_memories_by_category = MagicMock(return_value=[])
        store.delete_memory = MagicMock(return_value=True)
        store.list_memories = MagicMock(return_value=[])
        store.count = MagicMock(return_value=0)
        return store

    @pytest.fixture
    def memory_manager(self, mock_embeddings_client, mock_vector_store):
        """Create a test memory manager."""
        return MemoryManager(
            embeddings_client=mock_embeddings_client,
            vector_store=mock_vector_store,
        )

    @pytest.mark.asyncio
    async def test_store_memory(self, memory_manager, mock_embeddings_client, mock_vector_store):
        """Test storing a memory."""
        # Store memory
        memory_id = await memory_manager.store_memory(
            text="User prefers dark mode",
            category="preference",
            source="conversation",
        )
        
        # Verify embeddings client was called
        mock_embeddings_client.get_embedding.assert_called_once_with("User prefers dark mode")
        
        # Verify vector store was called
        mock_vector_store.add_embedding.assert_called_once()
        call_args = mock_vector_store.add_embedding.call_args
        assert call_args[1]["text"] == "User prefers dark mode"
        assert call_args[1]["category"] == "preference"
        assert call_args[1]["source"] == "conversation"
        
        # Verify memory ID returned
        assert memory_id == "mem_test123"

    @pytest.mark.asyncio
    async def test_search_memories(self, memory_manager, mock_embeddings_client, mock_vector_store):
        """Test searching memories."""
        # Mock search results
        mock_vector_store.search.return_value = [
            {"text": "User prefers dark mode", "similarity": 0.9},
            {"text": "User works late nights", "similarity": 0.8},
        ]
        
        # Search memories
        results = await memory_manager.search_memories(
            query="user preferences",
            limit=5,
        )
        
        # Verify embeddings client was called
        mock_embeddings_client.get_embedding.assert_called_once_with("user preferences")
        
        # Verify vector store search was called
        mock_vector_store.search.assert_called_once()
        call_args = mock_vector_store.search.call_args
        query_embedding = call_args[1]["query_embedding"]
        assert len(query_embedding) == 5
        assert call_args[1]["limit"] == 5
        
        # Verify results
        assert len(results) == 2

    def test_get_memory(self, memory_manager, mock_vector_store):
        """Test getting a memory by ID."""
        # Mock memory
        mock_vector_store.get_memory.return_value = {
            "id": "mem_test123",
            "text": "Test memory",
        }
        
        # Get memory
        memory = memory_manager.get_memory("mem_test123")
        
        # Verify
        assert memory is not None
        assert memory["text"] == "Test memory"
        mock_vector_store.get_memory.assert_called_once_with("mem_test123")

    def test_delete_memory(self, memory_manager, mock_vector_store):
        """Test deleting a memory."""
        # Delete memory
        deleted = memory_manager.delete_memory("mem_test123")
        
        # Verify
        assert deleted is True
        mock_vector_store.delete_memory.assert_called_once_with("mem_test123")

    def test_list_memories(self, memory_manager, mock_vector_store):
        """Test listing memories."""
        # Mock memories
        mock_vector_store.list_memories.return_value = [
            {"id": "mem_1", "text": "Memory 1"},
            {"id": "mem_2", "text": "Memory 2"},
        ]
        
        # List memories
        memories = memory_manager.list_memories(limit=10)
        
        # Verify
        assert len(memories) == 2
        mock_vector_store.list_memories.assert_called_once_with(limit=10)

    def test_count(self, memory_manager, mock_vector_store):
        """Test counting memories."""
        # Mock count
        mock_vector_store.count.return_value = 5
        
        # Get count
        count = memory_manager.count()
        
        # Verify
        assert count == 5
        mock_vector_store.count.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_memories_from_conversation(self, memory_manager):
        """Test extracting memories from conversation (pre-filter passes, extractor called)."""
        # Ensure pre-filter passes: need at least 2 user messages and 80+ user chars
        memory_manager.extract_min_user_messages = 2
        memory_manager.extract_min_user_chars = 80
        # Mock memory extractor
        mock_extractor = AsyncMock(spec=MemoryExtractor)
        mock_extractor.extract_memories = AsyncMock(return_value=[
            {
                "text": "User prefers dark mode",
                "category": "preference",
                "confidence": "high",
                "source": "conversation",
            },
            {
                "text": "User works late nights",
                "category": "habit",
                "confidence": "medium",
                "source": "conversation",
            },
        ])
        memory_manager.memory_extractor = mock_extractor
        # Two user messages with enough content to pass pre-filter (min 80 user chars)
        messages = [
            {"role": "user", "content": "I prefer dark mode for my IDE and terminal. It's easier on my eyes."},
            {"role": "assistant", "content": "Noted!"},
            {"role": "user", "content": "I also work late nights usually."},
        ]
        memory_ids = await memory_manager.extract_memories_from_conversation(
            messages=messages,
            max_memories=3,
        )
        mock_extractor.extract_memories.assert_called_once()
        # Only high-confidence memories are stored
        assert len(memory_ids) == 1

    @pytest.mark.asyncio
    async def test_extract_memories_skips_low_value_and_duplicates(self, memory_manager):
        """Extraction skips ephemeral/small-talk entries and duplicate durable memories."""
        memory_manager.extract_min_user_messages = 2
        memory_manager.extract_min_user_chars = 20
        memory_manager.vector_store.metadata = {
            "mem_existing": {
                "id": "mem_existing",
                "text": "User prefers dark mode for coding",
                "embedding_index": 0,
            }
        }

        mock_extractor = AsyncMock(spec=MemoryExtractor)
        mock_extractor.extract_memories = AsyncMock(return_value=[
            {
                "text": "Thanks!",
                "category": "fact",
                "confidence": "high",
                "source": "conversation",
            },
            {
                "text": "User prefers dark mode for coding",
                "category": "preference",
                "confidence": "high",
                "source": "conversation",
            },
            {
                "text": "User currently needs this fixed right now",
                "category": "need",
                "confidence": "high",
                "source": "conversation",
            },
        ])
        memory_manager.memory_extractor = mock_extractor
        memory_manager.store_memory = AsyncMock(return_value="mem_new")

        messages = [
            {"role": "user", "content": "I prefer dark mode for coding and terminal work."},
            {"role": "assistant", "content": "Noted."},
            {"role": "user", "content": "Can you remember these details for next time?"},
        ]
        memory_ids = await memory_manager.extract_memories_from_conversation(messages=messages, max_memories=3)

        # All extracted candidates were filtered out by quality/duplicate checks.
        assert memory_ids == []
        memory_manager.store_memory.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_memories_skipped_when_conversation_too_short(self, memory_manager):
        """Test that extraction is skipped when pre-filter fails (too few user messages/chars)."""
        mock_extractor = AsyncMock(spec=MemoryExtractor)
        memory_manager.memory_extractor = mock_extractor
        # One user message only (below default min of 2)
        messages = [
            {"role": "user", "content": "I prefer dark mode"},
            {"role": "assistant", "content": "Noted!"},
        ]
        memory_ids = await memory_manager.extract_memories_from_conversation(
            messages=messages,
            max_memories=3,
        )
        mock_extractor.extract_memories.assert_not_called()
        assert memory_ids == []

    def test_is_operational_memory_text_detects_task_state(self, memory_manager):
        """Operational todo/task/status snapshots should be detected as non-durable memory text."""
        assert memory_manager.is_operational_memory_text("Todo list: 1. Pay rent 2. Submit report") is True
        assert memory_manager.is_operational_memory_text("Task execution status: awaiting confirmation") is True
        assert memory_manager.is_operational_memory_text("User prefers dark mode for coding.") is False

    def test_filter_memories_for_conversation_context_excludes_task_and_state(self, memory_manager):
        """Conversation context filter should keep durable profile memories only."""
        memories = [
            {"text": "User prefers dark mode.", "category": "preference", "source": "conversation", "similarity": 0.92},
            {"text": "Task outcome memory. Task: deploy app.", "category": "task_experience", "source": "task_execution", "similarity": 0.90},
            {"text": "Todo list: 1. buy milk", "category": "general", "source": "telegram", "similarity": 0.89},
        ]
        out = memory_manager.filter_memories_for_conversation_context(memories)
        assert [m.get("text") for m in out] == ["User prefers dark mode."]

    @pytest.mark.asyncio
    async def test_record_task_outcome_stores_events_and_learning_memories(
        self,
        mock_embeddings_client,
        mock_vector_store,
    ):
        """Task outcome recording writes JSONL events and stores experience memories."""
        tmp_dir = Path("memory_data") / f"test_task_learning_{uuid.uuid4().hex}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        try:
            manager = MemoryManager(
                storage_path=str(tmp_dir),
                embeddings_client=mock_embeddings_client,
                vector_store=mock_vector_store,
            )
            result = await manager.record_task_outcome(
                task_description="Fix weather lookup timeout handling",
                status="awaiting_confirmation",
                summary="Added retries and fallback parsing; run completed.",
                tool_names=["web_search", "write_file"],
                metadata={"task_id": 7},
            )

            assert result.get("outcome") == "success"
            assert len(result.get("memory_ids", [])) >= 1
            assert mock_vector_store.add_embedding.call_count >= 1

            events = manager.list_task_learning_events(limit=5)
            assert len(events) == 1
            assert events[0].get("task_description", "").startswith("Fix weather lookup timeout")
            assert events[0].get("outcome") == "success"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_build_task_execution_guidance_uses_task_learning_memories(self, memory_manager):
        """Guidance builder should include repeat/avoid hints from matching task memories."""
        memory_manager.search_memories = AsyncMock(
            return_value=[
                {
                    "text": "Successful pattern: use write_file to persist final output.",
                    "category": "task_learning",
                    "outcome": "success",
                    "similarity": 0.86,
                },
                {
                    "text": "Failure trigger to avoid: task stalled without tool usage.",
                    "category": "task_experience",
                    "outcome": "failure",
                    "similarity": 0.83,
                },
            ]
        )

        context = await memory_manager.get_task_learning_context("Generate a report and save it")
        assert len(context["successes"]) == 1
        assert len(context["failures"]) == 1

        guidance = await memory_manager.build_task_execution_guidance("Generate a report and save it")
        assert "Repeat:" in guidance
        assert "Avoid:" in guidance


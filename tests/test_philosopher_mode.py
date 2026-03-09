"""
Unit tests for PhilosopherMode class.
Tests cover 70%+ of methods as required.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.features.philosopher_mode import PhilosopherMode


class TestPhilosopherMode:
    """Test suite for PhilosopherMode class."""

    @pytest.fixture
    def mock_memory_manager(self):
        """Create a mock memory manager for testing."""
        # Create mock memory manager
        mock_manager = MagicMock()
        # Mock search_memories to return empty list by default
        mock_manager.search_memories = AsyncMock(return_value=[])
        # Mock store_memory to return a memory ID
        mock_manager.store_memory = AsyncMock(return_value="test_memory_id_123")
        return mock_manager

    @pytest.fixture
    def philosopher_mode(self, mock_memory_manager):
        """Create a PhilosopherMode instance for testing."""
        return PhilosopherMode(
            api_key="test_api_key",
            api_base="https://api.test.com/v1",
            model="test-model",
            memory_manager=mock_memory_manager,
            max_cycles=5,
            similarity_threshold=0.3,
            memory_limit=10,
        )

    @pytest.mark.asyncio
    async def test_get_relevant_memories(self, philosopher_mode, mock_memory_manager):
        """Test retrieving relevant memories."""
        # Setup mock to return test memories
        test_memories = [
            {"text": "Test memory 1", "similarity": 0.8},
            {"text": "Test memory 2", "similarity": 0.7},
        ]
        mock_memory_manager.search_memories.return_value = test_memories

        # Call method
        result = await philosopher_mode.get_relevant_memories("test query")

        # Verify results
        assert len(result) == 2
        assert result[0]["text"] == "Test memory 1"
        assert mock_memory_manager.search_memories.called
        # Verify it was called with no category filter
        call_args = mock_memory_manager.search_memories.call_args
        assert call_args.kwargs.get("category") is None

    @pytest.mark.asyncio
    async def test_get_relevant_memories_no_manager(self):
        """Test retrieving memories when memory manager is not available."""
        # Create philosopher mode without memory manager
        philosopher = PhilosopherMode(
            api_key="test_key",
            memory_manager=None,
        )

        # Call method
        result = await philosopher.get_relevant_memories("test query")

        # Should return empty list
        assert result == []

    def test_build_memory_context(self, philosopher_mode):
        """Test building memory context string."""
        # Test with empty memories
        result = philosopher_mode._build_memory_context([])
        assert result == ""

        # Test with memories
        memories = [
            {"text": "Memory 1", "similarity": 0.8},
            {"text": "Memory 2", "similarity": 0.7},
        ]
        result = philosopher_mode._build_memory_context(memories)

        # Verify context includes memory text
        assert "Memory 1" in result
        assert "Memory 2" in result
        assert "0.80" in result or "0.8" in result
        assert "0.70" in result or "0.7" in result

    @pytest.mark.asyncio
    async def test_call_llm_success(self, philosopher_mode):
        """Test successful LLM API call."""
        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test response", "tool_calls": None}}]
        }

        # Patch httpx.AsyncClient
        with patch("src.features.philosopher_mode.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Call method
            result = await philosopher_mode._call_llm(
                [{"role": "user", "content": "test"}]
            )

            # Verify result is a dictionary with content
            assert isinstance(result, dict)
            assert result["content"] == "Test response"
            assert result.get("tool_calls") is None

    @pytest.mark.asyncio
    async def test_call_llm_error(self, philosopher_mode):
        """Test LLM API call with error."""
        # Mock httpx response with error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        # Patch httpx.AsyncClient
        with patch("src.features.philosopher_mode.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Call method - should raise exception on error
            with pytest.raises(Exception) as exc_info:
                await philosopher_mode._call_llm(
                    [{"role": "user", "content": "test"}]
                )
            
            # Verify exception message contains error details
            assert "500" in str(exc_info.value) or "Internal Server Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_contemplation_question(self, philosopher_mode, mock_memory_manager):
        """Test generating a contemplation question."""
        # Setup mocks
        test_memories = [{"text": "Previous thought", "similarity": 0.8}]
        mock_memory_manager.search_memories.return_value = test_memories

        # Mock _call_llm to return a question (as dict with content)
        with patch.object(
            philosopher_mode, "_call_llm", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = {"content": "What is the meaning of existence?", "tool_calls": None}

            # Call method
            result = await philosopher_mode.generate_contemplation_question()

            # Verify result
            assert result == "What is the meaning of existence?"
            assert mock_call.called
            # Verify it was called with system prompt and user prompt
            call_args = mock_call.call_args
            messages = call_args[0][0]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_is_satisfied_with_answer_yes(self, philosopher_mode):
        """Test satisfaction check when answer is satisfactory."""
        # Mock _call_llm to return "yes" (as dict with content)
        with patch.object(
            philosopher_mode, "_call_llm", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = {"content": "Yes, I am satisfied with this answer.", "tool_calls": None}

            # Call method
            result = await philosopher_mode.is_satisfied_with_answer(
                "Test question", "Test answer", "Test answer"
            )

            # Should return True
            assert result is True

    @pytest.mark.asyncio
    async def test_is_satisfied_with_answer_no(self, philosopher_mode):
        """Test satisfaction check when answer is not satisfactory."""
        # Mock _call_llm to return "no" (as dict with content)
        with patch.object(
            philosopher_mode, "_call_llm", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = {"content": "No, I need to think more about this.", "tool_calls": None}

            # Call method
            result = await philosopher_mode.is_satisfied_with_answer(
                "Test question", "Test answer", "Test answer"
            )

            # Should return False
            assert result is False

    @pytest.mark.asyncio
    async def test_is_satisfied_uses_full_contemplation_context_when_short(self, philosopher_mode):
        """When full contemplation is short enough, include it in LLM satisfaction prompt."""
        captured = {}

        async def _capture_call(messages, **kwargs):
            captured["prompt"] = messages[1]["content"]
            return {"content": "no", "tool_calls": None}

        with patch.object(philosopher_mode, "_call_llm", side_effect=_capture_call):
            await philosopher_mode.is_satisfied_with_answer(
                "Test question",
                "Recent step",
                "Full contemplation context should be present.",
            )

        prompt = captured.get("prompt", "")
        assert "Current contemplation context" in prompt
        assert "Full contemplation context should be present." in prompt

    @pytest.mark.asyncio
    async def test_store_contemplation(self, philosopher_mode, mock_memory_manager):
        """Test storing a contemplation in memory."""
        # Call method
        result = await philosopher_mode.store_contemplation(
            question="Test question",
            conclusion="Test conclusion",
            cycle_count=3,
        )

        # Verify result
        assert result == "test_memory_id_123"
        assert mock_memory_manager.store_memory.called

        # Verify it was called with correct parameters
        call_args = mock_memory_manager.store_memory.call_args
        assert "philosopher_contemplation" in call_args.kwargs.get("category", "")
        assert "philosopher_mode" in call_args.kwargs.get("source", "")
        assert call_args.kwargs.get("metadata") is not None
        assert call_args.kwargs["metadata"]["question"] == "Test question"
        assert call_args.kwargs["metadata"]["conclusion"] == "Test conclusion"
        assert call_args.kwargs["metadata"]["cycle_count"] == 3

    @pytest.mark.asyncio
    async def test_store_contemplation_no_manager(self):
        """Test storing contemplation when memory manager is not available."""
        # Create philosopher mode without memory manager
        philosopher = PhilosopherMode(
            api_key="test_key",
            memory_manager=None,
        )

        # Call method
        result = await philosopher.store_contemplation(
            question="Test question",
            conclusion="Test conclusion",
        )

        # Should return None
        assert result is None

    @pytest.mark.asyncio
    async def test_contemplate_question_satisfied(self, philosopher_mode, mock_memory_manager):
        """Test contemplating a question until satisfied."""
        # Setup mocks
        test_memories = [{"text": "Context memory", "similarity": 0.8}]
        mock_memory_manager.search_memories.return_value = test_memories

        # Mock _call_llm to return contemplation steps (as dict with content)
        contemplation_step = "This is my contemplation about the question."
        with patch.object(
            philosopher_mode, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm, patch.object(
            philosopher_mode, "is_satisfied_with_answer", new_callable=AsyncMock
        ) as mock_satisfied, patch.object(
            philosopher_mode, "_get_available_tools", new_callable=AsyncMock
        ) as mock_get_tools:
            # First call returns contemplation, second call checks satisfaction
            mock_call_llm.return_value = {"content": contemplation_step, "tool_calls": None}
            mock_satisfied.return_value = True  # Satisfied after first step
            mock_get_tools.return_value = []  # No tools available

            # Call method
            result = await philosopher_mode.contemplate_question("Test question?")

            # Verify result structure
            assert "question" in result
            assert "contemplation_steps" in result
            assert "conclusion" in result
            assert "cycle_count" in result
            assert result["question"] == "Test question?"
            assert len(result["contemplation_steps"]) > 0
            assert result["cycle_count"] > 0

    @pytest.mark.asyncio
    async def test_contemplate_question_max_cycles(self, philosopher_mode, mock_memory_manager):
        """Test contemplation that reaches max cycles."""
        # Setup mocks
        test_memories = []
        mock_memory_manager.search_memories.return_value = test_memories

        # Mock _call_llm to return contemplation steps (as dict with content)
        contemplation_step = "Thinking about this..."
        with patch.object(
            philosopher_mode, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm, patch.object(
            philosopher_mode, "is_satisfied_with_answer", new_callable=AsyncMock
        ) as mock_satisfied, patch.object(
            philosopher_mode, "_get_available_tools", new_callable=AsyncMock
        ) as mock_get_tools:
            # Never satisfied, will hit max cycles
            mock_call_llm.return_value = {"content": contemplation_step, "tool_calls": None}
            mock_satisfied.return_value = False
            mock_get_tools.return_value = []  # No tools available

            # Set max cycles to 2 for this test
            philosopher_mode.max_cycles = 2

            # Call method
            result = await philosopher_mode.contemplate_question("Test question?")

            # Verify it stopped at max cycles
            assert result["cycle_count"] == 2
            assert len(result["contemplation_steps"]) == 2

    @pytest.mark.asyncio
    async def test_ensure_token_budget_summarizes_when_over_limit(self, mock_memory_manager, monkeypatch):
        monkeypatch.setenv("MAX_TOKEN_LIMIT", "50")
        philosopher = PhilosopherMode(
            api_key="test_api_key",
            api_base="https://api.test.com/v1",
            model="test-model",
            memory_manager=mock_memory_manager,
        )
        long_messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "x" * 500},
            {"role": "assistant", "content": "y" * 500},
            {"role": "user", "content": "z" * 500},
        ]
        summarized = [
            {"role": "system", "content": "system"},
            {"role": "system", "content": "Summary of previous context:\nsummary"},
            {"role": "user", "content": "tail"},
        ]
        philosopher._summarize_messages_for_budget = AsyncMock(return_value=summarized)
        result = await philosopher._ensure_token_budget(long_messages, max_tokens=2000)
        assert result == summarized
        assert philosopher._summarize_messages_for_budget.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


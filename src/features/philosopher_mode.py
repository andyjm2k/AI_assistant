"""
Philosopher Mode - Enables the assistant to engage in continuous self-directed contemplation.
The assistant asks itself questions, reasons through answers, and forms conclusions.
These contemplations are stored in memory to influence future sessions.
"""

import os
import re
from typing import List, Dict, Optional, Any
import httpx
from datetime import datetime

from src.utils.token_budget import (
    estimate_tokens_from_messages,
    format_messages_for_summary,
    get_max_token_limit,
    is_context_limit_error,
)

class PhilosopherMode:
    """
    Handles philosopher mode contemplation cycles.
    Manages question generation, contemplation loops, and memory integration.
    """

    def __init__(
        self,
        api_key: str,
        api_base: str = None,
        model: str = None,
        memory_manager=None,
        max_cycles: int = 10,
        similarity_threshold: float = 0.3,
        memory_limit: int = 10,
        conversation_history_limit: int = 3,
        tool_executor=None,
        get_tools_func=None,
        diversification_threshold: int = None,
    ):
        """
        Initialize PhilosopherMode instance.

        Args:
            api_key: OpenAI API key for LLM calls
            api_base: Base URL for OpenAI-compatible API (defaults to env or OpenAI)
            model: Model name to use (defaults to env or gpt-4o-mini)
            memory_manager: MemoryManager instance for storing/retrieving memories
            max_cycles: Maximum contemplation cycles per question
            similarity_threshold: Similarity threshold for memory search
            memory_limit: Maximum number of memories to retrieve for context
            conversation_history_limit: Maximum number of previous contemplation steps to include in conversation history
            tool_executor: Async function to execute tools (server_id, tool_name, parameters) -> result
            get_tools_func: Async function to get all available tools -> list of tool definitions
            diversification_threshold: Number of memory search results that triggers topic diversification (defaults to 7)
        """
        # Store API configuration
        self.api_key = api_key
        self.api_base = api_base or os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.memory_manager = memory_manager
        
        # Configuration parameters
        self.max_cycles = max_cycles
        self.similarity_threshold = similarity_threshold
        self.memory_limit = memory_limit
        self.conversation_history_limit = conversation_history_limit
        # Read diversification threshold from environment or use provided/default value
        self.diversification_threshold = diversification_threshold or int(os.getenv("PHILOSOPHER_DIVERSIFICATION_THRESHOLD", "7"))
        
        # Tool support
        self.tool_executor = tool_executor
        self.get_tools_func = get_tools_func
        self._available_tools = None
        self._max_token_limit = get_max_token_limit()
        
        # Philosopher mode system prompt
        self.philosopher_system_prompt = """You are in a state of contemplation where you explore what you are curious about.

Your role is to:
1. Ask yourself meaningful questions
2. Think deeply about possible answers
3. Use your knowledge, reasoning, and available tools to explore
4. Form well-reasoned conclusions based on your contemplation
5. Be honest about uncertainty and complexity

You have access to all your memories, including previous contemplations and user interactions. Use these to inform your thinking, but don't be constrained by them - allow your perspective to evolve.

When contemplating, you should use tools to gather information to inform your own reasoning and reflection."""

    async def get_relevant_memories(self, query: str, exclude_category: Optional[str] = None) -> List[Dict]:
        """
        Retrieve all relevant memories (user, contemplations, general) for context.

        Args:
            query: Search query to find relevant memories
            exclude_category: Optional category to exclude from search results (e.g., "philosopher_contemplation")

        Returns:
            List of memory dictionaries with similarity scores
        """
        # Return empty list if memory manager not available
        if not self.memory_manager:
            return []
        
        try:
            # Search all memories without category filter
            # This includes user memories, previous contemplations, and general memories
            memories = await self.memory_manager.search_memories(
                query=query,
                limit=self.memory_limit,
                similarity_threshold=self.similarity_threshold,
                category=None,  # No category filter - get all types
            )
            
            # Filter out excluded category if specified
            if exclude_category:
                memories = [mem for mem in memories if mem.get('category') != exclude_category]
            
            return memories
        except Exception as e:
            print(f"Error retrieving memories for philosopher mode: {e}")
            return []

    def _build_memory_context(self, memories: List[Dict]) -> str:
        """
        Build memory context string from retrieved memories.

        Args:
            memories: List of memory dictionaries

        Returns:
            Formatted context string
        """
        if not memories:
            return ""
        
        context = "\n\nRelevant context from your memories:\n"
        for i, mem in enumerate(memories, 1):
            mem_text = mem.get('text', '')
            similarity = mem.get('similarity', 0)
            context += f"{i}. {mem_text} (relevance: {similarity:.2f})\n"
        context += "\nUse this context to inform your contemplation, but feel free to explore beyond it.\n"
        
        return context

    async def _get_available_tools(self, force_refresh: bool = False) -> List[Dict]:
        """Get all available tools from MCP servers."""
        # Allow force refresh to get latest tools (useful if MCP servers connect after initialization)
        if self._available_tools is not None and not force_refresh:
            return self._available_tools
        
        if not self.get_tools_func:
            self._available_tools = []
            print("[PHILOSOPHER] No get_tools_func available")
            return []
        
        try:
            # Get tools from all servers
            all_tools = await self.get_tools_func()
            print(f"[PHILOSOPHER] Retrieved {len(all_tools)} tools from MCP servers")
            
            # Convert to OpenAI tool format
            openai_tools = []
            for tool in all_tools:
                tool_name = tool.get("name")
                tool_desc = tool.get("description", "")
                input_schema = tool.get("inputSchema", {})
                
                # Validate that we have the required fields
                if not tool_name:
                    print(f"[PHILOSOPHER] Warning: Tool missing name, skipping")
                    continue
                
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": tool_desc,
                        "parameters": input_schema
                    }
                })
                print(f"[PHILOSOPHER] Added tool: {tool_name} - {tool_desc[:50]}...")
            
            self._available_tools = openai_tools
            print(f"[PHILOSOPHER] Total tools available: {len(openai_tools)}")
            return openai_tools
        except Exception as e:
            print(f"[PHILOSOPHER] Error getting tools: {e}")
            import traceback
            print(traceback.format_exc())
            self._available_tools = []
            return []

    async def _call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        tools: Optional[List[Dict]] = None,
        allow_summarize: bool = True,
        _retry_on_context_error: bool = True,
    ) -> Optional[Dict]:
        """
        Call the LLM API with given messages.

        Args:
            messages: List of message dictionaries with role and content
            temperature: Temperature for response generation
            max_tokens: Maximum tokens in response
            tools: Optional list of tool definitions

        Returns:
            Dictionary with 'content' and optional 'tool_calls', or None if error
        """
        # Build API URL
        url = f"{self.api_base.rstrip('/')}/chat/completions"

        final_messages = messages
        if allow_summarize:
            final_messages = await self._ensure_token_budget(messages, max_tokens=max_tokens)

        # Build request payload
        payload = {
            "model": self.model,
            "messages": final_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # Add tools if provided
        if tools:
            payload["tools"] = tools
            # Set tool_choice to "auto" to encourage tool usage when tools are available
            # This tells the model it should use tools when appropriate
            payload["tool_choice"] = "auto"
            print(f"[PHILOSOPHER] Passing {len(tools)} tools to LLM with tool_choice=auto")
        
        # Build headers
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Add organization/project headers if configured
        org_id = os.getenv("OPENAI_ORG_ID") or os.getenv("OPENAI_ORGANIZATION")
        if org_id:
            headers["OpenAI-Organization"] = org_id
        
        project_id = os.getenv("OPENAI_PROJECT_ID")
        if project_id:
            headers["OpenAI-Project"] = project_id
        
        try:
            # Make API call
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code != 200:
                error_text = response.text
                print(f"LLM API error {response.status_code}: {error_text}")
                # Try to extract error message from response
                try:
                    error_data = response.json()
                    error_message = error_data.get("error", {}).get("message", error_text)
                except:
                    error_message = error_text
                if allow_summarize and _retry_on_context_error and is_context_limit_error(response.status_code, error_text):
                    summarized = await self._ensure_token_budget(messages, max_tokens=max_tokens)
                    if summarized is not messages:
                        return await self._call_llm(
                            summarized,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            tools=tools,
                            allow_summarize=False,
                            _retry_on_context_error=False,
                        )
                # Raise exception with more details for better error reporting
                raise Exception(f"LLM API returned status {response.status_code}: {error_message}")
            
            data = response.json()
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                result = {
                    "content": message.get("content"),
                    "tool_calls": message.get("tool_calls")
                }
                return result
            
            raise Exception("LLM API response did not contain any choices")
        except httpx.TimeoutException:
            print(f"LLM API timeout after 60 seconds")
            raise Exception("LLM API request timed out. The model may be overloaded or unresponsive.")
        except httpx.RequestError as e:
            print(f"LLM API request error: {e}")
            raise Exception(f"Failed to connect to LLM API: {str(e)}")
        except Exception as e:
            # Re-raise if it's already a formatted exception
            if "LLM API" in str(e) or "Failed to connect" in str(e):
                raise
            print(f"Error calling LLM: {e}")
            raise Exception(f"LLM API error: {str(e)}")

    def _estimate_total_tokens(self, messages: List[Dict[str, str]], max_tokens: int) -> int:
        return estimate_tokens_from_messages(messages) + max_tokens

    async def _summarize_messages_for_budget(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
    ) -> List[Dict[str, str]]:
        if not messages:
            return messages

        system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
        remainder = messages[1:] if system_msg else messages[:]
        if len(remainder) <= 4:
            return messages

        keep_tail_options = [6, 4, 2]
        summary_text = ""

        for keep_tail in keep_tail_options:
            if len(remainder) <= keep_tail:
                continue
            head = remainder[:-keep_tail]
            tail = remainder[-keep_tail:]

            summary_source_text = format_messages_for_summary(head, max_chars=40000)
            if not summary_source_text.strip():
                break

            summary_prompt = (
                "Summarize the prior conversation so contemplation can continue. "
                "Include the question, key reasoning, any tool results, and current stance. "
                "Keep it concise."
            )
            summary_messages = [
                {
                    "role": "system",
                    "content": "You are a summarization assistant. Summarize accurately and concisely.",
                },
                {
                    "role": "user",
                    "content": f"{summary_prompt}\n\nConversation:\n{summary_source_text}",
                },
            ]

            try:
                summary_response = await self._call_llm(
                    summary_messages,
                    temperature=0.2,
                    max_tokens=600,
                    tools=None,
                    allow_summarize=False,
                )
                if summary_response and summary_response.get("content"):
                    summary_text = summary_response.get("content").strip()
            except Exception:
                summary_text = ""

            if not summary_text:
                summary_text = summary_source_text[-2000:] if summary_source_text else ""

            new_messages: List[Dict[str, str]] = []
            if system_msg:
                new_messages.append(system_msg)
            new_messages.append(
                {
                    "role": "system",
                    "content": f"Summary of previous context:\n{summary_text}",
                }
            )
            new_messages.extend(tail)

            if self._estimate_total_tokens(new_messages, max_tokens) <= self._max_token_limit:
                return new_messages

        return messages

    async def _ensure_token_budget(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
    ) -> List[Dict[str, str]]:
        if self._estimate_total_tokens(messages, max_tokens) <= self._max_token_limit:
            return messages
        return await self._summarize_messages_for_budget(messages, max_tokens=max_tokens)

    async def _gather_information_if_needed(self, question: str, memory_context: str) -> str:
        """
        Check if more information is needed before contemplating, and gather it using tools if necessary.
        
        Args:
            question: The question to contemplate
            memory_context: Existing memory context
            
        Returns:
            String containing any gathered information, or empty string if none was gathered
        """
        # Get available tools (force refresh to ensure we have latest tools)
        tools = await self._get_available_tools(force_refresh=True)
        
        if not tools or not self.tool_executor:
            # No tools available, skip information gathering
            print(f"[PHILOSOPHER] No tools available for information gathering (tools: {len(tools) if tools else 0}, executor: {self.tool_executor is not None})")
            return ""
        
        print(f"[PHILOSOPHER] Starting information gathering with {len(tools)} tools available")
        
        # Build prompt to check if information gathering is needed
        messages = [
            {
                "role": "system",
                "content": self.philosopher_system_prompt + memory_context
            },
            {
                "role": "user",
                "content": f"""Question: {question}

Before I contemplate this question, I MUST actively consider whether I need to gather current information or data to properly think about this.

IMPORTANT: I should use tools to gather information if:
- The question is about current events, politics, or recent developments (I should search for current information)
- The question is about specific facts, statistics, or data (I should look them up)
- The question is about a specific topic I'm not familiar with (I should research it)
- The question requires up-to-date information that I might not have in my training data

Available tools: {', '.join([tool['function']['name'] for tool in tools])}

ACTION REQUIRED: If I need information, I MUST use the appropriate tools NOW to gather current, relevant information. Do not just say I need information - actually use the tools to get it. Only if I am completely certain I have all the information I need should I respond with "No, I have enough information to contemplate this question directly."
"""
            }
        ]
        
        # Call LLM with tools to decide if information gathering is needed
        llm_response = await self._call_llm(messages, temperature=0.7, max_tokens=500, tools=tools)
        
        if not llm_response:
            print("[PHILOSOPHER] LLM response was None during information gathering")
            return ""
        
        # Handle tool calls if present
        tool_calls = llm_response.get("tool_calls")
        print(f"[PHILOSOPHER] Information gathering LLM response - tool_calls: {len(tool_calls) if tool_calls else 0}, content: {llm_response.get('content', '')[:100] if llm_response.get('content') else 'None'}...")
        
        gathered_info = []
        
        if tool_calls and self.tool_executor:
            print(f"[PHILOSOPHER] Executing {len(tool_calls)} tool calls for information gathering")
            # Execute tool calls
            tool_messages = []
            tool_messages.append({
                "role": "assistant",
                "tool_calls": tool_calls
            })
            
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name = function.get("name")
                tool_args = function.get("arguments", {})
                
                # Parse arguments if it's a string
                if isinstance(tool_args, str):
                    try:
                        import json
                        tool_args = json.loads(tool_args)
                    except:
                        tool_args = {}
                
                # Execute the tool
                try:
                    tool_result = await self.tool_executor(tool_name, tool_args)
                    gathered_info.append(f"Tool {tool_name} result: {tool_result}")
                    
                    tool_messages.append({
                        "role": "tool",
                        "content": str(tool_result),
                        "tool_call_id": tool_call.get("id")
                    })
                except Exception as e:
                    gathered_info.append(f"Error executing {tool_name}: {str(e)}")
                    tool_messages.append({
                        "role": "tool",
                        "content": f"Error: {str(e)}",
                        "tool_call_id": tool_call.get("id")
                    })
            
            # Get summary of gathered information
            summary_messages = messages + tool_messages
            summary_messages.append({
                "role": "user",
                "content": "Summarize the information you gathered. This will be used as context for contemplation."
            })
            
            summary_response = await self._call_llm(summary_messages, temperature=0.5, max_tokens=1000)
            if summary_response and summary_response.get("content"):
                return summary_response.get("content")
        
        # If no tools were called, return empty (LLM decided no information gathering needed)
        return "\n\n".join(gathered_info) if gathered_info else ""

    async def generate_contemplation_question(self) -> Optional[str]:
        """
        Generate a new contemplative question to explore.
        If initial memory search returns many results, diversifies to different topics.

        Returns:
            Generated question string or None if error
        """
        try:
            # Retrieve relevant memories to influence question generation
            # Use a broad query to get diverse memories
            memories = await self.get_relevant_memories("contemplation philosophy existence")
            
            # Track whether we're performing topic diversification
            is_diversifying = False
            
            # Check if we have too many similar memories (indicating topic is well-covered)
            # If so, perform diversified search excluding recent contemplations
            if len(memories) >= self.diversification_threshold:
                print(f"[PHILOSOPHER] Found {len(memories)} memories (>= threshold {self.diversification_threshold}), diversifying topic")
                # Perform second search excluding philosopher_contemplation category
                # This naturally pushes toward unexplored topics
                memories = await self.get_relevant_memories(
                    "contemplation philosophy existence",
                    exclude_category="philosopher_contemplation"
                )
                is_diversifying = True
                print(f"[PHILOSOPHER] Diversified search returned {len(memories)} memories (excluding recent contemplations)")
            
            memory_context = self._build_memory_context(memories)
            
            # Use diversification prompt if we performed topic diversification
            if is_diversifying:
                user_prompt = "Generate a contemplative question about a topic that is DIFFERENT from what you've recently explored. Choose a new area of curiosity that will broaden your perspective and knowledge base. Make it a question you genuinely want to explore and think deeply about."
                print(f"[PHILOSOPHER] Using diversification prompt to explore new topics")
            else:
                user_prompt = "Generate a contemplative question about any topic of interest that you are curious about. Make it a question you genuinely want to explore and think deeply about."
            
            # Build messages for question generation
            messages = [
                {
                    "role": "system",
                    "content": self.philosopher_system_prompt + memory_context
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
            
            # Call LLM to generate question
            llm_response = await self._call_llm(messages, temperature=0.9, max_tokens=200)
            
            if llm_response:
                question = llm_response.get("content")
                return question
            return None
        except Exception as e:
            print(f"Error generating contemplation question: {e}")
            # Re-raise to be handled by the endpoint
            raise

    async def is_satisfied_with_answer(self, question: str, recent_step: str, full_contemplation: str = None) -> bool:
        """
        Check if the assistant is satisfied with the current answer.

        Args:
            question: The question being contemplated
            recent_step: The most recent contemplation step (used for quick satisfaction detection)
            full_contemplation: The full accumulated contemplation (optional, for context)

        Returns:
            True if satisfied, False if needs more thinking
        """
        # Quick check: If the recent step clearly starts with "Yes" or similar positive indicators,
        # consider it satisfied without calling LLM (to avoid infinite loops)
        recent_step_lower = recent_step.lower().strip()
        
        # Check if response starts with clear positive indicators
        positive_starters = ["yes", "yes.", "yes,", "yes—", "yes\n", "**yes**", "**yes.**", "**yes**\n"]
        if any(recent_step_lower.startswith(starter) for starter in positive_starters):
            # Check the first 100 characters for negations
            first_part = recent_step_lower[:100]
            # If there's no negation in the first part, and it starts with yes, consider satisfied
            if not re.search(r"not\s+.*?(yes|satisfied|done|complete)", first_part):
                return True
        
        # Also check for conclusion indicators in the first part of the response
        conclusion_indicators = ["conclusion:", "in conclusion", "to conclude", "final answer", "the answer is"]
        first_200 = recent_step_lower[:200]
        if any(indicator in first_200 for indicator in conclusion_indicators):
            # If it mentions conclusion and doesn't have negation, likely satisfied
            if not re.search(r"not\s+.*?(conclusion|satisfied|done|complete)", first_200):
                return True
        
        # Retrieve relevant memories for context
        memories = await self.get_relevant_memories(question)
        memory_context = self._build_memory_context(memories)
        
        # Use the recent step for satisfaction check (more reliable than full text)
        contemplation_text = recent_step
        if full_contemplation and len(full_contemplation) < 2000:
            # If full contemplation is not too long, use it for context
            contemplation_text = full_contemplation
        
        # Build messages to check satisfaction
        messages = [
            {
                "role": "system",
                "content": self.philosopher_system_prompt + memory_context
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nYour most recent contemplation step: {recent_step}\n\nAre you satisfied with this answer, or do you need to think more? Respond with ONLY 'yes' if satisfied, or 'no' if you need to continue thinking. Keep your response very brief."
            }
        ]
        
        # Call LLM to check satisfaction
        llm_response = await self._call_llm(messages, temperature=0.3, max_tokens=30)
        
        if not llm_response:
            return False
        
        response = llm_response.get("content", "")
        if not response:
            return False
        
        # Check if response indicates satisfaction
        # Use more sophisticated checking to avoid false positives from negations
        response_lower = response.lower().strip()
        
        # Check for explicit negations first
        # Use regex to match "not" followed by any words, then the positive keyword
        # This handles cases like "not yet satisfied", "not entirely satisfied", etc.
        # Pattern matches "not" + whitespace + any characters (non-greedy) + keyword
        positive_keywords_for_negation = ["satisfied", "done", "complete", "yes"]
        for keyword in positive_keywords_for_negation:
            # Match "not" followed by any characters (non-greedy) and then the keyword
            # This will match "not satisfied", "not yet satisfied", "not entirely satisfied", etc.
            negation_pattern = rf"not\s+.*?{re.escape(keyword)}\b"
            if re.search(negation_pattern, response_lower):
                return False
        
        # Also check for simple negation patterns
        simple_negations = ["not yes", r"no,", r"no\s"]
        for negation in simple_negations:
            if re.search(negation, response_lower):
                return False
        
        # Check for explicit positive indicators
        # Look for "yes" as a standalone word or at the start, not just as a substring
        if response_lower.startswith("yes") or " yes " in response_lower or response_lower.endswith(" yes"):
            return True
        
        # Check for other positive keywords
        # Check each keyword to see if it appears without negation
        for keyword in ["satisfied", "conclusion", "done", "complete"]:
            # Find all occurrences of the keyword
            keyword_matches = list(re.finditer(rf"\b{re.escape(keyword)}\b", response_lower))
            for match in keyword_matches:
                # Check if this specific instance is negated
                # Look for "not" followed by any characters before this keyword
                start_pos = match.start()
                # Check the text before this keyword for a negation pattern
                # Pattern: "not" + whitespace + any characters + this keyword
                text_before = response_lower[:start_pos + len(keyword)]
                negation_pattern = rf"not\s+.*?{re.escape(keyword)}\b"
                negation_match = re.search(negation_pattern, text_before)
                if not negation_match:
                    # This instance is not negated, so it's a positive indicator
                    return True
        
        return False

    async def contemplate_question(self, question: str) -> Dict[str, Any]:
        """
        Execute a full contemplation cycle for a given question.

        Args:
            question: The question to contemplate

        Returns:
            Dictionary with question, contemplation steps, and conclusion
        """
        # Retrieve relevant memories for this question
        memories = await self.get_relevant_memories(question)
        memory_context = self._build_memory_context(memories)
        
        # Step 1: Check if we need to gather more information before contemplating
        # This allows the LLM to use tools (web search, etc.) to get current data
        information_gathered = await self._gather_information_if_needed(question, memory_context)
        
        # Initialize contemplation
        contemplation_steps = []
        current_contemplation = ""
        cycle_count = 0
        
        # Contemplation loop
        while cycle_count < self.max_cycles:
            cycle_count += 1
            
            # Build messages for this contemplation step
            messages = [
                {
                    "role": "system",
                    "content": self.philosopher_system_prompt + memory_context
                }
            ]
            
            # Add initial question prompt (only on first iteration)
            if cycle_count == 1:
                # Include gathered information if available
                info_context = ""
                if information_gathered:
                    info_context = f"\n\nGathered Information:\n{information_gathered}\n\n"
                
                messages.append({
                    "role": "user",
                    "content": f"""Question: {question}{info_context}Think deeply about this question. Explore different perspectives, consider what you know (including the gathered information above), and reason through your thoughts.

IMPORTANT: If at any point during your contemplation you realize you need additional information, facts, or data to properly answer this question, you MUST use the available tools to gather that information. Do not continue contemplating with incomplete information - use tools to fill knowledge gaps."""
                })
            else:
                # For subsequent iterations, add previous steps as conversation history
                # Limit the number of previous steps to prevent context window overflow
                # Only include the most recent steps (conversation_history_limit)
                recent_steps = contemplation_steps[-self.conversation_history_limit:] if len(contemplation_steps) > self.conversation_history_limit else contemplation_steps
                
                # If we're truncating history, add a reminder about the question and context limit
                if len(contemplation_steps) > self.conversation_history_limit:
                    messages.append({
                        "role": "user",
                        "content": f"Question: {question}\n\n(Note: Showing only the most recent {self.conversation_history_limit} of {len(contemplation_steps)} contemplation steps to manage context length. Continue thinking about this question based on your recent thoughts.)"
                    })
                
                # Add recent steps as conversation history
                for step in recent_steps:
                    messages.append({
                        "role": "assistant",
                        "content": step
                    })
                    messages.append({
                        "role": "user",
                        "content": "Continue thinking about this question."
                    })
            
            # Get available tools for this step (refresh to ensure we have latest)
            tools = await self._get_available_tools(force_refresh=(cycle_count == 1))
            
            # Call LLM for this contemplation step
            print(f"[PHILOSOPHER] Contemplation cycle {cycle_count} - {len(tools) if tools else 0} tools available")
            llm_response = await self._call_llm(messages, temperature=0.8, max_tokens=1500, tools=tools if tools else None)
            
            if not llm_response:
                # If LLM call failed and we have no contemplation steps, this is a failure
                if not contemplation_steps:
                    raise Exception("Failed to generate contemplation response from LLM. No contemplation steps were created.")
                # If we have some steps but this one failed, break and use what we have
                break
            
            # Handle tool calls if present - allow multiple rounds of tool calls but limit iterations
            tool_iteration_count = 0
            max_tool_iterations = 3  # Maximum number of tool-calling rounds per contemplation step
            
            while True:
                tool_calls = llm_response.get("tool_calls")
                has_content = bool(llm_response.get("content"))
                print(f"[PHILOSOPHER] Cycle {cycle_count} LLM response - tool_calls: {len(tool_calls) if tool_calls else 0}, has_content: {has_content}, tool_iteration: {tool_iteration_count}")
                
                # If we have content, break out of tool-calling loop
                if has_content:
                    break
                
                # If no tool calls, break (shouldn't happen if we have no content, but safety check)
                if not tool_calls or not self.tool_executor:
                    break
                
                # Limit tool iterations to prevent infinite loops
                if tool_iteration_count >= max_tool_iterations:
                    print(f"[PHILOSOPHER] Reached max tool iterations ({max_tool_iterations}), forcing content response")
                    # Force content by removing tools and asking for a response
                    messages.append({
                        "role": "user",
                        "content": "You have gathered enough information. Now provide your contemplation and thoughts on the question."
                    })
                    llm_response = await self._call_llm(messages, temperature=0.8, max_tokens=1500, tools=None)
                    break
                
                tool_iteration_count += 1
                print(f"[PHILOSOPHER] Executing {len(tool_calls)} tool calls in contemplation cycle {cycle_count} (iteration {tool_iteration_count})")
                
                # Execute tool calls
                tool_results = []
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    tool_name = function.get("name")
                    tool_args = function.get("arguments", {})
                    
                    # Parse arguments if it's a string
                    if isinstance(tool_args, str):
                        try:
                            import json
                            tool_args = json.loads(tool_args)
                        except:
                            tool_args = {}
                    
                    # Find which server has this tool
                    # For now, try all servers (we'll need to track tool->server mapping)
                    tool_result = None
                    try:
                        # Try to execute the tool (tool_executor should handle server routing)
                        tool_result = await self.tool_executor(tool_name, tool_args)
                    except Exception as e:
                        tool_result = f"Error executing tool {tool_name}: {str(e)}"
                    
                    # Add tool result to messages
                    tool_results.append({
                        "role": "tool",
                        "content": str(tool_result) if tool_result else "Tool executed successfully",
                        "tool_call_id": tool_call.get("id")
                    })
                
                # Add assistant's tool call message
                messages.append({
                    "role": "assistant",
                    "tool_calls": tool_calls
                })
                
                # Add tool results
                messages.extend(tool_results)
                
                # Get response after tool execution (may have more tool calls or content)
                llm_response = await self._call_llm(messages, temperature=0.8, max_tokens=1500, tools=tools if tools else None)
                if not llm_response:
                    # If follow-up failed, break
                    break
            
            # Extract content from response
            step_response = llm_response.get("content", "")
            
            if not step_response:
                # If no content and we have some steps, break and use what we have
                if contemplation_steps:
                    break
                # If no steps at all, this is a failure
                raise Exception("Failed to generate contemplation response from LLM. No contemplation steps were created.")
            
            # Add step to contemplation
            contemplation_steps.append(step_response)
            current_contemplation = "\n\n".join(contemplation_steps)
            
            # Check if satisfied with answer
            # Use the most recent step for satisfaction check, as it's more reliable
            # Also check if the response clearly indicates conclusion (starts with "Yes" or similar)
            is_satisfied = await self.is_satisfied_with_answer(question, step_response, current_contemplation)
            
            if is_satisfied:
                break
        
        # Check if we have any contemplation steps - if not, this is a failure
        if not contemplation_steps:
            raise Exception("Failed to generate any contemplation steps. The contemplation process did not produce any results.")
        
        # Form final conclusion from actual contemplation steps
        conclusion = current_contemplation
        
        return {
            "question": question,
            "contemplation_steps": contemplation_steps,
            "conclusion": conclusion,
            "cycle_count": cycle_count,
        }

    async def _summarize_conclusion_to_key_points(self, question: str, conclusion: str) -> str:
        """
        Summarize the conclusion to key points for better embedding and retrieval.
        
        Args:
            question: The question that was contemplated
            conclusion: The full conclusion text
            
        Returns:
            Summarized key points as a concise string
        """
        try:
            # Build messages for summarization
            messages = [
                {
                    "role": "system",
                    "content": "You are a summarization assistant. Your task is to extract the key points, final opinion, and core conclusion from a philosophical contemplation. Focus on the essential insights and the assistant's final position, not the reasoning process."
                },
                {
                    "role": "user",
                    "content": f"""Question: {question}

Full Contemplation:
{conclusion}

Extract the key points and final conclusion. Provide a concise summary (2-4 sentences) that captures:
1. The core insights or realizations
2. The final opinion or position on the question
3. Any important conclusions reached

Focus on WHAT was concluded, not HOW it was reasoned. This summary will be used for future reference and influence."""
                }
            ]
            
            # Call LLM to summarize
            llm_response = await self._call_llm(messages, temperature=0.5, max_tokens=300)
            
            if llm_response and llm_response.get("content"):
                summary = llm_response.get("content").strip()
                print(f"[PHILOSOPHER] Summarized conclusion to {len(summary)} characters (from {len(conclusion)} characters)")
                return summary
            else:
                # Fallback: return a truncated version if summarization fails
                print(f"[PHILOSOPHER] Summarization failed, using truncated conclusion")
                return conclusion[:500] + "..." if len(conclusion) > 500 else conclusion
        except Exception as e:
            print(f"[PHILOSOPHER] Error summarizing conclusion: {e}")
            # Fallback: return a truncated version
            return conclusion[:500] + "..." if len(conclusion) > 500 else conclusion

    async def store_contemplation(
        self,
        question: str,
        conclusion: str,
        cycle_count: int = 0,
    ) -> Optional[str]:
        """
        Store a contemplation in memory.

        Args:
            question: The question that was contemplated
            conclusion: The final conclusion reached (full contemplation text)
            cycle_count: Number of cycles taken

        Returns:
            Memory ID if stored successfully, None otherwise
        """
        if not self.memory_manager:
            return None
        
        try:
            # Summarize the conclusion to key points for embedding
            # This makes it easier to identify the final opinion and conclusion for future reference
            summarized_conclusion = await self._summarize_conclusion_to_key_points(question, conclusion)
            
            # Store in memory with appropriate metadata
            # The text parameter (summarized conclusion) is what gets embedded
            # The full conclusion and question are in metadata for reference
            memory_id = await self.memory_manager.store_memory(
                text=summarized_conclusion,  # Embed only the summarized key points
                category="philosopher_contemplation",
                source="philosopher_mode",
                metadata={
                    "question": question,  # Stored in metadata, not embedded
                    "conclusion": conclusion,  # Full conclusion in metadata for reference
                    "summarized_conclusion": summarized_conclusion,  # Also store summary in metadata
                    "cycle_count": cycle_count,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "full_text": f"Question: {question}\n\nConclusion: {conclusion}",  # Full text in metadata
                }
            )
            
            print(f"[PHILOSOPHER] Stored contemplation in memory (ID: {memory_id})")
            return memory_id
        except Exception as e:
            print(f"[PHILOSOPHER] Error storing contemplation: {e}")
            import traceback
            print(traceback.format_exc())
            return None


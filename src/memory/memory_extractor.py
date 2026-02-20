"""
Automatic memory extraction from conversations.
Uses LLM to identify important information to remember.
"""

import os
from typing import List, Dict, Optional
import httpx
from datetime import datetime


class MemoryExtractor:
    """
    Extracts important information from conversations for storage.
    Uses LLM to analyze conversations and identify facts to remember.
    """

    def __init__(
        self,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """
        Initialize memory extractor.

        Args:
            api_base: Base URL for LLM API (defaults to env var or OpenAI)
            model: Model name for extraction (defaults to env var or gpt-4o-mini)
            api_key: API key for authentication (optional for local models)
        """
        # Get configuration from environment variables or use defaults
        # Support MEMORY_EXTRACTOR_API_BASE for explicit configuration, fall back to OPENAI_API_BASE
        self.api_base = api_base or os.getenv(
            "MEMORY_EXTRACTOR_API_BASE",
            os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        )
        # Normalize base URL (remove trailing slash)
        self.api_base = self.api_base.rstrip("/")
        
        # Get model name (support MEMORY_EXTRACTOR_MODEL, fall back to OPENAI_MODEL)
        # Default to gpt-4o-mini for cost efficiency, but allow override for local models
        self.model = model or os.getenv(
            "MEMORY_EXTRACTOR_MODEL",
            os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        )
        
        # Get API key (optional for local models like LM Studio)
        # Support MEMORY_EXTRACTOR_API_KEY, fall back to OPENAI_API_KEY
        self.api_key = api_key or os.getenv("MEMORY_EXTRACTOR_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        # Build chat endpoint URL
        self.chat_url = f"{self.api_base}/chat/completions"
        
        # Categories for memory classification
        self.categories = [
            "preference",  # User preferences (e.g., "likes dark mode")
            "habit",       # User habits (e.g., "works late nights")
            "fact",        # Facts about user (e.g., "lives in New York")
            "need",        # User needs (e.g., "needs help with Python")
            "relationship", # Relationships (e.g., "has a dog named Max")
        ]

    async def extract_memories(
        self,
        messages: List[Dict[str, str]],
        max_memories: int = 3,
    ) -> List[Dict]:
        """
        Extract important memories from a conversation.

        Args:
            messages: List of conversation messages (role/content format)
            max_memories: Maximum number of memories to extract (at most; often 0)

        Returns:
            List of memory dictionaries with text, category, and confidence
        """
        # API key is optional for local models (like LM Studio)
        # Only skip if explicitly required via environment variable
        require_key = os.getenv("MEMORY_EXTRACTOR_REQUIRE_KEY", "false").lower() == "true"
        if require_key and not self.api_key:
            print("Warning: Memory extraction requires API key but none provided")
            return []
        
        # Build extraction prompt
        conversation_text = self._format_conversation(messages)
        
        extraction_prompt = f"""Analyze the following conversation and identify information about the user that is genuinely important to remember for future conversations.

What counts as "important":
- Something the USER explicitly said about themselves: preferences, situation, relationships, or needs
- Specific and likely to be useful in future chats (e.g. "User prefers dark mode", "User lives in London")
- Durable facts, not one-off context (e.g. avoid "User is working on X today" unless it reflects an ongoing need)

Do NOT include:
- Inferred or vague observations the user did not state
- One-off task context, small talk, or politeness ("thanks", "ok")
- Generic statements or advice that could apply to anyone
- Anything you are unsure about; when in doubt, omit it

Categories (only if you extract): preference, habit, fact, need, relationship.

Extract at most {max_memories} items. Often there will be zero. If nothing in this conversation meets the bar above, respond with an empty array: []

For each item you do extract, provide:
1. "text": concise statement (1-2 sentences)
2. "category": one of preference, habit, fact, need, relationship
3. "confidence": use "high" only when the user clearly stated it; otherwise "medium" or "low"

Respond with a JSON array only, e.g. [] or [{{"text": "...", "category": "...", "confidence": "high"}}].

Conversation:
{conversation_text}

JSON:"""

        # System message: allow empty array and stress selectivity
        system_content = (
            "You are a memory extraction system. You output a JSON array of memories. "
            "Return an empty array [] when nothing in the conversation is important enough to remember. "
            "Do not try to fill the list; it is better to return nothing than to store low-value items. "
            "Always respond with valid JSON only (a single array, or an object containing an array under 'memories' or 'items')."
        )
        # Prepare request payload
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_content
                },
                {
                    "role": "user",
                    "content": extraction_prompt
                }
            ],
            "temperature": 0.3,  # Lower temperature for more consistent extraction
        }
        
        # Only add response_format if explicitly enabled and model supports it
        # Local models (like LM Studio) may not support this parameter
        use_json_format = os.getenv("MEMORY_EXTRACTOR_USE_JSON_FORMAT", "false").lower() == "true"
        if use_json_format and ("gpt" in self.model.lower() or "o1" in self.model.lower()):
            payload["response_format"] = {"type": "json_object"}
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
        }
        # Only add Authorization header if API key is provided
        # Local models like LM Studio don't require authentication
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Make async HTTP request
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.chat_url,
                    json=payload,
                    headers=headers,
                )
                
                # Check for HTTP errors
                if response.status_code != 200:
                    print(f"Memory extraction API error: {response.status_code} - {response.text}")
                    return []
                
                # Parse response
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Parse JSON response
                import json
                try:
                    # Try to parse as JSON object first
                    parsed = json.loads(content)
                    # If it's a dict with a key, extract the array
                    if isinstance(parsed, dict):
                        # Look for common keys like "memories", "items", or first array value
                        # Check if keys exist (not just if values are truthy) to handle empty lists correctly
                        if "memories" in parsed:
                            memories = parsed["memories"]
                        elif "items" in parsed:
                            memories = parsed["items"]
                        else:
                            # Get first array value from dict
                            memories = None
                            for value in parsed.values():
                                if isinstance(value, list):
                                    memories = value
                                    break
                            if memories is None:
                                memories = []
                    elif isinstance(parsed, list):
                        memories = parsed
                    else:
                        memories = []
                except json.JSONDecodeError:
                    # If JSON parsing fails, try to extract JSON array from text
                    import re
                    # Try to find JSON array in the response
                    json_match = re.search(r'\[.*\]', content, re.DOTALL)
                    if json_match:
                        try:
                            memories = json.loads(json_match.group())
                        except json.JSONDecodeError:
                            memories = []
                    else:
                        print(f"Failed to parse extraction response: {content}")
                        return []
                
                # Validate and format memories
                extracted_memories = []
                for mem in memories:
                    if isinstance(mem, dict) and "text" in mem:
                        extracted_memories.append({
                            "text": mem.get("text", ""),
                            "category": mem.get("category", "general"),
                            "confidence": mem.get("confidence", "medium"),
                            "source": "conversation",
                        })
                
                return extracted_memories
                
        except httpx.RequestError as e:
            print(f"Memory extraction request error: {str(e)}")
            return []
        except Exception as e:
            print(f"Memory extraction error: {str(e)}")
            return []

    def _format_conversation(self, messages: List[Dict[str, str]]) -> str:
        """
        Format conversation messages into a readable string.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Formatted conversation string
        """
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role.capitalize()}: {content}")
        
        return "\n".join(formatted)


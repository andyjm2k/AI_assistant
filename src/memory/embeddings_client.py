"""
OpenAI-compatible embeddings client for generating vector embeddings.
Supports both local and cloud embeddings endpoints.
"""

import inspect
import os
from typing import List, Optional

import httpx
from pydantic import BaseModel


class EmbeddingResponse(BaseModel):
    """Response model for embedding API."""
    embedding: List[float]
    model: str


class EmbeddingsClient:
    """
    Client for OpenAI-compatible embeddings API.
    Supports both local (LM Studio, Ollama) and cloud (OpenAI) endpoints.
    """

    def __init__(
        self,
        api_base: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize embeddings client.

        Args:
            api_base: Base URL for embeddings API (defaults to OpenAI or env var)
            model: Model name for embeddings (defaults to text-embedding-ada-002)
            api_key: API key for authentication (optional for local models)
            timeout: Request timeout in seconds
        """
        # Get configuration from environment variables or use defaults
        self.api_base = api_base or os.getenv(
            "EMBEDDINGS_API_BASE",
            os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        )
        # Normalize base URL (remove trailing slash)
        self.api_base = self.api_base.rstrip("/")
        
        # Get model name (default to text-embedding-ada-002)
        self.model = model or os.getenv(
            "EMBEDDINGS_MODEL",
            "text-embedding-ada-002"
        )
        
        # Get API key (optional for local models)
        self.api_key = api_key or os.getenv("EMBEDDINGS_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        # Set timeout for requests
        self.timeout = timeout
        
        # Build embeddings endpoint URL
        self.embeddings_url = f"{self.api_base}/embeddings"

    @staticmethod
    async def _read_response_json(response) -> dict:
        """Handle both real httpx responses and async-mocked response.json callables."""
        data = response.json()
        if inspect.isawaitable(data):
            data = await data
        return data

    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for a text string.

        Args:
            text: Text to embed

        Returns:
            List of float values representing the embedding vector

        Raises:
            Exception: If embedding generation fails
        """
        # Prepare request payload (OpenAI-compatible format)
        payload = {
            "model": self.model,
            "input": text,
        }
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
        }
        
        # Add API key if available
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Make async HTTP request
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.embeddings_url,
                    json=payload,
                    headers=headers,
                )
                
                # Check for HTTP errors
                if response.status_code != 200:
                    error_text = response.text
                    raise Exception(
                        f"Embeddings API returned status {response.status_code}: {error_text}"
                    )
                
                # Parse response
                data = await self._read_response_json(response)
                
                # Handle OpenAI format: data[0].embedding
                if "data" in data and len(data["data"]) > 0:
                    embedding = data["data"][0].get("embedding", [])
                # Handle alternative format: embedding directly
                elif "embedding" in data:
                    embedding = data["embedding"]
                else:
                    raise Exception(f"Unexpected response format: {data}")
                
                # Normalize embedding vector (L2 normalization for cosine similarity)
                embedding = self._normalize_vector(embedding)
                
                return embedding
                
        except httpx.RequestError as e:
            raise Exception(f"Failed to connect to embeddings API: {str(e)}")
        except Exception as e:
            raise Exception(f"Error generating embedding: {str(e)}")

    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for multiple texts in a single request.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        # Prepare request payload with batch input
        payload = {
            "model": self.model,
            "input": texts,
        }
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
        }
        
        # Add API key if available
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # Make async HTTP request
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.embeddings_url,
                    json=payload,
                    headers=headers,
                )
                
                # Check for HTTP errors
                if response.status_code != 200:
                    error_text = response.text
                    raise Exception(
                        f"Embeddings API returned status {response.status_code}: {error_text}"
                    )
                
                # Parse response
                data = await self._read_response_json(response)
                
                # Handle OpenAI format: data array with multiple embeddings
                if "data" in data:
                    embeddings = [item.get("embedding", []) for item in data["data"]]
                else:
                    raise Exception(f"Unexpected response format: {data}")
                
                # Normalize all embedding vectors
                embeddings = [self._normalize_vector(emb) for emb in embeddings]
                
                return embeddings
                
        except httpx.RequestError as e:
            raise Exception(f"Failed to connect to embeddings API: {str(e)}")
        except Exception as e:
            raise Exception(f"Error generating embeddings: {str(e)}")

    @staticmethod
    def _normalize_vector(vector: List[float]) -> List[float]:
        """
        Normalize a vector using L2 normalization.
        This ensures cosine similarity works correctly.

        Args:
            vector: Input vector

        Returns:
            Normalized vector
        """
        import math
        
        # Calculate L2 norm
        norm = math.sqrt(sum(x * x for x in vector))
        
        # Avoid division by zero
        if norm == 0:
            return vector
        
        # Normalize by dividing by norm
        return [x / norm for x in vector]


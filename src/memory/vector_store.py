"""
Local file-based vector store for storing and searching embeddings.
Uses numpy for efficient vector operations and cosine similarity search.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import uuid
import numpy as np


class VectorStore:
    """
    Local file-based vector store for embeddings.
    Stores embeddings as numpy arrays and metadata as JSON.
    """

    def __init__(self, storage_path: str = "./memory_data"):
        """
        Initialize vector store.

        Args:
            storage_path: Directory path for storing embeddings and metadata
        """
        # Convert to Path object for easier manipulation
        self.storage_path = Path(storage_path)
        
        # Create storage directory if it doesn't exist
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Define file paths
        self.embeddings_file = self.storage_path / "embeddings.npy"
        self.metadata_file = self.storage_path / "metadata.json"
        self.config_file = self.storage_path / "config.json"
        
        # Initialize storage structures
        self.embeddings: np.ndarray = np.array([])  # Shape: [n_memories, embedding_dim]
        self.metadata: Dict[str, Dict] = {}  # Map memory_id -> metadata dict
        
        # Load existing data if available
        self._load()

    def _load(self) -> None:
        """Load embeddings and metadata from disk."""
        # Load embeddings if file exists
        if self.embeddings_file.exists():
            try:
                self.embeddings = np.load(str(self.embeddings_file))
            except Exception as e:
                print(f"Warning: Failed to load embeddings: {e}")
                self.embeddings = np.array([])
        
        # Load metadata if file exists
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.metadata = {item["id"]: item for item in data.get("memories", [])}
            except Exception as e:
                print(f"Warning: Failed to load metadata: {e}")
                self.metadata = {}
        
        # Validate consistency between embeddings and metadata
        self._validate_consistency()

    def _save(self) -> None:
        """Save embeddings and metadata to disk."""
        # Save embeddings array. When empty, remove stale on-disk vectors.
        if len(self.embeddings) > 0:
            np.save(str(self.embeddings_file), self.embeddings)
        elif self.embeddings_file.exists():
            try:
                self.embeddings_file.unlink()
            except Exception as e:
                print(f"Warning: Failed to remove stale embeddings file: {e}")
        
        # Save metadata as JSON
        memories_list = list(self.metadata.values())
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump({"memories": memories_list}, f, indent=2, ensure_ascii=False)
        
        # Save config
        config = {
            "embedding_dim": int(self.embeddings.shape[1]) if len(self.embeddings) > 0 else 0,
            "num_memories": len(self.metadata),
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

    def _validate_consistency(self) -> None:
        """Validate that embeddings and metadata are consistent."""
        # Check if number of embeddings matches number of metadata entries
        num_embeddings = len(self.embeddings) if len(self.embeddings) > 0 else 0
        num_metadata = len(self.metadata)
        
        # If mismatch, keep the smaller set and warn
        if num_embeddings != num_metadata:
            print(f"Warning: Embeddings ({num_embeddings}) and metadata ({num_metadata}) count mismatch")
            
            # If we have more embeddings than metadata, truncate embeddings
            if num_embeddings > num_metadata:
                self.embeddings = self.embeddings[:num_metadata]
            # If we have more metadata than embeddings, remove extra metadata
            elif num_metadata > num_embeddings:
                # Keep only first num_embeddings metadata entries
                metadata_items = list(self.metadata.items())[:num_embeddings]
                self.metadata = dict(metadata_items)

    def add_embedding(
        self,
        embedding: List[float],
        text: str,
        category: Optional[str] = None,
        source: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """
        Add an embedding to the store.

        Args:
            embedding: Embedding vector
            text: Original text that was embedded
            category: Category of the memory (e.g., "preference", "habit")
            source: Source of the memory (e.g., "conversation", "explicit")
            metadata: Additional metadata to store

        Returns:
            Memory ID of the added embedding
        """
        # Convert embedding to numpy array
        embedding_array = np.array(embedding, dtype=np.float32)
        
        # Normalize embedding vector (L2 normalization for cosine similarity)
        # This ensures consistency even if embeddings weren't normalized before
        norm = np.linalg.norm(embedding_array)
        if norm > 0:
            embedding_array = embedding_array / norm
        
        # Check if this is the first embedding
        if len(self.embeddings) == 0:
            # Initialize embeddings array with this embedding
            self.embeddings = embedding_array.reshape(1, -1)
        else:
            # Validate embedding dimension matches existing embeddings
            expected_dim = self.embeddings.shape[1]
            if len(embedding_array) != expected_dim:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {expected_dim}, got {len(embedding_array)}"
                )
            
            # Append embedding to array
            self.embeddings = np.vstack([self.embeddings, embedding_array.reshape(1, -1)])
        
        # Generate unique memory ID
        memory_id = f"mem_{uuid.uuid4().hex[:12]}"
        
        # Get embedding index
        embedding_index = len(self.embeddings) - 1
        
        # Create metadata entry
        memory_metadata = {
            "id": memory_id,
            "text": text,
            "category": category or "general",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": source or "unknown",
            "embedding_index": embedding_index,
        }
        
        # Add any additional metadata
        if metadata:
            memory_metadata.update(metadata)
        
        # Store metadata
        self.metadata[memory_id] = memory_metadata
        
        # Save to disk
        self._save()
        
        return memory_id

    def search(
        self,
        query_embedding: List[float],
        limit: int = 5,
        similarity_threshold: float = 0.7,
        category: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search for similar embeddings using cosine similarity.

        Args:
            query_embedding: Query embedding vector
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            category: Optional category filter

        Returns:
            List of memory dictionaries with similarity scores, sorted by relevance
        """
        # If no embeddings stored, return empty list
        if len(self.embeddings) == 0:
            return []
        
        # Convert query embedding to numpy array
        query_vector = np.array(query_embedding, dtype=np.float32)
        
        # Validate dimension
        if len(query_vector) != self.embeddings.shape[1]:
            raise ValueError(
                f"Query embedding dimension mismatch: expected {self.embeddings.shape[1]}, got {len(query_vector)}"
            )
        
        # Normalize query vector for cosine similarity
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []
        query_vector = query_vector / query_norm
        
        # Calculate cosine similarity (dot product of normalized vectors)
        # embeddings are already normalized when stored
        similarities = np.dot(self.embeddings, query_vector)
        
        # Get indices sorted by similarity (descending)
        sorted_indices = np.argsort(similarities)[::-1]
        
        # Filter by threshold and category, then limit results
        results = []
        for idx in sorted_indices:
            similarity = float(similarities[idx])
            
            # Skip if below threshold
            if similarity < similarity_threshold:
                continue
            
            # Find memory with this embedding index
            memory_id = None
            for mem_id, mem_data in self.metadata.items():
                if mem_data.get("embedding_index") == int(idx):
                    memory_id = mem_id
                    break
            
            if not memory_id:
                continue
            
            # Get memory metadata
            memory = self.metadata[memory_id].copy()
            
            # Filter by category if specified
            if category and memory.get("category") != category:
                continue
            
            # Add similarity score
            memory["similarity"] = similarity
            
            results.append(memory)
            
            # Stop if we have enough results
            if len(results) >= limit:
                break
        
        return results

    def get_memory(self, memory_id: str) -> Optional[Dict]:
        """
        Get memory by ID.

        Args:
            memory_id: Memory ID

        Returns:
            Memory metadata dict or None if not found
        """
        return self.metadata.get(memory_id)

    def get_memories_by_category(self, category: str) -> List[Dict]:
        """
        Get all memories in a specific category.

        Args:
            category: Category name

        Returns:
            List of memory metadata dicts
        """
        return [
            memory.copy()
            for memory in self.metadata.values()
            if memory.get("category") == category
        ]

    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a memory by ID.

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deleted, False if not found
        """
        if memory_id not in self.metadata:
            return False
        
        # Get embedding index with default value to handle missing keys
        embedding_index = self.metadata[memory_id].get("embedding_index")
        
        # Remove from metadata
        del self.metadata[memory_id]
        
        # Remove embedding from array only if we have a valid embedding_index
        if len(self.embeddings) > 0 and embedding_index is not None:
            # Validate embedding_index is within bounds
            if isinstance(embedding_index, int) and 0 <= embedding_index < len(self.embeddings):
                # Create new array without the deleted embedding
                indices = [i for i in range(len(self.embeddings)) if i != embedding_index]
                if indices:
                    self.embeddings = self.embeddings[indices]
                else:
                    self.embeddings = np.array([])
                
                # Update embedding indices in remaining metadata
                # Only update if embedding_index was valid
                for mem_data in self.metadata.values():
                    old_idx = mem_data.get("embedding_index", -1)
                    # Only compare if both are valid integers
                    if isinstance(old_idx, int) and isinstance(embedding_index, int) and old_idx > embedding_index:
                        mem_data["embedding_index"] = old_idx - 1
        
        # Save to disk
        self._save()
        
        return True

    def list_memories(self, limit: Optional[int] = None) -> List[Dict]:
        """
        List all memories, optionally limited.

        Args:
            limit: Maximum number of memories to return

        Returns:
            List of memory metadata dicts, sorted by timestamp (newest first)
        """
        memories = list(self.metadata.values())
        
        # Sort by timestamp (newest first)
        memories.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Apply limit if specified
        if limit:
            memories = memories[:limit]
        
        return [memory.copy() for memory in memories]

    def count(self) -> int:
        """Get total number of stored memories."""
        return len(self.metadata)


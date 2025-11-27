"""Abstract base class for embedding models.

This module defines the interface that all embedding models must implement,
allowing for easy swapping between different models (Titan, SapBERT, etc.)
via environment variables.
"""

from abc import ABC, abstractmethod
from typing import List, Union


class EmbeddingModel(ABC):
    """Abstract base class for embedding models.
    
    All embedding models must implement this interface to ensure
    consistency and swappability.
    """
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of the embedding vectors.
        
        Returns:
            int: Vector dimension (e.g., 1024 for Titan, 768 for SapBERT)
        """
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the name/identifier of the embedding model.
        
        Returns:
            str: Model name (e.g., "titan-embed-text-v2", "sapbert")
        """
        pass
    
    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding vector for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            List of floats representing the embedding vector
            
        Raises:
            ValueError: If text is empty or invalid
            Exception: If the underlying model API fails
        """
        pass
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for multiple texts.
        
        Default implementation calls embed() for each text sequentially.
        Subclasses can override this for more efficient batch processing.
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of embedding vectors (list of lists of floats)
            
        Raises:
            ValueError: If texts list is empty or contains invalid entries
            Exception: If the underlying model API fails
        """
        if not texts:
            raise ValueError("texts list cannot be empty")
        
        return [self.embed(text) for text in texts]
    
    def validate_text(self, text: str) -> None:
        """Validate input text before embedding.
        
        Args:
            text: Input text to validate
            
        Raises:
            ValueError: If text is empty, None, or invalid
        """
        if text is None:
            raise ValueError("text cannot be None")
        
        if not isinstance(text, str):
            raise ValueError(f"text must be string, got {type(text)}")
        
        if not text.strip():
            raise ValueError("text cannot be empty or whitespace only")


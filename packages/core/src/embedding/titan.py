"""Bedrock Titan Embeddings v2 implementation.

This module implements the EmbeddingModel interface using AWS Bedrock's
Titan Text Embeddings v2 model for generating 1024-dimensional vectors.
"""

import json
from typing import List

import boto3

from .base import EmbeddingModel


class TitanEmbedding(EmbeddingModel):
    """Bedrock Titan Text Embeddings v2 model.
    
    Uses AWS Bedrock's invoke_model API to generate 1024-dimensional
    embedding vectors optimized for semantic search.
    
    Configuration is loaded from centralized config to avoid hard-coding
    model IDs or regions.
    """
    
    def __init__(self, region: str = "us-east-1"):
        """Initialize Titan embedding model.
        
        Args:
            region: AWS region for Bedrock (default: us-east-1)
        """
        self.region = region
        self._client = None
        self._model_id = "amazon.titan-embed-text-v2:0"
    
    @property
    def client(self):
        """Lazy-load Bedrock client.
        
        Returns:
            boto3 Bedrock Runtime client
        """
        if self._client is None:
            self._client = boto3.client(
                service_name="bedrock-runtime",
                region_name=self.region
            )
        return self._client
    
    @property
    def dimension(self) -> int:
        """Return Titan v2 embedding dimension.
        
        Returns:
            1024 (Titan v2 default dimension)
        """
        return 1024
    
    @property
    def model_name(self) -> str:
        """Return Titan model identifier.
        
        Returns:
            Model ID used for Bedrock API calls
        """
        return self._model_id
    
    def embed(self, text: str) -> List[float]:
        """Generate embedding vector using Titan v2.
        
        Args:
            text: Input text to embed (drug name, query, etc.)
            
        Returns:
            1024-dimensional embedding vector
            
        Raises:
            ValueError: If text is empty or invalid
            Exception: If Bedrock API call fails
        """
        # Validate input
        self.validate_text(text)
        
        # Prepare request body for Titan v2
        request_body = {
            "inputText": text,
            "dimensions": 1024,
            "normalize": True  # Normalize for cosine similarity
        }
        
        try:
            # Call Bedrock API
            response = self.client.invoke_model(
                modelId=self._model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response["body"].read())
            embedding = response_body.get("embedding")
            
            if not embedding:
                raise ValueError("No embedding returned from Titan")
            
            if len(embedding) != 1024:
                raise ValueError(
                    f"Expected 1024-dim vector, got {len(embedding)}-dim"
                )
            
            return embedding
            
        except Exception as e:
            raise Exception(f"Titan embedding failed: {str(e)}") from e
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.
        
        Note: Titan v2 doesn't support native batch processing via Bedrock.
        This implementation calls embed() sequentially. For large batches,
        consider using concurrent processing at the application level.
        
        Args:
            texts: List of input texts to embed
            
        Returns:
            List of 1024-dimensional embedding vectors
            
        Raises:
            ValueError: If texts list is empty or contains invalid entries
            Exception: If any Bedrock API call fails
        """
        if not texts:
            raise ValueError("texts list cannot be empty")
        
        embeddings = []
        for i, text in enumerate(texts):
            try:
                embedding = self.embed(text)
                embeddings.append(embedding)
            except Exception as e:
                raise Exception(
                    f"Batch embedding failed at index {i} for text '{text[:50]}...': {str(e)}"
                ) from e
        
        return embeddings


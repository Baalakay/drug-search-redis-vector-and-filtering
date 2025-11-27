"""Embedding model factory and exports.

This module provides a factory function to instantiate the appropriate
embedding model based on environment variables, enabling zero-code-change
model swapping.

Usage:
    # Set environment variable
    export EMBEDDING_MODEL=titan  # or sapbert
    
    # Get model instance
    from embedding import get_embedding_model
    
    model = get_embedding_model()
    vector = model.embed("lisinopril 10mg tablet")
    
    # Switch models by changing environment variable only
    # No code changes required!
"""

import os
from typing import Optional

from .base import EmbeddingModel
from .titan import TitanEmbedding
from .sapbert import SapBERTEmbedding


# Export public API
__all__ = [
    "EmbeddingModel",
    "TitanEmbedding", 
    "SapBERTEmbedding",
    "get_embedding_model",
]


def get_embedding_model(
    model_type: Optional[str] = None,
    region: str = "us-east-1",
    **kwargs
) -> EmbeddingModel:
    """Factory function to get the appropriate embedding model.
    
    The model type can be specified via:
    1. Direct parameter: model_type="titan"
    2. Environment variable: EMBEDDING_MODEL=titan
    3. Default: "titan" (if neither is set)
    
    Args:
        model_type: Model to use ("titan" or "sapbert").
                   If None, reads from EMBEDDING_MODEL env var.
        region: AWS region for Bedrock/SageMaker (default: us-east-1)
        **kwargs: Additional model-specific parameters
                 (e.g., endpoint_name for SapBERT)
    
    Returns:
        Instance of EmbeddingModel (TitanEmbedding or SapBERTEmbedding)
    
    Raises:
        ValueError: If model_type is invalid or unsupported
        NotImplementedError: If SapBERT is requested but not deployed
    
    Examples:
        # Use Titan (default)
        model = get_embedding_model()
        
        # Use Titan explicitly
        model = get_embedding_model(model_type="titan")
        
        # Use SapBERT (when deployed)
        model = get_embedding_model(
            model_type="sapbert",
            endpoint_name="sapbert-prod-endpoint"
        )
        
        # Use environment variable
        os.environ["EMBEDDING_MODEL"] = "titan"
        model = get_embedding_model()
    """
    # Determine model type
    if model_type is None:
        model_type = os.getenv("EMBEDDING_MODEL", "titan").lower()
    else:
        model_type = model_type.lower()
    
    # Validate model type
    valid_models = ["titan", "sapbert"]
    if model_type not in valid_models:
        raise ValueError(
            f"Invalid model_type: '{model_type}'. "
            f"Must be one of: {', '.join(valid_models)}"
        )
    
    # Instantiate appropriate model
    if model_type == "titan":
        return TitanEmbedding(region=region)
    
    elif model_type == "sapbert":
        endpoint_name = kwargs.get("endpoint_name")
        
        if not endpoint_name:
            # Try to get from environment variable
            endpoint_name = os.getenv("SAPBERT_ENDPOINT")
        
        if not endpoint_name:
            raise ValueError(
                "SapBERT requires endpoint_name parameter or "
                "SAPBERT_ENDPOINT environment variable"
            )
        
        return SapBERTEmbedding(
            endpoint_name=endpoint_name,
            region=region
        )
    
    # Should never reach here due to validation above
    raise ValueError(f"Unsupported model type: {model_type}")


def get_default_model(region: str = "us-east-1") -> EmbeddingModel:
    """Get the default embedding model (Titan).
    
    Convenience function that always returns Titan, regardless of
    environment variables.
    
    Args:
        region: AWS region for Bedrock (default: us-east-1)
    
    Returns:
        TitanEmbedding instance
    
    Examples:
        model = get_default_model()
        vector = model.embed("aspirin 81mg tablet")
    """
    return TitanEmbedding(region=region)


# Example usage patterns for documentation
if __name__ == "__main__":
    # Example 1: Use factory with default (Titan)
    print("Example 1: Default model (Titan)")
    model = get_embedding_model()
    print(f"Model: {model.model_name}")
    print(f"Dimension: {model.dimension}")
    
    # Example 2: Explicit model selection
    print("\nExample 2: Explicit Titan")
    titan = get_embedding_model(model_type="titan")
    print(f"Model: {titan.model_name}")
    
    # Example 3: Environment variable
    print("\nExample 3: Environment variable")
    os.environ["EMBEDDING_MODEL"] = "titan"
    model = get_embedding_model()
    print(f"Model: {model.model_name}")
    
    # Example 4: Generate embedding
    print("\nExample 4: Generate embedding")
    text = "lisinopril 10mg tablet"
    vector = titan.embed(text)
    print(f"Text: {text}")
    print(f"Vector dimension: {len(vector)}")
    print(f"First 5 values: {vector[:5]}")
    
    print("\n✅ Embedding layer examples complete")


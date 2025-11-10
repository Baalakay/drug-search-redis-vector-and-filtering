"""
LLM Configuration Module

Centralized configuration for all LLM/AI model calls.
All model IDs, regions, and inference parameters should be defined here.
"""

import os
from typing import Dict, Any

# Global inference configuration
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")

# Use cross-region inference for better availability
BEDROCK_INFERENCE_PROFILE = os.environ.get(
    "BEDROCK_INFERENCE_PROFILE",
    "us.anthropic.claude-sonnet-4-0"  # Global inference profile
)

# Claude configuration
CLAUDE_CONFIG = {
    "region": BEDROCK_REGION,
    "model_id": BEDROCK_INFERENCE_PROFILE,
    "max_tokens": int(os.environ.get("CLAUDE_MAX_TOKENS", "1000")),
    "temperature": float(os.environ.get("CLAUDE_TEMPERATURE", "0")),
    "top_p": float(os.environ.get("CLAUDE_TOP_P", "1.0")),
}

# Titan Embeddings configuration  
TITAN_CONFIG = {
    "region": BEDROCK_REGION,
    "model_id": os.environ.get(
        "TITAN_MODEL_ID",
        "amazon.titan-embed-text-v2:0"
    ),
    "dimensions": int(os.environ.get("TITAN_DIMENSIONS", "1024")),
}

# SapBERT configuration (for future use)
SAPBERT_CONFIG = {
    "region": os.environ.get("SAGEMAKER_REGION", "us-east-1"),
    "endpoint_name": os.environ.get("SAPBERT_ENDPOINT_NAME", ""),
    "dimensions": int(os.environ.get("SAPBERT_DIMENSIONS", "768")),
}

# Embedding model selection
EMBEDDING_MODEL_TYPE = os.environ.get("EMBEDDING_MODEL", "titan")  # or "sapbert"


def get_llm_config() -> Dict[str, Any]:
    """
    Get Claude LLM configuration
    
    Returns:
        Dict with model_id, region, and inference config
    """
    return CLAUDE_CONFIG.copy()


def get_embedding_config() -> Dict[str, Any]:
    """
    Get embedding model configuration based on EMBEDDING_MODEL env var
    
    Returns:
        Dict with model configuration
    """
    if EMBEDDING_MODEL_TYPE == "sapbert":
        return SAPBERT_CONFIG.copy()
    else:
        return TITAN_CONFIG.copy()


def get_bedrock_client(service: str = "bedrock-runtime"):
    """
    Get configured Bedrock client
    
    Args:
        service: AWS service name (bedrock-runtime, bedrock, etc.)
    
    Returns:
        Configured boto3 client
    """
    import boto3
    return boto3.client(service, region_name=BEDROCK_REGION)


def get_sagemaker_client():
    """
    Get configured SageMaker Runtime client
    
    Returns:
        Configured boto3 SageMaker Runtime client
    """
    import boto3
    return boto3.client(
        "sagemaker-runtime",
        region_name=SAPBERT_CONFIG["region"]
    )

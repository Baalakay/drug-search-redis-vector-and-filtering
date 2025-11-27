"""
LLM Configuration Module

Centralized configuration for all LLM/AI model calls.
All model IDs, regions, and inference parameters should be defined here.

CRITICAL RULES:
1. ALWAYS use Bedrock Converse API (converse() method)
2. NEVER use invoke_model() - it bypasses prompt caching
3. ALWAYS return latency metrics and token usage
4. NEVER hard-code model IDs - import from this module
"""

import os
from typing import Dict, Any, Optional, List
from enum import Enum

# Global inference configuration
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")

# Use cross-region inference for better availability
BEDROCK_INFERENCE_PROFILE = os.environ.get(
    "BEDROCK_INFERENCE_PROFILE",
    "us.anthropic.claude-sonnet-4-0"  # Global inference profile
)


class LLMModel(Enum):
    """
    LLM model identifiers - use these instead of hard-coded strings
    
    EASILY SWAP MODELS: Just change DEFAULT_LLM_MODEL below to any of these
    """
    # Claude Models (using US inference endpoints for best performance)
    CLAUDE_SONNET_4 = "us.anthropic.claude-sonnet-4-20250514-v1:0"  # Claude Sonnet 4 cross-region inference
    CLAUDE_SONNET_3_5 = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    CLAUDE_HAIKU_3_5 = "anthropic.claude-3-haiku-20240307-v1:0"  # Claude 3 Haiku (3.5 not available via Converse API)
    
    # Nova Models (AWS-native, lower cost)
    NOVA_PRO = "us.amazon.nova-pro-v1:0"
    NOVA_LITE = "us.amazon.nova-lite-v1:0"
    NOVA_MICRO = "us.amazon.nova-micro-v1:0"


# ===================================================================
# 🎯 CHANGE THIS TO SWAP LLM MODELS (Single Variable!)
# ===================================================================
DEFAULT_LLM_MODEL = LLMModel.CLAUDE_HAIKU_3_5  # Benchmark: Testing Claude Haiku 3.5
# ===================================================================


class ClaudeModel(Enum):
    """DEPRECATED: Use LLMModel instead for consistency"""
    SONNET_4 = "us.anthropic.claude-sonnet-4-0"
    SONNET_3_5 = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    HAIKU_3_5 = "anthropic.claude-3-5-haiku-20241022-v1:0"


class TitanModel(Enum):
    """Titan embedding model identifiers"""
    EMBED_V2 = "amazon.titan-embed-text-v2:0"
    EMBED_V1 = "amazon.titan-embed-text-v1"


# Claude configuration
CLAUDE_CONFIG = {
    "region": BEDROCK_REGION,
    "model_id": os.environ.get(
        "BEDROCK_INFERENCE_PROFILE",
        DEFAULT_LLM_MODEL.value  # Uses DEFAULT_LLM_MODEL if env var not set
    ),
    "max_tokens": int(os.environ.get("CLAUDE_MAX_TOKENS", "1000")),
    "temperature": float(os.environ.get("CLAUDE_TEMPERATURE", "0")),
    "top_p": float(os.environ.get("CLAUDE_TOP_P", "1.0")),
}

# Titan Embeddings configuration  
TITAN_CONFIG = {
    "region": BEDROCK_REGION,
    "model_id": os.environ.get(
        "TITAN_MODEL_ID",
        TitanModel.EMBED_V2.value
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


def call_claude_converse(
    messages: List[Dict[str, Any]],
    system_prompts: Optional[List[Dict[str, str]]] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Call Claude using Converse API with proper metrics tracking
    
    ALWAYS use this function for LLM calls - NEVER use invoke_model()
    
    This function automatically uses the model configured in DEFAULT_LLM_MODEL
    or BEDROCK_INFERENCE_PROFILE env var. To test different models:
    
    1. Change DEFAULT_LLM_MODEL variable in this file, OR
    2. Set BEDROCK_INFERENCE_PROFILE env var
    
    Example model comparison:
        # Test Claude Sonnet 4
        DEFAULT_LLM_MODEL = LLMModel.CLAUDE_SONNET_4
        
        # Test Nova Pro (lower cost)
        DEFAULT_LLM_MODEL = LLMModel.NOVA_PRO
        
        # Test Nova Lite (fastest, cheapest)
        DEFAULT_LLM_MODEL = LLMModel.NOVA_LITE
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        system_prompts: Optional list of system prompt dicts
        max_tokens: Override default max_tokens
        temperature: Override default temperature
    
    Returns:
        Dict containing:
        - success: bool
        - content: str (response text)
        - usage: dict (inputTokens, outputTokens)
        - model: str (model ID used)
        - metadata: dict with tokens and latency
        - latency_ms: int (milliseconds)
    
    Example:
        ```python
        from packages.core.src.config.llm_config import call_claude_converse
        
        response = call_claude_converse(
            messages=[
                {"role": "user", "content": "What is lisinopril?"}
            ]
        )
        
        if response['success']:
            print(response['content'])
            print(f"Model: {response['model']}")
            print(f"Tokens: {response['metadata']['input_tokens']} in, {response['metadata']['output_tokens']} out")
            print(f"Latency: {response['latency_ms']}ms")
        ```
    """
    import time
    
    client = get_bedrock_client()
    config = get_llm_config()
    
    # Build inference config
    inference_config = {
        "maxTokens": max_tokens or config["max_tokens"],
        "temperature": temperature if temperature is not None else config["temperature"],
        "topP": config["top_p"],
    }
    
    # Prepare request
    request_params = {
        "modelId": config["model_id"],
        "messages": messages,
        "inferenceConfig": inference_config,
    }
    
    if system_prompts:
        request_params["system"] = system_prompts
    
    try:
        start_time = time.time()
        
        # Call Converse API (enables prompt caching)
        response = client.converse(**request_params)
        
        end_time = time.time()
        latency_ms = int((end_time - start_time) * 1000)
        
        # Extract content
        content = response['output']['message']['content'][0]['text']
        
        # Extract usage metrics
        usage = response.get('usage', {})
        
        # Extract latency from ConverseMetrics
        # AWS returns 'latencyMs' which is Bedrock's internal measurement
        # This is more accurate than client-side timing (excludes network overhead)
        metrics = response.get('metrics', {})
        bedrock_latency_ms = metrics.get('latencyMs', latency_ms)  # Fallback to client-side if not available
        
        return {
            'success': True,
            'content': content,
            'usage': usage,
            'model': config["model_id"],
            'metadata': {
                'input_tokens': usage.get('inputTokens', 0),
                'output_tokens': usage.get('outputTokens', 0),
                'latency_ms': bedrock_latency_ms,  # Use Bedrock's metric (inference only)
                'client_latency_ms': latency_ms,  # Keep client-side for debugging
            },
            'latency_ms': bedrock_latency_ms,  # Top-level uses Bedrock's metric
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'model': config["model_id"],
            'metadata': {
                'input_tokens': 0,
                'output_tokens': 0,
                'latency_ms': 0,
            }
        }


def generate_embedding(text: str) -> Dict[str, Any]:
    """
    Generate embedding using configured embedding model
    
    Args:
        text: Input text to embed
    
    Returns:
        Dict containing:
        - success: bool
        - embedding: List[float] (vector)
        - model: str
        - dimensions: int
    """
    config = get_embedding_config()
    
    if EMBEDDING_MODEL_TYPE == "sapbert":
        # SageMaker SapBERT implementation
        # TODO: Implement when SapBERT endpoint is deployed
        raise NotImplementedError("SapBERT embedding not yet implemented")
    else:
        # Titan embeddings
        import json
        
        client = get_bedrock_client()
        
        try:
            body = json.dumps({
                "inputText": text,
                "dimensions": config["dimensions"],
                "normalize": True
            })
            
            response = client.invoke_model(
                modelId=config["model_id"],
                body=body,
                contentType="application/json",
                accept="application/json"
            )
            
            result = json.loads(response['body'].read())
            
            return {
                'success': True,
                'embedding': result['embedding'],
                'model': config["model_id"],
                'dimensions': config["dimensions"]
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'model': config["model_id"],
                'dimensions': config["dimensions"]
            }


def get_model_info(model: LLMModel) -> Dict[str, Any]:
    """
    Get pricing and performance info for a model (for comparison testing)
    
    Args:
        model: LLMModel enum value
    
    Returns:
        Dict with pricing and performance characteristics
    
    Example:
        ```python
        from packages.core.src.config.llm_config import LLMModel, get_model_info
        
        claude_info = get_model_info(LLMModel.CLAUDE_SONNET_4)
        nova_info = get_model_info(LLMModel.NOVA_LITE)
        
        print(f"Claude: ${claude_info['input_price_per_1m']}/1M input tokens")
        print(f"Nova:   ${nova_info['input_price_per_1m']}/1M input tokens")
        ```
    """
    model_data = {
        # Claude Models
        LLMModel.CLAUDE_SONNET_4: {
            "name": "Claude Sonnet 4",
            "provider": "Anthropic",
            "input_price_per_1m": 3.00,
            "output_price_per_1m": 15.00,
            "context_window": 200000,
            "prompt_caching": True,
            "cached_price_per_1m": 0.30,  # 90% discount
            "notes": "Best quality, highest cost, excellent for complex medical reasoning"
        },
        LLMModel.CLAUDE_SONNET_3_5: {
            "name": "Claude Sonnet 3.5",
            "provider": "Anthropic",
            "input_price_per_1m": 3.00,
            "output_price_per_1m": 15.00,
            "context_window": 200000,
            "prompt_caching": True,
            "cached_price_per_1m": 0.30,
            "notes": "Previous generation, similar performance to Sonnet 4"
        },
        LLMModel.CLAUDE_HAIKU_3_5: {
            "name": "Claude Haiku 3.5",
            "provider": "Anthropic",
            "input_price_per_1m": 0.80,
            "output_price_per_1m": 4.00,
            "context_window": 200000,
            "prompt_caching": True,
            "cached_price_per_1m": 0.08,
            "notes": "Fastest Claude model, 75% cheaper, good for simple tasks"
        },
        
        # Nova Models (AWS-native)
        LLMModel.NOVA_PRO: {
            "name": "Amazon Nova Pro",
            "provider": "AWS",
            "input_price_per_1m": 0.80,
            "output_price_per_1m": 3.20,
            "context_window": 300000,
            "prompt_caching": False,  # Check latest docs
            "cached_price_per_1m": None,
            "notes": "AWS-native, 75% cheaper than Claude, good quality"
        },
        LLMModel.NOVA_LITE: {
            "name": "Amazon Nova Lite",
            "provider": "AWS",
            "input_price_per_1m": 0.06,
            "output_price_per_1m": 0.24,
            "context_window": 300000,
            "prompt_caching": False,  # Check latest docs
            "cached_price_per_1m": None,
            "notes": "Very fast, 95% cheaper than Claude, good for simple queries"
        },
        LLMModel.NOVA_MICRO: {
            "name": "Amazon Nova Micro",
            "provider": "AWS",
            "input_price_per_1m": 0.035,
            "output_price_per_1m": 0.14,
            "context_window": 128000,
            "prompt_caching": False,  # Check latest docs
            "cached_price_per_1m": None,
            "notes": "Fastest, cheapest, best for very simple classification tasks"
        },
    }
    
    return model_data.get(model, {
        "name": "Unknown",
        "provider": "Unknown",
        "input_price_per_1m": 0.0,
        "output_price_per_1m": 0.0,
        "context_window": 0,
        "prompt_caching": False,
        "cached_price_per_1m": None,
        "notes": "Pricing not available"
    })


def estimate_cost(input_tokens: int, output_tokens: int, model: Optional[LLMModel] = None, cache_hit_rate: float = 0.0) -> Dict[str, float]:
    """
    Estimate cost for a query based on token usage
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: LLMModel to calculate for (defaults to DEFAULT_LLM_MODEL)
        cache_hit_rate: Fraction of input tokens that hit cache (0.0-1.0)
    
    Returns:
        Dict with cost breakdown
    
    Example:
        ```python
        cost = estimate_cost(
            input_tokens=245,
            output_tokens=89,
            model=LLMModel.CLAUDE_SONNET_4,
            cache_hit_rate=0.5  # 50% cache hits
        )
        
        print(f"Total cost: ${cost['total']:.6f}")
        print(f"Input cost: ${cost['input']:.6f}")
        print(f"Output cost: ${cost['output']:.6f}")
        print(f"Cache savings: ${cost['cache_savings']:.6f}")
        ```
    """
    if model is None:
        model = DEFAULT_LLM_MODEL
    
    info = get_model_info(model)
    
    # Calculate input cost with caching
    if info['prompt_caching'] and cache_hit_rate > 0:
        cached_tokens = int(input_tokens * cache_hit_rate)
        uncached_tokens = input_tokens - cached_tokens
        input_cost = (
            (uncached_tokens * info['input_price_per_1m'] / 1_000_000) +
            (cached_tokens * info['cached_price_per_1m'] / 1_000_000)
        )
        cache_savings = cached_tokens * (info['input_price_per_1m'] - info['cached_price_per_1m']) / 1_000_000
    else:
        input_cost = input_tokens * info['input_price_per_1m'] / 1_000_000
        cache_savings = 0.0
    
    # Calculate output cost
    output_cost = output_tokens * info['output_price_per_1m'] / 1_000_000
    
    return {
        'input': input_cost,
        'output': output_cost,
        'cache_savings': cache_savings,
        'total': input_cost + output_cost,
        'model': info['name']
    }

# LLM Usage Standards & Best Practices

**Date:** 2025-11-15  
**Status:** ✅ ENFORCED - All LLM calls must follow these standards  
**Priority:** 🔴 CRITICAL

---

## 🚨 CRITICAL RULES - NEVER VIOLATE

### **Rule 1: ALWAYS Use Converse API**
```python
# ✅ CORRECT - Use Converse API
from packages.core.src.config.llm_config import call_claude_converse

response = call_claude_converse(
    messages=[{"role": "user", "content": "What is lisinopril?"}]
)

# ❌ WRONG - NEVER use invoke_model()
client.invoke_model(modelId="...", body="...")  # NO PROMPT CACHING!
```

**Why?**
- `converse()` enables **prompt caching** (90% cost savings for repeated prompts)
- `invoke_model()` bypasses caching entirely
- `converse()` provides standardized metrics

### **Rule 2: NEVER Hard-Code Model IDs**
```python
# ✅ CORRECT - Import from centralized config
from packages.core.src.config.llm_config import ClaudeModel, TitanModel, get_llm_config

config = get_llm_config()
model_id = config["model_id"]  # Uses BEDROCK_INFERENCE_PROFILE env var

# ❌ WRONG - Hard-coded model IDs
model_id = "anthropic.claude-sonnet-4-0"  # Breaks when we change models!
model_id = "us.anthropic.claude-sonnet-4-0"  # No flexibility!
```

**Why?**
- Centralized config allows environment-based switching
- Easy A/B testing (dev vs prod models)
- Single place to update when models change

### **Rule 3: ALWAYS Return Metrics**
```python
# ✅ CORRECT - Return complete metrics
return {
    'success': True,
    'content': content,
    'usage': usage,
    'model': self.model.value,
    'metadata': {
        'input_tokens': usage.get('inputTokens', 0),
        'output_tokens': usage.get('outputTokens', 0),
        'latency_ms': latency_ms,
        'bedrock_latency_ms': bedrock_latency_ms,
    },
    'latency_ms': latency_ms  # Top-level for convenience
}

# ❌ WRONG - Missing metrics
return response['output']['message']['content'][0]['text']  # Just the text!
```

**Why?**
- Cost monitoring (track token usage)
- Performance monitoring (track latency)
- Debugging (identify slow/expensive calls)
- Cache hit rate calculation

---

## 📚 Complete Usage Guide

### **1. Basic Claude Call**

```python
from packages.core.src.config.llm_config import call_claude_converse

response = call_claude_converse(
    messages=[
        {"role": "user", "content": "Expand this drug search: blood pressure medication"}
    ]
)

if response['success']:
    expanded_query = response['content']
    print(f"Tokens: {response['metadata']['input_tokens']} in, {response['metadata']['output_tokens']} out")
    print(f"Latency: {response['latency_ms']}ms")
    print(f"Model: {response['model']}")
else:
    print(f"Error: {response['error']}")
```

### **2. Claude with System Prompt**

```python
from packages.core.src.config.llm_config import call_claude_converse

response = call_claude_converse(
    messages=[
        {"role": "user", "content": "Expand: blood pressure medication"}
    ],
    system_prompts=[
        {
            "text": "You are a medical terminology expert. Expand drug search queries."
        }
    ]
)
```

### **3. Claude with Custom Parameters**

```python
from packages.core.src.config.llm_config import call_claude_converse

response = call_claude_converse(
    messages=[
        {"role": "user", "content": "List ACE inhibitors"}
    ],
    max_tokens=2000,  # Override default
    temperature=0.3   # Override default (0)
)
```

### **4. Multi-Turn Conversation**

```python
from packages.core.src.config.llm_config import call_claude_converse

messages = [
    {"role": "user", "content": "What is lisinopril?"},
    {"role": "assistant", "content": "Lisinopril is an ACE inhibitor..."},
    {"role": "user", "content": "What are alternatives?"}
]

response = call_claude_converse(messages=messages)
```

### **5. Generate Embeddings (Titan)**

```python
from packages.core.src.config.llm_config import generate_embedding

result = generate_embedding("lisinopril 10mg tablet")

if result['success']:
    embedding = result['embedding']  # List[float], 1024 dimensions
    print(f"Model: {result['model']}")
    print(f"Dimensions: {result['dimensions']}")
    print(f"Vector: {embedding[:5]}...")  # First 5 values
else:
    print(f"Error: {result['error']}")
```

---

## 📊 Metrics Reference

### **ConverseMetrics (from Bedrock)**
```python
response['metadata'] = {
    'input_tokens': 245,        # Prompt tokens
    'output_tokens': 89,        # Response tokens
    'latency_ms': 1234,         # Total call time (client-measured)
    'bedrock_latency_ms': 1189  # Bedrock-measured latency
}
```

**AWS Documentation:**
- [ConverseMetrics API Reference](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseMetrics.html)
- [Usage Tracking](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_TokenUsage.html)

### **Cost Calculation**

**Claude Sonnet 4 Pricing (with prompt caching):**
- Input tokens (non-cached): $3.00 per 1M tokens
- Input tokens (cached): $0.30 per 1M tokens (90% savings!)
- Output tokens: $15.00 per 1M tokens

**Example:**
```python
input_cost = (245 * 3.00) / 1_000_000  # $0.000735
output_cost = (89 * 15.00) / 1_000_000  # $0.001335
total_cost = input_cost + output_cost   # $0.00207 per call

# With 50% cache hit rate:
cached_input_cost = (122 * 0.30 + 123 * 3.00) / 1_000_000  # $0.000406
total_with_cache = cached_input_cost + output_cost         # $0.001741 (16% savings)
```

### **Performance Targets**

| Call Type | Target Latency | Token Budget | Notes |
|-----------|----------------|--------------|-------|
| Query expansion | <200ms | <500 tokens | High frequency |
| Drug classification | <300ms | <1000 tokens | Medium frequency |
| Full analysis | <1000ms | <4000 tokens | Low frequency |

---

## 🔧 Environment Configuration

### **Development (.env)**
```bash
# Bedrock Configuration
BEDROCK_REGION=us-east-1
BEDROCK_INFERENCE_PROFILE=us.anthropic.claude-sonnet-4-0

# Claude Settings
CLAUDE_MAX_TOKENS=1000
CLAUDE_TEMPERATURE=0
CLAUDE_TOP_P=1.0

# Titan Embeddings
TITAN_MODEL_ID=amazon.titan-embed-text-v2:0
TITAN_DIMENSIONS=1024

# Model Selection
EMBEDDING_MODEL=titan  # or "sapbert" when ready
```

### **Production Environment**
```bash
# Use cross-region inference profile for better availability
BEDROCK_INFERENCE_PROFILE=us.anthropic.claude-sonnet-4-0

# Conservative token limits for cost control
CLAUDE_MAX_TOKENS=2000

# Titan with full dimensions
TITAN_DIMENSIONS=1024
```

---

## 🎯 Implementation Checklist

### **For Every Lambda Function Using LLMs:**

- [ ] Import from `packages.core.src.config.llm_config`
- [ ] Use `call_claude_converse()` function (not `invoke_model()`)
- [ ] Never hard-code model IDs
- [ ] Return complete metrics in response
- [ ] Log token usage for cost tracking
- [ ] Log latency for performance monitoring
- [ ] Handle errors gracefully
- [ ] Add unit tests for LLM calls

### **Example Lambda Handler:**

```python
from packages.core.src.config.llm_config import call_claude_converse
import json

def lambda_handler(event, context):
    """Search endpoint with Claude preprocessing"""
    
    query = json.loads(event['body'])['query']
    
    # Call Claude using centralized config
    response = call_claude_converse(
        messages=[
            {"role": "user", "content": f"Expand drug search: {query}"}
        ]
    )
    
    if not response['success']:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': response['error']})
        }
    
    expanded_query = response['content']
    
    # TODO: Execute Redis search with expanded_query
    
    # Return results WITH metrics
    return {
        'statusCode': 200,
        'body': json.dumps({
            'results': [],  # Redis results
            'query': {
                'original': query,
                'expanded': expanded_query
            },
            'metrics': {
                'claude_tokens': {
                    'input': response['metadata']['input_tokens'],
                    'output': response['metadata']['output_tokens'],
                    'cost_estimate': calculate_cost(response['metadata'])
                },
                'claude_latency_ms': response['latency_ms'],
                'total_latency_ms': 0  # TODO: Calculate total
            }
        })
    }


def calculate_cost(metadata):
    """Calculate estimated cost from token usage"""
    input_cost = (metadata['input_tokens'] * 3.00) / 1_000_000
    output_cost = (metadata['output_tokens'] * 15.00) / 1_000_000
    return round(input_cost + output_cost, 6)
```

---

## 🚫 Common Mistakes to Avoid

### **Mistake 1: Using invoke_model()**
```python
# ❌ WRONG
response = bedrock_client.invoke_model(
    modelId="anthropic.claude-sonnet-4-0",
    body=json.dumps({"prompt": "..."}))
```
**Problem:** No prompt caching, no standardized metrics, hard-coded model ID

### **Mistake 2: Hard-Coding Model IDs**
```python
# ❌ WRONG
MODEL_ID = "us.anthropic.claude-sonnet-4-0"
```
**Problem:** Can't switch models per environment, inflexible

### **Mistake 3: Missing Metrics**
```python
# ❌ WRONG
def call_claude(text):
    response = client.converse(...)
    return response['output']['message']['content'][0]['text']  # Just text!
```
**Problem:** No visibility into costs or performance

### **Mistake 4: Not Handling Errors**
```python
# ❌ WRONG
response = call_claude_converse(messages=[...])
content = response['content']  # Crashes if error!
```
**Problem:** Uncaught exceptions crash Lambda

---

## 📈 Monitoring & Alerting

### **CloudWatch Metrics to Track:**

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

# Log token usage
cloudwatch.put_metric_data(
    Namespace='DAW/LLM',
    MetricData=[
        {
            'MetricName': 'ClaudeInputTokens',
            'Value': response['metadata']['input_tokens'],
            'Unit': 'Count'
        },
        {
            'MetricName': 'ClaudeOutputTokens',
            'Value': response['metadata']['output_tokens'],
            'Unit': 'Count'
        },
        {
            'MetricName': 'ClaudeLatency',
            'Value': response['latency_ms'],
            'Unit': 'Milliseconds'
        }
    ]
)
```

### **Cost Alarms:**

```python
# Alert if daily costs exceed $50
{
    "AlarmName": "DAW-Claude-High-Cost",
    "MetricName": "ClaudeInputTokens",
    "Threshold": 16666666,  # ~$50 in input tokens
    "ComparisonOperator": "GreaterThanThreshold",
    "Period": 86400,  # 1 day
    "EvaluationPeriods": 1,
    "Statistic": "Sum"
}
```

---

## ✅ Compliance Verification

Before deploying any Lambda function that uses LLMs:

1. ✅ Grep for `invoke_model` - should ONLY appear in `generate_embedding()`
2. ✅ Grep for hard-coded model IDs - should be ZERO
3. ✅ Check all LLM calls return metrics
4. ✅ Verify error handling for all LLM calls
5. ✅ Test with invalid inputs
6. ✅ Verify CloudWatch logging

**Verification Command:**
```bash
# Check for invoke_model usage (should only be in llm_config.py for embeddings)
grep -r "invoke_model" functions/ --exclude-dir=__pycache__

# Check for hard-coded model IDs
grep -r "anthropic\\.claude" functions/ --exclude-dir=__pycache__
grep -r "amazon\\.titan" functions/ --exclude-dir=__pycache__

# Check for converse() usage (good!)
grep -r "call_claude_converse" functions/ --exclude-dir=__pycache__
```

---

**Status:** 🔴 CRITICAL - These standards are mandatory for all LLM usage  
**Owner:** All developers  
**Reviewed:** 2025-11-15  
**Next Review:** Before Phase 6 deployment


# EmbeddingsCache Evaluation & Implementation Guide

**Date:** 2025-11-21  
**Status:** Evaluated - Recommended for Phase 7  
**Priority:** Medium-High (performance optimization)

---

## Executive Summary

**EmbeddingsCache** is a lightweight caching solution that stores Titan embedding vectors in Redis to avoid repeated API calls. Unlike SemanticCache (which requires heavy dependencies), EmbeddingsCache offers significant performance gains with minimal complexity.

**Key Metrics:**
- **50-100x latency reduction**: Redis lookup (<1ms) vs Titan API (50-100ms)
- **High hit rate expected**: Common drugs (insulin, metformin, atorvastatin) used repeatedly
- **Cost savings**: Eliminate Titan charges for cached drugs
- **Zero risk**: Titan embeddings are deterministic (same input = same output)

---

## Problem Statement

### Current Multi-Drug Search Flow

When a user searches for "high cholesterol", Claude extracts 5 drug names:
```json
{
  "search_text": "atorvastatin rosuvastatin simvastatin pravastatin lovastatin"
}
```

Our multi-drug search architecture performs **individual vector searches** for each drug:

```python
# Current implementation (search_handler.py)
for drug_name in ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "lovastatin"]:
    # Generate embedding via Bedrock Titan API
    embedding = bedrock_runtime.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": drug_name})
    )  # 50-100ms PER CALL
    
    # Perform vector search with this embedding
    results = redis_vector_only_search(embedding, ...)
```

**Total embedding latency**: 5 drugs × 50-100ms = **250-500ms**

For common queries, this is **pure waste** since Titan always returns the same embedding for the same drug name.

---

## Solution: EmbeddingsCache

### Architecture

```
User Query: "high cholesterol"
    ↓
Claude extracts: ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "lovastatin"]
    ↓
For EACH drug:
    ├─ Check Redis: f"embedding:titan-v2:{drug_name}"
    ├─ Cache HIT? → Use cached embedding (<1ms) ✅
    └─ Cache MISS? → Call Titan API (50-100ms) → Store in cache
    ↓
Vector search with embedding
```

### Expected Performance

**Before (No Cache)**:
- 5 Titan API calls: 250-500ms
- Cost: 5 × $0.00002 per 1K tokens ≈ $0.0001

**After (80% Cache Hit Rate)**:
- 1 Titan API call (miss): 50-100ms
- 4 Redis lookups (hits): <1ms each
- **Total**: ~50-100ms (5x improvement)
- **Cost**: 1 × $0.00002 = $0.00002 (5x savings)

**After (100% Cache Hit Rate)**:
- 0 Titan API calls
- 5 Redis lookups: <1ms each
- **Total**: <5ms (50-100x improvement)
- **Cost**: $0 for embeddings

---

## Implementation Options

### Option A: RedisVL EmbeddingsCache (Preferred)

**Advantages**:
- Clean, well-tested API
- Automatic TTL management
- Batch operations (`mget`, `mset`)
- Proper error handling

**Dependency Concern**:
- Requires `redisvl>=0.11.0` (confirmed lightweight)
- **NEEDS TESTING**: Does it work WITHOUT `sentence-transformers`?
  - EmbeddingsCache doesn't do semantic similarity (just key/value)
  - May not need heavy embedding models
  - Must verify before committing

**Code Example**:
```python
from redisvl.cache import EmbeddingsCache

# Initialize once per Lambda invocation
embeddings_cache = EmbeddingsCache(
    name="drug_embeddings",
    ttl=2592000,  # 30 days
    redis_client=redis_client
)

# Usage in multi-drug search
drug_embeddings = []
for drug_name in claude_drug_list:
    # Check cache
    cached = embeddings_cache.get(
        text=drug_name,
        model_name="amazon.titan-embed-text-v2:0"
    )
    
    if cached:
        embedding = cached['embedding']
        logger.info(f"Embedding cache HIT: {drug_name}")
    else:
        # Call Titan API
        response = bedrock_runtime.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps({"inputText": drug_name})
        )
        embedding = json.loads(response['body'].read())['embedding']
        
        # Store in cache
        embeddings_cache.set(
            text=drug_name,
            model_name="amazon.titan-embed-text-v2:0",
            embedding=embedding,
            metadata={"timestamp": time.time()}
        )
        logger.info(f"Embedding cache MISS: {drug_name} (cached for future)")
    
    drug_embeddings.append((drug_name, embedding))
```

**Reference**: https://redis.io/docs/latest/develop/ai/redisvl/api/cache/#embeddings-cache

---

### Option B: Manual Redis Hash Storage (Fallback)

**Advantages**:
- Zero dependencies (uses existing `redis` client)
- Full control over key format
- Simple, predictable behavior

**Disadvantages**:
- No batch operations
- Manual TTL management
- No built-in error handling

**Code Example**:
```python
import json
from typing import Optional, List

def get_cached_embedding(
    redis_client,
    drug_name: str,
    model_name: str = "amazon.titan-embed-text-v2:0"
) -> Optional[List[float]]:
    """Retrieve cached embedding from Redis."""
    key = f"embedding:{model_name}:{drug_name.lower()}"
    cached = redis_client.get(key)
    
    if cached:
        # Refresh TTL on access
        redis_client.expire(key, 2592000)  # 30 days
        return json.loads(cached)
    
    return None

def cache_embedding(
    redis_client,
    drug_name: str,
    embedding: List[float],
    model_name: str = "amazon.titan-embed-text-v2:0",
    ttl: int = 2592000  # 30 days
):
    """Store embedding in Redis with TTL."""
    key = f"embedding:{model_name}:{drug_name.lower()}"
    redis_client.setex(key, ttl, json.dumps(embedding))

# Usage in multi-drug search
drug_embeddings = []
for drug_name in claude_drug_list:
    embedding = get_cached_embedding(redis_client, drug_name)
    
    if embedding:
        logger.info(f"Embedding cache HIT: {drug_name}")
    else:
        # Call Titan API
        response = bedrock_runtime.invoke_model(
            modelId="amazon.titan-embed-text-v2:0",
            body=json.dumps({"inputText": drug_name})
        )
        embedding = json.loads(response['body'].read())['embedding']
        
        # Cache for future requests
        cache_embedding(redis_client, drug_name, embedding)
        logger.info(f"Embedding cache MISS: {drug_name}")
    
    drug_embeddings.append((drug_name, embedding))
```

---

## Expected Cache Hit Rates

### By Drug Popularity

Based on prescription volume data:

| Drug Type | Examples | Expected Hit Rate |
|-----------|----------|-------------------|
| **Top 100 drugs** | insulin, metformin, atorvastatin, lisinopril | **95-100%** |
| **Top 1,000 drugs** | Most chronic disease medications | **80-90%** |
| **Long-tail drugs** | Rare/specialty medications | **10-30%** |

### By Query Type

| Query Type | Cache Behavior | Expected Hit Rate |
|------------|----------------|-------------------|
| **Condition searches** | "high cholesterol" → 5 statins (same every time) | **100%** after first query |
| **Direct drug search** | "insulin" → 1 drug | **90-95%** |
| **Misspellings** | "cholestrol" → Claude corrects to "cholesterol" | **80-90%** |
| **Rare drug combinations** | "women hrt powder progesterone" | **30-50%** |

**Overall Expected Hit Rate**: **70-85%** after 1 week of production use

---

## Storage & Memory Impact

### Per Embedding
- Titan embedding: 1024 dimensions × 4 bytes (float32) = **4 KB**
- Redis key overhead: ~100 bytes
- **Total per drug**: ~4.1 KB

### Projected Storage
- **Top 1,000 drugs**: 1,000 × 4.1 KB = **4.1 MB**
- **Top 10,000 drugs**: 10,000 × 4.1 KB = **41 MB**
- **All 493K drugs**: 493K × 4.1 KB = **2 GB**

**Current Redis Usage**: 3.74 GB (drug search data)  
**With EmbeddingsCache (10K drugs)**: 3.78 GB (**+1% increase**)

**Verdict**: Negligible memory impact

---

## Testing Plan (Before Implementation)

### Step 1: Verify RedisVL Dependency Size
```bash
# Create a test Lambda layer
mkdir -p /tmp/test-layer/python
pip install redisvl -t /tmp/test-layer/python/
du -sh /tmp/test-layer/python/

# Check if sentence-transformers is pulled in
ls -lh /tmp/test-layer/python/ | grep -i sentence
```

**Success Criteria**: Total size < 50 MB (Lambda has 250 MB limit)

---

### Step 2: Benchmark Cache Performance
```python
import time

# Test 1: Titan API latency (baseline)
start = time.time()
for i in range(10):
    embedding = call_titan("atorvastatin")
titan_latency = (time.time() - start) / 10
print(f"Titan API: {titan_latency*1000:.2f}ms per call")

# Test 2: Redis cache latency
start = time.time()
for i in range(10):
    cached_embedding = redis_client.get("embedding:titan-v2:atorvastatin")
redis_latency = (time.time() - start) / 10
print(f"Redis cache: {redis_latency*1000:.2f}ms per call")

print(f"Speedup: {titan_latency/redis_latency:.1f}x")
```

**Expected Results**:
- Titan API: 50-100ms
- Redis cache: 0.5-1ms
- Speedup: 50-100x

---

### Step 3: A/B Test in Production
- Deploy with cache enabled to 50% of requests
- Compare metrics:
  - Embedding latency (p50, p95)
  - Total search latency
  - Titan API costs
  - Cache hit rate

**Success Criteria**:
- ≥50% cache hit rate within 24 hours
- ≥70% cache hit rate within 1 week
- 20-30% reduction in total search latency

---

## Rollback Plan

If EmbeddingsCache causes issues:

1. **Feature flag**: Toggle cache on/off via environment variable
```python
USE_EMBEDDINGS_CACHE = os.getenv("USE_EMBEDDINGS_CACHE", "false").lower() == "true"

if USE_EMBEDDINGS_CACHE:
    embedding = get_cached_embedding(...) or call_titan(...)
else:
    embedding = call_titan(...)
```

2. **No data loss**: Cache is purely additive (doesn't change search logic)

3. **Instant rollback**: Set `USE_EMBEDDINGS_CACHE=false` and redeploy (1 minute)

---

## Cost-Benefit Analysis

### Implementation Cost
- **Dev time**: 2-4 hours (if using RedisVL)
- **Testing time**: 2 hours
- **Memory**: +41 MB (top 10K drugs)
- **Risk**: Very low (cache is optional)

### Expected Benefits (Monthly)
Assuming 1M searches/month with 70% cache hit rate:

**Latency Savings**:
- Average drugs per query: 2
- Without cache: 2M × 75ms = **150,000 seconds** (42 hours)
- With cache (70% hit): 600K × 75ms + 1.4M × 1ms = **46,400 seconds** (13 hours)
- **Savings**: 103,600 seconds (29 hours) of cumulative user wait time

**Cost Savings**:
- Titan cost per 1K tokens: $0.00002
- Average drug name: ~2 tokens
- Without cache: 2M embeddings × $0.00002 × 0.002 = **$0.08**
- With cache (70% hit): 600K embeddings × $0.00002 × 0.002 = **$0.024**
- **Savings**: $0.056/month (minimal, but free money)

**ROI**: Very high (2-4 hours dev time for 29 hours/month user latency savings)

---

## Recommendation

### Priority: Medium-High

**When to Implement**: Phase 7 (after baseline performance validation)

**Why Not Now**:
- Current multi-drug search is working well
- Need to establish baseline metrics first
- No urgent performance issues

**Why Implement in Phase 7**:
- Easy win for performance optimization
- Validates Redis caching strategy for future features
- Demonstrates proactive cost management

**Preferred Approach**:
1. Test RedisVL dependency size
2. If ≤50 MB: Use RedisVL EmbeddingsCache (Option A)
3. If >50 MB: Use manual Redis storage (Option B)

---

## References

- **RedisVL EmbeddingsCache API**: https://redis.io/docs/latest/develop/ai/redisvl/api/cache/#embeddings-cache
- **Semantic Cache Evaluation**: `/workspaces/DAW/docs/SEMANTIC_CACHE_IMPLEMENTATION.md`
- **Multi-Drug Search Architecture**: `/workspaces/DAW/docs/2025-11-21_MULTI_DRUG_SEARCH_OPTIMIZATION.md`
- **Search Handler**: `/workspaces/DAW/functions/src/search_handler.py`

---

**Status**: Ready for Phase 7 implementation ✅


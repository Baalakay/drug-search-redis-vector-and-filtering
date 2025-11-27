# API Metrics Explanation

## Overview
The `/search` API returns detailed performance metrics for each component of the drug search pipeline.

## Metrics Breakdown

### 1. **LLM Latency** (`metrics.llm.latency_ms`)
- **Source**: Bedrock's internal `ConverseMetrics.latencyMs`
- **What it measures**: Pure LLM inference time (model processing only)
- **Does NOT include**: Network latency from Lambda to Bedrock
- **Typical values**: 
  - Claude Sonnet 4: ~1200-1400ms (warm)
  - Amazon Nova Micro: ~1800-2200ms (warm)
  - Claude Haiku 3.5: ~1300-1700ms (warm)
- **Reference**: [AWS Bedrock ConverseMetrics](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseMetrics.html)

### 2. **Embeddings Latency** (`metrics.embedding.latency_ms`)
- **Source**: Client-side timing (Lambda measurement)
- **What it measures**: Network round-trip + Titan embedding generation
- **Includes**: Lambda → Bedrock Titan → Lambda
- **Typical values**: 140-180ms (warm)
- **Note**: Titan embeddings API does not return internal latency metrics

### 3. **Redis Latency** (`metrics.redis.latency_ms`)
- **Source**: Client-side timing (Lambda measurement)
- **What it measures**: Redis query execution time
- **Accuracy**: Very accurate (VPC-local connection, ~1ms network overhead)
- **Typical values**: 
  - Cold start: 2000-3000ms (connection overhead)
  - Warm: 150-250ms (actual query time)

### 4. **Total Latency** (`metrics.total_latency_ms`)
- **Source**: Client-side timing (Lambda measurement)
- **What it measures**: End-to-end API response time
- **Includes**: LLM + Embeddings + Redis + result grouping + JSON serialization
- **Typical values**:
  - Cold start: 7000-9000ms
  - Warm: 1400-1800ms

## Cold Start vs Warm Performance

### Cold Start (First Request)
```
LLM:        1356ms  (Bedrock inference)
Embeddings:  160ms  (Network + Titan)
Redis:      3135ms  (Connection overhead + query)
─────────────────────────────────────────────
Total:      7333ms  (End-to-end)
```

### Warm (Subsequent Requests)
```
LLM:        1287ms  (Bedrock inference, may use prompt cache)
Embeddings:  159ms  (Network + Titan)
Redis:       197ms  (Query only, connection pooled)
─────────────────────────────────────────────
Total:      1540ms  (End-to-end)
```

## What Changed (2025-11-25)

### Before
- **LLM latency**: Client-side timing (network + inference + JSON parsing)
- **Reported**: ~2400-4200ms (inflated)

### After
- **LLM latency**: Bedrock's internal `latencyMs` metric (inference only)
- **Reported**: ~1200-1400ms (accurate)

### Impact
- ✅ More accurate LLM performance comparison
- ✅ Matches what's visible in UI screenshots
- ✅ Allows fair model-to-model benchmarking
- ✅ Better understanding of where time is spent

## Code References

### Backend (Lambda)
- **LLM Config**: `packages/core/src/config/llm_config.py:247`
  ```python
  bedrock_latency_ms = metrics.get('latencyMs', latency_ms)
  ```

- **Search Handler**: `functions/src/search_handler.py:71`
  ```python
  claude_time = claude_result.get('latency_ms', 0)  # Uses Bedrock metric
  ```

### Frontend (UI)
- **Display**: `frontend/app/components/drug-search.tsx:289`
  ```typescript
  value: `${metrics.llm.latency_ms.toFixed(0)} ms`
  ```

## Benchmark Script

The benchmark script (`scripts/benchmark_llm_models.py`) now uses the corrected Bedrock metrics:
- Runs each model 3 times
- First run = cold start (discarded from averages)
- Runs 2-3 = warm (used for fair comparison)
- Compares: latency, cost, accuracy

## Related Documentation
- [AWS Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
- [AWS Bedrock ConverseMetrics](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseMetrics.html)
- [Titan Embeddings](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)


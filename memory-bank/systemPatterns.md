# System Patterns: DAW Drug Search Architecture

## 🚨 CRITICAL: LLM Usage Standards (ALWAYS ENFORCE)

### **Rule 1: ALWAYS Use Bedrock Converse API**
```python
# ✅ CORRECT - Use centralized Converse function
from packages.core.src.config.llm_config import call_claude_converse

response = call_claude_converse(
    messages=[{"role": "user", "content": "What is lisinopril?"}]
)

# ❌ WRONG - NEVER use invoke_model() for Claude
client.invoke_model(modelId="...", body="...")  # NO PROMPT CACHING!
```

**Why:** `converse()` enables prompt caching (90% cost savings), `invoke_model()` bypasses it entirely.

### **Rule 2: NEVER Hard-Code Model IDs**
```python
# ✅ CORRECT - Import from centralized config
from packages.core.src.config.llm_config import get_llm_config

config = get_llm_config()
model_id = config["model_id"]  # Uses env var BEDROCK_INFERENCE_PROFILE

# ❌ WRONG - Hard-coded strings
model_id = "anthropic.claude-sonnet-4-0"
```

### **Rule 3: ALWAYS Return Complete Metrics**
```python
# ✅ CORRECT - Full response with metrics
return {
    'success': True,
    'content': content,
    'usage': usage,
    'model': config["model_id"],
    'metadata': {
        'input_tokens': usage.get('inputTokens', 0),
        'output_tokens': usage.get('outputTokens', 0),
        'latency_ms': latency_ms,
        'bedrock_latency_ms': bedrock_latency_ms,
    },
    'latency_ms': latency_ms
}
```

**Complete Documentation:** `docs/LLM_USAGE_STANDARDS.md`

---

## Architecture Overview

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                     API Gateway (REST)                          │
│                  https://api.daw.aws/v1/drugs                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│             Lambda: Drug Search Handler (Python 3.12)           │
│                                                                  │
│  Flow:                                                           │
│  1. Parse query with Claude Sonnet 4                            │
│  2. Generate embedding (Titan or SapBERT)                       │
│  3. Hybrid search in Redis (vector + filters)                   │
│  4. Enrich from Aurora (batch lookup)                           │
│  5. Format and return results                                   │
└───┬─────────┬─────────┬────────────┬────────────────────────────┘
    │         │         │            │
    ↓         ↓         ↓            ↓
┌────────┐ ┌──────┐ ┌────────┐  ┌─────────┐
│Bedrock │ │Bedrock│ │ Redis  │  │ Aurora  │
│Claude  │ │Titan  │ │Stack   │  │Postgres │
│Sonnet 4│ │Embed  │ │  8.2.2 │  │         │
└────────┘ └───────┘ └────────┘  └─────────┘
Query       Embedding   Vector     Complete
Parser      Generation  Search     Drug Data
```

---

## Core Patterns

### Pattern 1: Embedding Abstraction Layer

**Problem:** Need to switch between Titan and SapBERT without code changes

**Solution:** Abstract base class with factory pattern

```python
# Abstract interface
class EmbeddingModel(ABC):
    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        pass
    
    @abstractmethod
    def dimension(self) -> int:
        pass

# Implementations
class TitanEmbedding(EmbeddingModel):
    # Bedrock implementation
    
class SapBERTEmbedding(EmbeddingModel):
    # SageMaker implementation

# Factory
def get_embedding_model() -> EmbeddingModel:
    model_type = os.environ.get("EMBEDDING_MODEL", "titan")
    if model_type == "titan":
        return TitanEmbedding()
    elif model_type == "sapbert":
        return SapBERTEmbedding(os.environ["SAPBERT_ENDPOINT"])
```

**Benefits:**
- ✅ Zero code changes to switch models
- ✅ Easy A/B testing
- ✅ Testable (mock embedding model)
- ✅ Future-proof (add new models easily)

**Usage:**
```python
# In Lambda
model = get_embedding_model()  # Returns Titan by default
vector = model.embed("atorvastatin")  # Works with any implementation
```

---

### Pattern 2: Hybrid Search (Vector + Filters)

**Problem:** Need both semantic similarity AND exact filtering simultaneously

**Solution:** Redis Stack 8.2.2 hybrid query with LeanVec4x8 quantization (on EC2)

```python
# Single Redis query does both:
query = "(filter_clauses)=>[KNN 20 @embedding $vector AS score]"

# Example:
query = """
    (@drug_class:{statin} @drug_type:{prescription})
    =>[KNN 20 @embedding $vector AS score]
"""

# Returns: Top 20 statins (filtered) by vector similarity
```

**Key Innovation:** Aaron's insight - filter DURING search, not after

**Performance Impact:**
```
Before (filter after):
- Redis returns 100 results (10ms)
- Aurora enriches 100 records (25ms)
- Application filters to 20 (5ms)
- Total: 40ms, wasted 80 enrichments

After (filter during):
- Redis returns 20 filtered results (12ms)
- Aurora enriches 20 records (15ms)
- Total: 27ms, no waste
```

---

### Pattern 3: Query Enhancement Pipeline

**Problem:** User queries are messy (misspellings, abbreviations, conversational)

**Solution:** Claude Sonnet 4 as query preprocessor

```python
# Input
user_query = "give me an ACEI for high blood presure"

# Claude transforms to:
{
    "search_text": "lisinopril enalapril ramipril ACE inhibitor angiotensin-converting enzyme inhibitor",
    "filters": {
        "drug_class": "ace_inhibitor",
        "indication": "hypertension"
    },
    "corrections": ["presure → pressure", "ACEI → ACE inhibitor"]
}

# This goes to embedding + search
```

**Why Claude (not regex/dictionary):**
- Handles context ("blood presure" → hypertension, not just spell check)
- Expands abbreviations intelligently (ACEI → multiple synonyms)
- Extracts structured filters from natural language
- Maintains prompt caching for cost efficiency

---

### Pattern 4: Data Dua

lity (Redis + Aurora)

**Problem:** Need fast search AND complete drug data

**Solution:** Hybrid storage with strategic duplication

```
┌─────────────────────────────────────────────────┐
│               Redis (Fast Path)                 │
│  Purpose: Fast vector + filter search           │
│  Storage: ~1.2 KB per drug                      │
│                                                  │
│  Contains:                                       │
│  - Embedding (quantized, 1 KB)                  │
│  - Filter fields (drug_class, indication, etc.) │
│  - Preview fields (name, brand_name)            │
│                                                  │
│  Total: 60 MB for 50k drugs                     │
└─────────────────────────────────────────────────┘
                         ↓
                   Returns drug IDs
                         ↓
┌─────────────────────────────────────────────────┐
│           Aurora PostgreSQL (Source of Truth)   │
│  Purpose: Complete drug information             │
│  Storage: ~50+ KB per drug (with related data)  │
│                                                  │
│  Contains:                                       │
│  - All FDB fields                               │
│  - Dosing, warnings, contraindications          │
│  - Pricing, NDC codes                           │
│  - Ingredients, interactions                    │
│                                                  │
│  Total: 2.5+ GB for 50k drugs                   │
└─────────────────────────────────────────────────┘
```

**Sync Strategy:**
- Aurora is master (FDB updates go here first)
- Redis syncs from Aurora (daily batch job)
- Redis only stores searchable/filterable fields
- Aurora stores everything else

**Trade-offs:**
- ✅ Optimal performance (each DB does what it's best at)
- ✅ Cost-effective (Redis only stores search data)
- ❌ Data duplication (filter fields in both)
- ❌ Sync complexity (need to keep in sync)

---

### Pattern 5: Prompt Caching for Cost Efficiency

**Problem:** Medical terminology prompt is large and repeated every query

**Solution:** Bedrock prompt caching (ephemeral cache)

```python
request = {
    "system": [
        {
            "type": "text",
            "text": MEDICAL_SEARCH_PROMPT,  # Large prompt with all abbreviations
            "cache_control": {"type": "ephemeral"}  # ← Cache this!
        }
    ],
    "messages": [{"role": "user", "content": user_query}]  # Only this changes
}
```

**Cost Impact:**
```
Without caching:
- Input: 5000 tokens (prompt) + 50 tokens (query) = 5050 tokens
- Cost: $15/MTok × 5.05 = $0.075 per query
- At 100k queries: $7,500

With caching (90% cache hit):
- Cached: 5000 tokens at $1.50/MTok (10% write, 90% read)
- Fresh: 50 tokens at $15/MTok
- Cost: ~$0.003 per query
- At 100k queries: $300 (25x cheaper!)
```

---

### Pattern 6: Multi-Drug Search (Phase Separation)

**Problem:** Queries like "high cholesterol" extract multiple drugs ("atorvastatin rosuvastatin simvastatin"). Single combined embedding gives poor similarity (41%) and misses drugs.

**Solution:** Two-phase search with individual embeddings

```python
# PHASE 1: Vector search each drug individually (NO expansion)
drug_terms = ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "lovastatin"]
all_vector_results = []

for drug_term in drug_terms:
    embedding = generate_embedding(drug_term)  # Individual embedding
    results = redis_vector_only_search(embedding, filters)  # NO expansion
    all_vector_results.extend(results)

# PHASE 2: ONE expansion pass on combined results
expanded_results = perform_drug_expansion(
    initial_drugs=all_vector_results,
    filters=filters
)
```

**Performance Impact:**
```
Before (single embedding):
- Embedding: "atorvastatin rosuvastatin simvastatin..." → [vector]
- Redis KNN: 1 search → finds LOVASTATIN (41% similarity)
- Missing: ATORVASTATIN, ROSUVASTATIN, PRAVASTATIN
- Result: 1 of 5 drugs found ❌

After (individual embeddings):
- Embeddings: 5 separate → 5 vectors
- Redis KNN: 5 searches → finds ALL 5 drugs
- Similarities: 54-67% (vs 41%)
- Expansion: 1 pass (not 5)
- Result: 5 of 5 drugs found ✅
```

**Key Benefits:**
- ✅ 100% recall (finds all Claude-extracted drugs)
- ✅ Better similarity scores (50-60% vs 30-40%)
- ✅ Correct badge classification (vector not overwritten by expansion)
- ✅ More efficient (1 expansion instead of N)

**Implementation:**
- `redis_vector_only_search()`: Vector search without expansion
- `perform_drug_expansion()`: Unified expansion logic for drug_class + therapeutic_class
- Threshold: 3+ drugs triggers multi-drug search

---

### Pattern 7: Batch Enrichment

**Problem:** Fetching drug details one-by-one is slow

**Solution:** Batch Aurora query with IN clause

```python
# Instead of 20 separate queries:
for drug_id in drug_ids:
    fetch_drug(drug_id)  # 20 × 5ms = 100ms

# Single batch query:
query = f"""
    SELECT * FROM drugs 
    WHERE drug_id IN ({','.join(['%s'] * len(drug_ids))})
"""
cursor.execute(query, drug_ids)  # 1 × 15ms = 15ms
```

**Performance:**
- 20 queries: ~100ms total
- 1 batch query: ~15ms total
- **6-7x faster!**

---

## Data Flow Patterns

### Search Request Flow

```
1. User Query → API Gateway
   "statin for high cholesterol"

2. Lambda: Parse with Claude
   → {search_text: "atorvastatin rosuvastatin statin", 
      filters: {drug_class: "statin", indication: "hyperlipidemia"}}

3. Lambda: Generate Embedding
   → Titan.embed(search_text) → [0.12, -0.33, ..., 0.56] (1024 floats)

4. Lambda: Redis Hybrid Search
   → query with vector + filters → [drug_id: 123, 456, 789, ...]

5. Lambda: Aurora Batch Enrichment
   → SELECT * WHERE drug_id IN (123, 456, 789) → Full drug records

6. Lambda: Format Response
   → Merge vector scores + drug data → JSON

7. API Gateway → User
   → {results: [{name: "Atorvastatin", score: 0.95, ...}]}
```

**Latency Budget:**
- Claude: 150-200ms (cached prompt helps)
- Titan: 50-100ms
- Redis: 10-15ms
- Aurora: 15-20ms
- Overhead: 5-10ms
- **Total: 230-345ms** (target <350ms p95)

---

### Data Sync Flow

```
1. FDB Update
   → New SQL dump → database/imports/fdb_tables.sql

2. Load to Aurora
   → psql $DATABASE_URL < fdb_tables.sql

3. Trigger Sync Lambda
   → EventBridge schedule (daily) or manual invoke

4. Sync Lambda Process
   For each drug in Aurora:
     a. Fetch drug + metadata (name, class, indication, etc.)
     b. Create embedding text: "{name} {brand} {class} {indication}"
     c. Generate embedding: model.embed(text)
     d. Store in Redis: HSET drug:{id} {...fields, embedding}

5. Redis Index
   → Automatically updates with new drugs (FT.ADD not needed)

6. Validation
   → Count drugs in Aurora vs Redis
   → Sample search queries to verify accuracy
```

**Sync Performance:**
- 50,000 drugs
- Titan: ~100 embeds/second
- Total time: ~10 minutes for full reindex
- Cost: 50k × $0.0001 = **$5 per full sync**

---

## Key Technical Decisions

### Decision: Redis vs OpenSearch vs pgvector

| Feature | Redis Stack 8.2.2 | OpenSearch | pgvector |
|---------|-------------------|------------|----------|
| **Hybrid search** | ✅ Native | ✅ Native | ❌ Separate queries |
| **Quantization** | ✅ INT8 | ❌ No | ❌ No |
| **Latency** | 10-15ms | 30-50ms | 50-100ms |
| **Cost (50k docs)** | $120/mo | $200+/mo | $50/mo (in Aurora) |
| **Maintenance** | Medium (self-managed EC2) | Medium | Low |

**Winner: Redis Stack 8.2.2 on EC2** - Best performance, customer requirement, LeanVec4x8 quantization support
- Note: Using EC2 instead of ElastiCache because ElastiCache only supports Redis 7.1 (no quantization)
- See docs/REDIS_INFRASTRUCTURE_DECISION.md for full analysis

### Decision: Sync Strategy (Batch vs Streaming)

| Approach | Pros | Cons |
|----------|------|------|
| **Batch (daily)** | Simple, predictable cost | Stale data (up to 24h) |
| **Streaming (CDC)** | Real-time, always fresh | Complex, higher cost |
| **On-demand** | Manual control | Requires manual trigger |

**Winner: Batch (daily)** - FDB updates weekly, so daily sync is sufficient

### Decision: Embedding Dimensions

| Model | Dimensions | Storage | Accuracy |
|-------|-----------|---------|----------|
| **Titan v2** | 1024 | 4 KB → 1 KB (quant) | Good |
| **SapBERT** | 768 | 3 KB → 768 bytes (quant) | Better (medical) |

**Winner: Titan (start)** - Can upgrade to SapBERT if accuracy insufficient

---

## Scalability Patterns

### Horizontal Scaling

**API Layer:**
- Lambda auto-scales (1 → 1000+ concurrent)
- No warm-up needed (Python 3.12 fast cold start)
- Each invocation handles 1 request

**Redis:**
- Single Redis node: 50k RPS (more than enough)
- If needed: Redis Cluster (5+ nodes) → 250k+ RPS
- Read replicas for read-heavy workload

**Aurora:**
- Aurora Serverless v2: Auto-scales (0.5 → 128 ACU)
- Read replicas if enrichment becomes bottleneck
- Connection pooling in Lambda (reuse connections)

### Caching Strategy

**L1: Lambda Memory Cache**
```python
# Cache frequent queries in Lambda memory (reused across invocations)
query_cache = {}  # In-memory, per container

def search(query):
    if query in query_cache:
        return query_cache[query]  # ~0ms
    result = perform_search(query)
    query_cache[query] = result
    return result
```

**L2: Redis Cache**
- Vector search results already cached implicitly
- Query result caching (optional): TTL 1 hour

**L3: CloudFront (future)**
- Cache popular search results at edge
- Low TTL (5 minutes) for freshness

---

## Error Handling Patterns

### Graceful Degradation

```python
def search(query):
    try:
        # Try full pipeline
        parsed = claude_parse(query)
        embedding = get_embedding(parsed["search_text"])
        results = redis_search(embedding, parsed["filters"])
        enriched = aurora_enrich(results)
        return enriched
    except ClaudeError:
        # Fallback: Use query as-is
        embedding = get_embedding(query)
        results = redis_search(embedding)
        enriched = aurora_enrich(results)
        return enriched
    except RedisError:
        # Fallback: Direct Aurora search (slower)
        return aurora_text_search(query)
    except Exception as e:
        # Last resort: Return error
        log_error(e)
        return {"error": "Search temporarily unavailable"}
```

### Circuit Breaker

```python
# Protect against cascading failures
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
def claude_parse(query):
    # If Claude fails 5 times, stop calling for 60 seconds
    return claude.parse(query)
```

---

## Security Patterns

### Secrets Management

```typescript
// SST configuration
const dbPassword = new sst.Secret("DatabasePassword");
const redisAuth = new sst.Secret("RedisAuthToken");

// Lambda can access via environment
process.env.DATABASE_PASSWORD  // Auto-injected by SST
```

### VPC Security

```
┌──────────────────────────────────────────┐
│           Public Subnet                  │
│  ┌────────────────────┐                  │
│  │  API Gateway       │ (public)         │
│  └──────────┬─────────┘                  │
└─────────────┼────────────────────────────┘
              │
┌─────────────┼────────────────────────────┐
│           Private Subnet                 │
│  ┌──────────▼─────────┐                  │
│  │  Lambda Functions  │                  │
│  └──┬──────┬──────┬───┘                  │
│     │      │      │                      │
│  ┌──▼──┐┌─▼───┐┌─▼───────┐              │
│  │Redis││Aurora││SecretsMgr│             │
│  └─────┘└─────┘└──────────┘              │
│  (Private: No internet access)           │
└──────────────────────────────────────────┘
```

**Security Groups:**
- Lambda → Redis: Port 6379 only
- Lambda → Aurora: Port 5432 only
- Lambda → Bedrock: Via NAT Gateway (HTTPS)

---

## Monitoring Patterns

### Key Metrics

**Search Performance:**
- `search.latency.p50` - Median latency
- `search.latency.p95` - 95th percentile
- `search.latency.p99` - 99th percentile
- `search.throughput` - Queries per second

**Accuracy:**
- `search.zero_results_rate` - % queries with no results
- `search.avg_result_count` - Average results returned
- `search.filter_hit_rate` - % queries using filters

**Cost:**
- `bedrock.claude.invocations` - Claude calls
- `bedrock.claude.cache_hit_rate` - Prompt cache hits
- `bedrock.titan.invocations` - Embedding calls
- `redis.ops_per_second` - Redis operations

**Errors:**
- `errors.claude.rate` - Claude failures
- `errors.redis.rate` - Redis failures
- `errors.aurora.rate` - Aurora failures

### Alerting Thresholds

```yaml
Alerts:
  - Name: HighLatency
    Condition: search.latency.p95 > 100ms
    Action: SNS notification
  
  - Name: HighErrorRate
    Condition: errors.rate > 5%
    Action: SNS notification + PagerDuty
  
  - Name: LowCacheHitRate
    Condition: claude.cache_hit_rate < 70%
    Action: SNS notification (investigate prompt structure)
```

---

## Testing Patterns

### Unit Tests

```python
def test_embedding_abstraction():
    # Mock embedding model
    mock_model = MockEmbeddingModel()
    vector = mock_model.embed("test")
    assert vector.shape == (1024,)

def test_claude_parser():
    parser = ClaudeQueryParser()
    result = parser.parse("ASA for pain")
    assert "aspirin" in result["search_text"].lower()
    assert result["filters"]["indication"] == "pain"
```

### Integration Tests

```python
def test_end_to_end_search():
    # Test full pipeline
    response = search_api.post("/api/drugs/search", 
                               json={"query": "statin for cholesterol"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) > 0
    assert any("statin" in r["drug_class"].lower() for r in results)
```

### Load Tests

```bash
# Artillery load test
artillery run load-test.yml

# Config: 100 RPS for 5 minutes
# Verify: p95 < 100ms, error rate < 1%
```

---

**Status:** ✅ System patterns documented and updated with multi-drug search
**Last Updated:** 2025-11-21
**Next Review:** After user acceptance testing


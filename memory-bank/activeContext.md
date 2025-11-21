# Active Context: Current Work Focus

**Last Updated:** 2025-11-21  
**Session Status:** Multi-drug search optimization + query classification complete  
**Current Priority:** Production-ready search with accurate matching

---

## 🎯 Sprint Goal

Production-quality drug search with accurate semantic matching:
- Multi-drug queries find ALL drugs via individual vector searches
- Results properly badged: Vector Search → Pharmacological → Therapeutic Alternative
- Claude extracts ONLY drug names in embeddings (no condition words)
- Claude returns ONLY relevant filters (dosage_form, strength)

---

## ✅ Major Improvements (2025-11-21)

### 1. **Multi-Drug Search Architecture** ✅
**Problem**: Single embedding for "atorvastatin rosuvastatin simvastatin" gave 41% similarity, missed drugs

**Solution**: Two-phase approach
- Phase 1: Vector search EACH drug individually (no expansion)
- Phase 2: ONE expansion pass on combined results
- New functions: `redis_vector_only_search()`, `perform_drug_expansion()`

**Results**: All 5 statins found with 54-67% similarity (vs 41% before)

### 2. **Embedding Text Optimization** ✅
**Problem**: Embeddings included condition words → matched supplements

**Solution**: Claude extracts ONLY drug names
- "high cholesterol" → `"atorvastatin rosuvastatin simvastatin pravastatin lovastatin"`
- "male hormone replacement" → `"testosterone"`
- File: `functions/src/prompts/medical_search.py`

### 3. **Simplified Claude Schema** ✅
**Removed**: indication, drug_class, therapeutic_class, is_generic, dea_schedule, drug_type

**Kept**: Only `dosage_form` and `strength`

**Rationale**: Expansion logic is more accurate than Claude extraction

### 4. **Correct Badge Classification** ✅
**Problem**: Vector results overwritten as "Therapeutic Alternative" due to NDC duplicates

**Solution**: Deduplication prioritizes vector > drug_class > therapeutic

**Badge update**: "Exact Match" → "Vector Search"

### 5. **Result Sorting** ✅
Results sorted by match_type + similarity:
1. Vector Search (highest similarity first)
2. Pharmacological Match  
3. Therapeutic Alternative

---

## 🏗️ Current Architecture

### Search Flow
```
User Query
  ↓
Claude (extract drug names + filters)
  ↓
Multi-drug? (3+ drugs)
  ├─ YES: Vector search each → combine → expand once
  └─ NO: Single vector search + expansion
  ↓
Group by drug_class/brand_name
  ↓
Sort by match_type + similarity
  ↓
Return results
```

### Key Components
- **Redis Index**: `drugs_idx` (1024-dim Titan v2 embeddings, HNSW)
- **Lexical Pre-filter**: Uses Claude's drug names (not user's raw terms)
- **Drug Family Grouping**: By `brand_name` (brands) or `drug_class` (generics)
- **Manufacturer Grouping**: Within each family, collapsed by default
- **Indication Storage**: Separate Redis keys to save memory
- **Therapeutic Blacklist**: "Bulk Chemicals", "Miscellaneous", "Uncategorized", "Not Specified"

---

## ✅ What's Working

- ✅ Multi-drug search returns all expected drugs (100% recall)
- ✅ Correct badge classification (no badge overwrites)
- ✅ Proper result sorting by match type and similarity
- ✅ Clean embeddings (drug names only)
- ✅ Dosage form filtering with FDB mappings (injection → VIAL, SOL, SYRINGE)
- ✅ Strength filtering (post-expansion, handles decimals and unitless)
- ✅ Lexical pre-filter using Claude's extracted names
- ✅ Production data loaded (all active FDB drugs)

---

## 📋 Known Limitations

1. **Estrogen mapping**: "estrogen" doesn't exist in FDB (need "estradiol" synonym)
2. **Titan similarity scores**: Medical drug relationships have low scores (30-40%)
3. **No telemetry yet**: Should add latency/accuracy metrics

---

## 🔑 Reference Points

- **API Gateway (dev):** https://9yb31qmdfa.execute-api.us-east-1.amazonaws.com  
- **Search Handler:** `functions/src/search_handler.py`
- **Claude Prompt:** `functions/src/prompts/medical_search.py`
- **Redis Schema:** `docs/REDIS_FINAL_SCHEMA.md`
- **Redis Host:** 10.0.11.153 (EC2 r7g.large, Redis Stack 8.2.2)

---

## 🔍 Caching Evaluation (2025-11-21)

### SemanticCache (Not Implemented) ❌
**Purpose**: Cache LLM responses by semantic similarity  
**Decision**: NOT implementing due to complexity/size  
**Why**:
- Requires `redisvl>=0.11.0` + `sentence-transformers>=5.1.2`
- `sentence-transformers` is ~1.5 GB (Lambda 250 MB limit)
- Would need lightweight embedding model or external service
- Complexity not justified for current scale

**Status**: RedisVL installed on Redis EC2 (for testing), but NOT in Lambda

### EmbeddingsCache (Future Consideration) ✅ RECOMMENDED
**Purpose**: Cache Titan embedding vectors to avoid re-computing  
**Current Flow**:
```python
# "high cholesterol" → 5 drugs × 50-100ms each = 250-500ms
for drug in ["atorvastatin", "rosuvastatin", "simvastatin", ...]:
    embedding = bedrock.invoke_model(...)  # Titan API call
```

**With EmbeddingsCache**:
```python
for drug in drugs:
    cached = embeddings_cache.get(text=drug, model="titan-v2")
    if cached:
        embedding = cached['embedding']  # <1ms from Redis! 🚀
    else:
        embedding = bedrock.invoke_model(...)
        embeddings_cache.set(text=drug, model="titan-v2", embedding=embedding)
```

**Benefits**:
- **Latency**: Redis lookup (<1ms) vs Titan API (50-100ms) = 50-100x faster
- **Cost**: Titan charges per token - caching common drugs saves money
- **High hit rate**: Common drugs (insulin, metformin, atorvastatin, lisinopril) cached after first use
- **Deterministic**: Titan embeddings are deterministic (same input = same output)

**Implementation**:
- **Easy IF** `redisvl` works WITHOUT `sentence-transformers` (needs testing)
- **Fallback**: Manual Redis hash storage (80% of benefit, zero dependencies)

```python
# Simple manual implementation (no RedisVL needed)
def get_cached_embedding(drug_name: str) -> Optional[List[float]]:
    key = f"embedding:titan-v2:{drug_name}"
    cached = redis_client.get(key)
    return json.loads(cached) if cached else None

def cache_embedding(drug_name: str, embedding: List[float], ttl: int = 2592000):
    key = f"embedding:titan-v2:{drug_name}"
    redis_client.setex(key, ttl, json.dumps(embedding))
```

**Recommendation**: Implement after baseline performance validation (Phase 7)

**Reference**: https://redis.io/docs/latest/develop/ai/redisvl/api/cache/#embeddings-cache

---

## 💬 Next Steps

1. **Add medical synonym mapping** (estrogen → estradiol, etc.)
2. **Performance telemetry** (search latency, embedding costs)
3. **Consider EmbeddingsCache** for Titan API call optimization (50-100x latency reduction)
4. **User acceptance testing** with actual prescriber workflows


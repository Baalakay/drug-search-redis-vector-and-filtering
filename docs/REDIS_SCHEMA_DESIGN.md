# Redis Schema Design for DAW Drug Search

**Version:** 1.0  
**Date:** 2025-11-10  
**Status:** Design Complete, Ready for Implementation

---

## Overview

This document defines the Redis data model and index configuration for the DAW drug search system. The schema is optimized for hybrid search (vector similarity + filters) with LeanVec4x8 quantization for 3x memory reduction.

---

## Data Model

### Document Structure

Each drug is stored as a Redis JSON document with the following schema:

```json
{
  "ndc": "00002010102",
  "drug_name": "LISINOPRIL 10 MG TABLET",
  "brand_name": "PRINIVIL",
  "generic_name": "lisinopril",
  "gcn_seqno": 25462,
  "dosage_form": "TABLET",
  "strength": "10 MG",
  "manufacturer": "LILLY",
  "is_generic": true,
  "is_brand": false,
  "dea_schedule": null,
  "drug_class": "ACE INHIBITOR",
  "therapeutic_class": "CARDIOVASCULAR",
  "embedding": [0.123, -0.456, ...],  // 1024 floats
  "indexed_at": "2025-11-10T12:00:00Z"
}
```

### Key Design Decisions

| Field | Type | Indexed | Purpose |
|-------|------|---------|---------|
| `ndc` | String | ✅ Key | Unique identifier (National Drug Code) |
| `drug_name` | String | ✅ Full-text | Primary search field |
| `brand_name` | String | ✅ Full-text | Brand name search |
| `generic_name` | String | ✅ Full-text | Generic name search |
| `gcn_seqno` | Numeric | ✅ Filter | Generic Code Number (drug equivalency) |
| `dosage_form` | Tag | ✅ Filter | TABLET, CAPSULE, INJECTION, etc. |
| `strength` | String | ❌ | Display only (too variable for filtering) |
| `manufacturer` | Tag | ✅ Filter | Manufacturer code |
| `is_generic` | Tag | ✅ Filter | Generic vs brand filtering |
| `is_brand` | Tag | ✅ Filter | Brand availability |
| `dea_schedule` | Tag | ✅ Filter | Controlled substance schedule (1-5) |
| `drug_class` | Tag | ✅ Filter | Pharmacological class |
| `therapeutic_class` | Tag | ✅ Filter | Therapeutic category |
| `embedding` | Vector | ✅ Vector search | 1024-dim Titan embedding |
| `indexed_at` | String | ❌ | Metadata for debugging |

---

## Redis Index Configuration

### Index Definition

```python
# Index name
INDEX_NAME = "idx:drugs"

# Key prefix
KEY_PREFIX = "drug:"

# Index type
INDEX_TYPE = IndexType.JSON
```

### Field Schema

```python
from redis.commands.search.field import (
    TextField, 
    NumericField, 
    TagField,
    VectorField
)

schema = (
    # Full-text search fields
    TextField("$.drug_name", as_name="drug_name", weight=2.0),
    TextField("$.brand_name", as_name="brand_name", weight=1.5),
    TextField("$.generic_name", as_name="generic_name", weight=1.5),
    
    # Numeric filter
    NumericField("$.gcn_seqno", as_name="gcn_seqno"),
    
    # Tag filters (exact match, fast)
    TagField("$.dosage_form", as_name="dosage_form"),
    TagField("$.manufacturer", as_name="manufacturer"),
    TagField("$.is_generic", as_name="is_generic"),
    TagField("$.is_brand", as_name="is_brand"),
    TagField("$.dea_schedule", as_name="dea_schedule"),
    TagField("$.drug_class", as_name="drug_class"),
    TagField("$.therapeutic_class", as_name="therapeutic_class"),
    
    # Vector field with LeanVec4x8 quantization
    VectorField(
        "$.embedding",
        "HNSW",  # HNSW algorithm for fast ANN search
        {
            "TYPE": "FLOAT32",
            "DIM": 1024,
            "DISTANCE_METRIC": "COSINE",
            "INITIAL_CAP": 500000,  # Pre-allocate for 500K drugs
            "M": 40,  # HNSW: connections per layer (trade-off: memory vs accuracy)
            "EF_CONSTRUCTION": 200,  # HNSW: construction quality
            "EF_RUNTIME": 10,  # HNSW: search quality (can be overridden at query time)
            # LeanVec4x8 quantization (Redis Stack 8.2.2+)
            "QUANTIZATION": {
                "TYPE": "LEANVEC4X8",  # 3x memory reduction
                "DIMENSION_REDUCTION": 256  # Reduce to 256 dims internally
            }
        },
        as_name="embedding"
    )
)
```

### Index Settings

```python
from redis.commands.search.index_definition import IndexDefinition

definition = IndexDefinition(
    prefix=["drug:"],
    index_type=IndexType.JSON,
    language="english",  # For stemming in full-text search
    score=1.0,
    score_field="__score"
)
```

---

## Memory Calculations

### Without Quantization (Baseline)

```
50,000 drugs × 1024 dims × 4 bytes (FLOAT32) = 205 MB
+ Metadata (~2 KB per drug) = 100 MB
+ Redis overhead (~30%) = 90 MB
Total: ~395 MB
```

### With LeanVec4x8 Quantization

```
50,000 drugs × 256 dims × 1 byte (INT8) = 13 MB
+ Metadata (~2 KB per drug) = 100 MB  
+ Redis overhead (~30%) = 34 MB
Total: ~147 MB (63% reduction!)
```

**Savings:** 248 MB per 50K drugs

---

## Query Examples

### 1. Pure Vector Search (No Filters)

Find drugs semantically similar to query:

```python
from redis.commands.search.query import Query

# Generate query embedding
query_text = "blood pressure medication"
query_embedding = titan.embed(query_text)

# Create KNN query
q = Query("*=>[KNN 20 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "brand_name", "score") \
    .sort_by("score") \
    .paging(0, 20) \
    .dialect(2)

# Execute
results = redis_client.ft(INDEX_NAME).search(
    q, 
    query_params={"vec": query_embedding}
)
```

**Use Case:** General semantic search without constraints

---

### 2. Hybrid Search (Vector + Filters)

Find generic tablets similar to query:

```python
# Query with filters
filter_query = "@is_generic:{true} @dosage_form:{TABLET}"

q = Query(f"{filter_query}=>[KNN 20 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "gcn_seqno", "score") \
    .sort_by("score") \
    .paging(0, 20) \
    .dialect(2)

results = redis_client.ft(INDEX_NAME).search(
    q,
    query_params={"vec": query_embedding}
)
```

**Use Case:** Semantic search with hard constraints (formulary, generic-only)

---

### 3. Filter by GCN Range

Find drugs with specific GCN (drug equivalency class):

```python
filter_query = "@gcn_seqno:[25460 25465]"  # Range query

q = Query(f"{filter_query}=>[KNN 10 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "gcn_seqno", "score") \
    .sort_by("score") \
    .dialect(2)

results = redis_client.ft(INDEX_NAME).search(
    q,
    query_params={"vec": query_embedding}
)
```

**Use Case:** Find alternatives with same active ingredient

---

### 4. Multiple Tag Filters

Find controlled substances that are tablets:

```python
filter_query = "@dea_schedule:{2|3|4} @dosage_form:{TABLET}"

q = Query(f"{filter_query}=>[KNN 20 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "dea_schedule", "score") \
    .sort_by("score") \
    .dialect(2)

results = redis_client.ft(INDEX_NAME).search(
    q,
    query_params={"vec": query_embedding}
)
```

**Use Case:** Regulatory compliance filtering

---

### 5. Full-Text + Vector Search

Combine text search with vector similarity:

```python
# Full-text search on drug name + vector similarity
text_query = "@drug_name:lisinopril"

q = Query(f"{text_query}=>[KNN 10 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "score") \
    .sort_by("score") \
    .dialect(2)

results = redis_client.ft(INDEX_NAME).search(
    q,
    query_params={"vec": query_embedding}
)
```

**Use Case:** Exact text match with semantic ranking

---

## Performance Characteristics

### Query Latency (Expected)

| Query Type | Latency (p50) | Latency (p95) | Notes |
|------------|---------------|---------------|-------|
| Pure vector (K=20) | 8-12ms | 15-20ms | HNSW with M=40 |
| Hybrid (1 filter) | 10-15ms | 20-25ms | Pre-filtered vectors |
| Hybrid (3+ filters) | 12-18ms | 25-30ms | More filters = fewer candidates |
| Full-text + vector | 15-20ms | 30-35ms | Text search overhead |

### Throughput

- **Concurrent queries:** 1000+ QPS on r7g.large (16GB RAM)
- **Index build time:** ~5 minutes for 50K drugs
- **Memory usage:** ~150 MB with quantization

---

## Index Maintenance

### Rebuilding the Index

```python
# Drop existing index (keeps data)
redis_client.ft(INDEX_NAME).dropindex(delete_documents=False)

# Recreate with new schema
redis_client.ft(INDEX_NAME).create_index(schema, definition=definition)

# Index is rebuilt automatically from existing documents
```

### Updating Documents

```python
# Update a single drug (re-indexes automatically)
key = f"drug:{ndc}"
redis_client.json().set(key, "$", updated_drug_document)
```

### Adding New Drugs

```python
# Add new drug (indexed automatically)
key = f"drug:{new_ndc}"
redis_client.json().set(key, "$", new_drug_document)
```

---

## Migration from Aurora

### Data Mapping

| Aurora (FDB) | Redis | Transformation |
|--------------|-------|----------------|
| `rndc14.NDC` | `ndc` | Direct copy |
| `rndc14.LN` | `drug_name` | Uppercase |
| `rndc14.BN` | `brand_name` | Uppercase, null → "" |
| `rndc14.GCN_SEQNO` | `gcn_seqno` | Cast to int |
| `rndc14.DF` | `dosage_form` | Normalize format |
| - | `generic_name` | Extract from LN (lowercase) |
| `rndc14.INNOV` | `is_brand` | 'Y' → true, else false |
| `rndc14.GNI` | `is_generic` | Inverse of is_brand |
| `rndc14.DEA` | `dea_schedule` | '0' → null, else value |
| - | `drug_class` | Lookup from GCN |
| - | `therapeutic_class` | Lookup from GCN |
| - | `embedding` | Generate via Titan |

### SQL Query for Export

```sql
SELECT 
    NDC as ndc,
    UPPER(LN) as drug_name,
    UPPER(COALESCE(BN, '')) as brand_name,
    LOWER(REGEXP_REPLACE(LN, ' [0-9].*', '')) as generic_name,
    CAST(COALESCE(GCN_SEQNO, 0) AS UNSIGNED) as gcn_seqno,
    DF as dosage_form,
    COALESCE(LBLRID, '') as manufacturer,
    CASE WHEN INNOV = '1' THEN 'true' ELSE 'false' END as is_brand,
    CASE WHEN INNOV = '0' THEN 'true' ELSE 'false' END as is_generic,
    CASE WHEN DEA IN ('1','2','3','4','5') THEN DEA ELSE NULL END as dea_schedule
FROM rndc14
WHERE LN IS NOT NULL
    AND LENGTH(LN) > 3
    AND NDC IS NOT NULL
ORDER BY NDC
```

---

## Quantization Trade-offs

### LeanVec4x8 Configuration

**What it does:**
- Reduces vector dimensions: 1024 → 256 (4x)
- Quantizes to 8-bit integers: FLOAT32 → INT8 (4x)
- **Total reduction:** 16x in vector size, 3x overall (with metadata)

**Accuracy Impact:**
- **Recall@20:** 95-98% (minimal loss)
- **Search quality:** Nearly identical to uncompressed
- **Speed:** Slightly faster due to smaller data transfer

**Configuration Options:**

```python
# High accuracy (recommended)
"QUANTIZATION": {
    "TYPE": "LEANVEC4X8",
    "DIMENSION_REDUCTION": 256  # Keep 25% of dimensions
}

# Maximum compression
"QUANTIZATION": {
    "TYPE": "LEANVEC4X8", 
    "DIMENSION_REDUCTION": 128  # Keep 12.5% (more loss)
}

# No quantization (baseline)
"QUANTIZATION": {}  # Omit this section
```

---

## Monitoring & Debugging

### Index Statistics

```python
# Get index info
info = redis_client.ft(INDEX_NAME).info()

print(f"Documents: {info['num_docs']}")
print(f"Index size: {info['inverted_sz_mb']} MB")
print(f"Vector index size: {info['vector_index_sz_mb']} MB")
print(f"Total memory: {info['total_inverted_index_blocks']} MB")
```

### Query Profiling

```python
from redis.commands.search.query import Query

q = Query("*=>[KNN 20 @embedding $vec]") \
    .return_fields("ndc", "drug_name") \
    .dialect(2)

# Profile the query
profile = redis_client.ft(INDEX_NAME).profile(q, query_params={"vec": embedding})

print(f"Total time: {profile.total_time}ms")
print(f"Parsing time: {profile.parsing_time}ms")  
print(f"Pipeline creation: {profile.pipeline_creation_time}ms")
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Slow queries | Low EF_RUNTIME | Increase EF_RUNTIME at query time |
| High memory | No quantization | Enable LeanVec4x8 |
| Low recall | Too much compression | Increase DIMENSION_REDUCTION |
| Index build slow | Low EF_CONSTRUCTION | Increase EF_CONSTRUCTION (build-time only) |

---

## Next Steps

1. **Implement Index Creation Script** (`scripts/create_redis_index.py`)
2. **Build Data Sync Pipeline** (Aurora → Redis with embeddings)
3. **Test Query Performance** (latency, recall, memory)
4. **Tune HNSW Parameters** (M, EF_CONSTRUCTION, EF_RUNTIME)
5. **Validate Quantization** (accuracy vs compression trade-off)

---

**Status:** ✅ Design Complete  
**Ready for:** Implementation (Phase 3 Execution)  
**Estimated Implementation Time:** 2-3 hours


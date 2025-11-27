# Redis Query Examples for DAW Drug Search

**Version:** 1.0  
**Date:** 2025-11-10  
**Prerequisites:** Redis Stack 8.2.2+, Index created via `scripts/create_redis_index.py`

---

## Quick Reference

### Index Information
- **Index Name:** `idx:drugs`
- **Key Prefix:** `drug:`
- **Document Type:** JSON
- **Vector Dimension:** 1024 (Titan embeddings)
- **Quantization:** LeanVec4x8 (1024 → 256 dims)

### Common Query Patterns

```python
from redis.commands.search.query import Query

# 1. Pure vector search (no filters)
q = Query("*=>[KNN 20 @embedding $vec AS score]")

# 2. Vector + single filter
q = Query("@is_generic:{true}=>[KNN 20 @embedding $vec AS score]")

# 3. Vector + multiple filters
q = Query("@is_generic:{true} @dosage_form:{TABLET}=>[KNN 20 @embedding $vec AS score]")

# 4. Vector + numeric range
q = Query("@gcn_seqno:[25000 26000]=>[KNN 20 @embedding $vec AS score]")

# 5. Full-text + vector
q = Query("@drug_name:lisinopril=>[KNN 10 @embedding $vec AS score]")
```

---

## Complete Examples

### Setup

```python
import redis
import boto3
import json
from redis.commands.search.query import Query

# Connect to Redis
r = redis.Redis(host='10.0.11.245', port=6379, decode_responses=False)

# Bedrock client for embeddings
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def generate_embedding(text):
    """Generate embedding using Titan v2"""
    body = json.dumps({
        "inputText": text,
        "dimensions": 1024,
        "normalize": True
    })
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=body
    )
    return json.loads(response["body"].read())["embedding"]
```

---

### Example 1: Basic Vector Search

Find drugs similar to "blood pressure medication":

```python
# Generate query embedding
query_text = "blood pressure medication"
query_embedding = generate_embedding(query_text)

# Create query
q = Query("*=>[KNN 20 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "brand_name", "gcn_seqno", "score") \
    .sort_by("score") \
    .paging(0, 20) \
    .dialect(2)

# Execute search
results = r.ft("idx:drugs").search(
    q,
    query_params={"vec": json.dumps(query_embedding).encode()}
)

# Display results
print(f"Found {results.total} results:")
for i, doc in enumerate(results.docs, 1):
    print(f"{i}. {doc.drug_name} (NDC: {doc.ndc}) - Score: {doc.score}")
```

**Output:**
```
Found 20 results:
1. LISINOPRIL 10 MG TABLET (NDC: 00002010102) - Score: 0.92
2. ATENOLOL 50 MG TABLET (NDC: 00003020203) - Score: 0.89
3. LOSARTAN 50 MG TABLET (NDC: 00004030304) - Score: 0.87
...
```

---

### Example 2: Generic Only Filter

Find only generic drugs:

```python
query_text = "pain reliever"
query_embedding = generate_embedding(query_text)

# Add generic filter
q = Query("@is_generic:{true}=>[KNN 20 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "is_generic", "score") \
    .sort_by("score") \
    .paging(0, 20) \
    .dialect(2)

results = r.ft("idx:drugs").search(
    q,
    query_params={"vec": json.dumps(query_embedding).encode()}
)

print(f"Generic drugs only: {results.total} results")
for doc in results.docs[:5]:
    print(f"  • {doc.drug_name} (Generic: {doc.is_generic})")
```

---

### Example 3: Dosage Form Filter

Find only tablets:

```python
query_text = "antibiotic"
query_embedding = generate_embedding(query_text)

# Filter by dosage form
q = Query("@dosage_form:{TABLET}=>[KNN 15 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "dosage_form", "score") \
    .sort_by("score") \
    .paging(0, 15) \
    .dialect(2)

results = r.ft("idx:drugs").search(
    q,
    query_params={"vec": json.dumps(query_embedding).encode()}
)

print(f"Tablet antibiotics: {results.total} results")
for doc in results.docs[:5]:
    print(f"  • {doc.drug_name} ({doc.dosage_form})")
```

---

### Example 4: Multiple Filters (Generic + Tablet)

Combine multiple tag filters:

```python
query_text = "cholesterol medication"
query_embedding = generate_embedding(query_text)

# Multiple filters: generic AND tablet
q = Query("@is_generic:{true} @dosage_form:{TABLET}=>[KNN 20 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "is_generic", "dosage_form", "score") \
    .sort_by("score") \
    .paging(0, 20) \
    .dialect(2)

results = r.ft("idx:drugs").search(
    q,
    query_params={"vec": json.dumps(query_embedding).encode()}
)

print(f"Generic tablets only: {results.total} results")
for doc in results.docs[:5]:
    print(f"  • {doc.drug_name} - {doc.dosage_form} (Generic: {doc.is_generic})")
```

---

### Example 5: GCN Range Query

Find drugs in specific GCN range (drug equivalency class):

```python
query_text = "statin"
query_embedding = generate_embedding(query_text)

# Filter by GCN range (e.g., all statins)
q = Query("@gcn_seqno:[25000 26000]=>[KNN 20 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "gcn_seqno", "score") \
    .sort_by("score") \
    .paging(0, 20) \
    .dialect(2)

results = r.ft("idx:drugs").search(
    q,
    query_params={"vec": json.dumps(query_embedding).encode()}
)

print(f"Drugs in GCN range 25000-26000: {results.total} results")
for doc in results.docs[:5]:
    print(f"  • {doc.drug_name} (GCN: {doc.gcn_seqno})")
```

---

### Example 6: Controlled Substances

Find controlled substances (DEA Schedule 2-4):

```python
query_text = "pain medication"
query_embedding = generate_embedding(query_text)

# Filter by DEA schedule (controlled substances)
q = Query("@dea_schedule:{2|3|4}=>[KNN 15 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "dea_schedule", "score") \
    .sort_by("score") \
    .paging(0, 15) \
    .dialect(2)

results = r.ft("idx:drugs").search(
    q,
    query_params={"vec": json.dumps(query_embedding).encode()}
)

print(f"Controlled substances: {results.total} results")
for doc in results.docs[:5]:
    print(f"  • {doc.drug_name} (DEA Schedule: {doc.dea_schedule})")
```

---

### Example 7: Full-Text Search

Combine exact text match with vector similarity:

```python
query_text = "lisinopril"
query_embedding = generate_embedding(query_text)

# Text search on drug name + vector ranking
q = Query("@drug_name:lisinopril=>[KNN 10 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "brand_name", "score") \
    .sort_by("score") \
    .paging(0, 10) \
    .dialect(2)

results = r.ft("idx:drugs").search(
    q,
    query_params={"vec": json.dumps(query_embedding).encode()}
)

print(f"Drugs containing 'lisinopril': {results.total} results")
for doc in results.docs:
    print(f"  • {doc.drug_name} (Brand: {doc.brand_name})")
```

---

### Example 8: Custom EF_RUNTIME (Query-Time Tuning)

Adjust search quality at query time:

```python
query_text = "diabetes medication"
query_embedding = generate_embedding(query_text)

# Increase EF_RUNTIME for higher accuracy (slower)
q = Query("*=>[KNN 20 @embedding $vec AS score EF_RUNTIME 50]") \
    .return_fields("ndc", "drug_name", "score") \
    .sort_by("score") \
    .paging(0, 20) \
    .dialect(2)

results = r.ft("idx:drugs").search(
    q,
    query_params={"vec": json.dumps(query_embedding).encode()}
)

print(f"High-accuracy search: {results.total} results")
for doc in results.docs[:5]:
    print(f"  • {doc.drug_name} - Score: {doc.score}")
```

**Note:** Default EF_RUNTIME is 10. Higher values = better accuracy but slower. Try 20, 50, or 100 for different quality/speed trade-offs.

---

### Example 9: Pagination

Get results in pages:

```python
query_text = "antibiotic"
query_embedding = generate_embedding(query_text)

page_size = 10
page_num = 2  # Get page 2 (results 11-20)

q = Query("*=>[KNN 100 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "score") \
    .sort_by("score") \
    .paging(page_num * page_size, page_size) \
    .dialect(2)

results = r.ft("idx:drugs").search(
    q,
    query_params={"vec": json.dumps(query_embedding).encode()}
)

print(f"Page {page_num + 1} of {results.total // page_size + 1}:")
for doc in results.docs:
    print(f"  • {doc.drug_name}")
```

---

### Example 10: Get Specific Document by NDC

Fetch a drug by its NDC (no search, direct lookup):

```python
ndc = "00002010102"
key = f"drug:{ndc}"

# Direct JSON get
drug = r.json().get(key)

if drug:
    print(f"Drug: {drug['drug_name']}")
    print(f"Brand: {drug['brand_name']}")
    print(f"GCN: {drug['gcn_seqno']}")
    print(f"Dosage Form: {drug['dosage_form']}")
else:
    print(f"Drug not found: {ndc}")
```

---

## Advanced Query Patterns

### Complex Filter Combinations

```python
# Generic tablets that are NOT controlled substances
filter_query = "@is_generic:{true} @dosage_form:{TABLET} -@dea_schedule:{1|2|3|4|5}"

q = Query(f"{filter_query}=>[KNN 20 @embedding $vec AS score]") \
    .return_fields("ndc", "drug_name", "is_generic", "dosage_form", "dea_schedule", "score") \
    .sort_by("score") \
    .dialect(2)

results = r.ft("idx:drugs").search(q, query_params={"vec": json.dumps(query_embedding).encode()})
```

### Wildcard Text Search

```python
# Find all drugs starting with "LISI"
q = Query("@drug_name:LISI*") \
    .return_fields("ndc", "drug_name") \
    .paging(0, 20) \
    .dialect(2)

results = r.ft("idx:drugs").search(q)
```

### Fuzzy Text Search

```python
# Find drugs with spelling tolerance
q = Query("@drug_name:%lisino%") \
    .return_fields("ndc", "drug_name") \
    .paging(0, 20) \
    .dialect(2)

results = r.ft("idx:drugs").search(q)
```

---

## Performance Tips

### 1. Use Appropriate K Value
- **K=20:** Good balance for most queries
- **K=50:** Better recall for diverse results
- **K=100+:** Expensive, use only if needed

### 2. Filter First, Search Second
```python
# Good: Filter reduces search space
"@dosage_form:{TABLET}=>[KNN 20 ...]"

# Bad: Searches everything, then filters
"*=>[KNN 100 ...] @dosage_form:{TABLET}"
```

### 3. Use Tag Fields for Exact Matches
```python
# Fast (tag field)
"@dosage_form:{TABLET}"

# Slow (full-text field)
"@drug_name:TABLET"
```

### 4. Tune EF_RUNTIME Based on Needs
```python
# Fast (default)
"=>[KNN 20 @embedding $vec AS score]"

# Balanced
"=>[KNN 20 @embedding $vec AS score EF_RUNTIME 20]"

# Accurate
"=>[KNN 20 @embedding $vec AS score EF_RUNTIME 50]"
```

---

## Debugging

### Check Index Stats

```python
info = r.ft("idx:drugs").info()
print(f"Documents: {info['num_docs']}")
print(f"Index size: {info['inverted_sz_mb']} MB")
```

### Profile a Query

```python
from redis.commands.search.query import Query

q = Query("*=>[KNN 20 @embedding $vec]").return_fields("ndc").dialect(2)

# Profile the query
profile = r.ft("idx:drugs").profile(q, query_params={"vec": json.dumps(query_embedding).encode()})

print(f"Total time: {profile.total_time}ms")
```

### Inspect a Document

```python
# Get full document
drug = r.json().get("drug:00002010102")
print(json.dumps(drug, indent=2))
```

---

## Common Errors

### Error: "No such index"
```python
# Check if index exists
try:
    r.ft("idx:drugs").info()
    print("Index exists")
except:
    print("Index not found - run create_redis_index.py")
```

### Error: "Unknown vector field"
```python
# Verify vector field name
q = Query("*=>[KNN 20 @embedding $vec AS score]")  # Correct
q = Query("*=>[KNN 20 @vector $vec AS score]")    # Wrong field name
```

### Error: "WRONGTYPE Operation against a key holding the wrong kind of value"
```python
# Check key type
key_type = r.type("drug:00002010102")
print(f"Key type: {key_type}")  # Should be "ReJSON-RL"
```

---

**Status:** ✅ Query examples complete  
**See Also:**  
- `docs/REDIS_SCHEMA_DESIGN.md` - Schema and index design
- `scripts/create_redis_index.py` - Index creation script
- `scripts/poc_redis_search.py` - End-to-end PoC example


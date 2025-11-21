#!/usr/bin/env python3
"""
Quick PoC: End-to-End Drug Search with Redis + Bedrock Titan

This script demonstrates the complete search pipeline:
1. Fetch sample drugs from Aurora
2. Generate embeddings using Bedrock Titan
3. Store in Redis with vector + filter fields
4. Test hybrid search (vector similarity + filters)
"""

import json
import sys
import boto3
import redis
from redis.commands.search.field import TextField, NumericField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query

print("🚀 DAW Drug Search PoC - End-to-End Test")
print("=" * 60)

# Step 1: Fetch sample drugs (from previous step)
print("\n📊 Step 1: Loading sample drugs...")
try:
    with open('/tmp/sample_drugs.json', 'r') as f:
        drugs = json.load(f)
    print(f"✅ Loaded {len(drugs)} drugs")
    for i, drug in enumerate(drugs[:3], 1):
        print(f"   {i}. {drug['drug_name'][:50]}")
except FileNotFoundError:
    print("❌ Sample drugs not found. Run poc_test.py first.")
    sys.exit(1)

# Step 2: Generate embeddings using Titan
print("\n🧠 Step 2: Generating embeddings with Bedrock Titan...")

bedrock = boto3.client(service_name="bedrock-runtime", region_name="us-east-1")

def generate_embedding(text):
    """Generate 1024-dim embedding using Titan v2"""
    body = json.dumps({
        "inputText": text,
        "dimensions": 1024,
        "normalize": True
    })
    
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        contentType="application/json",
        accept="application/json",
        body=body
    )
    
    result = json.loads(response["body"].read())
    return result["embedding"]

# Generate embeddings for all drugs
for drug in drugs:
    drug_text = drug['drug_name']
    drug['embedding'] = generate_embedding(drug_text)
    print(f"   ✅ {drug_text[:40]}")

print(f"✅ Generated {len(drugs)} embeddings (1024-dim each)")

# Step 3: Connect to Redis
print("\n🔴 Step 3: Connecting to Redis...")

try:
    r = redis.Redis(host='10.0.11.245', port=6379, decode_responses=False)
    r.ping()
    print(f"✅ Connected to Redis at 10.0.11.245:6379")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
    sys.exit(1)

# Step 4: Create Redis index with vectors
print("\n📑 Step 4: Creating RediSearch index...")

index_name = "idx:drugs"

# Drop existing index if it exists
try:
    r.ft(index_name).dropindex(delete_documents=True)
    print("   🗑️  Dropped existing index")
except:
    pass

# Create index schema
schema = (
    TextField("$.drug_name", as_name="drug_name"),
    TextField("$.brand_name", as_name="brand_name"),
    NumericField("$.gcn_seqno", as_name="gcn_seqno"),
    TextField("$.dosage_form", as_name="dosage_form"),
    VectorField(
        "$.embedding",
        "FLAT",  # Use FLAT for PoC, HNSW for production
        {
            "TYPE": "FLOAT32",
            "DIM": 1024,
            "DISTANCE_METRIC": "COSINE"
        },
        as_name="embedding"
    )
)

definition = IndexDefinition(prefix=["drug:"], index_type=IndexType.JSON)

r.ft(index_name).create_index(schema, definition=definition)
print(f"✅ Created index '{index_name}' with vector field (1024-dim)")

# Step 5: Store drugs in Redis
print("\n💾 Step 5: Storing drugs in Redis...")

for i, drug in enumerate(drugs):
    key = f"drug:{drug['ndc']}"
    
    # Prepare document
    doc = {
        "ndc": drug['ndc'],
        "drug_name": drug['drug_name'],
        "brand_name": drug['brand_name'] or "",
        "gcn_seqno": int(drug['gcn_seqno'] or 0),
        "dosage_form": drug['dosage_form'] or "",
        "embedding": drug['embedding']
    }
    
    # Store as JSON
    r.json().set(key, "$", doc)
    
    if i < 3:
        print(f"   ✅ {key}: {drug['drug_name'][:40]}")

print(f"✅ Stored {len(drugs)} drugs in Redis")

# Step 6: Test vector search
print("\n🔍 Step 6: Testing vector search...")

# Query: Search for "aspirin" (should match A.S.A. drugs)
query_text = "aspirin 325mg tablet"
print(f"   Query: '{query_text}'")

# Generate query embedding
query_embedding = generate_embedding(query_text)

# Create KNN query
q = Query("*=>[KNN 3 @embedding $vec AS score]").return_fields("drug_name", "brand_name", "score").sort_by("score").paging(0, 3).dialect(2)

# Execute search
results = r.ft(index_name).search(q, query_params={"vec": json.dumps(query_embedding).encode()})

print(f"\n   📊 Top 3 Results:")
for i, doc in enumerate(results.docs, 1):
    print(f"      {i}. {doc.drug_name} (score: {doc.score})")

# Step 7: Test hybrid search (vector + filter)
print("\n🔍 Step 7: Testing hybrid search (vector + filter)...")

# Query: Search for "aspirin" with filter on GCN
query_text = "pain reliever"
print(f"   Query: '{query_text}' + filter (GCN > 0)")

query_embedding = generate_embedding(query_text)

# Hybrid query: vector search + filter
q = Query("@gcn_seqno:[0 inf]=>[KNN 3 @embedding $vec AS score]").return_fields("drug_name", "gcn_seqno", "score").sort_by("score").paging(0, 3).dialect(2)

results = r.ft(index_name).search(q, query_params={"vec": json.dumps(query_embedding).encode()})

print(f"\n   📊 Top 3 Results (with GCN filter):")
for i, doc in enumerate(results.docs, 1):
    print(f"      {i}. {doc.drug_name} - GCN:{doc.gcn_seqno} (score: {doc.score})")

# Summary
print("\n" + "=" * 60)
print("🎉 PoC Test Complete!")
print("=" * 60)
print("\n✅ Verified:")
print("   • Bedrock Titan embeddings (1024-dim)")
print("   • Redis vector storage")
print("   • RediSearch index creation")
print("   • Vector similarity search")
print("   • Hybrid search (vector + filter)")
print("\n💡 Next Steps:")
print("   • Add LeanVec4x8 quantization (3x memory reduction)")
print("   • Switch to HNSW index (faster for large datasets)")
print("   • Sync all 464K drugs from Aurora")
print("   • Integrate Claude for query preprocessing")

print("\n✅ DAW Drug Search PoC - SUCCESS!")


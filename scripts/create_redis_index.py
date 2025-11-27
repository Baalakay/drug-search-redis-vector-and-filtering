#!/usr/bin/env python3
"""
Create Redis Search Index for DAW Drug Search

This script creates the production Redis index with:
- Vector field with LeanVec4x8 quantization
- Full-text search fields
- Filter fields (tags, numeric)
- HNSW algorithm for fast vector search

Usage:
    python3 scripts/create_redis_index.py --host 10.0.11.245 --port 6379
    
Options:
    --host: Redis host (default: 10.0.11.245)
    --port: Redis port (default: 6379)
    --drop: Drop existing index before creating
    --quantization: Enable LeanVec4x8 quantization (default: True)
"""

import argparse
import redis
from redis.commands.search.field import TextField, NumericField, TagField, VectorField
from redis.commands.search.index_definition import IndexDefinition, IndexType

# Index configuration
INDEX_NAME = "idx:drugs"
KEY_PREFIX = "drug:"

def create_index(
    redis_client: redis.Redis,
    drop_existing: bool = False,
    enable_quantization: bool = True
):
    """Create the Redis search index with vector support.
    
    Args:
        redis_client: Redis client connection
        drop_existing: Whether to drop existing index
        enable_quantization: Whether to enable LeanVec4x8 quantization
    """
    
    print(f"🔴 Creating Redis Search Index: {INDEX_NAME}")
    print(f"   Host: {redis_client.connection_pool.connection_kwargs['host']}")
    print(f"   Port: {redis_client.connection_pool.connection_kwargs['port']}")
    print(f"   Quantization: {'ENABLED (LeanVec4x8)' if enable_quantization else 'DISABLED'}")
    print()
    
    # Drop existing index if requested
    if drop_existing:
        try:
            redis_client.ft(INDEX_NAME).dropindex(delete_documents=False)
            print("   🗑️  Dropped existing index (documents preserved)")
        except Exception as e:
            print(f"   ℹ️  No existing index to drop")
    
    # Define index schema
    print("   📋 Defining schema...")
    
    # Vector field configuration
    vector_params = {
        "TYPE": "FLOAT32",
        "DIM": 1024,
        "DISTANCE_METRIC": "COSINE",
        "INITIAL_CAP": 500000,  # Pre-allocate for 500K drugs
        "M": 40,  # HNSW: connections per layer
        "EF_CONSTRUCTION": 200,  # HNSW: construction quality
        "EF_RUNTIME": 10,  # HNSW: search quality (overridable at query time)
    }
    
    # Add quantization if enabled
    if enable_quantization:
        vector_params["QUANTIZATION"] = {
            "TYPE": "LEANVEC4X8",
            "DIMENSION_REDUCTION": 256  # Reduce 1024 → 256 dims
        }
        print("      • Vector quantization: LeanVec4x8 (1024 → 256 dims)")
    else:
        print("      • Vector quantization: DISABLED (full 1024 dims)")
    
    # Create schema
    schema = (
        # Full-text search fields (weighted)
        TextField("$.drug_name", as_name="drug_name", weight=2.0),
        TextField("$.brand_name", as_name="brand_name", weight=1.5),
        TextField("$.generic_name", as_name="generic_name", weight=1.5),
        
        # Numeric filter (for GCN range queries)
        NumericField("$.gcn_seqno", as_name="gcn_seqno"),
        
        # Tag filters (exact match, fast)
        TagField("$.dosage_form", as_name="dosage_form"),
        TagField("$.manufacturer", as_name="manufacturer"),
        TagField("$.is_generic", as_name="is_generic"),
        TagField("$.is_brand", as_name="is_brand"),
        TagField("$.dea_schedule", as_name="dea_schedule"),
        TagField("$.drug_class", as_name="drug_class"),
        TagField("$.therapeutic_class", as_name="therapeutic_class"),
        
        # Vector field with HNSW
        VectorField(
            "$.embedding",
            "HNSW",
            vector_params,
            as_name="embedding"
        )
    )
    
    print("      • Full-text fields: drug_name, brand_name, generic_name")
    print("      • Numeric fields: gcn_seqno")
    print("      • Tag fields: dosage_form, manufacturer, is_generic, is_brand, dea_schedule, drug_class, therapeutic_class")
    print("      • Vector field: embedding (1024-dim HNSW)")
    
    # Create index definition
    definition = IndexDefinition(
        prefix=[KEY_PREFIX],
        index_type=IndexType.JSON,
        language="english",  # For stemming in full-text search
        score=1.0,
        score_field="__score"
    )
    
    # Create the index
    print(f"\n   🔨 Creating index...")
    try:
        redis_client.ft(INDEX_NAME).create_index(
            schema,
            definition=definition
        )
        print(f"   ✅ Index '{INDEX_NAME}' created successfully!")
    except Exception as e:
        print(f"   ❌ Failed to create index: {e}")
        raise
    
    # Get index info
    print(f"\n   📊 Index Information:")
    try:
        info = redis_client.ft(INDEX_NAME).info()
        print(f"      • Index name: {INDEX_NAME}")
        print(f"      • Documents: {info.get('num_docs', 0)}")
        print(f"      • Key prefix: {KEY_PREFIX}")
        print(f"      • Index type: JSON")
        print(f"      • Language: english")
    except Exception as e:
        print(f"      ⚠️  Could not retrieve index info: {e}")
    
    print(f"\n✅ Redis index creation complete!")
    print(f"\n💡 Next steps:")
    print(f"   1. Run data sync pipeline to load drugs")
    print(f"   2. Test queries with vector search")
    print(f"   3. Tune HNSW parameters if needed")


def verify_index(redis_client: redis.Redis):
    """Verify the index was created correctly.
    
    Args:
        redis_client: Redis client connection
    """
    print(f"\n🔍 Verifying index '{INDEX_NAME}'...")
    
    try:
        info = redis_client.ft(INDEX_NAME).info()
        
        print(f"   ✅ Index exists and is accessible")
        print(f"   📊 Statistics:")
        print(f"      • Documents indexed: {info.get('num_docs', 0)}")
        print(f"      • Number of fields: {info.get('num_records', 0)}")
        print(f"      • Index size (MB): {info.get('inverted_sz_mb', 0):.2f}")
        
        # Check if vector field exists
        fields = info.get('attributes', [])
        vector_field = next((f for f in fields if f.get('identifier') == 'embedding'), None)
        
        if vector_field:
            print(f"      • Vector field: FOUND")
            print(f"      • Vector algorithm: {vector_field.get('type', 'UNKNOWN')}")
        else:
            print(f"      ⚠️  Vector field: NOT FOUND")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Index verification failed: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Create Redis search index for DAW drug search"
    )
    parser.add_argument(
        "--host",
        default="10.0.11.245",
        help="Redis host (default: 10.0.11.245)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6379,
        help="Redis port (default: 6379)"
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop existing index before creating"
    )
    parser.add_argument(
        "--no-quantization",
        action="store_true",
        help="Disable LeanVec4x8 quantization (use full vectors)"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing index, don't create"
    )
    
    args = parser.parse_args()
    
    # Connect to Redis
    print(f"🔗 Connecting to Redis at {args.host}:{args.port}...")
    try:
        r = redis.Redis(
            host=args.host,
            port=args.port,
            decode_responses=False,
            socket_connect_timeout=5
        )
        r.ping()
        print(f"   ✅ Connected successfully\n")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return 1
    
    # Verify only mode
    if args.verify_only:
        success = verify_index(r)
        return 0 if success else 1
    
    # Create index
    try:
        create_index(
            r,
            drop_existing=args.drop,
            enable_quantization=not args.no_quantization
        )
        
        # Verify it was created
        verify_index(r)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())


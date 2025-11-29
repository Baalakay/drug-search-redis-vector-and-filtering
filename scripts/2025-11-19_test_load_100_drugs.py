#!/usr/bin/env python3
"""
Phase 3-4: Test Load 100 Drugs to Redis
Includes CRESTOR, rosuvastatin, and diverse drug classes for testing Option B alternatives

Usage:
    python3 2025-11-19_test_load_100_drugs.py [--verify-only] [--clear-test]
    
Options:
    --verify-only: Only verify existing test data, don't load
    --clear-test: Clear test data before loading
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime
from typing import List, Dict, Any

# Add packages to path
sys.path.insert(0, '/workspaces/DAW/packages/core/src')

import boto3
import mysql.connector
import redis
import numpy as np

# AWS clients
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

# Configuration
TEST_KEY_PREFIX = 'drug_test:'  # Use separate namespace for testing
TEST_INDEX_NAME = 'drugs_test_idx'

# Add packages to path
sys.path.insert(0, '/workspaces/DAW/packages/core/src')
from config.secrets import get_db_credentials, get_redis_config

def connect_to_aurora():
    """Connect to Aurora MySQL using secrets utility"""
    print("🔗 Connecting to Aurora...")
    db_creds = get_db_credentials()
    return mysql.connector.connect(**db_creds)

def connect_to_redis():
    """Connect to Redis using secrets utility"""
    print("🔗 Connecting to Redis...")
    redis_config = get_redis_config()
    return redis.Redis(
        host=redis_config['host'],
        port=redis_config['port'],
        password=redis_config['password'],
        decode_responses=False  # Binary data for embeddings
    )

def generate_embedding(text: str) -> List[float]:
    """Generate embedding using Bedrock Titan"""
    body = json.dumps({
        "inputText": text,
        "dimensions": 1024,
        "normalize": True
    })
    
    response = bedrock_client.invoke_model(
        modelId='amazon.titan-embed-text-v2:0',
        body=body
    )
    
    result = json.loads(response['body'].read())
    return result['embedding']

def fetch_test_drugs(conn) -> List[Dict[str, Any]]:
    """
    Fetch 100 test drugs including:
    - All CRESTOR variants (5-10 drugs)
    - All rosuvastatin generics (10-15 drugs)  
    - Sample of other statins (LIPITOR, etc)
    - Sample of other drug classes (lisinopril, metformin, etc)
    """
    cursor = conn.cursor(dictionary=True)
    
    print("\n📋 Fetching test dataset...")
    
    # Main query with all required fields for Option B
    base_query = """
    SELECT 
        -- Core identification
        n.NDC as ndc,
        UPPER(TRIM(n.LN)) as drug_name,
        UPPER(TRIM(COALESCE(n.BN, ''))) as brand_name,
        LOWER(TRIM(REGEXP_REPLACE(n.LN, ' [0-9].*', ''))) as generic_name,
        CAST(COALESCE(n.GCN_SEQNO, 0) AS UNSIGNED) as gcn_seqno,
        
        -- Dosage & form
        TRIM(COALESCE(n.DF, '')) as dosage_form,
        COALESCE(g.GCRT, '') as route,
        COALESCE(g.STR, COALESCE(g.STR60, '')) as strength,
        
        -- Status flags
        CASE WHEN n.INNOV = '1' THEN 'true' ELSE 'false' END as is_brand,
        CASE WHEN n.INNOV = '0' THEN 'true' ELSE 'false' END as is_generic,
        CASE WHEN n.DEA IN ('1','2','3','4','5') THEN n.DEA ELSE '' END as dea_schedule,
        'true' as is_active,
        
        -- Classification (CRITICAL for Option B alternatives)
        COALESCE(TRIM(hc.GNN), '') as drug_class,  -- Ingredient name (e.g., "rosuvastatin calcium")
        COALESCE(TRIM(tc.ETC_NAME), '') as therapeutic_class,  -- e.g., "Antihyperlipidemic - HMG CoA Reductase Inhibitors (statins)"
        
        -- Manufacturer/Labeler
        TRIM(COALESCE(n.LBLRID, '')) as labeler_id,
        TRIM(COALESCE(lbl.MFG, '')) as manufacturer_name
        
    FROM rndc14 n
    LEFT JOIN rgcnseq4 g ON n.GCN_SEQNO = g.GCN_SEQNO
    LEFT JOIN rhiclsq1 hc ON g.HICL_SEQNO = hc.HICL_SEQNO
    LEFT JOIN retcgc0 tclink ON g.GCN_SEQNO = tclink.GCN_SEQNO AND tclink.ETC_DEFAULT_USE_IND = '1'
    LEFT JOIN retctbl0 tc ON tclink.ETC_ID = tc.ETC_ID
    LEFT JOIN rlblrid3 lbl ON n.LBLRID = lbl.LBLRID
    WHERE n.LN IS NOT NULL
        AND LENGTH(TRIM(n.LN)) > 3
        AND n.NDC IS NOT NULL
        AND n.OBSDTEC = '0000-00-00'  -- ACTIVE DRUGS ONLY
        AND {condition}
    ORDER BY n.NDC
    LIMIT {limit}
    """
    
    drugs = []
    
    # 1. Get CRESTOR variants
    print("   Fetching CRESTOR variants...")
    query1 = base_query.format(condition="UPPER(n.BN) = 'CRESTOR'", limit=10)
    cursor.execute(query1)
    crestor_drugs = cursor.fetchall()
    drugs.extend(crestor_drugs)
    print(f"   ✓ Found {len(crestor_drugs)} CRESTOR variants")
    
    if crestor_drugs:
        crestor_gcn = crestor_drugs[0]['gcn_seqno']
        print(f"   📌 CRESTOR GCN: {crestor_gcn}")
        
        # 2. Get rosuvastatin generics (same GCN)
        print("   Fetching rosuvastatin generics (same GCN)...")
        query2 = base_query.format(
            condition=f"n.GCN_SEQNO = {crestor_gcn} AND n.INNOV = '0'",
            limit=15
        )
        cursor.execute(query2)
        rosuva_generics = cursor.fetchall()
        drugs.extend(rosuva_generics)
        print(f"   ✓ Found {len(rosuva_generics)} rosuvastatin generics")
    
    # 3. Get other statins (same drug_class, different GCN)
    print("   Fetching other statins...")
    query3 = base_query.format(
        condition="UPPER(n.LN) LIKE '%ATORVASTATIN%' OR UPPER(n.LN) LIKE '%SIMVASTATIN%' OR UPPER(n.LN) LIKE '%PRAVASTATIN%'",
        limit=20
    )
    cursor.execute(query3)
    other_statins = cursor.fetchall()
    drugs.extend(other_statins)
    print(f"   ✓ Found {len(other_statins)} other statins")
    
    # 4. Get LIPITOR (brand competitor)
    print("   Fetching LIPITOR...")
    query4 = base_query.format(condition="UPPER(n.BN) = 'LIPITOR'", limit=5)
    cursor.execute(query4)
    lipitor = cursor.fetchall()
    drugs.extend(lipitor)
    print(f"   ✓ Found {len(lipitor)} LIPITOR variants")
    
    # 5. Get diverse drug classes for comprehensive testing
    print("   Fetching diverse drug classes...")
    query5 = base_query.format(
        condition="""(
            UPPER(n.LN) LIKE '%LISINOPRIL%' OR
            UPPER(n.LN) LIKE '%METFORMIN%' OR
            UPPER(n.LN) LIKE '%AMLODIPINE%' OR
            UPPER(n.LN) LIKE '%OMEPRAZOLE%' OR
            UPPER(n.LN) LIKE '%LEVOTHYROXINE%'
        )""",
        limit=30
    )
    cursor.execute(query5)
    diverse_drugs = cursor.fetchall()
    drugs.extend(diverse_drugs)
    print(f"   ✓ Found {len(diverse_drugs)} drugs from diverse classes")
    
    # Fill remaining slots with random active drugs
    remaining = 100 - len(drugs)
    if remaining > 0:
        print(f"   Fetching {remaining} random drugs to reach 100...")
        query6 = base_query.format(condition="1=1", limit=remaining)
        cursor.execute(query6)
        random_drugs = cursor.fetchall()
        drugs.extend(random_drugs)
        print(f"   ✓ Found {len(random_drugs)} random drugs")
    
    cursor.close()
    
    print(f"\n✅ Total drugs fetched: {len(drugs)}")
    return drugs[:100]  # Ensure exactly 100

def fetch_indications(conn, ndcs: List[str]) -> Dict[str, str]:
    """Fetch indications for NDCs (separate query due to GROUP_CONCAT)"""
    # NOTE: The FDB schema doesn't have rdlim14/rdindc tables as expected
    # Skipping indication fetching for now - can be added later if needed
    print("\n💊 Skipping indications (tables not available in current FDB schema)")
    
    # Return empty dict - indications are optional for search functionality
    indications = {}
    
    print(f"   ℹ️  Returning empty indications (not critical for search)")
    return indications

def load_drugs_to_redis(redis_client, drugs: List[Dict], indications: Dict[str, str]):
    """Load drugs to Redis with test key prefix"""
    print("\n💾 Loading drugs to Redis...")
    
    success_count = 0
    fail_count = 0
    
    for i, drug in enumerate(drugs, 1):
        ndc = drug['ndc']
        
        # Add indication if available
        drug['indication'] = indications.get(ndc, '')
        
        # Generate embedding with semantic context for better vector search
        # Include: drug name + therapeutic class + drug class + indication
        embedding_parts = [drug['drug_name']]
        
        if drug.get('therapeutic_class'):
            embedding_parts.append(drug['therapeutic_class'])
        
        if drug.get('drug_class'):
            embedding_parts.append(drug['drug_class'])
        
        if drug.get('indication'):
            embedding_parts.append(drug['indication'])
        
        embedding_text = ' '.join(embedding_parts)
        
        try:
            # Generate embedding
            embedding = generate_embedding(embedding_text)
            
            # Convert to binary (4 bytes per float)
            embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
            
            # Store as HASH
            key = f"{TEST_KEY_PREFIX}{ndc}"
            
            # Prepare fields (exclude embedding for HSET, add separately)
            fields = {k: str(v) if v is not None else '' for k, v in drug.items()}
            fields['embedding_text'] = embedding_text  # Store what we embedded
            fields['indexed_at'] = datetime.utcnow().isoformat() + 'Z'
            
            # Store drug data
            redis_client.hset(key, mapping=fields)
            
            # Store embedding separately (binary data)
            redis_client.hset(key, 'embedding', embedding_bytes)
            
            success_count += 1
            
            if i % 10 == 0:
                print(f"   [{i}/100] Loaded {success_count} drugs...")
                
        except Exception as e:
            print(f"   ⚠️  Failed to load {ndc}: {e}")
            fail_count += 1
    
    print(f"\n✅ Loaded {success_count} drugs, {fail_count} failed")
    return success_count, fail_count

def verify_test_data(redis_client):
    """Verify test data was loaded correctly"""
    print("\n🔍 Verifying test data...")
    
    # Get all test keys
    test_keys = redis_client.keys(f"{TEST_KEY_PREFIX}*")
    print(f"   Total test keys: {len(test_keys)}")
    
    if len(test_keys) == 0:
        print("   ❌ No test data found!")
        return False
    
    # Sample 5 random drugs and verify fields
    import random
    sample_keys = random.sample(test_keys, min(5, len(test_keys)))
    
    print("\n   Sample verification:")
    for key in sample_keys:
        ndc = key.decode('utf-8').replace(TEST_KEY_PREFIX, '')
        
        # Get all fields
        drug = redis_client.hgetall(key)
        
        print(f"\n   NDC: {ndc}")
        print(f"      drug_name: {drug.get(b'drug_name', b'').decode('utf-8')[:50]}")
        print(f"      brand_name: {drug.get(b'brand_name', b'').decode('utf-8')[:30]}")
        print(f"      gcn_seqno: {drug.get(b'gcn_seqno', b'').decode('utf-8')}")
        print(f"      drug_class: {drug.get(b'drug_class', b'').decode('utf-8')[:50]}")
        print(f"      is_generic: {drug.get(b'is_generic', b'').decode('utf-8')}")
        print(f"      is_active: {drug.get(b'is_active', b'').decode('utf-8')}")
        
        # Check embedding
        embedding_bytes = drug.get(b'embedding')
        if embedding_bytes:
            embedding_array = np.frombuffer(embedding_bytes, dtype=np.float32)
            print(f"      embedding: {len(embedding_array)} dimensions ✓")
        else:
            print(f"      embedding: MISSING ❌")
    
    print("\n✅ Verification complete")
    return True

def clear_test_data(redis_client):
    """Clear all test data"""
    print("\n🗑️  Clearing test data...")
    
    test_keys = redis_client.keys(f"{TEST_KEY_PREFIX}*")
    if test_keys:
        redis_client.delete(*test_keys)
        print(f"   ✓ Deleted {len(test_keys)} test keys")
    else:
        print("   No test data to clear")

def main():
    parser = argparse.ArgumentParser(description='Test load 100 drugs to Redis')
    parser.add_argument('--verify-only', action='store_true', help='Only verify, do not load')
    parser.add_argument('--clear-test', action='store_true', help='Clear test data before loading')
    args = parser.parse_args()
    
    print("="*80)
    print("TEST LOAD: 100 Drugs for Option B Alternatives Testing")
    print("="*80)
    
    # Connect to Redis
    redis_client = connect_to_redis()
    
    if args.clear_test:
        clear_test_data(redis_client)
    
    if args.verify_only:
        verify_test_data(redis_client)
        return
    
    # Connect to Aurora
    db_conn = connect_to_aurora()
    
    # Fetch drugs
    drugs = fetch_test_drugs(db_conn)
    
    # Fetch indications
    ndcs = [d['ndc'] for d in drugs]
    indications = fetch_indications(db_conn, ndcs)
    
    # Load to Redis
    success, failed = load_drugs_to_redis(redis_client, drugs, indications)
    
    # Verify
    verify_test_data(redis_client)
    
    # Summary
    print("\n" + "="*80)
    print("✅ TEST LOAD COMPLETE")
    print("="*80)
    print(f"\nDrugs loaded: {success}")
    print(f"Failures: {failed}")
    print(f"Redis key prefix: {TEST_KEY_PREFIX}")
    print(f"\nNext step: Run field-by-field verification on CRESTOR")
    
    db_conn.close()
    redis_client.close()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


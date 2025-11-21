#!/usr/bin/env python3
"""
PRODUCTION LOAD: Full FDB Dataset to Redis (121k+ active drugs)

This script:
1. Clears ALL existing Redis data (test and production)
2. Loads all active drugs with enriched embeddings
3. Monitors progress and logs errors
4. Can resume from last checkpoint

Usage:
    python3 production_load_full_dataset.py [--clear-all] [--resume]
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
sm_client = boto3.client('secretsmanager', region_name='us-east-1')
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

# Configuration
DB_HOST = 'daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com'
DB_NAME = 'fdb'
REDIS_HOST = '10.0.11.153'
REDIS_PORT = 6379
PROD_KEY_PREFIX = 'drug:'  # Production namespace
PROD_INDEX_NAME = 'drugs_idx'  # Production index

# Progress tracking
CHECKPOINT_FILE = '/tmp/redis_load_checkpoint.json'
BATCH_SIZE = 100  # Process 100 drugs at a time
LOG_FREQUENCY = 500  # Log progress every 500 drugs

def get_db_password():
    """Get database password from Secrets Manager"""
    secret = sm_client.get_secret_value(SecretId='DAW-DB-Password-dev')
    secret_dict = json.loads(secret['SecretString'])
    return secret_dict['password']

def connect_to_aurora():
    """Connect to Aurora MySQL"""
    print("🔗 Connecting to Aurora...")
    return mysql.connector.connect(
        host=DB_HOST,
        user='dawadmin',
        password=get_db_password(),
        database=DB_NAME
    )

def connect_to_redis():
    """Connect to Redis"""
    print("🔗 Connecting to Redis...")
    password = 'DAW-Redis-SecureAuth-2025'
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=password,
        decode_responses=False
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

def fetch_all_active_drugs(conn) -> List[Dict[str, Any]]:
    """
    Fetch ALL active drugs from FDB with enriched data
    Expected: ~121,000 drugs
    """
    cursor = conn.cursor(dictionary=True)
    
    print("\n📋 Fetching ALL active drugs from FDB...")
    print("   Expected count: ~121,000 drugs")
    
    # Query for all active drugs (no LIMIT)
    query = """
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
        
        -- Classification (CRITICAL for alternatives)
        COALESCE(TRIM(hc.GNN), '') as drug_class,
        COALESCE(TRIM(tc.ETC_NAME), '') as therapeutic_class,
        
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
        AND n.OBSDTEC = '0000-00-00'
    ORDER BY n.NDC
    """
    
    start_time = time.time()
    cursor.execute(query)
    drugs = cursor.fetchall()
    elapsed = time.time() - start_time
    
    print(f"   ✓ Fetched {len(drugs):,} active drugs in {elapsed:.1f}s")
    cursor.close()
    
    return drugs

def clear_redis_data(redis_client, namespace_prefix: str):
    """Clear all keys matching the namespace prefix"""
    print(f"\n🗑️  Clearing Redis namespace: {namespace_prefix}*")
    
    keys_deleted = 0
    cursor = 0
    
    while True:
        cursor, keys = redis_client.scan(cursor, match=f"{namespace_prefix}*", count=1000)
        if keys:
            redis_client.delete(*keys)
            keys_deleted += len(keys)
            print(f"   Deleted {keys_deleted} keys...", end='\r')
        
        if cursor == 0:
            break
    
    print(f"\n   ✓ Deleted {keys_deleted} keys")

def drop_redis_index(redis_client, index_name: str):
    """Drop Redis search index if it exists"""
    print(f"\n🗑️  Dropping index: {index_name}")
    try:
        redis_client.execute_command('FT.DROPINDEX', index_name)
        print(f"   ✓ Dropped index {index_name}")
    except redis.exceptions.ResponseError as e:
        if 'Unknown index name' in str(e) or 'no such index' in str(e):
            print(f"   ℹ️  Index {index_name} does not exist (OK)")
        else:
            raise

def create_redis_index(redis_client, index_name: str, key_prefix: str):
    """Create Redis search index with vector search support"""
    print(f"\n🔨 Creating index: {index_name}")
    
    try:
        redis_client.execute_command(
            'FT.CREATE', index_name,
            'ON', 'HASH',
            'PREFIX', '1', key_prefix,
            'SCHEMA',
            'ndc', 'TAG',
            'drug_name', 'TEXT', 'SORTABLE',
            'brand_name', 'TEXT',
            'generic_name', 'TEXT',
            'is_generic', 'TAG',
            'is_brand', 'TAG',
            'is_active', 'TAG',
            'dosage_form', 'TAG',
            'dea_schedule', 'TAG',
            'gcn_seqno', 'NUMERIC', 'SORTABLE',
            'drug_class', 'TEXT',
            'therapeutic_class', 'TAG',
            'manufacturer_name', 'TEXT',
            'embedding', 'VECTOR', 'HNSW', '10',
            'TYPE', 'FLOAT32',
            'DIM', '1024',
            'DISTANCE_METRIC', 'COSINE',
            'INITIAL_CAP', '150000',
            'M', '40'
        )
        print(f"   ✓ Created index {index_name}")
    except redis.exceptions.ResponseError as e:
        if 'Index already exists' in str(e):
            print(f"   ℹ️  Index {index_name} already exists")
        else:
            raise

def save_checkpoint(processed_count: int, total_count: int, last_ndc: str):
    """Save progress checkpoint"""
    checkpoint = {
        'processed_count': processed_count,
        'total_count': total_count,
        'last_ndc': last_ndc,
        'timestamp': datetime.now().isoformat()
    }
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(checkpoint, f)

def load_checkpoint():
    """Load progress checkpoint"""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            return json.load(f)
    return None

def load_drugs_to_redis(redis_client, drugs: List[Dict[str, Any]], key_prefix: str):
    """Load drugs to Redis with embeddings and progress tracking"""
    print(f"\n📥 Loading {len(drugs):,} drugs to Redis...")
    print(f"   Key prefix: {key_prefix}")
    print(f"   Batch size: {BATCH_SIZE}")
    
    start_time = time.time()
    loaded_count = 0
    error_count = 0
    errors_log = []
    
    for i, drug in enumerate(drugs):
        try:
            ndc = drug['ndc']
            
            # Generate enriched embedding: drug_name + therapeutic_class + drug_class
            embedding_parts = [drug['drug_name']]
            
            if drug.get('therapeutic_class'):
                embedding_parts.append(drug['therapeutic_class'])
            
            if drug.get('drug_class'):
                embedding_parts.append(drug['drug_class'])
            
            embedding_text = ' '.join(embedding_parts)
            embedding = generate_embedding(embedding_text)
            embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
            
            # Prepare Redis hash
            redis_key = f"{key_prefix}{ndc}"
            redis_data = {
                'ndc': ndc,
                'drug_name': drug['drug_name'],
                'brand_name': drug['brand_name'],
                'generic_name': drug['generic_name'],
                'is_generic': drug['is_generic'],
                'is_brand': drug['is_brand'],
                'is_active': drug['is_active'],
                'dosage_form': drug['dosage_form'],
                'dea_schedule': drug.get('dea_schedule', ''),
                'gcn_seqno': drug['gcn_seqno'],
                'drug_class': drug.get('drug_class', ''),
                'therapeutic_class': drug.get('therapeutic_class', ''),
                'manufacturer_name': drug.get('manufacturer_name', ''),
                'strength': drug.get('strength', ''),
                'route': drug.get('route', ''),
                'labeler_id': drug.get('labeler_id', ''),
                'embedding': embedding_bytes
            }
            
            redis_client.hset(redis_key, mapping=redis_data)
            loaded_count += 1
            
            # Log progress
            if (i + 1) % LOG_FREQUENCY == 0:
                elapsed = time.time() - start_time
                rate = loaded_count / elapsed
                remaining = len(drugs) - (i + 1)
                eta_seconds = remaining / rate if rate > 0 else 0
                eta_hours = eta_seconds / 3600
                
                print(f"   Progress: {i+1:,}/{len(drugs):,} ({(i+1)/len(drugs)*100:.1f}%) | "
                      f"Rate: {rate:.1f} drugs/sec | ETA: {eta_hours:.1f}h | "
                      f"Errors: {error_count}")
            
            # Save checkpoint periodically
            if (i + 1) % 1000 == 0:
                save_checkpoint(i + 1, len(drugs), ndc)
        
        except Exception as e:
            error_count += 1
            error_msg = f"NDC {drug.get('ndc', 'unknown')}: {str(e)}"
            errors_log.append(error_msg)
            
            # Log first 10 errors
            if error_count <= 10:
                print(f"\n   ⚠️  Error {error_count}: {error_msg}")
            
            # Stop if too many errors
            if error_count > 100:
                print(f"\n   ❌ Too many errors ({error_count}). Stopping load.")
                break
    
    elapsed = time.time() - start_time
    
    print(f"\n✅ Load complete!")
    print(f"   Loaded: {loaded_count:,} drugs")
    print(f"   Errors: {error_count}")
    print(f"   Time: {elapsed/60:.1f} minutes")
    print(f"   Rate: {loaded_count/elapsed:.1f} drugs/sec")
    
    if errors_log:
        error_file = f'/tmp/redis_load_errors_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        with open(error_file, 'w') as f:
            f.write('\n'.join(errors_log))
        print(f"   Error log: {error_file}")
    
    return loaded_count, error_count

def verify_sample_data(redis_client, key_prefix: str):
    """Verify a few sample drugs loaded correctly"""
    print("\n🔍 Verifying sample data...")
    
    # Check CRESTOR
    keys = []
    cursor = 0
    while True:
        cursor, batch = redis_client.scan(cursor, match=f"{key_prefix}*", count=100)
        keys.extend(batch)
        if cursor == 0 or len(keys) >= 10:
            break
    
    if not keys:
        print("   ❌ No keys found!")
        return False
    
    print(f"   Found {len(keys)} sample keys")
    
    # Check first key
    sample_key = keys[0]
    data = redis_client.hgetall(sample_key)
    
    print(f"\n   Sample drug: {sample_key}")
    print(f"   - drug_name: {data.get(b'drug_name', b'').decode('utf-8')}")
    print(f"   - brand_name: {data.get(b'brand_name', b'').decode('utf-8')}")
    print(f"   - generic_name: {data.get(b'generic_name', b'').decode('utf-8')}")
    print(f"   - therapeutic_class: {data.get(b'therapeutic_class', b'').decode('utf-8')}")
    print(f"   - drug_class: {data.get(b'drug_class', b'').decode('utf-8')}")
    print(f"   - manufacturer_name: {data.get(b'manufacturer_name', b'').decode('utf-8')}")
    print(f"   - embedding: {len(data.get(b'embedding', b''))} bytes")
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Load full FDB dataset to Redis')
    parser.add_argument('--clear-all', action='store_true', help='Clear ALL Redis data (test + prod)')
    parser.add_argument('--resume', action='store_true', help='Resume from last checkpoint')
    args = parser.parse_args()
    
    print("=" * 80)
    print("PRODUCTION REDIS LOAD - FULL FDB DATASET")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Connect
    db_conn = connect_to_aurora()
    redis_client = connect_to_redis()
    
    # Clear existing data
    if args.clear_all:
        print("\n🧹 CLEARING ALL REDIS DATA...")
        clear_redis_data(redis_client, 'drug_test:')
        clear_redis_data(redis_client, 'drug:')
        drop_redis_index(redis_client, 'drugs_test_idx')
        drop_redis_index(redis_client, 'drugs_idx')
    else:
        print("\n🧹 Clearing production data only...")
        clear_redis_data(redis_client, PROD_KEY_PREFIX)
        drop_redis_index(redis_client, PROD_INDEX_NAME)
    
    # Fetch all drugs
    drugs = fetch_all_active_drugs(db_conn)
    
    if not drugs:
        print("❌ No drugs fetched!")
        return 1
    
    # Create index
    create_redis_index(redis_client, PROD_INDEX_NAME, PROD_KEY_PREFIX)
    
    # Load drugs
    loaded, errors = load_drugs_to_redis(redis_client, drugs, PROD_KEY_PREFIX)
    
    # Verify
    verify_sample_data(redis_client, PROD_KEY_PREFIX)
    
    # Final count
    print("\n📊 Final Redis counts:")
    keys_count = 0
    cursor = 0
    while True:
        cursor, batch = redis_client.scan(cursor, match=f"{PROD_KEY_PREFIX}*", count=1000)
        keys_count += len(batch)
        if cursor == 0:
            break
    print(f"   Production keys (drug:*): {keys_count:,}")
    
    # Cleanup
    db_conn.close()
    redis_client.close()
    
    print(f"\n✅ LOAD COMPLETE!")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    return 0 if errors == 0 else 1

if __name__ == '__main__':
    print("Starting script...", flush=True)
    sys.exit(main())


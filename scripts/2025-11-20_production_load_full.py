#!/usr/bin/env python3
"""
Production Full Load with Optimized Schema

Features:
- dosage_form as TAG (normalized: CREAM, GEL, TABLET)
- drug_class as TEXT (ROSUVASTATIN_CALCIUM format for production compatibility)
- therapeutic_class as TAG
- indication stored separately by drug family (Option A - 80%+ memory savings)
- Joins rdosed2 for human-readable dosage forms
- Joins indication tables for complete medical data
- Only loads active drugs (OBSDTEC = '0000-00-00')

Usage:
    python3 2025-11-20_production_load_full.py
"""

import os
import sys
import json
import time
import re
from datetime import datetime
from typing import List, Dict, Any, Set

# Add packages to path
sys.path.insert(0, '/workspaces/DAW/packages/core/src')

import boto3
import mysql.connector
import redis
import numpy as np
from config.secrets import get_db_credentials, get_redis_config

# AWS clients
bedrock_client = boto3.client('bedrock-runtime', region_name='us-east-1')

# Configuration
PROD_KEY_PREFIX = 'drug:'  # Production prefix
PROD_INDEX_NAME = 'drugs_idx'  # Production index
BATCH_SIZE = 1000  # Process in batches for progress reporting

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
        decode_responses=False
    )

def normalize_dosage_form(raw_form: str) -> str:
    """
    Normalize dosage form from FDB format to TAG format
    
    Examples:
        "CREAM (GRAM)" → "CREAM"
        "GEL (ML)" → "GEL"
        "GEL PACKET" → "GEL"
        "TABLET, EXTENDED RELEASE" → "TABLET"
    """
    if not raw_form:
        return ''
    
    # Extract base form (before parentheses or comma)
    base = raw_form.split('(')[0].split(',')[0].strip().upper()
    
    # Extract first word (handles "GEL PACKET" → "GEL", "CREAM PACK" → "CREAM")
    first_word = base.split()[0] if base else ''
    
    return first_word

def normalize_drug_class(raw_class: str) -> str:
    """
    Normalize drug_class for TEXT field (production compatibility)
    
    Examples:
        "rosuvastatin calcium" → "ROSUVASTATIN_CALCIUM"
        "testosterone" → "TESTOSTERONE"
    """
    if not raw_class:
        return ''
    
    return raw_class.strip().upper().replace(' ', '_').replace('-', '_')

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

def fetch_all_drugs(conn) -> List[Dict[str, Any]]:
    """
    Fetch all active drugs from FDB
    """
    cursor = conn.cursor(dictionary=True)
    
    print("\n📋 Fetching all active drugs...")
    
    # Production query - NO LIMIT, all active drugs
    query = """
    SELECT 
        -- Core identification
        n.NDC,
        TRIM(n.LN) as drug_name,
        TRIM(COALESCE(n.BN, '')) as brand_name,
        TRIM(COALESCE(hc.GNN, '')) as generic_name,
        CAST(COALESCE(n.GCN_SEQNO, 0) AS UNSIGNED) as gcn_seqno,
        
        -- Dosage & form (Join rdosed2 for human-readable forms)
        COALESCE(TRIM(df.DOSE), TRIM(g.GCDF), '') as dosage_form_raw,
        TRIM(COALESCE(g.GCRT, '')) as route,
        TRIM(COALESCE(g.STR, COALESCE(g.STR60, ''))) as strength,
        
        -- Classification
        TRIM(COALESCE(hc.GNN, '')) as drug_class,
        TRIM(COALESCE(tc.ETC_NAME, '')) as therapeutic_class,
        
        -- Manufacturer
        TRIM(COALESCE(lblr.MFG, '')) as manufacturer_name,
        
        -- Generic/Brand status (INNOV field)
        CASE 
            WHEN n.INNOV = '0' THEN 'true'
            WHEN n.INNOV = '1' THEN 'false'
            ELSE 'unknown'
        END as is_generic,
        
        -- DEA Schedule
        TRIM(COALESCE(n.DEA, '')) as dea_schedule,
        
        -- Active status
        CASE 
            WHEN n.OBSDTEC = '0000-00-00' THEN 'true'
            ELSE 'false'
        END as is_active
        
    FROM rndc14 n
    LEFT JOIN rgcnseq4 g ON n.GCN_SEQNO = g.GCN_SEQNO
    LEFT JOIN rhiclsq1 hc ON g.HICL_SEQNO = hc.HICL_SEQNO
    LEFT JOIN retcgc0 tclink ON g.GCN_SEQNO = tclink.GCN_SEQNO AND tclink.ETC_DEFAULT_USE_IND = '1'
    LEFT JOIN retctbl0 tc ON tclink.ETC_ID = tc.ETC_ID
    LEFT JOIN rlblrid3 lblr ON n.LBLRID = lblr.LBLRID
    LEFT JOIN rdosed2 df ON g.GCDF = df.GCDF
    WHERE n.OBSDTEC = '0000-00-00'  -- Active drugs only
    ORDER BY n.NDC
    """
    
    cursor.execute(query)
    drugs = cursor.fetchall()
    cursor.close()
    
    print(f"   ✅ Fetched {len(drugs)} active drugs")
    return drugs

def fetch_indications_for_gcns(conn, gcns: List[int]) -> Dict[int, str]:
    """
    Fetch indications for given GCNs
    
    Returns: {gcn_seqno: "indication1 | indication2 | ..."}
    """
    if not gcns:
        return {}
    
    cursor = conn.cursor(dictionary=True)
    
    print(f"\n💊 Fetching indications for {len(gcns)} unique GCNs...")
    
    # Join indication tables: rindmgc0 → rindmma2 → rfmldx0
    # Batch the query to avoid hitting MySQL packet limits
    indication_map = {}
    batch_size = 5000
    
    for i in range(0, len(gcns), batch_size):
        batch = gcns[i:i + batch_size]
        query = """
        SELECT 
            ig.GCN_SEQNO,
            GROUP_CONCAT(DISTINCT d.DXID_DESC100 ORDER BY d.DXID_DESC100 SEPARATOR ' | ') as indication
        FROM rindmgc0 ig
        JOIN rindmma2 im ON ig.INDCTS = im.INDCTS
        JOIN rfmldx0 d ON im.DXID = d.DXID
        WHERE ig.GCN_SEQNO IN ({})
        GROUP BY ig.GCN_SEQNO
        """.format(','.join(str(gcn) for gcn in batch))
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        for row in results:
            indication_map[row['GCN_SEQNO']] = row['indication']
        
        print(f"   Processed {min(i + batch_size, len(gcns))}/{len(gcns)} GCNs...")
    
    cursor.close()
    
    print(f"   ✅ Found indications for {len(indication_map)} GCNs")
    return indication_map

def clear_production_data(redis_client):
    """Clear existing production data"""
    print("\n🗑️  Clearing old production data...")
    
    # Delete production drug keys
    cursor = 0
    deleted_count = 0
    while True:
        cursor, keys = redis_client.scan(cursor, match=f'{PROD_KEY_PREFIX}*', count=1000)
        if keys:
            redis_client.delete(*keys)
            deleted_count += len(keys)
            print(f"   Deleted {deleted_count} keys...")
        if cursor == 0:
            break
    
    print(f"   ✅ Deleted {deleted_count} old drug keys")
    
    # Delete indication keys
    cursor = 0
    deleted_count = 0
    while True:
        cursor, keys = redis_client.scan(cursor, match='indication:*', count=1000)
        if keys:
            redis_client.delete(*keys)
            deleted_count += len(keys)
            print(f"   Deleted {deleted_count} indication keys...")
        if cursor == 0:
            break
    
    print(f"   ✅ Deleted {deleted_count} old indication keys")
    
    # Drop existing index
    try:
        redis_client.execute_command('FT.DROPINDEX', PROD_INDEX_NAME)
        print(f"   ✅ Dropped existing index: {PROD_INDEX_NAME}")
    except Exception as e:
        if 'Unknown index name' in str(e) or 'no such index' in str(e).lower():
            print(f"   ℹ️  Index {PROD_INDEX_NAME} does not exist, skipping drop")
        else:
            print(f"   ⚠️  Error dropping index: {e}")

def create_production_index(redis_client):
    """Create production Redis Search index with optimized schema"""
    print(f"\n🏗️  Creating production index: {PROD_INDEX_NAME}...")
    
    try:
        # Create index with production schema (drug_class as TEXT to match existing production data)
        redis_client.execute_command(
            'FT.CREATE', PROD_INDEX_NAME,
            'ON', 'HASH',
            'PREFIX', '1', PROD_KEY_PREFIX,
            'SCHEMA',
            'ndc', 'TAG', 'SEPARATOR', ',', 'SORTABLE',
            'drug_name', 'TEXT', 'WEIGHT', '2',
            'brand_name', 'TEXT', 'WEIGHT', '1.5',
            'generic_name', 'TEXT', 'WEIGHT', '1',
            'drug_class', 'TEXT',  # TEXT for production compatibility
            'therapeutic_class', 'TAG', 'SEPARATOR', ',',
            'dosage_form', 'TAG', 'SEPARATOR', ',',
            'is_generic', 'TAG', 'SEPARATOR', ',',
            'is_active', 'TAG', 'SEPARATOR', ',',
            'dea_schedule', 'TAG', 'SEPARATOR', ',',
            'gcn_seqno', 'NUMERIC', 'SORTABLE',
            'manufacturer_name', 'TEXT', 'WEIGHT', '1',
            'embedding', 'VECTOR', 'HNSW', '6',
                'TYPE', 'FLOAT32',
                'DIM', '1024',
                'DISTANCE_METRIC', 'COSINE',
            'indication_key', 'TAG', 'SEPARATOR', ','
        )
        print(f"   ✅ Index created successfully")
    except Exception as e:
        print(f"   ❌ Error creating index: {e}")
        raise

def build_indication_key(drug: Dict[str, Any]) -> str:
    """
    Build indication key based on drug family
    Option A: Store indications once per drug family (brand or generic class)
    """
    brand_name = drug.get('brand_name', '').strip().upper()
    drug_class = drug.get('drug_class', '').strip().upper()
    
    if brand_name:
        return f"brand:{brand_name}"
    elif drug_class:
        return f"generic:{drug_class}"
    else:
        return f"gcn:{drug.get('gcn_seqno', 0)}"

def store_indications_by_family(redis_client, drugs: List[Dict[str, Any]], indication_map: Dict[int, str]):
    """
    Store indications separately by drug family (Option A)
    """
    print("\n💾 Storing indications by drug family...")
    
    family_indications: Dict[str, str] = {}
    
    # Group indications by family
    for drug in drugs:
        gcn = drug.get('gcn_seqno', 0)
        if gcn not in indication_map:
            continue
        
        indication = indication_map[gcn]
        family_key = build_indication_key(drug)
        
        # Use first indication found for this family (they should all be the same)
        if family_key not in family_indications:
            family_indications[family_key] = indication
    
    # Store in Redis
    for family_key, indication in family_indications.items():
        redis_key = f"indication:{family_key}"
        redis_client.set(redis_key, indication)
    
    print(f"   ✅ Stored {len(family_indications)} unique family indications")
    print(f"   💾 Memory savings: ~{len(drugs) - len(family_indications)} redundant entries avoided")

def load_drugs_to_redis(redis_client, drugs: List[Dict[str, Any]], indication_map: Dict[int, str]):
    """Load drugs into Redis with embeddings"""
    print(f"\n🚀 Loading {len(drugs)} drugs to Redis...")
    
    start_time = time.time()
    loaded_count = 0
    error_count = 0
    last_report_time = start_time
    
    for drug in drugs:
        try:
            # Generate embedding with semantic context
            embedding_parts = [drug['drug_name']]
            
            if drug.get('therapeutic_class'):
                embedding_parts.append(drug['therapeutic_class'])
            
            if drug.get('drug_class'):
                embedding_parts.append(drug['drug_class'])
            
            # Note: Not including indication in embedding as it's stored separately
            embedding_text = ' '.join(embedding_parts)
            embedding = generate_embedding(embedding_text)
            embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
            
            # Prepare Redis hash
            drug_key = f"{PROD_KEY_PREFIX}{drug['NDC']}"
            
            # Normalize fields
            dosage_form = normalize_dosage_form(drug.get('dosage_form_raw', ''))
            drug_class_normalized = normalize_drug_class(drug.get('drug_class', ''))
            
            # Build indication key
            indication_key = build_indication_key(drug)
            
            # Store in Redis
            redis_client.hset(drug_key, mapping={
                'ndc': drug['NDC'],
                'drug_name': drug['drug_name'],
                'brand_name': drug.get('brand_name', ''),
                'generic_name': drug.get('generic_name', ''),
                'drug_class': drug_class_normalized,
                'therapeutic_class': drug.get('therapeutic_class', ''),
                'dosage_form': dosage_form,
                'strength': drug.get('strength', ''),
                'manufacturer_name': drug.get('manufacturer_name', ''),
                'is_generic': drug.get('is_generic', 'unknown'),
                'is_active': drug.get('is_active', 'true'),
                'dea_schedule': drug.get('dea_schedule', ''),
                'gcn_seqno': str(drug.get('gcn_seqno', 0)),
                'indication_key': indication_key,
                'embedding': embedding_bytes
            })
            
            loaded_count += 1
            
            # Progress reporting every 30 seconds
            current_time = time.time()
            if current_time - last_report_time >= 30:
                elapsed = current_time - start_time
                rate = loaded_count / elapsed
                remaining = (len(drugs) - loaded_count) / rate if rate > 0 else 0
                print(f"   Progress: {loaded_count}/{len(drugs)} drugs ({loaded_count/len(drugs)*100:.1f}%) "
                      f"| Rate: {rate:.1f} drugs/sec | ETA: {remaining/60:.1f} min")
                last_report_time = current_time
            
        except Exception as e:
            error_count += 1
            if error_count <= 5:  # Only print first 5 errors
                print(f"   ⚠️  Error loading NDC {drug.get('NDC')}: {e}")
    
    elapsed = time.time() - start_time
    print(f"\n   ✅ Loaded {loaded_count} drugs in {elapsed:.1f}s ({loaded_count/elapsed:.1f} drugs/sec)")
    if error_count > 0:
        print(f"   ⚠️  {error_count} errors encountered")

def verify_load(redis_client):
    """Verify the production load"""
    print("\n🔍 Verifying production load...")
    
    # Count drug keys
    cursor = 0
    count = 0
    while True:
        cursor, keys = redis_client.scan(cursor, match=f'{PROD_KEY_PREFIX}*', count=1000)
        count += len(keys)
        if cursor == 0:
            break
    
    print(f"   ✅ Found {count} drug keys in Redis")
    
    # Count indication keys
    cursor = 0
    indication_count = 0
    while True:
        cursor, keys = redis_client.scan(cursor, match='indication:*', count=1000)
        indication_count += len(keys)
        if cursor == 0:
            break
    
    print(f"   ✅ Found {indication_count} indication keys in Redis")
    
    # Check index
    try:
        info = redis_client.execute_command('FT.INFO', PROD_INDEX_NAME)
        for i, item in enumerate(info):
            if item == 'num_docs':
                num_docs = info[i + 1]
                print(f"   ✅ Index {PROD_INDEX_NAME} has {num_docs} documents")
                break
    except Exception as e:
        print(f"   ⚠️  Error checking index: {e}")
    
    # Test searches
    print("\n🧪 Testing sample searches...")
    
    test_queries = ['crestor', 'testosterone', 'atorvastatin']
    for query in test_queries:
        try:
            result = redis_client.execute_command(
                'FT.SEARCH', PROD_INDEX_NAME,
                f'(@drug_name:{query}* | @brand_name:{query}*)',
                'LIMIT', '0', '5'
            )
            print(f"   ✅ '{query}': {result[0]} results")
        except Exception as e:
            print(f"   ⚠️  '{query}': Error - {e}")

def main():
    """Main execution"""
    print("=" * 80)
    print("PRODUCTION FULL LOAD - Optimized Schema")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Connect
        db_conn = connect_to_aurora()
        redis_client = connect_to_redis()
        
        # Clear old data
        clear_production_data(redis_client)
        
        # Create index
        create_production_index(redis_client)
        
        # Fetch drugs
        drugs = fetch_all_drugs(db_conn)
        
        if len(drugs) == 0:
            print("❌ No drugs fetched, aborting")
            return
        
        # Fetch indications
        unique_gcns = list(set(drug['gcn_seqno'] for drug in drugs if drug.get('gcn_seqno')))
        indication_map = fetch_indications_for_gcns(db_conn, unique_gcns)
        
        # Store indications by family (Option A)
        store_indications_by_family(redis_client, drugs, indication_map)
        
        # Load drugs
        load_drugs_to_redis(redis_client, drugs, indication_map)
        
        # Verify
        verify_load(redis_client)
        
        print("\n" + "=" * 80)
        print("✅ PRODUCTION LOAD COMPLETE!")
        print("=" * 80)
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        if 'db_conn' in locals():
            db_conn.close()

if __name__ == '__main__':
    main()


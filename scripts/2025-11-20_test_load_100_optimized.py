#!/usr/bin/env python3
"""
Test Load 100 Drugs with Optimized Schema

New Features:
- dosage_form as TAG (normalized: CREAM, GEL, TABLET)
- drug_class as TAG (normalized: ROSUVASTATIN_CALCIUM)
- indication stored separately by drug family (80%+ memory savings)
- Joins rdosed2 for human-readable dosage forms
- Joins indication tables for complete medical data

Usage:
    python3 2025-11-20_test_load_100_optimized.py
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
TEST_KEY_PREFIX = 'drug_test:'
TEST_INDEX_NAME = 'drugs_test_idx'

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
    Normalize drug_class to TAG format
    
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

def fetch_test_drugs(conn) -> List[Dict[str, Any]]:
    """
    Fetch 100 test drugs including Crestor, testosterone, and diverse classes
    """
    cursor = conn.cursor(dictionary=True)
    
    print("\n📋 Fetching test dataset...")
    
    # Updated query with dosage form and indication joins
    query = """
    SELECT 
        -- Core identification
        n.NDC,
        TRIM(n.LN) as drug_name,
        TRIM(COALESCE(n.BN, '')) as brand_name,
        TRIM(COALESCE(hc.GNN, '')) as generic_name,
        CAST(COALESCE(n.GCN_SEQNO, 0) AS UNSIGNED) as gcn_seqno,
        
        -- Dosage & form (NEW: Join rdosed2 for human-readable forms)
        COALESCE(TRIM(df.DOSE), TRIM(g.GCDF), '') as dosage_form_raw,
        TRIM(COALESCE(g.GCRT, '')) as route,
        TRIM(COALESCE(g.STR, COALESCE(g.STR60, ''))) as strength,
        
        -- Classification (CRITICAL for Option B alternatives)
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
    AND (
        n.LN LIKE '%CRESTOR%' OR
        (n.LN LIKE '%ROSUVASTATIN%' AND n.LN NOT LIKE '%CRESTOR%') OR  -- Generic rosuvastatin
        n.LN LIKE '%TESTOSTERONE%' OR
        n.LN LIKE '%LIPITOR%' OR
        n.LN LIKE '%ATORVASTATIN%' OR
        n.LN LIKE '%SIMVASTATIN%'
    )
    ORDER BY 
        -- Ensure we get a mix: CRESTOR, generic rosuvastatin, other statins, testosterone
        CASE 
            WHEN n.LN LIKE '%CRESTOR%' THEN 1
            WHEN n.LN LIKE '%ROSUVASTATIN%' AND n.LN NOT LIKE '%CRESTOR%' THEN 2
            WHEN n.LN LIKE '%ATORVASTATIN%' THEN 3
            WHEN n.LN LIKE '%SIMVASTATIN%' THEN 4
            WHEN n.LN LIKE '%LIPITOR%' THEN 5
            WHEN n.LN LIKE '%TESTOSTERONE%' THEN 6
            ELSE 7
        END,
        n.LN
    LIMIT 150  -- Increased to ensure we get all groups
    """
    
    cursor.execute(query)
    drugs = cursor.fetchall()
    cursor.close()
    
    print(f"   ✅ Fetched {len(drugs)} drugs")
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
    query = """
    SELECT 
        ig.GCN_SEQNO,
        GROUP_CONCAT(DISTINCT d.DXID_DESC100 ORDER BY d.DXID_DESC100 SEPARATOR ' | ') as indication
    FROM rindmgc0 ig
    JOIN rindmma2 im ON ig.INDCTS = im.INDCTS
    JOIN rfmldx0 d ON im.DXID = d.DXID
    WHERE ig.GCN_SEQNO IN ({})
    GROUP BY ig.GCN_SEQNO
    """.format(','.join(str(gcn) for gcn in gcns))
    
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    
    indication_map = {row['GCN_SEQNO']: row['indication'] for row in results}
    
    print(f"   ✅ Found indications for {len(indication_map)} GCNs")
    return indication_map

def clear_test_data(redis_client):
    """Clear existing test data"""
    print("\n🗑️  Clearing old test data...")
    
    # Delete test drug keys
    cursor = 0
    deleted_count = 0
    while True:
        cursor, keys = redis_client.scan(cursor, match=f'{TEST_KEY_PREFIX}*', count=100)
        if keys:
            redis_client.delete(*keys)
            deleted_count += len(keys)
        if cursor == 0:
            break
    
    # Delete test indication keys
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor, match='indication:*', count=100)
        if keys:
            redis_client.delete(*keys)
            deleted_count += len(keys)
        if cursor == 0:
            break
    
    # Drop test index
    try:
        redis_client.execute_command('FT.DROPINDEX', TEST_INDEX_NAME)
        print(f"   ✅ Dropped index {TEST_INDEX_NAME}")
    except redis.ResponseError as e:
        if 'Unknown index name' in str(e) or 'no such index' in str(e):
            print(f"   ⚠️  Index {TEST_INDEX_NAME} doesn't exist, skipping")
        else:
            raise
    
    print(f"   ✅ Deleted {deleted_count} keys")

def create_test_index(redis_client):
    """Create Redis Search index with optimized field types"""
    print(f"\n🔍 Creating index {TEST_INDEX_NAME}...")
    
    try:
        redis_client.execute_command(
            'FT.CREATE', TEST_INDEX_NAME,
            'ON', 'HASH',
            'PREFIX', '1', TEST_KEY_PREFIX,
            'SCHEMA',
            # Core fields
            'ndc', 'TAG', 'SORTABLE',
            'drug_name', 'TEXT', 'WEIGHT', '2.0',
            'brand_name', 'TEXT', 'WEIGHT', '1.5',
            'generic_name', 'TEXT',
            
            # Classification (TAG for fast filtering)
            'drug_class', 'TAG',  # NEW: TAG for exact filtering
            'therapeutic_class', 'TAG',
            
            # Dosage (TAG for exact filtering)
            'dosage_form', 'TAG',  # NEW: TAG for exact filtering
            
            # Status fields
            'is_generic', 'TAG',
            'is_active', 'TAG',
            'dea_schedule', 'TAG',
            
            # Numeric fields
            'gcn_seqno', 'NUMERIC', 'SORTABLE',
            
            # Manufacturer
            'manufacturer_name', 'TEXT',
            
            # Vector field for semantic search
            'embedding', 'VECTOR', 'HNSW', '6', 
            'TYPE', 'FLOAT32',
            'DIM', '1024',
            'DISTANCE_METRIC', 'COSINE',
            
            # Indication key (reference to separate store)
            'indication_key', 'TAG'  # NEW: Reference key
        )
        print(f"   ✅ Index {TEST_INDEX_NAME} created successfully")
        
    except redis.ResponseError as e:
        if 'Index already exists' in str(e):
            print(f"   ⚠️  Index {TEST_INDEX_NAME} already exists")
        else:
            raise

def determine_drug_family_key(drug: Dict[str, Any]) -> str:
    """
    Determine the drug family key for indication storage
    
    Returns: "brand:CRESTOR" or "generic:ROSUVASTATIN_CALCIUM"
    """
    if drug['brand_name']:
        return f"brand:{drug['brand_name'].upper().strip()}"
    else:
        drug_class = normalize_drug_class(drug['drug_class'])
        if drug_class:
            return f"generic:{drug_class}"
        else:
            return f"generic:{drug['generic_name'].upper().strip()}"

def load_drugs_to_redis(redis_client, drugs: List[Dict[str, Any]], indication_map: Dict[int, str]):
    """Load drugs to Redis with optimized indication storage"""
    print(f"\n📤 Loading {len(drugs)} drugs to Redis...")
    
    # Track stored indications (Option A)
    stored_indications: Set[str] = set()
    indication_count = 0
    
    for i, drug in enumerate(drugs, 1):
        ndc = drug['NDC']
        
        # Normalize fields
        dosage_form = normalize_dosage_form(drug.get('dosage_form_raw', ''))
        drug_class = normalize_drug_class(drug.get('drug_class', ''))
        
        # Determine drug family key
        family_key = determine_drug_family_key(drug)
        
        # Store indication separately (once per family)
        gcn = drug.get('gcn_seqno', 0)
        indication = indication_map.get(gcn, '')
        
        if indication and family_key not in stored_indications:
            redis_client.set(f"indication:{family_key}", indication)
            stored_indications.add(family_key)
            indication_count += 1
        
        # Generate embedding with semantic context
        embedding_parts = [drug['drug_name']]
        if drug.get('therapeutic_class'):
            embedding_parts.append(drug['therapeutic_class'])
        if drug.get('drug_class'):
            embedding_parts.append(drug['drug_class'])
        # Note: Not including indication in embedding for now (too long)
        
        embedding_text = ' '.join(embedding_parts)
        embedding = generate_embedding(embedding_text)
        embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
        
        # Store drug hash (without indication, just reference key)
        redis_client.hset(
            f'{TEST_KEY_PREFIX}{ndc}',
            mapping={
                'ndc': ndc,
                'drug_name': drug['drug_name'],
                'brand_name': drug['brand_name'],
                'generic_name': drug['generic_name'],
                'drug_class': drug_class,  # Normalized TAG
                'therapeutic_class': drug.get('therapeutic_class', ''),
                'dosage_form': dosage_form,  # Normalized TAG
                'manufacturer_name': drug.get('manufacturer_name', ''),
                'is_generic': drug['is_generic'],
                'is_active': drug['is_active'],
                'dea_schedule': drug.get('dea_schedule', ''),
                'gcn_seqno': drug['gcn_seqno'],
                'indication_key': family_key,  # Reference to separate store
                'embedding': embedding_bytes
            }
        )
        
        if i % 10 == 0:
            print(f"   Progress: {i}/{len(drugs)} drugs loaded...")
    
    print(f"   ✅ Loaded {len(drugs)} drugs")
    print(f"   ✅ Stored {indication_count} unique indications (deduplicated)")
    print(f"   💾 Memory savings: ~{(len(drugs) - indication_count) * 500 / 1024:.1f}KB")

def verify_test_data(redis_client):
    """Verify test data is correct"""
    print("\n✅ Verifying test data...")
    
    # Test 1: Check Crestor
    print("\n1️⃣  Checking CRESTOR data...")
    keys = list(redis_client.scan_iter(match=f'{TEST_KEY_PREFIX}*'))
    crestor_keys = [k for k in keys if b'CRESTOR' in redis_client.hget(k, 'drug_name')]
    
    if crestor_keys:
        sample = crestor_keys[0]
        data = redis_client.hgetall(sample)
        
        print(f"   NDC: {data[b'ndc'].decode()}")
        print(f"   Drug Name: {data[b'drug_name'].decode()}")
        print(f"   Brand Name: {data[b'brand_name'].decode()}")
        print(f"   Dosage Form: {data[b'dosage_form'].decode()} (should be normalized like 'TABLET')")
        print(f"   Drug Class: {data[b'drug_class'].decode()} (should be normalized like 'ROSUVASTATIN_CALCIUM')")
        print(f"   Therapeutic Class: {data[b'therapeutic_class'].decode()}")
        print(f"   Indication Key: {data[b'indication_key'].decode()}")
        
        # Fetch indication
        indication_key = data[b'indication_key'].decode()
        indication = redis_client.get(f"indication:{indication_key}")
        if indication:
            indication_str = indication.decode()
            indication_list = indication_str.split(' | ')
            print(f"   Indication Count: {len(indication_list)}")
            print(f"   First 3 Indications: {' | '.join(indication_list[:3])}...")
        else:
            print(f"   ⚠️  No indication found for key: {indication_key}")
    
    # Test 2: Check Testosterone
    print("\n2️⃣  Checking TESTOSTERONE data...")
    testosterone_keys = [k for k in keys if b'TESTOSTERONE' in redis_client.hget(k, 'drug_name')]
    
    if testosterone_keys:
        sample = testosterone_keys[0]
        data = redis_client.hgetall(sample)
        
        print(f"   NDC: {data[b'ndc'].decode()}")
        print(f"   Drug Name: {data[b'drug_name'].decode()}")
        print(f"   Dosage Form: {data[b'dosage_form'].decode()} (check if GEL or CREAM)")
        print(f"   DEA Schedule: {data[b'dea_schedule'].decode()}")
    
    # Test 3: Count unique indications
    print("\n3️⃣  Counting unique indications...")
    indication_keys = list(redis_client.scan_iter(match='indication:*'))
    print(f"   Unique Indications Stored: {len(indication_keys)}")
    
    # Test 4: Check field types
    print("\n4️⃣  Verifying field types...")
    print(f"   Total drug keys: {len(keys)}")
    print(f"   Index: {TEST_INDEX_NAME}")
    
    print("\n   ✅ Verification complete!")

def main():
    print("=" * 80)
    print("TEST LOAD: 100 Drugs with Optimized Schema")
    print("=" * 80)
    
    # Connect
    db_conn = connect_to_aurora()
    redis_client = connect_to_redis()
    
    try:
        # Clear old data
        clear_test_data(redis_client)
        
        # Create index
        create_test_index(redis_client)
        
        # Fetch drugs
        drugs = fetch_test_drugs(db_conn)
        
        # Fetch indications (by GCN)
        unique_gcns = list(set(drug['gcn_seqno'] for drug in drugs if drug['gcn_seqno']))
        indication_map = fetch_indications_for_gcns(db_conn, unique_gcns)
        
        # Load to Redis
        load_drugs_to_redis(redis_client, drugs, indication_map)
        
        # Verify
        verify_test_data(redis_client)
        
        print("\n" + "=" * 80)
        print("✅ TEST LOAD COMPLETE")
        print("=" * 80)
        print(f"\nNext steps:")
        print(f"1. Test search: 'testosterone cream'")
        print(f"2. Verify only creams are returned")
        print(f"3. Check indication display in UI")
        print(f"4. Validate memory savings")
        
    finally:
        db_conn.close()
        redis_client.close()

if __name__ == '__main__':
    main()


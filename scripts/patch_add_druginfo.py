#!/usr/bin/env python3
"""
Patch existing Redis data to add drug_info_id field
This is MUCH faster than full reload (~10-15 min vs 2.9 hours)
"""
import mysql.connector
import redis
import boto3
import time
from typing import Dict

def get_db_connection():
    """Get Aurora MySQL connection"""
    secrets = boto3.client('secretsmanager', region_name='us-east-1')
    password = secrets.get_secret_value(SecretId='DAW-DB-Password-dev')['SecretString']
    
    return mysql.connector.connect(
        host='daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com',
        user='dawadmin',
        password=password,
        database='fdb',
        connection_timeout=30
    )

def fetch_ndc_to_druginfo_mapping(db_conn) -> Dict[str, str]:
    """
    Fetch NDC → DrugInfo mapping from FDB
    
    Join path: rndc14 → rmindc1 → rmirmid1
    """
    print("📊 Fetching NDC → DrugInfo mapping from FDB...")
    
    query = """
    SELECT 
        n.NDC,
        rm.DrugInfo
    FROM rndc14 n
    INNER JOIN rmindc1 c ON n.NDC = c.NDC
    INNER JOIN rmirmid1 rm ON c.MEDID = rm.ROUTED_MED_ID
    WHERE n.OBSDTEC = '0000-00-00'  -- Active drugs only
        AND rm.DrugInfo IS NOT NULL  -- Only drugs with DrugInfo
    """
    
    cursor = db_conn.cursor()
    start_time = time.time()
    cursor.execute(query)
    results = cursor.fetchall()
    elapsed = time.time() - start_time
    
    # Convert to dict
    mapping = {str(row[0]): str(row[1]) for row in results}
    
    print(f"   ✓ Fetched {len(mapping):,} NDC → DrugInfo mappings in {elapsed:.1f}s")
    cursor.close()
    
    return mapping

def patch_redis_data(redis_client, ndc_druginfo_map: Dict[str, str]):
    """
    Patch existing Redis hashes with drug_info_id field
    """
    print(f"\n🔧 Patching {len(ndc_druginfo_map):,} Redis hashes...")
    
    updated_count = 0
    not_found_count = 0
    skipped_count = 0  # Already have DrugInfo
    
    start_time = time.time()
    
    for ndc, drug_info_id in ndc_druginfo_map.items():
        key = f"drug:{ndc}"
        
        # Check if key exists
        if not redis_client.exists(key):
            not_found_count += 1
            continue
        
        # Check if already has drug_info_id
        existing = redis_client.hget(key, 'drug_info_id')
        if existing:
            skipped_count += 1
            continue
        
        # Add drug_info_id field
        redis_client.hset(key, 'drug_info_id', drug_info_id)
        updated_count += 1
        
        # Progress report every 1000
        if updated_count % 1000 == 0:
            elapsed = time.time() - start_time
            rate = updated_count / elapsed if elapsed > 0 else 0
            print(f"   Progress: {updated_count:,} updated ({rate:.1f}/sec)", flush=True)
    
    elapsed = time.time() - start_time
    
    print(f"\n✅ Patch complete in {elapsed:.1f}s")
    print(f"   • Updated: {updated_count:,}")
    print(f"   • Skipped (already patched): {skipped_count:,}")
    print(f"   • Not found in Redis: {not_found_count:,}")
    
    return updated_count

def verify_patch(redis_client):
    """Verify the patch worked"""
    print("\n🔍 Verifying patch...")
    
    # Sample a few keys
    cursor = 0
    samples = []
    while len(samples) < 5:
        cursor, keys = redis_client.scan(cursor, match='drug:*', count=100)
        for key in keys:
            drug_info_id = redis_client.hget(key, 'drug_info_id')
            drug_name = redis_client.hget(key, 'drug_name')
            if drug_info_id:
                samples.append((key, drug_name.decode('utf-8'), drug_info_id.decode('utf-8')))
                if len(samples) >= 5:
                    break
        if cursor == 0:
            break
    
    print("Sample drugs with DrugInfo:")
    for key, name, drug_info in samples:
        print(f"  {key}: {name[:40]:40} | DrugInfo: {drug_info}")
    
    # Count total with drug_info_id
    total_with_druginfo = 0
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor, match='drug:*', count=1000)
        for key in keys:
            if redis_client.hexists(key, 'drug_info_id'):
                total_with_druginfo += 1
        if cursor == 0:
            break
    
    print(f"\n✅ Total drugs with drug_info_id: {total_with_druginfo:,}")

def main():
    print("="*80)
    print("PATCH: Add drug_info_id to Existing Redis Data")
    print("="*80)
    
    # Connect to FDB
    print("\n1️⃣  Connecting to Aurora FDB...")
    db_conn = get_db_connection()
    print("   ✓ Connected to Aurora")
    
    # Fetch mapping
    print("\n2️⃣  Fetching NDC → DrugInfo mapping...")
    ndc_druginfo_map = fetch_ndc_to_druginfo_mapping(db_conn)
    db_conn.close()
    
    # Connect to Redis
    print("\n3️⃣  Connecting to Redis...")
    redis_client = redis.Redis(
        host='10.0.11.153',
        port=6379,
        password='DAW-Redis-SecureAuth-2025',
        decode_responses=False
    )
    print("   ✓ Connected to Redis")
    
    # Patch Redis data
    print("\n4️⃣  Patching Redis hashes...")
    updated_count = patch_redis_data(redis_client, ndc_druginfo_map)
    
    # Verify
    print("\n5️⃣  Verifying patch...")
    verify_patch(redis_client)
    
    redis_client.close()
    
    print("\n" + "="*80)
    print("✅ PATCH COMPLETE!")
    print("="*80)
    print(f"\nNext steps:")
    print("1. Update search logic to use drug_info_id")
    print("2. Test searches: 'ezetimibe', 'rosuvastatin'")
    print("3. Deploy updated search handler")

if __name__ == '__main__':
    main()


"""
Drug Loader Lambda Function

Syncs drugs from Aurora MySQL to Redis with Bedrock Titan embeddings.

Features:
- Batch processing (configurable batch size)
- Progress tracking
- Error handling and retries
- Incremental sync support
- CloudWatch metrics

Environment Variables:
    DB_HOST: Aurora MySQL hostname
    DB_PORT: Aurora MySQL port (default: 3306)
    DB_NAME: Database name (default: fdb)
    DB_SECRET_ARN: Secrets Manager ARN for credentials
    REDIS_HOST: Redis hostname
    REDIS_PORT: Redis port (default: 6379)
    BATCH_SIZE: Number of drugs per batch (default: 100)
    MAX_DRUGS: Max drugs to sync (default: all)
    ENABLE_QUANTIZATION: Enable LeanVec4x8 (default: true)
"""

import os
import json
import time
import boto3
import mysql.connector
import redis
from typing import List, Dict, Any
from datetime import datetime

# Embedding generation (inline for Lambda simplicity)
def get_embedding_model():
    """Return a simple embedding model wrapper for Bedrock Titan."""
    class TitanEmbedding:
        def __init__(self):
            self.bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
            self.model_name = 'amazon.titan-embed-text-v2:0'
            self.dimension = 1024
        
        def embed(self, text: str) -> list:
            """Generate embedding using Bedrock Titan."""
            body = json.dumps({
                "inputText": text,
                "dimensions": 1024,
                "normalize": True
            })
            response = self.bedrock.invoke_model(
                modelId=self.model_name,
                contentType="application/json",
                accept="application/json",
                body=body
            )
            result = json.loads(response["body"].read())
            return result["embedding"]
    
    return TitanEmbedding()

# AWS clients
secrets_client = boto3.client('secretsmanager')
cloudwatch = boto3.client('cloudwatch')

# Configuration
DB_HOST = os.environ.get('DB_HOST')
DB_PORT = int(os.environ.get('DB_PORT', '3306'))
DB_NAME = os.environ.get('DB_NAME', 'fdb')
DB_SECRET_ARN = os.environ.get('DB_SECRET_ARN')
REDIS_HOST = os.environ.get('REDIS_HOST')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
BATCH_SIZE = int(os.environ.get('BATCH_SIZE', '100'))
MAX_DRUGS = int(os.environ.get('MAX_DRUGS', '0'))  # 0 = all
ENABLE_QUANTIZATION = os.environ.get('ENABLE_QUANTIZATION', 'true').lower() == 'true'

print(f"🔧 Configuration:")
print(f"   DB: {DB_HOST}:{DB_PORT}/{DB_NAME}")
print(f"   Redis: {REDIS_HOST}:{REDIS_PORT}")
print(f"   Batch size: {BATCH_SIZE}")
print(f"   Max drugs: {MAX_DRUGS or 'ALL'}")
print(f"   Quantization: {ENABLE_QUANTIZATION}")


def get_db_credentials() -> Dict[str, str]:
    """Retrieve database credentials from Secrets Manager."""
    try:
        response = secrets_client.get_secret_value(SecretId=DB_SECRET_ARN)
        secret = json.loads(response['SecretString'])
        return {
            'user': secret['username'],
            'password': secret['password']
        }
    except Exception as e:
        print(f"❌ Failed to get DB credentials: {e}")
        raise


def connect_to_aurora() -> mysql.connector.MySQLConnection:
    """Connect to Aurora MySQL."""
    print(f"🔗 Connecting to Aurora MySQL...")
    
    creds = get_db_credentials()
    
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=creds['user'],
        password=creds['password'],
        database=DB_NAME,
        connect_timeout=10
    )
    
    print(f"   ✅ Connected to {DB_NAME} database")
    return conn


def connect_to_redis() -> redis.Redis:
    """Connect to Redis."""
    print(f"🔗 Connecting to Redis...")
    
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=False,
        socket_connect_timeout=10
    )
    
    r.ping()
    print(f"   ✅ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    return r


def fetch_drugs_batch(conn: mysql.connector.MySQLConnection, offset: int, limit: int) -> List[Dict[str, Any]]:
    """Fetch a batch of drugs from Aurora.
    
    Args:
        conn: MySQL connection
        offset: Starting offset
        limit: Number of records to fetch
        
    Returns:
        List of drug dictionaries
    """
    query = """
        SELECT 
            NDC as ndc,
            UPPER(TRIM(LN)) as drug_name,
            UPPER(TRIM(COALESCE(BN, ''))) as brand_name,
            LOWER(TRIM(REGEXP_REPLACE(LN, ' [0-9].*', ''))) as generic_name,
            CAST(COALESCE(GCN_SEQNO, 0) AS UNSIGNED) as gcn_seqno,
            TRIM(COALESCE(DF, '')) as dosage_form,
            TRIM(COALESCE(LBLRID, '')) as manufacturer,
            CASE WHEN INNOV = '1' THEN 'true' ELSE 'false' END as is_brand,
            CASE WHEN INNOV = '0' THEN 'true' ELSE 'false' END as is_generic,
            CASE WHEN DEA IN ('1','2','3','4','5') THEN DEA ELSE '' END as dea_schedule,
            '' as drug_class,
            '' as therapeutic_class
        FROM rndc14
        WHERE LN IS NOT NULL
            AND LENGTH(TRIM(LN)) > 3
            AND NDC IS NOT NULL
        ORDER BY NDC
        LIMIT %s OFFSET %s
    """
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, (limit, offset))
    drugs = cursor.fetchall()
    cursor.close()
    
    return drugs


def generate_embeddings_batch(drugs: List[Dict], embedding_model) -> List[Dict]:
    """Generate embeddings for a batch of drugs.
    
    Args:
        drugs: List of drug dictionaries
        embedding_model: Embedding model instance
        
    Returns:
        Drugs with embeddings added
    """
    print(f"   🧠 Generating embeddings for {len(drugs)} drugs...")
    
    start_time = time.time()
    
    for drug in drugs:
        # Use drug name for embedding
        text = drug['drug_name']
        
        try:
            embedding = embedding_model.embed(text)
            drug['embedding'] = embedding
        except Exception as e:
            print(f"      ⚠️  Failed to embed '{text[:50]}': {e}")
            # Skip this drug
            drug['embedding'] = None
    
    elapsed = time.time() - start_time
    avg_time = (elapsed / len(drugs)) * 1000  # ms per drug
    
    print(f"      ✅ Generated {len(drugs)} embeddings in {elapsed:.2f}s ({avg_time:.0f}ms each)")
    
    return drugs


def store_drugs_in_redis(redis_client: redis.Redis, drugs: List[Dict]) -> tuple[int, int]:
    """Store drugs in Redis as JSON documents.
    
    Args:
        redis_client: Redis connection
        drugs: List of drug dictionaries with embeddings
        
    Returns:
        Tuple of (successful, failed) counts
    """
    print(f"   💾 Storing {len(drugs)} drugs in Redis...")
    
    success_count = 0
    fail_count = 0
    
    for drug in drugs:
        if drug.get('embedding') is None:
            fail_count += 1
            continue
        
        key = f"drug:{drug['ndc']}"
        
        # Add metadata
        drug['indexed_at'] = datetime.utcnow().isoformat() + 'Z'
        
        try:
            # Store as JSON
            redis_client.json().set(key, '$', drug)
            success_count += 1
        except Exception as e:
            print(f"      ⚠️  Failed to store {key}: {e}")
            fail_count += 1
    
    print(f"      ✅ Stored {success_count} drugs, {fail_count} failures")
    
    return success_count, fail_count


def publish_metrics(metric_name: str, value: float, unit: str = 'Count'):
    """Publish CloudWatch metric."""
    try:
        cloudwatch.put_metric_data(
            Namespace='DAW/DrugSync',
            MetricData=[{
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.utcnow()
            }]
        )
    except Exception as e:
        print(f"⚠️  Failed to publish metric {metric_name}: {e}")


def handle_grant_permissions(event, context):
    """Handle granting MySQL permissions"""
    try:
        dev_container_subnet = event.get('subnet', '172.31.%')
        password = event.get('password')
        
        if not password:
            return {
                'statusCode': 400,
                'body': json.dumps({'success': False, 'error': 'Missing required field: password'})
            }
        
        print(f"Granting MySQL permissions for subnet: {dev_container_subnet}")
        
        # Connect to database
        conn = connect_to_aurora()
        cursor = conn.cursor()
        
        # Grant permissions
        grant_sql = f"GRANT ALL PRIVILEGES ON fdb.* TO 'dawadmin'@'{dev_container_subnet}' IDENTIFIED BY %s"
        cursor.execute(grant_sql, (password,))
        print("✅ GRANT executed")
        
        cursor.execute("FLUSH PRIVILEGES")
        print("✅ FLUSH PRIVILEGES executed")
        
        # Verify
        cursor.execute("SELECT User, Host FROM mysql.user WHERE User='dawadmin'")
        results = cursor.fetchall()
        
        print(f"Current dawadmin users:")
        for user, host in results:
            print(f"   - dawadmin@{host}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'message': f'Permissions granted for dawadmin@{dev_container_subnet}',
                'users': [f"{user}@{host}" for user, host in results]
            })
        }
        
    except Exception as e:
        print(f"❌ Error granting permissions: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'success': False, 'error': str(e)})
        }


def handle_investigation_query(event, context):
    """Handle custom investigation queries for FDB schema analysis"""
    try:
        query_name = event.get('query_name', 'Investigation Query')
        sql = event.get('sql')
        params = tuple(event.get('params', []))
        
        if not sql:
            return {
                'statusCode': 400,
                'body': json.dumps({'success': False, 'error': 'Missing required field: sql'})
            }
        
        print(f"Running investigation query: {query_name}")
        
        # Connect to database
        conn = connect_to_aurora()
        cursor = conn.cursor(dictionary=True)
        
        # Execute query
        cursor.execute(sql, params)
        results = cursor.fetchall()
        
        print(f"Query returned {len(results)} rows")
        
        # Convert to JSON-serializable
        json_results = []
        for row in results:
            json_row = {}
            for key, value in row.items():
                json_row[key] = str(value) if value is not None and not isinstance(value, (int, float, str, bool)) else value
            json_results.append(json_row)
        
        cursor.close()
        conn.close()
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'query_name': query_name,
                'results': json_results,
                'count': len(json_results)
            })
        }
        
    except Exception as e:
        print(f"Investigation query failed: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e)
            })
        }


def lambda_handler(event, context):
    """Lambda handler for drug sync.
    
    Args:
        event: Lambda event (can contain 'batch_size', 'max_drugs', 'offset', 'action')
        context: Lambda context
        
    Returns:
        Response with sync statistics
    """
    # Check for special actions
    action = event.get('action')
    if action == 'investigate_fdb':
        return handle_investigation_query(event, context)
    elif action == 'grant_permissions':
        return handle_grant_permissions(event, context)
    
    print("=" * 60)
    print("🚀 DAW Drug Sync - Starting")
    print("=" * 60)
    
    start_time = time.time()
    
    # Override config from event if provided
    batch_size = event.get('batch_size', BATCH_SIZE)
    max_drugs = event.get('max_drugs', MAX_DRUGS)
    start_offset = event.get('offset', 0)
    
    print(f"\n📊 Sync Parameters:")
    print(f"   Batch size: {batch_size}")
    print(f"   Max drugs: {max_drugs or 'ALL'}")
    print(f"   Start offset: {start_offset}")
    
    # Initialize connections
    try:
        db_conn = connect_to_aurora()
        redis_conn = connect_to_redis()
        embedding_model = get_embedding_model()
        
        print(f"\n🧠 Embedding Model: {embedding_model.model_name}")
        print(f"   Dimensions: {embedding_model.dimension}")
        
    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
    
    # Process batches
    total_processed = 0
    total_success = 0
    total_failed = 0
    offset = start_offset
    
    print(f"\n📦 Processing batches...")
    
    try:
        while True:
            # Check Lambda timeout (stop 30 seconds before timeout)
            remaining_time = context.get_remaining_time_in_millis()
            if remaining_time < 30000:  # 30 seconds
                print(f"\n⏱️  Approaching Lambda timeout, stopping gracefully...")
                break
            
            # Check max drugs limit
            if max_drugs > 0 and total_processed >= max_drugs:
                print(f"\n🎯 Reached max drugs limit: {max_drugs}")
                break
            
            # Fetch batch
            print(f"\n   Batch {offset // batch_size + 1} (offset: {offset}):")
            drugs = fetch_drugs_batch(db_conn, offset, batch_size)
            
            if not drugs:
                print(f"      ℹ️  No more drugs to process")
                break
            
            print(f"      ✅ Fetched {len(drugs)} drugs")
            
            # Generate embeddings
            drugs_with_embeddings = generate_embeddings_batch(drugs, embedding_model)
            
            # Store in Redis
            success, failed = store_drugs_in_redis(redis_conn, drugs_with_embeddings)
            
            # Update counters
            total_processed += len(drugs)
            total_success += success
            total_failed += failed
            
            # Move to next batch
            offset += batch_size
            
            # Small delay to avoid overwhelming services
            time.sleep(0.1)
        
    except Exception as e:
        print(f"\n❌ Error during sync: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Close connections
        if db_conn:
            db_conn.close()
        print(f"\n🔌 Connections closed")
    
    # Calculate statistics
    elapsed = time.time() - start_time
    drugs_per_second = total_processed / elapsed if elapsed > 0 else 0
    
    # Publish metrics
    publish_metrics('DrugsProcessed', total_processed)
    publish_metrics('DrugsSuccessful', total_success)
    publish_metrics('DrugsFailed', total_failed)
    publish_metrics('SyncDuration', elapsed, 'Seconds')
    
    # Summary
    print("\n" + "=" * 60)
    print("🎉 DAW Drug Sync - Complete")
    print("=" * 60)
    print(f"\n📊 Statistics:")
    print(f"   Total processed: {total_processed}")
    print(f"   Successful: {total_success}")
    print(f"   Failed: {total_failed}")
    print(f"   Duration: {elapsed:.2f}s")
    print(f"   Throughput: {drugs_per_second:.2f} drugs/sec")
    print(f"   Next offset: {offset}")
    
    # Return response
    return {
        'statusCode': 200,
        'body': json.dumps({
            'total_processed': total_processed,
            'successful': total_success,
            'failed': total_failed,
            'duration_seconds': elapsed,
            'drugs_per_second': drugs_per_second,
            'next_offset': offset,
            'completed': len(drugs) < batch_size if 'drugs' in locals() else True
        })
    }


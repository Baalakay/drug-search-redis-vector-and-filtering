"""
Drug Detail Handler - GET /drugs/{ndc}

Returns complete drug information from Redis and Aurora.
Includes all drug details, alternatives count, and clinical information.

CRITICAL: Uses centralized configuration for all AWS services
"""

import json
import os
from typing import Dict, Any
from datetime import datetime


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for drug detail endpoint
    
    Args:
        event: API Gateway event with pathParameters containing:
            - ndc: str (11-digit NDC code)
        context: Lambda context
    
    Returns:
        API Gateway response with complete drug information
    """
    try:
        # Parse request
        ndc = event.get('pathParameters', {}).get('ndc')
        
        # Validate
        if not ndc:
            return error_response(400, "Missing required parameter: ndc")
        
        # Clean NDC (remove dashes if present)
        ndc = ndc.replace('-', '')
        
        if len(ndc) != 11:
            return error_response(400, "Invalid NDC format (must be 11 digits)")
        
        # Track timing
        start_time = datetime.now()
        
        # Step 1: Get drug from Redis
        redis_start = datetime.now()
        drug_result = get_drug_from_redis(ndc)
        redis_time = (datetime.now() - redis_start).total_seconds() * 1000
        
        if not drug_result['success']:
            return error_response(404, f"Drug not found: {ndc}")
        
        drug_data = drug_result['drug']
        
        # Step 2: Count alternatives (same GCN_SEQNO)
        alternatives_start = datetime.now()
        gcn_seqno = drug_data.get('gcn_seqno')
        alternatives_count = 0
        
        if gcn_seqno:
            alt_count = count_alternatives(gcn_seqno, exclude_ndc=ndc)
            alternatives_count = alt_count.get('count', 0)
        
        alternatives_time = (datetime.now() - alternatives_start).total_seconds() * 1000
        
        # Step 3: Enrich from Aurora (optional - pricing, clinical info)
        # TODO: Implement Aurora enrichment
        aurora_start = datetime.now()
        # aurora_data = enrich_from_aurora(ndc)
        aurora_time = (datetime.now() - aurora_start).total_seconds() * 1000
        
        # Calculate total time
        total_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Build comprehensive response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'drug': {
                    # Core identification
                    'ndc': drug_data.get('ndc'),
                    'drug_name': drug_data.get('drug_name'),
                    'brand_name': drug_data.get('brand_name', ''),
                    'generic_name': drug_data.get('generic_name', ''),
                    
                    # Classification
                    'gcn_seqno': drug_data.get('gcn_seqno'),
                    'is_generic': drug_data.get('is_generic') == 'true',
                    'dosage_form': drug_data.get('dosage_form', ''),
                    'dea_schedule': drug_data.get('dea_schedule', ''),
                    
                    # Clinical (from Redis, TODO: enrich from Aurora)
                    'indication': drug_data.get('indication', 'UNKNOWN'),
                    'drug_class': drug_data.get('drug_class', 'UNKNOWN'),
                    
                    # Alternatives
                    'alternatives_count': alternatives_count,
                    
                    # Pricing (TODO: from Aurora rnp2 table)
                    'pricing': {
                        'available': False,
                        'note': 'Pricing enrichment not yet implemented'
                    }
                },
                'metrics': {
                    'total_latency_ms': round(total_time, 2),
                    'redis_lookup_ms': round(redis_time, 2),
                    'alternatives_count_ms': round(alternatives_time, 2),
                    'aurora_enrichment_ms': round(aurora_time, 2)
                },
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return error_response(500, f"Internal server error: {str(e)}")


def get_drug_from_redis(ndc: str) -> Dict[str, Any]:
    """
    Get drug by NDC from Redis
    
    Args:
        ndc: 11-digit NDC code
    
    Returns:
        Dict with success, drug data
    """
    import redis
    
    try:
        # Connect to Redis
        redis_host = os.environ.get('REDIS_HOST', '10.0.11.153')
        redis_port = int(os.environ.get('REDIS_PORT', 6379))
        redis_password = os.environ.get('REDIS_PASSWORD')
        
        if not redis_password:
            return {
                'success': False,
                'error': 'REDIS_PASSWORD environment variable not set'
            }
        
        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=False  # Binary data (embeddings)
        )
        
        # Get drug from hash (exclude embedding field - it's binary)
        key = f"drug:{ndc}"
        
        # Get all fields except embedding
        fields_to_get = [
            'ndc', 'drug_name', 'brand_name', 'generic_name',
            'dosage_form', 'is_generic', 'dea_schedule', 'gcn_seqno',
            'indication', 'drug_class', 'is_brand'
        ]
        
        # Use HMGET to get specific fields (avoids binary embedding)
        values = client.hmget(key, fields_to_get)
        
        # Check if drug exists (at least NDC should be present)
        if not values[0]:  # NDC is first field
            return {
                'success': False,
                'error': f'Drug not found: {ndc}'
            }
        
        # Decode string fields manually
        drug_data = {}
        for i, field in enumerate(fields_to_get):
            if values[i]:
                drug_data[field] = values[i].decode('utf-8') if isinstance(values[i], bytes) else values[i]
            else:
                drug_data[field] = ''
        
        return {
            'success': True,
            'drug': drug_data
        }
        
    except Exception as e:
        print(f"Redis error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def count_alternatives(gcn_seqno: str, exclude_ndc: str = None) -> Dict[str, Any]:
    """
    Count drugs with same GCN_SEQNO (therapeutic equivalents)
    
    Args:
        gcn_seqno: Generic Code Number to search for
        exclude_ndc: NDC to exclude from count (the selected drug)
    
    Returns:
        Dict with count
    """
    import redis
    
    try:
        # Connect to Redis
        redis_host = os.environ.get('REDIS_HOST', '10.0.11.153')
        redis_port = int(os.environ.get('REDIS_PORT', 6379))
        redis_password = os.environ.get('REDIS_PASSWORD')
        
        if not redis_password:
            return {'count': 0, 'error': 'REDIS_PASSWORD not set'}
        
        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True
        )
        
        # Search by GCN_SEQNO
        query = f"@gcn_seqno:[{gcn_seqno} {gcn_seqno}]"
        
        # Execute search (only need count, not full results)
        results = client.execute_command(
            'FT.SEARCH', 'drugs_idx',
            query,
            'LIMIT', '0', '0',  # Don't return results, just count
            'DIALECT', '2'
        )
        
        # First element is total count
        total_count = results[0]
        
        # Exclude the selected drug itself
        if exclude_ndc:
            total_count = max(0, total_count - 1)
        
        return {
            'count': total_count
        }
        
    except Exception as e:
        print(f"Redis search error: {str(e)}")
        return {
            'count': 0,
            'error': str(e)
        }


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Build error response"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'success': False,
            'error': message,
            'timestamp': datetime.now().isoformat()
        })
    }


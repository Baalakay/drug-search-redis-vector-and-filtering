"""
Drug Alternatives Handler - GET /drugs/{ndc}/alternatives

Finds therapeutic equivalents using GCN_SEQNO grouping.
Returns generic and brand alternatives with pricing from Aurora.

CRITICAL: Uses centralized configuration for all AWS services
"""

import json
import os
from typing import Dict, Any, List
from datetime import datetime
import boto3


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for alternatives endpoint
    
    Args:
        event: API Gateway event with pathParameters containing:
            - ndc: str (11-digit NDC code)
        context: Lambda context
    
    Returns:
        API Gateway response with:
            - drug: selected drug info
            - alternatives: generic and brand options
            - total_count: number of alternatives
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
        
        # Step 1: Get selected drug from Redis
        redis_start = datetime.now()
        selected_drug = get_drug_from_redis(ndc)
        redis_time = (datetime.now() - redis_start).total_seconds() * 1000
        
        if not selected_drug['success']:
            return error_response(404, f"Drug not found: {ndc}")
        
        drug_data = selected_drug['drug']
        gcn_seqno = drug_data.get('gcn_seqno')
        
        if not gcn_seqno:
            return error_response(500, "Drug missing GCN_SEQNO")
        
        # Step 2: Find all drugs with same GCN_SEQNO
        alternatives_start = datetime.now()
        alternatives = find_alternatives_by_gcn(gcn_seqno, exclude_ndc=ndc)
        alternatives_time = (datetime.now() - alternatives_start).total_seconds() * 1000
        
        if not alternatives['success']:
            return error_response(500, f"Failed to find alternatives: {alternatives.get('error')}")
        
        # Step 3: Enrich with pricing from Aurora (optional)
        # TODO: Implement Aurora pricing enrichment
        
        # Group by generic/brand
        generic_options = [d for d in alternatives['drugs'] if d.get('is_generic') == 'true']
        brand_options = [d for d in alternatives['drugs'] if d.get('is_generic') == 'false']
        
        # Calculate total time
        total_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Build response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'drug': {
                    'ndc': drug_data.get('ndc'),
                    'drug_name': drug_data.get('drug_name'),
                    'brand_name': drug_data.get('brand_name'),
                    'generic_name': drug_data.get('generic_name'),
                    'gcn_seqno': gcn_seqno,
                    'is_generic': drug_data.get('is_generic'),
                    'dosage_form': drug_data.get('dosage_form')
                },
                'alternatives': {
                    'generic_options': generic_options,
                    'brand_options': brand_options,
                    'total_count': len(alternatives['drugs'])
                },
                'metrics': {
                    'total_latency_ms': round(total_time, 2),
                    'redis_lookup_ms': round(redis_time, 2),
                    'alternatives_search_ms': round(alternatives_time, 2)
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
        
        # Get drug from hash (exclude embedding field)
        key = f"drug:{ndc}"
        
        # Get only GCN_SEQNO field
        gcn_seqno = client.hget(key, 'gcn_seqno')
        
        if not gcn_seqno:
            return {
                'success': False,
                'error': f'Drug not found: {ndc}'
            }
        
        # Decode if bytes
        if isinstance(gcn_seqno, bytes):
            gcn_seqno = gcn_seqno.decode('utf-8')
        
        drug_data = {'gcn_seqno': gcn_seqno}
        
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


def find_alternatives_by_gcn(gcn_seqno: str, exclude_ndc: str = None) -> Dict[str, Any]:
    """
    Find all drugs with same GCN_SEQNO (therapeutic equivalents)
    
    Args:
        gcn_seqno: Generic Code Number to search for
        exclude_ndc: NDC to exclude from results (the selected drug)
    
    Returns:
        Dict with success, drugs list
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
            decode_responses=True
        )
        
        # Search by GCN_SEQNO
        # Query: @gcn_seqno:[{gcn} {gcn}] (exact match)
        query = f"@gcn_seqno:[{gcn_seqno} {gcn_seqno}]"
        
        # Return fields
        return_fields = [
            'ndc', 'drug_name', 'brand_name', 'generic_name',
            'is_generic', 'dosage_form', 'gcn_seqno'
        ]
        
        # Build RETURN clause
        return_clause = []
        for field in return_fields:
            return_clause.extend([field, field])
        
        # Execute search
        results = client.execute_command(
            'FT.SEARCH', 'drugs_idx',
            query,
            'RETURN', str(len(return_clause)), *return_clause,
            'SORTBY', 'is_generic', 'DESC',  # Generics first
            'LIMIT', '0', '100',  # Max 100 alternatives
            'DIALECT', '2'
        )
        
        # Parse results
        total_results = results[0]
        drugs = []
        
        for i in range(1, len(results), 2):
            if i + 1 < len(results):
                key = results[i]
                fields = results[i + 1]
                
                drug = {}
                for j in range(0, len(fields), 2):
                    if j + 1 < len(fields):
                        field_name = fields[j]
                        field_value = fields[j + 1]
                        drug[field_name] = field_value
                
                # Exclude the selected drug itself
                if exclude_ndc and drug.get('ndc') == exclude_ndc:
                    continue
                
                drugs.append(drug)
        
        return {
            'success': True,
            'drugs': drugs,
            'total_found': total_results - (1 if exclude_ndc else 0)  # Exclude selected drug from count
        }
        
    except Exception as e:
        print(f"Redis search error: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'drugs': []
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


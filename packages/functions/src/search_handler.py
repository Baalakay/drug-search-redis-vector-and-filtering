"""
Drug Search Handler - POST /search

Implements natural language drug search with:
1. Claude Sonnet 4 preprocessing (query expansion)
2. Bedrock Titan embeddings
3. Redis hybrid search (vector + filters)
4. Aurora enrichment

CRITICAL: Uses centralized llm_config.py for all LLM calls
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Centralized LLM configuration
from functions.src.config.llm_config import (
    call_claude_converse,
    estimate_cost,
    generate_embedding,
)
from functions.src.prompts import build_medical_search_prompts

# Redis index configuration
# Set to 'drugs_test_idx' for testing, 'drugs_idx' for production
REDIS_INDEX_NAME = os.environ.get('REDIS_INDEX_NAME', 'drugs_idx')  # Default to production index


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for drug search endpoint
    
    Args:
        event: API Gateway event with body containing:
            - query: str (natural language search)
            - filters: dict (optional, e.g., is_generic, dea_schedule)
            - max_results: int (optional, default 20)
        context: Lambda context
    
    Returns:
        API Gateway response with:
            - results: list of drugs
            - metadata: search metrics
            - query_info: original + expanded query
    """
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))
        query = body.get('query')
        user_filters = body.get('filters', {}) or {}
        if not isinstance(user_filters, dict):
            user_filters = {}
        max_results = body.get('max_results', 20)
        
        # Validate
        if not query:
            return error_response(400, "Missing required field: query")
        
        if max_results > 100:
            return error_response(400, "max_results cannot exceed 100")
        
        # Track overall timing
        start_time = datetime.now()
        
        # Step 1: Claude preprocessing (structured query parsing)
        claude_result = expand_query_with_claude(query)
        # Use Bedrock's internal latency metric (not client-side timing)
        claude_time = claude_result.get('latency_ms', 0)
        
        if not claude_result['success']:
            return error_response(500, f"Claude preprocessing failed: {claude_result.get('error')}")
        
        structured_query = claude_result.get('structured', {})
        claude_metrics = claude_result['metadata']
        expanded_query = structured_query.get('search_text') or claude_result.get('content') or query
        claude_filters = structured_query.get('filters', {}) or {}
        if not isinstance(claude_filters, dict):
            claude_filters = {}
        claude_terms = structured_query.get('search_terms')
        if not claude_terms:
            claude_terms = extract_search_terms(expanded_query)
        
        # Extract original query terms for lexical filtering (prioritize literal matches)
        original_terms = extract_search_terms(query)
        
        # Decide which terms to use for lexical matching:
        # ALWAYS use Claude's extracted terms if they're actual drug names
        # Claude now extracts ONLY drug names, never descriptive words or conditions
        corrections = structured_query.get('corrections', [])
        if corrections and len(claude_terms) <= len(original_terms) + 2:
            # Spelling correction case (e.g., "crester" → "crestor")
            exact_match_terms = claude_terms
        elif claude_terms and expanded_query != query:
            # Claude extracted/transformed the query to actual drug names
            # Use Claude's terms for better matching
            exact_match_terms = claude_terms
        else:
            # Fallback to original terms (rare case)
            exact_match_terms = original_terms
        
        # Step 2: Use VECTOR SEARCH + EXPANSION for ALL queries
        # Now that Claude extracts clean drug names for all query types,
        # we can use the same approach universally:
        # 1. Vector search on Claude's drug names
        # 2. Drug class expansion (pharmacological equivalents)
        # 3. Therapeutic class expansion (therapeutic alternatives)
        redis_start = datetime.now()
        merged_filters = merge_filters(user_filters, claude_filters)
        
        print(f"[SEARCH] Using vector search + expansion approach")
        
        # Initialize embedding_result for metrics
        embedding_result = None
        
        # MULTI-DRUG SEARCH: If Claude extracted multiple drugs (e.g., "atorvastatin rosuvastatin simvastatin"),
        # search for each drug individually and combine results for better accuracy
        drug_terms = [term for term in claude_terms if len(term) > 3]  # Filter out short words
        
        if len(drug_terms) >= 3:
            # Multiple drugs detected - search each individually for better accuracy
            # STRATEGY: 
            # 1. Do vector search for ALL drugs first (no expansion)
            # 2. Combine all vector results
            # 3. Do ONE expansion pass on the combined results
            print(f"[SEARCH] Multi-drug search detected: {len(drug_terms)} drugs")
            embedding_start = datetime.now()
            
            # PHASE 1: Vector search for each drug (NO expansion yet)
            all_vector_results = []
            seen_ndcs = set()
            
            for drug_term in drug_terms:
                # Generate embedding for this specific drug
                drug_embedding_result = generate_embedding(drug_term)
                if not drug_embedding_result['success']:
                    print(f"[WARNING] Failed to generate embedding for '{drug_term}': {drug_embedding_result.get('error')}")
                    continue
                
                # Do VECTOR-ONLY search (no expansion)
                drug_search = redis_vector_only_search(
                    embedding=drug_embedding_result['embedding'],
                    original_terms=[drug_term],
                    filters=merged_filters,
                    limit=20  # Get top 20 per drug
                )
                
                if drug_search['success']:
                    # Add unique results (deduplicate by NDC)
                    for result in drug_search['raw_results']:
                        ndc = result.get('ndc')
                        if ndc and ndc not in seen_ndcs:
                            seen_ndcs.add(ndc)
                            all_vector_results.append(result)
                    print(f"[SEARCH] Vector search for '{drug_term}': {len(drug_search['raw_results'])} results")
            
            embedding_time = (datetime.now() - embedding_start).total_seconds() * 1000
            
            print(f"[SEARCH] Phase 1 complete: {len(all_vector_results)} vector results from {len(drug_terms)} drugs")
            
            # PHASE 2: Do ONE expansion pass on the combined vector results
            expansion_start = datetime.now()
            all_raw_results = perform_drug_expansion(
                initial_drugs=all_vector_results,
                original_terms=exact_match_terms,
                claude_terms=claude_terms,
                filters=merged_filters
            )
            expansion_time = (datetime.now() - expansion_start).total_seconds() * 1000
            
            print(f"[SEARCH] Phase 2 complete: {len(all_raw_results)} total results after expansion")
            
            all_expansion_debug = all_raw_results.get('expansion_debug', {}) if isinstance(all_raw_results, dict) else {}
            
            # Extract raw results if wrapped in dict
            if isinstance(all_raw_results, dict) and 'raw_results' in all_raw_results:
                all_raw_results = all_raw_results['raw_results']
            
            embedding_time = (datetime.now() - embedding_start).total_seconds() * 1000
            redis_time = (datetime.now() - redis_start).total_seconds() * 1000
            
            # Now group the combined results
            print(f"[SEARCH] Combined {len(all_raw_results)} unique results from {len(drug_terms)} drug searches")
            import redis as redis_module
            redis_host = os.environ.get('REDIS_HOST', '10.0.11.153')
            redis_port = int(os.environ.get('REDIS_PORT', 6379))
            redis_password = os.environ.get('REDIS_PASSWORD')
            redis_client = redis_module.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                decode_responses=False
            )
            
            grouped_results = group_search_results(
                drugs=all_raw_results,
                original_terms=exact_match_terms,
                claude_terms=claude_terms,
                filters=merged_filters,
                redis_client=redis_client
            )
            
            search_results = {
                'success': True,
                'groups': grouped_results,
                'raw_results': all_raw_results,
                'expansion_debug': all_expansion_debug
            }
            
        else:
            # Single drug or simple query - use original approach
            embedding_start = datetime.now()
            embedding_result = generate_embedding(expanded_query)
            embedding_time = (datetime.now() - embedding_start).total_seconds() * 1000
            
            if not embedding_result['success']:
                return error_response(500, f"Embedding generation failed: {embedding_result.get('error')}")
            
            embedding = embedding_result['embedding']
            
            search_results = redis_hybrid_search(
                embedding=embedding,
                original_terms=exact_match_terms,
                claude_terms=claude_terms,
                filters=merged_filters,
                limit=max_results * 3
            )
            redis_time = (datetime.now() - redis_start).total_seconds() * 1000
        
        if not search_results['success']:
            return error_response(500, f"Redis search failed: {search_results.get('error')}")
        
        grouped_results = search_results['groups']
        raw_results = search_results['raw_results']
        expansion_debug = search_results.get('expansion_debug', {})  # Get expansion debug info
        
        # Limit grouped results to requested max_results
        if len(grouped_results) > max_results:
            grouped_results = grouped_results[:max_results]
        
        # Step 4: Aurora enrichment (if needed)
        # TODO: Implement Aurora enrichment for additional drug details
        
        # Calculate total time
        total_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Calculate costs
        claude_cost = estimate_cost(
            input_tokens=claude_metrics['input_tokens'],
            output_tokens=claude_metrics['output_tokens']
        )
        
        query_info = {
            'original': query,
            'expanded': expanded_query,
            'search_terms': original_terms,  # Show original terms used for filtering
            'claude_terms': claude_terms,  # Show Claude's expansions separately
            'filters': {
                'user': user_filters,
                'claude': claude_filters,
                'merged': merged_filters,
                'applied': search_results.get('applied_filters')
            },
            'claude': {
                'corrections': structured_query.get('corrections', []),
                'confidence': structured_query.get('confidence'),
                'raw_output': claude_result.get('content'),
                'parse_warning': claude_result.get('parse_warning')
            },
            'message': search_results.get('message'),
            'redis_query': search_results.get('redis_query')
        }
        
        # Build response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'  # Configure CORS as needed
            },
            'body': json.dumps({
                'success': True,
                'results': grouped_results,
                'raw_results': raw_results,
                'total_results': len(grouped_results),
                'raw_results_count': len(raw_results),
                'query_info': query_info,
                'expansion_debug': expansion_debug,  # Add expansion debug info
                'message': search_results.get('message'),
                'metrics': {
                    'total_latency_ms': round(total_time, 2),  # End-to-end API latency
                    'llm': {
                        'latency_ms': round(claude_time, 2),  # Bedrock's internal LLM inference time
                        'input_tokens': claude_metrics['input_tokens'],
                        'output_tokens': claude_metrics['output_tokens'],
                        'model': claude_result['model'],
                        'cost_estimate': claude_cost['total']
                    },
                    'embedding': {
                        'latency_ms': round(embedding_time, 2),  # Titan embedding time (client-side, includes network)
                        'model': embedding_result['model'] if embedding_result else 'N/A',
                        'dimensions': embedding_result['dimensions'] if embedding_result else 0
                    },
                    'redis': {
                        'latency_ms': round(redis_time, 2),  # Redis query time (VPC-local, accurate)
                        'results_count': search_results.get('raw_total', len(raw_results))
                    }
                },
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return error_response(500, f"Internal server error: {str(e)}")


def expand_query_with_claude(query: str) -> Dict[str, Any]:
    """
    Use Claude to parse the query into structured search parameters.
    """
    system_prompts, user_messages = build_medical_search_prompts(query)
    
    response = call_claude_converse(
        messages=user_messages,
        system_prompts=system_prompts,
        max_tokens=400,
        temperature=0.0
    )
    
    if not response.get('success'):
        return response
    
    raw_content = response.get('content', '')
    
    structured = {
        'search_text': (raw_content or query).strip(),
        'filters': {},
        'corrections': [],
        'confidence': None,
        'search_terms': []
    }
    
    try:
        parsed = json.loads(raw_content)
        structured['search_text'] = (parsed.get('search_text') or structured['search_text']).strip()
        structured['filters'] = parsed.get('filters') or {}
        structured['corrections'] = parsed.get('corrections') or []
        structured['confidence'] = parsed.get('confidence')
        structured['search_terms'] = parsed.get('search_terms') or parsed.get('terms') or []
    except json.JSONDecodeError as exc:
        response['parse_warning'] = f"Claude returned non-JSON output: {exc}"
    
    if not structured['search_terms']:
        structured['search_terms'] = extract_search_terms(structured['search_text'])
    
    response['structured'] = structured
    return response


def parse_redis_document(fields: List) -> Dict[str, Any]:
    """Parse Redis FT.SEARCH result document into a dictionary"""
    drug: Dict[str, Any] = {}
    
    for j in range(0, len(fields), 2):
        if j + 1 >= len(fields):
            continue
        field_name = fields[j].decode('utf-8') if isinstance(fields[j], bytes) else fields[j]
        field_value = fields[j + 1]
        
        if isinstance(field_value, bytes):
            value = field_value.decode('utf-8')
        else:
            value = field_value
        
        drug[field_name] = value
    
    return drug


def redis_filter_only_search(
    claude_terms: List[str],
    filters: Optional[Dict[str, Any]],
    limit: int = 20
) -> Dict[str, Any]:
    """
    Execute filter-only search in Redis (no vector search).
    Used for condition searches where Claude expands to drug names.
    
    Strategy:
    1. Find drugs matching Claude's expanded terms
    2. Extract their therapeutic classes
    3. Return ALL drugs in those therapeutic classes
    
    Much faster than vector search for condition queries!
    """
    import redis
    
    try:
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
            decode_responses=False
        )
        
        # Step 1: Find sample drugs matching Claude's terms to get therapeutic classes
        # FILTER OUT condition words - only search for actual drug names
        condition_words = {'cholesterol', 'hyperlipidemia', 'dyslipidemia', 'hypertension', 
                          'diabetes', 'pressure', 'blood', 'high', 'low', 'pain', 'for', 
                          'drugs', 'medication', 'treatment'}
        drug_name_terms = [term for term in claude_terms if term.lower() not in condition_words]
        
        therapeutic_classes = set()
        for term in drug_name_terms[:8]:  # Search up to 8 drug names
            # Search for drugs matching this term
            sample_query = f"(@drug_name:{term}* | @brand_name:{term}* | @generic_name:{term}*)"
            
            results = client.execute_command(
                'FT.SEARCH', REDIS_INDEX_NAME,
                sample_query,
                'RETURN', '2', 'therapeutic_class', 'therapeutic_class',
                'LIMIT', '0', '10'
            )
            
            if len(results) > 1:
                for i in range(1, len(results), 2):
                    if i + 1 < len(results):
                        drug_data = results[i + 1]
                        if isinstance(drug_data, list):
                            for j in range(0, len(drug_data), 2):
                                if drug_data[j] == b'therapeutic_class':
                                    tc = drug_data[j + 1].decode('utf-8') if isinstance(drug_data[j + 1], bytes) else drug_data[j + 1]
                                    if tc:
                                        therapeutic_classes.add(tc)
        
        if not therapeutic_classes:
            return {
                'success': True,
                'groups': [],
                'raw_results': [],
                'raw_total': 0,
                'applied_filters': {},
                'text_terms': claude_terms,
                'redis_query': 'No therapeutic classes found',
                'message': 'No matching drugs found for the specified terms'
            }
        
        # Step 2: Search for ALL drugs in those therapeutic classes using TAG filter
        filter_clause, applied_filters = build_filter_clause(filters or {})
        
        # Build TAG query for therapeutic classes
        tc_filter_parts = []
        for tc in therapeutic_classes:
            # Escape special characters for Redis TAG syntax
            tc_escaped = tc.replace(' ', '\\ ').replace('-', '\\-').replace('(', '\\(').replace(')', '\\)')
            tc_filter_parts.append(tc_escaped)
        
        tc_query = f"@therapeutic_class:{{{' | '.join(tc_filter_parts)}}}"
        
        # Combine with other filters if present
        if filter_clause:
            query = f"({filter_clause}) {tc_query}"
        else:
            query = tc_query
        
        print(f"[FILTER-ONLY] Query: {query}")
        print(f"[FILTER-ONLY] Therapeutic classes: {len(therapeutic_classes)}")
        
        return_fields = [
            'ndc', 'drug_name', 'brand_name', 'generic_name',
            'is_generic', 'dosage_form', 'dea_schedule', 'gcn_seqno',
            'indication', 'drug_class', 'therapeutic_class', 'manufacturer_name',
            'indication_key'  # For Option A separate indication store
        ]
        
        return_clause = []
        for field in return_fields:
            return_clause.extend([field, field])
        
        # Execute TAG filter query
        results = client.execute_command(
            'FT.SEARCH', REDIS_INDEX_NAME,
            query,
            'RETURN', str(len(return_clause)), *return_clause,
            'LIMIT', '0', str(limit * 5),  # Get many drugs for grouping (condition searches return whole classes)
            'DIALECT', '2'
        )
        
        total_results = results[0] if len(results) > 0 else 0
        drugs = []
        
        for i in range(1, len(results), 2):
            if i + 1 >= len(results):
                break
            
            doc_data = results[i + 1]
            drug = parse_redis_document(doc_data)
            
            # No similarity score for filter-only searches
            drug['similarity_score'] = None
            drug['similarity_score_pct'] = None
            drug['search_method'] = 'filter'  # Mark as filter-based
            drugs.append(drug)
        
        # Group results
        grouped_results = group_search_results(
            drugs=drugs,
            original_terms=claude_terms,  # Use Claude terms for grouping
            claude_terms=claude_terms,
            redis_client=client,  # For fetching indications
            filters=filters or {}
        )
        
        return {
            'success': True,
            'groups': grouped_results,
            'raw_results': drugs,
            'raw_total': total_results,
            'applied_filters': applied_filters,
            'text_terms': claude_terms,
            'redis_query': f"Filter by therapeutic classes: {len(therapeutic_classes)} found",
            'message': None
        }
        
    except Exception as e:
        import traceback
        return {
            'success': False,
            'error': f"Redis filter search failed: {str(e)}",
            'traceback': traceback.format_exc()
        }


def redis_hybrid_search(
    embedding: List[float],
    original_terms: Optional[List[str]],
    claude_terms: Optional[List[str]],
    filters: Optional[Dict[str, Any]],
    limit: int = 20
) -> Dict[str, Any]:
    """
    Execute hybrid search in Redis (vector + filters + lexical gating).
    
    Args:
        original_terms: User's actual query terms (for exact match detection)
        claude_terms: Claude's corrected/expanded terms (for therapeutic class filtering)
    """
    import redis
    import numpy as np
    
    try:
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
            decode_responses=False
        )
        
        # Normalize both original and claude terms
        _, normalized_original = build_text_clause(original_terms or [])
        _, normalized_claude = build_text_clause(claude_terms or [])
        filter_clause, applied_filters = build_filter_clause(filters or {})
        
        # Build lexical filter for exact matches (CRITICAL FIX for crestor → cortisone bug)
        # This ensures drugs matching the search term lexically are always included
        # CRITICAL: Exclude dosage form terms - they should only match via dosage_form TAG field
        DOSAGE_FORM_TERMS = {
            'cream', 'gel', 'tablet', 'capsule', 'injection', 'liquid', 'solution',
            'powder', 'patch', 'spray', 'inhaler', 'vial', 'ampule', 'suppository',
            'lotion', 'ointment', 'drops', 'syrup', 'suspension', 'pellet',
            'syringe', 'cartridge', 'injectable'  # Additional injectable terms
        }
        
        # Extract strength filter from Claude (prioritize Claude's extraction)
        import re
        strength_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|%|unit)', re.IGNORECASE)
        unitless_number_pattern = re.compile(r'\b(\d+(?:\.\d+)?)\b')
        strength_values = []  # Store original (number, unit) pairs for post-filter
        drug_name_terms = []
        
        # Get strength from Claude's filters
        strength = filters.get('strength') if filters else None
        if strength:
            # Parse Claude's strength format (e.g., "200mg", "10 mg", "0.5%")
            strength_str = str(strength).strip()
            strength_match = strength_pattern.search(strength_str)
            if strength_match:
                number = strength_match.group(1)
                unit = strength_match.group(2).upper()
                
                # Store original values for post-filter ONLY
                # Don't use strength in lexical filter because:
                # 1. Wildcards don't handle spaces well ("*2.5*MG*" won't match "2.5 MG")
                # 2. Decimals with periods cause Redis query syntax issues
                # 3. Post-filter regex handles all edge cases correctly
                strength_values.append((number, unit))
                print(f"[SEARCH] Will post-filter by strength: {number} {unit}")
            else:
                # Claude extracted a number without a unit (e.g., "12.5")
                # This happens when drug name is misspelled and Claude lacks context
                # Check if it's a valid number that could be a strength
                try:
                    num_value = float(strength_str)
                    if 0.001 <= num_value <= 10000:
                        # Treat as unitless strength
                        strength_values.append((strength_str, None))
                        print(f"[SEARCH] Will post-filter by unitless strength: {strength_str} (Claude extracted without unit)")
                except ValueError:
                    pass
        
        # FALLBACK: If Claude didn't extract strength, check for unitless numbers in original query
        # e.g., "testosterone 12.5" → match any unit (12.5 MG, 12.5%, etc.)
        if not strength_values and normalized_original:
            for term in normalized_original:
                # Check if this is a decimal/number that could be a strength
                if unitless_number_pattern.fullmatch(term):
                    # Only consider it if it looks like a reasonable strength value
                    # (between 0.001 and 10000, to avoid matching years, counts, etc.)
                    try:
                        num_value = float(term)
                        if 0.001 <= num_value <= 10000:
                            # Match any unit: "12.5" → matches "12.5 MG", "12.5%", "12.5 MCG", etc.
                            strength_values.append((term, None))  # None = any unit
                            print(f"[SEARCH] Will post-filter by unitless strength: {term} (any unit)")
                    except ValueError:
                        pass
        
        # Process normalized terms for drug names (skip dosage form terms and unit terms)
        if normalized_original:
            for term in normalized_original:
                if not term or len(term) <= 2:
                    continue
                    
                # Skip dosage form terms (they're filtered by dosage_form TAG field)
                if term.lower() in DOSAGE_FORM_TERMS:
                    continue
                
                # Skip unit-only terms (mg, mcg, etc.)
                if term.lower() in ['mg', 'mcg', 'g', 'ml', 'unit', 'units', '%']:
                    continue
                
                # Skip pure numbers (they're likely part of strength)
                if term.isdigit():
                    continue
                
                # This is a drug name term - save it
                drug_name_terms.append(term)
        
        # Build lexical filter with smart logic:
        # - Drug name terms: OR across fields (match in any name field)
        # - Strength terms: AND (must match)
        # - If dosage_form filter exists + drug name terms: require drug name match
        lexical_parts = []
        drug_name_clause_parts = []
        
        for term in drug_name_terms:
            # Build OR clause for this term across all name fields
            drug_name_clause_parts.append(f"@drug_name:{term}*")
            drug_name_clause_parts.append(f"@brand_name:{term}*")
            drug_name_clause_parts.append(f"@generic_name:{term}*")
        
        # If we have drug name terms, add them as a group (OR within, but required as a group)
        if drug_name_clause_parts:
            drug_name_clause = '(' + ' | '.join(drug_name_clause_parts) + ')'
            lexical_parts.append(drug_name_clause)
        
        # NOTE: Strength filtering is done in post-filter only (after expansions)
        # Not in lexical filter because wildcards don't handle spaces/decimals well
        
        # Combine filters
        filter_parts = []
        if filter_clause:
            filter_parts.append(filter_clause)
        
        # Add lexical parts (drug name + strength)
        if lexical_parts:
            # Combine lexical parts with AND (all must match)
            # Each part is already properly formatted
            filter_parts.extend(lexical_parts)
        
        # Build final filter string
        if len(filter_parts) > 1:
            # Multiple parts: wrap in parentheses for KNN syntax
            filter_str = '(' + ' '.join(filter_parts) + ')'
        elif len(filter_parts) == 1:
            # Single part: use as-is
            filter_str = filter_parts[0]
        else:
            # No filters: match all
            filter_str = "*"
        
        query = f"{filter_str}=>[KNN {limit} @embedding $vec AS score]"
        
        embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
        
        return_fields = [
            'ndc', 'drug_name', 'brand_name', 'generic_name',
            'is_generic', 'dosage_form', 'dea_schedule', 'gcn_seqno',
            'indication', 'drug_class', 'therapeutic_class', 'manufacturer_name', 'score',
            'indication_key'  # For Option A separate indication store
        ]
        
        return_clause: List[str] = []
        for field in return_fields:
            return_clause.extend([field, field])
        
        results = client.execute_command(
            'FT.SEARCH', REDIS_INDEX_NAME,
            query,
            'PARAMS', '2', 'vec', embedding_bytes,
            'RETURN', str(len(return_clause)), *return_clause,
            'SORTBY', 'score', 'ASC',
            'LIMIT', '0', str(limit),
            'DIALECT', '2'
        )
        
        total_results = results[0]
        drugs: List[Dict[str, Any]] = []
        
        for i in range(1, len(results), 2):
            if i + 1 >= len(results):
                break
            fields = results[i + 1]
            drug: Dict[str, Any] = {}
            
            for j in range(0, len(fields), 2):
                if j + 1 >= len(fields):
                    continue
                field_name = fields[j].decode('utf-8')
                field_value = fields[j + 1]
                
                if isinstance(field_value, bytes):
                    value = field_value.decode('utf-8')
                else:
                    value = field_value
                
                drug[field_name] = value
            
            raw_score = drug.pop('score', None)
            if isinstance(raw_score, bytes):
                raw_score = raw_score.decode('utf-8')
            
            similarity = None
            if raw_score is not None:
                try:
                    distance = float(raw_score)
                    similarity = max(0.0, min(1.0, 1.0 - distance))
                except (ValueError, TypeError):
                    similarity = None
            
            if similarity is not None:
                drug['similarity_score'] = similarity
                drug['similarity_score_pct'] = round(similarity * 100, 2)
            else:
                drug['similarity_score'] = None
                drug['similarity_score_pct'] = None
            
            drug['search_method'] = 'vector'  # Mark as vector-based
            
            drugs.append(drug)
        
        # CRITICAL FIX: If we found exact matches, expand by BOTH:
        # 1. drug_class (pharmacologic equivalents - same ingredient)
        # 2. therapeutic_class (therapeutic alternatives - different ingredients, same class)
        drug_classes_to_expand = set()
        therapeutic_classes_to_expand = set()
        
        # Track expansion info for debugging
        expansion_debug = {
            'drug_classes_found': [],
            'therapeutic_classes_found': [],
            'initial_drug_count': len(drugs)
        }
        
        for drug in drugs:
            # Check if this is an exact match
            corpus = " ".join([
                str(drug.get('drug_name', '')).lower(),
                str(drug.get('brand_name', '')).lower(),
                str(drug.get('generic_name', '')).lower()
            ])
            
            # Check against original terms
            is_exact = any(term and term.lower() in corpus for term in (original_terms or []))
            
            if is_exact:
                dc = drug.get('drug_class', '').strip()
                tc = drug.get('therapeutic_class', '').strip()
                if dc:
                    drug_classes_to_expand.add(dc)
                if tc:
                    therapeutic_classes_to_expand.add(tc)
        
        # Update debug info (will be updated later with filtered therapeutic classes)
        expansion_debug['drug_classes_found'] = list(drug_classes_to_expand)
        expansion_debug['therapeutic_classes_found_raw'] = list(therapeutic_classes_to_expand)
        
        # STEP 1: Expand by drug_class (pharmacologic equivalents)
        if drug_classes_to_expand:
            print(f"[SEARCH] Found {len(drug_classes_to_expand)} drug classes to expand")
            
            # Build TEXT filter query for drug classes (drug_class is TEXT field in production)
            dc_filter_parts = []
            for dc in drug_classes_to_expand:
                # For TEXT fields, wrap in quotes and escape internal quotes
                dc_quoted = f'"{dc}"'
                dc_filter_parts.append(dc_quoted)
            
            # drug_class is a TEXT field in production, use TEXT syntax
            tc_query = f"@drug_class:({' | '.join(dc_filter_parts)})"
            
            # Add any existing filters
            if filter_clause:
                tc_query = f"({filter_clause}) {tc_query}"
            
            print(f"[SEARCH] Expanding with drug_class query: {tc_query}")
            
            # Execute drug_class expansion query
            dc_results = client.execute_command(
                'FT.SEARCH', REDIS_INDEX_NAME,
                tc_query,
                'RETURN', str(len(return_clause)), *return_clause,
                'LIMIT', '0', str(limit * 2),  # Get more alternatives
                'DIALECT', '2'
            )
            
            # Parse additional results
            existing_ndcs = {d.get('ndc') for d in drugs}
            
            for i in range(1, len(dc_results), 2):
                if i + 1 >= len(dc_results):
                    break
                fields = dc_results[i + 1]
                drug: Dict[str, Any] = {}
                
                for j in range(0, len(fields), 2):
                    if j + 1 >= len(fields):
                        continue
                    field_name = fields[j].decode('utf-8')
                    field_value = fields[j + 1]
                    
                    if isinstance(field_value, bytes):
                        value = field_value.decode('utf-8')
                    else:
                        value = field_value
                    
                    drug[field_name] = value
                
                # Skip if already in results
                if drug.get('ndc') in existing_ndcs:
                    continue
                
                # Mark as drug_class filter (pharmacologic equivalent)
                drug['similarity_score'] = None
                drug['similarity_score_pct'] = None
                drug['search_method'] = 'drug_class_filter'
                
                drugs.append(drug)
                existing_ndcs.add(drug.get('ndc'))
            
            print(f"[SEARCH] Total drugs after drug_class expansion: {len(drugs)}")
        
        # STEP 2: Expand by therapeutic_class (therapeutic alternatives)
        # CRITICAL: Filter out meaningless therapeutic classes
        THERAPEUTIC_CLASS_BLACKLIST = {
            'Bulk Chemicals',           # Too broad - groups unrelated drugs
            'Miscellaneous',            # Too vague
            'Uncategorized',            # No clinical meaning
            'Not Specified',            # No clinical meaning
        }
        
        # Remove blacklisted classes
        therapeutic_classes_filtered = {
            tc for tc in therapeutic_classes_to_expand 
            if tc not in THERAPEUTIC_CLASS_BLACKLIST
        }
        
        if therapeutic_classes_to_expand != therapeutic_classes_filtered:
            blacklisted = therapeutic_classes_to_expand - therapeutic_classes_filtered
            print(f"[SEARCH] Filtered out blacklisted therapeutic classes: {blacklisted}")
        
        expansion_debug['therapeutic_classes_found_filtered'] = list(therapeutic_classes_filtered)
        
        if therapeutic_classes_filtered:
            print(f"[SEARCH] Found {len(therapeutic_classes_filtered)} valid therapeutic classes to expand")
            
            # Build TAG filter query for therapeutic classes
            tc_filter_parts = []
            for tc in therapeutic_classes_filtered:
                # Escape special characters for Redis TAG syntax
                tc_escaped = tc.replace(' ', '\\ ').replace('-', '\\-').replace('(', '\\(').replace(')', '\\)')
                tc_filter_parts.append(tc_escaped)
            
            tc_query = f"@therapeutic_class:{{{' | '.join(tc_filter_parts)}}}"
            
            # Add any existing filters
            if filter_clause:
                tc_query = f"({filter_clause}) {tc_query}"
            
            print(f"[SEARCH] Expanding with therapeutic_class query: {tc_query}")
            
            # Execute therapeutic_class expansion query
            tc_results = client.execute_command(
                'FT.SEARCH', REDIS_INDEX_NAME,
                tc_query,
                'RETURN', str(len(return_clause)), *return_clause,
                'LIMIT', '0', str(limit * 2),  # Get therapeutic alternatives
                'DIALECT', '2'
            )
            
            # Parse additional results
            existing_ndcs = {d.get('ndc') for d in drugs}
            
            for i in range(1, len(tc_results), 2):
                if i + 1 >= len(tc_results):
                    break
                fields = tc_results[i + 1]
                drug: Dict[str, Any] = {}
                
                for j in range(0, len(fields), 2):
                    if j + 1 >= len(fields):
                        continue
                    field_name = fields[j].decode('utf-8')
                    field_value = fields[j + 1]
                    
                    if isinstance(field_value, bytes):
                        value = field_value.decode('utf-8')
                    else:
                        value = field_value
                    
                    drug[field_name] = value
                
                # Skip if already in results
                if drug.get('ndc') in existing_ndcs:
                    continue
                
                # Mark as therapeutic_class filter (therapeutic alternative)
                drug['similarity_score'] = None
                drug['similarity_score_pct'] = None
                drug['search_method'] = 'therapeutic_class_filter'
                
                drugs.append(drug)
                existing_ndcs.add(drug.get('ndc'))
            
            print(f"[SEARCH] Total drugs after therapeutic_class expansion: {len(drugs)}")
        
        # POST-FILTER: Apply strength filter to all results (after expansions)
        # If user specified a strength (e.g., "200mg"), filter out drugs that don't have that strength
        if strength_values:
            print(f"[SEARCH] Applying post-expansion strength filter: {len(strength_values)} patterns")
            
            # Build regex patterns from original (number, unit) pairs
            strength_patterns = []
            for number, unit in strength_values:
                if unit is None:
                    # Unitless strength (e.g., "12.5") - match any unit
                    # CRITICAL: Use negative lookbehind/lookahead to prevent matching inside larger numbers
                    # Match: "12.5 MG" ✓, but NOT "112.5 MG" ✗
                    # Pattern: (?<!\d)12\.5(?!\d)\s*[A-Z%]
                    strength_patterns.append(re.compile(rf'(?<!\d){re.escape(number)}(?!\d)\s*[A-Z%]', re.IGNORECASE))
                else:
                    # Specific unit (e.g., "12.5 mg") - match that unit only
                    # Match: "12.5 MG", "12.5MG", "12.5 MG/ML", etc.
                    # Also use negative lookbehind/lookahead for consistency
                    strength_patterns.append(re.compile(rf'(?<!\d){re.escape(number)}(?!\d)\s*{re.escape(unit)}', re.IGNORECASE))
            
            if strength_patterns:
                filtered_drugs = []
                for drug in drugs:
                    drug_name = str(drug.get('drug_name', '')).upper()
                    # Keep drug if its name matches ANY of the strength patterns
                    if any(pattern.search(drug_name) for pattern in strength_patterns):
                        filtered_drugs.append(drug)
                
                print(f"[SEARCH] Strength post-filter: {len(drugs)} → {len(filtered_drugs)} drugs")
                drugs = filtered_drugs
        
        # POST-FILTER: Remove generic compounding bases and formulation components
        # These are not prescribable drugs, they're ingredients/bases for compounding
        generic_base_patterns = [
            r'BASE[_\s]*NO\.',        # GEL_BASE_NO.30, CREAM_BASE_NO.52, etc. (with _ or space)
            r'^MENTHOL$',             # Pure menthol (not menthol combinations)
            r'^CAMPHOR$',             # Pure camphor
            r'^GELFILM$',             # Generic gel film
            r'^POLYDIMETHYLSILOXANES$',  # Generic silicone base
            r'DIAPER.*DISPOSABLE',    # Medical supplies, not drugs
            r'^HYPROMELLOSE$',        # Generic cellulose derivative (binder/filler)
            r'VEHICLE[_\s]',          # VEHICLE_CREAM_BASE, VEHICLE_GEL, etc.
        ]
        
        filtered_drugs = []
        for drug in drugs:
            drug_class = str(drug.get('drug_class', '')).upper()
            drug_name = str(drug.get('drug_name', '')).upper()
            
            # Skip if this is a generic base/formulation component
            is_generic_base = any(
                re.search(pattern, drug_class) or re.search(pattern, drug_name)
                for pattern in generic_base_patterns
            )
            
            if not is_generic_base:
                filtered_drugs.append(drug)
        
        if len(filtered_drugs) < len(drugs):
            print(f"[SEARCH] Filtered out generic bases: {len(drugs)} → {len(filtered_drugs)} drugs")
            drugs = filtered_drugs
        
        grouped_results = group_search_results(
            drugs=drugs,
            original_terms=normalized_original,  # For exact match detection
            claude_terms=normalized_claude,      # For therapeutic class filtering
            redis_client=client,  # For fetching indications
            filters=filters or {}
        )
        message = None
        if not grouped_results:
            message = "No results found for the provided criteria."
        
        expansion_debug['final_drug_count'] = len(drugs)  # Update with final count
        expansion_debug['grouping_debug'] = {
            'input_drugs': len(drugs),
            'output_groups': len(grouped_results),
            'normalized_original': normalized_original,
            'normalized_claude': normalized_claude
        }
        
        return {
            'success': True,
            'groups': grouped_results,
            'raw_results': drugs,
            'raw_total': total_results,
            'applied_filters': applied_filters,
            'text_terms': normalized_original,  # Show original terms
            'redis_query': query,
            'message': message,
            'expansion_debug': expansion_debug  # Add debug info
        }
    
    except Exception as e:
        print(f"Redis search error: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'groups': [],
            'raw_results': []
        }


def redis_vector_only_search(
    embedding: List[float],
    original_terms: Optional[List[str]],
    filters: Optional[Dict[str, Any]],
    limit: int = 20
) -> Dict[str, Any]:
    """
    Execute vector-only search in Redis (NO expansion).
    Returns just the KNN vector search results.
    """
    import redis
    import numpy as np
    
    try:
        redis_host = os.environ.get('REDIS_HOST', '10.0.11.153')
        redis_port = int(os.environ.get('REDIS_PORT', 6379))
        redis_password = os.environ.get('REDIS_PASSWORD')
        
        if not redis_password:
            return {'success': False, 'error': 'REDIS_PASSWORD not set', 'raw_results': []}
        
        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=False
        )
        
        # Build filter clause
        filter_clause, applied_filters = build_filter_clause(filters or {})
        _, normalized_terms = build_text_clause(original_terms or [])
        
        # Build lexical filter for drug names
        lexical_parts = []
        drug_name_clause_parts = []
        
        for term in normalized_terms:
            if not term or len(term) <= 2:
                continue
            drug_name_clause_parts.append(f"@drug_name:{term}*")
            drug_name_clause_parts.append(f"@brand_name:{term}*")
            drug_name_clause_parts.append(f"@generic_name:{term}*")
        
        if drug_name_clause_parts:
            drug_name_clause = '(' + ' | '.join(drug_name_clause_parts) + ')'
            lexical_parts.append(drug_name_clause)
        
        # Combine filters
        filter_parts = []
        if filter_clause:
            filter_parts.append(filter_clause)
        if lexical_parts:
            filter_parts.extend(lexical_parts)
        
        if len(filter_parts) > 1:
            filter_str = '(' + ' '.join(filter_parts) + ')'
        elif len(filter_parts) == 1:
            filter_str = filter_parts[0]
        else:
            filter_str = "*"
        
        query = f"{filter_str}=>[KNN {limit} @embedding $vec AS score]"
        embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
        
        return_fields = [
            'ndc', 'drug_name', 'brand_name', 'generic_name',
            'is_generic', 'dosage_form', 'dea_schedule', 'gcn_seqno',
            'indication', 'drug_class', 'therapeutic_class', 'manufacturer_name', 'score',
            'indication_key'
        ]
        
        return_clause: List[str] = []
        for field in return_fields:
            return_clause.extend([field, field])
        
        results = client.execute_command(
            'FT.SEARCH', REDIS_INDEX_NAME,
            query,
            'PARAMS', '2', 'vec', embedding_bytes,
            'RETURN', str(len(return_clause)), *return_clause,
            'SORTBY', 'score', 'ASC',
            'LIMIT', '0', str(limit),
            'DIALECT', '2'
        )
        
        drugs: List[Dict[str, Any]] = []
        
        for i in range(1, len(results), 2):
            if i + 1 >= len(results):
                break
            fields = results[i + 1]
            drug: Dict[str, Any] = {}
            
            for j in range(0, len(fields), 2):
                if j + 1 >= len(fields):
                    continue
                field_name = fields[j].decode('utf-8')
                field_value = fields[j + 1]
                
                if isinstance(field_value, bytes):
                    value = field_value.decode('utf-8')
                else:
                    value = field_value
                
                drug[field_name] = value
            
            raw_score = drug.pop('score', None)
            if isinstance(raw_score, bytes):
                raw_score = raw_score.decode('utf-8')
            
            similarity = None
            if raw_score is not None:
                try:
                    distance = float(raw_score)
                    similarity = max(0.0, min(1.0, 1.0 - distance))
                except (ValueError, TypeError):
                    similarity = None
            
            if similarity is not None:
                drug['similarity_score'] = similarity
                drug['similarity_score_pct'] = round(similarity * 100, 2)
            else:
                drug['similarity_score'] = None
                drug['similarity_score_pct'] = None
            
            drug['search_method'] = 'vector'
            drugs.append(drug)
        
        return {
            'success': True,
            'raw_results': drugs
        }
    
    except Exception as e:
        print(f"Redis vector search error: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'raw_results': []
        }


def perform_drug_expansion(
    initial_drugs: List[Dict[str, Any]],
    original_terms: List[str],
    claude_terms: List[str],
    filters: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Perform drug_class and therapeutic_class expansion on initial drug results.
    """
    import redis
    
    try:
        redis_host = os.environ.get('REDIS_HOST', '10.0.11.153')
        redis_port = int(os.environ.get('REDIS_PORT', 6379))
        redis_password = os.environ.get('REDIS_PASSWORD')
        
        if not redis_password:
            return initial_drugs
        
        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=False
        )
        
        drugs = list(initial_drugs)  # Copy
        drug_classes_to_expand = set()
        therapeutic_classes_to_expand = set()
        
        # Find drug_class and therapeutic_class from initial results
        for drug in initial_drugs:
            corpus = " ".join([
                str(drug.get('drug_name', '')).lower(),
                str(drug.get('brand_name', '')).lower(),
                str(drug.get('generic_name', '')).lower()
            ])
            
            is_exact = any(term and term.lower() in corpus for term in (original_terms or []))
            
            if is_exact:
                dc = drug.get('drug_class', '').strip()
                tc = drug.get('therapeutic_class', '').strip()
                if dc:
                    drug_classes_to_expand.add(dc)
                if tc:
                    therapeutic_classes_to_expand.add(tc)
        
        print(f"[EXPANSION] Found {len(drug_classes_to_expand)} drug classes, {len(therapeutic_classes_to_expand)} therapeutic classes")
        
        filter_clause, _ = build_filter_clause(filters or {})
        
        return_fields = [
            'ndc', 'drug_name', 'brand_name', 'generic_name',
            'is_generic', 'dosage_form', 'dea_schedule', 'gcn_seqno',
            'indication', 'drug_class', 'therapeutic_class', 'manufacturer_name',
            'indication_key'
        ]
        
        return_clause: List[str] = []
        for field in return_fields:
            return_clause.extend([field, field])
        
        existing_ndcs = {d.get('ndc') for d in drugs}
        
        # STEP 1: Expand by drug_class
        if drug_classes_to_expand:
            dc_filter_parts = [f'"{dc}"' for dc in drug_classes_to_expand]
            tc_query = f"@drug_class:({' | '.join(dc_filter_parts)})"
            
            if filter_clause:
                tc_query = f"({filter_clause}) {tc_query}"
            
            dc_results = client.execute_command(
                'FT.SEARCH', REDIS_INDEX_NAME,
                tc_query,
                'RETURN', str(len(return_clause)), *return_clause,
                'LIMIT', '0', '100',
                'DIALECT', '2'
            )
            
            for i in range(1, len(dc_results), 2):
                if i + 1 >= len(dc_results):
                    break
                fields = dc_results[i + 1]
                drug: Dict[str, Any] = {}
                
                for j in range(0, len(fields), 2):
                    if j + 1 >= len(fields):
                        continue
                    field_name = fields[j].decode('utf-8')
                    field_value = fields[j + 1]
                    
                    if isinstance(field_value, bytes):
                        value = field_value.decode('utf-8')
                    else:
                        value = field_value
                    
                    drug[field_name] = value
                
                if drug.get('ndc') in existing_ndcs:
                    continue
                
                drug['similarity_score'] = None
                drug['similarity_score_pct'] = None
                drug['search_method'] = 'drug_class_filter'
                
                drugs.append(drug)
                existing_ndcs.add(drug.get('ndc'))
        
        # STEP 2: Expand by therapeutic_class (with blacklist)
        THERAPEUTIC_CLASS_BLACKLIST = {
            'Bulk Chemicals',
            'Miscellaneous',
            'Uncategorized',
            'Not Specified',
        }
        
        therapeutic_classes_filtered = {
            tc for tc in therapeutic_classes_to_expand 
            if tc not in THERAPEUTIC_CLASS_BLACKLIST
        }
        
        if therapeutic_classes_filtered:
            tc_filter_parts = []
            for tc in therapeutic_classes_filtered:
                tc_escaped = tc.replace(' ', '\\ ').replace('-', '\\-').replace('(', '\\(').replace(')', '\\)')
                tc_filter_parts.append(tc_escaped)
            
            tc_query = f"@therapeutic_class:{{{' | '.join(tc_filter_parts)}}}"
            
            if filter_clause:
                tc_query = f"({filter_clause}) {tc_query}"
            
            tc_results = client.execute_command(
                'FT.SEARCH', REDIS_INDEX_NAME,
                tc_query,
                'RETURN', str(len(return_clause)), *return_clause,
                'LIMIT', '0', '100',
                'DIALECT', '2'
            )
            
            for i in range(1, len(tc_results), 2):
                if i + 1 >= len(tc_results):
                    break
                fields = tc_results[i + 1]
                drug: Dict[str, Any] = {}
                
                for j in range(0, len(fields), 2):
                    if j + 1 >= len(fields):
                        continue
                    field_name = fields[j].decode('utf-8')
                    field_value = fields[j + 1]
                    
                    if isinstance(field_value, bytes):
                        value = field_value.decode('utf-8')
                    else:
                        value = field_value
                    
                    drug[field_name] = value
                
                if drug.get('ndc') in existing_ndcs:
                    continue
                
                drug['similarity_score'] = None
                drug['similarity_score_pct'] = None
                drug['search_method'] = 'therapeutic_class_filter'
                
                drugs.append(drug)
                existing_ndcs.add(drug.get('ndc'))
        
        return drugs
    
    except Exception as e:
        print(f"Expansion error: {str(e)}")
        return initial_drugs


def merge_filters(user_filters: Dict[str, Any], claude_filters: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    
    for key, value in (claude_filters or {}).items():
        if key not in AUTO_APPLY_CLAUDE_FILTERS:
            continue
        if value in (None, '', [], {}):
            continue
        merged[key] = value
    
    for key, value in (user_filters or {}).items():
        if value in (None, '', [], {}):
            continue
        merged[key] = value
    
    return merged


def extract_search_terms(text: str, max_terms: int = 8) -> List[str]:
    if not text:
        return []
    tokens = re.findall(r"[a-zA-Z0-9\-\+]+", text.lower())
    seen: List[str] = []
    for token in tokens:
        if token not in seen:
            seen.append(token)
        if len(seen) >= max_terms:
            break
    return seen


def sanitize_text_term(term: str) -> Optional[str]:
    if not term:
        return None
    cleaned = re.sub(r"\s+", " ", str(term)).strip()
    return cleaned or None


def build_text_clause(terms: List[str]) -> Tuple[Optional[str], List[str]]:
    """Build text clause for Redis TEXT search with fuzzy matching.
    
    Note: This is currently NOT used for filtering, only for match classification.
    Text terms are used to determine if a result is an "exact match" or "alternative".
    """
    normalized_terms: List[str] = []
    clauses: List[str] = []
    
    for term in terms:
        cleaned = sanitize_text_term(term)
        if not cleaned:
            continue
        normalized_terms.append(cleaned)
        # Use fuzzy matching without quotes for case-insensitive, partial matching
        escaped = cleaned.replace('"', '\\"')
        clause = f"(@drug_name:{escaped}* | @brand_name:{escaped}* | @generic_name:{escaped}*)"
        clauses.append(clause)
    
    if not clauses:
        return None, normalized_terms
    
    combined = " | ".join(clauses)
    return f"({combined})", normalized_terms


TAG_FIELDS = {
    'ndc', 'drug_class', 'dosage_form',
    'is_generic', 'dea_schedule'
    # NOTE: indication tagging pending full data load
}
AUTO_APPLY_CLAUDE_FILTERS: set[str] = {
    'dosage_form',  # Enable dosage form filtering (e.g., "cream", "gel")
    'strength',      # Enable strength filtering (e.g., "10mg", "20mg")
    # 'dea_schedule' removed - redundant with drug class/therapeutic class filtering
    'is_generic',    # Enable generic/brand filtering
    'ndc',           # Enable specific NDC lookup
    'gcn_seqno'      # Enable GCN filtering
}
NUMERIC_FIELDS = {'gcn_seqno'}


def build_filter_clause(filters: Dict[str, Any]) -> Tuple[Optional[str], Dict[str, Any]]:
    clauses: List[str] = []
    applied: Dict[str, Any] = {}
    
    for key, value in (filters or {}).items():
        normalized_key = key.lower()
        
        if normalized_key == 'drug_type':
            # Map older prompt output to is_generic when possible
            if isinstance(value, str):
                if value.lower() == 'generic':
                    normalized_key = 'is_generic'
                    value = 'true'
                elif value.lower() == 'brand':
                    normalized_key = 'is_generic'
                    value = 'false'
        
        if normalized_key in TAG_FIELDS:
            normalized_values = normalize_tag_values(normalized_key, value)
            if not normalized_values:
                continue
            applied[normalized_key] = normalized_values
            joined = "|".join(normalized_values)
            clauses.append(f"@{normalized_key}:{{{joined}}}")
        elif normalized_key in NUMERIC_FIELDS:
            numeric_clause, applied_value = build_numeric_clause(normalized_key, value)
            if not numeric_clause:
                continue
            applied[normalized_key] = applied_value
            clauses.append(numeric_clause)
        else:
            continue
    
    if not clauses:
        return None, applied
    
    return " ".join(clauses), applied


def normalize_tag_values(field: str, value: Any) -> List[str]:
    if value is None:
        return []
    
    values = value if isinstance(value, (list, tuple, set)) else [value]
    normalized: List[str] = []
    
    for item in values:
        if item in (None, ''):
            continue
        token = str(item).strip()
        if not token:
            continue
        
        if field == 'ndc':
            token = token.replace('-', '')
        elif field in {'indication', 'drug_class', 'dosage_form'}:
            token = token.upper().replace(' ', '_')
            
            # CRITICAL: Map Claude's generic forms to actual FDB dosage forms
            # Claude normalizes "vial", "syringe", "injection" → "injection"
            # But FDB has specific forms: VIAL, SOL, AMPULE, etc.
            if field == 'dosage_form':
                DOSAGE_FORM_MAPPINGS = {
                    'INJECTION': ['VIAL', 'SOL', 'AMPULE', 'CARTRIDGE', 'SYRINGE'],  # Map to all injectable forms
                    'ORAL': ['TABLET', 'CAPSULE', 'SOLUTION', 'SUSPENSION', 'SYRUP'],  # Map to all oral forms
                }
                
                # If this is a generic form that maps to multiple specific forms,
                # expand it (we'll handle this by returning multiple tokens)
                if token in DOSAGE_FORM_MAPPINGS:
                    # Return all mapped forms instead of just the generic one
                    normalized.extend(DOSAGE_FORM_MAPPINGS[token])
                    continue  # Skip adding the generic token itself
        elif field == 'is_generic':
            token = token.lower()
        else:
            token = token.upper()
        
        normalized.append(token)
    
    return normalized


def build_numeric_clause(field: str, value: Any) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        start, end = value
    else:
        start = end = value
    
    if start is None and end is None:
        return None, None
    
    start_str = str(start) if start is not None else "-inf"
    end_str = str(end) if end is not None else "+inf"
    clause = f"@{field}:[{start_str} {end_str}]"
    return clause, {'start': start_str, 'end': end_str}


def group_search_results(
    drugs: List[Dict[str, Any]],
    original_terms: List[str],
    claude_terms: List[str],
    filters: Dict[str, Any],
    redis_client: Any = None  # For fetching indications from separate store
) -> List[Dict[str, Any]]:
    """
    Group search results by drug family.
    
    Args:
        original_terms: User's actual query terms (for exact match detection)
        claude_terms: Claude's corrected/expanded terms (for therapeutic class filtering)
    """
    groups: List[Dict[str, Any]] = []
    index: Dict[str, Dict[str, Any]] = {}
    lowered_original = [term.lower() for term in original_terms]
    lowered_claude = [term.lower() for term in claude_terms]
    
    requested_ndc = None
    ndc_filter = filters.get('ndc') if filters else None
    if isinstance(ndc_filter, list):
        requested_ndc = ndc_filter[0]
    elif isinstance(ndc_filter, str):
        requested_ndc = ndc_filter
    
    # PASS 1: Find matches and their therapeutic classes
    # Include both exact matches (user's query) AND Claude's expansions (for condition searches)
    exact_match_therapeutic_classes = set()
    for doc in drugs:
        corpus = " ".join([
            str(doc.get('drug_name', '')).lower(),
            str(doc.get('brand_name', '')).lower(),
            str(doc.get('generic_name', '')).lower()
        ])
        
        # Check ORIGINAL terms for exact matches (user searched for this drug)
        is_exact_match = any(token and token in corpus for token in lowered_original)
        
        # ALSO check CLAUDE terms for condition searches (e.g., "high cholesterol" → "statin")
        # This allows therapeutic class filtering to work for condition-based queries
        is_claude_match = any(token and token in corpus for token in lowered_claude)
        
        if is_exact_match or is_claude_match:
            therapeutic_class = doc.get('therapeutic_class', '').strip()
            if therapeutic_class:
                exact_match_therapeutic_classes.add(therapeutic_class)
    
    # PASS 2: Group drugs, filtering alternatives by therapeutic class
    for doc in drugs:
        # Create composite key that separates brand families from generic families
        brand_name = doc.get('brand_name', '').strip()
        generic_name = doc.get('generic_name', '').strip()
        drug_name = doc.get('drug_name', '').strip()
        
        # Use the is_generic field from Redis to determine brand vs generic
        is_generic_str = str(doc.get('is_generic', 'true')).lower()
        is_branded_product = is_generic_str == 'false'
        
        if is_branded_product:
            # Brand drugs: group by brand name (includes repackaged brands)
            # e.g., all CRESTOR strengths together (5mg, 10mg, 20mg, 40mg)
            group_key = f"brand:{brand_name}"
        else:
            # Generic drugs: group by drug_class (ingredient) to combine all strengths
            # e.g., all rosuvastatin calcium together (5mg, 10mg, 20mg, 40mg)
            # NOT by GCN (which would split by strength)
            drug_class = doc.get('drug_class', '').strip()
            if drug_class:
                group_key = f"generic:{drug_class}"
            else:
                # Fallback: use generic_name
                group_key = f"generic:{generic_name or drug_name or doc.get('ndc')}"
        
        if not group_key:
            continue
        
        group = index.get(group_key)
        if not group:
            # Determine match type based on search method
            search_method = doc.get('search_method', 'vector')
            
            if search_method == 'drug_class_filter':
                # DRUG_CLASS FILTER: Pharmacologic equivalent (same ingredient)
                match_type = "pharmacologic"
                match_reason = "Drug class match"
                similarity_score = None  # No similarity score for filter
            elif search_method == 'therapeutic_class_filter':
                # THERAPEUTIC_CLASS FILTER: Therapeutic alternative (different ingredient, same class)
                match_type = "therapeutic_alternative"
                match_reason = "Therapeutic alternative class match"
                similarity_score = None  # No similarity score for filter
            elif search_method == 'filter':
                # CONDITION SEARCH FILTER-ONLY: All drugs are alternatives from therapeutic class
                match_type = "therapeutic_alternative"
                match_reason = "Therapeutic class match"
                similarity_score = None  # No similarity score for filter-only
            else:
                # VECTOR SEARCH: Use ORIGINAL terms for match classification
                match_type, match_reason = classify_match_type(doc, lowered_original, requested_ndc)
                
                # Use actual Redis similarity score (not hardcoded)
                similarity_score = doc.get('similarity_score_pct')
            
            # Set display name based on whether it's brand or generic family
            if is_branded_product and brand_name:
                display_name = brand_name
            else:
                # For generics, use drug_class (ingredient name) for display
                display_name = doc.get('drug_class', '') or doc.get('generic_name', '') or doc.get('drug_name', '')
                # Clean up the display name (remove strength/form details for family name)
                if display_name:
                    # Extract just the drug name part (before dosage info)
                    clean_name = re.sub(r'\s+\d+(\.\d+)?\s*(MG|MCG|G|ML|%|UNIT).*$', '', display_name, flags=re.IGNORECASE)
                    display_name = clean_name.strip() or display_name
            
            # Fetch indication from separate store (Option A optimization)
            indication_key = doc.get('indication_key', '')
            indication = ''
            indication_list = []
            
            if indication_key and redis_client:
                try:
                    indication_data = redis_client.get(f"indication:{indication_key}")
                    if indication_data:
                        indication = indication_data.decode('utf-8') if isinstance(indication_data, bytes) else indication_data
                        indication_list = indication.split(' | ') if indication else []
                        print(f"[INFO] Fetched {len(indication_list)} indications for {indication_key}")
                except Exception as e:
                    print(f"[WARNING] Failed to fetch indication for key {indication_key}: {e}")
            
            group = {
                'group_id': group_key,
                'display_name': display_name,
                'brand_name': doc.get('brand_name', ''),
                'generic_name': doc.get('drug_class', ''),  # Use drug_class instead of generic_name
                'is_generic': not is_branded_product,
                'gcn_seqno': doc.get('gcn_seqno'),
                'indication': indication,  # From separate store
                'indication_list': indication_list,  # Split for frontend
                'indication_count': len(indication_list),
                'dosage_forms': set(),
                'match_type': match_type,
                'match_reason': match_reason,
                'best_similarity': similarity_score,
                'primary_ndc': doc.get('ndc'),
                'variants': []
            }
            index[group_key] = group
            groups.append(group)
        else:
            if doc.get('similarity_score_pct') is not None:
                best = group.get('best_similarity')
                if best is None or doc['similarity_score_pct'] > best:
                    group['best_similarity'] = doc['similarity_score_pct']
                    group['primary_ndc'] = doc.get('ndc') or group.get('primary_ndc')
        
        if doc.get('dosage_form'):
            group['dosage_forms'].add(doc['dosage_form'])
        
        # Extract strength from drug_name for better variant organization
        strength = ''
        strength_match = re.search(r'(\d+(?:\.\d+)?\s*(?:MG|MCG|G|ML|%|UNIT))', doc.get('drug_name', ''), re.IGNORECASE)
        if strength_match:
            strength = strength_match.group(1).strip()
        
        group['variants'].append({
            'ndc': doc.get('ndc'),
            'label': doc.get('drug_name') or doc.get('brand_name') or doc.get('generic_name'),
            'dosage_form': doc.get('dosage_form'),
            'strength': strength,
            'manufacturer': doc.get('manufacturer_name', ''),
            'is_generic': str(doc.get('is_generic', '')).lower() == 'true',
            'similarity_score': doc.get('similarity_score_pct'),
            'dea_schedule': doc.get('dea_schedule')
        })
    
    for group in groups:
        dosage_set = group.get('dosage_forms')
        if isinstance(dosage_set, set):
            group['dosage_forms'] = sorted(list(dosage_set))
        
        # Group variants by manufacturer
        variants = group.get('variants', [])
        if variants:
            mfr_groups = {}
            for variant in variants:
                mfr = variant.get('manufacturer', 'Unknown Manufacturer').strip() or 'Unknown Manufacturer'
                if mfr not in mfr_groups:
                    mfr_groups[mfr] = []
                mfr_groups[mfr].append(variant)
            
            # Convert to list of manufacturer groups
            group['manufacturer_groups'] = [
                {
                    'manufacturer': mfr,
                    'variants': variants_list
                }
                for mfr, variants_list in sorted(mfr_groups.items())
            ]
            
            # Keep flat variants list for backward compatibility
            # group['variants'] remains unchanged
    
    # Convert sets to lists for JSON serialization
    for group in groups:
        if isinstance(group.get('dosage_forms'), set):
            group['dosage_forms'] = sorted(list(group['dosage_forms']))
    
    # Sort results by match_type priority and similarity score
    # Priority: 1. exact (vector search), 2. pharmacologic, 3. therapeutic_alternative
    # Within exact matches, sort by highest similarity score first
    def sort_key(group):
        match_type = group.get('match_type', 'therapeutic_alternative')
        similarity = group.get('best_similarity')
        
        # Define match type priority (lower number = higher priority)
        priority = {
            'exact': 0,
            'pharmacologic': 1,
            'therapeutic_alternative': 2
        }
        
        type_priority = priority.get(match_type, 3)
        
        # For sorting: (type_priority ascending, similarity descending)
        # Use negative similarity for descending order, handle None as -infinity
        similarity_sort = -(similarity if similarity is not None else float('-inf'))
        
        return (type_priority, similarity_sort)
    
    groups.sort(key=sort_key)
    
    return groups


def classify_match_type(
    drug: Dict[str, Any],
    tokens: List[str],
    requested_ndc: Optional[str]
) -> Tuple[str, str]:
    ndc = drug.get('ndc')
    if requested_ndc and ndc == requested_ndc:
        return "exact", "Matches requested NDC"
    
    corpus = " ".join([
        str(drug.get('drug_name', '')).lower(),
        str(drug.get('brand_name', '')).lower(),
        str(drug.get('generic_name', '')).lower()
    ])
    
    for token in tokens:
        if token and token in corpus:
            return "exact", f"Name contains \"{token}\""
    
    if not tokens:
        return "exact", "No lexical tokens provided"
    
    # Check search method to provide appropriate reason
    search_method = drug.get('search_method', 'vector')
    if search_method == 'filter':
        return "alternative", "Therapeutic class match"
    else:
        return "alternative", "Semantic similarity match"


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


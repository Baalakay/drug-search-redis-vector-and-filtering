#!/usr/bin/env python3
"""
Test Titan Embedding Similarity for Drug Names

Compare semantic similarity between:
- Brand name (Crestor) vs Generic name (rosuvastatin)
- To validate if vector search alone can find alternatives
"""

import boto3
import json
import numpy as np
from typing import List

# Bedrock client
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def get_embedding(text: str) -> List[float]:
    """Generate Titan v2 embedding for text"""
    response = bedrock.invoke_model(
        modelId='amazon.titan-embed-text-v2:0',
        body=json.dumps({
            'inputText': text,
            'dimensions': 1024,
            'normalize': True
        })
    )
    result = json.loads(response['body'].read())
    return result['embedding']

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))

def main():
    print("=" * 80)
    print("TITAN EMBEDDING SIMILARITY TEST")
    print("=" * 80)
    print()
    
    # Test cases
    test_pairs = [
        # Brand vs Generic
        ("crestor", "rosuvastatin"),
        ("crestor", "rosuvastatin calcium"),
        ("crestor", "ROSUVASTATIN CALCIUM"),
        
        # Brand vs Brand (same drug)
        ("crestor", "crestor 10mg"),
        ("crestor", "CRESTOR"),
        
        # Generic vs Generic (same drug)
        ("rosuvastatin", "rosuvastatin calcium"),
        
        # Brand vs Different Generic (different drug, same class)
        ("crestor", "atorvastatin"),
        ("crestor", "lipitor"),
        ("crestor", "simvastatin"),
        
        # Brand vs Unrelated Drug
        ("crestor", "metformin"),
        ("crestor", "lisinopril"),
        
        # Condition vs Drug
        ("high cholesterol", "rosuvastatin"),
        ("high cholesterol", "crestor"),
        ("hypercholesterolemia", "rosuvastatin"),
        
        # Drug Class vs Drug
        ("statin", "rosuvastatin"),
        ("HMG-CoA reductase inhibitor", "rosuvastatin"),
        
        # Misspellings
        ("crester", "crestor"),
        ("rosuvastatine", "rosuvastatin"),
        
        # Testosterone examples
        ("testosterone", "testosterone cream"),
        ("testosterone", "testosterone gel"),
        ("testosterone cream", "testosterone gel"),
        
        # Indication examples
        ("male hypogonadism", "testosterone"),
        ("low testosterone", "testosterone"),
        ("hypogonadism", "male hypogonadism"),
    ]
    
    results = []
    
    for term1, term2 in test_pairs:
        print(f"Comparing: '{term1}' vs '{term2}'")
        
        # Generate embeddings
        emb1 = get_embedding(term1)
        emb2 = get_embedding(term2)
        
        # Calculate similarity
        similarity = cosine_similarity(emb1, emb2)
        similarity_pct = similarity * 100
        
        results.append({
            'term1': term1,
            'term2': term2,
            'similarity': similarity,
            'similarity_pct': similarity_pct
        })
        
        print(f"   Similarity: {similarity:.4f} ({similarity_pct:.2f}%)")
        print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY - RANKED BY SIMILARITY")
    print("=" * 80)
    print()
    
    # Sort by similarity
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    for r in results:
        print(f"{r['similarity_pct']:6.2f}% | {r['term1']:30s} → {r['term2']}")
    
    print()
    print("=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)
    print()
    
    # Find key results
    brand_to_generic = [r for r in results if r['term1'] == 'crestor' and 'rosuvastatin' in r['term2'].lower()]
    if brand_to_generic:
        avg_similarity = sum(r['similarity_pct'] for r in brand_to_generic) / len(brand_to_generic)
        print(f"Brand → Generic (Crestor → Rosuvastatin): {avg_similarity:.2f}% average")
        for r in brand_to_generic:
            print(f"   {r['similarity_pct']:.2f}% | {r['term1']} → {r['term2']}")
    
    print()
    
    same_class = [r for r in results if r['term1'] == 'crestor' and r['term2'] in ['atorvastatin', 'lipitor', 'simvastatin']]
    if same_class:
        avg_similarity = sum(r['similarity_pct'] for r in same_class) / len(same_class)
        print(f"Same Class (Crestor → Other Statins): {avg_similarity:.2f}% average")
        for r in same_class:
            print(f"   {r['similarity_pct']:.2f}% | {r['term1']} → {r['term2']}")
    
    print()
    
    condition_match = [r for r in results if 'cholesterol' in r['term1'] and ('rosuvastatin' in r['term2'] or 'crestor' in r['term2'])]
    if condition_match:
        avg_similarity = sum(r['similarity_pct'] for r in condition_match) / len(condition_match)
        print(f"Condition → Drug: {avg_similarity:.2f}% average")
        for r in condition_match:
            print(f"   {r['similarity_pct']:.2f}% | {r['term1']} → {r['term2']}")
    
    print()
    print("=" * 80)

if __name__ == '__main__':
    main()


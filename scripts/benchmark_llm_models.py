#!/usr/bin/env python3
"""
LLM Model Benchmark Script

Benchmarks the currently deployed LLM model on the drug search API.
Automatically detects which model is running and benchmarks only that model.

Runs multiple times to account for:
- Lambda cold starts
- LLM prompt caching
- Network variability

Usage:
    python scripts/benchmark_llm_models.py
    
Outputs benchmark results to .output/ directory with model-specific filename.
"""

import json
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import statistics

# Configuration
API_BASE_URL = "https://9yb31qmdfa.execute-api.us-east-1.amazonaws.com"
TEST_QUERY = "tastosterne 200 mg vial"
RUNS_PER_MODEL = 5  # Number of times to run (first run is cold start, runs 2-5 are warm and averaged)

# Model pricing lookup (for cost calculation)
MODEL_PRICING = {
    "us.anthropic.claude-sonnet-4-20250514-v1:0": {
        "name": "Claude Sonnet 4",
        "input_price_per_1m": 3.00,
        "output_price_per_1m": 15.00,
    },
    "us.amazon.nova-micro-v1:0": {
        "name": "Amazon Nova Micro",
        "input_price_per_1m": 0.035,
        "output_price_per_1m": 0.14,
    },
    "anthropic.claude-3-haiku-20240307-v1:0": {
        "name": "Claude Haiku 3",
        "input_price_per_1m": 0.80,
        "output_price_per_1m": 4.00,
    },
    "us.amazon.nova-pro-v1:0": {
        "name": "Amazon Nova Pro",
        "input_price_per_1m": 0.80,
        "output_price_per_1m": 3.20,
    },
    "us.amazon.nova-lite-v1:0": {
        "name": "Amazon Nova Lite",
        "input_price_per_1m": 0.06,
        "output_price_per_1m": 0.24,
    },
}

OUTPUT_DIR = Path("/workspaces/DAW/.output")


def detect_current_model() -> Optional[Dict[str, Any]]:
    """
    Detect which LLM model is currently deployed by making a test API call
    
    Returns:
        Dict with model info, or None if detection fails
    """
    print("🔍 Detecting currently deployed model...")
    
    response = call_search_api(TEST_QUERY)
    
    if not response["success"]:
        print(f"❌ Failed to detect model: {response.get('error')}")
        return None
    
    data = response["data"]
    metrics = data.get("metrics", {})
    llm_metrics = metrics.get("llm", {})
    model_id = llm_metrics.get("model", "unknown")
    
    if model_id == "unknown" or model_id not in MODEL_PRICING:
        print(f"⚠️  Unknown model ID: {model_id}")
        print(f"   Add pricing info to MODEL_PRICING dict if needed")
        # Return with default pricing
        return {
            "model_id": model_id,
            "name": model_id.split(".")[-1] if "." in model_id else model_id,
            "input_price_per_1m": 0.0,
            "output_price_per_1m": 0.0,
        }
    
    model_info = MODEL_PRICING[model_id].copy()
    model_info["model_id"] = model_id
    
    print(f"✅ Detected: {model_info['name']} ({model_id})")
    return model_info


def call_search_api(query: str, timeout: int = 30) -> Dict[str, Any]:
    """
    Call the drug search API
    
    Args:
        query: Search query string
        timeout: Request timeout in seconds
    
    Returns:
        Dict with API response data
    """
    url = f"{API_BASE_URL}/search"
    headers = {"Content-Type": "application/json"}
    payload = {"query": query}
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
        end_time = time.time()
        
        response.raise_for_status()
        data = response.json()
        
        return {
            "success": True,
            "data": data,
            "latency_seconds": end_time - start_time,
            "status_code": response.status_code,
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "latency_seconds": 0,
            "status_code": getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
        }


def calculate_cost(input_tokens: int, output_tokens: int, input_price: float, output_price: float) -> Dict[str, float]:
    """
    Calculate cost for a query based on token usage
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        input_price: Price per 1M input tokens
        output_price: Price per 1M output tokens
    
    Returns:
        Dict with cost breakdown
    """
    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": input_cost + output_cost,
    }


def extract_llm_output(api_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract the LLM's structured output from the API response
    
    Args:
        api_response: Full API response
    
    Returns:
        Dict with extracted LLM output for comparison
    """
    query_info = api_response.get("query_info", {})
    claude_info = query_info.get("claude", {})
    
    return {
        "expanded_query": query_info.get("expanded", ""),
        "search_terms": query_info.get("claude_terms", []),
        "filters": query_info.get("filters", {}).get("claude", {}),
        "corrections": claude_info.get("corrections", []),
        "raw_output": claude_info.get("raw_output", ""),
    }


def compare_accuracy(ground_truth: Dict[str, Any], test_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare test output against ground truth
    
    Args:
        ground_truth: Output from Claude Sonnet 4 (baseline)
        test_output: Output from model being tested
    
    Returns:
        Dict with accuracy metrics
    """
    # Compare search terms
    gt_terms = set(ground_truth.get("search_terms", []))
    test_terms = set(test_output.get("search_terms", []))
    
    terms_match = gt_terms == test_terms
    
    # Compare expanded query
    expanded_match = ground_truth.get("expanded_query", "").strip() == test_output.get("expanded_query", "").strip()
    
    # Compare filters (dosage_form and strength)
    gt_filters = ground_truth.get("filters", {})
    test_filters = test_output.get("filters", {})
    
    dosage_form_match = gt_filters.get("dosage_form") == test_filters.get("dosage_form")
    strength_match = gt_filters.get("strength") == test_filters.get("strength")
    
    # Calculate overall accuracy
    checks = [terms_match, expanded_match, dosage_form_match, strength_match]
    accuracy_pct = (sum(checks) / len(checks)) * 100
    
    return {
        "accuracy_percent": accuracy_pct,
        "terms_match": terms_match,
        "expanded_match": expanded_match,
        "dosage_form_match": dosage_form_match,
        "strength_match": strength_match,
        "ground_truth_terms": list(gt_terms),
        "test_terms": list(test_terms),
        "ground_truth_filters": gt_filters,
        "test_filters": test_filters,
    }


def run_benchmark() -> Dict[str, Any]:
    """
    Run benchmark test for the currently deployed model
    
    Returns:
        Dict with benchmark results
    """
    # Detect current model
    model_config = detect_current_model()
    if not model_config:
        print("❌ Failed to detect model. Exiting.")
        return {}
    
    model_name = model_config["name"]
    model_id = model_config["model_id"]
    
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n🚀 Starting LLM Model Benchmark - Session: {session_id}")
    print(f"📝 Test Query: '{TEST_QUERY}'")
    print(f"🔗 API: {API_BASE_URL}")
    print(f"🤖 Model: {model_name}")
    print(f"🔄 Runs: {RUNS_PER_MODEL} (first run = cold start)")
    print("=" * 80)
    
    results = {
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "test_query": TEST_QUERY,
        "api_url": API_BASE_URL,
        "runs_per_model": RUNS_PER_MODEL,
        "model": model_name,
        "model_id": model_id,
        "all_runs": [],
        "averages": {},
    }
    
    # Store all runs
    all_runs = []
    
    print(f"\n📊 Testing {model_name}...")
    print(f"    Model ID: {model_id}")
    print(f"    Running {RUNS_PER_MODEL} times...")
    
    # Run multiple times
    for run_num in range(1, RUNS_PER_MODEL + 1):
        run_type = "COLD START" if run_num == 1 else f"WARM RUN {run_num - 1}"
        print(f"\n    [{run_num}/{RUNS_PER_MODEL}] {run_type}...")
        
        # Small delay between runs
        if run_num > 1:
            time.sleep(1)
        
        # Call the API
        response = call_search_api(TEST_QUERY)
        
        if not response["success"]:
            print(f"        ❌ API call failed: {response['error']}")
            all_runs.append({
                "run_number": run_num,
                "run_type": run_type,
                "success": False,
                "error": response["error"],
            })
            continue
        
        # Extract metrics
        data = response["data"]
        metrics = data.get("metrics", {})
        llm_metrics = metrics.get("llm", {})
        
        input_tokens = llm_metrics.get("input_tokens", 0)
        output_tokens = llm_metrics.get("output_tokens", 0)
        llm_latency_ms = llm_metrics.get("latency_ms", 0)  # Bedrock's internal inference time
        total_latency_s = response["latency_seconds"]  # Client-side end-to-end time
        model_used = llm_metrics.get("model", "unknown")
        
        # Verify model matches
        if model_used != model_id:
            print(f"        ⚠️  Warning: Expected {model_id}, got {model_used}")
        
        # Calculate cost
        cost = calculate_cost(
            input_tokens,
            output_tokens,
            model_config["input_price_per_1m"],
            model_config["output_price_per_1m"]
        )
        
        # Extract LLM output
        llm_output = extract_llm_output(data)
        
        # Print metrics
        print(f"        🔢 Input: {input_tokens}, Output: {output_tokens} tokens")
        print(f"        ⏱️  LLM: {llm_latency_ms:.0f}ms, Total: {total_latency_s:.2f}s")
        print(f"        💰 ${cost['total_cost']:.6f}")
        
        # Store this run
        run_result = {
            "run_number": run_num,
            "run_type": run_type,
            "success": True,
            "model_used": model_used,
            "metrics": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "llm_latency_ms": llm_latency_ms,
                "total_latency_seconds": total_latency_s,
            },
            "cost": cost,
            "llm_output": llm_output,
            "full_api_response": data,
        }
        
        all_runs.append(run_result)
    
    # Calculate aggregate statistics (excluding cold start)
    successful_runs = [r for r in all_runs if r["success"]]
    warm_runs = [r for r in successful_runs if r["run_number"] > 1]
    
    if not successful_runs:
        print(f"\n    ❌ All runs failed")
        results["success"] = False
        results["all_runs"] = all_runs
        return results
    
    # Calculate averages for warm runs (or all runs if only 1 run)
    runs_for_avg = warm_runs if warm_runs else successful_runs
    
    avg_input_tokens = statistics.mean([r["metrics"]["input_tokens"] for r in runs_for_avg])
    avg_output_tokens = statistics.mean([r["metrics"]["output_tokens"] for r in runs_for_avg])
    avg_llm_latency = statistics.mean([r["metrics"]["llm_latency_ms"] for r in runs_for_avg])
    avg_total_latency = statistics.mean([r["metrics"]["total_latency_seconds"] for r in runs_for_avg])
    avg_cost = statistics.mean([r["cost"]["total_cost"] for r in runs_for_avg])
    
    # Print summary
    print(f"\n    📊 SUMMARY ({model_name}):")
    print(f"        Successful runs: {len(successful_runs)}/{RUNS_PER_MODEL}")
    if warm_runs:
        print(f"        Warm run averages (excluding cold start):")
        print(f"          Tokens: {avg_input_tokens:.0f} in, {avg_output_tokens:.0f} out")
        print(f"          LLM Latency: {avg_llm_latency:.0f}ms")
        print(f"          Total Latency: {avg_total_latency:.2f}s")
        print(f"          Cost: ${avg_cost:.6f}")
    
    # Store aggregated results
    results["success"] = True
    results["runs"] = len(successful_runs)
    results["all_runs"] = all_runs
    results["averages"] = {
        "input_tokens": avg_input_tokens,
        "output_tokens": avg_output_tokens,
        "llm_latency_ms": avg_llm_latency,
        "total_latency_seconds": avg_total_latency,
        "cost": avg_cost,
    }
    results["pricing"] = {
        "input_price_per_1m": model_config["input_price_per_1m"],
        "output_price_per_1m": model_config["output_price_per_1m"],
    }
    results["llm_output"] = successful_runs[0]["llm_output"]
    
    print("\n" + "=" * 80)
    print("✅ Benchmark Complete!")
    
    return results


def save_results(results: Dict[str, Any]) -> str:
    """
    Save benchmark results to .output directory with model-specific filename
    
    Args:
        results: Benchmark results
    
    Returns:
        Path to saved file
    """
    session_id = results["session_id"]
    model_name = results.get("model", "unknown").replace(" ", "_").lower()
    
    # Create model-specific filename
    filename = f"{session_id}_{model_name}_benchmark.json"
    filepath = OUTPUT_DIR / filename
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save JSON
    with open(filepath, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {filepath}")
    
    # Also create a human-readable summary
    summary_filename = f"{session_id}_{model_name}_benchmark_summary.txt"
    summary_filepath = OUTPUT_DIR / summary_filename
    
    with open(summary_filepath, 'w') as f:
        f.write(f"LLM Model Benchmark Summary\n")
        f.write(f"{'=' * 80}\n\n")
        f.write(f"Session ID: {session_id}\n")
        f.write(f"Timestamp: {results['timestamp']}\n")
        f.write(f"Model: {results.get('model', 'Unknown')}\n")
        f.write(f"Model ID: {results.get('model_id', 'Unknown')}\n")
        f.write(f"Test Query: '{results['test_query']}'\n")
        f.write(f"API URL: {results['api_url']}\n\n")
        
        if not results.get("success"):
            f.write(f"❌ Benchmark failed: All runs failed\n")
            return str(filepath)
        
        f.write(f"{'=' * 80}\n")
        f.write(f"RESULTS (Averages from warm runs, excluding cold start)\n")
        f.write(f"{'=' * 80}\n\n")
        
        f.write(f"✅ {results['model']}\n")
        f.write(f"   Model ID: {results['model_id']}\n")
        f.write(f"   Successful Runs: {results['runs']}/{results['runs_per_model']}\n")
        f.write(f"   \n")
        f.write(f"   Average Metrics (warm runs):\n")
        f.write(f"     Input Tokens:  {results['averages']['input_tokens']:.0f}\n")
        f.write(f"     Output Tokens: {results['averages']['output_tokens']:.0f}\n")
        f.write(f"     LLM Latency:   {results['averages']['llm_latency_ms']:.0f}ms\n")
        f.write(f"     Total Latency: {results['averages']['total_latency_seconds']:.2f}s\n")
        f.write(f"   \n")
        f.write(f"   Average Cost:\n")
        f.write(f"     Total:  ${results['averages']['cost']:.6f}\n")
        f.write(f"   \n")
        f.write(f"   Pricing:\n")
        f.write(f"     Input:  ${results['pricing']['input_price_per_1m']:.2f} per 1M tokens\n")
        f.write(f"     Output: ${results['pricing']['output_price_per_1m']:.2f} per 1M tokens\n")
    
    print(f"📄 Summary saved to: {summary_filepath}")
    
    return str(filepath)


def main():
    """Main entry point"""
    print("\n" + "=" * 80)
    print("LLM MODEL BENCHMARK")
    print("=" * 80)
    print("\n⚠️  IMPORTANT: This script benchmarks the currently deployed model")
    print(f"   The API will be called {RUNS_PER_MODEL} times")
    print(f"   First run = cold start, subsequent runs = warm (with caching)")
    print(f"   Results will be saved with model-specific filename\n")
    print("=" * 80 + "\n")
    
    # Run benchmark
    results = run_benchmark()
    
    if not results or not results.get("success"):
        print("\n❌ Benchmark failed. Check errors above.")
        return
    
    # Save results
    filepath = save_results(results)
    
    print(f"\n✅ Benchmark complete! Results saved to: {filepath}")
    print(f"   Run the comparison script after testing all 3 models to compare results.")


if __name__ == "__main__":
    main()


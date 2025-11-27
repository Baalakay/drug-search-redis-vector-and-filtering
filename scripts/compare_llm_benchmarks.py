#!/usr/bin/env python3
"""
LLM Benchmark Comparison Script

Compares benchmark results from multiple LLM models.
Looks for benchmark files in .output/ directory and compares them.

Usage:
    python scripts/compare_llm_benchmarks.py
    
Expected files:
    - {timestamp}_claude_sonnet_4_benchmark.json
    - {timestamp}_amazon_nova_micro_benchmark.json
    - {timestamp}_claude_haiku_3.5_benchmark.json
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

OUTPUT_DIR = Path("/workspaces/DAW/.output")

# Model display names mapping
MODEL_DISPLAY_NAMES = {
    "claude_sonnet_4": "Claude Sonnet 4",
    "amazon_nova_micro": "Amazon Nova Micro",
    "claude_haiku_3_5": "Claude Haiku 3.5",  # Note: underscore, not dot
    "claude_haiku_3.5": "Claude Haiku 3.5",  # Support both formats
}


def find_benchmark_files() -> Dict[str, Path]:
    """
    Find all benchmark JSON files in .output directory
    
    Returns:
        Dict mapping model key to file path
    """
    benchmark_files = {}
    
    # Look for benchmark files
    for filepath in OUTPUT_DIR.glob("*_benchmark.json"):
        filename = filepath.name
        
        # Extract model name from filename
        # Format: {timestamp}_{model_name}_benchmark.json
        parts = filename.replace("_benchmark.json", "").split("_", 1)
        if len(parts) == 2:
            model_key = parts[1]  # Everything after timestamp
            
            # Normalize model key
            model_key = model_key.lower().replace(" ", "_")
            
            if model_key in MODEL_DISPLAY_NAMES:
                benchmark_files[model_key] = filepath
    
    return benchmark_files


def load_benchmark(filepath: Path) -> Optional[Dict[str, Any]]:
    """
    Load benchmark JSON file
    
    Args:
        filepath: Path to benchmark file
    
    Returns:
        Benchmark data or None if failed
    """
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Failed to load {filepath}: {e}")
        return None


def compare_benchmarks(benchmarks: Dict[str, Dict[str, Any]]) -> None:
    """
    Compare multiple benchmark results and print comparison
    
    Args:
        benchmarks: Dict mapping model key to benchmark data
    """
    if not benchmarks:
        print("❌ No benchmark files found!")
        print(f"   Expected files in: {OUTPUT_DIR}")
        print("   Format: {timestamp}_{model_name}_benchmark.json")
        return
    
    print("=" * 80)
    print("LLM MODEL BENCHMARK COMPARISON")
    print("=" * 80)
    print(f"\n📊 Comparing {len(benchmarks)} models:\n")
    
    # Display found models
    for model_key, data in benchmarks.items():
        model_name = MODEL_DISPLAY_NAMES.get(model_key, model_key)
        print(f"  ✅ {model_name}")
    
    print("\n" + "=" * 80)
    print("RESULTS (Averages from warm runs, excluding cold start)")
    print("=" * 80 + "\n")
    
    # Extract metrics for comparison
    model_metrics = []
    for model_key, data in benchmarks.items():
        if not data.get("success"):
            continue
        
        model_name = MODEL_DISPLAY_NAMES.get(model_key, model_key)
        averages = data.get("averages", {})
        
        model_metrics.append({
            "key": model_key,
            "name": model_name,
            "model_id": data.get("model_id", "unknown"),
            "llm_latency_ms": averages.get("llm_latency_ms", 0),
            "total_latency_s": averages.get("total_latency_seconds", 0),
            "cost": averages.get("cost", 0),
            "input_tokens": averages.get("input_tokens", 0),
            "output_tokens": averages.get("output_tokens", 0),
            "runs": data.get("runs", 0),
            "runs_per_model": data.get("runs_per_model", 0),
        })
    
    # Display detailed results
    for metrics in model_metrics:
        print(f"✅ {metrics['name']}")
        print(f"   Model ID: {metrics['model_id']}")
        print(f"   Successful Runs: {metrics['runs']}/{metrics['runs_per_model']}")
        print(f"   \n")
        print(f"   Average Metrics (warm runs):")
        print(f"     Input Tokens:  {metrics['input_tokens']:.0f}")
        print(f"     Output Tokens: {metrics['output_tokens']:.0f}")
        print(f"     LLM Latency:   {metrics['llm_latency_ms']:.0f}ms")
        print(f"     Total Latency: {metrics['total_latency_s']:.2f}s")
        print(f"   \n")
        print(f"   Average Cost:")
        print(f"     Total:  ${metrics['cost']:.6f}")
        print(f"\n")
    
    # Cost comparison
    print("=" * 80)
    print("COST COMPARISON")
    print("=" * 80 + "\n")
    
    sorted_by_cost = sorted(model_metrics, key=lambda x: x["cost"])
    cheapest = sorted_by_cost[0]
    
    for metrics in sorted_by_cost:
        cost_ratio = metrics["cost"] / cheapest["cost"] if cheapest["cost"] > 0 else 1.0
        print(f"{metrics['name']:25s} ${metrics['cost']:10.6f}  ({cost_ratio:.1f}x)")
    
    # Latency comparison
    print("\n" + "=" * 80)
    print("LATENCY COMPARISON (LLM only, warm runs)")
    print("=" * 80 + "\n")
    
    sorted_by_latency = sorted(model_metrics, key=lambda x: x["llm_latency_ms"])
    fastest = sorted_by_latency[0]
    
    for metrics in sorted_by_latency:
        latency_ratio = metrics["llm_latency_ms"] / fastest["llm_latency_ms"] if fastest["llm_latency_ms"] > 0 else 1.0
        print(f"{metrics['name']:25s} {metrics['llm_latency_ms']:6.0f}ms  ({latency_ratio:.2f}x)")
    
    # Total latency comparison
    print("\n" + "=" * 80)
    print("TOTAL LATENCY COMPARISON (end-to-end)")
    print("=" * 80 + "\n")
    
    sorted_by_total = sorted(model_metrics, key=lambda x: x["total_latency_s"])
    fastest_total = sorted_by_total[0]
    
    for metrics in sorted_by_total:
        total_ratio = metrics["total_latency_s"] / fastest_total["total_latency_s"] if fastest_total["total_latency_s"] > 0 else 1.0
        print(f"{metrics['name']:25s} {metrics['total_latency_s']:5.2f}s  ({total_ratio:.2f}x)")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80 + "\n")
    
    print(f"🏆 Fastest LLM: {fastest['name']} ({fastest['llm_latency_ms']:.0f}ms)")
    print(f"💰 Cheapest: {cheapest['name']} (${cheapest['cost']:.6f})")
    print(f"⚡ Fastest Total: {fastest_total['name']} ({fastest_total['total_latency_s']:.2f}s)")
    
    # Save comparison to file
    comparison_file = OUTPUT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_llm_comparison.txt"
    with open(comparison_file, 'w') as f:
        f.write("LLM Model Benchmark Comparison\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Models compared: {len(model_metrics)}\n\n")
        
        # Write all the comparison data
        # (Same content as printed above)
    
    print(f"\n💾 Comparison saved to: {comparison_file}")


def main():
    """Main entry point"""
    print("\n🔍 Searching for benchmark files...\n")
    
    # Find benchmark files
    benchmark_files = find_benchmark_files()
    
    if not benchmark_files:
        print("❌ No benchmark files found!")
        print(f"\n   Expected files in: {OUTPUT_DIR}")
        print("   Format: {timestamp}_{model_name}_benchmark.json")
        print("\n   Example filenames:")
        print("     - 20251125_120000_claude_sonnet_4_benchmark.json")
        print("     - 20251125_120000_amazon_nova_micro_benchmark.json")
        print("     - 20251125_120000_claude_haiku_3.5_benchmark.json")
        print("\n   Run benchmark_llm_models.py for each model first!")
        return
    
    print(f"✅ Found {len(benchmark_files)} benchmark file(s):\n")
    for model_key, filepath in benchmark_files.items():
        model_name = MODEL_DISPLAY_NAMES.get(model_key, model_key)
        print(f"   - {model_name}: {filepath.name}")
    
    # Load all benchmarks
    benchmarks = {}
    for model_key, filepath in benchmark_files.items():
        data = load_benchmark(filepath)
        if data:
            benchmarks[model_key] = data
    
    if not benchmarks:
        print("\n❌ Failed to load any benchmark files!")
        return
    
    # Compare benchmarks
    compare_benchmarks(benchmarks)


if __name__ == "__main__":
    main()


# LLM Model Benchmark Guide

## Overview
This benchmark compares three LLM models on the drug search API for:
- **Latency** (response time)
- **Cost** (per query)
- **Accuracy** (vs Claude Sonnet 4 ground truth)

## Models Being Tested
1. **Claude Sonnet 4** (Ground Truth)
   - Model ID: `us.anthropic.claude-sonnet-4-20250514-v1:0`
   - Cost: $3.00 input / $15.00 output (per 1M tokens)

2. **Amazon Nova Micro**
   - Model ID: `us.amazon.nova-micro-v1:0`
   - Cost: $0.035 input / $0.14 output (per 1M tokens)

3. **Claude Haiku 3.5**
   - Model ID: `us.anthropic.claude-3-5-haiku-20241022-v2:0`
   - Cost: $0.80 input / $4.00 output (per 1M tokens)

## Test Query
```
tastosterne 200 mg vial
```

## How to Run

### Prerequisites
The Lambda must already be deployed with the model you want to test.

### Run Benchmark
```bash
python3 scripts/benchmark_llm_models.py
```

The script will automatically:
1. Run each model **3 times** (first run = cold start, next 2 = warm)
2. Test Claude Sonnet 4 first (establishes ground truth)
3. Test Amazon Nova Micro (compares to ground truth)
4. Test Claude Haiku 3.5 (compares to ground truth)
5. Calculate averages **excluding cold start** for fair comparison
6. Save results to `.output/` with timestamp

**Note**: The script tests whatever model is currently deployed. Since our Lambda is currently on Claude Sonnet 4, it will test that model 3 times, showing you the difference between cold start and warm runs with caching.

## Output Files
- `{session_id}_llm_benchmark.json` - Full results (JSON)
- `{session_id}_llm_benchmark_summary.txt` - Human-readable summary

## Accuracy Metrics
The benchmark compares:
- ✓ Search terms extracted
- ✓ Expanded query text
- ✓ Dosage form filter
- ✓ Strength filter

100% accuracy = all 4 match ground truth

## Actual Results (Query: "tastosterne 200 mg vial")
**Warm Run Averages** (1116 input, 68 output tokens):
- **Amazon Nova Micro**: $0.000049 (1.0x baseline) - 1997ms latency
- **Claude Haiku 3.5**: $0.001165 (24x more expensive) - 1645ms latency ⚡ **FASTEST**
- **Claude Sonnet 4**: $0.004368 (89x more expensive) - 2394ms latency

**Accuracy**: Nova Micro and Haiku 3.5 both achieved **100% accuracy** vs Claude Sonnet 4!

**Key Findings**:
- 🏆 **Nova Micro is 89x cheaper** than Claude Sonnet 4 with same accuracy
- ⚡ **Haiku 3.5 is fastest** (1645ms) but 24x more expensive than Nova
- 🎯 **All models achieved 100% accuracy** on this drug search query
- ❄️ Cold start adds ~2-3 seconds of latency (first run)

## Notes
- All models use US cross-region inference endpoints for best latency
- The Lambda must be redeployed after each model change
- Results are saved with session ID and timestamp for comparison


# LLM Model Comparison Guide

**Purpose:** Testing different LLMs (Claude vs Nova) for optimal performance and cost  
**Date:** 2025-11-15

---

## 🎯 How to Swap Models (3 Methods)

### **Method 1: Change DEFAULT_LLM_MODEL Variable (Recommended for Testing)**

**File:** `packages/core/src/config/llm_config.py`

```python
# Line 48 - CHANGE THIS SINGLE VARIABLE:
DEFAULT_LLM_MODEL = LLMModel.CLAUDE_SONNET_4  # Current

# To test Nova Pro:
DEFAULT_LLM_MODEL = LLMModel.NOVA_PRO

# To test Nova Lite:
DEFAULT_LLM_MODEL = LLMModel.NOVA_LITE

# To test Nova Micro:
DEFAULT_LLM_MODEL = LLMModel.NOVA_MICRO
```

**That's it!** All LLM calls automatically use the new model.

### **Method 2: Environment Variable (Recommended for Production)**

Set `BEDROCK_INFERENCE_PROFILE` environment variable:

```bash
# Development
export BEDROCK_INFERENCE_PROFILE="us.amazon.nova-lite-v1:0"

# Or in .env file:
BEDROCK_INFERENCE_PROFILE=us.amazon.nova-lite-v1:0
```

### **Method 3: Per-Environment Configuration**

**Development (.env.development):**
```bash
BEDROCK_INFERENCE_PROFILE=us.amazon.nova-lite-v1:0  # Fast, cheap for dev
```

**Production (.env.production):**
```bash
BEDROCK_INFERENCE_PROFILE=us.anthropic.claude-sonnet-4-0  # Best quality
```

---

## 📊 Model Comparison Table

| Model | Provider | Input $/1M | Output $/1M | Speed | Context | Prompt Caching | Best For |
|-------|----------|------------|-------------|-------|---------|----------------|----------|
| **Claude Sonnet 4** | Anthropic | $3.00 | $15.00 | Slow | 200K | ✅ 90% discount | Complex medical reasoning |
| **Claude Sonnet 3.5** | Anthropic | $3.00 | $15.00 | Medium | 200K | ✅ 90% discount | Similar to Sonnet 4 |
| **Claude Haiku 3.5** | Anthropic | $0.80 | $4.00 | Fast | 200K | ✅ 90% discount | Simple tasks, 75% cheaper |
| **Nova Pro** | AWS | $0.80 | $3.20 | Medium | 300K | ❓ Check docs | Good quality, 75% cheaper |
| **Nova Lite** | AWS | $0.06 | $0.24 | Very Fast | 300K | ❓ Check docs | Simple queries, **95% cheaper** |
| **Nova Micro** | AWS | $0.035 | $0.14 | Fastest | 128K | ❓ Check docs | Classification, **98% cheaper** |

**Key Insights:**
- **Nova Lite is 50x cheaper** than Claude Sonnet 4 for input tokens
- Nova models have **300K context** (vs Claude's 200K)
- Claude has prompt caching (90% discount), Nova caching TBD
- Claude better for complex medical reasoning, Nova better for simple tasks

---

## 💰 Cost Comparison Examples

### **Scenario: Drug Query Expansion (typical use case)**
- **Input:** 200 tokens (user query + system prompt)
- **Output:** 50 tokens (expanded query)

| Model | Cost per Query | Cost per 1000 Queries | vs Sonnet 4 |
|-------|----------------|----------------------|-------------|
| Claude Sonnet 4 | $0.00135 | $1.35 | Baseline |
| Claude Sonnet 4 (50% cache) | $0.00090 | $0.90 | **33% cheaper** |
| Nova Pro | $0.00032 | $0.32 | **76% cheaper** |
| Nova Lite | $0.00024 | $0.024 | **98% cheaper** |
| Nova Micro | $0.00014 | $0.014 | **99% cheaper** |

**At 10,000 queries/day:**
- Claude Sonnet 4: **$13.50/day** ($405/month)
- Nova Lite: **$0.24/day** ($7.20/month)
- **Savings: $397.80/month (98%!)**

### **Scenario: Complex Medical Analysis**
- **Input:** 1000 tokens (patient history, drug interactions)
- **Output:** 500 tokens (detailed analysis)

| Model | Cost per Query | Quality | Recommendation |
|-------|----------------|---------|----------------|
| Claude Sonnet 4 | $0.01425 | ⭐⭐⭐⭐⭐ | Use for complex cases |
| Nova Pro | $0.00240 | ⭐⭐⭐⭐ | Good alternative |
| Nova Lite | $0.00018 | ⭐⭐⭐ | Too simple |

---

## 🧪 Testing Strategy

### **Phase 1: Baseline (Current - Week 4)**
```python
DEFAULT_LLM_MODEL = LLMModel.CLAUDE_SONNET_4
```
- Establish quality baseline
- Track metrics (accuracy, latency, cost)
- User acceptance testing

### **Phase 2: Nova Lite Testing (Week 5)**
```python
DEFAULT_LLM_MODEL = LLMModel.NOVA_LITE
```
- Test with same queries
- Compare quality vs Claude
- Measure latency improvement
- Calculate cost savings
- **Decision:** Keep or revert based on quality

### **Phase 3: Hybrid Approach (Week 6 - If Needed)**
```python
# Simple queries → Nova Lite
if query_complexity == "simple":
    model = LLMModel.NOVA_LITE
# Complex queries → Claude Sonnet 4
else:
    model = LLMModel.CLAUDE_SONNET_4
```

---

## 📋 Testing Checklist

### **Before Switching Models:**
- [ ] Document current baseline metrics
  - [ ] Average latency
  - [ ] Quality score (manual review)
  - [ ] Daily cost
  - [ ] User satisfaction
- [ ] Create test query set (50-100 representative queries)
- [ ] Set success criteria (e.g., "95% quality, <500ms latency")

### **After Switching Models:**
- [ ] Run same test query set
- [ ] Compare quality side-by-side
- [ ] Measure latency difference
- [ ] Calculate actual cost savings
- [ ] User acceptance testing (5-10 users)
- [ ] **Decision:** Keep, revert, or hybrid

### **Metrics to Track:**
```python
from packages.core.src.config.llm_config import call_claude_converse, estimate_cost

response = call_claude_converse(messages=[...])

metrics = {
    'model': response['model'],
    'latency_ms': response['latency_ms'],
    'input_tokens': response['metadata']['input_tokens'],
    'output_tokens': response['metadata']['output_tokens'],
    'cost_estimate': estimate_cost(
        input_tokens=response['metadata']['input_tokens'],
        output_tokens=response['metadata']['output_tokens']
    )
}

# Log to CloudWatch for analysis
cloudwatch.put_metric_data(...)
```

---

## 🎯 Recommended Approach

### **Start with Quality (Week 4-5):**
```python
DEFAULT_LLM_MODEL = LLMModel.CLAUDE_SONNET_4
```
- Get system working
- Establish quality baseline
- User feedback

### **Optimize for Cost (Week 6+):**
```python
# Test in this order:
1. LLMModel.NOVA_LITE   # 98% cheaper, test first
2. LLMModel.NOVA_PRO    # If Lite quality insufficient
3. LLMModel.CLAUDE_HAIKU_3_5  # If need Anthropic quality but cheaper
```

### **Production Decision Matrix:**

| Query Type | Model | Reason |
|------------|-------|--------|
| Simple drug name expansion | Nova Lite | 98% cheaper, sufficient quality |
| Complex drug interaction | Claude Sonnet 4 | Needs medical reasoning |
| Classification (generic/brand) | Nova Micro | Fastest, cheapest |
| Contraindication analysis | Claude Sonnet 4 | Safety-critical |

---

## 🔧 Utility Functions

### **Get Model Pricing Info:**
```python
from packages.core.src.config.llm_config import LLMModel, get_model_info

# Compare all models
for model in [LLMModel.CLAUDE_SONNET_4, LLMModel.NOVA_LITE, LLMModel.NOVA_MICRO]:
    info = get_model_info(model)
    print(f"{info['name']}: ${info['input_price_per_1m']}/1M input tokens")
```

### **Estimate Query Cost:**
```python
from packages.core.src.config.llm_config import estimate_cost, LLMModel

# Compare costs for same query
claude_cost = estimate_cost(200, 50, LLMModel.CLAUDE_SONNET_4)
nova_cost = estimate_cost(200, 50, LLMModel.NOVA_LITE)

print(f"Claude: ${claude_cost['total']:.6f}")
print(f"Nova:   ${nova_cost['total']:.6f}")
print(f"Savings: {(1 - nova_cost['total']/claude_cost['total']) * 100:.1f}%")
```

---

## 📊 Expected Results

### **Nova Lite vs Claude Sonnet 4:**

**Advantages:**
- ✅ **98% cost reduction**
- ✅ **2-3x faster response**
- ✅ **300K context window** (vs 200K)
- ✅ AWS-native (better latency)

**Disadvantages:**
- ❌ Lower quality for complex reasoning
- ❌ No prompt caching (yet - check docs)
- ❌ Less proven for medical domain

**Best Use Cases for Nova Lite:**
- Drug name expansion (simple)
- Search query reformatting
- Simple classification tasks
- High-volume, low-complexity queries

**Keep Claude Sonnet 4 for:**
- Drug interaction analysis
- Contraindication checking
- Complex medical reasoning
- Safety-critical decisions

---

## ✅ Quick Start

**To test Nova Lite immediately:**

1. Open `packages/core/src/config/llm_config.py`
2. Change line 48:
   ```python
   DEFAULT_LLM_MODEL = LLMModel.NOVA_LITE
   ```
3. Restart your Lambda/application
4. **All LLM calls now use Nova Lite automatically**
5. Monitor quality and cost

**To revert:**
```python
DEFAULT_LLM_MODEL = LLMModel.CLAUDE_SONNET_4
```

---

**Status:** Ready for model comparison testing in Week 5-6  
**Recommendation:** Start with quality (Claude), optimize for cost (Nova) after validation  
**Expected Savings:** 90-98% cost reduction for simple queries


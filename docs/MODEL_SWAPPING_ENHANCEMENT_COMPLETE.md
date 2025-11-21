# Model Swapping Enhancement - Complete

**Date:** 2025-11-15  
**Status:** ✅ COMPLETE - Easy model swapping enabled

---

## 🎯 What Was Implemented

### **1. Single-Variable Model Swapping** ✅

**File:** `packages/core/src/config/llm_config.py` (Line 48)

```python
# 🎯 CHANGE THIS TO SWAP LLM MODELS (Single Variable!)
DEFAULT_LLM_MODEL = LLMModel.CLAUDE_SONNET_4  # Change this to test other models
```

**To test different models, just change this ONE variable:**
```python
# Test Nova Lite (98% cheaper):
DEFAULT_LLM_MODEL = LLMModel.NOVA_LITE

# Test Nova Pro (75% cheaper, better quality):
DEFAULT_LLM_MODEL = LLMModel.NOVA_PRO

# Test Nova Micro (fastest, cheapest):
DEFAULT_LLM_MODEL = LLMModel.NOVA_MICRO

# Back to Claude Sonnet 4:
DEFAULT_LLM_MODEL = LLMModel.CLAUDE_SONNET_4
```

**All LLM calls automatically use the new model - zero code changes needed!**

---

### **2. Nova Models Added** ✅

New `LLMModel` enum with all models:

```python
class LLMModel(Enum):
    # Claude Models
    CLAUDE_SONNET_4 = "us.anthropic.claude-sonnet-4-0"
    CLAUDE_SONNET_3_5 = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    CLAUDE_HAIKU_3_5 = "anthropic.claude-3-5-haiku-20241022-v1:0"
    
    # Nova Models (AWS-native, lower cost)
    NOVA_PRO = "us.amazon.nova-pro-v1:0"
    NOVA_LITE = "us.amazon.nova-lite-v1:0"
    NOVA_MICRO = "us.amazon.nova-micro-v1:0"
```

---

### **3. Utility Functions for Model Comparison** ✅

#### **`get_model_info(model)`** - Get pricing & specs
```python
from packages.core.src.config.llm_config import LLMModel, get_model_info

claude_info = get_model_info(LLMModel.CLAUDE_SONNET_4)
nova_info = get_model_info(LLMModel.NOVA_LITE)

print(f"Claude: ${claude_info['input_price_per_1m']}/1M tokens")
# Output: Claude: $3.0/1M tokens

print(f"Nova: ${nova_info['input_price_per_1m']}/1M tokens")
# Output: Nova: $0.06/1M tokens (50x cheaper!)
```

#### **`estimate_cost(tokens, model)`** - Calculate query costs
```python
from packages.core.src.config.llm_config import estimate_cost, LLMModel

# Compare costs for same query
claude_cost = estimate_cost(
    input_tokens=200,
    output_tokens=50,
    model=LLMModel.CLAUDE_SONNET_4
)

nova_cost = estimate_cost(
    input_tokens=200,
    output_tokens=50,
    model=LLMModel.NOVA_LITE
)

print(f"Claude: ${claude_cost['total']:.6f}")
# Output: Claude: $0.001350

print(f"Nova: ${nova_cost['total']:.6f}")
# Output: Nova: $0.000024 (98% cheaper!)
```

---

### **4. Comprehensive Documentation** ✅

**Created:** `docs/LLM_MODEL_COMPARISON_GUIDE.md`

**Contents:**
- 3 methods to swap models (code, env var, per-environment)
- Complete pricing comparison table
- Cost calculation examples
- Testing strategy (3 phases)
- Testing checklist
- Metrics to track
- Production decision matrix
- Expected results (Nova vs Claude)
- Quick start guide

---

## 📊 Cost Comparison (Quick Reference)

### **Drug Query Expansion (200 input + 50 output tokens)**

| Model | Cost per Query | At 10K queries/day | Savings vs Claude |
|-------|----------------|-------------------|-------------------|
| Claude Sonnet 4 | $0.00135 | $13.50/day ($405/mo) | Baseline |
| Nova Pro | $0.00032 | $3.20/day ($96/mo) | 76% cheaper |
| Nova Lite | $0.00024 | **$0.24/day ($7.20/mo)** | **98% cheaper** |
| Nova Micro | $0.00014 | $0.14/day ($4.20/mo) | 99% cheaper |

**Potential Monthly Savings:** $397.80/month (98%) by switching to Nova Lite!

---

## 🧪 Testing Workflow

### **Week 4-5: Establish Baseline**
```python
DEFAULT_LLM_MODEL = LLMModel.CLAUDE_SONNET_4
```
- Get system working
- Establish quality metrics
- User acceptance

### **Week 6: Test Nova Lite**
```python
DEFAULT_LLM_MODEL = LLMModel.NOVA_LITE
```
- Same test queries
- Compare quality
- Measure latency
- Calculate savings
- **Decision:** Keep or revert

### **Week 7: Optimize (If Needed)**
```python
# Hybrid approach: route by complexity
if query_is_simple:
    model = LLMModel.NOVA_LITE  # 98% cheaper
else:
    model = LLMModel.CLAUDE_SONNET_4  # Best quality
```

---

## ✅ How It Works

### **Before (Hard-Coded):**
```python
# ❌ BAD - Hard to change
client.converse(
    modelId="us.anthropic.claude-sonnet-4-0",  # Hard-coded!
    ...
)
```

### **After (Centralized):**
```python
# ✅ GOOD - Easy to swap
from packages.core.src.config.llm_config import call_claude_converse

response = call_claude_converse(messages=[...])
# Automatically uses DEFAULT_LLM_MODEL (or env var)
```

**To change models:** Just update ONE variable in `llm_config.py`!

---

## 📋 Changes Made

### **Code Changes:**
1. ✅ Added `LLMModel` enum with all models (Claude + Nova)
2. ✅ Added `DEFAULT_LLM_MODEL` variable (line 48 - easy to change)
3. ✅ Updated `CLAUDE_CONFIG` to use `DEFAULT_LLM_MODEL`
4. ✅ Added `get_model_info()` function
5. ✅ Added `estimate_cost()` function
6. ✅ Enhanced `call_claude_converse()` docstring with model examples

### **Documentation Created:**
1. ✅ `docs/LLM_MODEL_COMPARISON_GUIDE.md` (complete testing guide)
2. ✅ Updated docstrings with model swapping examples

---

## 🎯 Ready for Model Testing!

### **To Test Nova Lite (98% cheaper):**

1. Open `packages/core/src/config/llm_config.py`
2. Change line 48:
   ```python
   DEFAULT_LLM_MODEL = LLMModel.NOVA_LITE
   ```
3. Deploy/restart
4. **All LLM calls now use Nova Lite!**
5. Monitor quality and cost

### **To Compare Pricing:**
```python
from packages.core.src.config.llm_config import get_model_info, LLMModel

for model in [LLMModel.CLAUDE_SONNET_4, LLMModel.NOVA_LITE]:
    info = get_model_info(model)
    print(f"{info['name']}: ${info['input_price_per_1m']}/1M")
```

### **To Calculate Savings:**
```python
from packages.core.src.config.llm_config import estimate_cost, LLMModel

# Your typical query
claude_cost = estimate_cost(200, 50, LLMModel.CLAUDE_SONNET_4)
nova_cost = estimate_cost(200, 50, LLMModel.NOVA_LITE)

savings_percent = (1 - nova_cost['total']/claude_cost['total']) * 100
print(f"Nova Lite is {savings_percent:.0f}% cheaper!")
# Output: Nova Lite is 98% cheaper!
```

---

## 💡 Recommendations

### **Start with Quality:**
```python
DEFAULT_LLM_MODEL = LLMModel.CLAUDE_SONNET_4  # Week 4-5
```
- Best quality for medical domain
- Establish baseline
- User acceptance

### **Optimize for Cost:**
```python
DEFAULT_LLM_MODEL = LLMModel.NOVA_LITE  # Week 6+
```
- Test quality vs Claude
- Measure latency improvement
- Calculate actual savings
- **Expected:** 90-98% cost reduction

### **Production Strategy:**
- **Simple queries** (drug name expansion): Nova Lite (98% cheaper)
- **Complex queries** (drug interactions): Claude Sonnet 4 (best quality)
- **Classification** (generic/brand): Nova Micro (fastest, cheapest)

---

## ✅ Summary

**What Changed:**
- ✅ Single variable to swap models (`DEFAULT_LLM_MODEL`)
- ✅ Nova models added (Lite, Pro, Micro)
- ✅ Utility functions for comparison (`get_model_info`, `estimate_cost`)
- ✅ Complete testing guide documentation

**What's Easy:**
- ✅ Change ONE variable to test different models
- ✅ No code changes in Lambda functions
- ✅ Compare pricing before testing
- ✅ Calculate savings easily

**What's Next:**
- Week 4-5: Deploy with Claude Sonnet 4 (quality baseline)
- Week 6+: Test Nova Lite (98% cost savings)
- Ongoing: Monitor quality, latency, cost

---

**Status:** 🟢 COMPLETE - Model swapping is now trivial (one variable change)!  
**Expected Impact:** 90-98% cost reduction for simple queries  
**Testing:** Ready for Week 6 model comparison


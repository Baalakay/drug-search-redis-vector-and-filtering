# LLM Quick Reference Card

**🚨 CRITICAL RULES - Print This and Keep at Your Desk! 🚨**

---

## ✅ DO THIS:

### **1. Use Converse API (Centralized Function)**
```python
from packages.core.src.config.llm_config import call_claude_converse

response = call_claude_converse(
    messages=[
        {"role": "user", "content": "Expand: blood pressure medication"}
    ]
)

if response['success']:
    print(response['content'])
    print(f"Tokens: {response['metadata']['input_tokens']}/{response['metadata']['output_tokens']}")
    print(f"Latency: {response['latency_ms']}ms")
```

### **2. Import Config, Never Hard-Code**
```python
from packages.core.src.config.llm_config import (
    get_llm_config,
    get_embedding_config,
    ClaudeModel,
    TitanModel
)

config = get_llm_config()  # Get current model from env
```

### **3. Return Complete Metrics**
```python
return {
    'success': True,
    'content': content,
    'usage': usage,
    'model': config["model_id"],
    'metadata': {
        'input_tokens': usage.get('inputTokens', 0),
        'output_tokens': usage.get('outputTokens', 0),
        'latency_ms': latency_ms
    }
}
```

---

## ❌ NEVER DO THIS:

### **1. NEVER Use invoke_model() for Claude**
```python
# ❌ WRONG - No prompt caching!
response = client.invoke_model(
    modelId="anthropic.claude-sonnet-4-0",
    body=json.dumps({"prompt": "..."})
)
```

### **2. NEVER Hard-Code Model IDs**
```python
# ❌ WRONG
MODEL_ID = "us.anthropic.claude-sonnet-4-0"
TITAN_MODEL = "amazon.titan-embed-text-v2:0"
```

### **3. NEVER Return Just Text**
```python
# ❌ WRONG - Missing metrics!
return response['output']['message']['content'][0]['text']
```

---

## 📋 Pre-Deployment Checklist

Before deploying ANY Lambda with LLM calls:

- [ ] Uses `call_claude_converse()` from `llm_config.py`
- [ ] No `invoke_model()` calls (except for embeddings)
- [ ] No hard-coded model IDs anywhere
- [ ] Returns complete metrics (tokens + latency)
- [ ] Handles errors gracefully
- [ ] Logs metrics to CloudWatch
- [ ] Has unit tests

---

## 📞 Quick Help

**File:** `packages/core/src/config/llm_config.py`  
**Docs:** `docs/LLM_USAGE_STANDARDS.md`  
**Pattern:** `memory-bank/systemPatterns.md` (line 3-50)

---

**Cost Impact:**
- ✅ Converse API with caching: **90% savings** on repeated prompts
- ❌ invoke_model(): **$0** savings (no caching)

**Why This Matters:**
- Saves ~$500-1000/month in production
- Enables cost monitoring
- Enables performance tracking
- Standardized error handling

---

_Print this card and pin it to your monitor!_


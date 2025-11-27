# Phase 6 Deployment Guide - Drug Search API

**Date:** 2025-11-15  
**Status:** ✅ READY FOR DEPLOYMENT  
**Prerequisites:** Read `docs/SST_UV_RECURRING_ISSUES.md` and `docs/SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md`

---

## 📁 Project Structure (Current)

```
functions/
├── __init__.py                    # ✅ Required
├── pyproject.toml                 # ✅ Package config
├── .python-version                # ✅ Should be "3.12"
└── src/
    ├── __init__.py                # ✅ Required
    ├── search_handler.py          # POST /search
    ├── alternatives_handler.py    # GET /drugs/{ndc}/alternatives
    └── drug_detail_handler.py     # GET /drugs/{ndc}

packages/core/src/config/
└── llm_config.py                  # Centralized LLM configuration

infra/
├── search-api.ts                  # SST Lambda functions (sst.aws.Function)
└── api.ts                         # API Gateway setup (Pulumi)
```

---

## 🚨 CRITICAL PRE-DEPLOYMENT CHECKLIST

### **Before EVERY deployment, verify:**

- [x] **Node.js v24.5.0** (SST VPC Lambda requirement)
  ```bash
  node --version  # Must be v24.5.0
  nvm use 24.5.0
  ```

- [ ] **functions/pyproject.toml exists** with `[build-system]`
  ```bash
  grep -q "\[build-system\]" functions/pyproject.toml && echo "✅" || echo "❌"
  ```

- [ ] **All \_\_init\_\_.py files exist**
  ```bash
  test -f functions/__init__.py && test -f functions/src/__init__.py && echo "✅" || echo "❌"
  ```

- [ ] **functions added to root workspace**
  ```bash
  grep -q "functions" pyproject.toml && echo "✅" || echo "❌"
  ```

- [ ] **No .venv in functions/ directory**
  ```bash
  test ! -d functions/.venv && echo "✅" || echo "❌ Remove it!"
  ```

- [ ] **.python-version files exist**
  ```bash
  test -f .python-version && test -f functions/.python-version && echo "✅" || echo "❌"
  ```

### **Clean Build Environment (ALWAYS do this first):**

```bash
# Clean UV artifacts
rm -rf functions/.venv functions/.pytest_cache functions/__pycache__
find functions -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Clear SST artifacts cache
rm -rf .sst/artifacts

# Regenerate lock file
cd functions && uv lock --upgrade && cd ..

echo "✅ Ready for deployment"
```

---

## 📝 Configuration Required

### **Environment Variables (Set in sst.config.ts or .env):**

```bash
# VPC Configuration
export VPC_ID="vpc-050fab8a9258195b7"
export PRIVATE_SUBNET_1="subnet-xxx"  # TODO: Get from network stack
export PRIVATE_SUBNET_2="subnet-yyy"  # TODO: Get from network stack
export LAMBDA_SECURITY_GROUP_ID="sg-xxx"  # TODO: Get from network stack

# Redis Configuration  
export REDIS_HOST="10.0.11.153"
export REDIS_PASSWORD="DAW-Redis-SecureAuth-2025"

# LLM Configuration (optional, has defaults)
export BEDROCK_INFERENCE_PROFILE="us.anthropic.claude-sonnet-4-0"
```

---

## 🚀 Deployment Steps

### **Step 1: Verify Prerequisites**

```bash
# Check Node.js version
node --version  # Must be v24.5.0

# Check Python version
python3 --version  # Should be 3.12.x

# Check UV is installed
uv --version
```

### **Step 2: Clean Build Environment**

```bash
# Run pre-deployment cleanup
./scripts/pre-deploy.sh

# OR manually:
rm -rf functions/.venv functions/.pytest_cache functions/__pycache__
find functions -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
rm -rf .sst/artifacts
cd functions && uv lock --upgrade && cd ..
```

### **Step 3: Verify Package Structure**

```bash
# Test UV export works
cd functions
uv export > /dev/null 2>&1 && echo "✅ UV export works" || echo "❌ UV export fails"
cd ..
```

### **Step 4: Deploy with SST**

```bash
# Deploy to development
npx sst deploy --stage dev

# Monitor deployment
# Watch for any errors in output
```

### **Step 5: Verify Deployment**

```bash
# Check Lambda functions exist
aws lambda list-functions --query 'Functions[?contains(FunctionName, `DrugSearch`)].FunctionName'

# Should return:
# - DrugSearch
# - DrugAlternatives  
# - DrugDetail

# Get API Gateway URL
npx sst deploy --stage dev | grep "api:"
```

### **Step 6: Test Endpoints**

```bash
# Set API URL
API_URL="https://xxx.execute-api.us-east-1.amazonaws.com/dev"

# Test search endpoint
curl -X POST "$API_URL/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "blood pressure medication", "max_results": 5}'

# Test alternatives endpoint
curl "$API_URL/drugs/00093111301/alternatives"

# Test drug detail endpoint
curl "$API_URL/drugs/00093111301"
```

---

## 🔧 Troubleshooting

### **Issue: "No module named 'daw_functions'"**

**Cause:** Handler path doesn't match package name in pyproject.toml

**Fix:**
1. Check `functions/pyproject.toml` - `name` field
2. Update handler paths in `infra/search-api.ts`:
   ```typescript
   // If name is "daw-functions", use:
   handler: "daw_functions.src.search_handler.lambda_handler"
   ```

### **Issue: "failed to run uv export: exit status 2"**

**Cause:** Functions not in workspace or .venv pollution

**Fix:**
```bash
# Add to root pyproject.toml:
[tool.uv.workspace]
members = [
    "packages/core",
    "functions",  # ← Must be here!
]

# Clean and rebuild
rm -rf functions/.venv
cd functions && uv lock --upgrade && cd ..
```

### **Issue: "RangeError: Invalid string length"**

**Cause:** Wrong Node.js version

**Fix:**
```bash
nvm install 24.5.0
nvm use 24.5.0
nvm alias default 24.5.0
echo "24.5.0" > .nvmrc
```

### **Issue: Lambda times out or can't reach Redis**

**Cause:** VPC/security group misconfiguration

**Fix:**
1. Verify Lambda is in correct private subnets
2. Verify security group allows Redis access (port 6379)
3. Check NAT Gateway for Bedrock access

---

## 📊 Expected Results

### **Search Endpoint Performance:**
- **Cold start:** ~3-5 seconds (first invocation)
- **Warm start:** ~285ms
  - Claude: ~150ms
  - Embeddings: ~120ms
  - Redis: ~15ms

### **Alternatives Endpoint Performance:**
- **Response time:** ~25ms
  - Redis lookup: ~5ms
  - Redis search: ~18ms

### **Drug Detail Endpoint Performance:**
- **Response time:** ~15ms
  - Redis lookup: ~5ms
  - Alternatives count: ~8ms

### **Costs (10K queries/day):**
- Claude Sonnet 4: ~$13.63/day ($408.90/month)
- Titan Embeddings: ~$0.13/day ($3.90/month)
- Lambda execution: ~$5/day ($150/month)
- **Total:** ~$562.80/month

---

## 🎯 Post-Deployment Verification

### **1. Check CloudWatch Logs:**

```bash
# Search function logs
aws logs tail /aws/lambda/DrugSearch --follow

# Check for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/DrugSearch \
  --filter-pattern "ERROR"
```

### **2. Check CloudWatch Metrics:**

```bash
# Function invocations
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=DrugSearch \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### **3. Test Error Handling:**

```bash
# Test invalid NDC
curl "$API_URL/drugs/INVALID" | jq

# Test missing query
curl -X POST "$API_URL/search" \
  -H "Content-Type: application/json" \
  -d '{}' | jq
```

---

## 📚 Reference Documentation

**MUST READ before deployment:**
1. `docs/SST_UV_RECURRING_ISSUES.md` - Known issues & solutions
2. `docs/SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md` - Complete deployment patterns
3. `docs/LLM_USAGE_STANDARDS.md` - LLM configuration standards
4. `docs/PHASE_6_API_IMPLEMENTATION_COMPLETE.md` - API implementation details

---

## ✅ Deployment Checklist Summary

Before running `npx sst deploy`:

- [ ] Node.js v24.5.0
- [ ] Clean build environment (no .venv in functions/)
- [ ] All __init__.py files exist
- [ ] functions in root workspace
- [ ] .python-version files exist
- [ ] UV export works (`cd functions && uv export`)
- [ ] Environment variables set (VPC, Redis, etc.)
- [ ] Read SST troubleshooting docs

---

**Status:** Ready for deployment following SST best practices  
**Next:** Configure environment variables and deploy to dev


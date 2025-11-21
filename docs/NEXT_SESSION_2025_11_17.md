# 🚀 Next Session - Start Here (2025-11-17)

**Status:** Phase 6 API is 100% complete – all three endpoints are healthy in dev.

---

## 📋 QUICK STATUS

### ✅ What's Working (DEPLOYED & TESTED)
- **API Gateway (dev):** https://9yb31qmdfa.execute-api.us-east-1.amazonaws.com
  - Old gateway `https://h9xppq0iog...` is superseded – all tests should target the new URL.
- **POST /search**
  - ✅ Working after handler/package realignment + Bedrock IAM expansion
  - `{"query":"insulin"}` now returns 20 results (phenobarbital set in sample data)
  - Latency (2025-11-18): ~10.5s total (Claude 7.5s, Titan 158ms, Redis 2.8s)
- **GET /drugs/{ndc}**
  - ✅ Working, returns Redis-enriched record with metrics
  - Sample NDC `49348055320`: 1.8s total latency
- **GET /drugs/{ndc}/alternatives**
  - ✅ Working, returns 45 options (43 generic / 2 brand) grouped by GCN_SEQNO
  - Latency: ~1.7s (Redis lookup dominated)
- **Redis:** 493,573 drugs still resident at 10.0.11.153 (LeanVec4x8 compression verified)

### 🔍 What Needs Attention
- **Post-deploy hardening**
  - Capture load/perf metrics for `POST /search` (p50/p95 targets)
  - Re-run semantic cache hit-rate script (cost tracking)
  - Document IAM changes + handler path fix in runbook (partially done below)
- **Phase 7 planning**
  - Define regression test suite + alerting
  - Prep prod-stage deploy checklist

---

## 🎯 YOUR FIRST TASK

Focus on **post-fix validation + prod readiness** rather than break/fix:

1. **Capture baseline metrics**
   - Run 5x POST /search requests (insulin, metformin, ozempic, “type 2 diabetes”, “cholesterol”)
   - Record Claude latency, Redis latency, total latency from response payload
   - Compare with goal (<7s total once Claude cache is hot)

2. **Semantic cache + Claude costs**
   - Inspect Redis semantic cache key count (`FT.SEARCH semantic_cache_idx * LIMIT 0 1`)
   - Confirm `llm_config` is logging `estimate_cost` output (SearchFunction CloudWatch)

3. **Phase 7 prep**
   - Draft test checklist (latency, error handling, throttling)
   - Identify any prod-only prerequisites (VPC endpoints, secrets rotation, etc.)

---

## 🖥️ FRONTEND DEMO & ENV VARS

- The React Router demo UI lives in `frontend/` and talks directly to the dev API Gateway.
- Run it locally with port forwarding: `cd frontend && PORT=4173 npm run dev -- --host 0.0.0.0`
  - When developing from AWS WorkSpaces, forward port `4173` from the EC2 devcontainer to your desktop (VS Code Ports tab or `ssh -L 4173:127.0.0.1:4173 <devcontainer>`), then open `http://localhost:4173`.
- `DrugSearch` reads the backend URL from `VITE_SEARCH_API_URL`. If unset, it defaults to `https://9yb31qmdfa.execute-api.us-east-1.amazonaws.com`.
  - Example: create `frontend/.env` with `VITE_SEARCH_API_URL=https://9yb31qmdfa.execute-api.us-east-1.amazonaws.com` for dev, or point to a prod stage later.
  - Restart `npm run dev` after changing the env var.

---

## 🔑 CRITICAL INFORMATION

### API Gateway
- **URL:** https://9yb31qmdfa.execute-api.us-east-1.amazonaws.com
- **Region:** us-east-1
- **Stage:** dev

### Lambda Functions
- **SearchFunction:** `DAW-dev-SearchFunctionFunction-zwvsszso` (latest) ✅
- **AlternativesFunction:** `DAW-dev-AlternativesFunctionFunction-smtcvcww` ✅
- **DrugDetailFunction:** `DAW-dev-DrugDetailFunctionFunction-dvsfxkzt` ✅
- **DrugSync:** `DAW-DrugSync-dev` ✅

### Redis
- **Instance ID:** i-0aad9fc4ba71454fa
- **IP:** 10.0.11.153
- **Port:** 6379
- **Password:** DAW-Redis-SecureAuth-2025
- **Data:** 493,573 drugs with LeanVec4x8 embeddings
- **Key Format:** `drug:49348055320` (11-digit NDC)

### Aurora MySQL
- **Endpoint:** daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com
- **Database:** fdb
- **Username:** dawadmin
- **Password:** (stored in Secrets Manager `DAW-DB-Password-dev`)

### Valid Test NDCs (Use These!)
- `49348055320` - SM MINERAL OIL ENEMA (tested, works)
- `00228214310` - (from Redis keys)
- `35046000751` - (from Redis keys)
- `63162051830` - (from Redis keys)

---

## 🚨 CRITICAL LESSONS FROM THIS SESSION

### 1. Handler Packaging Lessons (Issue #0)
*Still valid – documenting the fix for future reference.*

- ✅ Correct format (matches `functions/pyproject.toml`):  
  `handler: "daw_functions/src/search_handler.lambda_handler"`
- ❌ Old/broken format:  
  `handler: "functions/src/search_handler.lambda_handler"`

SST packages the entire `functions` project (pyproject `name="daw-functions"`). Using dotted module paths caused Lambda to look for a non-existent `functions` package, leading to `Runtime.ImportModuleError`.

### 2. Bedrock IAM Alignment
- SearchFunction role needed explicit `bedrock:Converse*` + inference profile ARNs
- Added both regional model ARNs (`arn:aws:bedrock:us-east-1::foundation-model/...`) and the account-scoped inference profile (`arn:aws:bedrock:us-east-1:750389970429:inference-profile/*`)
- After redeploy, Bedrock calls succeed (see CloudWatch metrics block in SearchFunction logs)

### 3. State Hygiene
Same guidance as before:
```bash
npx sst refresh --stage dev   # whenever AWS resources are touched manually
npx sst deploy --stage dev    # never skip deploy via SST
```

### 4. Test Data Verification
**NEVER assume test data exists – always verify:**
```bash
# Get actual NDCs from Redis
aws ssm send-command --instance-ids i-0aad9fc4ba71454fa \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["redis-cli -a DAW-Redis-SecureAuth-2025 --no-auth-warning KEYS '\''drug:*'\'' | head -10"]' \
  --query 'Command.CommandId' --output text

# Wait 3 seconds then get results
aws ssm get-command-invocation --command-id <COMMAND_ID> --instance-id i-0aad9fc4ba71454fa --query 'StandardOutputContent' --output text
```

---

## 📁 KEY FILES TO REFERENCE

### Infrastructure (All Correct)
- `infra/search-api.ts` - API Gateway + Lambda definitions (handlers fixed)
- `infra/sync.ts` - DrugSync Lambda (handler fixed)
- `infra/network.ts` - VPC with all resources imported
- `infra/database.ts` - DB subnet group imported
- `sst.config.ts` - Redis hard-coded (NOT managed by SST)

### Lambda Handlers
- `functions/src/search_handler.py` ⚠️ (needs debugging)
- `functions/src/alternatives_handler.py` ✅
- `functions/src/drug_detail_handler.py` ✅
- `functions/src/handlers/drug_loader.py` ✅

### Python Package Config
- `functions/pyproject.toml` - Package name: `daw-functions` (becomes `daw_functions`)
- `functions/__init__.py` - Required
- `functions/src/__init__.py` - Required
- `functions/src/config/__init__.py` - Empty (no imports!)

### Configuration
- `functions/src/config/llm_config.py` - LLM config (moved from packages/core)
- LLM Model: Claude Sonnet 4 (global.anthropic.claude-sonnet-4-20250514-v1:0)
- Bedrock Region: us-east-1

### Documentation
- `memory-bank/progress.md` - Updated to 100% complete (Phase 6)
- `docs/PHASE_6_DEPLOYMENT_SUCCESS.md` - Full deployment story
- `docs/SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md` - SST patterns & solutions
- `docs/SST_UV_RECURRING_ISSUES.md` - Known issues & fixes

---

## 🧪 TESTING COMMANDS

### Test Drug Detail (Working)
```bash
curl -s https://9yb31qmdfa.execute-api.us-east-1.amazonaws.com/drugs/49348055320 | jq '.'
```

**Expected:** Full drug details with metrics

### Test Alternatives (Working)
```bash
curl -s https://9yb31qmdfa.execute-api.us-east-1.amazonaws.com/drugs/49348055320/alternatives | jq '.'
```

**Expected:** 45 alternatives (43 generic, 2 brand)

### Test Search (Working)
```bash
curl -X POST https://9yb31qmdfa.execute-api.us-east-1.amazonaws.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "insulin"}' | jq '.'
```

**Expected Result:** 
```json
{
  "success": true,
  "results": [...],
  "metrics": {
    "total_latency_ms": 10476.58,
    "claude": {...},
    "embedding": {...},
    "redis": {...}
  }
}
```

---

## 🔍 DEBUGGING SEARCH ENDPOINT

### Likely Issues (Priority Order)

1. **Bedrock Permissions**
   - Check if Lambda role has `bedrock:InvokeModel` permission
   - Check if the inference profile ID is correct
   ```bash
   aws lambda get-function-configuration --function-name DAW-dev-SearchFunctionFunction-urmsawfv --query 'Environment.Variables.BEDROCK_INFERENCE_PROFILE' --output text
   ```

2. **LLM Config Import**
   - Verify `llm_config.py` is at `functions/src/config/llm_config.py`
   - Check imports in `search_handler.py`

3. **Redis Connection**
   - Verify environment variables (REDIS_HOST, REDIS_PORT, REDIS_PASSWORD)
   - Check VPC connectivity

4. **Claude Message Format**
   - The Converse API requires specific message format
   - Content must be list of dicts: `[{"text": "..."}]`

### Check Lambda Environment
```bash
aws lambda get-function-configuration --function-name DAW-dev-SearchFunctionFunction-urmsawfv --query 'Environment.Variables' --output json
```

### Invoke Lambda Directly
```bash
aws lambda invoke \
  --function-name DAW-dev-SearchFunctionFunction-urmsawfv \
  --payload '{"body":"{\"query\":\"insulin\"}"}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/search_test.json && cat /tmp/search_test.json | jq '.'
```

---

## 📊 DEPLOYMENT HISTORY SUMMARY

### What Happened (Chronological)
1. ✅ All infrastructure deployed via SST
2. ✅ Redis data preserved (493,573 drugs safe)
3. ✅ All infrastructure imported via Pulumi `import` flags (Option 1)
4. ❌ Lambda handlers initially wrong (file paths vs module paths)
5. ⚠️ Accidentally made manual AWS CLI handler updates (violated SST rule)
6. ✅ Fixed with `sst refresh` (synced state)
7. ✅ Corrected all handler paths to `daw_functions.src.*` format
8. ✅ Deployed successfully (multiple `sst deploy` + `sst refresh` cycles)
9. ✅ Cleared lingering Lambda/log group conflicts by deleting stale resources + S3 state cache
10. ✅ Search endpoint fixed (handler path corrected, Bedrock IAM expanded, redeployed)

### Key Decisions
- **Used Pulumi Import:** Added `import` flags to existing resources
- **Manual Changes Required Refresh:** Used `sst refresh` to sync state
- **Handler Format:** Module paths matching pyproject.toml package name
- **Redis Not Managed by SST:** Hard-coded IP to prevent data loss

---

## 🎯 SUCCESS CRITERIA

### Phase 6 Complete ✅
- [x] All 3 endpoints working in dev
- [x] Search endpoint returns results with Claude preprocessing + Titan embeddings
- [x] Metrics tracked (Claude/Titan/Redis latency, Claude token counts, cost estimate)
- [x] CloudWatch logs clean (no ImportModuleError / AccessDenied)
- [x] Post-deploy smoke tests captured (detail, alternatives, search)

### Next Phase (Phase 7 Prep):
- Performance & load testing (p50/p95 latency targets, concurrent requests)
- Claude cost optimization (semantic cache validation, Nova Lite experiment)
- Aurora enrichment enhancements (pricing) – optional Phase 6.5 deliverable

---

## 💬 TEXT TO START NEW AGENT WITH

```
Phase 6 API is fully deployed with all three endpoints working in dev. Your focus is
post-fix validation (latency/cost baselines) and Phase 7 readiness tasks. Reference
docs/NEXT_SESSION_2025_11_17.md for the full handoff, and keep following the SST docs
(SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md + SST_UV_RECURRING_ISSUES.md) before touching infra.

CRITICAL REMINDERS:
- NEVER make manual AWS changes outside SST; if you must, immediately run `npx sst refresh --stage dev`
- Handler paths must stay as `daw_functions/src/...`
- Semantic cache + Claude cost metrics live in SearchFunction logs; capture them when you run perf tests

Working test NDC: 49348055320  
API Gateway (dev): https://9yb31qmdfa.execute-api.us-east-1.amazonaws.com
```

---

## 📚 REFERENCE DOCUMENTATION

**Must Read Before Debugging:**
1. `docs/SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md` - Complete SST patterns
2. `docs/SST_UV_RECURRING_ISSUES.md` - Known issues & solutions
3. `docs/LLM_USAGE_STANDARDS.md` - Bedrock Converse API requirements
4. `memory-bank/progress.md` - Current project status

**Supporting Docs:**
- `docs/PHASE_6_DEPLOYMENT_SUCCESS.md` - Deployment story
- `docs/REDIS_SCHEMA_DESIGN.md` - Redis data structure
- `docs/FDB_DATABASE_SCHEMA_REFERENCE.md` - Database schema

---

**Session End Time:** 2025-11-18 19:45 UTC  
**Next Session Goal:** Capture latency/cost baselines + outline Phase 7 test plan  
**Current Blocker:** None – continue with validation/optimization tasks


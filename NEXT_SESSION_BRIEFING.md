# Next Session Briefing for Cursor Agent

**Date:** 2025-11-06  
**Project:** DAW Drug Search System  
**Current Phase:** DEVELOPMENT - Phase 1 Infrastructure Complete (75%)  
**Framework:** CursorRIPER (RIPER workflow active)

---

## 🎯 Quick Context

You're working on **DAW**, a highly accurate drug search system for an e-prescribing platform. The customer (Aaron) requires:
- **Redis quantization** (LeanVec4x8 for 3x memory reduction - using Redis Stack 8.2.2 on EC2)
- **Hybrid search** (vector + filter simultaneously)
- **Medical terminology** handling (abbreviations, misspellings)
- **AWS-only** deployment

---

## ✅ What's Already Done (Phase 1 - 75%)

### Infrastructure Code (100% Complete)
All infrastructure is coded and ready to deploy:

**Files Created:**
- ✅ `infra/network.ts` - VPC, subnets, NAT, security groups
- ✅ `infra/database.ts` - Aurora PostgreSQL Serverless v2
- ✅ `infra/redis-ec2.ts` - **Redis Stack 8.2.2 on EC2 r7g.large** (ARM Graviton3)
- ✅ `sst.config.ts` - Main SST configuration
- ✅ `project.config.ts` - Stage-specific settings
- ✅ `packages/core/src/config/llm_config.py` - Centralized LLM config

**Key Decision:** Using **self-managed Redis Stack 8.2.2** on EC2 instead of ElastiCache because:
- ElastiCache only supports Redis 7.1 (no quantization)
- Need LeanVec4x8 compression (3x memory reduction)
- Need RediSearch module for hybrid search
- 16% cost savings ($104/month vs $124/month)

**Documentation Created:**
- ✅ `docs/REDIS_INFRASTRUCTURE_DECISION.md` - Complete technical analysis (show to Aaron)
- ✅ `docs/REDIS_DECISION_SUMMARY.md` - Executive summary (show to Aaron)
- ✅ `docs/IMPLEMENTATION_PLAN.md` - Complete implementation guide
- ✅ `docs/DEPLOYMENT_GUIDE.md` - Deployment instructions

---

## 🔄 What's Next (Phase 1 - Remaining 25%)

### Option A: Deploy Infrastructure Now
```bash
npx sst deploy --stage dev
```
**Time:** 15-20 minutes  
**Creates:** VPC, Aurora, Redis EC2, security groups, secrets

**Then:**
1. Import FDB data: `psql $DB_CONN < database/imports/fdb\ tables.sql`
2. Create indexes on key columns (NDC, GCN_SEQNO)
3. Verify connectivity

### Option B: Build Phase 2 First (Embedding Layer)
Continue coding before deploying. Build the embedding abstraction layer:

**Files to Create:**
1. `packages/core/src/embedding/base.py` - Abstract interface
2. `packages/core/src/embedding/titan.py` - Bedrock Titan impl
3. `packages/core/src/embedding/sapbert.py` - SageMaker SapBERT stub
4. `packages/core/src/embedding/__init__.py` - Factory pattern

---

## 🎨 Architecture Summary

```
User Query
    ↓
Claude Sonnet 4 (Bedrock Converse API)
  - Parse query
  - Correct spelling
  - Extract filters
  - Expand medical terms
    ↓
Titan Embeddings (Bedrock)
  - Convert to 1024-dim vector
    ↓
Redis Stack 8.2.2 (EC2 r7g.large)
  - HNSW index with LeanVec4x8 quantization
  - Hybrid search (vector + filters)
  - Returns top 20 drug IDs
    ↓
Aurora PostgreSQL
  - Batch fetch full drug details
  - FDB data enrichment
    ↓
API Response (JSON)
```

---

## 📋 Key Technical Constraints

### **CRITICAL: Always Follow These Rules**

1. **Use Converse API ONLY** (not InvokeModel)
   - All Claude calls use `bedrock.converse()`
   - Use global inference profile: `us.anthropic.claude-sonnet-4-0`

2. **Use Centralized Config** (no hard-coding)
   - Import from `packages/core/src/config/llm_config.py`
   - All model IDs, regions, params come from config
   - Never hard-code model IDs or regions

3. **Resource Naming** (DAW prefix, no auto-suffixes)
   - All resources start or end with "DAW"
   - Use raw Pulumi if SST adds auto-suffixes
   - Examples: `DAW-VPC`, `DAW-Aurora-Cluster`, `DAW-Redis-Server`

4. **SST + UV Best Practices** (critical to avoid errors)
   - Consult `docs/SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md`
   - Consult `docs/SST_UV_RECURRING_ISSUES.md`
   - Use `functions.src.*` import paths (not `src.*`)
   - Never delete `.venv` directory

5. **Python Package Structure**
   - Use `packages/core/src/` for shared code
   - Use `functions/` for Lambda handlers
   - Follow hatchling packaging (`pyproject.toml`)

---

## 📚 Key Files to Reference

### **Memory Bank** (Essential Context)
- `memory-bank/projectbrief.md` - Project goals, requirements
- `memory-bank/systemPatterns.md` - Architecture patterns
- `memory-bank/techContext.md` - Technology stack
- `memory-bank/activeContext.md` - Current work focus (THIS FILE - read it!)
- `memory-bank/progress.md` - What's done, what's left

### **Implementation Guides**
- `docs/IMPLEMENTATION_PLAN.md` - Complete week-by-week plan with code examples
- `docs/DEPLOYMENT_GUIDE.md` - How to deploy infrastructure
- `docs/REDIS_INFRASTRUCTURE_DECISION.md` - Redis architecture rationale

### **Technical References**
- `docs/SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md` - SST + Python best practices
- `docs/SST_UV_RECURRING_ISSUES.md` - Common UV/SST pitfalls

### **Infrastructure Code**
- `sst.config.ts` - Main SST app config
- `project.config.ts` - Stage settings
- `infra/network.ts` - VPC infrastructure
- `infra/database.ts` - Aurora RDS
- `infra/redis-ec2.ts` - Redis Stack 8.2.2

### **Configuration**
- `packages/core/src/config/llm_config.py` - **USE THIS FOR ALL LLM CALLS**

---

## 🚀 Recommended Next Steps

### Step 1: Review Context (5 minutes)
```bash
# Read these files to understand current state:
cat memory-bank/activeContext.md
cat memory-bank/progress.md
cat docs/REDIS_DECISION_SUMMARY.md
```

### Step 2: Choose Path
Ask the user:
> "Infrastructure code is complete. Should I:
> 
> **A) Deploy infrastructure to AWS now** (npx sst deploy --stage dev)
> 
> **B) Continue building Phase 2** (embedding abstraction layer)
>
> **C) Review the Redis decision docs** before proceeding?"

### Step 3: Execute
- If A: Deploy and verify
- If B: Create embedding layer
- If C: Present Redis docs to Aaron

---

## 💡 Important Notes

### Redis Decision (Show to Aaron)
We chose **Redis Stack 8.2.2 on EC2** instead of ElastiCache. See:
- `docs/REDIS_DECISION_SUMMARY.md` (2-page exec summary)
- `docs/REDIS_INFRASTRUCTURE_DECISION.md` (15-page technical deep dive)

**Key benefits:**
- ✅ LeanVec4x8 quantization (3x memory reduction)
- ✅ Hybrid vector + filter search
- ✅ 16% cost savings
- ✅ Latest Redis features (8.2.2)

### Customer (Aaron) Requirements
From transcript:
- Must use Redis with quantization (using Redis Stack 8.2.2 with LeanVec4x8 on EC2)
- Hybrid search (vector + filter simultaneously)
- Multi-species support (veterinary use case)
- Cost-conscious (minimize SageMaker initially)

### Technology Stack
- **LLM:** Claude Sonnet 4 (via Bedrock Converse API)
- **Embeddings:** Titan v2 (1024-dim) → Can upgrade to SapBERT later
- **Vector Store:** Redis Stack 8.2.2 with RediSearch + LeanVec4x8
- **Database:** Aurora PostgreSQL Serverless v2
- **Infrastructure:** SST v3 on AWS
- **Python:** 3.12 with UV package manager

---

## 🎯 Success Criteria

### Phase 1 Complete When:
- [ ] Infrastructure deployed to AWS
- [ ] Aurora accessible from Lambda
- [ ] Redis accessible from Lambda
- [ ] FDB data imported to Aurora
- [ ] Database indexes created

### Phase 2 Goals:
- [ ] Embedding abstraction layer complete
- [ ] Can generate embeddings with Titan
- [ ] Can switch to SapBERT via env variable
- [ ] Unit tests passing

---

## 🔧 Troubleshooting Quick Reference

**If SST deployment fails:**
- Check AWS credentials are configured
- Verify region is us-east-1
- Review CloudFormation events for errors

**If UV/Python issues:**
- Check `docs/SST_UV_RECURRING_ISSUES.md`
- Never delete `.venv` directory
- Use `functions.src.*` import paths

**If Redis issues:**
- Verify user-data script completed (check EC2 console)
- SSH into instance: `aws ssm start-session --target i-xxxxx`
- Check logs: `sudo journalctl -u redis-stack-server`

---

## 📞 Questions to Ask User

1. **"Should I deploy the infrastructure now, or continue building Phase 2?"**
2. **"Have you shared the Redis decision docs with Aaron for approval?"**
3. **"Do you want me to deploy to dev, staging, or both?"**

---

**Status:** Ready to proceed with Phase 1 deployment or Phase 2 development  
**Last Updated:** 2025-11-06  
**Current Mode:** EXECUTE (infrastructure complete) or PLAN (if moving to Phase 2)


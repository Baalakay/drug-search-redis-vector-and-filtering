# Next Session Briefing for Cursor Agent

**Date:** 2025-11-10  
**Project:** DAW Drug Search System  
**Current Phase:** DEVELOPMENT - Phase 1 Infrastructure COMPLETE ✅  
**Framework:** CursorRIPER (RIPER workflow active)

---

## 🎯 Quick Context

You're working on **DAW**, a highly accurate drug search system for an e-prescribing platform. The customer (Aaron) requires:
- **Redis quantization** (LeanVec4x8 for 3x memory reduction - using Redis Stack 8.2.2 on EC2)
- **Hybrid search** (vector + filter simultaneously)
- **Medical terminology** handling (abbreviations, misspellings)
- **AWS-only** deployment

---

## ✅ What's Already Done (Phase 1 - 100% COMPLETE)

### Infrastructure Deployed & Data Loaded ✅

**AWS Resources Created:**
- ✅ **VPC:** `vpc-050fab8a9258195b7` (public/private subnets, NAT Gateway)
- ✅ **Aurora MySQL 8.0:** `daw-aurora-dev` (aurora-mysql 8.0.39)
  - Endpoint: `daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com:3306`
  - Database: `fdb` (note: SQL file created its own database)
  - Credentials: `dawadmin` / `DawAdmin2025!SecurePass`
- ✅ **Redis Stack 8.2.2:** EC2 r7g.large (i-0ec914f45110b9b9c)
  - Internal IP: 10.0.11.245:6379
  - Ubuntu 22.04 with Redis Stack 8.2.2

**FDB Data Successfully Loaded:**
- ✅ **118 tables** imported (11.4M+ rows, ~835 MB total)
- ✅ **Key tables:**
  - `rnp2` - 11.4M rows (835 MB) - Drug products
  - `rndc14` - 464K rows (213 MB) - NDC codes with GCN mapping
  - `rxnconso` - 961K rows (212 MB) - RxNorm concepts
  - `rimkcs0_rxn_fdb_cs_lnk` - 833K rows (160 MB) - RxNorm-FDB links
- ✅ **Indexes verified:**
  - Primary key on NDC in rndc14
  - Index on GCN_SEQNO, LBLRID in rndc14
  - Composite primary key on rnp2
- ✅ **Query performance tested:**
  - NDC lookup: 0.02s (PRIMARY KEY)
  - GCN lookup: 0.03s (indexed)
  - Name search: 0.26s (LIKE on 464K rows)
  - RxNorm search: 0.14s

**Infrastructure Code Files:**
- ✅ `infra/network.ts` - VPC, subnets, NAT, security groups
- ✅ `infra/database.ts` - Aurora MySQL Serverless v2 (corrected from PostgreSQL)
- ✅ `infra/redis-ec2.ts` - Redis Stack 8.2.2 on EC2 r7g.large (ARM Graviton3)
- ✅ `sst.config.ts` - Main SST configuration
- ✅ `project.config.ts` - Stage-specific settings
- ✅ `packages/core/src/config/llm_config.py` - Centralized LLM config

**Key Decision:** Using **self-managed Redis Stack 8.2.2** on EC2 instead of ElastiCache because:
- ElastiCache only supports Redis 7.1 (no quantization)
- Need LeanVec4x8 compression (3x memory reduction)
- Need RediSearch module for hybrid search
- 16% cost savings ($104/month vs $124/month)

**Documentation Created:**
- ✅ `docs/REDIS_INFRASTRUCTURE_DECISION.md` - Complete technical analysis
- ✅ `docs/REDIS_DECISION_SUMMARY.md` - Executive summary
- ✅ `docs/DAW_ARCHITECTURE_OVERVIEW.md` - For Aaron (architecture patterns)
- ✅ `docs/IMPLEMENTATION_PLAN.md` - Complete implementation guide

**Critical Correction:** Changed from Aurora PostgreSQL to Aurora MySQL because FDB data dump is in MySQL format (backticks, LOCK TABLES syntax).

---

## 🔄 What's Next (Phase 2 - Embedding Layer)

### Phase 2: Build Embedding Abstraction Layer (0% Complete)
**Goal:** Swappable embedding models (Titan/SapBERT)

**Files to Create:**
1. `packages/core/src/embedding/base.py` - Abstract interface
2. `packages/core/src/embedding/titan.py` - Bedrock Titan implementation
3. `packages/core/src/embedding/sapbert.py` - SageMaker SapBERT (stub)
4. `packages/core/src/embedding/__init__.py` - Factory pattern
5. Unit tests for embedding abstraction

**Key Requirements:**
- Use centralized config from `packages/core/src/config/llm_config.py`
- No hard-coded model IDs or regions
- Environment variable switching (EMBEDDING_MODEL=titan or sapbert)
- Conforms to SST + UV best practices (see docs/SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md)

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
Aurora MySQL (`fdb` database)
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

6. **Database Connection**
   - Database name is `fdb` (not `daw`)
   - Connection: `mysql://dawadmin:DawAdmin2025!SecurePass@daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com:3306/fdb`

---

## 📚 Key Files to Reference

### **Memory Bank** (Essential Context)
- `memory-bank/projectbrief.md` - Project goals, requirements
- `memory-bank/systemPatterns.md` - Architecture patterns
- `memory-bank/techContext.md` - Technology stack
- `memory-bank/activeContext.md` - Current work focus
- `memory-bank/progress.md` - What's done, what's left

### **Implementation Guides**
- `docs/IMPLEMENTATION_PLAN.md` - Complete week-by-week plan with code examples
- `docs/DEPLOYMENT_GUIDE.md` - How to deploy infrastructure
- `docs/REDIS_INFRASTRUCTURE_DECISION.md` - Redis architecture rationale
- `docs/DAW_ARCHITECTURE_OVERVIEW.md` - For Aaron (human medical examples)

### **Technical References**
- `docs/SST_LAMBDA_MIGRATION_COMPLETE_GUIDE.md` - SST + Python best practices
- `docs/SST_UV_RECURRING_ISSUES.md` - Common UV/SST pitfalls

### **Infrastructure Code**
- `sst.config.ts` - Main SST app config
- `project.config.ts` - Stage settings
- `infra/network.ts` - VPC infrastructure
- `infra/database.ts` - Aurora MySQL
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
```

### Step 2: Begin Phase 2 (Embedding Layer)
Create the embedding abstraction layer with swappable models:

1. Create `packages/core/src/embedding/base.py` (abstract interface)
2. Create `packages/core/src/embedding/titan.py` (Bedrock Titan)
3. Create `packages/core/src/embedding/sapbert.py` (SageMaker stub)
4. Create `packages/core/src/embedding/__init__.py` (factory pattern)
5. Write unit tests

---

## 💡 Important Notes

### Database Structure
- **Database name:** `fdb` (not `daw` - SQL file created its own database)
- **Key tables:**
  - `rndc14` - NDC codes with GCN_SEQNO mapping
  - `rnp2` - Drug product information
  - `rxnconso` - RxNorm concept names
- **Indexes:** Already exist on NDC (primary key) and GCN_SEQNO

### Customer (Aaron) Requirements
From transcript:
- Must use Redis with quantization (✅ using Redis Stack 8.2.2 with LeanVec4x8 on EC2)
- Hybrid search (vector + filter simultaneously)
- Multi-species support (veterinary use case)
- Cost-conscious (minimize SageMaker initially)

### Technology Stack
- **LLM:** Claude Sonnet 4 (via Bedrock Converse API)
- **Embeddings:** Titan v2 (1024-dim) → Can upgrade to SapBERT later
- **Vector Store:** Redis Stack 8.2.2 with RediSearch + LeanVec4x8
- **Database:** Aurora MySQL 8.0 Serverless v2 (`fdb` database)
- **Infrastructure:** SST v3 on AWS
- **Python:** 3.12 with UV package manager

---

## 🎯 Success Criteria

### Phase 1 Complete ✅
- [x] Infrastructure deployed to AWS
- [x] Aurora accessible and data loaded
- [x] Redis deployed and running
- [x] FDB data imported (118 tables, 11.4M+ rows)
- [x] Database indexes verified
- [x] Query performance tested

### Phase 2 Goals:
- [ ] Embedding abstraction layer complete
- [ ] Can generate embeddings with Titan
- [ ] Can switch to SapBERT via env variable
- [ ] Unit tests passing

---

## 🔧 Infrastructure Details

### Aurora MySQL
- **Cluster:** `daw-aurora-dev`
- **Endpoint:** `daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com:3306`
- **Database:** `fdb`
- **Username:** `dawadmin`
- **Password:** `DawAdmin2025!SecurePass`
- **Engine:** aurora-mysql 8.0.39
- **Tables:** 118 (11.4M+ rows, ~835 MB)

### Redis EC2
- **Instance ID:** `i-0ec914f45110b9b9c`
- **Internal IP:** `10.0.11.245`
- **Port:** 6379
- **Version:** Redis Stack 8.2.2
- **OS:** Ubuntu 22.04
- **Instance Type:** r7g.large (ARM Graviton3)

### VPC
- **VPC ID:** `vpc-050fab8a9258195b7`
- **Region:** us-east-1
- **NAT Gateway:** Configured for Lambda → Bedrock access

---

## 📊 Project Progress

### Overall: 30% Complete
```
[######              ] 30%
```

- ✅ Planning & Architecture: 100%
- ✅ Infrastructure Code: 100%
- ✅ Infrastructure Deployment: 100%
- ✅ Data Load: 100%
- ⏳ Embedding Layer: 0%
- ⏳ Redis Setup: 0%
- ⏳ API Layer: 0%
- ⏳ Testing: 0%

---

**Status:** Ready to proceed with Phase 2 (Embedding Abstraction Layer)  
**Last Updated:** 2025-11-10  
**Current Mode:** PLAN → EXECUTE (ready to build Phase 2)

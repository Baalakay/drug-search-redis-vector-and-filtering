# Active Context: Current Work Focus

**Last Updated:** 2025-11-06  
**Current Phase:** DEVELOPMENT - Phase 1 Infrastructure Complete  
**Focus:** Infrastructure deployed, ready for Phase 2 (Embedding Layer)

---

## Current Sprint Focus

### ✅ Completed: Phase 1 Infrastructure (75% Complete)

**Architecture & Planning:**
- [x] Chose embedding model strategy (Titan start, SapBERT optional upgrade)
- [x] Defined hybrid search architecture (Redis Stack 8.2.2 with LeanVec4x8 quantization)
- [x] Clarified Claude Sonnet 4 role (query preprocessing with medical terminology)
- [x] Decided on data storage pattern (Redis + Aurora hybrid)
- [x] Created comprehensive implementation plan
- [x] Updated to use Converse API and centralized config
- [x] Documented all memory bank files

**Infrastructure Code Complete:**
- [x] VPC with public/private subnets (infra/network.ts)
- [x] Aurora MySQL Serverless v2 (infra/database.ts) - **CORRECTED:** Changed from PostgreSQL to MySQL to match FDB data format
- [x] Redis Stack 8.2.2 on EC2 r7g.large ARM Graviton3 (infra/redis-ec2.ts)
- [x] Security groups for Lambda, RDS, Redis
- [x] NAT Gateway for Lambda → Bedrock access
- [x] Secrets Manager for credentials
- [x] Parameter Store for connection strings
- [x] CloudWatch monitoring and alarms
- [x] All resources named with "DAW" prefix (no SST auto-suffixes)

**Documentation:**
- [x] Created REDIS_INFRASTRUCTURE_DECISION.md (technical deep dive for Aaron)
- [x] Created REDIS_DECISION_SUMMARY.md (executive summary for Aaron)
- [x] Updated DEPLOYMENT_GUIDE.md with EC2 Redis instructions
- [x] Comprehensive implementation plan (IMPLEMENTATION_PLAN.md)

### 🎯 Next Immediate Tasks

#### Phase 1 Status (95% Complete)
- [x] Deploy infrastructure to AWS (`npx sst deploy --stage dev`)
- [x] VPC, subnets, NAT Gateway deployed
- [x] Redis EC2 r7g.large deployed and running
- [x] ~~Aurora PostgreSQL deployed~~ **CORRECTED:** Switched to Aurora MySQL (FDB data is MySQL format)
- [x] Security groups configured (Redis→Aurora access added manually)
- [x] Data load script updated for MySQL client
- [ ] **IN PROGRESS:** Aurora MySQL cluster deploying (ETA: 5-10 min)
- [ ] Import FDB data to Aurora MySQL
- [ ] Create database indexes  
- [ ] Verify connectivity (Lambda → Aurora, Lambda → Redis)

#### Phase 2: Embedding Abstraction Layer (Next Priority)
**Goal:** Swappable embedding models (Titan/SapBERT)

**Files to create:**
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

## Recent Decisions & Rationale

### Decision Log (Last Session)

**2025-11-07: Aurora MySQL instead of PostgreSQL (Critical Correction)**
- **Reason:** FDB data dump is in MySQL format (backticks, LOCK TABLES syntax)
- **Impact:**
  - Must use Aurora MySQL 8.0 instead of PostgreSQL 15
  - Connection string changed from `postgresql://` to `mysql://`
  - Port changed from 5432 to 3306
  - Data load script updated to use `mysql` client instead of `psql`
- **Change:** Deleted PostgreSQL cluster, deploying MySQL cluster
- **Status:** 🔄 In Progress (MySQL cluster deploying)

**2025-11-06: Redis Stack 8.2.2 on EC2 r7g.large (Critical Decision)**
- **Reason:** AWS ElastiCache only supports Redis 7.1, no quantization support
- **Impact:** 
  - LeanVec4x8 quantization: 3x memory reduction (250 MB → 80 MB)
  - 16% cost savings ($124 → $104/month)
  - Full control over configuration
- **Change:** Replaced ElastiCache infrastructure with self-managed EC2
- **Documentation:** Created detailed decision doc for Aaron (docs/REDIS_INFRASTRUCTURE_DECISION.md)
- **Status:** ✅ Approved and implemented

**2025-11-06: Use Claude Sonnet 4 instead of Claude 3.5**
- **Reason:** Latest model with better medical knowledge
- **Impact:** No cost increase, better accuracy
- **Change:** Updated all references to use `us.anthropic.claude-sonnet-4-0` (global inference profile)
- **Status:** ✅ Approved

**2025-11-06: Use Converse API + Centralized Config**
- **Reason:** User requirement for consistency and no hard-coded values
- **Impact:** All LLM calls use `packages/core/src/config/llm_config.py`
- **Change:** Updated implementation plan with Converse API examples
- **Status:** ✅ Approved

**2025-11-06: Start with Titan, not SapBERT**
- **Reason:** 200x cheaper, simpler infrastructure, good enough with Claude
- **Impact:** Saves $500/month initially
- **Upgrade path:** Easy switch via environment variable
- **Status:** ✅ Approved

**2025-11-06: Use Aaron's hybrid search approach**
- **Reason:** Filter DURING search (Redis Stack 8.2.2), not after
- **Impact:** 32% faster (40ms → 27ms), more accurate
- **Implementation:** Store filter fields in Redis alongside vectors
- **Status:** ✅ Approved

**2025-11-06: Redis quantization strategy**
- **Reason:** LeanVec4x8 quantization reduces storage 3x (Redis Stack 8.2.2 feature)
- **Impact:** 4KB → ~1.3KB per drug, 50k drugs = ~65MB instead of 200MB
- **Cost:** Minimal (+$0.15/month for extra filter fields)
- **Status:** ✅ Approved

---

## Open Questions & Blockers

### Questions for User
1. ✅ **RESOLVED:** Use Claude 4 instead of 3.5? → Yes, use Claude Sonnet 4
2. ✅ **RESOLVED:** Redis version decision? → Redis Stack 8.2.2 on EC2 (not ElastiCache)
3. ⏳ **PENDING:** Ready to begin Phase 1 deployment (infrastructure code complete)?
4. ⏳ **PENDING:** Confirm AWS account IDs for dev/staging/prod stages

### Technical Unknowns
- ✅ **RESOLVED:** ElastiCache only supports Redis 7.1, using self-managed Redis Stack 8.2.2 on EC2
  - Rationale: Need LeanVec4x8 quantization (3x memory reduction)
  - See docs/REDIS_INFRASTRUCTURE_DECISION.md for full analysis
- **FDB schema relationships:** 100+ tables, need to identify key joins
  - Mitigation: Start with core tables only (rndc14, rgcnseq4, rnp2)

### No Current Blockers
- All architectural decisions made
- Implementation plan complete
- Ready to proceed with development

---

## Work in Progress

### Current Files Being Worked On
- ✅ `/workspaces/DAW/docs/IMPLEMENTATION_PLAN.md` - Complete
- ✅ `/workspaces/DAW/memory-bank/projectbrief.md` - Complete
- ✅ `/workspaces/DAW/memory-bank/systemPatterns.md` - Complete
- ✅ `/workspaces/DAW/memory-bank/techContext.md` - Complete
- 🔄 `/workspaces/DAW/memory-bank/activeContext.md` - This file
- ⏳ `/workspaces/DAW/memory-bank/progress.md` - Next

### Next Files to Create
**Phase 1 Infrastructure:**
1. `/workspaces/DAW/infra/database.ts` - Aurora RDS setup
2. `/workspaces/DAW/infra/cache.ts` - Redis ElastiCache setup
3. `/workspaces/DAW/infra/network.ts` - VPC, subnets, security groups
4. `/workspaces/DAW/sst.config.ts` - Update with infrastructure references

**Phase 2 Core Logic:**
1. `/workspaces/DAW/packages/core/src/embedding/__init__.py` - Factory
2. `/workspaces/DAW/packages/core/src/embedding/base.py` - Abstract interface
3. `/workspaces/DAW/packages/core/src/embedding/titan.py` - Titan implementation
4. `/workspaces/DAW/packages/core/src/embedding/sapbert.py` - SapBERT stub

---

## Key Insights from Recent Work

### Understanding: Vector vs Filter Fields
**Clarification gained:** The vector embedding itself is identical in both approaches (filtered vs unfiltered Redis). The difference is in the **additional structured fields** stored alongside the vector.

- **Vector:** Contains semantic meaning (implicit, fuzzy)
- **Filter fields:** Contain exact values (explicit, precise)
- **Both needed:** Vectors find similar, filters ensure exact matches

**Impact:** Confirmed Aaron's approach is correct - store filter fields in Redis for hybrid search.

### Understanding: Claude's Role with Titan
**Clarification gained:** With SapBERT, Claude is helpful but not critical. With Titan, Claude becomes essential for medical terminology.

- **Titan alone:** Misses medical abbreviations, weak drug class matching
- **Titan + Claude:** Claude expands abbreviations, adds synonyms, corrects spelling
- **Result:** Good enough accuracy without SapBERT

**Impact:** Confirmed Titan + Claude is viable starting point.

### Understanding: Embedding Model Abstraction
**Key pattern:** Factory pattern allows zero-code-change model swapping.

```python
# Just change environment variable
EMBEDDING_MODEL=titan → EMBEDDING_MODEL=sapbert

# Code stays the same
model = get_embedding_model()
vector = model.embed(text)
```

**Impact:** Easy A/B testing, low-risk upgrade path.

---

## Communication Notes

### Customer (Aaron) Requirements
1. **Redis quantization:** Specifically requested for size reduction (using LeanVec4x8 in Redis Stack 8.2.2)
2. **Hybrid search:** Vector + filter simultaneously (one query)
3. **Veterinary use case:** Multi-species support (canine, feline, equine)
4. **Cost-conscious:** Wants to minimize SageMaker costs initially

### User Preferences
- **Start simple:** Titan first, upgrade to SapBERT only if needed
- **AWS-only:** No multi-cloud considerations
- **SST v3:** Preferred IaC tool
- **CursorRIPER workflow:** Following RIPER methodology

---

## Context for Next Session

### When Resuming Work
1. **Current state:** START phase complete, ready for DEVELOPMENT phase
2. **Next phase:** Phase 1 - Infrastructure implementation
3. **First task:** Create SST infrastructure files (database.ts, cache.ts)
4. **Prerequisites:** User approval to proceed with implementation

### Key Files to Reference
- **Implementation plan:** `/workspaces/DAW/docs/IMPLEMENTATION_PLAN.md`
- **Project brief:** `/workspaces/DAW/memory-bank/projectbrief.md`
- **System patterns:** `/workspaces/DAW/memory-bank/systemPatterns.md`
- **Tech context:** `/workspaces/DAW/memory-bank/techContext.md`

### Important Context
- **FDB data:** Already available in `/workspaces/DAW/database/imports/fdb tables.sql`
- **SST template:** Already configured, ready to add resources
- **AWS region:** us-east-1 (fixed requirement)
- **Python version:** 3.12 (for all Lambda functions)

---

## Metrics & Goals (Current Sprint)

### Sprint Goal
Complete START phase documentation and get approval to begin Phase 1 implementation.

### Success Criteria
- [x] All memory bank files created
- [x] Implementation plan reviewed and approved
- [x] Architecture decisions documented
- [ ] User confirms readiness to proceed
- [ ] CursorRIPER state updated to DEVELOPMENT

### Timeline
- **Start:** 2025-11-06
- **Current:** 2025-11-06 (same day)
- **Expected completion:** Today (awaiting user approval)

---

## Notes for AI Assistant (Future Sessions)

### When Continuing This Project
1. **Always read memory bank first:** Essential context for consistency
2. **Reference implementation plan:** Detailed steps and code examples
3. **Follow phase order:** Don't skip ahead (infrastructure → logic → API)
4. **Test incrementally:** Deploy and test each phase before moving on
5. **Update progress.md:** Keep track of what's built and what's left

### Key Patterns to Remember
- **Embedding abstraction:** Use factory pattern, environment variable switching
- **Hybrid search:** Redis Stack 8.2.2 with vector + filter in single query
- **Claude preprocessing:** Essential for Titan, expands medical terminology
- **Data duality:** Redis for search (fast), Aurora for enrichment (complete)
- **Cost optimization:** Prompt caching for Claude (90%+ cache hit rate)
- **Redis deployment:** Self-managed on EC2 (not ElastiCache) for quantization support

### Watch Out For
- **Redis Stack 8.2.2:** Self-managed on EC2, requires operational monitoring
- **FDB schema:** 100+ tables, focus on core ones only
- **Lambda cold starts:** Python 3.12 is faster, but still ~150-200ms
- **Bedrock rate limits:** Start at 200/min for Claude (can increase)

---

**Status:** ✅ Active context documented, ready for next phase
**Next Action:** Await user approval to begin Phase 1 implementation
**Estimated Time to Phase 1 Start:** Immediate (pending approval)


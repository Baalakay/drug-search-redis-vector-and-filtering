# Project Brief: DAW Drug Search System

## Project Identity
- **Name:** DAW (Digital pharmacy/e-prescribing platform)
- **Primary Use Case:** Highly accurate drug search for e-prescribing
- **Customer:** Aaron (veterinary practice with multi-species prescribing needs)
- **Project Phase:** Development (RIPER workflow active)
- **Started:** 2025-11-06

---

## Core Problem Statement

Build a drug search system that:
1. Handles **medical terminology** (abbreviations like "ASA" → Aspirin)
2. Tolerates **misspellings** ("cholestrl" → cholesterol)
3. Understands **drug relationships** (brand ↔ generic, drug classes)
4. Supports **semantic search** (finds related drugs beyond keyword matching)
5. Enables **precise filtering** (by indication, drug class, species, route)
6. Returns **fast results** (<50ms p95 latency)

**Current Pain Point:** Traditional keyword search fails on medical queries:
- "ASA" returns nothing (should find Aspirin)
- "statin" doesn't find all statins
- Misspellings break search entirely
- No understanding of brand/generic equivalents

---

## Primary Goals

### 1. Search Accuracy (Priority 1)
- ✅ >85% relevant results for medical terminology queries
- ✅ Handle common drug abbreviations (ASA, ACEI, ARB, NSAID, etc.)
- ✅ Correct spelling errors automatically
- ✅ Cross-reference brand/generic names
- ✅ Find drugs by therapeutic class or indication

### 2. Performance (Priority 2)
- ✅ <50ms p95 search latency
- ✅ Support 500+ queries per second
- ✅ Sub-second data enrichment (full drug details)

### 3. Cost Efficiency (Priority 3)
- ✅ <$1 per 100k queries all-in
- ✅ Minimize SageMaker costs (avoid if possible)
- ✅ Optimize for prompt caching

### 4. Future-Proof (Priority 4)
- ✅ Easy upgrade path to medical-specific embeddings (SapBERT)
- ✅ Swappable embedding models
- ✅ Modular architecture for adding new search features

---

## Target Users

### Primary User: Prescribers
- Veterinarians (Aaron's use case)
- Physicians
- Nurse practitioners
- Physician assistants

### User Behavior:
- Often use **medical abbreviations** (ASA instead of Aspirin)
- Make **spelling errors** when typing drug names
- Search by **indication** ("something for diabetes")
- Search by **drug class** ("give me a statin")
- Need to see **brand and generic** options
- Want to filter by **species** (canine, feline, equine for veterinary)

---

## Success Metrics

### Functional Requirements (Must Have)
1. **Medical terminology recognition:** Handle 100+ common abbreviations
2. **Spelling tolerance:** Correct misspellings within 2-3 character edits
3. **Drug class matching:** Find all drugs in a therapeutic class
4. **Brand/generic cross-reference:** Show both when searching either
5. **Multi-species support:** Filter drugs by approved species (vet use case)

### Performance Requirements (Must Have)
1. **Search latency:** <50ms p95 for vector search + filters
2. **Enrichment latency:** <30ms for Aurora batch lookup
3. **Total API latency:** <100ms p95 end-to-end
4. **Throughput:** Handle 500+ QPS without degradation
5. **Availability:** 99.9% uptime

### Quality Metrics (Should Have)
1. **Precision@10:** >90% (9 out of 10 results are relevant)
2. **Recall@20:** >85% (find 85% of all relevant drugs)
3. **User satisfaction:** <5% query reformulation rate
4. **Zero-result rate:** <2% of queries return no results

---

## Key Constraints

### Business Constraints
1. **Budget:** ~$300-500/month infrastructure budget
2. **Timeline:** MVP in 4-5 weeks
3. **Maintenance:** Minimal ongoing maintenance (serverless preferred)

### Technical Constraints
1. **AWS-only:** Must deploy entirely on AWS
2. **US-East-1:** Primary region (customer requirement)
3. **Data source:** FDB (First Databank) drug database (existing)
4. **Database:** Aurora PostgreSQL (existing, can't change)
5. **No local Docker:** Development on AWS Workspace (VDI environment)

### Data Constraints
1. **Drug count:** ~100,000 medications in FDB database
2. **Update frequency:** Weekly FDB updates
3. **Data size:** ~200MB SQL dump (FDB tables)
4. **Search scope:** Drug search only (pharmacy search deferred)

---

## Out of Scope (Explicitly Not Included)

1. ❌ **Pharmacy search** - Different use case, deferred to later phase
2. ❌ **Drug interaction checking** - FDB has this data, but not search feature
3. ❌ **Dosing calculator** - Clinical decision support, separate feature
4. ❌ **Prescription writing** - E-prescribing workflow (separate)
5. ❌ **Patient matching** - Not part of drug search

---

## Key Architectural Decisions

### Decision 1: Embeddings Model
**Choice:** Start with **Titan Embeddings**, upgrade to **SapBERT** if needed

**Rationale:**
- Titan is 200x cheaper (~$0.01 vs $70+ per 1M queries)
- Fully managed (no SageMaker endpoint maintenance)
- Good enough with Claude preprocessing
- Easy upgrade path if accuracy insufficient

**Trade-off:** 
- ✅ Lower cost, simpler infrastructure
- ❌ Slightly lower accuracy on medical terms (mitigated by Claude)

### Decision 2: Vector Store
**Choice:** **Redis Stack 8.2.2 on EC2** with LeanVec4x8 quantization

**Rationale:**
- Redis Stack 8.2.2 supports LeanVec4x8 quantization (3x memory reduction)
- Simultaneous vector + filter search (hybrid search in one query)
- Customer specifically requested quantization feature
- ElastiCache only supports Redis 7.1, so using self-managed EC2 instance
- Much faster than alternatives (pgvector, OpenSearch)

**Trade-off:**
- ✅ Best performance for hybrid search
- ✅ LeanVec4x8 quantization (3x memory savings)
- ✅ 16% cost savings vs ElastiCache ($104/mo vs $124/mo)
- ⚠️ Self-managed (operational responsibility)

### Decision 3: Query Preprocessing
**Choice:** **Claude Sonnet 4** with prompt caching

**Rationale:**
- Medical knowledge is good enough (vs specialized medical LLM)
- Prompt caching makes it cost-effective (~$0.30 per 100k queries)
- Handles both medical terminology AND conversational queries
- Easier to maintain than BioGPT/PubMedGPT

**Trade-off:**
- ✅ Best balance of capability, cost, and maintenance
- ❌ Not as specialized as medical-only LLMs

### Decision 4: Data Storage
**Choice:** **Hybrid** - Redis for search, Aurora for enrichment

**Rationale:**
- Redis stores: vectors + filter fields (fast search)
- Aurora stores: complete drug records (source of truth)
- Best of both worlds: speed + richness

**Trade-off:**
- ✅ Optimal performance and accuracy
- ❌ Data duplication (filter fields in both Redis and Aurora)

---

## Dependencies

### External Services
1. **FDB (First Databank):** Drug database provider (customer has license)
2. **AWS Bedrock:** Claude Sonnet 4 + Titan Embeddings
3. **AWS Aurora:** PostgreSQL for FDB data
4. **AWS EC2:** Redis Stack 8.2.2 for vector search (r7g.large ARM Graviton3)
5. **AWS Parameter Store/Secrets Manager:** Configuration

### Data Dependencies
1. FDB table dumps (SQL) - provided in `database/imports/`
2. Drug class mappings - from FDB `rgcnseq4` table
3. Drug indication mappings - from FDB `rdlimxx` tables
4. Pricing data - from FDB `rnp2` table

---

## Risk Assessment

### High Risk
1. ✅ **RESOLVED: Redis quantization availability**
   - ElastiCache only supports Redis 7.1 (no quantization)
   - Solution: Self-managed Redis Stack 8.2.2 on EC2 r7g.large
   - See docs/REDIS_INFRASTRUCTURE_DECISION.md for full analysis
2. **Titan embedding accuracy:** May not be sufficient for medical terms
   - *Mitigation:* Build with abstraction layer, easy upgrade to SapBERT

### Medium Risk
1. **FDB schema complexity:** 100+ tables, unclear relationships
   - *Mitigation:* Focus only on core drug tables (rndc14, rgcnseq4)
2. **Data sync performance:** 100k drugs to embed and index
   - *Mitigation:* Batch processing with Lambda + async

### Low Risk
1. **Claude cost overrun:** If prompt caching doesn't work as expected
   - *Mitigation:* Cache hit rate monitoring, adjust prompt structure

---

## Project Timeline

### Week 1: Infrastructure
- Deploy Aurora RDS with FDB data
- Deploy Redis Stack 8.2.2 on EC2 (infra code complete)
- Create embedding abstraction layer

### Week 2: Search Core
- Build Claude query parser
- Implement Redis hybrid search
- Create Redis indexes with quantization

### Week 3: Data Pipeline
- Aurora → Redis sync job
- Embedding generation for all drugs
- Initial indexing complete

### Week 4: API Layer
- Search API endpoint
- Aurora enrichment logic
- End-to-end integration

### Week 5: Testing & Optimization
- Performance testing
- Accuracy validation
- Documentation

---

## Reference Materials

### Key Documents
- **Implementation Plan:** `/workspaces/DAW/docs/IMPLEMENTATION_PLAN.md`
- **FDB Schema:** `/workspaces/DAW/database/imports/fdb tables.sql`
- **Template Info:** `/workspaces/DAW/docs/CURSOR_RIPPER_PROJECT_TEMPLATE_INFO.md`

### Relevant Conversations
- Customer call transcript (Aaron) - defined use case and requirements
- Redis quantization discussion - hybrid search approach (using LeanVec4x8 in Redis Stack 8.2.2)
- Titan vs SapBERT comparison - embedding model selection
- Claude preprocessing strategy - medical terminology handling
- Redis infrastructure decision - ElastiCache vs EC2 (chose EC2 for quantization support)

---

## Contact & Stakeholders

### Primary Stakeholder
- **Aaron (Customer):** Veterinary practice owner, primary user
- **Requirements source:** Call transcript, Redis quantization feature request

### Technical Leads
- **AI Assistant (via CursorRIPER):** Architecture and implementation
- **Deployment:** SST v3 on AWS

---

**Status:** ✅ Project brief complete and approved
**Last Updated:** 2025-11-06
**Next Review:** After Week 1 milestone


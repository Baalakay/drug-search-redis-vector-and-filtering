# Redis Data Reload - Comprehensive Test Plan

**Date:** 2025-11-19  
**Purpose:** Verify data accuracy before full reload of 493,573 drugs

---

## PHASE 1: FDB Schema Investigation

### 1.1 Understand Drug Class Data Source

Based on the customer's existing system showing:
> "Rosuvastatin = HMG-CoA reductase inhibitor"

**FDB Tables to Query:**
```sql
-- Get drug class from GCN classification
SELECT 
    n.NDC,
    n.BN as brand_name,
    g.GNN60 as generic_name,
    g.HIC3 as therapeutic_class_code,
    h.HIC3DESC as drug_class_description
FROM rndc14 n
JOIN rgcnseq4 g ON n.GCN_SEQNO = g.GCN_SEQNO
JOIN rhclass h ON g.HIC3 = h.HIC3
WHERE UPPER(n.BN) = 'CRESTOR'
LIMIT 5;
```

**Expected Result:**
- `HIC3DESC` should contain "HMG-CoA REDUCTASE INHIBITOR" or similar

### 1.2 Understand Indication Data Source

Customer system shows:
> "for Primary hypercholesterolemia + Mixed dyslipidemias"

**FDB Tables to Query:**
```sql
-- Get indications from drug-indication linkage
SELECT 
    n.NDC,
    n.BN,
    d.INDICID,
    i.INDICDESC as indication_description,
    d.INDICTYPE,
    d.RELTYPE
FROM rndc14 n
JOIN rdlim14 d ON n.GCN_SEQNO = d.GCN_SEQNO
JOIN rdindc i ON d.INDICID = i.INDICID
WHERE UPPER(n.BN) = 'CRESTOR'
LIMIT 20;
```

**Expected Result:**
- Should find records for "PRIMARY HYPERCHOLESTEROLEMIA" and "MIXED DYSLIPIDEMIA"

### 1.3 Identify Active/Inactive Field

**Query:**
```sql
-- Check OBSDTEC field distribution
SELECT 
    CASE WHEN OBSDTEC IS NULL THEN 'ACTIVE' ELSE 'INACTIVE' END as status,
    COUNT(*) as count
FROM rndc14
WHERE UPPER(BN) = 'CRESTOR'
GROUP BY status;
```

**Rule:** `OBSDTEC IS NULL` = Active drug

---

## PHASE 2: Required Redis Fields Analysis

### 2.1 Core Fields (From rndc14)
| Field | Source | Transform | Purpose |
|-------|--------|-----------|---------|
| `ndc` | NDC | None | Unique ID |
| `drug_name` | LN | UPPER(TRIM()) | Primary search |
| `brand_name` | BN | UPPER(TRIM()) | Brand search |
| `generic_name` | LN | Extract chemical name | Generic search |
| `gcn_seqno` | GCN_SEQNO | Cast to UNSIGNED | Equivalency |
| `dosage_form` | DF | TRIM() | Filter |
| `is_generic` | INNOV | '0'='true', '1'='false' | Filter |
| `dea_schedule` | DEA | Filter 1-5 only | Filter |
| `manufacturer` | LBLRID | TRIM() | Filter (optional) |
| `is_active` | OBSDTEC | 'NULL'='true' | Filter |

### 2.2 Lookup Fields (Require JOINS)
| Field | Source Tables | Logic |
|-------|---------------|-------|
| `drug_class` | rgcnseq4 + rhclass | JOIN on GCN_SEQNO → HIC3 → HIC3DESC |
| `indication` | rgcnseq4 + rdlim14 + rdindc | JOIN on GCN_SEQNO → INDICID → GROUP_CONCAT(INDICDESC, '\|') |
| `therapeutic_class` | rgcnseq4 + rhclass | Same as drug_class (HIC3DESC) |

### 2.3 Additional Fields (From Codex Notes)

Checking REDIS_SCHEMA_DESIGN.md (lines 22-38), the previous AI suggested:
- `strength` - Display only (from rgcnseq4.STR or parsed from LN)
- `route` - Filter field (from rgcnseq4.GCRT)
- `manufacturer` - Filter field (from rndc14.LBLRID)

**My Assessment:**
- ✅ `strength`: Include as TEXT field for search ("crestor 10 mg")
- ✅ `route`: Include as TAG for filtering (oral, injection, etc.)
- ✅ `manufacturer`: Optional - may not be needed for MVP
- ✅ `is_active`: **CRITICAL** - Must add based on OBSDTEC

---

## PHASE 3: Complete SQL Query for Redis Load

```sql
SELECT 
    -- Core fields
    n.NDC as ndc,
    UPPER(TRIM(n.LN)) as drug_name,
    UPPER(TRIM(COALESCE(n.BN, ''))) as brand_name,
    LOWER(TRIM(REGEXP_REPLACE(n.LN, ' [0-9].*', ''))) as generic_name,
    CAST(COALESCE(n.GCN_SEQNO, 0) AS UNSIGNED) as gcn_seqno,
    TRIM(COALESCE(n.DF, '')) as dosage_form,
    TRIM(COALESCE(n.LBLRID, '')) as manufacturer,
    
    -- Brand/Generic flags
    CASE WHEN n.INNOV = '1' THEN 'true' ELSE 'false' END as is_brand,
    CASE WHEN n.INNOV = '0' THEN 'true' ELSE 'false' END as is_generic,
    
    -- DEA schedule
    CASE WHEN n.DEA IN ('1','2','3','4','5') THEN n.DEA ELSE '' END as dea_schedule,
    
    -- Active status (CRITICAL NEW FIELD)
    CASE WHEN n.OBSDTEC IS NULL THEN 'true' ELSE 'false' END as is_active,
    
    -- Drug class (from GCN classification)
    COALESCE(h.HIC3DESC, '') as drug_class,
    
    -- Therapeutic class (same as drug_class for now)
    COALESCE(h.HIC3DESC, '') as therapeutic_class,
    
    -- Route
    COALESCE(g.GCRT, '') as route,
    
    -- Strength
    COALESCE(g.STR, COALESCE(g.STR60, '')) as strength
    
FROM rndc14 n
LEFT JOIN rgcnseq4 g ON n.GCN_SEQNO = g.GCN_SEQNO
LEFT JOIN rhclass h ON g.HIC3 = h.HIC3
WHERE n.LN IS NOT NULL
    AND LENGTH(TRIM(n.LN)) > 3
    AND n.NDC IS NOT NULL
    AND n.OBSDTEC IS NULL  -- ONLY ACTIVE DRUGS
ORDER BY n.NDC
LIMIT 100;  -- For test load
```

**Note:** Indication requires GROUP_CONCAT, which is more complex. See Phase 4.

---

## PHASE 4: Indication Data (Separate Query or CTE)

```sql
-- Get indications for a drug
SELECT 
    n.NDC,
    GROUP_CONCAT(DISTINCT i.INDICDESC SEPARATOR '|') as indication
FROM rndc14 n
LEFT JOIN rdlim14 d ON n.GCN_SEQNO = d.GCN_SEQNO
LEFT JOIN rdindc i ON d.INDICID = i.INDICID
WHERE n.OBSDTEC IS NULL
GROUP BY n.NDC
LIMIT 100;
```

**Implementation Options:**
1. **Two-pass load:** Load base data, then update indications
2. **Complex JOIN:** Use subquery in main SELECT
3. **Post-process:** Enrich from Aurora after Redis load (slower)

**Recommendation:** Two-pass load for clarity and debuggability

---

## PHASE 5: Test Dataset Selection

### 5.1 Test Set Composition (100 drugs)

**Specific Drugs (for manual verification):**
1. **CRESTOR** (5 variants) - Brand statin
2. **Rosuvastatin** generics (10 variants) - Generic equivalents
3. **LIPITOR** (5 variants) - Different brand statin
4. **Lisinopril** (5 variants) - ACE inhibitor (different class)
5. **Metformin** (5 variants) - Diabetes drug
6. **Ozempic** (if exists) - GLP-1 agonist

**Additional Drugs (fill to 100):**
- Random active drugs from different classes
- Mix of brands and generics
- Various dosage forms (tablets, injections, etc.)

### 5.2 SQL for Test Dataset

```sql
-- Get test dataset
(SELECT * FROM (...main query...) WHERE UPPER(BN) = 'CRESTOR' LIMIT 5)
UNION ALL
(SELECT * FROM (...main query...) WHERE UPPER(LN) LIKE '%ROSUVASTATIN%' AND INNOV = '0' LIMIT 10)
UNION ALL
(SELECT * FROM (...main query...) WHERE UPPER(BN) = 'LIPITOR' LIMIT 5)
UNION ALL
(SELECT * FROM (...main query...) WHERE UPPER(LN) LIKE '%LISINOPRIL%' LIMIT 5)
UNION ALL
(SELECT * FROM (...main query...) WHERE UPPER(LN) LIKE '%METFORMIN%' LIMIT 5)
UNION ALL
(SELECT * FROM (...main query...) ORDER BY RAND() LIMIT 70);
```

---

## PHASE 6: Realistic Doctor Search Queries

### 6.1 Test Query Set

| # | Query | Expected Behavior | Filters Expected |
|---|-------|-------------------|------------------|
| 1 | `"crestor"` | Exact brand match first | `is_generic: false` suggested |
| 2 | `"rosuvastatin"` | Generic + brand alternatives | Mix |
| 3 | `"statin for cholesterol"` | All statins | `drug_class: STATIN` |
| 4 | `"crestor 10 mg"` | Crestor 10mg variants only | Text match on strength |
| 5 | `"atorvastatin tablet"` | Tablet forms only | `dosage_form: TABLET` |
| 6 | `"blood pressure medication"` | ACE inhibitors, ARBs, etc. | `indication: HYPERTENSION` |
| 7 | `"crestr"` (misspelled) | Crestor with fuzzy match | Spell correction |
| 8 | `"injectable diabetes drug"` | GLP-1, insulin injections | `dosage_form: INJECTION`, `indication: DIABETES` |

### 6.2 Expected Claude Preprocessing

Each query should generate:
```json
{
  "search_text": "expanded medical terms",
  "filters": {
    "drug_class": "...",
    "indication": "...",
    "dosage_form": "...",
    "is_generic": "true/false"
  },
  "corrections": [...],
  "confidence": 0.0-1.0
}
```

---

## PHASE 7: Verification Checklist

### 7.1 Data Accuracy (Per Drug)
- [ ] NDC matches FDB
- [ ] Drug name matches FDB
- [ ] Brand name matches FDB (empty string if none)
- [ ] Generic name correctly extracted/matched
- [ ] GCN_SEQNO matches FDB
- [ ] `is_generic` matches INNOV field logic
- [ ] `is_active` = true (since we filtered OBSDTEC IS NULL)
- [ ] `drug_class` matches customer's existing system
- [ ] `indication` contains relevant medical conditions
- [ ] Dosage form is populated
- [ ] DEA schedule correct (or empty)

### 7.2 Redis Index Verification
- [ ] All 100 drugs loaded to Redis
- [ ] Index `drugs_idx` exists
- [ ] Vector search returns results
- [ ] Text search works (drug_name, brand_name, generic_name)
- [ ] Tag filters work (drug_class, indication, dosage_form)
- [ ] Numeric filter works (gcn_seqno)

### 7.3 Search Quality Verification
- [ ] Query "crestor" returns CRESTOR first
- [ ] Query "rosuvastatin" shows both brand and generic
- [ ] Query "statin" returns multiple statin drugs
- [ ] Misspelled "crestr" suggests/returns CRESTOR
- [ ] Filter combinations work correctly

---

## PHASE 8: Test Load Execution Plan

### 8.1 Preparation
1. Backup current Redis data (export keys to file)
2. Create test index `drugs_test_idx`
3. Run SQL queries to verify data quality

### 8.2 Test Load (100 drugs)
1. Run main SQL query with LIMIT 100
2. Generate embeddings (from `drug_name + drug_class + indication`)
3. Load to Redis with key prefix `drug_test:`
4. Create test index

### 8.3 Field-by-Field Comparison
1. Select 5 specific drugs (CRESTOR, rosuvastatin generic, LIPITOR, lisinopril, metformin)
2. Query FDB for each
3. Query Redis for each
4. Compare ALL fields in a table

### 8.4 Search Testing
1. Run all 8 test queries via API
2. Inspect results for accuracy
3. Compare with expectations

### 8.5 Decision Point
- **PASS:** Proceed to full load (493,573 drugs)
- **FAIL:** Identify issues, fix SQL/load script, repeat test

---

## PHASE 9: Full Load (If Test Passes)

### 9.1 Full Load Script
- Same SQL as test, remove LIMIT 100
- Add `WHERE OBSDTEC IS NULL` (active only)
- Batch size: 100 drugs at a time
- Log every 1,000 drugs
- Expected time: 2.5-4 hours

### 9.2 Monitoring
- Track progress via log file
- Check Redis memory usage
- Verify document count matches query count

### 9.3 Final Verification
- Spot-check 20 random drugs
- Run all 8 test queries
- Compare results with test load
- Check for any data quality issues

---

## OPEN QUESTIONS

1. **Indication formatting:** Should we use pipe-separated (`HYPERTENSION|DIABETES`) or comma-separated?
   - **Answer:** Pipe-separated (matches Redis TAG field separator)

2. **Drug class normalization:** HIC3DESC may have inconsistent casing/formatting
   - **Answer:** UPPER(TRIM()) for consistency

3. **Embedding input:** What fields should be included?
   - **Current:** `drug_name + drug_class + indication`
   - **Alternative:** `drug_name` only (simpler, may be sufficient)
   - **Recommendation:** Test both approaches

4. **Inactive drugs:** Should they be in Redis at all, or filtered at query time?
   - **Answer:** Filter at load time (`OBSDTEC IS NULL`), simpler and faster

---

## NEXT STEPS

1. [ ] Run Phase 1 queries manually to verify FDB schema
2. [ ] Write test load script with complete SQL
3. [ ] Execute test load (100 drugs)
4. [ ] Verify field-by-field accuracy
5. [ ] Test all 8 search queries
6. [ ] Document any issues found
7. [ ] Iterate until test passes
8. [ ] Execute full load

---

**Status:** Ready for Phase 1 execution  
**Owner:** Claude Sonnet 4  
**Review Date:** 2025-11-19


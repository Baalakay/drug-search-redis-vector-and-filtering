# Phase 1: FDB Schema Analysis - CRESTOR & Required Fields

**Date:** 2025-11-19  
**Status:** Schema Analysis Complete (Based on FDB Documentation)

---

## Summary

Based on FDB schema documentation and the customer's existing system showing:
> "Rosuvastatin = HMG-CoA reductase inhibitor - for Primary hypercholesterolemia + Mixed dyslipidemias"

This document outlines the correct SQL queries and data sources for the Redis reload.

---

## 1. Drug Class Source

### FDB Tables
- `rgcnseq4`: GCN classification table
  - Links: `GCN_SEQNO` → `HIC3` (therapeutic class code)
  - Contains: `GNN60` (generic name), `HIC3`, `GCRT` (route), `STR` (strength)
  
- `rhclass`: Hierarchical classification
  - Key: `HIC3`
  - Contains: `HIC3DESC` (human-readable drug class description)

### SQL for Drug Class
```sql
SELECT 
    n.NDC,
    n.BN as brand_name,
    g.HIC3 as class_code,
    h.HIC3DESC as drug_class
FROM rndc14 n
LEFT JOIN rgcnseq4 g ON n.GCN_SEQNO = g.GCN_SEQNO
LEFT JOIN rhclass h ON g.HIC3 = h.HIC3
WHERE UPPER(n.BN) = 'CRESTOR';
```

**Expected for CRESTOR:**
- `HIC3DESC` should contain text like: "HMG-CoA REDUCTASE INHIBITORS" or "STATINS"

---

## 2. Indication Source

### FDB Tables
- `rdlim14`: Drug-indication linkage table
  - Links: `GCN_SEQNO` → `INDICID`
  - Contains: `INDICTYPE`, `RELTYPE` (relationship type)
  
- `rdindc`: Indication descriptions
  - Key: `INDICID`
  - Contains: `INDICDESC` (human-readable indication)

### SQL for Indications
```sql
SELECT 
    n.NDC,
    n.BN,
    GROUP_CONCAT(DISTINCT i.INDICDESC SEPARATOR '|') as indication
FROM rndc14 n
LEFT JOIN rdlim14 d ON n.GCN_SEQNO = d.GCN_SEQNO
LEFT JOIN rdindc i ON d.INDICID = i.INDICID
WHERE UPPER(n.BN) = 'CRESTOR'
GROUP BY n.NDC;
```

**Expected for CRESTOR:**
- Indications should include:
  - "PRIMARY HYPERCHOLESTEROLEMIA"
  - "MIXED DYSLIPIDEMIA"
  - Possibly: "HYPERTRIGLYCERIDEMIA", "ATHEROSCLEROSIS PREVENTION"

---

## 3. Active vs Inactive Drugs

### Field: `OBSDTEC` in `rndc14`
- **NULL**: Drug is ACTIVE (currently marketed)
- **NOT NULL**: Drug is INACTIVE/OBSOLETE (date indicates when it was discontinued)

### SQL for Active Drugs Only
```sql
SELECT * FROM rndc14
WHERE OBSDTEC IS NULL;
```

**Redis Load Rule:** 
- **Only load drugs where `OBSDTEC IS NULL`**
- Add field: `is_active: 'true'` (all loaded drugs are active)
- Inactive drugs will NOT be in Redis

---

## 4. Complete Redis Field Mapping

| Redis Field | FDB Source | Transform/Logic |
|-------------|------------|-----------------|
| **Core Fields** |||
| `ndc` | `rndc14.NDC` | None (Primary key) |
| `drug_name` | `rndc14.LN` | `UPPER(TRIM())` |
| `brand_name` | `rndc14.BN` | `UPPER(TRIM(COALESCE(BN, '')))` |
| `generic_name` | `rndc14.LN` | Extract chemical name (before dosage info) |
| `gcn_seqno` | `rndc14.GCN_SEQNO` | `CAST(COALESCE(GCN_SEQNO, 0) AS UNSIGNED)` |
| **Classification** |||
| `drug_class` | `rgcnseq4.HIC3` → `rhclass.HIC3DESC` | JOIN via GCN_SEQNO |
| `therapeutic_class` | Same as `drug_class` | (Alias for now) |
| **Indication** |||
| `indication` | `rdlim14` + `rdindc` | `GROUP_CONCAT(INDICDESC, '\|')` |
| **Dosage & Route** |||
| `dosage_form` | `rndc14.DF` | `TRIM(COALESCE(DF, ''))` |
| `route` | `rgcnseq4.GCRT` | JOIN via GCN_SEQNO |
| `strength` | `rgcnseq4.STR` or `STR60` | For TEXT search ("10 mg") |
| **Status** |||
| `is_generic` | `rndc14.INNOV` | `'0' = 'true', '1' = 'false'` |
| `is_brand` | `rndc14.INNOV` | `'1' = 'true', '0' = 'false'` |
| `is_active` | `rndc14.OBSDTEC` | `NULL = 'true'` (filter at load) |
| `dea_schedule` | `rndc14.DEA` | Filter to `'1'-'5'`, else `''` |
| **Other** |||
| `manufacturer` | `rndc14.LBLRID` | Optional (for filters) |
| `embedding` | Generated | From `drug_name + drug_class + indication` |

---

## 5. Embedding Generation Strategy

### Option A: Rich Embeddings (Recommended)
```python
embedding_text = f"{drug_name} {drug_class} {indication}"
# Example: "CRESTOR 10 MG TABLET HMG-CoA REDUCTASE INHIBITORS PRIMARY HYPERCHOLESTEROLEMIA|MIXED DYSLIPIDEMIA"
```

**Pros:**
- Better semantic search (finds drugs by class/indication)
- Matches how doctors think ("I need a statin for cholesterol")

**Cons:**
- If data quality is poor, embeddings will be poor

### Option B: Drug Name Only (Simpler)
```python
embedding_text = drug_name
# Example: "CRESTOR 10 MG TABLET"
```

**Pros:**
- Simple, no dependency on drug_class/indication quality
- Faster to load

**Cons:**
- Limited semantic search capability
- Won't find alternatives by class

**Recommendation:** Start with Option B (drug name only), add drug_class/indication later if data quality is verified.

---

## 6. Complete SQL Query for Test Load (100 Drugs)

```sql
SELECT 
    -- Core identification
    n.NDC as ndc,
    UPPER(TRIM(n.LN)) as drug_name,
    UPPER(TRIM(COALESCE(n.BN, ''))) as brand_name,
    LOWER(TRIM(REGEXP_REPLACE(n.LN, ' [0-9].*', ''))) as generic_name,
    CAST(COALESCE(n.GCN_SEQNO, 0) AS UNSIGNED) as gcn_seqno,
    
    -- Dosage & form
    TRIM(COALESCE(n.DF, '')) as dosage_form,
    COALESCE(g.GCRT, '') as route,
    COALESCE(g.STR, COALESCE(g.STR60, '')) as strength,
    
    -- Status flags
    CASE WHEN n.INNOV = '1' THEN 'true' ELSE 'false' END as is_brand,
    CASE WHEN n.INNOV = '0' THEN 'true' ELSE 'false' END as is_generic,
    CASE WHEN n.DEA IN ('1','2','3','4','5') THEN n.DEA ELSE '' END as dea_schedule,
    'true' as is_active,  -- All loaded drugs are active
    
    -- Classification (via GCN)
    COALESCE(h.HIC3DESC, '') as drug_class,
    COALESCE(h.HIC3DESC, '') as therapeutic_class,
    
    -- Manufacturer (optional)
    TRIM(COALESCE(n.LBLRID, '')) as manufacturer
    
FROM rndc14 n
LEFT JOIN rgcnseq4 g ON n.GCN_SEQNO = g.GCN_SEQNO
LEFT JOIN rhclass h ON g.HIC3 = h.HIC3
WHERE n.LN IS NOT NULL
    AND LENGTH(TRIM(n.LN)) > 3
    AND n.NDC IS NOT NULL
    AND n.OBSDTEC IS NULL  -- ACTIVE DRUGS ONLY
ORDER BY n.NDC
LIMIT 100;
```

**Note:** Indications require a separate query with GROUP_CONCAT (see below).

---

## 7. Indication Query (Separate Pass)

Due to GROUP_CONCAT complexity, load indications in a second pass:

```sql
SELECT 
    n.NDC,
    GROUP_CONCAT(DISTINCT i.INDICDESC SEPARATOR '|') as indication
FROM rndc14 n
LEFT JOIN rdlim14 d ON n.GCN_SEQNO = d.GCN_SEQNO
LEFT JOIN rdindc i ON d.INDICID = i.INDICID
WHERE n.OBSDTEC IS NULL
    AND n.NDC IN (...list of 100 NDCs from previous query...)
GROUP BY n.NDC;
```

Then merge into Redis documents.

---

## 8. Verification Queries

### Count Total Active Drugs
```sql
SELECT COUNT(*) FROM rndc14 WHERE OBSDTEC IS NULL;
```

**Expected:** ~450,000-500,000 (depends on FDB version)

### Count CRESTOR Variants
```sql
SELECT 
    CASE WHEN OBSDTEC IS NULL THEN 'ACTIVE' ELSE 'INACTIVE' END as status,
    COUNT(*) as count
FROM rndc14
WHERE UPPER(BN) = 'CRESTOR'
GROUP BY status;
```

**Expected:** Some active, some inactive CRESTOR variants

### Sample Drug Class Distribution
```sql
SELECT 
    h.HIC3DESC as drug_class,
    COUNT(*) as drug_count
FROM rndc14 n
LEFT JOIN rgcnseq4 g ON n.GCN_SEQNO = g.GCN_SEQNO
LEFT JOIN rhclass h ON g.HIC3 = h.HIC3
WHERE n.OBSDTEC IS NULL
GROUP BY h.HIC3DESC
ORDER BY drug_count DESC
LIMIT 20;
```

**Expected:** Top classes like "ANALGESICS", "ANTIBIOTICS", "ANTIHYPERTENSIVES", etc.

---

## 9. Data Quality Concerns

### Known Issues
1. **HIC3DESC formatting:** May have inconsistent casing or abbreviations
2. **Missing drug_class:** Some GCNs may not have HIC3 mappings
3. **Missing indications:** Not all drugs have indication linkages in FDB
4. **Generic name extraction:** `REGEXP_REPLACE(LN, ' [0-9].*', '')` is imperfect

### Mitigation Strategies
1. **Normalize drug_class:** `UPPER(TRIM(HIC3DESC))` for consistency
2. **Default values:** Use `COALESCE(..., '')` for missing data
3. **Validation:** Spot-check 20 random drugs after load
4. **Logging:** Track drugs with missing drug_class or indication

---

## 10. Next Steps

- [x] Phase 1: FDB Schema Analysis (this document)
- [ ] Phase 2: Create test load script with 100 drugs
- [ ] Phase 3: Execute test load to Redis test index
- [ ] Phase 4: Field-by-field verification (5 sample drugs)
- [ ] Phase 5: Test 8 doctor search queries
- [ ] Phase 6: Full load (450K+ active drugs)
- [ ] Phase 7: Production deployment

---

**Status:** ✅ COMPLETE - Ready for Phase 2 implementation  
**Key Decision:** Use drug name only for embeddings initially, add drug_class/indication later if data quality verified


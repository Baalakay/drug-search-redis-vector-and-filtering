# Redis Data Quality Issue - CRITICAL

**Date:** 2025-11-19  
**Status:** 🔴 **BLOCKING SEARCH FUNCTIONALITY**

---

## Problem

The bulk load script (`/tmp/bulk_load_drugs.py` on Redis EC2 instance `i-0aad9fc4ba71454fa`) loaded **ALL 493,573 drugs** with:

- `drug_class: "ACE_INHIBITOR"` (WRONG - should be specific to each drug)
- `indication: "HYPERTENSION|DIABETES"` (WRONG - should be specific to each drug)

**Impact:**
- ✅ Drug names, NDCs, GCNs, brand/generic status are CORRECT
- ❌ `drug_class` and `indication` fields are INCORRECT for all drugs
- ❌ **Embeddings were generated with this wrong data**, so semantic search is returning unrelated drugs

---

## Evidence

### Example: CRESTOR (Rosuvastatin - a STATIN)

**Expected:**
```
drug_class: "STATIN"
indication: "HYPERLIPIDEMIA|HIGH_CHOLESTEROL"
```

**Actual in Redis:**
```
drug_class: "ACE_INHIBITOR"
indication: "HYPERTENSION|DIABETES"
```

**Search Impact:**
- Searching for "crestor" returns: pravastatin, clocort, glycopyrrolate
- Searching for "statin" returns: random drugs with "ACE_INHIBITOR" in their embeddings
- Generic rosuvastatin is not shown as an alternative to CRESTOR

---

## Root Cause

The bulk load script on the EC2 instance is different from `/workspaces/DAW/functions/src/handlers/drug_loader.py`.

**Correct code** (in repo):
```python:156:157:functions/src/handlers/drug_loader.py
            '' as drug_class,
            '' as therapeutic_class
```

**Suspected issue** (in `/tmp/bulk_load_drugs.py` on EC2):
- Hardcoded values: `drug_class = "ACE_INHIBITOR"`, `indication = "HYPERTENSION|DIABETES"`
- OR: A test drug's values were reused for all drugs due to a loop bug

---

## Temporary Workaround (DEPLOYED)

1. ✅ **Removed `drug_class` and `indication` from API responses** (search_handler.py lines 596-597)
2. ⚠️ **Semantic search is still broken** because embeddings were generated with wrong data

---

## Proper Fix Required

### Option 1: Reload Redis Data (2-4 hours)

**Steps:**
1. Update bulk load script to get proper `drug_class` and `indication` from FDB:
   ```sql
   SELECT 
       n.NDC,
       n.LN,
       n.BN,
       g.HIC3 as drug_class_code,
       COALESCE(GROUP_CONCAT(DISTINCT i.indication SEPARATOR '|'), '') as indication
   FROM rndc14 n
   LEFT JOIN rgcnseq4 g ON n.GCN_SEQNO = g.GCN_SEQNO
   LEFT JOIN rdlimxx i ON g.GCN_SEQNO = i.GCN_SEQNO
   WHERE n.LN IS NOT NULL
   GROUP BY n.NDC
   ```

2. Map `HIC3` codes to human-readable drug classes (requires FDB reference tables)

3. Re-run bulk load: `nohup python3 -u /tmp/bulk_load_drugs_v2.py > /tmp/bulk_load_v2.log 2>&1 &`

4. Monitor progress: `tail -f /tmp/bulk_load_v2.log`

**Time:** 2.5-4 hours (493,573 drugs × 3-5 drugs/sec)

### Option 2: Generate Embeddings from Drug Names Only (RECOMMENDED)

**Rationale:**
- Drug names alone are sufficient for semantic search (e.g., "CRESTOR" → "rosuvastatin")
- `drug_class` and `indication` should be TAG filters, not part of the embedding
- Simpler data pipeline, faster reload

**Steps:**
1. Update bulk load to generate embeddings from `drug_name` only (already done in repo code)
2. Set `drug_class = ''` and `indication = ''` (already done in repo code)
3. Copy correct script to EC2: `scp functions/src/handlers/drug_loader.py ec2:/tmp/bulk_load_drugs_v2.py`
4. Re-run bulk load

**Time:** 2.5-4 hours

---

## Next Steps

**IMMEDIATE:**
- [x] Deploy workaround (remove drug_class/indication from API)
- [ ] User decision: Reload Redis now OR continue with limited search?

**SHORT-TERM (if reloading):**
- [ ] Copy correct loader script to EC2
- [ ] Clear Redis index: `FT.DROPINDEX drugs_idx`
- [ ] Re-create index: `python3 /tmp/create_redis_index.py`
- [ ] Run bulk load v2: `nohup python3 -u /tmp/bulk_load_drugs_v2.py > /tmp/bulk_load_v2.log 2>&1 &`
- [ ] Monitor progress every 30 min

**LONG-TERM:**
- [ ] Implement proper FDB joins for drug_class/indication
- [ ] Add data validation tests before bulk load
- [ ] Document FDB schema mappings

---

## Files Affected

- `/tmp/bulk_load_drugs.py` (on EC2 `i-0aad9fc4ba71454fa`) - **INCORRECT VERSION**
- `/workspaces/DAW/functions/src/handlers/drug_loader.py` - **CORRECT VERSION**
- `/workspaces/DAW/functions/src/search_handler.py` - **WORKAROUND DEPLOYED**

---

## Additional Notes

- Redis has 493,573 drugs loaded (correct count)
- NDCs, drug names, brand names, GCNs are all CORRECT
- Only `drug_class` and `indication` (and their embeddings) are wrong
- This issue was introduced during the initial bulk load on 2025-11-15


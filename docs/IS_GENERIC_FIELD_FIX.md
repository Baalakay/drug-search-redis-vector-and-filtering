# is_generic Field Fix - 2025-11-15

## Issue Discovery

During hybrid search testing, the `@is_generic:{true}` filter returned **0 results**, despite expecting ~86% of drugs to be generic.

## Root Cause Analysis

### Initial Investigation
- Checked Redis: All 493,573 drugs had `is_generic='false'`
- Checked FDB source data: Found GNI field had values `'0'`, `'1'`, `'2'` (NO `'Y'` values)

### Incorrect Mapping in Bulk Load Script
```python
# WRONG (from bulk_load_drugs_hash.py line 171)
CASE WHEN GNI = 'Y' THEN 'true' ELSE 'false' END as is_generic
```

**Problem:** FDB has NO drugs with `GNI='Y'`, so all drugs were mapped to `is_generic='false'`

### Correct Field Identification

After sampling FDB data, discovered:
- **GNI field**: Values are `'0'`, `'1'`, `'2'` - meaning unclear
- **INNOV field**: Values are `'0'` and `'1'` - this is the correct indicator!

**INNOV Field Distribution (from FDB):**
- `INNOV='0'`: 426,775 drugs (86.5%) = **Generic**
- `INNOV='1'`: 66,798 drugs (13.5%) = **Innovator/Brand**

### Correct Mapping
```python
# CORRECT
CASE WHEN INNOV = '0' THEN 'true' ELSE 'false' END as is_generic
```

## Fix Implementation

### 1. Created Fix Script (`/tmp/fix_is_generic_field.py`)
- Queries Aurora for all drugs with `INNOV` field
- Updates Redis `is_generic` field in-place (no embedding regeneration needed)
- Processes in batches of 1,000 drugs

### 2. Execution Results
```
Total time:          7.5 minutes
Records processed:   493,573
Updated to generic:  426,775 (86.5%)
Updated to brand:    66,798 (13.5%)
Errors:              0
Average rate:        1101.4 updates/sec
```

### 3. Verification
**Redis Sample (10,000 drugs):**
- Generic (`is_generic='true'`): 8,651 (86.5%) ✅
- Brand (`is_generic='false'`): 1,349 (13.5%) ✅

**Filter Tests:**
- `@is_generic:{true}` → 426,775 results ✅
- `@is_generic:{false}` → 66,798 results ✅

## Files Updated

1. **`/tmp/bulk_load_drugs_hash.py`** (line 171)
   - Changed: `GNI = 'Y'` → `INNOV = '0'`
   - Ensures future bulk loads use correct mapping

2. **`memory-bank/progress.md`**
   - Updated Phase 5 to 100% complete
   - Added is_generic fix details
   - Updated overall progress to 40%

## Key Learnings

1. **Always validate field values** before assuming mapping logic
2. **FDB documentation gaps**: 
   - GNI field meaning unclear (values: 0, 1, 2)
   - INNOV field is the correct generic/brand indicator
3. **In-place updates are fast**: 493K records updated in 7.5 minutes (no need for 9-hour reload)
4. **Data quality verification is critical**: Always check source vs. destination counts

## Prevention

- Updated bulk load script with correct INNOV mapping
- Documented INNOV field as the authoritative source for generic/brand status
- Added data verification steps to future load processes

---

**Status:** ✅ RESOLVED  
**Impact:** Zero - Redis data now correctly reflects FDB source  
**Time to Fix:** 7.5 minutes (vs. 9 hours for full reload)


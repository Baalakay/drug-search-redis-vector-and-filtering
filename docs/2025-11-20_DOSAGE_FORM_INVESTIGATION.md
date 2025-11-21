# Dosage Form Investigation Results
## Date: 2025-11-20

## Executive Summary

✅ **Successfully exported all 116 FDB tables to CSV** (`database/exports/csv/`)  
✅ **Found the dosage form lookup chain:**
```
rndc14.GCN_SEQNO → rgcnseq4.GCDF → rdosed2.GCDF_DESC
```

## Critical Findings

### Issue #1: Claude Filters Are Being Dropped ❌

**Location:** Line 864 in `/workspaces/DAW/functions/src/search_handler.py`

```python
AUTO_APPLY_CLAUDE_FILTERS: set[str] = set()  # ❌ EMPTY SET!
```

**Impact:** ALL Claude-extracted filters are ignored, including:
- `dosage_form` (e.g., "cream")
- `dea_schedule`
- `is_generic`
- `ndc`, `gcn_seqno`

**Example:** When searching "testosterone creams", Claude correctly extracts:
```json
{
  "dosage_form": "cream",
  "dea_schedule": "3",
  "indication": "hormone replacement"
}
```

But `merge_filters()` drops ALL of these because they're not in `AUTO_APPLY_CLAUDE_FILTERS`.

**Fix:**
```python
AUTO_APPLY_CLAUDE_FILTERS: set[str] = {
    'dosage_form', 'dea_schedule', 'is_generic', 
    'ndc', 'gcn_seqno'
}
```

---

### Issue #2: Dosage Form Contains FDB Codes, Not Text ❌

**Current Redis Data:**
- `dosage_form = "3"` (FDB internal code)
- `dosage_form = "KA"` (FDB GCDF code)
- `dosage_form = ""` (empty from `rndc14.DF`)

**Expected Redis Data:**
- `dosage_form = "CREAM"` or `dosage_form = "GEL"`
- Human-readable text that can be filtered

**Root Cause:**
The load script (`production_load_full_dataset.py`) uses:
```python
TRIM(COALESCE(n.DF, '')) as dosage_form,
```

But `rndc14.DF` is mostly empty or contains codes like "F/C", "AD", etc. The actual dosage form is in:
```
rndc14.GCN_SEQNO → rgcnseq4.GCDF → rdosed2.GCDF_DESC
```

---

## FDB Schema Discovery

### Key Tables Identified

#### `rgcnseq4` - GCN Sequence (Links NDC to Dosage Form Code)
- **Columns:** GCN_SEQNO, GCDF, GCRT, STR, etc.
- **Purpose:** Links NDC to dosage form code (`GCDF`) and route (`GCRT`)
- **Row Count:** 38,102 rows
- **Example:**
  ```
  GCN_SEQNO | GCDF | GCRT | STR
  67588     | HS   | A    | 1.5 MG
  44689     | HV   | 2    | 2.5 MG/ML
  ```

#### `rdosed2` - Dosage Form Lookup Table
- **Columns:** GCDF, DOSE, GCDF_DESC
- **Purpose:** Maps GCDF codes to human-readable descriptions
- **Row Count:** Unknown (sample shows 10 rows)
- **Example:**
  ```
  GCDF | DOSE      | GCDF_DESC
  KA   | CREAM (G) | CREAM (GRAM)
  JG   | GEL (GRAM)| GEL (GRAM)
  JC   | GEL (ML)  | GEL (ML)
  ```

#### Dosage Forms Found for "testosterone creams" Use Case:
- `KA` = CREAM (GRAM)
- `KM` = CREAM (ML)
- `KS` = CREAM IN PACKET (ML)
- `IW` = CREAM IN PACKET (GRAM)
- `KH` = CREAM IN PACKET (EA)
- `JG` = GEL (GRAM)
- `JC` = GEL (ML)
- And 80+ more GEL/CREAM variants...

---

## Recommended Fixes

### Fix #1: Enable Claude Filter Application (Immediate)

**File:** `/workspaces/DAW/functions/src/search_handler.py`  
**Line:** 864

```python
# OLD:
AUTO_APPLY_CLAUDE_FILTERS: set[str] = set()

# NEW:
AUTO_APPLY_CLAUDE_FILTERS: set[str] = {
    'dosage_form',  # Enable dosage form filtering
    'dea_schedule', # Enable DEA schedule filtering
    'is_generic',   # Enable generic/brand filtering
    'ndc',          # Enable specific NDC lookup
    'gcn_seqno'     # Enable GCN filtering
}
```

**Impact:** Allows Claude-extracted filters to be applied immediately.

**Limitation:** Filters will still fail because Redis has "KA" instead of "CREAM".

---

### Fix #2A: Update Load Script (Requires Full Reload)

**File:** `/workspaces/DAW/scripts/production_load_full_dataset.py`

**Change SQL Query:**
```sql
-- OLD:
TRIM(COALESCE(n.DF, '')) as dosage_form,

-- NEW:
COALESCE(TRIM(d.DOSE), TRIM(g.GCDF), '') as dosage_form,
```

**Add Join:**
```sql
LEFT JOIN rdosed2 d ON g.GCDF = d.GCDF
```

**Full Updated Query:**
```sql
SELECT
    n.NDC,
    -- ... other fields ...
    COALESCE(TRIM(d.DOSE), TRIM(g.GCDF), '') as dosage_form,  -- Human-readable form
    -- ... other fields ...
FROM rndc14 n
LEFT JOIN rgcnseq4 g ON n.GCN_SEQNO = g.GCN_SEQNO
LEFT JOIN rhiclsq1 hc ON g.HICL_SEQNO = hc.HICL_SEQNO
LEFT JOIN retcgc0 tclink ON g.GCN_SEQNO = tclink.GCN_SEQNO AND tclink.ETC_DEFAULT_USE_IND = '1'
LEFT JOIN retctbl0 tc ON tclink.ETC_ID = tc.ETC_ID
LEFT JOIN rlblrid3 lblr ON n.LBLRID = lblr.LBLRID
LEFT JOIN rdosed2 d ON g.GCDF = d.GCDF  -- NEW: Join dosage form lookup
WHERE n.OBSDTEC = '0000-00-00'  -- Active drugs only
```

**Impact:** Redis will have `dosage_form = "CREAM (G)"` or `"GEL (ML)"` instead of "KA" or "3".

**Downside:** Requires full Redis reload (~2 hours).

---

### Fix #2B: Patch Existing Redis Data (Faster)

Create a script to patch existing Redis hashes:
1. Query FDB for NDC → GCDF → DOSE mapping
2. Update each Redis `drug:*` hash with human-readable `dosage_form`
3. No need to regenerate embeddings or drop index

**Estimated Time:** 10-15 minutes

---

### Fix #3: Normalize Dosage Form Values

**Problem:** `rdosed2.DOSE` has very specific values like:
- `"CREAM (G)"` vs `"CREAM (GRAM)"`
- `"GEL (ML)"` vs `"GEL (GRAM)"` vs `"GEL (EA)"`

**Claude extracts:** `"cream"` (lowercase, no unit)

**Solution Options:**

**Option A: Simple Normalization (in Load Script)**
```python
dosage_form = row['dosage_form']
# Normalize: "CREAM (G)" → "CREAM", "GEL (ML)" → "GEL"
dosage_form_simple = dosage_form.split('(')[0].strip() if dosage_form else ''
drug['dosage_form'] = dosage_form_simple
```

**Redis Result:** `dosage_form = "CREAM"` or `"GEL"`

**Option B: Keep Full Description, Update Claude**
```python
# Keep: dosage_form = "CREAM (GRAM)"
# Update Claude prompt to extract: "CREAM (GRAM)"
# Or update Redis query to use wildcard: @dosage_form:*CREAM*
```

**Recommendation:** Use Option A for simplicity.

---

## Testing Plan

### Test Case: "testosterone creams"

**Current Behavior:**
1. ✅ Claude extracts: `{"dosage_form": "cream"}`
2. ❌ Filters are dropped by `merge_filters()`
3. ❌ Returns ALL testosterone products (gels, injections, pellets, etc.)

**Expected Behavior After Fix:**
1. ✅ Claude extracts: `{"dosage_form": "cream"}`
2. ✅ Filter is applied: `@dosage_form:{CREAM}`
3. ✅ Returns only testosterone CREAM products
4. ✅ Groups by manufacturer
5. ✅ Shows only CREAM variants in each group

---

## Next Steps

**Immediate (No Reload Required):**
1. ✅ Export all FDB tables to CSV (DONE)
2. ⏳ Fix `AUTO_APPLY_CLAUDE_FILTERS` to enable filters
3. ⏳ Deploy and test with current data (will still fail, but confirms filter logic works)

**Short-Term (Requires Data Update):**
4. ⏳ Create patch script to update Redis `dosage_form` values
5. ⏳ Run patch script (~10 min)
6. ⏳ Test "testosterone creams" search
7. ⏳ Update Claude prompt to extract strengths as filters

**Long-Term (Next Full Reload):**
8. ⏳ Update `production_load_full_dataset.py` with corrected SQL
9. ⏳ Add `drug_class` as TAG field (from previous issue)
10. ⏳ Full reload with all corrections

---

## Files Created

### CSV Exports
- **Location:** `/workspaces/DAW/database/exports/csv/`
- **Count:** 116 CSV files
- **Key Tables:**
  - `rndc14.csv` - Main NDC table (10 sample rows)
  - `rgcnseq4.csv` - GCN sequence (10 sample rows)
  - `rdosed2.csv` - Dosage form lookup (10 sample rows)
  - `rmidfd1.csv` - Med dosage form IDs (10 sample rows)
  - Plus 112 more tables...

### Scripts
- **Export Script:** `/workspaces/DAW/scripts/export_fdb_samples.py`
  - Exports 10 random rows from each FDB table
  - Creates CSV files for easy text searching
  - Successfully exported 116/118 tables (2 empty)

---

## Grep Commands for Further Investigation

```bash
# Search for specific dosage forms
grep -r -i 'TABLET\|CAPSULE\|INJECTION' database/exports/csv/*.csv

# Search for indication-related tables
grep -r -i 'indication\|indic' database/exports/csv/*.csv

# Search for route information
grep -r -i 'ORAL\|TOPICAL\|INTRAVENOUS' database/exports/csv/*.csv

# Find tables with specific drug names
grep -r -i 'CRESTOR\|ROSUVASTATIN' database/exports/csv/*.csv
```

---

## Summary

**Two critical bugs identified:**
1. ❌ `AUTO_APPLY_CLAUDE_FILTERS = set()` - Drops all Claude filters
2. ❌ `dosage_form` contains FDB codes ("3", "KA") instead of text ("GEL", "CREAM")

**Root cause:** Load script uses wrong field (`rndc14.DF` instead of `rgcnseq4.GCDF + rdosed2.DOSE`)

**Fastest fix:** Enable filters + patch Redis data (~15 min total)
**Best long-term fix:** Update load script for next full reload


# Drug Search Grouping Fix - 2025-11-19

**Status:** ✅ FIXED  
**Issue:** Search results were merging brand and generic drugs into single family groups  
**Solution:** Changed grouping strategy to separate brand families from generic families

---

## Problem Identified

### Original Incorrect Grouping

The search handler was grouping drugs by `gcn_seqno` first:

```python
# OLD LOGIC (WRONG):
group_key = doc.get('gcn_seqno') or doc.get('generic_name') or ...
```

**Result:** CRESTOR (brand) and ROSUVASTATIN CALCIUM (generic) were merged into ONE group because they share the same `gcn_seqno=51784` (for 10mg strength).

### Investigation Results

**What's Actually in Redis (Verified 2025-11-19):**

**CRESTOR 10mg (Brand - INNOV='1'):**
```
ndc: 00310075139
drug_name: "CRESTOR 10 MG TABLET"
brand_name: "CRESTOR"
is_generic: false
gcn_seqno: 51784
```

**ROSUVASTATIN CALCIUM 10mg (Generic - INNOV='0'):**
```
ndc: 00093757198
drug_name: "ROSUVASTATIN CALCIUM 10 MG TAB"
brand_name: "ROSUVASTATIN CALCIUM"
is_generic: true
gcn_seqno: 51784  <-- SAME GCN!
```

**Key Finding:** ✅ Redis has ALL the data needed (brand_name, is_generic, gcn_seqno)  
**Previous Agent Claim:** ❌ GPT Codex incorrectly claimed data needed to be reloaded from Aurora

---

## Solution Implemented

### New Grouping Strategy

```python
# NEW LOGIC (CORRECT):
is_brand = str(doc.get('is_generic', '')).lower() == 'false'
brand_name = doc.get('brand_name', '').strip()

if is_brand and brand_name:
    # Brand drugs: group by brand name
    group_key = f"brand:{brand_name}"
else:
    # Generic drugs: group by GCN
    gcn = doc.get('gcn_seqno')
    if gcn:
        group_key = f"generic:{gcn}"
    else:
        # Fallback for drugs without GCN
        group_key = f"generic:{doc.get('generic_name') or doc.get('drug_name') or doc.get('ndc')}"
```

### Display Name Enhancement

For brand families, use the brand name directly:
```python
display_name = "CRESTOR"
```

For generic families, clean up the name to show just the drug family:
```python
display_name = "ROSUVASTATIN CALCIUM"  # (cleaned from "ROSUVASTATIN CALCIUM 10 MG TAB")
```

---

## Expected Results After Fix

### Search: "ROSUVASTATIN"

Returns TWO separate family groups:

**1. ROSUVASTATIN CALCIUM** (Generic Family)
- Match type: "Exact" (name contains "rosuvastatin")
- is_generic: true
- Variants: 5mg, 10mg, 20mg, 40mg tablets
- gcn_seqno: 51783, 51784, 51785, 51786 (different strengths)

**2. CRESTOR** (Brand Family)  
- Match type: "Alternative" (same GCN family, semantic match)
- is_generic: false
- Variants: 5mg, 10mg, 20mg, 40mg tablets
- gcn_seqno: 51783, 51784, 51785, 51786 (corresponding strengths)

### Search: "CRESTOR"

Returns TWO separate family groups:

**1. CRESTOR** (Brand Family)
- Match type: "Exact" (name contains "crestor")
- is_generic: false
- Primary result

**2. ROSUVASTATIN CALCIUM** (Generic Family)
- Match type: "Alternative" (same GCN, generic equivalent)
- is_generic: true
- Therapeutic alternative

### Search: "drugs for high cholesterol"

Returns MULTIPLE statin family groups:
- LIPITOR (brand)
- ATORVASTATIN (generic)
- CRESTOR (brand)
- ROSUVASTATIN CALCIUM (generic)
- ZOCOR (brand)
- SIMVASTATIN (generic)
- etc.

All marked as "Alternative" (semantic similarity to query).

---

## Code Changes

**File:** `functions/src/search_handler.py`  
**Function:** `group_search_results()` (lines ~508-574)

### Changes Made:

1. **Composite grouping key** - Separates brands from generics
2. **Display name logic** - Shows clean family names
3. **Preserved all metadata** - gcn_seqno, is_generic, brand_name, etc.

### No Changes Needed:

- ✅ Redis data (already has all fields)
- ✅ Redis schema (brand_name field exists)
- ✅ Bulk load process (loads brand_name correctly)
- ✅ Aurora queries (not involved in grouping)

---

## Testing Plan

### Test Queries

1. **"ROSUVASTATIN"** - Should show generic + CRESTOR brand separately
2. **"CRESTOR"** - Should show CRESTOR first, then generic alternative
3. **"statin"** - Should show all statin families (brand and generic separate)
4. **"drugs for high cholesterol"** - Should show various statin families
5. **"lisinopril"** - Should show PRINIVIL brand + lisinopril generic separately

### Success Criteria

- ✅ Brand drugs grouped by brand name (all CRESTOR strengths together)
- ✅ Generic drugs grouped by GCN (all rosuvastatin generics together)
- ✅ No duplicate family rows
- ✅ Each family shows multiple variants (strengths/packages)
- ✅ Match type accurately reflects exact vs alternative
- ✅ is_generic flag correctly shows brand/generic status

---

## Why This Fix is Correct

1. **Separates brand equity** - Doctors want to see "CRESTOR" as distinct from generic
2. **Aligns with medical practice** - Brands and generics are prescribed differently
3. **Uses existing data** - No Aurora queries needed, Redis has everything
4. **Maintains therapeutic grouping** - GCN still used for generics
5. **Preserves search semantics** - Vector similarity + lexical matching unchanged

---

## Related Documents

- `docs/2025-11-19_SEARCH_AND_UI_ALIGNMENT.md` - Original alignment document
- `docs/FDB_DATABASE_SCHEMA_REFERENCE.md` - INNOV and GCN_SEQNO fields
- `docs/GNI_TO_INNOV_CORRECTION_COMPLETE.md` - is_generic field fix
- `functions/src/search_handler.py` - Implementation

---

**Fixed by:** Claude 4.5 Sonnet  
**Fixed on:** 2025-11-19  
**Status:** Ready for deployment and testing



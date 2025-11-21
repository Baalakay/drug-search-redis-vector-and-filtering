# Grouping Logic Fix - Drug Class vs GCN
**Date:** 2025-11-20  
**Status:** ✅ Deployed

---

## Problem Identified

### Issue 1: Generic Drugs Split by Strength
**Before:** Generic drugs were grouped by `GCN_SEQNO` (5-digit code)  
**Problem:** Each strength created a SEPARATE group
```
- Rosuvastatin 5mg  (GCN 52944) - separate group
- Rosuvastatin 10mg (GCN 51784) - separate group  
- Rosuvastatin 20mg (GCN 51785) - separate group
- Rosuvastatin 40mg (GCN 51786) - separate group
```

**After:** Generic drugs grouped by `drug_class` (ingredient name)  
**Solution:** All strengths together in ONE group
```
- Rosuvastatin Calcium
  ├─ 5mg tablet
  ├─ 10mg tablet
  ├─ 20mg tablet
  └─ 40mg tablet
```

### Issue 2: Multiple NDCs Without Manufacturer Info
**Before:** UI showed many duplicate "ROSUVASTATIN CALCIUM 5 MG TAB" entries with different NDCs  
**Problem:** Each NDC is a different manufacturer/package, but no way to distinguish them

**After:** Variants now include `manufacturer_name` and `strength` fields
```json
{
  "ndc": "13668072005",
  "label": "ROSUVASTATIN CALCIUM 5 MG TAB",
  "strength": "5 MG",
  "manufacturer": "TORRENT PHARMA",
  "dosage_form": "TABLET"
}
```

---

## FDB Data Structure Clarification

### GCN (Generic Code Number) - 5 digits
- **Definition:** Identifies specific drug formulation (ingredient + strength + form)
- **Scope:** Narrow - different strengths have different GCNs
- **Example:** 
  - Rosuvastatin 5mg tablet = GCN 52944
  - Rosuvastatin 10mg tablet = GCN 51784

### Drug Class (Ingredient Name)
- **Definition:** Active ingredient(s) in the drug
- **Scope:** Broad - covers all strengths and forms
- **Source:** `rhiclsq1.GNN` via `rgcnseq4.HICL_SEQNO`
- **Example:** "rosuvastatin calcium" (covers all strengths)

### GSN (Generic Sequence Number) - 6 digits
- **Note:** FDB doesn't use GSN in our schema. The field is called `GCN_SEQNO` but is actually a 5-digit GCN.

---

## Code Changes

### 1. Test Load Script (`2025-11-19_test_load_100_drugs.py`)

**Added Manufacturer Name:**
```sql
LEFT JOIN rlblrid3 lbl ON n.LBLRID = lbl.LBLRID
```

**New Fields:**
- `labeler_id` - FDB labeler code (e.g., "A54569")
- `manufacturer_name` - Human-readable name (e.g., "A-S MEDICATION")

### 2. Search Handler (`search_handler.py`)

**Changed Grouping Logic:**
```python
# OLD: Group by GCN (splits by strength)
if not is_branded_product:
    group_key = f"generic:{gcn}"

# NEW: Group by drug_class (combines all strengths)
if not is_branded_product:
    drug_class = doc.get('drug_class', '').strip()
    if drug_class:
        group_key = f"generic:{drug_class}"
```

**Enhanced Variant Structure:**
```python
group['variants'].append({
    'ndc': doc.get('ndc'),
    'label': doc.get('drug_name'),
    'dosage_form': doc.get('dosage_form'),
    'strength': strength,              # NEW
    'manufacturer': doc.get('manufacturer_name', ''),  # NEW
    'is_generic': is_generic,
    'similarity_score': score,
    'dea_schedule': dea
})
```

---

## Expected Search Results

### Search: "crestor"

**Result 1: CRESTOR (Brand)**
- Match: 100% (Exact match)
- Type: Brand
- Variants:
  - 5 MG TABLET (4 formats from different manufacturers)
  - 10 MG TABLET (4 formats from different manufacturers)
  - 20 MG TABLET (4 formats from different manufacturers)
  - 40 MG TABLET (4 formats from different manufacturers)

**Result 2: Rosuvastatin Calcium (Generic Alternative)**
- Match: 85% (Same therapeutic class)
- Type: Generic
- Reason: Same therapeutic class (Antihyperlipidemic - HMG CoA Reductase Inhibitors)
- Variants:
  - 5 MG TAB - A-S MEDICATION
  - 5 MG TAB - TORRENT PHARMA
  - 5 MG TAB - ACCORD HEALTHCARE
  - 10 MG TAB - A-S MEDICATION
  - ... (all strengths, all manufacturers)

**Result 3: Other Statins (Alternative)**
- Atorvastatin, Simvastatin, etc.
- Only shown if in same therapeutic class

---

## Deployment Status

✅ Test data reloaded with manufacturer names (100 drugs)  
✅ Search handler deployed with new grouping logic  
✅ Therapeutic class filtering active  
✅ Exact match boosting (100% score)

---

## Next Steps

1. **Test UI** - Verify grouping works correctly
2. **Check Variants** - Ensure "View formats" shows proper hierarchy
3. **Test Queries** - Run realistic doctor searches
4. **Full Load** - If tests pass, load all 121k active drugs

---

## Files Modified

- `/workspaces/DAW/scripts/2025-11-19_test_load_100_drugs.py` - Added manufacturer join
- `/workspaces/DAW/functions/src/search_handler.py` - Changed grouping from GCN to drug_class


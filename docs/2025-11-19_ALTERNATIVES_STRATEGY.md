# Alternative Drugs Strategy - Option B

**Date:** 2025-11-19  
**Decision:** Same GCN + Same Drug Class (Option B)

---

## How Alternatives Are Determined

When searching for a specific drug (e.g., "Crestor"), results should include:

### 1. Exact Match (Top Result)
- **Brand Family:** All CRESTOR variants grouped together
- **Match Badge:** "Exact Match"
- **Grouping Key:** `brand:CRESTOR`

### 2. Therapeutic Equivalents (Same GCN)
- **What:** Generic versions of the same drug (e.g., Rosuvastatin for CRESTOR)
- **Match Badge:** "Generic Alternative" or "Therapeutic Equivalent"
- **Matching Logic:** `gcn_seqno` matches the original drug's GCN
- **Example:** CRESTOR (GCN=57784) → Rosuvastatin Generic (GCN=57784)

### 3. Same Drug Class Alternatives
- **What:** Different drugs in the same therapeutic class (e.g., other statins)
- **Match Badge:** "Alternative" or "Same Class"
- **Matching Logic:** `drug_class` matches the original drug's class
- **Example:** CRESTOR (class=HMG-CoA REDUCTASE INHIBITORS) → Atorvastatin, Simvastatin, Pravastatin

---

## Required Redis Fields

| Field | Source | Critical? | Purpose |
|-------|--------|-----------|---------|
| `gcn_seqno` | `rndc14.GCN_SEQNO` | ✅ CRITICAL | Find therapeutic equivalents |
| `drug_class` | `rgcnseq4.HIC3` → `rhclass.HIC3DESC` | ✅ CRITICAL | Find same-class alternatives |
| `is_generic` | `rndc14.INNOV` | ✅ CRITICAL | Badge display logic |
| `is_brand` | `rndc14.INNOV` | ✅ CRITICAL | Badge display logic |
| `indication` | `rdlim14` + `rdindc` | ⚠️ NICE TO HAVE | Additional context |

---

## Search Result Example: "Crestor"

```json
{
  "results": [
    {
      "group_id": "brand:CRESTOR",
      "display_name": "CRESTOR",
      "is_generic": false,
      "gcn_seqno": 57784,
      "drug_class": "HMG-CoA REDUCTASE INHIBITORS",
      "match_type": "exact",
      "match_reason": "Brand name contains 'crestor'"
    },
    {
      "group_id": "generic:57784",
      "display_name": "rosuvastatin calcium",
      "is_generic": true,
      "gcn_seqno": 57784,
      "drug_class": "HMG-CoA REDUCTASE INHIBITORS",
      "match_type": "alternative",
      "match_reason": "Therapeutic equivalent (same GCN)"
    },
    {
      "group_id": "generic:25521",
      "display_name": "atorvastatin calcium",
      "is_generic": true,
      "gcn_seqno": 25521,
      "drug_class": "HMG-CoA REDUCTASE INHIBITORS",
      "match_type": "alternative",
      "match_reason": "Same drug class"
    },
    {
      "group_id": "brand:LIPITOR",
      "display_name": "LIPITOR",
      "is_generic": false,
      "gcn_seqno": 25521,
      "drug_class": "HMG-CoA REDUCTASE INHIBITORS",
      "match_type": "alternative",
      "match_reason": "Same drug class"
    }
  ]
}
```

---

## Match Classification Logic

```python
def classify_match_type(doc, search_terms, original_gcn, original_class):
    """Classify how this drug matches the search"""
    
    # 1. Exact match by name
    brand = doc.get('brand_name', '').lower()
    generic = doc.get('generic_name', '').lower()
    
    for term in search_terms:
        if term in brand or term in generic:
            return 'exact', f'Name contains "{term}"'
    
    # 2. Therapeutic equivalent (same GCN)
    if doc.get('gcn_seqno') == original_gcn:
        is_generic = doc.get('is_generic') == 'true'
        if is_generic:
            return 'alternative', 'Generic equivalent (same active ingredient)'
        else:
            return 'alternative', 'Brand equivalent (same active ingredient)'
    
    # 3. Same drug class
    if doc.get('drug_class') == original_class:
        return 'alternative', 'Same drug class'
    
    # 4. Semantic similarity (fallback)
    return 'alternative', 'Semantic similarity match'
```

---

## UI Display

### Result Card for Exact Match
```
┌─────────────────────────────────────────┐
│ 🏷️ CRESTOR                    [BRAND]  │
│ Generic: rosuvastatin calcium           │
│ Class: HMG-CoA Reductase Inhibitor      │
│ ✓ Exact Match                           │
│ 19 forms available                      │
│ [SELECT]                                │
└─────────────────────────────────────────┘
```

### Result Card for Generic Alternative
```
┌─────────────────────────────────────────┐
│ 💊 rosuvastatin calcium      [GENERIC]  │
│ Brand: CRESTOR                          │
│ Class: HMG-CoA Reductase Inhibitor      │
│ 🔄 Generic Alternative                  │
│ 45 forms available                      │
│ [SELECT]                                │
└─────────────────────────────────────────┘
```

### Result Card for Same Class Alternative
```
┌─────────────────────────────────────────┐
│ 💊 atorvastatin calcium      [GENERIC]  │
│ Brand: LIPITOR                          │
│ Class: HMG-CoA Reductase Inhibitor      │
│ ⚡ Alternative (Same Class)             │
│ 67 forms available                      │
│ [SELECT]                                │
└─────────────────────────────────────────┘
```

---

## Data Quality Requirements

For Option B to work correctly:

### Critical: Accurate `drug_class`
- **Must verify:** `rgcnseq4.HIC3` → `rhclass.HIC3DESC` mappings are correct
- **Test:** Load CRESTOR and verify `drug_class` = "HMG-CoA REDUCTASE INHIBITORS" or similar
- **Fallback:** If drug_class is empty/null, still show therapeutic equivalents (GCN-based)

### Critical: Accurate `gcn_seqno`
- **Assumption:** FDB GCN data is reliable (industry standard)
- **Test:** Verify CRESTOR and rosuvastatin generic have same GCN

### Nice to Have: `indication`
- **Use:** Additional context in detail view
- **Not required:** For alternatives matching logic

---

## Benefits of Option B

1. **Clinical Utility:** Doctors can see both exact equivalents AND therapeutic alternatives
2. **Formulary Flexibility:** Insurance may prefer generic or different drug in same class
3. **Patient Options:** Price-sensitive patients can see multiple options
4. **Predictable:** Clear hierarchy (Exact → Same GCN → Same Class)

---

**Status:** ✅ CONFIRMED - Proceeding with Option B implementation


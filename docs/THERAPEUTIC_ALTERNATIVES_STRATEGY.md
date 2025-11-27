# GCN_SEQNO and Therapeutic Alternatives - Implementation Status

**Date:** 2025-11-15  
**Status:** PARTIAL IMPLEMENTATION - Needs API logic

---

## ✅ What We're Currently Doing

### 1. **GCN_SEQNO is Stored in Redis**

Yes, we ARE storing `gcn_seqno` for every drug:

```python
# From bulk_load_drugs_hash.py (line 218)
'gcn_seqno': str(drug.get('gcn_seqno', 0))
```

**Current Status:**
- ✅ All 493,573 drugs have `gcn_seqno` stored in Redis
- ✅ Field is indexed as NUMERIC SORTABLE in Redis
- ✅ Can be used for filtering and grouping

### 2. **What GCN_SEQNO Represents**

**GCN_SEQNO = Generic Code Number Sequence**

This is FDB's primary identifier for grouping **therapeutically equivalent drugs** that can be substituted for each other.

**Examples from FDB:**
- `GCN_SEQNO = 25462`: All lisinopril 10mg products (generic AND brand)
- `GCN_SEQNO = 9881`: All atorvastatin 10mg products
- **32,257 unique GCN codes** across all 493K drugs

**What "Therapeutically Equivalent" Means:**
- Same active ingredient
- Same strength
- Same dosage form (tablet, capsule, etc.)
- Bioequivalent (FDA-approved as substitutable)

**Example:**
All of these share the same GCN_SEQNO:
- LISINOPRIL 10 MG TABLET (generic, various manufacturers)
- PRINIVIL 10 MG TABLET (brand name)
- ZESTRIL 10 MG TABLET (brand name)

They can be substituted for each other because they have the **same therapeutic effect**.

---

## ❌ What We're NOT Doing Yet

### **Therapeutic Alternatives Logic in API**

We currently have **NO API implementation** to:
1. Find all drugs with the same `gcn_seqno` (therapeutic equivalents)
2. Display generic alternatives for a brand drug
3. Display all brand options for a generic
4. Sort alternatives by price or manufacturer

---

## 🎯 How This Should Work (Proposed Implementation)

### **Scenario 1: Doctor searches for "lisinopril 10mg"**

**Current Behavior:**
1. Claude expands: "lisinopril ACE inhibitor blood pressure"
2. Redis returns top 20 vector matches
3. Aurora enriches with full details
4. **DONE** ✅

**What We Should ADD:**
5. For each result, query: "Show me all alternatives with same GCN_SEQNO"
6. Group results by GCN_SEQNO
7. Show user: "15 generic options, 2 brand options"
8. Allow filtering by manufacturer, price, package size

### **Scenario 2: Doctor clicks on a specific drug**

**Proposed Flow:**
```python
# 1. Get the selected drug's GCN
selected_drug = get_drug_by_ndc("00093111301")
gcn = selected_drug['gcn_seqno']  # e.g., 25462

# 2. Find all therapeutic equivalents
query = f"@gcn_seqno:[{gcn} {gcn}]"  # Exact match on GCN
alternatives = redis_client.ft("drugs_idx").search(
    Query(query)
    .return_fields("ndc", "drug_name", "brand_name", "is_generic", "gcn_seqno")
    .sort_by("is_generic", "asc")  # Generic first
    .paging(0, 100)
)

# 3. Enrich from Aurora (get pricing, manufacturer, etc.)
ndcs = [alt.ndc for alt in alternatives]
full_data = aurora.query(
    "SELECT * FROM rndc14 JOIN rnp2 ON rndc14.NDC = rnp2.NDC WHERE rndc14.NDC IN (%s)",
    ndcs
)

# 4. Return grouped alternatives
return {
    "selected_drug": selected_drug,
    "alternatives": {
        "generic_options": [d for d in full_data if d['is_generic'] == 'true'],
        "brand_options": [d for d in full_data if d['is_generic'] == 'false'],
        "total_count": len(full_data)
    }
}
```

**API Response Example:**
```json
{
  "selected_drug": {
    "ndc": "00093111301",
    "drug_name": "LISINOPRIL 10 MG TABLET",
    "gcn_seqno": 25462,
    "is_generic": true
  },
  "alternatives": {
    "generic_options": [
      {
        "ndc": "00093111301",
        "drug_name": "LISINOPRIL 10 MG TABLET",
        "manufacturer": "TEVA",
        "price": "$4.99",
        "is_generic": true
      },
      {
        "ndc": "00378018093",
        "drug_name": "LISINOPRIL 10 MG TABLET",
        "manufacturer": "MYLAN",
        "price": "$5.49",
        "is_generic": true
      }
      // ... 13 more generic options
    ],
    "brand_options": [
      {
        "ndc": "00006001928",
        "drug_name": "PRINIVIL 10 MG TABLET",
        "manufacturer": "MERCK",
        "price": "$89.99",
        "is_generic": false
      },
      {
        "ndc": "00310012990",
        "drug_name": "ZESTRIL 10 MG TABLET",
        "manufacturer": "ASTRAZENECA",
        "price": "$95.00",
        "is_generic": false
      }
    ],
    "total_count": 17
  }
}
```

---

## 📊 Additional FDB Tables for Richer Alternatives

### **Beyond Basic Substitution (Future Enhancement)**

While GCN_SEQNO handles **exact therapeutic equivalents** (same drug, same strength), FDB provides additional tables for **broader therapeutic alternatives**:

#### **1. `rgcnseq4` - Drug Classification**
- Links to `GCN_SEQNO`
- Provides therapeutic class, ingredient codes
- Example: "All ACE inhibitors" (not just lisinopril)

#### **2. `rdlimxx` tables - Drug-Indication Mappings**
- What conditions each drug treats
- Example: "All drugs for hypertension" (ACE inhibitors, beta blockers, calcium channel blockers, etc.)

#### **3. `rnp2` - Pricing Data**
- 12.8 million pricing records
- Allows sorting alternatives by cost
- Critical for doctors to find cheapest option

**Example Query for "Related Therapeutic Alternatives":**
```sql
-- Find all drugs in the same therapeutic class as lisinopril
SELECT d.*
FROM rndc14 d
JOIN rgcnseq4 g1 ON d.GCN_SEQNO = g1.GCN_SEQNO
JOIN rgcnseq4 g2 ON g1.HIC3 = g2.HIC3  -- Same therapeutic class
WHERE g2.GCN_SEQNO = (
    SELECT GCN_SEQNO FROM rndc14 WHERE NDC = '00093111301'
)
```

This would return:
- Lisinopril (exact match)
- Enalapril (same class - ACE inhibitor)
- Ramipril (same class - ACE inhibitor)
- etc.

---

## 🚀 Recommended Implementation Plan

### **Phase 1: Basic Therapeutic Equivalents (Week 4)**
1. ✅ GCN_SEQNO already in Redis
2. Add API endpoint: `GET /drugs/{ndc}/alternatives`
3. Query Redis by GCN_SEQNO range: `@gcn_seqno:[{gcn} {gcn}]`
4. Enrich from Aurora with pricing
5. Return grouped by generic/brand

### **Phase 2: Enhanced Search UI (Week 5)**
1. Show "X alternatives available" badge on search results
2. Click to expand and show all options
3. Sort by price, manufacturer, package size
4. Highlight cost savings (brand vs generic)

### **Phase 3: Broader Therapeutic Class (Future)**
1. Join to `rgcnseq4` for therapeutic class
2. Show "Similar drugs" section (e.g., other ACE inhibitors)
3. Requires more complex Aurora joins

---

## ⚠️ Current Gaps

1. **❌ No API endpoint** to retrieve alternatives by GCN
2. **❌ No pricing data** in Redis (only in Aurora `rnp2`)
3. **❌ No manufacturer data** in Redis (only `LBLRID` code)
4. **❌ No UI/UX** for displaying alternatives to users

---

## 💡 Key Takeaways

1. ✅ **GCN_SEQNO is stored** - We have the foundation
2. ✅ **It's indexed in Redis** - Can query efficiently
3. ✅ **FDB data is comprehensive** - Supports full therapeutic alternatives
4. ❌ **API logic not implemented** - Needs to be built in Phase 6 (Search API)
5. 💰 **Pricing is critical** - Doctors need cost comparison for alternatives

**Next Step:** When we build the Search API (Phase 6), we need to add the alternatives endpoint that leverages `gcn_seqno` for therapeutic substitution.

---

**Status:** Documentation complete, ready for Phase 6 implementation  
**Related Files:**
- `/workspaces/DAW/docs/FDB_DATABASE_SCHEMA_REFERENCE.md`
- `/workspaces/DAW/docs/REDIS_FINAL_SCHEMA.md`
- `/workspaces/DAW/scripts/create-indexes.sql`


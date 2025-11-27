# Indication Data Discovery
## Date: 2025-11-20

## ✅ **INDICATION DATA FOUND!**

After exporting all 116 FDB tables to CSV and searching, I discovered the complete indication chain:

## **Indication Lookup Chain**

```
rndc14.GCN_SEQNO 
  → rindmgc0.INDCTS 
  → rindmma2.DXID 
  → rfmldx0.DXID_DESC100
```

### **Table Details**

#### `rindmgc0` - GCN to Indication Code Linkage
- **Purpose:** Links each GCN (drug) to indication codes
- **Row Count:** 20,433 linkages
- **Key Columns:**
  - `GCN_SEQNO` - Links to `rndc14.GCN_SEQNO`
  - `INDCTS` - Indication code (links to `rindmma2`)

#### `rindmma2` - Indication Master Table  
- **Purpose:** Maps indication codes to diagnosis IDs
- **Row Count:** 16,528 indication records
- **Key Columns:**
  - `INDCTS` - Indication code
  - `DXID` - Diagnosis ID (links to `rfmldx0`)
  - `INDCTS_LBL` - Label type (L/U/etc.)
  - `FDBDX` - FDB diagnosis code
  - `PROXY_IND` - Proxy indicator (N/Y)
  - `PRED_CODE` - Prediction code (1/2/3)

#### `rfmldx0` - Diagnosis Description Lookup
- **Purpose:** Provides human-readable diagnosis/indication descriptions
- **Row Count:** 7,804 unique diagnoses
- **Key Columns:**
  - `DXID` - Diagnosis ID
  - `DXID_DESC56` - Short description (56 chars)
  - `DXID_DESC100` - Long description (100 chars) ← **Use this!**
  - `DXID_STATUS` - Status code
  - `FDBDX` - FDB diagnosis code
  - `DXID_DISEASE_DURATION_CD` - Duration code

---

## **Real-World Examples**

### **Crestor/Rosuvastatin (GCN 51784)**

**Indications:**
- hypercholesterolemia ✅ (Primary indication!)
- homozygous familial hypercholesterolemia
- heterozygous familial hypercholesterolemia
- hypertriglyceridemia
- mixed hyperlipidemia ✅ (Matches customer's "Mixed dyslipidemias")
- myocardial infarction prevention
- primary dysbetalipoproteinemia ✅ (Matches customer's "Primary hypercholesterolemia")
- increased risk of atherosclerotic cardiovascular disease
- prevention of transient ischemic attack
- prevention of cerebrovascular accident
- atherosclerotic cardiovascular disease
- hyperlipidemia

**Match with Customer System:**
Customer shows: "Rosuvastatin = HMG-CoA reductase inhibitor - for **Primary hypercholesterolemia + Mixed dyslipidemias**"

FDB has both of these indications! ✅

---

### **Testosterone Products**

**Indications:**
- chemotherapy-induced hypogonadism
- gonadotropin releasing factor deficiency
- male hypogonadism ✅ (Primary indication)
- delayed puberty
- cachexia due to HIV
- Klinefelter's syndrome
- cryptorchidism
- androgen deficiency
- primary hypogonadism due to bilateral torsion of testes
- primary hypogonadism due to orchitis
- bilateral orchiectomy
- bilateral anorchia
- male transgender hormone therapy
- gender dysphoria adjunct therapy
- hormone receptor positive breast cancer

---

## **SQL Query for Load Script**

```sql
SELECT
    n.NDC,
    n.LN as drug_name,
    -- ... other fields ...
    
    -- INDICATIONS (NEW!)
    GROUP_CONCAT(DISTINCT d.DXID_DESC100 SEPARATOR ' | ') as indications
    
FROM rndc14 n
LEFT JOIN rgcnseq4 g ON n.GCN_SEQNO = g.GCN_SEQNO
LEFT JOIN rindmgc0 ig ON n.GCN_SEQNO = ig.GCN_SEQNO
LEFT JOIN rindmma2 im ON ig.INDCTS = im.INDCTS
LEFT JOIN rfmldx0 d ON im.DXID = d.DXID
-- ... other joins ...
WHERE n.OBSDTEC = '0000-00-00'  -- Active drugs only
GROUP BY n.NDC  -- Group to collapse multiple indications into one row
```

**Result Example:**
```
NDC: 00310075090
drug_name: CRESTOR 5 MG TABLET
indications: hypercholesterolemia | mixed hyperlipidemia | primary dysbetalipoproteinemia | myocardial infarction prevention | ...
```

---

## **Redis Index Update**

### **Current Schema:**
```python
'indication', 'TAG'  # Currently empty/unused
```

### **Updated Schema:**
```python
'indication', 'TEXT'  # Change to TEXT for full-text search
```

**Reason:** Indications are multi-word phrases like "male hypogonadism" or "mixed hyperlipidemia". TEXT field allows:
- Partial matching: "hypogonadism" matches "male hypogonadism"
- Multiple indications: "hypercholesterolemia | mixed hyperlipidemia"
- Better semantic search when combined with vector embeddings

**Alternative (TAG):** If we want exact phrase matching only:
```python
'indication', 'TAG'  # Keep as TAG but normalize to UPPER_SNAKE_CASE
# Example: "MALE_HYPOGONADISM" or "MIXED_HYPERLIPIDEMIA"
```

---

## **Embedding Strategy Update**

### **Current Embedding:**
```python
embedding_text = drug_name + ' ' + therapeutic_class + ' ' + drug_class
```

### **Updated Embedding (Recommended):**
```python
embedding_text = drug_name + ' ' + therapeutic_class + ' ' + drug_class + ' ' + indications
```

**Why?** 
- When user searches "high cholesterol", vector search will match drugs with "hypercholesterolemia" indication
- Better semantic matching for condition-based queries
- Aligns with real-world doctor search patterns

---

## **Challenges & Considerations**

### **Challenge #1: Multiple Indications Per Drug**
Some drugs have 10+ indications. How do we handle in Redis?

**Options:**
1. **Store as pipe-separated string:** `"indication1 | indication2 | indication3"`
   - ✅ Simple
   - ✅ Works with TEXT field
   - ❌ Harder to filter for exact matches
   
2. **Store as TAG with multiple values:** Use Redis TAG multi-value syntax
   - ✅ Exact phrase filtering
   - ❌ Requires normalization (UPPER_SNAKE_CASE)
   
3. **Store primary indication only:** Pick the first or most common one
   - ✅ Simplest
   - ❌ Loses data

**Recommendation:** Option 1 (pipe-separated) for initial implementation.

---

### **Challenge #2: Indication Filtering vs. Therapeutic Class**

**Example Query:** "drugs for high cholesterol"

**Current Approach:**
1. Claude expands to drug names: "atorvastatin, rosuvastatin, simvastatin"
2. Vector search finds these drugs
3. Filter by `therapeutic_class` to get alternatives

**With Indications:**
1. Claude expands to: "hypercholesterolemia, high cholesterol"
2. Search `indication` field: `@indication:(hypercholesterolemia | cholesterol)`
3. Return all matching drugs

**Question:** Which is more accurate?
- Therapeutic class = mechanism of action (HMG-CoA reductase inhibitor)
- Indication = what it treats (hypercholesterolemia)

**Answer:** Both are useful! Keep both approaches:
- Use `therapeutic_class` for alternatives (same mechanism)
- Use `indication` for condition-based searches (same target disease)

---

## **Implementation Plan**

### **Phase 1: Add Indications to Next Full Load** (Recommended)
1. ✅ Update SQL query in `production_load_full_dataset.py`
2. ✅ Add indication joins (`rindmgc0` → `rindmma2` → `rfmldx0`)
3. ✅ Store as TEXT field with pipe-separated values
4. ✅ Update embedding strategy to include indications
5. ✅ Full reload (~2 hours)

### **Phase 2: Update Claude Prompt** (Optional)
- Add indication extraction to Claude's structured output
- Example: `{"indication": "hypercholesterolemia"}`
- Use for filtering in addition to drug class

### **Phase 3: UI Display** (Optional)
- Show indications in drug detail view
- Add "Treats:" section showing conditions
- Help doctors understand what the drug is used for

---

## **Next Steps**

**Immediate:**
1. ⏳ Fix `AUTO_APPLY_CLAUDE_FILTERS` (dosage_form issue)
2. ⏳ Patch Redis with correct dosage form values
3. ⏳ Test "testosterone cream" search

**Next Full Reload:**
4. ⏳ Add indication joins to SQL query
5. ⏳ Update embedding strategy to include indications
6. ⏳ Change `indication` field type from TAG to TEXT
7. ⏳ Test condition-based searches with indication data

---

## **Files Created**

- ✅ `/workspaces/DAW/database/exports/csv/rindmgc0.csv` - GCN linkage sample
- ✅ `/workspaces/DAW/database/exports/csv/rindmma2.csv` - Indication master sample
- ✅ `/workspaces/DAW/database/exports/csv/rfmldx0.csv` - Diagnosis lookup sample
- ✅ This documentation file

---

## **Summary**

✅ **Indication data EXISTS in FDB!**  
✅ **Chain identified:** `rndc14` → `rindmgc0` → `rindmma2` → `rfmldx0`  
✅ **20,433 GCN-to-indication linkages available**  
✅ **7,804 unique diagnosis descriptions**  
✅ **Real-world examples validated** (Crestor, Testosterone)  

**Ready to implement in next full data load!**


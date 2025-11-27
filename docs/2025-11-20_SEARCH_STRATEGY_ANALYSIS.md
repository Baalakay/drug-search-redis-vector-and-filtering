# Search Strategy Analysis: Field Types & Query Patterns
## Date: 2025-11-20

---

## **Field Type Options**

| Type | Matching | Speed | Use Case |
|------|----------|-------|----------|
| **TAG** | Exact match | ⚡ Fastest | Categorical data (e.g., "CREAM", "HYPERCHOLESTEROLEMIA") |
| **TEXT** | Tokenized, partial | 🐇 Fast | Full-text search with partial matching |
| **VECTOR** | Semantic similarity | 🐢 Slowest | Fuzzy/synonym matching, misspellings |

---

## **Scenario Analysis**

### **Scenario 1: Medical Indication Search**
**User Query:** `"hypercholesterolemia"`

#### **Approach A: Indication as TAG Field**
```python
# Redis query
@indication:{HYPERCHOLESTEROLEMIA}
```

**Flow:**
1. User types: "hypercholesterolemia"
2. Claude extracts: `{"indication": "hypercholesterolemia"}`
3. Normalize to TAG: `"HYPERCHOLESTEROLEMIA"`
4. Redis TAG filter: `@indication:{HYPERCHOLESTEROLEMIA}`
5. Return all drugs with exact match

**Pros:**
- ⚡ **Fastest** (TAG filter, no vector search)
- ✅ **Deterministic** (exact matches only)
- ✅ **Scalable** (no embedding generation)

**Cons:**
- ❌ **Requires exact match:** If FDB has "homozygous familial hypercholesterolemia" and Claude extracts "hypercholesterolemia", won't match
- ❌ **Synonym issues:** "high cholesterol" ≠ "hypercholesterolemia"
- ❌ **Multiple indications:** If drug has "hypercholesterolemia | mixed hyperlipidemia", TAG might not work well

**Accuracy:** 7/10 (depends on Claude's medical terminology)  
**Performance:** 10/10  
**Risk:** High - Claude must use EXACT FDB terminology

---

#### **Approach B: Indication as TEXT Field**
```python
# Redis query
@indication:(hypercholesterolemia)
```

**Flow:**
1. User types: "hypercholesterolemia"
2. Claude extracts: `{"indication": "hypercholesterolemia"}`
3. Redis TEXT search: `@indication:(hypercholesterolemia)`
4. Matches any drug with that word in indication field

**Pros:**
- ✅ **Partial matching:** "hypercholesterolemia" matches "homozygous familial hypercholesterolemia"
- ✅ **Multiple indications:** Works with pipe-separated values
- 🐇 **Fast** (faster than vector, slower than TAG)

**Cons:**
- ❌ **No synonyms:** "high cholesterol" won't match "hypercholesterolemia"
- ❌ **Still requires medical terms:** Claude must extract proper medical terminology

**Accuracy:** 8/10 (better than TAG for partial matches)  
**Performance:** 8/10  
**Risk:** Medium - Claude must use medical terms, but partial matching helps

---

#### **Approach C: Indication as VECTOR + Claude Drug Name Expansion**
```python
# Current approach (no indication field)
# Vector search on drug names
```

**Flow:**
1. User types: "hypercholesterolemia"
2. Claude expands to drug names: `["atorvastatin", "rosuvastatin", "simvastatin", ...]`
3. Vector search on drug names (embedding includes indication data)
4. Filter by therapeutic class of found drugs

**Pros:**
- ✅ **Works now** (already implemented)
- ✅ **No new fields needed**
- ✅ **Semantic matching** (embedding can capture indication similarity)

**Cons:**
- 🐢 **Slower** (vector search + class filtering)
- ❌ **Indirect:** Searches drugs, not indications
- ❌ **Relies on Claude expansion accuracy**

**Accuracy:** 8/10 (good if Claude expands correctly)  
**Performance:** 5/10  
**Risk:** Medium - Depends on Claude's drug knowledge

---

#### **Approach D: Hybrid - Indication as TEXT + Vector Fallback**
```python
# Try TEXT search first, fall back to vector
if indication_extracted:
    @indication:(indication_term)
else:
    vector_search(embedding_with_indication)
```

**Flow:**
1. User types: "hypercholesterolemia"
2. Claude extracts: `{"indication": "hypercholesterolemia"}`
3. TEXT search: `@indication:(hypercholesterolemia)`
4. If no results, fall back to vector search

**Pros:**
- ✅ **Fast path** (TEXT) for exact/partial matches
- ✅ **Fallback** (VECTOR) for synonyms/fuzzy
- ✅ **Best of both worlds**

**Cons:**
- ❌ **Complexity:** Two search paths to maintain
- ❌ **Embedding overhead:** Still need to include indication in embedding

**Accuracy:** 9/10  
**Performance:** 7/10 (depends on hit rate)  
**Risk:** Low - Multiple fallback strategies

---

### **Scenario 2: Drug Name + Dosage Form**
**User Query:** `"testosterone cream"`

#### **Approach A: Dosage Form as TAG Field**
```python
# Redis query
@drug_name:(testosterone) @dosage_form:{CREAM}
```

**Flow:**
1. User types: "testosterone cream"
2. Claude extracts: `{"drug_name": "testosterone", "dosage_form": "cream"}`
3. Normalize: `dosage_form = "CREAM"`
4. Vector search: drug_name="testosterone" (boosted)
5. TAG filter: `@dosage_form:{CREAM}`
6. Return only creams

**Pros:**
- ⚡ **Fast** (vector for drug, TAG for form)
- ✅ **Accurate** (exact dosage form match)
- ✅ **Simple:** Dosage forms are standardized (CREAM, GEL, TABLET, etc.)

**Cons:**
- ❌ **Normalization required:** FDB has "CREAM (GRAM)" vs "CREAM (ML)"
- ❌ **Must normalize in load script:** "CREAM (GRAM)" → "CREAM"

**Accuracy:** 10/10 (with normalization)  
**Performance:** 9/10  
**Risk:** Low - Dosage forms are standard medical terms

**Recommendation:** ✅ **USE THIS** for dosage_form

---

#### **Approach B: Dosage Form as TEXT Field**
```python
# Redis query
@drug_name:(testosterone) @dosage_form:(cream)
```

**Flow:**
1. User types: "testosterone cream"
2. Claude extracts: `{"dosage_form": "cream"}`
3. TEXT search: `@dosage_form:(cream)`
4. Matches "CREAM (GRAM)", "CREAM (ML)", etc.

**Pros:**
- ✅ **No normalization:** "cream" matches "CREAM (GRAM)" automatically
- ✅ **Flexible:** Partial matching

**Cons:**
- 🐇 **Slower** than TAG
- ❌ **Overmatch risk:** "cream" might match "ice cream" (unlikely but possible)

**Accuracy:** 9/10  
**Performance:** 7/10  
**Risk:** Low

---

### **Scenario 3: Plain Language Condition**
**User Query:** `"itchy skin"`

#### **Approach A: Claude Converts → Indication TAG**
```python
# Claude extracts medical term
{"indication": "eczema"}
# Redis TAG filter
@indication:{ECZEMA}
```

**Flow:**
1. User types: "itchy skin"
2. Claude converts to medical term: `{"indication": "eczema"}`
3. TAG filter: `@indication:{ECZEMA}`
4. Return all drugs for eczema

**Pros:**
- ⚡ **Fast** (TAG filter)
- ✅ **Accurate** (if Claude converts correctly)

**Cons:**
- ❌ **High risk:** "itchy skin" could be:
  - Eczema (atopic dermatitis)
  - Psoriasis
  - Contact dermatitis
  - Allergic reaction
  - Dry skin
  - Fungal infection
- ❌ **Single term limitation:** Claude picks ONE indication, but multiple might be valid

**Accuracy:** 6/10 (high risk of wrong indication)  
**Performance:** 10/10  
**Risk:** High - Medical diagnosis from symptoms is complex

---

#### **Approach B: Claude Expands to Drug Names (Current)**
```python
# Claude expands to drugs used for "itchy skin"
["hydrocortisone", "triamcinolone", "cetirizine", ...]
```

**Flow:**
1. User types: "itchy skin"
2. Claude expands to common treatments: `["hydrocortisone", "cetirizine", ...]`
3. Vector search for these drug names
4. Filter by therapeutic class

**Pros:**
- ✅ **Covers multiple conditions:** Returns drugs for various causes
- ✅ **Works now** (already implemented)
- ✅ **Broader results:** Better for ambiguous symptoms

**Cons:**
- 🐢 **Slower** (vector search)
- ❌ **Less precise:** Returns many drugs

**Accuracy:** 7/10 (broad but not precise)  
**Performance:** 5/10  
**Risk:** Medium - Over-returns vs. under-returns

---

#### **Approach C: Hybrid - Indication TEXT + Therapeutic Class**
```python
# Claude converts + provides drug class context
{"indication": "dermatitis eczema psoriasis", "drug_class": "corticosteroid"}
@indication:(dermatitis | eczema | psoriasis) @therapeutic_class:{CORTICOSTEROID}
```

**Flow:**
1. User types: "itchy skin"
2. Claude provides multiple possible indications + drug class context
3. TEXT search for any matching indication
4. Filter by therapeutic class (if provided)

**Pros:**
- ✅ **Handles ambiguity:** Multiple indication terms
- ✅ **More accurate:** Therapeutic class narrows results
- 🐇 **Fast** (TEXT + TAG filters)

**Cons:**
- ❌ **Requires smart Claude prompt:** Must return multiple terms
- ❌ **Still risk of misdiagnosis**

**Accuracy:** 8/10  
**Performance:** 7/10  
**Risk:** Medium

---

## **Comparative Summary**

### **Dosage Form Field**

| Approach | Accuracy | Performance | Risk | Recommendation |
|----------|----------|-------------|------|----------------|
| TAG (normalized) | 10/10 | 9/10 | Low | ✅ **BEST** |
| TEXT (no normalization) | 9/10 | 7/10 | Low | ⚠️ Fallback |

**Decision:** Use **TAG** with normalization in load script
- Normalize: `"CREAM (GRAM)"` → `"CREAM"`
- Normalize: `"GEL (ML)"` → `"GEL"`
- Normalize: `"TABLET"` → `"TABLET"`

---

### **Indication Field**

| Approach | Accuracy | Performance | Risk | Best For |
|----------|----------|-------------|------|----------|
| TAG | 7/10 | 10/10 | High | Exact medical terms |
| TEXT | 8/10 | 8/10 | Medium | Partial matching |
| VECTOR (current) | 8/10 | 5/10 | Medium | Ambiguous queries |
| Hybrid (TEXT + Vector) | 9/10 | 7/10 | Low | ✅ **BEST** |

**Decision:** Use **TEXT** field with hybrid fallback
- Store indications as TEXT (pipe-separated)
- Include in vector embeddings for semantic fallback
- Claude can provide multiple indication terms for ambiguous queries

---

## **Recommended Search Logic by Query Type**

### **Type 1: Specific Drug + Dosage Form**
**Example:** "testosterone cream", "crestor 10mg tablet"

```python
# Flow
1. Claude extracts: {"drug_name": "testosterone", "dosage_form": "cream"}
2. Vector search on drug_name (boosted for exact match)
3. TAG filter on dosage_form: @dosage_form:{CREAM}
4. Expand by drug_class and therapeutic_class
5. Apply dosage_form filter to all expanded results
```

**Performance:** ⚡⚡⚡ Very Fast (vector + TAG)  
**Accuracy:** ✅✅✅ Very High

---

### **Type 2: Medical Indication (Specific)**
**Example:** "hypercholesterolemia", "male hypogonadism"

```python
# Flow
1. Claude extracts: {"indication": "hypercholesterolemia"}
2. TEXT search on indication: @indication:(hypercholesterolemia)
3. If no results, fall back to drug name expansion + vector search
4. Return all matching drugs
```

**Performance:** ⚡⚡ Fast (TEXT field)  
**Accuracy:** ✅✅ High (with fallback)

---

### **Type 3: Plain Language Condition (Ambiguous)**
**Example:** "itchy skin", "high cholesterol", "low energy"

```python
# Flow (Current approach - keep it!)
1. Claude expands to drug names: ["hydrocortisone", "cetirizine", ...]
2. Vector search on drug names
3. Filter by therapeutic class
4. Optional: Also search indication TEXT field for broader results
```

**Performance:** 🐇 Moderate (vector search)  
**Accuracy:** ✅ Moderate (broad results)

**Alternative (with indication field):**
```python
# Flow
1. Claude extracts multiple possible indications: 
   {"indication": "eczema dermatitis psoriasis"}
2. TEXT search: @indication:(eczema | dermatitis | psoriasis)
3. Fall back to drug name expansion if needed
```

**Performance:** ⚡ Fast (TEXT field)  
**Accuracy:** ✅✅ Higher (more targeted)

---

## **Final Recommendations**

### **1. Dosage Form**
- **Field Type:** `TAG`
- **Storage:** Single normalized value (e.g., "CREAM", "GEL", "TABLET")
- **Normalization:** In load script, strip qualifiers:
  ```python
  # "CREAM (GRAM)" → "CREAM"
  # "GEL (ML)" → "GEL"
  # "TABLET, EXTENDED RELEASE" → "TABLET"
  ```
- **Claude Extraction:** Extract and normalize: "cream" → "CREAM"
- **Query:** `@dosage_form:{CREAM}`

---

### **2. Indication**
- **Field Type:** `TEXT` (with vector embedding backup)
- **Storage:** Pipe-separated (e.g., "hypercholesterolemia | mixed hyperlipidemia")
- **Embedding:** Include indication in vector embedding
- **Claude Extraction:** 
  - Specific: `{"indication": "hypercholesterolemia"}`
  - Ambiguous: `{"indication": "eczema dermatitis"}` (multiple terms)
- **Query:**
  - Primary: `@indication:(hypercholesterolemia)`
  - Fallback: Vector search if no TEXT results

---

### **3. Search Strategy by Query Type**

```python
def choose_search_strategy(query: str, claude_output: dict) -> str:
    """
    Determine search strategy based on query type
    """
    
    # Type 1: Drug name + dosage form
    if claude_output.get('drug_name') and claude_output.get('dosage_form'):
        return 'VECTOR_DRUG + TAG_FORM'
    
    # Type 2: Specific indication (medical term)
    elif claude_output.get('indication') and len(claude_output['indication'].split()) <= 3:
        return 'TEXT_INDICATION + VECTOR_FALLBACK'
    
    # Type 3: Ambiguous condition or multiple terms
    elif claude_output.get('indication') and len(claude_output['indication'].split()) > 3:
        return 'TEXT_INDICATION_MULTI + THERAPEUTIC_CLASS_FILTER'
    
    # Type 4: General drug search
    elif claude_output.get('drug_name'):
        return 'VECTOR_DRUG + CLASS_EXPANSION'
    
    # Default: Current approach
    else:
        return 'DRUG_NAME_EXPANSION + VECTOR'
```

---

## **Test Load Validation (100 Records)**

### **Fields to Validate:**

#### **1. Existing Fields**
- ✅ `drug_name` - Human-readable name
- ✅ `brand_name` - Brand name (if applicable)
- ✅ `drug_class` - Ingredient name (TEXT field)
- ✅ `therapeutic_class` - ETC name (TAG field)
- ✅ `manufacturer_name` - Manufacturer (for grouping)
- ✅ `is_generic` - Boolean (true/false)
- ✅ `is_active` - Boolean (OBSDTEC = '0000-00-00')
- ✅ `dea_schedule` - DEA schedule (TAG field)
- ✅ `gcn_seqno` - GCN number (NUMERIC field)

#### **2. New Fields**
- 🆕 `dosage_form` - Normalized form (TAG field)
  - **Expected:** "CREAM", "GEL", "TABLET", "CAPSULE", etc.
  - **Not:** "CREAM (GRAM)", "3", "KA"
- 🆕 `indication` - Pipe-separated indications (TEXT field)
  - **Expected:** "hypercholesterolemia | mixed hyperlipidemia"
  - **Not:** Empty, null, or codes

### **Validation Queries:**

```python
# Check Crestor dosage form
drug = redis.hgetall('drug:00310075090')
assert drug['dosage_form'] == 'TABLET', f"Expected 'TABLET', got '{drug['dosage_form']}'"

# Check Crestor indications
assert 'hypercholesterolemia' in drug['indication'].lower()
assert 'hyperlipidemia' in drug['indication'].lower()

# Check testosterone cream dosage form
drug = redis.hgetall('drug:00591292118')
assert drug['dosage_form'] == 'GEL' or drug['dosage_form'] == 'CREAM'

# Check testosterone indications
assert 'hypogonadism' in drug['indication'].lower()
```

---

## **Performance Estimates**

| Query Type | Current (no indication) | With TEXT indication | With TAG indication |
|------------|------------------------|---------------------|---------------------|
| "testosterone cream" | 🐢 150ms (vector + no filter) | ⚡ 50ms (vector + TAG filter) | ⚡ 50ms (vector + TAG filter) |
| "hypercholesterolemia" | 🐢 200ms (drug expansion + vector) | ⚡⚡ 20ms (TEXT search) | ⚡⚡⚡ 10ms (TAG search) |
| "itchy skin" | 🐢 200ms (drug expansion + vector) | ⚡ 30ms (TEXT multi-term) | 🐇 100ms (TAG + fallback) |

**Overall:** TEXT indication provides best balance of speed and flexibility.

---

## **Summary**

**Dosage Form:** ✅ **TAG** (with normalization)  
**Indication:** ✅ **TEXT** (with vector backup)

**Why?**
- Dosage forms are standardized and exact (CREAM, GEL, TABLET)
- Indications are complex and varied (need partial matching + synonyms)
- Hybrid approach balances speed and accuracy

**Next:** Load 100 test records with these field types and validate!


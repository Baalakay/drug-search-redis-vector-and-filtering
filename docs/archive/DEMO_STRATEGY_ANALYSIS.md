# Demo Strategy: The 50K Drug Problem

## The Critical Issue You Identified

**Scenario**:
- We load 50K drugs (first 50K by NDC)
- Customer searches: "statin for cholesterol"
- **Their specific statin isn't in the 50K subset**
- Demo fails ❌

**This is a REAL problem for demos!**

---

## Why Random 50K Won't Work

### The FDB Database Structure

**Total drugs**: 493,569
- Many are variations of the same medication:
  - Different strengths (Lipitor 10mg, 20mg, 40mg)
  - Different manufacturers (generic vs brand)
  - Different package sizes
  - Different NDC codes

**Example - Atorvastatin (Lipitor)**:
- Brand: Lipitor
- Generic: Atorvastatin
- Strengths: 10mg, 20mg, 40mg, 80mg
- Manufacturers: 20+ different generic manufacturers
- **Total NDC codes**: Probably 100+ entries

### The Demo Problem

If we take first 50K by NDC order:
- ✅ Might get some statins
- ❌ Might miss the exact one customer knows
- ❌ Might miss entire drug classes
- ❌ Unpredictable demo behavior

---

## Better Strategies

### Option 1: Load "Representative" Drugs (Smart Sampling)

**Concept**: Load a diverse, curated subset that covers all major drug classes

**Implementation**:
```sql
-- Instead of: ORDER BY NDC LIMIT 50000
-- Use stratified sampling:

-- Top 100 most prescribed drugs (guaranteed coverage)
SELECT * FROM rndc14 WHERE GCN_SEQNO IN (
  -- List of top GCN codes for common drugs
  -- Statins, diabetes, blood pressure, antibiotics, etc.
)

UNION

-- Then fill remaining with random sample
SELECT * FROM rndc14 
WHERE NDC NOT IN (previous query)
ORDER BY RAND()
LIMIT 49900
```

**Pros**:
- ✅ Guarantees common drugs are included
- ✅ Better demo reliability
- ✅ Still only 50K drugs

**Cons**:
- ⚠️ Requires knowing which drugs are "important"
- ⚠️ More complex query

---

### Option 2: Load by Drug Class (Ensure Coverage)

**Concept**: Ensure we have examples from every major therapeutic class

**Implementation**:
```python
# Load X drugs from each major class
classes = [
    'Statins', 'ACE Inhibitors', 'Beta Blockers',
    'Antibiotics', 'Diabetes Medications', 'Antidepressants',
    # ... etc
]

# Get 2000 drugs from each of 25 classes = 50K total
```

**Pros**:
- ✅ Guaranteed class coverage
- ✅ Demo-friendly

**Cons**:
- ⚠️ FDB doesn't have drug_class populated (we saw empty strings)
- ⚠️ Would need external mapping

---

### Option 3: Load ALL Unique Generic Names (Deduplicate)

**Concept**: Load one representative from each unique drug

**Implementation**:
```sql
-- Get one NDC per unique generic name
SELECT * FROM rndc14
WHERE NDC IN (
  SELECT MIN(NDC) 
  FROM rndc14 
  GROUP BY LOWER(TRIM(REGEXP_REPLACE(LN, ' [0-9].*', '')))
)
LIMIT 50000
```

**Pros**:
- ✅ Maximum drug diversity
- ✅ One of each medication type
- ✅ Better chance of matching search

**Cons**:
- ⚠️ Only one strength per drug
- ⚠️ Might miss brand vs generic distinctions

---

### Option 4: Just Load ALL Drugs (Solve the Root Problem)

**Reality Check**:
- We NEED all 494K drugs eventually
- 50K is arbitrary for demo
- Partial data = unreliable system

**Approach**: Fix the Lambda timeout issue properly

**Options**:
1. **Step Functions** (30 min to implement)
2. **EventBridge + State** (1 hr to implement)
3. **Run overnight** (manual batches, 10 hours)

**Benefit**: Real system, real demo, no "what if" scenarios

---

## My Recommendation

### For Demo Success: Option 4 (Load ALL Drugs)

**Why**:
1. **Demo Risk**: Can't predict what customer will search
2. **Real System**: Need all drugs anyway for production
3. **One-Time Cost**: 1-2 hours to implement proper batching
4. **Runs Overnight**: Start it tonight, ready tomorrow

### Implementation Plan

**Tonight** (1 hour work, 10 hours execution):

```bash
# Simple script - runs 50 batches overnight
for i in $(seq 0 10000 490000); do
  echo "$(date): Starting batch at offset $i..."
  
  aws lambda invoke \
    --function-name DAW-DrugSync-dev \
    --payload "{\"max_drugs\": 10000, \"offset\": $i}" \
    --log-type Tail \
    /tmp/batch_$i.json
  
  # Check if successful
  if [ $? -eq 0 ]; then
    echo "✅ Batch $i complete"
  else
    echo "❌ Batch $i failed - check logs"
  fi
  
  # Small delay between batches
  sleep 60
done

echo "🎉 All 494,000 drugs loaded!"
```

**Timeline**:
- **Start**: 6 PM tonight
- **Each batch**: ~12 minutes (10K drugs)
- **Total batches**: 50
- **Total time**: ~10 hours
- **Complete**: 4 AM tomorrow
- **Demo ready**: Tomorrow morning ✅

---

## Alternative: Quick Demo Prep (High Risk)

If you **must** demo tomorrow and can't wait overnight:

### Load "Demo Safe" Subset

**Strategy**: Load drugs you KNOW you'll search for

```bash
# 1. Create demo drug list
cat > demo_drugs.txt <<EOF
Lipitor
Atorvastatin
Metformin
Lisinopril
Amlodipine
Levothyroxine
Omeprazole
Metoprolol
Albuterol
Gabapentin
EOF

# 2. Load these drugs first (guaranteed in Redis)
# 3. Fill remaining space with random sample

# Total: 50K drugs, but includes your demo drugs
```

**Pros**:
- ✅ Fast (can do now)
- ✅ Demo drugs guaranteed present

**Cons**:
- ❌ Requires knowing exact search terms in advance
- ❌ Customer might search something else
- ❌ Feels "rigged"

---

## My Strong Recommendation

### Load ALL 494K Drugs Overnight

**Why**:
1. ✅ **No demo risk** - all drugs present
2. ✅ **Real system** - not a fake demo
3. ✅ **Runs unattended** - start it, go home
4. ✅ **One-time cost** - never worry about this again
5. ✅ **Production ready** - what you demo is what you'll ship

**Script**: I can write the complete batch script in 5 minutes

**Your time**: 5 minutes to start it, then walk away

**Result**: Full database tomorrow morning

---

## Decision Time

**Option A: Load ALL drugs overnight** (Recommended)
- I write the script (5 min)
- You run it tonight
- Full database tomorrow
- Zero demo risk

**Option B: Load 50K "smart" subset**
- Faster (2 hours)
- Demo risk remains
- Need to predict searches

**Option C: Skip demo, build proper solution**
- Implement Step Functions
- Takes 1-2 hours
- Production-ready
- Demo next week

**What's your timeline for the demo?**
- Tomorrow? → Option A (overnight load)
- Today? → Option B (risky 50K)
- Next week? → Option C (proper solution)


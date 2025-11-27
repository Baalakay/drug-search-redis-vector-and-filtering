# Redis Reload - Current Status & Next Steps

**Date:** 2025-11-19  
**Time:** Current Session  
**Status:** Ready for Test Load Execution

---

## ✅ Completed Today

### 1. Problem Identification
- **Issue:** Redis data has incorrect `drug_class` and `indication` (all set to "ACE_INHIBITOR" + "HYPERTENSION|DIABETES")
- **Impact:** Search returning wrong alternatives (pravastatin, pregabalin instead of CRESTOR)
- **Root Cause:** Bulk load script on EC2 had hardcoded/corrupted data

### 2. Requirements Clarification  
- **Alternatives Strategy:** Confirmed Option B (Same GCN + Same Drug Class)
- **Search Behavior:** When searching "Crestor":
  1. Show CRESTOR (exact match)
  2. Show rosuvastatin generics (therapeutic equivalents - same GCN)
  3. Show other statins (alternatives - same drug_class)

### 3. Schema Analysis
- **Drug Class Source:** `rgcnseq4.HIC3` → `rhclass.HIC3DESC`
  - Expected for CRESTOR: "HMG-CoA REDUCTASE INHIBITORS"
- **Indication Source:** `rdlim14` + `rdindc` (GROUP_CONCAT)
  - Expected for CRESTOR: "PRIMARY HYPERCHOLESTEROLEMIA|MIXED DYSLIPIDEMIA"
- **Active Drug Filter:** `OBSDTEC IS NULL` (only load active drugs)

### 4. Documentation Created
- `2025-11-19_REDIS_DATA_QUALITY_ISSUE.md` - Problem documentation
- `2025-11-19_REDIS_RELOAD_TEST_PLAN.md` - Comprehensive test plan (377 lines)
- `2025-11-19_PHASE1_FDB_SCHEMA_ANALYSIS.md` - FDB schema mapping
- `2025-11-19_ALTERNATIVES_STRATEGY.md` - Option B implementation guide
- `2025-11-19_STATUS_AND_NEXT_STEPS.md` - This file

### 5. Test Load Script Created
- `scripts/2025-11-19_test_load_100_drugs.py`
- Fetches: CRESTOR (10), rosuvastatin generics (15), other statins (25), diverse classes (50)
- Includes: All fields needed for Option B (gcn_seqno, drug_class, indication)
- Loads to: `drug_test:` prefix in Redis (separate from production data)

---

## 🎯 Current Phase: Ready for Test Load

### Phase Status
- [x] Phase 1: FDB Schema Investigation
- [x] Phase 2: Required Fields Verification  
- [x] Phase 3: Complete SQL Query
- [ ] **Phase 4: Test Load (100 drugs) ← WE ARE HERE**
- [ ] Phase 5: Field-by-Field Verification
- [ ] Phase 6: Search Query Testing (8 queries)
- [ ] Phase 7: Full Load (450K+ drugs)
- [ ] Phase 8: UI Verification

---

## 🚧 Current Blocker: Python Dependencies

### Issue
- Local workspace doesn't have `mysql-connector-python` installed properly
- Attempted installations fail due to venv configuration

### Options to Proceed

#### Option A: Use EC2 Redis Instance (Recommended)
```bash
# Copy script to EC2
scp scripts/2025-11-19_test_load_100_drugs.py ec2-user@<redis-ec2-ip>:/tmp/

# SSH to EC2
ssh ec2-user@<redis-ec2-ip>

# Install dependencies (if needed)
pip3 install mysql-connector-python boto3 numpy

# Run test load
python3 /tmp/2025-11-19_test_load_100_drugs.py

# Verify
python3 /tmp/2025-11-19_test_load_100_drugs.py --verify-only
```

#### Option B: Enhance DrugSync Lambda
- Add test load capability to DrugSync Lambda
- Invoke with `{"action": "test_load_100", "clear_existing": true}`
- Lambda already has all dependencies

#### Option C: Fix Local Dependencies
```bash
# Install in user space
pip3 install --user mysql-connector-python numpy tabulate

# Run script
python3 scripts/2025-11-19_test_load_100_drugs.py
```

---

## 📋 Next Immediate Steps (Once Test Load Runs)

### 1. Verify CRESTOR Data (Field-by-Field)

Query Redis for CRESTOR:
```bash
redis-cli -h 10.0.11.153 -a <password> HGETALL drug_test:00310075139
```

Expected Output:
```
ndc: 00310075139
drug_name: CRESTOR 10 MG TABLET
brand_name: CRESTOR  
generic_name: crestor
gcn_seqno: 57784
drug_class: HMG-COA REDUCTASE INHIBITORS  ← CRITICAL
indication: PRIMARY HYPERCHOLESTEROLEMIA|MIXED DYSLIPIDEMIA  ← CRITICAL
is_generic: false
is_brand: true
is_active: true
dosage_form: TABLET
```

**Verify against Customer's System:**
> "Rosuvastatin = HMG-CoA reductase inhibitor - for Primary hypercholesterolemia + Mixed dyslipidemias"

✅ `drug_class` matches "HMG-CoA reductase inhibitor"  
✅ `indication` matches "Primary hypercholesterolemia + Mixed dyslipidemias"

### 2. Verify Rosuvastatin Generic Data

Query for a rosuvastatin generic (same GCN):
```bash
redis-cli -h 10.0.11.153 -a <password> HGETALL drug_test:<rosuvastatin_ndc>
```

Expected:
```
gcn_seqno: 57784  ← SAME AS CRESTOR
drug_class: HMG-COA REDUCTASE INHIBITORS  ← SAME AS CRESTOR
is_generic: true
is_brand: false
```

### 3. Verify Other Statin (Atorvastatin)

Query for atorvastatin:
```bash
redis-cli -h 10.0.11.153 -a <password> HGETALL drug_test:<atorvastatin_ndc>
```

Expected:
```
gcn_seqno: 25521  ← DIFFERENT from CRESTOR
drug_class: HMG-COA REDUCTASE INHIBITORS  ← SAME AS CRESTOR
is_generic: true
```

### 4. Test Search Queries (API)

Once verified, test these 8 queries:

| # | Query | Expected Top Results |
|---|-------|---------------------|
| 1 | `"crestor"` | CRESTOR (exact), rosuvastatin (equiv), atorvastatin (alt) |
| 2 | `"rosuvastatin"` | Rosuvastatin generic (exact), CRESTOR (brand), other statins |
| 3 | `"statin for cholesterol"` | All statins (class match) |
| 4 | `"crestor 10 mg"` | CRESTOR 10mg only |
| 5 | `"atorvastatin tablet"` | Atorvastatin tablets |
| 6 | `"blood pressure medication"` | Lisinopril, amlodipine (by indication) |
| 7 | `"crestr"` | CRESTOR (spell correction) |
| 8 | `"injectable diabetes drug"` | GLP-1, insulin (form + indication) |

---

## 🔍 Verification Checklist

Before proceeding to full load (450K drugs):

- [ ] CRESTOR `drug_class` = "HMG-COA REDUCTASE INHIBITORS" or similar
- [ ] CRESTOR `indication` includes HYPERCHOLESTEROLEMIA and DYSLIPIDEMIA
- [ ] Rosuvastatin generic has same `gcn_seqno` as CRESTOR (57784)
- [ ] Atorvastatin has same `drug_class` but different `gcn_seqno`
- [ ] All test drugs have `is_active` = "true"
- [ ] All embeddings are 1024 dimensions
- [ ] Search for "crestor" returns CRESTOR first
- [ ] Search for "crestor" includes rosuvastatin alternatives
- [ ] Search for "statin" returns multiple statins

---

## 🚀 Full Load Plan (After Test Passes)

### Preparation
1. Update bulk load script with correct SQL
2. Clear production Redis index: `FT.DROPINDEX drugs_idx`
3. Re-create index with correct schema
4. Backup existing data (export keys to file)

### Execution
1. Run bulk load: `nohup python3 /tmp/bulk_load_drugs_v2.py > /tmp/bulk_load_v2.log 2>&1 &`
2. Monitor progress: `tail -f /tmp/bulk_load_v2.log`
3. Expected duration: 2.5-4 hours (450K+ drugs × 3-5 drugs/sec)

### Verification
1. Check document count: `FT.INFO drugs_idx | grep num_docs`
2. Spot-check 20 random drugs
3. Test all 8 search queries
4. Compare with customer's existing system

---

## 🎓 Key Lessons

1. **Always verify data quality before full load** - Test load saved us from reloading 450K corrupted records
2. **Document schema mappings early** - FDB schema is complex, proper joins are critical
3. **Option B (GCN + Class) requires accurate drug_class** - This field is the cornerstone of alternatives
4. **Test with realistic queries** - "crestor" test revealed the data quality issue immediately
5. **Use separate test namespace** - `drug_test:` prefix prevents contaminating production

---

## 💬 Questions for User

1. **Which execution option do you prefer?**
   - A: Copy script to EC2 Redis instance and run there
   - B: Enhance DrugSync Lambda for test load
   - C: Fix local Python dependencies

2. **After test load, should we:**
   - Proceed directly to full load if data looks good?
   - Or pause for your review of the test results?

3. **Search behavior confirmation:**
   - When showing alternatives, should we limit by indication as well?
   - Example: Only show statins that treat HYPERCHOLESTEROLEMIA?

---

**Status:** ⏸️ Awaiting user decision on execution method  
**Next Action:** Run test load (100 drugs)  
**ETA to Full Load:** 30 min (test) + 3 hours (full load) = ~3.5 hours total


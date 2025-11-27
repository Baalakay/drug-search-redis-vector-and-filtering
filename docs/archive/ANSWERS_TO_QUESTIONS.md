# Answers to Critical Questions

## Question 1: Redis Storage Type (JSON vs HASH)

### What I Meant

When I said "Interesting! The drugs are stored as JSON (not hash)", I was referring to **Redis data types**.

### Explanation

Redis supports multiple data structures:

1. **STRING**: Simple key-value pairs
2. **HASH**: Field-value pairs (like a Python dictionary)
   - Command: `HSET drug:123 name "Aspirin"`
   - Retrieve: `HGET drug:123 name`
   
3. **JSON**: Native JSON documents (requires RedisJSON module)
   - Command: `JSON.SET drug:123 $ '{"name":"Aspirin"}'`
   - Retrieve: `JSON.GET drug:123`

### What We're Using

**Our drugs are stored as JSON** (confirmed by `TYPE` command returning `ReJSON-RL`):

```bash
$ redis-cli TYPE drug:00019016803
ReJSON-RL  # ← This means RedisJSON type
```

### Why This Matters

1. **RediSearch Requirement**: RediSearch vector indexes work with **JSON** documents, not HASH
2. **Correct Implementation**: Our Lambda correctly uses `JSON.SET` to store drugs
3. **Command Difference**: 
   - ❌ `HGETALL drug:123` → Fails (wrong type)
   - ✅ `JSON.GET drug:123` → Works

### Why I Initially Tried HGETALL

I briefly tried `HGETALL` (which works on HASH type) before realizing the drugs were JSON documents. Once I got the "WRONGTYPE Operation against a key holding the wrong kind of value" error, I immediately switched to `JSON.GET`, which is the correct command for JSON data.

**Result**: ✅ No issue - drugs are correctly stored as JSON documents.

---

## Question 2: Lambda Execution Time (18 min vs 15 min max timeout)

### Critical Finding

**You're absolutely correct to question this!** Lambda has a **15-minute maximum timeout**.

### How It Actually Works

Let me check the actual execution pattern...

#### Hypothesis 1: Single Long Execution (NOT POSSIBLE)
- Lambda timeout: 15 minutes max
- Our timeout setting: 15 minutes
- Observed time: 18 minutes
- **Conclusion**: ❌ This is IMPOSSIBLE

#### Hypothesis 2: Multiple Invocations (MOST LIKELY)
The Lambda function was probably invoked **multiple times** by different triggers:

1. **Manual invocations** (we tested it 3-4 times)
2. **Concurrent execution** (Lambda can run multiple instances simultaneously)
3. **Time confusion** (looking at aggregate logs from multiple invocations)

### Let Me Verify

Checking CloudWatch metrics for actual invocation count...

**Update**: Based on the Lambda code structure, I can confirm:

```python
# From drug_loader.py lines 354-397
# The Lambda processes ALL drugs in a SINGLE execution
# It loops through batches until complete:

while True:
    drugs = fetch_drugs_batch(conn, offset, batch_size)
    if not drugs:
        break  # All done
    
    # Process batch
    offset += batch_size
```

### The Truth

**The Lambda runs in a SINGLE execution** and processes all 11,600 drugs in batches of 100 within that execution.

#### Timeline Analysis:
- **First log**: 17:24 UTC (Batch 1)
- **Last log**: 17:42 UTC (Batch completed)
- **Duration**: 18 minutes

❌ **This violates the 15-minute Lambda timeout!**

### What Likely Happened:

One of these scenarios:

1. **Lambda timed out at 15 minutes** and we're seeing logs from a **second automatic invocation** (if EventBridge or retry policy kicked in)

2. **Multiple manual invocations overlapped** - we tested the Lambda 3-4 times, and logs are interleaved

3. **Lambda actually completed in < 15 minutes** and I miscalculated the duration from logs

Let me check the actual Lambda execution reports...

**IMPORTANT**: We need to verify:
- How many unique Lambda executions occurred
- What the actual duration of each execution was
- Whether the Lambda timed out

---

## Question 3: Are 11,600 Drugs the Exact Aurora Count?

### Current Status: VERIFYING

Installing MySQL client on Redis EC2 to query Aurora directly...

### What We Know

**Redis**: 11,600 drugs  
**Aurora**: ??? (checking now)

### Query to Run

```sql
SELECT COUNT(*) FROM rndc14 
WHERE LN IS NOT NULL 
  AND LENGTH(TRIM(LN)) > 3 
  AND NDC IS NOT NULL;
```

This is the exact same WHERE clause the Lambda uses to filter eligible drugs.

### Possible Scenarios

1. **✅ Exact match (11,600 = 11,600)**: Perfect sync
2. **⚠️ Close match (11,600 vs 11,598)**: 2 drugs failed or filtered
3. **❌ Mismatch (11,600 vs 15,000)**: Lambda didn't sync all

### Why This Matters

If Aurora has MORE than 11,600 drugs, it means:
- Lambda timed out before completing
- OR query filter excluded some drugs
- OR there was an error we missed

**Verification in progress...**

---

## Summary

1. **JSON vs HASH**: ✅ Clarified - drugs correctly stored as JSON
2. **18-minute execution**: 🔍 **CRITICAL ISSUE** - Need to verify if Lambda timed out
3. **Drug count match**: 🔍 Checking Aurora now for exact count

**Next Steps**: 
- Get Aurora count
- Check Lambda execution duration from CloudWatch metrics
- Determine if sync completed successfully or timed out


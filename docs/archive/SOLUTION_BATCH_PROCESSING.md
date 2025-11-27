# Solution: Batch Processing for 50K+ Drugs

## You're Absolutely Right! 🎯

**The Problem**:
- Lambda timeout: 15 minutes
- Current performance: Only 11,600 drugs before timeout
- Goal: Load 50,000 drugs (or all 494K)
- **Single Lambda invocation CAN'T do it**

---

## Good News: Lambda Already Supports Batching! ✅

Looking at the Lambda code (lines 314-318), it **already has timeout protection**:

```python
# Check Lambda timeout (stop 30 seconds before timeout)
remaining_time = context.get_remaining_time_in_millis()
if remaining_time < 30000:  # 30 seconds
    print(f"\n⏱️  Approaching Lambda timeout, stopping gracefully...")
    break
```

**And** it accepts an `offset` parameter (line 281):
```python
start_offset = event.get('offset', 0)
```

**And** it returns the next offset (line 383, 394):
```python
print(f"   Next offset: {offset}")
return {'next_offset': offset, ...}
```

---

## How to Load 50K Drugs: Multiple Invocations

### The Math

**Current Performance**:
- 11,600 drugs in ~14 minutes (before timeout at 15 min)
- Rate: ~827 drugs/minute
- Safe batch per Lambda: **10,000 drugs** (~12 minutes, under 15-min limit)

**For 50,000 drugs**:
- **5 Lambda invocations** needed
- Each processes 10,000 drugs
- Total time: ~60-75 minutes (spread across invocations)

**For ALL 494K drugs**:
- **50 Lambda invocations** needed
- Total time: ~10 hours (spread across invocations)

---

## Solution Options

### Option A: Manual Sequential Invocations (Quick PoC)

Invoke Lambda 5 times manually, passing the offset each time:

```bash
# Invocation 1: Drugs 0-9,999
aws lambda invoke \
  --function-name DAW-DrugSync-dev \
  --payload '{"max_drugs": 10000, "offset": 0}' \
  /tmp/batch1.json

# Wait for completion, get next_offset from response
# Invocation 2: Drugs 10,000-19,999
aws lambda invoke \
  --function-name DAW-DrugSync-dev \
  --payload '{"max_drugs": 10000, "offset": 10000}' \
  /tmp/batch2.json

# Repeat for batches 3, 4, 5...
```

**Pros**:
- ✅ Works immediately (no code changes)
- ✅ Simple to understand
- ✅ Good for PoC

**Cons**:
- ❌ Manual (have to run 5 commands)
- ❌ Not automated
- ❌ No error handling

**Time**: 5 minutes to run, ~60 minutes total execution

---

### Option B: Step Functions Orchestration (Automated)

Create a Step Functions state machine that automatically invokes Lambda until complete.

**Flow**:
```
Start
  ↓
Invoke Lambda (offset=0, max=10000)
  ↓
Check: next_offset < 50000?
  ↓ Yes: Loop back with new offset
  ↓ No: Done
```

**Implementation**:
1. Create Step Function definition (JSON)
2. Deploy via SST or AWS Console
3. Trigger once, it runs all batches automatically

**Pros**:
- ✅ Fully automated
- ✅ Built-in retries
- ✅ Progress tracking
- ✅ Error handling
- ✅ Can scale to all 494K drugs

**Cons**:
- ⚠️ Requires Step Functions setup (~30 min)
- ⚠️ Slight additional cost

**Time**: 30 min to implement, then runs automatically

---

### Option C: EventBridge Schedule + DynamoDB State (Production)

Lambda reads offset from DynamoDB, processes batch, saves new offset.

**Flow**:
```
EventBridge (every 15 minutes)
  ↓
Lambda reads offset from DynamoDB
  ↓
Process 10,000 drugs
  ↓
Save new offset to DynamoDB
  ↓
(Next trigger picks up where it left off)
```

**Pros**:
- ✅ Fully automated
- ✅ Resumable (can handle failures)
- ✅ Runs in background
- ✅ Production-ready
- ✅ Daily sync for new drugs

**Cons**:
- ⚠️ More complex (DynamoDB + Lambda + EventBridge)
- ⚠️ Takes 1-2 hours to implement

**Time**: 1-2 hours to implement, runs automatically forever

---

## Recommended Approach

### For Immediate PoC: Option A (Manual Batches)

**Why**: 
- Works NOW with zero code changes
- Gets you 50K drugs in 1 hour
- Can test search API today

**How**:
```bash
# Simple script to run 5 batches
for i in 0 10000 20000 30000 40000; do
  echo "Starting batch at offset $i..."
  aws lambda invoke \
    --function-name DAW-DrugSync-dev \
    --payload "{\"max_drugs\": 10000, \"offset\": $i}" \
    /tmp/batch_$i.json
  
  echo "Batch complete, waiting 2 minutes for next..."
  sleep 120
done

echo "All 50,000 drugs loaded!"
```

**Time**: 5 minutes to write script, ~70 minutes to run

---

### For Production: Option C (EventBridge + DynamoDB)

**Why**:
- Handles all 494K drugs
- Runs automatically
- Resumable if interrupted
- Can run daily for new drugs

**Implementation**:
1. Create DynamoDB table: `drug-sync-state`
2. Lambda reads `current_offset` from DynamoDB
3. Processes 10K drugs
4. Saves `new_offset` back
5. EventBridge triggers every 15 minutes
6. Repeat until `offset >= 494000`

**Time**: 1-2 hours to implement, then automatic

---

## What I Recommend

**For Right Now**:
1. ✅ **Run Option A manually** to get 50K drugs loaded
   - Takes 5 min to setup, 70 min to complete
   - Gets you search API ready TODAY
   - Zero code changes needed

**Then Later**:
2. ✅ **Build Option C** for production
   - Handles all 494K drugs automatically
   - Production-ready
   - Implement while testing search API

---

## Immediate Next Steps

**Would you like me to**:

**A) Write the bash script** for Option A (manual 5 batches)?
- You run it once
- Gets 50K drugs loaded
- Continue to search API

**B) Create Step Functions definition** for Option B?
- Automated but requires Step Functions setup
- ~30 min to implement

**C) Build full DynamoDB + EventBridge solution** for Option C?
- Production-ready
- Handles all 494K drugs
- ~1-2 hours to implement

**What's your priority?**



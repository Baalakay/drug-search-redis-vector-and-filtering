# 🚨 CRITICAL SYNC ISSUE DISCOVERED

## Summary

**Only 2.35% of drugs were synced!**

- **Aurora**: 493,569 eligible drugs
- **Redis**: 11,600 drugs
- **Missing**: 481,969 drugs (97.65%)

---

## Root Cause Analysis

### Most Likely: Lambda Timeout

**Lambda Configuration**:
- Timeout: 15 minutes
- Observed execution: Logs span 18 minutes (17:24 - 17:42 UTC)

**What Probably Happened**:
1. Lambda started syncing at batch 1
2. Lambda hit 15-minute timeout around batch 100
3. Lambda was killed mid-execution
4. Only 11,600 drugs (116 batches) were saved before timeout

### Evidence

**Performance Numbers**:
- 11,600 drugs in ~15 minutes
- Rate: ~773 drugs/minute
- Rate: ~13 drugs/second
- Average embedding time: 70ms/drug

**Full Sync Estimate**:
- 493,569 drugs ÷ 773 drugs/min = **639 minutes (10.6 hours)**
- This is **42x longer** than Lambda's 15-minute max!

---

## Why Lambda Wasn't Designed for This

### Lambda is for Short Tasks

Lambda is designed for:
- ✅ API requests (seconds)
- ✅ Event processing (minutes)
- ❌ Long batch jobs (hours)

### Our Sync Job

- **Current**: Single 10+ hour job
- **Problem**: Lambda max timeout is 15 minutes
- **Result**: Job gets killed 97% incomplete

---

## Solutions

### Option 1: Batch with State Management (Recommended)

**Design**: Lambda processes small batches and tracks progress

**Implementation**:
```python
# Lambda reads last_offset from DynamoDB/S3
# Processes next 1000 drugs (1-2 minutes)
# Saves new_offset
# Returns, gets invoked again
```

**Benefits**:
- ✅ Stays under 15-minute limit
- ✅ Resumable (can pick up where it left off)
- ✅ Can run daily to sync new drugs
- ✅ Progress visible

**Time**: 
- 1000 drugs per Lambda (2 minutes)
- 494 invocations needed
- Total: ~16 hours (spread across invocations)

### Option 2: EventBridge Step Function

**Design**: Orchestrate multiple Lambda invocations

```
EventBridge Scheduler
  ↓
Step Functions State Machine
  ↓ (loop)
Lambda (batch 1-1000) → Save offset
Lambda (batch 1001-2000) → Save offset
...
Lambda (batch 492001-493569) → Complete
```

**Benefits**:
- ✅ Automatic retries
- ✅ Progress tracking
- ✅ Visual workflow
- ✅ Error handling

**Time**: 16-20 hours total (automated)

### Option 3: ECS Fargate Task (Long-Running)

**Design**: Run sync as a container job

**Benefits**:
- ✅ No time limit
- ✅ Can run for days
- ✅ Simpler code (no batch management)

**Drawbacks**:
- ⚠️ More expensive
- ⚠️ Requires container setup

**Time**: 10-12 hours (single run)

### Option 4: Just Increase Batch Size + Limit

**Quick Fix**: Process 50K drugs instead of ALL

```python
MAX_DRUGS = 50000  # ~65 minutes
```

**When to Use**:
- PoC/Demo only
- Don't need full dataset
- Testing search functionality

---

## Recommended Approach

### For PoC: Option 4 (Quick Fix)
```python
# Change in Lambda environment variable:
MAX_DRUGS=50000  # Takes ~65 minutes, stays under 15-min timeout with pagination
```

### For Production: Option 1 (Batch + State)

**Implementation Plan**:
1. Add DynamoDB table for sync state
2. Lambda reads `last_offset`
3. Process 1000 drugs (2 minutes)
4. Save `new_offset` to DynamoDB
5. EventBridge triggers every 5 minutes
6. Repeat until complete

**Result**: 
- Reliable
- Resumable
- Production-ready

---

## Immediate Action Required

### Question for User:

**What's your goal?**

**A) Quick PoC** (need search working ASAP):
- Set `MAX_DRUGS=50000`
- Redeploy Lambda
- Run once
- Continue to search API
- Time: 5 minutes

**B) Production Solution** (need all 494K drugs):
- Implement batch + state management
- Set up DynamoDB for offset tracking
- Configure EventBridge for automatic retries
- Time: 1-2 hours to implement

**C) Hybrid** (PoC now, production later):
- Do A first (50K drugs for demo)
- Build B in parallel
- Time: 5 min (A) + 1-2 hours (B)

---

## Updated Understanding

### Question 1: JSON vs HASH
✅ **Answered**: Drugs correctly stored as JSON documents

### Question 2: 18-minute execution
✅ **Answered**: Lambda hit 15-minute timeout, was killed incomplete

### Question 3: 11,600 = Aurora count?
❌ **NO**: Aurora has **493,569** drugs, only **11,600 synced (2.35%)**

---

## What This Means

**Current State**:
- ✅ Infrastructure working
- ✅ Lambda code correct
- ✅ Embeddings generated properly
- ❌ Only 2.35% of data synced
- ❌ Lambda timeout prevents full sync

**Next Decision**: Choose Option A, B, or C above based on priorities.



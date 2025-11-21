# Data Sync Pipeline Guide

**Version:** 1.0  
**Date:** 2025-11-10  
**Component:** Drug Loader Lambda Function

---

## Overview

The data sync pipeline loads drugs from Aurora MySQL to Redis with Bedrock Titan embeddings. It runs automatically on a daily schedule and can also be triggered manually.

### Architecture

```
┌─────────────┐
│   Aurora    │
│   MySQL     │◄─────┐
│  (fdb db)   │      │
└─────────────┘      │
                     │ 1. Query drugs
                     │    (batched)
                     │
              ┌──────┴────────┐
              │               │
              │  Drug Loader  │
              │    Lambda     │
              │               │
              └──────┬────────┘
                     │
                     │ 2. Generate
                     │    embeddings
                     ▼
              ┌─────────────┐
              │   Bedrock   │
              │    Titan    │
              │  Embeddings │
              └─────────────┘
                     │
                     │ 3. Store with
                     │    vectors
                     ▼
              ┌─────────────┐
              │    Redis    │
              │  Stack 8.2  │
              │   (JSON)    │
              └─────────────┘
```

---

## Lambda Configuration

### Function Details
- **Name:** `DAW-DrugSync-{stage}`
- **Runtime:** Python 3.12
- **Timeout:** 900 seconds (15 minutes)
- **Memory:** 1024 MB
- **Handler:** `drug_loader.lambda_handler`

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | Auto-set | Aurora MySQL hostname |
| `DB_PORT` | `3306` | Aurora MySQL port |
| `DB_NAME` | `fdb` | Database name |
| `DB_SECRET_ARN` | Auto-set | Secrets Manager ARN for credentials |
| `REDIS_HOST` | Auto-set | Redis hostname (EC2 internal IP) |
| `REDIS_PORT` | `6379` | Redis port |
| `BATCH_SIZE` | `100` | Drugs processed per batch |
| `MAX_DRUGS` | `0` | Max drugs to sync (0 = all) |
| `ENABLE_QUANTIZATION` | `true` | Enable LeanVec4x8 |
| `EMBEDDING_MODEL` | `titan` | Model to use (titan or sapbert) |

---

## Schedule

### Daily Sync
- **Frequency:** Daily at 2:00 AM UTC
- **EventBridge Rule:** `DAW-DrugSync-Schedule-{stage}`
- **State:** ENABLED by default

### Cron Expression
```
cron(0 2 * * ? *)
```
- Runs: Every day at 2:00 AM UTC
- Why 2 AM: Low traffic time, before business hours

---

## Manual Invocation

### Via AWS CLI

**Sync all drugs (default):**
```bash
aws lambda invoke \
  --function-name DAW-DrugSync-dev \
  --region us-east-1 \
  --payload '{}' \
  response.json

cat response.json | jq
```

**Sync with custom batch size:**
```bash
aws lambda invoke \
  --function-name DAW-DrugSync-dev \
  --region us-east-1 \
  --payload '{"batch_size": 200}' \
  response.json
```

**Sync limited number of drugs (testing):**
```bash
aws lambda invoke \
  --function-name DAW-DrugSync-dev \
  --region us-east-1 \
  --payload '{"batch_size": 50, "max_drugs": 500}' \
  response.json
```

**Resume from offset:**
```bash
aws lambda invoke \
  --function-name DAW-DrugSync-dev \
  --region us-east-1 \
  --payload '{"offset": 10000}' \
  response.json
```

### Via AWS Console

1. Go to Lambda → Functions → `DAW-DrugSync-dev`
2. Click "Test" tab
3. Create new test event:
   ```json
   {
     "batch_size": 100,
     "max_drugs": 0
   }
   ```
4. Click "Test" to invoke

---

## Response Format

```json
{
  "statusCode": 200,
  "body": {
    "total_processed": 50000,
    "successful": 49850,
    "failed": 150,
    "duration_seconds": 823.45,
    "drugs_per_second": 60.7,
    "next_offset": 50000,
    "completed": true
  }
}
```

### Fields
- **total_processed:** Total drugs processed in this run
- **successful:** Drugs successfully stored in Redis
- **failed:** Drugs that failed (embedding or storage error)
- **duration_seconds:** Total execution time
- **drugs_per_second:** Throughput rate
- **next_offset:** Offset for next batch (for resuming)
- **completed:** Whether all drugs were processed

---

## Monitoring

### CloudWatch Metrics

**Namespace:** `DAW/DrugSync`

| Metric | Unit | Description |
|--------|------|-------------|
| `DrugsProcessed` | Count | Total drugs processed |
| `DrugsSuccessful` | Count | Drugs successfully synced |
| `DrugsFailed` | Count | Drugs that failed |
| `SyncDuration` | Seconds | Execution time |

**View metrics:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace "DAW/DrugSync" \
  --metric-name "DrugsProcessed" \
  --start-time "2025-11-10T00:00:00Z" \
  --end-time "2025-11-11T00:00:00Z" \
  --period 3600 \
  --statistics Sum \
  --region us-east-1
```

### CloudWatch Logs

**Log Group:** `/aws/lambda/DAW-DrugSync-{stage}`  
**Retention:** 7 days

**View recent logs:**
```bash
aws logs tail /aws/lambda/DAW-DrugSync-dev \
  --follow \
  --region us-east-1
```

**Filter for errors:**
```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/DAW-DrugSync-dev \
  --filter-pattern "ERROR" \
  --region us-east-1
```

### CloudWatch Alarms

**1. High Failure Rate**
- **Metric:** `DrugsFailed`
- **Threshold:** > 100 failures
- **Period:** 1 hour
- **Action:** Alert when sync quality degrades

**2. Lambda Errors**
- **Metric:** `AWS/Lambda Errors`
- **Threshold:** > 0 errors
- **Period:** 5 minutes
- **Action:** Alert when Lambda fails

---

## Performance

### Expected Throughput

| Batch Size | Drugs/sec | Time for 50K drugs |
|------------|-----------|-------------------|
| 50 | ~40 | ~21 minutes |
| 100 | ~60 | ~14 minutes |
| 200 | ~70 | ~12 minutes |

**Limiting Factors:**
1. Bedrock Titan API rate limits (1000 RPM)
2. Network latency (Lambda → Bedrock)
3. Redis write throughput

### Optimization Tips

**1. Increase batch size (faster):**
```json
{"batch_size": 200}
```

**2. Use concurrency (for large datasets):**
```bash
# Process in parallel chunks
aws lambda invoke --function-name DAW-DrugSync-dev \
  --payload '{"offset": 0, "max_drugs": 10000}' r1.json &

aws lambda invoke --function-name DAW-DrugSync-dev \
  --payload '{"offset": 10000, "max_drugs": 10000}' r2.json &

wait
```

**3. Disable quantization (faster, more memory):**
Set `ENABLE_QUANTIZATION=false` in environment variables

---

## Troubleshooting

### Issue: Lambda Timeout

**Symptom:** Function stops after 15 minutes

**Solution:**
1. Check `next_offset` in response
2. Resume from offset:
   ```bash
   aws lambda invoke \
     --function-name DAW-DrugSync-dev \
     --payload '{"offset": 30000}' \
     response.json
   ```

### Issue: High Failure Rate

**Symptom:** `failed` count is high

**Causes:**
1. Bedrock throttling
2. Redis connection issues
3. Invalid drug data

**Debug:**
1. Check CloudWatch Logs for error details
2. Look for patterns in failed drugs
3. Test embedding generation manually:
   ```python
   from embedding import get_embedding_model
   model = get_embedding_model()
   vec = model.embed("test drug name")
   ```

### Issue: Redis Out of Memory

**Symptom:** Redis errors in logs

**Solution:**
1. Enable quantization (if disabled)
2. Check Redis memory usage:
   ```bash
   redis-cli -h 10.0.11.245 INFO memory
   ```
3. Upgrade to larger instance if needed

### Issue: Aurora Connection Timeout

**Symptom:** Cannot connect to Aurora

**Causes:**
1. Security group misconfiguration
2. Aurora not in same VPC as Lambda
3. Wrong credentials

**Debug:**
1. Check Lambda is in VPC:
   ```bash
   aws lambda get-function-configuration \
     --function-name DAW-DrugSync-dev \
     --query 'VpcConfig'
   ```
2. Verify security groups allow Lambda → Aurora (port 3306)
3. Test credentials from Parameter Store

---

## Data Flow Details

### 1. Query Drugs from Aurora

**SQL Query:**
```sql
SELECT 
    NDC as ndc,
    UPPER(TRIM(LN)) as drug_name,
    UPPER(TRIM(COALESCE(BN, ''))) as brand_name,
    LOWER(TRIM(REGEXP_REPLACE(LN, ' [0-9].*', ''))) as generic_name,
    CAST(COALESCE(GCN_SEQNO, 0) AS UNSIGNED) as gcn_seqno,
    TRIM(COALESCE(DF, '')) as dosage_form,
    CASE WHEN INNOV = '1' THEN 'true' ELSE 'false' END as is_brand,
    CASE WHEN INNOV = '0' THEN 'true' ELSE 'false' END as is_generic,
    CASE WHEN DEA IN ('1','2','3','4','5') THEN DEA ELSE '' END as dea_schedule
FROM rndc14
WHERE LN IS NOT NULL
    AND LENGTH(TRIM(LN)) > 3
    AND NDC IS NOT NULL
ORDER BY NDC
LIMIT 100 OFFSET 0
```

### 2. Generate Embeddings

**For each drug:**
1. Extract drug name
2. Call Bedrock Titan:
   ```python
   embedding = bedrock.invoke_model(
       modelId="amazon.titan-embed-text-v2:0",
       body={"inputText": drug_name, "dimensions": 1024, "normalize": True}
   )
   ```
3. Add embedding to drug document

**Rate Limits:**
- Bedrock Titan: 1000 requests/minute
- Lambda automatically throttles to stay within limits

### 3. Store in Redis

**For each drug:**
```python
key = f"drug:{ndc}"
drug_doc = {
    "ndc": "00002010102",
    "drug_name": "LISINOPRIL 10 MG TABLET",
    "embedding": [0.123, -0.456, ...],  // 1024 floats
    "indexed_at": "2025-11-10T12:00:00Z",
    ...
}
redis.json().set(key, "$", drug_doc)
```

**Index:**
- Drugs are automatically indexed by RediSearch
- No manual indexing required (if index exists)

---

## Deployment

### Initial Deployment

```bash
cd /workspaces/DAW
npx sst deploy --stage dev
```

This will:
1. Create Lambda function
2. Set up IAM roles and policies
3. Create EventBridge schedule
4. Create CloudWatch alarms
5. Create log group

### Update Function Code

```bash
# Edit functions/sync/drug_loader.py
# Then redeploy
npx sst deploy --stage dev
```

### Update Environment Variables

**Via SST (recommended):**
Edit `infra/sync.ts` → redeploy

**Via AWS CLI (quick):**
```bash
aws lambda update-function-configuration \
  --function-name DAW-DrugSync-dev \
  --environment "Variables={BATCH_SIZE=200}" \
  --region us-east-1
```

---

## Cost Estimate

### Per Full Sync (50K drugs)

| Component | Cost | Notes |
|-----------|------|-------|
| Lambda execution | $0.20 | 15 min × 1024 MB |
| Bedrock Titan | $0.50 | 50K × $0.0001/1K tokens |
| Data transfer | $0.05 | In-region |
| **Total** | **~$0.75** | Per full sync |

### Monthly Cost (Daily Syncs)

| Item | Cost |
|------|------|
| Daily syncs | $22.50 |
| CloudWatch Logs | $1.00 |
| CloudWatch Metrics | $0.50 |
| **Total** | **~$24/month** |

---

## Next Steps

1. **Initial Sync:** Run manual invocation to load all drugs
2. **Verify Data:** Check Redis to confirm drugs are indexed
3. **Test Queries:** Use query examples to test search
4. **Monitor:** Watch CloudWatch metrics for first few runs
5. **Tune:** Adjust batch size based on performance

---

**Status:** ✅ Data sync pipeline complete  
**Ready for:** Deployment and initial sync  
**See Also:**
- `functions/sync/drug_loader.py` - Lambda function code
- `infra/sync.ts` - Infrastructure definition
- `docs/REDIS_QUERY_EXAMPLES.md` - Query examples after sync


# DAW Database Setup Guide

**Purpose:** Complete guide for deploying and loading the Aurora PostgreSQL database  
**Date:** November 6, 2025

---

## Overview

This guide walks through deploying the DAW infrastructure (VPC, Aurora, Redis) and loading FDB drug data into Aurora PostgreSQL.

### What Gets Deployed

1. **VPC Infrastructure** (via SST)
   - VPC with public and private subnets
   - NAT Gateway for Lambda outbound access
   - Security groups for RDS, Redis, Lambda
   - Internet Gateway

2. **Aurora PostgreSQL Serverless v2** (via SST)
   - Engine: PostgreSQL 15.5
   - Scaling: 0.5-4 ACU (auto-scaling)
   - Database name: `daw`
   - Username: `dawadmin`
   - Password: Auto-generated, stored in Secrets Manager
   - Connection string: Stored in Parameter Store

3. **Redis Stack 8.2.2 on EC2** (via SST)
   - Instance: r7g.large (ARM Graviton3)
   - Redis version: 8.2.2 with RediSearch module
   - LeanVec4x8 quantization support
   - Connection URL: Stored in Parameter Store

---

## Step-by-Step Deployment

### Prerequisites

1. **AWS CLI configured** with appropriate credentials
   ```bash
   aws configure
   # Set region to us-east-1
   ```

2. **PostgreSQL client installed** (for data loading)
   ```bash
   # Check if installed
   psql --version
   
   # If not, install:
   sudo apt-get update
   sudo apt-get install postgresql-client
   ```

3. **Node.js and npm** (for SST)
   ```bash
   node --version  # Should be v18+
   npm --version
   ```

4. **FDB data files** present
   ```bash
   ls -lh database/imports/
   # Should see: fdb tables.sql
   ```

---

### Step 1: Deploy Infrastructure (15-20 minutes)

**Deploy all infrastructure via SST:**

```bash
cd /workspaces/DAW
npx sst deploy --stage dev
```

**What this creates:**
- VPC with 2 public + 2 private subnets
- NAT Gateway (for Lambda → Bedrock connectivity)
- Security groups (RDS, Redis, Lambda)
- Aurora PostgreSQL Serverless v2 cluster + instance
- Redis Stack 8.2.2 on EC2 r7g.large
- Secrets Manager entries (DB password)
- Parameter Store entries (connection strings)

**Expected output:**
```
🚀 Deploying DAW to stage: dev
📍 Region: us-east-1
🌐 Creating network infrastructure...
💾 Creating Aurora PostgreSQL database...
🔴 Creating Redis Stack 8.2.2 on EC2 (ARM Graviton3)...

✓ Complete
```

**Deployment artifacts:**
- All resources tagged with `Project: DAW`
- All resources named with `DAW` prefix
- CloudFormation stack: `DAW-dev`

---

### Step 2: Verify Deployment (2-3 minutes)

**Run verification script:**

```bash
./scripts/verify-deployment.sh dev
```

**Expected healthy output:**
```
1️⃣  Checking Parameter Store...
   📍 Database connection string... ✅
   📍 Redis connection URL... ✅

2️⃣  Checking Aurora PostgreSQL...
   🗄️  Cluster status... ✅ Available
   📊 Instance count... 1
   🔌 Endpoint... daw-aurora-dev.cluster-xxxxx.us-east-1.rds.amazonaws.com

3️⃣  Checking Redis EC2 Instance...
   🔴 Instance status... ✅ Running
   🆔 Instance ID... i-xxxxx
   💻 Instance type... r7g.large
   🌐 Private IP... 10.0.x.x

4️⃣  Checking VPC Resources...
   🌐 VPC... ✅ vpc-xxxxx
   🔒 Security groups... 3 found
   📡 NAT Gateway... ✅ 1 available

5️⃣  Testing Database Connection...
   🔌 PostgreSQL connection... ✅ Connected
   📊 Database exists... ✅ Yes

✅ Infrastructure is READY!
```

**If not ready:**
- Aurora may still be initializing (wait 5-10 minutes)
- Redis EC2 may be provisioning
- Run script again after waiting

---

### Step 3: Load FDB Data (5-15 minutes)

**Load FDB tables SQL dump:**

```bash
./scripts/load-fdb-data.sh dev
```

**What this does:**
1. Retrieves Aurora connection string from Parameter Store
2. Tests database connectivity
3. Loads `database/imports/fdb tables.sql` in a transaction
4. Verifies key tables (rndc14, rgcnseq4, rnp2) have data
5. Creates log file: `/tmp/fdb-load-dev.log`

**Expected output:**
```
📡 Retrieving database connection string from Parameter Store...
✅ Connection string retrieved

🔌 Testing database connection...
✅ Database connection successful

📦 Loading FDB tables SQL dump (125M)...
   This may take 5-15 minutes depending on file size...

[PostgreSQL output...]

✅ FDB data loaded successfully!
   Duration: 8m 34s

🔍 Verifying data...
   Checking rndc14... ✅ 245,678 rows
   Checking rgcnseq4... ✅ 52,341 rows
   Checking rnp2... ✅ 523,981 rows
```

**If errors occur:**
- Check `/tmp/fdb-load-dev.log` for details
- Common issues:
  - Duplicate key violations (data already loaded)
  - Missing tables (SQL syntax errors)
  - Connection timeout (security group issues)

---

### Step 4: Create Indexes (2-5 minutes)

**Create performance indexes:**

```bash
./scripts/create-indexes.sh dev
```

**What this does:**
1. Creates indexes on key columns (NDC, GCN_SEQNO, etc.)
2. Handles optional tables gracefully (if not present in FDB dump)
3. Runs ANALYZE on all tables for query planner
4. Shows index summary and table row counts

**Expected output:**
```
📊 Creating indexes on rndc14 (primary drug table)...
✅ rndc14 indexes created

📊 Creating indexes on rgcnseq4 (drug classification)...
✅ rgcnseq4 indexes created

📊 Creating indexes on rnp2 (pricing)...
✅ rnp2 indexes created

📈 Analyzing tables for query optimizer...

✅ All indexes created and tables analyzed!

📋 Index Summary:
[Table showing all created indexes and sizes]

📊 Table Row Counts:
[Table showing row counts per table]

✅ Indexes created successfully!
   Duration: 3m 12s
```

**Indexes created:**

| Table | Index | Purpose |
|-------|-------|---------|
| rndc14 | idx_rndc14_ndc | Primary key lookups |
| rndc14 | idx_rndc14_gcn_seqno | Drug classification joins |
| rndc14 | idx_rndc14_ln | Label name searches |
| rndc14 | idx_rndc14_dea | DEA schedule filtering |
| rgcnseq4 | idx_rgcnseq4_gcn_seqno | Primary key |
| rgcnseq4 | idx_rgcnseq4_hicl_seqno | Drug class lookups |
| rgcnseq4 | idx_rgcnseq4_gtc | Therapeutic class |
| rnp2 | idx_rnp2_ndc | Price lookups by NDC |
| rnp2 | idx_rnp2_ndc_type_date | Composite price query |

---

### Step 5: Verify Data Load (1-2 minutes)

**Connect to database and verify:**

```bash
# Get connection string
export DB_CONN=$(aws ssm get-parameter \
  --name "/daw/dev/database/connection-string" \
  --with-decryption \
  --query 'Parameter.Value' \
  --output text)

# Connect
psql "$DB_CONN"
```

**Run test queries:**

```sql
-- Check table counts
SELECT 
  'rndc14' as table_name, 
  COUNT(*) as row_count 
FROM rndc14
UNION ALL
SELECT 
  'rgcnseq4', 
  COUNT(*) 
FROM rgcnseq4
UNION ALL
SELECT 
  'rnp2', 
  COUNT(*) 
FROM rnp2;

-- Test drug search (should be fast with indexes)
SELECT 
  d.ndc,
  d.ln as drug_name,
  d.bn as brand_name,
  g.str as strength,
  g.gcrt as route
FROM rndc14 d
JOIN rgcnseq4 g ON d.gcn_seqno = g.gcn_seqno
WHERE d.ln ILIKE '%atorvastatin%'
LIMIT 10;

-- Check index usage (should show index scans, not seq scans)
EXPLAIN ANALYZE
SELECT * FROM rndc14 WHERE ndc = '00071015023';

-- Verify query performance
\timing on
SELECT COUNT(*) FROM rndc14 WHERE gcn_seqno = 12345;
-- Should be < 10ms
```

**Expected results:**
- Row counts match FDB data (typically 200K-500K rows in rndc14)
- Drug searches return results in < 50ms
- EXPLAIN shows index scans (not sequential scans)
- Joins between tables work correctly

---

## Troubleshooting

### Deployment Issues

**Error: "Cannot find module './infra/network'"**
- **Cause:** SST v3 requires dynamic imports
- **Fix:** Check sst.config.ts uses `await import()` syntax

**Error: "Invalid stage: dev"**
- **Cause:** Stage not defined in project.config.ts
- **Fix:** Verify `stages.dev` exists in project.config.ts

**Error: "AWS account not configured"**
- **Cause:** AWS CLI not configured
- **Fix:** Run `aws configure` and set credentials

### Aurora Issues

**Error: "Cannot connect to database"**
- **Cause:** Security group not allowing your IP
- **Solution 1:** Add your IP to RDS security group (temporary)
- **Solution 2:** Use AWS Cloud9 or EC2 bastion host in same VPC
- **Solution 3:** Wait for Lambda functions (they'll be in VPC)

**Error: "Cluster is creating"**
- **Cause:** Aurora takes 10-15 minutes to fully provision
- **Fix:** Wait and re-run verification script

**Error: "Password authentication failed"**
- **Cause:** Password mismatch or not retrieved correctly
- **Fix:** Get password from Secrets Manager:
  ```bash
  aws secretsmanager get-secret-value \
    --secret-id DAW-DB-Password-dev \
    --query SecretString \
    --output text | jq -r '.password'
  ```

### Data Loading Issues

**Error: "relation already exists"**
- **Cause:** Tables already created (data partially loaded)
- **Fix:** Either:
  1. Drop and recreate database
  2. Skip table creation in SQL file

**Error: "out of memory"**
- **Cause:** Aurora ACU scaled too low for large import
- **Fix:** Wait or manually scale Aurora to higher ACU

**Error: "timeout"**
- **Cause:** Large SQL file taking too long
- **Fix:** Split file or increase statement timeout:
  ```sql
  SET statement_timeout = '30min';
  ```

### Index Creation Issues

**Warning: "table not found"**
- **Cause:** Optional FDB table not in your dump
- **Impact:** None - script handles gracefully
- **Fix:** No action needed

**Slow index creation**
- **Cause:** Large tables (>500K rows)
- **Impact:** May take 5-10 minutes
- **Fix:** Wait for completion (check CloudWatch for Aurora activity)

---

## Post-Deployment Tasks

### Security Hardening (Production)

1. **Rotate database password**
   ```bash
   aws secretsmanager rotate-secret \
     --secret-id DAW-DB-Password-prod
   ```

2. **Enable Aurora automatic backups**
   - Already configured (7-14 days retention)
   - Verify in AWS Console

3. **Enable VPC Flow Logs**
   ```bash
   aws ec2 create-flow-logs \
     --resource-type VPC \
     --resource-ids <vpc-id> \
     --traffic-type ALL \
     --log-destination-type cloud-watch-logs \
     --log-group-name /aws/vpc/daw-prod
   ```

### Monitoring Setup

1. **CloudWatch Alarms**
   - Aurora CPU > 80%
   - Aurora connections > 100
   - Aurora storage > 80% of allocated
   - Redis memory > 80%

2. **Query Performance Insights**
   - Enable in Aurora cluster settings
   - Review slow queries weekly

3. **Cost Monitoring**
   - Set up AWS Budget alert ($300/month threshold)
   - Monitor ACU usage trends

---

## Cost Estimate

| Resource | Configuration | Monthly Cost |
|----------|---------------|--------------|
| Aurora Serverless v2 | 0.5-2 ACU average | $50-100 |
| Redis EC2 (r7g.large) | 730 hours | $104 |
| EBS storage (Redis) | 100 GB GP3 | $8 |
| NAT Gateway | 1 instance | $32 |
| Data transfer | Moderate usage | $10 |
| **Total (dev)** | | **~$210/month** |

**Production will be higher** due to:
- Multi-AZ Aurora (2x instances)
- Higher ACU usage
- Additional backups
- Longer retention periods

---

## Next Steps

After database is loaded:

1. **Deploy Lambda functions** (search API, sync job)
2. **Sync data to Redis** (populate vector embeddings)
3. **Test end-to-end search** (API → Claude → Titan → Redis → Aurora)
4. **Set up monitoring** (CloudWatch dashboards)
5. **Load test** (verify performance targets)

---

## Quick Reference

### Useful Commands

```bash
# Check deployment status
./scripts/verify-deployment.sh dev

# Connect to database
psql "$(aws ssm get-parameter --name /daw/dev/database/connection-string --with-decryption --query Parameter.Value --output text)"

# View Aurora metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBClusterIdentifier,Value=daw-aurora-dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average

# SSH to Redis EC2 (via SSM)
aws ssm start-session --target <instance-id>

# Check Redis status
redis-cli -h <private-ip> ping

# Teardown (WARNING: Deletes everything)
npx sst remove --stage dev
```

### Support Resources

- **SST Documentation:** https://sst.dev/docs
- **Aurora PostgreSQL:** https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/
- **Redis Stack:** https://redis.io/docs/stack/
- **Project Docs:** `/workspaces/DAW/docs/`

---

**Last Updated:** November 6, 2025  
**Maintained by:** DAW Development Team


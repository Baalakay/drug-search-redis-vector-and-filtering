# DAW Infrastructure Deployment Status

**Date:** November 6, 2025  
**Stage:** dev  
**Status:** 🟡 IN PROGRESS

---

## What's Happening Now

### ✅ Completed Steps

1. **✅ Fixed SST Configuration**
   - Updated `sst.config.ts` to use dynamic imports (required by SST v3)
   - Changed from `import` to `await import()` syntax

2. **✅ Installed Dependencies**
   - Used `pnpm install` (handles workspace protocol correctly)
   - Installed @pulumi/aws 7.11.0
   - Installed SST 3.17.23
   - Total: 396 packages installed

3. **✅ Created Deployment Scripts**
   - `scripts/load-fdb-data.sh` - Load FDB tables SQL into Aurora
   - `scripts/create-indexes.sh` - Create performance indexes
   - `scripts/create-indexes.sql` - Index definitions
   - `scripts/verify-deployment.sh` - Check deployment status

4. **✅ Created Documentation**
   - `docs/DATABASE_SETUP_GUIDE.md` - Complete setup guide
   - `docs/DAW_ARCHITECTURE_OVERVIEW.md` - Architecture for Aaron (human-focused examples)

### 🟡 Currently Running

**SST Infrastructure Deployment:**
```bash
npx sst deploy --stage dev
```

**This is deploying:**
- VPC with public/private subnets (2 AZs)
- Internet Gateway
- NAT Gateway (for Lambda → Bedrock access)
- Security groups (RDS, Redis, Lambda)
- **Aurora PostgreSQL Serverless v2 cluster** (15-20 minutes)
  - Engine: PostgreSQL 15.5
  - Scaling: 0.5-4 ACU
  - Database: `daw`
  - Password: Auto-generated, stored in Secrets Manager
  - Connection string: Parameter Store `/daw/dev/database/connection-string`
- **Redis Stack 8.2.2 on EC2 r7g.large** (5-10 minutes)
  - ARM Graviton3 instance
  - User-data script installs Redis Stack 8.2.2
  - LeanVec4x8 quantization support
  - Connection URL: Parameter Store `/daw/dev/redis/url`

**Expected completion:** 15-20 minutes (Aurora is the slowest)

**Monitor progress:**
```bash
# Check real-time logs
tail -f /tmp/sst-deploy-full.log

# Check deployment status
./scripts/verify-deployment.sh dev
```

---

## Next Steps (After Deployment Completes)

### Step 1: Verify Deployment (2 minutes)

```bash
./scripts/verify-deployment.sh dev
```

**Expected output when ready:**
- ✅ Aurora cluster: Available
- ✅ Redis EC2: Running
- ✅ VPC resources: Created
- ✅ Database connection: Successful

### Step 2: Load FDB Data (5-15 minutes)

```bash
./scripts/load-fdb-data.sh dev
```

**What this does:**
- Retrieves Aurora connection string from Parameter Store
- Tests database connectivity
- Loads `database/imports/fdb tables.sql`
- Verifies key tables have data (rndc14, rgcnseq4, rnp2)

**Expected result:**
- FDB tables loaded successfully
- 200K-500K drugs in rndc14
- Log file: `/tmp/fdb-load-dev.log`

### Step 3: Create Indexes (2-5 minutes)

```bash
./scripts/create-indexes.sh dev
```

**What this does:**
- Creates indexes on NDC, GCN_SEQNO, drug names
- Handles optional tables gracefully
- Runs ANALYZE for query optimizer
- Shows index summary and row counts

**Expected result:**
- 15-20 indexes created
- All tables analyzed
- Query performance optimized

### Step 4: Verify Data & Performance (2 minutes)

```bash
# Connect to database
export DB_CONN=$(aws ssm get-parameter \
  --name "/daw/dev/database/connection-string" \
  --with-decryption \
  --query 'Parameter.Value' \
  --output text)

psql "$DB_CONN"
```

**Test queries:**
```sql
-- Check row counts
SELECT 
  'rndc14' as table, COUNT(*) as rows FROM rndc14
UNION ALL
SELECT 'rgcnseq4', COUNT(*) FROM rgcnseq4
UNION ALL
SELECT 'rnp2', COUNT(*) FROM rnp2;

-- Test indexed query (should be < 10ms)
\timing on
SELECT * FROM rndc14 WHERE ndc = '00071015023';

-- Test drug search
SELECT 
  d.ndc,
  d.ln as drug_name,
  g.str as strength
FROM rndc14 d
JOIN rgcnseq4 g ON d.gcn_seqno = g.gcn_seqno
WHERE d.ln ILIKE '%atorvastatin%'
LIMIT 10;
```

---

## Infrastructure Components

### VPC & Networking

| Resource | Configuration | Purpose |
|----------|---------------|---------|
| VPC | 10.0.0.0/16 | Isolated network |
| Public Subnets | 10.0.1.0/24, 10.0.2.0/24 | NAT Gateway, Bastion |
| Private Subnets | 10.0.3.0/24, 10.0.4.0/24 | RDS, Redis, Lambda |
| NAT Gateway | 1 instance | Lambda → Bedrock access |
| Internet Gateway | 1 instance | Public subnet internet |

### Aurora PostgreSQL

| Setting | Value |
|---------|-------|
| Engine | aurora-postgresql |
| Version | 15.5 |
| Mode | Serverless v2 |
| Min ACU | 0.5 |
| Max ACU | 4 |
| Database | daw |
| Master User | dawadmin |
| Backup Retention | 7 days (dev), 14 days (prod) |
| Encryption | Yes (at-rest) |
| Multi-AZ | No (dev), Yes (prod) |

### Redis Stack on EC2

| Setting | Value |
|---------|-------|
| Instance Type | r7g.large (ARM Graviton3) |
| vCPUs | 2 |
| Memory | 16 GB |
| Redis Version | 8.2.2 (Redis Stack) |
| Modules | RediSearch, RedisJSON |
| Quantization | LeanVec4x8 support |
| Storage | 100 GB GP3 SSD |
| Monitoring | CloudWatch agent |

### Security Groups

| Group | Purpose | Inbound Rules |
|-------|---------|---------------|
| RDS-SG | Aurora access | PostgreSQL (5432) from Lambda-SG, Redis-SG |
| Redis-SG | Redis access | Redis (6379) from Lambda-SG |
| Lambda-SG | Lambda functions | None (outbound only) |

---

## Cost Estimate

| Resource | Monthly Cost (dev) |
|----------|-------------------|
| Aurora Serverless v2 | $50-100 |
| Redis EC2 (r7g.large) | $104 |
| EBS Storage (100GB) | $8 |
| NAT Gateway | $32 |
| Data Transfer | $10 |
| **Total** | **~$210/month** |

**Note:** Production costs will be higher due to:
- Multi-AZ Aurora (2x instances)
- Higher ACU usage
- Additional backups
- Longer retention

---

## Troubleshooting

### If Deployment Fails

**Error: "Cannot find package @pulumi/aws"**
- ✅ FIXED: Installed via `pnpm install`

**Error: "Top level imports not allowed"**
- ✅ FIXED: Changed to dynamic imports in sst.config.ts

**Error: "AWS credentials not configured"**
- Run: `aws configure`
- Set region to `us-east-1`

**Error: "Insufficient permissions"**
- Verify IAM user has required permissions:
  - EC2 (VPC, instances, security groups)
  - RDS (clusters, instances, subnet groups)
  - SSM (parameters)
  - Secrets Manager
  - CloudFormation
  - IAM (limited, for service roles)

### If Connection Fails After Deployment

**Aurora: Cannot connect**
- Security group may not allow your IP
- Aurora may still be initializing (wait 5-10 minutes)
- Try from EC2 bastion in same VPC

**Redis: Cannot connect**
- Use AWS Systems Manager Session Manager:
  ```bash
  aws ssm start-session --target <instance-id>
  redis-cli ping
  ```

---

## Monitoring Deployment

### Check CloudFormation

```bash
# View stack events
aws cloudformation describe-stack-events \
  --stack-name DAW-dev \
  --max-items 20 \
  --region us-east-1 \
  --query 'StackEvents[*].[Timestamp,ResourceStatus,ResourceType,LogicalResourceId]' \
  --output table
```

### Check Aurora Status

```bash
# Cluster status
aws rds describe-db-clusters \
  --db-cluster-identifier daw-aurora-dev \
  --query 'DBClusters[0].Status' \
  --output text

# Instance status
aws rds describe-db-instances \
  --db-instance-identifier daw-aurora-instance-dev \
  --query 'DBInstances[0].DBInstanceStatus' \
  --output text
```

### Check Redis EC2

```bash
# Instance status
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=DAW-Redis-Server-dev" \
  --query 'Reservations[0].Instances[0].[State.Name,PrivateIpAddress,InstanceId]' \
  --output table

# Check user-data script completion
aws ec2 get-console-output \
  --instance-id <instance-id> \
  --output text | grep -A5 "Redis Stack"
```

---

## After Database is Loaded

### Phase 2 Development Tasks

1. **Create Embedding Abstraction Layer**
   - `packages/core/src/embedding/base.py`
   - `packages/core/src/embedding/titan.py`
   - `packages/core/src/embedding/sapbert.py`
   - `packages/core/src/embedding/__init__.py`

2. **Create Data Sync Lambda**
   - Query drugs from Aurora
   - Generate embeddings via Titan
   - Store in Redis with filters
   - Schedule nightly via EventBridge

3. **Create Search API Lambda**
   - Claude query preprocessing
   - Titan embedding generation
   - Redis hybrid search
   - Aurora enrichment
   - Response formatting

4. **Deploy & Test**
   - Update sst.config.ts with Lambda functions
   - Deploy to dev
   - Test end-to-end search
   - Measure latency and accuracy

---

## Quick Reference Commands

```bash
# Deploy infrastructure
npx sst deploy --stage dev

# Check deployment status
./scripts/verify-deployment.sh dev

# Load FDB data
./scripts/load-fdb-data.sh dev

# Create indexes
./scripts/create-indexes.sh dev

# Connect to database
psql "$(aws ssm get-parameter --name /daw/dev/database/connection-string --with-decryption --query Parameter.Value --output text)"

# SSH to Redis (via SSM)
INSTANCE_ID=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=DAW-Redis-Server-dev" --query 'Reservations[0].Instances[0].InstanceId' --output text)
aws ssm start-session --target $INSTANCE_ID

# View SST outputs
npx sst dev --stage dev  # Start SST console
# Or: cat .sst/outputs.json

# Remove everything (WARNING: Deletes all data!)
npx sst remove --stage dev
```

---

## Support

- **Documentation:** `/workspaces/DAW/docs/`
- **SST Docs:** https://sst.dev/docs
- **Aurora Docs:** https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/
- **Redis Stack:** https://redis.io/docs/stack/

---

**Last Updated:** November 6, 2025 21:35 UTC  
**Deployment Log:** `/tmp/sst-deploy-full.log`  
**Status:** 🟡 Deploying (Aurora cluster creation ~15-20 min total)


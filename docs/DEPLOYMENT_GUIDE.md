# DAW Deployment Guide

## Prerequisites

### AWS Credentials
Ensure you have AWS credentials configured for the target account:

```bash
# Set AWS credentials
export AWS_PROFILE=your-profile-name

# Or use environment variables
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
```

### Account Configuration
Set account IDs for each stage (optional, defaults in `project.config.ts`):

```bash
export AWS_ACCOUNT_ID_DEV=123456789012
export AWS_ACCOUNT_ID_STAGING=234567890123
export AWS_ACCOUNT_ID_PROD=345678901234
```

---

## Phase 1: Infrastructure Deployment

### Step 1: Install Dependencies

```bash
# Install Node.js dependencies
npm install

# Verify SST is installed
npx sst version
```

### Step 2: Deploy Infrastructure

```bash
# Deploy to dev stage
npx sst deploy --stage dev

# This will create:
# - VPC with public/private subnets
# - NAT Gateway
# - Aurora PostgreSQL Serverless v2 cluster
# - Redis Stack 8.2.2 on EC2 r7g.large (ARM Graviton3)
# - Security groups
# - Secrets Manager entries
# - Parameter Store entries
# - CloudWatch logs and alarms
```

**Expected time:** 15-20 minutes (Aurora and Redis take time to provision)

### Step 3: Verify Deployment

```bash
# Check deployment status
npx sst dev --stage dev

# View outputs
npx sst console --stage dev
```

Expected outputs:
- `database.endpoint` - Aurora endpoint
- `database.connectionString` - Parameter Store path
- `redis.endpoint` - Redis endpoint  
- `redis.connectionUrl` - Parameter Store path
- `network.vpcId` - VPC ID
- `network.lambdaSecurityGroupId` - Lambda security group

### Step 4: Import FDB Data

```bash
# Get database connection string
DB_CONN=$(aws ssm get-parameter --name "/daw/dev/database/connection-string" --with-decryption --query "Parameter.Value" --output text)

# Import FDB tables
psql "$DB_CONN" < database/imports/fdb\ tables.sql
```

**Expected time:** 5-10 minutes (200MB SQL file)

### Step 5: Create Database Indexes

```sql
-- Connect to database
psql "$DB_CONN"

-- Create indexes on key columns
CREATE INDEX idx_rndc14_ndc ON rndc14(NDC);
CREATE INDEX idx_rndc14_gcn_seqno ON rndc14(GCN_SEQNO);
CREATE INDEX idx_rndc14_ln ON rndc14(LN);
CREATE INDEX idx_rndc14_bn ON rndc14(BN);

CREATE INDEX idx_rgcnseq4_gcn_seqno ON rgcnseq4(GCN_SEQNO);
CREATE INDEX idx_rgcnseq4_hic3 ON rgcnseq4(HIC3);
CREATE INDEX idx_rgcnseq4_hicl_seqno ON rgcnseq4(HICL_SEQNO);

CREATE INDEX idx_rnp2_ndc ON rnp2(NDC);
```

---

## Phase 2: Embedding Layer (Coming Soon)

Will be covered in next deployment phase.

---

## Troubleshooting

### Issue: SST deployment fails with "no default VPC"

**Solution:** The infrastructure creates its own VPC, this shouldn't happen. If it does, check AWS credentials.

### Issue: Aurora cluster creation times out

**Solution:** Aurora can take 10-15 minutes. Wait patiently. Check CloudFormation events:

```bash
aws cloudformation describe-stack-events \
  --stack-name DAW-dev-aurora-stack \
  --max-items 10
```

### Issue: Redis cluster fails to create

**Solution:** Check if Redis 7.1 is available in us-east-1:

```bash
aws elasticache describe-cache-engine-versions \
  --engine redis \
  --engine-version 7.1
```

If not available, update `infra/cache.ts` to use `engineVersion: "7.0"`.

### Issue: Import fails - "permission denied"

**Solution:** Check security group allows your IP:

```bash
# Get your IP
MY_IP=$(curl -s https://checkip.amazonaws.com)

# Add temporary ingress rule
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 5432 \
  --cidr $MY_IP/32
```

**Remember to remove this rule after import!**

---

## Cleanup

### Remove Deployment

```bash
# Remove dev stage
npx sst remove --stage dev
```

**Warning:** This will delete all resources including databases!

### Staged Removal

If you want to keep data:

1. Take Aurora snapshot
2. Export Redis data
3. Remove deployment
4. Restore from snapshots later

---

## Cost Estimate

### Dev Stage (running 24/7)
- Aurora Serverless v2 (0.5-4 ACU): ~$45/month
- Redis EC2 r7g.large: ~$95/month
- EBS GP3 storage (50 GB): ~$4/month
- NAT Gateway: ~$33/month
- Data transfer: ~$10/month
- **Total: ~$190/month** (16% savings vs ElastiCache)

### Optimization Tips
- Stop Aurora when not in use (saves ~$45/month)
- Use smaller Redis node in dev (r7g.medium saves ~$60/month)
- Remove dev stack overnight (run deploy script each morning)

---

## Next Steps

After infrastructure is deployed:
1. ✅ Phase 1 complete
2. ⏳ Phase 2: Create embedding abstraction layer
3. ⏳ Phase 3: Set up Redis indexes
4. ⏳ Phase 4: Build Claude query parser
5. ⏳ Phase 5: Create data sync pipeline

See `docs/IMPLEMENTATION_PLAN.md` for full roadmap.


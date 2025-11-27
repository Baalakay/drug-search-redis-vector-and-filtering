# DAW Infrastructure Deployment Status

**Last Updated:** 2025-11-10  
**Stage:** dev  
**Region:** us-east-1  
**Status:** ✅ DEPLOYED AND OPERATIONAL

---

## 📊 Deployment Summary

| Component | Status | Details |
|-----------|--------|---------|
| **VPC** | ✅ Deployed | vpc-050fab8a9258195b7 |
| **Aurora MySQL** | ✅ Deployed & Data Loaded | daw-aurora-dev (118 tables, 11.4M+ rows) |
| **Redis Stack** | ✅ Deployed & Running | i-0ec914f45110b9b9c (Redis 8.2.2) |
| **Security Groups** | ✅ Configured | Lambda, Redis, RDS access |
| **NAT Gateway** | ✅ Deployed | For Lambda → Bedrock |

---

## 🌐 Network Infrastructure

### VPC Configuration
- **VPC ID:** `vpc-050fab8a9258195b7`
- **CIDR:** 10.0.0.0/16
- **Public Subnets:** 2 (us-east-1a, us-east-1b)
- **Private Subnets:** 2 (us-east-1a, us-east-1b)
- **NAT Gateway:** Deployed in public subnet
- **Internet Gateway:** Attached

### Security Groups
- **DAW-Lambda-SG:** For Lambda functions (access to Redis + Aurora)
- **DAW-Redis-SG:** For Redis EC2 (port 6379)
- **DAW-RDS-SG:** For Aurora MySQL (port 3306)

---

## 💾 Aurora MySQL Database

### Cluster Details
- **Identifier:** `daw-aurora-dev`
- **Endpoint:** `daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com`
- **Port:** 3306
- **Engine:** aurora-mysql
- **Engine Version:** 8.0.mysql_aurora.3.08.2
- **Status:** available

### Connection Information
- **Username:** `dawadmin`
- **Password:** `DawAdmin2025!SecurePass` (manually set for testing)
- **Database:** `fdb` (note: SQL import created its own database)

### Data Load Status ✅
- **Tables Loaded:** 118
- **Total Rows:** 11.4M+
- **Total Size:** ~835 MB
- **Load Date:** 2025-11-10
- **Load Duration:** ~14 minutes

### Key Tables
| Table | Rows | Size | Description |
|-------|------|------|-------------|
| `rnp2` | 11.4M | 835 MB | Drug products |
| `rndc14` | 464K | 213 MB | NDC codes with GCN mapping |
| `rxnconso` | 961K | 212 MB | RxNorm concepts |
| `rimkcs0_rxn_fdb_cs_lnk` | 833K | 160 MB | RxNorm-FDB links |

### Indexes
- ✅ **rndc14:**
  - PRIMARY KEY on `NDC`
  - Index on `LBLRID`
  - Index on `GCN_SEQNO`
- ✅ **rnp2:**
  - Composite PRIMARY KEY on `(NDC, NPT_TYPE, NPT_DATEC)`
  - Index on `NPT_TYPE`
- ✅ **rxnconso:**
  - Index on `RXCUI`
  - Index on `TTY`
  - Index on `CODE`

### Query Performance
- **NDC lookup:** 0.02s (PRIMARY KEY)
- **GCN_SEQNO lookup:** 0.03s (indexed)
- **Drug name search (LIKE):** 0.26s (464K rows)
- **RxNorm concept search:** 0.14s (961K rows)

---

## 🔴 Redis Stack on EC2

### Instance Details
- **Instance ID:** `i-0ec914f45110b9b9c`
- **Instance Type:** r7g.large (ARM Graviton3, 2 vCPU, 16 GB RAM)
- **AMI:** Ubuntu 22.04 LTS
- **Internal IP:** 10.0.11.245
- **Availability Zone:** us-east-1a

### Redis Configuration
- **Version:** Redis Stack 8.2.2
- **Port:** 6379
- **Modules:**
  - RediSearch 2.10.10
  - RedisJSON 2.8.7
  - RedisTimeSeries 1.12.4
  - RedisBloom 2.8.7
- **Memory:** 16 GB available for vectors
- **Quantization:** LeanVec4x8 support available

### Monitoring
- **CloudWatch Alarm:** CPU > 80% for 5 minutes
- **CloudWatch Alarm:** Memory > 80% for 5 minutes
- **Logs:** CloudWatch Logs Group `/daw/redis/dev`

### Access
- **From Lambda:** Configured via security group
- **SSH Access:** Via AWS Systems Manager Session Manager
  ```bash
  aws ssm start-session --target i-0ec914f45110b9b9c --region us-east-1
  ```

---

## 🔐 Secrets & Parameters

### Secrets Manager
- **DAW-DB-Password-dev:** Aurora MySQL password (JSON format)
- **DAW-Redis-AuthToken-dev:** Redis authentication token

### Parameter Store
- **/daw/dev/database/connection-string:** Aurora connection string (SecureString)
- **/daw/dev/redis/url:** Redis connection URL
- **/daw/dev/redis/host:** Redis host (10.0.11.245)

---

## 📈 Cost Estimate (Monthly)

| Resource | Type | Cost |
|----------|------|------|
| Aurora MySQL | Serverless v2 (0.5-1 ACU) | ~$43-86/month |
| Redis EC2 | r7g.large | ~$104/month |
| NAT Gateway | Data transfer | ~$45/month |
| Data Transfer | Inter-AZ | ~$10/month |
| **Total** | | **~$202-245/month** |

---

## ✅ Deployment Verification

### Infrastructure Checks ✅
- [x] VPC created with correct CIDR
- [x] Public/private subnets in 2 AZs
- [x] Internet Gateway attached
- [x] NAT Gateway deployed
- [x] Security groups configured
- [x] Aurora MySQL cluster deployed
- [x] Aurora MySQL instance running
- [x] Redis EC2 instance running
- [x] Secrets created and accessible
- [x] Parameters stored correctly

### Data Load Verification ✅
- [x] FDB SQL file downloaded to Redis EC2
- [x] MySQL client installed on Redis EC2
- [x] Aurora MySQL master password reset
- [x] Connection from Redis EC2 to Aurora successful
- [x] SQL import completed (118 tables)
- [x] Table count verified (118 tables)
- [x] Row counts verified (11.4M+ rows)
- [x] Indexes verified (PRIMARY KEY + secondary)
- [x] Query performance tested (< 1s)

### Connectivity Tests ✅
- [x] Redis EC2 can access Aurora MySQL (port 3306)
- [x] Security group rules validated
- [x] MySQL connection successful
- [x] Data queries return expected results

---

## 🚀 Next Steps

### Phase 2: Embedding Layer (In Progress)
1. Create embedding abstraction layer
   - `packages/core/src/embedding/base.py`
   - `packages/core/src/embedding/titan.py`
   - `packages/core/src/embedding/sapbert.py`
   - `packages/core/src/embedding/__init__.py`
2. Write unit tests for embedding layer
3. Test Titan embeddings via Bedrock

### Phase 3: Redis Index Setup
1. Design Redis schema for drug search
2. Create RediSearch index with quantization
3. Configure hybrid search (vector + filters)
4. Test index creation and queries

### Phase 4: Data Sync Pipeline
1. Create Lambda function to sync Aurora → Redis
2. Generate embeddings for drug names
3. Store in Redis with filter fields
4. Schedule daily sync job

---

## 📝 Known Issues & Notes

### Notes
1. **Database Name:** FDB SQL dump created its own `fdb` database (not `daw`)
2. **Password:** Temporarily set to `DawAdmin2025!SecurePass` for testing
   - Should rotate to Parameter Store value for production
3. **Redis Auth:** Not yet enabled (will enable in Phase 3)
4. **User:** Running on AWS Workspace VDI without local Docker support

### Resolved Issues ✅
1. ~~Aurora PostgreSQL → MySQL:~~ Corrected engine type to match FDB format
2. ~~Password mismatch:~~ Manually reset Aurora password for testing
3. ~~DNS resolution:~~ Used cluster endpoint successfully
4. ~~MySQL client missing:~~ Installed `mysql-client` on Ubuntu
5. ~~S3 access denied:~~ Added IAM permissions to Redis EC2 role
6. ~~Security group:~~ Added Redis→Aurora ingress rule

---

## 🔧 Maintenance Commands

### Connect to Aurora MySQL
```bash
mysql -h daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com \
  -P 3306 -u dawadmin -p'DawAdmin2025!SecurePass' fdb
```

### SSH to Redis EC2
```bash
aws ssm start-session --target i-0ec914f45110b9b9c --region us-east-1
```

### Check Redis Status
```bash
# On Redis EC2
sudo systemctl status redis-stack-server
redis-cli ping
```

### Query Database Stats
```bash
mysql -h daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com \
  -P 3306 -u dawadmin -p'DawAdmin2025!SecurePass' fdb \
  -e "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema='fdb' ORDER BY table_rows DESC LIMIT 10;"
```

### Redeploy Infrastructure
```bash
cd /workspaces/DAW
npx sst deploy --stage dev
```

---

**Deployment Status:** ✅ COMPLETE AND OPERATIONAL  
**Ready for:** Phase 2 - Embedding Abstraction Layer  
**Last Verified:** 2025-11-10

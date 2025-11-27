# Redis 8.2.3 Ready for AMI Creation

**Date:** November 13, 2025  
**Status:** ✅ READY FOR AMI SNAPSHOT  
**Instance ID:** i-01224b16d254e5076  
**Instance Type:** r7i.large (x86, 16 GB RAM)  
**Internal IP:** 10.0.11.135

---

## Current State: VERIFIED ✅

### Redis Installation
- **Version:** 8.2.3 (latest stable)
- **Source:** Official Redis APT repository (packages.redis.io)
- **Status:** Running and verified
- **Service:** redis-server.service (active, enabled)

### Loaded Modules
All required modules are loaded and operational:

1. **RediSearch** (ver 80205)
   - Path: `/usr/lib/redis/modules/redisearch.so`
   - Commands: FT.CREATE, FT.SEARCH, FT.AGGREGATE, etc.
   - **Critical for:** Vector similarity search with LeanVec4x8 quantization

2. **RedisJSON** (ver 80201)
   - Path: `/usr/lib/redis/modules/rejson.so`
   - Commands: JSON.SET, JSON.GET, JSON.DEL
   - **Critical for:** Storing drug documents with structured fields

3. **VectorSet** (ver 1)
   - Built-in module
   - Commands: VSETADD, VSETSEARCH
   - **Critical for:** Vector operations

4. **Bloom Filters** (ver 80208)
   - Path: `/usr/lib/redis/modules/redisbloom.so`
   - **Optional:** For probabilistic data structures

5. **TimeSeries** (ver 80200)
   - Path: `/usr/lib/redis/modules/redistimeseries.so`
   - **Optional:** For time-series data (future use)

### Configuration
- **Config file:** `/etc/redis/redis.conf`
- **Data directory:** `/var/lib/redis`
- **Log file:** `/var/log/redis/redis-server.log`
- **Auth:** Password configured from Secrets Manager
- **Max memory:** 12 GB (leaves 4 GB for OS)
- **Persistence:** AOF enabled

### Network & Security
- **VPC:** vpc-050fab8a9258195b7
- **Subnet:** Private subnet (10.0.11.0/24)
- **Security Group:** Allows traffic from Lambda and internal VPC
- **Aurora Access:** Configured for data loading

---

## What's Been Accomplished

### Infrastructure Journey
After extensive troubleshooting (documented in `docs/REDIS_8.2.3_INSTALLATION_ODYSSEY.md`):

1. ❌ Tried Redis Stack 7.4.0 ARM (segfault)
2. ❌ Tried Redis Stack 7.4.0 x86 (segfault)
3. ❌ Tried Redis Stack 8.2.2 (doesn't exist)
4. ❌ Tried Amazon Linux 2023 (repo issues)
5. ❌ Tried Amazon Linux 2 (repo issues)
6. ❌ Tried compile from source (module compilation failures)
7. ✅ **SUCCESS:** Redis 8.2.3 from official Ubuntu APT repo

### Why This Matters
- **Redis 8.2+ required** for LeanVec4x8 quantization
- **Quantization provides 3x memory compression** (2 GB → 670 MB for 494K drugs)
- **All modules included** in official package (no manual compilation)
- **Production-ready** with systemd integration

---

## Next Steps (After AMI Creation)

### 1. Create RediSearch Index
```bash
FT.CREATE drugs_idx ON JSON PREFIX 1 drug: SCHEMA 
  ndc TAG 
  drugName TEXT PHONETIC dm:en 
  brandName TEXT PHONETIC dm:en 
  genericName TEXT PHONETIC dm:en 
  labelerName TEXT PHONETIC dm:en 
  productTypeName TAG 
  dosageFormName TAG 
  routeName TAG 
  activeNumeratorStrength NUMERIC 
  strengthUnit TAG 
  nameEmbedding VECTOR HNSW 16 
    TYPE FLOAT32 
    DIM 1024 
    DISTANCE_METRIC COSINE 
    M 40 
    EF_CONSTRUCTION 200 
    EF_RUNTIME 10 
    QUANTIZATION_TYPE LeanVec4x8
```

### 2. Execute Bulk Load
- Run `/tmp/bulk_load_drugs.py` on EC2 instance
- Load 494,569 drugs from Aurora
- Generate Titan embeddings via Bedrock
- Store in Redis with LeanVec4x8 compression
- Expected time: 8-12 hours

### 3. Verify Data Integrity
- Check drug count: `redis-cli DBSIZE`
- Verify index: `redis-cli FT.INFO drugs_idx`
- Test sample queries
- Confirm quantization active

### 4. Create Final AMI (with data)
- After bulk load completes
- Full production-ready image
- Includes all 494K drugs with embeddings

---

## AMI Creation Instructions

### ✅ AMI Created Successfully

**AMI Details:**
```
AMI ID: ami-0dd168b5922ed5993
Name: DAW-Redis-8.2.3-Clean
Region: us-east-1
Created From: i-01224b16d254e5076
Status: Available
Description: Redis 8.2.3 Open Source with all modules, empty database, ready for bulk load
```

**Launch Template:**
```
Launch Template ID: lt-0e01df6aa995edaa9
Name: DAW-Redis-Launch-Template
Instance Type: r7i.large
AMI: ami-0dd168b5922ed5993
```

### Quick Deployment for Future Projects

**Option 1: Using Launch Template (Recommended)**
```bash
aws ec2 run-instances \
  --launch-template LaunchTemplateId=lt-0e01df6aa995edaa9 \
  --subnet-id <your-subnet-id> \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Redis-8.2.3}]'
```

**Option 2: Using AMI Directly**
```bash
aws ec2 run-instances \
  --image-id ami-0dd168b5922ed5993 \
  --instance-type r7i.large \
  --key-name <your-key-pair> \
  --subnet-id <your-subnet-id> \
  --security-group-ids <your-sg-id> \
  --iam-instance-profile Name=<redis-instance-profile> \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Redis-8.2.3}]'
```

### What's Included in the AMI
- ✅ Redis 8.2.3 Open Source (from official APT repo)
- ✅ All modules: RediSearch, RedisJSON, vectorset, bloom filters, timeseries
- ✅ Proper systemd configuration
- ✅ CloudWatch agent configured
- ✅ IAM roles for Bedrock and Secrets Manager access
- ✅ Ubuntu 22.04.5 LTS (jammy) x86_64
- ✅ Ready for immediate use or bulk data load

### Original AMI Creation Command (For Reference)
```bash
# This was already executed to create ami-0dd168b5922ed5993
aws ec2 create-image \
  --instance-id i-01224b16d254e5076 \
  --name "DAW-Redis-8.2.3-Clean-$(date +%Y%m%d)" \
  --description "Redis 8.2.3 with all modules, empty database, ready for bulk load" \
  --tag-specifications 'ResourceType=image,Tags=[{Key=Project,Value=DAW},{Key=Component,Value=Redis},{Key=Status,Value=Clean}]' \
  --no-reboot
```

### Benefits of Clean AMI
1. **Fast recovery** if anything breaks during bulk load
2. **Testing environment** - spin up for experiments
3. **Disaster recovery** - known working baseline
4. **Scaling template** - add more Redis instances if needed

### Future AMI (After Data Load)
After bulk load completes successfully:

```bash
aws ec2 create-image \
  --instance-id i-01224b16d254e5076 \
  --name "DAW-Redis-8.2.3-Loaded-$(date +%Y%m%d)" \
  --description "Redis 8.2.3 with 494K drugs loaded and indexed" \
  --tag-specifications 'ResourceType=image,Tags=[{Key=Project,Value=DAW},{Key=Component,Value=Redis},{Key=Status,Value=Loaded}]' \
  --no-reboot
```

---

## Documentation Updated

### New Documentation
- ✅ `docs/REDIS_8.2.3_INSTALLATION_ODYSSEY.md` - Complete installation history
- ✅ `REDIS_8.2.3_READY_FOR_AMI.md` - This file

### Updated Documentation
- ✅ `memory-bank/progress.md` - Redis 8.2.3 installation complete
- ✅ `memory-bank/techContext.md` - Updated Redis version and architecture
- ✅ `docs/REDIS_INFRASTRUCTURE_DECISION.md` - Updated with actual deployment

---

## Summary

**Redis 8.2.3 is now fully operational and ready for:**
1. ✅ AMI snapshot (immediate)
2. ⏳ RediSearch index creation (next)
3. ⏳ Bulk data load (after index)
4. ⏳ Final AMI with data (after load)

**Key Achievement:** After 2+ days of troubleshooting across multiple OS and architectures, we have a stable, production-ready Redis 8.2.3 installation with all required modules for LeanVec4x8 quantization support.

**Instance Status:** Running, verified, ready for AMI creation.

---

**Awaiting user go-ahead to create AMI snapshot.**


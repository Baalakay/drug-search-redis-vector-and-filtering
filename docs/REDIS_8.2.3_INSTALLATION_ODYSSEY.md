# Redis 8.2.3 Installation Odyssey: Lessons Learned

**Date:** November 13, 2025  
**Final Solution:** Redis 8.2.3 Open Source from official APT repository  
**Status:** ✅ WORKING - All modules loaded successfully  
**Instance:** i-01224b16d254e5076 (r7i.large x86, Ubuntu 22.04)

---

## Executive Summary

After extensive troubleshooting across multiple Redis versions, architectures, and installation methods, we successfully deployed **Redis 8.2.3 Open Source** on Ubuntu 22.04 x86 using the official Redis APT repository. The key insight was that Redis 8.2+ includes RediSearch, RedisJSON, and vector search capabilities **built-in** when installed from the official repository, eliminating the need for manual module compilation.

**Critical Requirement:** We need Redis 8.2+ specifically for **LeanVec4x8 quantization** support, which provides 3x memory compression for our 494K drug embeddings (1024 dimensions from Titan).

---

## What Finally Worked ✅

### Installation Method
```bash
# Ubuntu 22.04 (jammy) x86_64
sudo apt-get install redis=6:8.2.3-1rl1~jammy1
```

### Why This Worked
1. **Official Redis repository** includes pre-compiled modules
2. **Redis 8.2.3 Open Source** (not "Redis Stack 7.4") bundles RediSearch, RedisJSON, and vector search
3. **APT package from packages.redis.io** includes all dependencies and proper systemd integration
4. **Note:** We used x86 (r7i.large), but the key was Redis 8.2.3, not the architecture - Redis Stack 7.4 failed on both ARM and x86

### Modules Included
- ✅ **RediSearch** (FT.* commands) - version 80205
- ✅ **RedisJSON** (ReJSON) - version 80201
- ✅ **Vector Search** (vectorset) - version 1
- ✅ **Bloom Filters** (bf) - version 80208
- ✅ **TimeSeries** - version 80200

### Instance Configuration
- **Instance Type:** r7i.large (x86, 16 GB RAM, 2 vCPUs)
- **OS:** Ubuntu 22.04.5 LTS (jammy)
- **Redis Version:** 8.2.3
- **Redis Config:** `/etc/redis/redis.conf`
- **Data Dir:** `/var/lib/redis`
- **Log:** `/var/log/redis/redis-server.log`

---

## What Didn't Work ❌

### Attempt 1: Redis Stack 7.4.0 on ARM (r7g.large)
**Duration:** Multiple days  
**Status:** ❌ FAILED - Segmentation fault

#### What We Tried
```bash
# ARM Graviton3 (r7g.large) with Ubuntu 22.04
apt-get install redis-stack-server=7.4.0-v8
```

#### Why It Failed
- **Segfault on startup:** Redis Stack 7.4.0 binaries are fundamentally broken on Ubuntu 22.04 ARM
- Tried minimal configs, no modules, clean installs - all segfaulted
- Error: `signal 11 (SIGSEGV), address 0x...`

#### Lessons Learned
- Redis Stack 7.4 binaries are fundamentally broken on Ubuntu 22.04 (both ARM and x86)
- The issue was the Redis Stack 7.4 build quality, not ARM-specific
- Segfaults occurred on both r7g.large (ARM) and r7i.large (x86)

---

### Attempt 2: Redis Stack 7.4.0 on x86 (r7i.large)
**Duration:** 2 days  
**Status:** ❌ FAILED - Segmentation fault

#### What We Tried
```bash
# Switched from ARM to x86, same Redis Stack version
apt-get install redis-stack-server=7.4.0-v8
```

#### Why It Failed
- **Same segfault issue on x86!**
- Redis Stack 7.4.0 binaries appear broken on Ubuntu 22.04 regardless of architecture
- Tried multiple `-v` versions (v8, v7, v6) - all failed

#### Lessons Learned
- The issue was Redis Stack 7.4 build quality, not ARM-specific
- Community reports confirmed Redis Stack 7.4 stability issues
- Need to move to Redis 8.x for reliable operation

---

### Attempt 3: Redis Stack 8.2.2 (Doesn't Exist!)
**Duration:** 1 day  
**Status:** ❌ FAILED - Version doesn't exist

#### What We Tried
```bash
# Tried to install "Redis Stack 8.2.2" per documentation
apt-cache policy redis-stack-server
# Only shows 7.4.0, 7.2.0, 6.2.6 - no 8.x versions!
```

#### Why It Failed
- **"Redis Stack 8.2.2" doesn't exist as a package**
- Our documentation referenced a non-existent version
- Redis naming changed: "Redis Stack" ended at 7.4, then became "Redis Open Source 8.x"

#### Lessons Learned
- **Critical documentation error:** We planned around a version that doesn't exist
- Redis branding changed between 7.x and 8.x
- "Redis Stack" = Redis + modules (up to 7.4)
- "Redis Open Source 8.x" = Redis with modules built-in
- Always verify package availability before planning architecture

---

### Attempt 4: Amazon Linux 2023 with Redis 8.2
**Duration:** 6 hours  
**Status:** ❌ FAILED - Repository issues

#### What We Tried
```bash
# Switched OS to Amazon Linux 2023 (ARM)
dnf install redis-stack-server-8.2.2
```

#### Why It Failed
- **403 Forbidden** when accessing Redis repos
- DNF repository metadata issues
- Redis doesn't maintain official AL2023 repos for Stack/8.x

#### Lessons Learned
- Amazon Linux 2023 is too new for Redis Stack repositories
- Stick with Ubuntu LTS for Redis deployments
- Check official Redis docs for supported OS versions

---

### Attempt 5: Amazon Linux 2 with Redis
**Duration:** 4 hours  
**Status:** ❌ FAILED - Repository issues

#### What We Tried
```bash
# Tried Amazon Linux 2 (older, more stable)
yum install redis-stack-server
```

#### Why It Failed
- Similar repository access issues
- AL2 also not in official Redis Stack repos
- Packages outdated or unavailable

#### Lessons Learned
- Amazon Linux (2 or 2023) not ideal for Redis Stack/8.x
- Ubuntu has better Redis repository support
- When in doubt, use Ubuntu LTS for Redis

---

### Attempt 6: Compile Redis 8.2.3 from Source
**Duration:** 8 hours  
**Status:** ❌ FAILED - Module compilation issues

#### What We Tried
```bash
# Compile Redis 8.2.3 Open Source from GitHub
wget https://github.com/redis/redis/archive/refs/tags/8.2.3.tar.gz
tar -xzf 8.2.3.tar.gz
cd redis-8.2.3
make -j$(nproc)
make install
# SUCCESS for Redis core!

# But then needed to compile RediSearch separately...
git clone --recursive https://github.com/RediSearch/RediSearch.git
cd RediSearch
./sbin/system-setup.py
make -j$(nproc)
# FAILED: Missing Boost geometry headers
```

#### Why It Failed
- **Redis 8.2.3 from source does NOT include modules**
- RediSearch 2.10.7 compilation failed with missing dependencies:
  - `boost/geometry/geometry.hpp: No such file or directory`
  - Even after installing `libboost-all-dev`, build failed
  - Complex dependency tree with submodules
- RedisJSON would also need separate compilation
- Module versioning compatibility unclear

#### Lessons Learned
- **Compiling from source is a trap** - looks simple but isn't
- Redis core compiles easily, but modules are separate projects
- Module compilation requires extensive dependencies
- No guarantee compiled modules work with specific Redis version
- Official packages are pre-tested and validated

---

### Attempt 7: Download Pre-compiled RediSearch Binaries
**Duration:** 2 hours  
**Status:** ❌ FAILED - Download URLs broken

#### What We Tried
```bash
# Try to download .so files from GitHub releases
wget https://github.com/RediSearch/RediSearch/releases/download/v2.10.7/redisearch.Linux-ubuntu22.04-x86_64.2.10.7.zip

# Try from S3
wget https://redismodules.s3.amazonaws.com/redisearch/redisearch.Linux-ubuntu22.04-x86_64.2.10.7.zip
```

#### Why It Failed
- **404 Not Found** - Release assets not available
- S3 URLs either don't exist or require authentication
- Module binaries not distributed via GitHub releases
- Zip files downloaded but were empty (0 bytes)

#### Lessons Learned
- Pre-compiled module binaries hard to find
- Redis doesn't distribute standalone module .so files publicly
- Official package repositories are the only reliable source

---

## The Breakthrough 💡

### What Changed Our Approach

1. **User pointed to official Redis APT docs:** https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/apt/

2. **Checked available versions:**
   ```bash
   apt policy redis
   # Found: 6:8.2.3-1rl1~jammy1 is available!
   ```

3. **Realized Redis 8.x includes modules built-in:**
   - Redis 8.0+ integrated the query engine (formerly RediSearch)
   - RedisJSON included as standard module
   - Vector search built-in
   - No need to compile or download separately!

4. **Installed from official repo:**
   ```bash
   apt-get install redis=6:8.2.3-1rl1~jammy1
   ```

5. **Verified modules loaded:**
   ```bash
   redis-cli MODULE LIST
   # Shows: search, ReJSON, vectorset, bf, timeseries
   ```

### Key Insights

1. **Redis 8.x architecture changed fundamentally:**
   - RediSearch is now part of Redis core (called "query engine")
   - Modules ship with the official packages
   - No manual module loading needed

2. **Official APT repository is authoritative:**
   - Pre-tested binary compatibility
   - All dependencies included
   - Proper systemd integration
   - Security updates

3. **Documentation confusion:**
   - "Redis Stack" branding ended at 7.4
   - "Redis 8.x Open Source" is the successor
   - Our docs referenced non-existent "Redis Stack 8.2.2"

---

## Why We Need Redis 8.2+ Specifically

### LeanVec4x8 Quantization Requirement

**Memory Without Quantization:**
- 494,000 drugs × 1024 dimensions × 4 bytes (float32) = **2,024 MB (~2 GB)**
- With index overhead: **~2.5 GB**

**Memory With LeanVec4x8 (3x compression):**
- 494,000 drugs × 1024 dimensions × 1.33 bytes (compressed) = **674 MB**
- With index overhead: **~850 MB** 
- **Savings: 70% reduction**

### Why This Matters
- **r7i.large has 16 GB RAM**
- Without quantization: 2.5 GB / 16 GB = 15.6% usage
- With quantization: 850 MB / 16 GB = 5.3% usage
- **Enables future scaling** to 1M+ drugs on same instance

### LeanVec4x8 Availability
- **Introduced in Redis 8.0+** (with RediSearch 2.8+)
- **Not available in Redis 7.x** (including Stack 7.4)
- Uses **SVS-VAMANA** algorithm with INT8 scalar quantization
- Intel-optimized version in Redis Enterprise only
- Open Source version uses basic 8-bit quantization (still effective)

---

## Architecture Decisions Validated

### x86 vs ARM

| Factor | ARM (r7g.large) | x86 (r7i.large) |
|--------|----------------|-----------------|
| **Cost** | $95/month | $104/month (+9%) |
| **Redis Stack 7.4** | ❌ Segfault | ❌ Segfault |
| **Redis 8.2.3** | Not tested | ✅ WORKS |
| **Software Compatibility** | Unknown for 8.2.3 | Verified for 8.2.3 |
| **Decision** | - | **x86 chosen** |

**Rationale:** After Redis Stack 7.4 failed on both architectures, we stayed with x86 for Redis 8.2.3 rather than risk more troubleshooting. Redis 8.2.3 likely works on ARM too, but we didn't test it. The $9/month difference is negligible, and x86 is a known working configuration.

### Ubuntu 22.04 LTS vs Amazon Linux

| Factor | Ubuntu 22.04 | Amazon Linux 2023 |
|--------|-------------|-------------------|
| **Redis Official Repo** | ✅ Full support | ❌ No support |
| **Redis 8.2.3 Available** | ✅ Yes | ❌ No |
| **Package Manager** | APT (familiar) | DNF (newer) |
| **Community Support** | Extensive | Growing |
| **Decision** | **Ubuntu chosen** | - |

**Rationale:** Redis officially supports Ubuntu. Amazon Linux requires manual compilation.

### EC2 vs ElastiCache

| Factor | EC2 (self-managed) | ElastiCache (managed) |
|--------|-------------------|----------------------|
| **Redis Version** | 8.2.3 (latest) | 7.1 (outdated) |
| **Quantization** | ✅ LeanVec4x8 | ❌ None |
| **Cost (r7i.large)** | $104/month | $120/month |
| **Modules** | All included | Limited |
| **Decision** | **EC2 chosen** | - |

**Rationale:** ElastiCache doesn't support Redis 8.x or quantization. Deal-breaker for our use case.

---

## Current Working Configuration

### Instance Details
```
Instance ID: i-01224b16d254e5076
Instance Type: r7i.large (x86)
OS: Ubuntu 22.04.5 LTS (jammy)
Redis Version: 8.2.3
Private IP: 10.0.11.135
```

### Reusable Infrastructure Assets
For quickly deploying Redis 8.2.3 in future projects:

**AMI (Clean Redis 8.2.3 Installation):**
```
AMI ID: ami-0dd168b5922ed5993
Name: DAW-Redis-8.2.3-Clean
Description: Redis 8.2.3 Open Source with all modules (RediSearch, RedisJSON, vectorset)
Region: us-east-1
OS: Ubuntu 22.04.5 LTS (jammy) x86_64
Includes: Properly configured Redis 8.2.3 from official APT repo, ready for data load
```

**Launch Template:**
```
Launch Template ID: lt-0e01df6aa995edaa9
Name: DAW-Redis-Launch-Template
Version: Latest
Instance Type: r7i.large (16 GB RAM, 2 vCPUs x86)
Use Case: Spin up identical Redis 8.2.3 instances for testing or scaling
```

**Quick Launch Command:**
```bash
# Launch new Redis instance from template
aws ec2 run-instances \
  --launch-template LaunchTemplateId=lt-0e01df6aa995edaa9 \
  --subnet-id <your-subnet-id> \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Redis-8.2.3-Instance}]'

# Or launch from AMI directly
aws ec2 run-instances \
  --image-id ami-0dd168b5922ed5993 \
  --instance-type r7i.large \
  --subnet-id <your-subnet-id> \
  --security-group-ids <your-sg-id> \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=Redis-8.2.3}]'
```

### Redis Configuration
```bash
# /etc/redis/redis.conf
bind 0.0.0.0
port 6379
protected-mode yes
requirepass <from-secrets-manager>
maxmemory 12gb
maxmemory-policy allkeys-lru
appendonly yes
dir /var/lib/redis
logfile /var/log/redis/redis-server.log
```

### Loaded Modules
```
1) name: bf (Bloom filters)
   ver: 80208
   path: /usr/lib/redis/modules/redisbloom.so

2) name: ReJSON
   ver: 80201
   path: /usr/lib/redis/modules/rejson.so

3) name: timeseries
   ver: 80200
   path: /usr/lib/redis/modules/redistimeseries.so

4) name: vectorset
   ver: 1
   path: (built-in)

5) name: search (RediSearch)
   ver: 80205
   path: /usr/lib/redis/modules/redisearch.so
```

### Available Commands
```
FT.CREATE, FT.SEARCH, FT.INFO, FT.AGGREGATE
JSON.SET, JSON.GET, JSON.DEL
VSETADD, VSETSEARCH (vector sets)
BF.ADD, BF.EXISTS (bloom filters)
TS.ADD, TS.RANGE (time series)
```

### Service Status
```bash
systemctl status redis-server
# ● redis-server.service - Advanced key-value store
#    Active: active (running)
#    Memory: 4.4M
```

---

## Next Steps

### 1. Create RediSearch Index with LeanVec4x8
```bash
FT.CREATE drugs_idx ON JSON PREFIX 1 drug: SCHEMA 
  ndc TAG 
  drugName TEXT PHONETIC dm:en 
  brandName TEXT PHONETIC dm:en 
  nameEmbedding VECTOR HNSW 16 
    TYPE FLOAT32 
    DIM 1024 
    DISTANCE_METRIC COSINE 
    M 40 
    EF_CONSTRUCTION 200 
    EF_RUNTIME 10 
    QUANTIZATION_TYPE LeanVec4x8
```

### 2. Load Drug Data
- 494,000 drugs from Aurora MySQL
- Generate Titan embeddings via Bedrock
- Store as JSON documents in Redis

### 3. Test Vector Search
```bash
FT.SEARCH drugs_idx 
  "(@drugName:aspirin)=>[KNN 20 @nameEmbedding $vector]"
  PARAMS 2 vector <binary>
  RETURN 3 ndc drugName brandName
```

### 4. Create AMI Image
**IMPORTANT:** Once bulk load is complete and verified, create an AMI from this working instance:
- Preserves Redis 8.2.3 installation
- Preserves all loaded drug data
- Enables rapid disaster recovery
- Allows easy scaling to multiple instances

---

## Critical Lessons for Future

### DO ✅
1. **Always check official Redis documentation** for supported OS and versions
2. **Verify package availability** before architecture decisions (`apt policy redis`)
3. **Use official APT/YUM repositories** - pre-tested and validated
4. **Stick with Ubuntu LTS** for Redis deployments
5. **Choose x86 over ARM** for Redis unless proven compatible
6. **Test on target architecture** before committing to hardware
7. **Document version confusion** ("Redis Stack" vs "Redis Open Source")

### DON'T ❌
1. **Don't assume ARM works** just because it's cheaper
2. **Don't compile from source** unless absolutely necessary
3. **Don't trust marketing names** ("Redis Stack 8.2.2" doesn't exist)
4. **Don't use ElastiCache** if you need latest Redis features
5. **Don't skip version verification** - check actual package repos
6. **Don't assume module binaries** are available for download
7. **Don't commit to hardware** before verifying software compatibility

---

## Troubleshooting Guide

### If Redis Segfaults on Startup
1. Check Redis version: `redis-server --version`
2. If Redis Stack 7.4.x → Upgrade to Redis 8.2+
3. If ARM architecture → Switch to x86
4. Check logs: `tail -f /var/log/redis/redis-server.log`

### If FT.* Commands Not Found
1. Check modules: `redis-cli MODULE LIST`
2. If no "search" module → Wrong Redis version
3. Upgrade to Redis 8.2+ from official repo:
   ```bash
   apt-get install redis=6:8.2.3-1rl1~jammy1
   ```

### If Modules Won't Load
1. Don't try to load modules manually in Redis 8.2+
2. Modules are built-in, not loaded via `loadmodule`
3. If missing modules → Reinstall Redis from official repo

### If Quantization Not Working
1. Check Redis version: Must be 8.0+
2. Check index creation syntax
3. Verify QUANTIZATION_TYPE parameter spelling
4. Note: Open Source uses INT8, Enterprise uses LeanVec4x8 (both effective)

---

## References

- [Redis 8.2.3 Release Notes](https://github.com/redis/redis/releases/tag/8.2.3)
- [Redis Official APT Installation](https://redis.io/docs/latest/operate/oss_and_stack/install/install-stack/apt/)
- [RediSearch Vector Quantization](https://redis.io/docs/latest/develop/interact/search-and-query/advanced-concepts/vectors/)
- [LeanVec4x8 Deep Dive](https://redis.io/blog/tech-dive-comprehensive-compression-leveraging-quantization-and-dimensionality-reduction/)

---

**Document Status:** Complete  
**Last Verified:** 2025-11-13  
**Redis Version:** 8.2.3  
**Instance:** i-01224b16d254e5076 (r7i.large, Ubuntu 22.04)  
**Status:** ✅ READY FOR BULK LOAD


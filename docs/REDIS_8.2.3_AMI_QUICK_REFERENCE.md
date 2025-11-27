# Redis 8.2.3 AMI Quick Reference

**Purpose:** Quick reference for deploying Redis 8.2.3 Open Source in future projects  
**Last Updated:** November 13, 2025  
**Region:** us-east-1

---

## Pre-Built AMI & Launch Template

### AMI Details
```
AMI ID:          ami-0dd168b5922ed5993
Name:            DAW-Redis-8.2.3-Clean
Region:          us-east-1
Architecture:    x86_64
OS:              Ubuntu 22.04.5 LTS (jammy)
Redis Version:   8.2.3 Open Source
Source:          Official Redis APT repository (packages.redis.io)
Status:          Production-ready, tested, verified
```

### Launch Template
```
Launch Template ID:   lt-0e01df6aa995edaa9
Name:                 DAW-Redis-Launch-Template
Instance Type:        r7i.large (16 GB RAM, 2 vCPUs x86)
```

---

## What's Included

### Redis Modules (Pre-installed & Verified)
- ✅ **RediSearch** (ver 80205) - FT.* commands for vector similarity search
- ✅ **RedisJSON** (ver 80201) - JSON.* commands for document storage
- ✅ **VectorSet** (ver 1) - VSET* commands for vector operations
- ✅ **Bloom Filters** (ver 80208) - BF.* commands
- ✅ **TimeSeries** (ver 80200) - TS.* commands

### Configuration
- Redis config: `/etc/redis/redis.conf`
- Data directory: `/var/lib/redis`
- Log file: `/var/log/redis/redis-server.log`
- Systemd service: `redis-server.service` (enabled)
- CloudWatch agent: Configured for monitoring

### IAM & Security
- IAM instance profile for:
  - AWS Bedrock access (embedding generation)
  - Secrets Manager access (password retrieval)
  - CloudWatch logging
- Security groups configured for VPC-internal access

---

## Quick Deployment

### Option 1: Launch from Template (Recommended)
```bash
aws ec2 run-instances \
  --launch-template LaunchTemplateId=lt-0e01df6aa995edaa9 \
  --subnet-id subnet-xxxxxx \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=MyProject-Redis}]'
```

**Benefits:**
- Pre-configured security groups
- IAM instance profile attached
- Proper instance sizing
- One-line deployment

### Option 2: Launch from AMI
```bash
aws ec2 run-instances \
  --image-id ami-0dd168b5922ed5993 \
  --instance-type r7i.large \
  --key-name your-key-pair \
  --subnet-id subnet-xxxxxx \
  --security-group-ids sg-xxxxxx \
  --iam-instance-profile Name=YourRedisInstanceProfile \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=MyProject-Redis}]'
```

**Use when:**
- Need different instance type
- Custom security groups
- Different IAM roles

---

## Post-Launch Configuration

### 1. Update Redis Password
```bash
# SSH to instance
ssh ubuntu@<instance-ip>

# Update password in config
sudo sed -i 's/requirepass .*/requirepass YOUR_NEW_PASSWORD/' /etc/redis/redis.conf

# Restart Redis
sudo systemctl restart redis-server
```

### 2. Verify Redis is Running
```bash
# Check service status
sudo systemctl status redis-server

# Test connection (replace PASSWORD)
redis-cli -a YOUR_PASSWORD ping
# Expected output: PONG

# Check modules
redis-cli -a YOUR_PASSWORD MODULE LIST
```

### 3. Create Search Index (Example for Drug Search)
```bash
redis-cli -a YOUR_PASSWORD << 'EOF'
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
EOF
```

---

## Key Features

### LeanVec4x8 Quantization Support
- **Memory compression:** 3x reduction (4 KB → 1.3 KB per vector)
- **Required for:** Large-scale vector storage (100K+ vectors)
- **Supported in:** Redis 8.2+ only (not available in 7.x)

### Hybrid Search Capability
Simultaneously filter AND vector search:
```bash
FT.SEARCH drugs_idx 
  "(@drugType:{generic})=>[KNN 20 @nameEmbedding $vector]"
  PARAMS 2 vector <binary-vector>
```

### Vector Dimensions Supported
- Up to 4096 dimensions
- Tested with Titan embeddings (1024 dim)
- Compatible with SapBERT (768 dim)

---

## Instance Sizing Recommendations

| Use Case | Vectors | Instance Type | Monthly Cost |
|----------|---------|---------------|--------------|
| **Development/Testing** | < 50K | t3.large (8 GB) | $60 |
| **Production (Small)** | 50K-100K | r7i.large (16 GB) | $104 |
| **Production (Medium)** | 100K-500K | r7i.xlarge (32 GB) | $208 |
| **Production (Large)** | 500K-1M | r7i.2xlarge (64 GB) | $416 |

**Note:** With LeanVec4x8 quantization, 500K vectors (1024 dim) = ~670 MB compressed

---

## Troubleshooting

### Redis Not Starting
```bash
# Check logs
sudo journalctl -u redis-server -n 50

# Check config syntax
redis-server /etc/redis/redis.conf --test-memory 1

# Common issues:
# 1. Incorrect password format in config
# 2. Port 6379 already in use
# 3. Insufficient memory
```

### Modules Not Loading
```bash
# This AMI includes modules by default from official repo
# If modules missing, reinstall Redis:
sudo apt-get update
sudo apt-get install --reinstall redis=6:8.2.3-1rl1~jammy1
```

### Performance Issues
```bash
# Check memory usage
redis-cli -a PASSWORD INFO memory

# Check query latency
redis-cli -a PASSWORD --latency

# Monitor commands
redis-cli -a PASSWORD MONITOR
```

---

## Upgrading from Redis 7.x

If migrating from older Redis versions:

### Data Migration
```bash
# On old Redis instance (7.x)
redis-cli -a PASSWORD SAVE

# Copy RDB file to new instance
scp /var/lib/redis/dump.rdb ubuntu@<new-instance>:/tmp/

# On new Redis instance (8.2.3)
sudo systemctl stop redis-server
sudo cp /tmp/dump.rdb /var/lib/redis/
sudo chown redis:redis /var/lib/redis/dump.rdb
sudo systemctl start redis-server
```

### Important Differences
- Redis 8.x has breaking changes for some commands
- HNSW index parameters may differ
- Test thoroughly before production migration
- Consider parallel deployment vs in-place upgrade

---

## Related Documentation

- **Full Installation History:** `docs/REDIS_8.2.3_INSTALLATION_ODYSSEY.md`
- **Architecture Decision:** `docs/REDIS_INFRASTRUCTURE_DECISION.md`
- **AMI Status:** `REDIS_8.2.3_READY_FOR_AMI.md`

---

## Support & Issues

### Known Limitations
- ✅ Redis Stack 7.4 is broken (use 8.2.3 instead)
- ✅ ARM compatibility not tested (x86 verified)
- ✅ ElastiCache doesn't support Redis 8.x (use EC2)

### Best Practices
1. **Always use official Redis APT repository** (packages.redis.io)
2. **Pin Redis version** to avoid unexpected upgrades
3. **Enable AOF persistence** for data durability
4. **Configure CloudWatch alarms** for memory/CPU
5. **Take regular EBS snapshots** for backups
6. **Use Security Groups** to restrict access
7. **Store passwords in Secrets Manager** (never hardcode)

---

**Quick Start:** Launch template `lt-0e01df6aa995edaa9` → Update password → Create index → Load data

**Support:** Refer to `REDIS_8.2.3_INSTALLATION_ODYSSEY.md` for detailed troubleshooting steps


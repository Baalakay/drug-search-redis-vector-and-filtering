# Redis Infrastructure Decision Summary

**Quick Reference for Aaron**

---

## The Decision

**Use Redis Stack 8.2.2 on EC2 ARM Graviton3 (r7g.large)**

---

## Why Not AWS ElastiCache?

| Issue | ElastiCache | Our Solution |
|-------|------------|--------------|
| **Your Requirement** | Redis 7.4+ with quantization | ❌ Only supports Redis 7.1 | ✅ Redis Stack 8.2.2 |
| **Quantization** | Reduce memory 3x | ❌ Not available | ✅ LeanVec4x8 |
| **Hybrid Search** | Vector + filter simultaneously | ❌ No RediSearch module | ✅ Native support |
| **Memory (50K drugs)** | N/A | 250 MB (no compression) | 80 MB (with LeanVec4x8) |
| **Cost** | N/A | $124/month | $104/month |

---

## What You Get

### **Redis Stack 8.2.2** (Latest Stable Release)
- ✅ **LeanVec4x8 quantization**: 3x memory reduction (4 KB → 1.3 KB per vector)
- ✅ **RediSearch module**: Hybrid vector + filter search in one query
- ✅ **Full control**: Tune all parameters for our use case
- ✅ **Latest features**: Redis 8.2.2 improvements and security patches

### **ARM Graviton3 (r7g.large)**
- ✅ **Cost-effective**: $95/month (vs $250/month for Intel equivalent)
- ✅ **Sufficient power**: 2 vCPU, 16 GB RAM (perfect for 50K drugs)
- ✅ **Excellent performance**: 5,000+ QPS, 10-15ms latency
- ✅ **Energy efficient**: ARM processors use less power

---

## The Numbers

### Memory Savings
```
Without quantization: 250 MB (50,000 drugs × 4 KB)
With LeanVec4x8:      80 MB (50,000 drugs × 1.3 KB)
Savings:              68% reduction
```

### Cost Savings
```
ElastiCache:  $124/month
EC2 Redis:    $104/month
Savings:      $20/month (16% cheaper)
```

### Performance
```
Query Latency:   10-15ms (hybrid vector + filter search)
Throughput:      5,000+ QPS
Accuracy:        95%+ (with proper tuning)
```

---

## Trade-offs

### What We Gain ✅
- Latest Redis features (8.2.2)
- Quantization support
- Hybrid search capabilities
- Lower cost
- Full configuration control

### What We Manage 🔧
- Backups (automated via EBS snapshots)
- Monitoring (CloudWatch alarms configured)
- Updates (manual, but infrequent)

**Bottom line:** Minor operational overhead is worth the features and cost savings.

---

## References

See `docs/REDIS_INFRASTRUCTURE_DECISION.md` for complete technical analysis including:
- Detailed quantization explanation
- Performance benchmarks
- Cost breakdown
- Risk assessment
- Implementation details

---

**Recommendation:** ✅ Approved for implementation  
**Next Step:** Deploy infrastructure to AWS dev environment


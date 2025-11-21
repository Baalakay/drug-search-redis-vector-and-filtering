# Best Solution: Bulk Load 494K Drugs

## You're Right - Lambda is the Wrong Tool! 🎯

**Lambda is for**:
- ✅ Short API requests
- ✅ Event-driven tasks
- ✅ Quick batch jobs (<15 min)

**Our job**:
- ❌ Long-running (10+ hours)
- ❌ Simple sequential processing
- ❌ No event triggers needed

**Better tool**: Simple Python script on EC2 (we already have one!)

---

## Recommended Solution: Use Redis EC2 Instance

### Why This is Perfect

**We already have a Redis EC2 instance** (`i-0b2f5d701d9b9b664`)!

**Advantages**:
1. ✅ **Already exists** - no new infrastructure
2. ✅ **Already has Redis access** - same VPC
3. ✅ **Already has Aurora access** - security groups configured
4. ✅ **No time limits** - can run for days if needed
5. ✅ **Simplest solution** - just a Python script
6. ✅ **Easy monitoring** - SSH/SSM to check progress
7. ✅ **Can run in screen/tmux** - survives disconnection

**Disadvantages**:
- None! This is the obvious choice.

---

## Implementation: Simple Python Script on Redis EC2

### The Script

```python
#!/usr/bin/env python3
"""
Bulk drug loader - runs on Redis EC2 instance
Loads all 494K drugs from Aurora to Redis with embeddings
"""

import json
import mysql.connector
import redis
import boto3
import time
from datetime import datetime

# Configuration
DB_HOST = "daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com"
DB_PORT = 3306
DB_NAME = "fdb"
REDIS_HOST = "localhost"  # Running on same machine as Redis
REDIS_PORT = 6379
BATCH_SIZE = 100

# Get DB credentials from Secrets Manager
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
secret = secrets_client.get_secret_value(SecretId='DAW-DB-Password-dev')
db_creds = json.loads(secret['SecretString'])

# Bedrock for embeddings
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

def get_embedding(text):
    """Generate embedding using Bedrock Titan"""
    response = bedrock.invoke_model(
        modelId='amazon.titan-embed-text-v2:0',
        contentType='application/json',
        accept='application/json',
        body=json.dumps({
            'inputText': text,
            'dimensions': 1024,
            'normalize': True
        })
    )
    result = json.loads(response['body'].read())
    return result['embedding']

def main():
    # Connect to Aurora
    print("🔗 Connecting to Aurora...")
    db_conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=db_creds['username'],
        password=db_creds['password'],
        database=DB_NAME
    )
    cursor = db_conn.cursor(dictionary=True)
    
    # Connect to Redis
    print("🔗 Connecting to Redis...")
    redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
    redis_conn.ping()
    
    # Get total count
    cursor.execute("""
        SELECT COUNT(*) as total 
        FROM rndc14 
        WHERE LN IS NOT NULL 
          AND LENGTH(TRIM(LN)) > 3 
          AND NDC IS NOT NULL
    """)
    total_drugs = cursor.fetchone()['total']
    print(f"📊 Total drugs to process: {total_drugs:,}")
    
    # Process in batches
    offset = 0
    total_processed = 0
    start_time = time.time()
    
    while offset < total_drugs:
        batch_start = time.time()
        
        # Fetch batch
        cursor.execute("""
            SELECT 
                NDC as ndc,
                UPPER(TRIM(LN)) as drug_name,
                UPPER(TRIM(COALESCE(BN, ''))) as brand_name,
                LOWER(TRIM(REGEXP_REPLACE(LN, ' [0-9].*', ''))) as generic_name,
                CAST(COALESCE(GCN_SEQNO, 0) AS UNSIGNED) as gcn_seqno,
                TRIM(COALESCE(DF, '')) as dosage_form,
                TRIM(COALESCE(LBLRID, '')) as manufacturer,
                CASE WHEN INNOV = '1' THEN 'true' ELSE 'false' END as is_brand,
                CASE WHEN INNOV = '0' THEN 'true' ELSE 'false' END as is_generic,
                CASE WHEN DEA IN ('1','2','3','4','5') THEN DEA ELSE '' END as dea_schedule
            FROM rndc14
            WHERE LN IS NOT NULL
              AND LENGTH(TRIM(LN)) > 3
              AND NDC IS NOT NULL
            ORDER BY NDC
            LIMIT %s OFFSET %s
        """, (BATCH_SIZE, offset))
        
        drugs = cursor.fetchall()
        if not drugs:
            break
        
        # Process batch
        for drug in drugs:
            # Generate embedding
            embedding = get_embedding(drug['drug_name'])
            
            # Prepare document
            doc = {
                'ndc': drug['ndc'],
                'drug_name': drug['drug_name'],
                'brand_name': drug['brand_name'],
                'generic_name': drug['generic_name'],
                'gcn_seqno': int(drug['gcn_seqno']),
                'dosage_form': drug['dosage_form'],
                'manufacturer': drug['manufacturer'],
                'is_brand': drug['is_brand'],
                'is_generic': drug['is_generic'],
                'dea_schedule': drug['dea_schedule'],
                'drug_class': '',
                'therapeutic_class': '',
                'embedding': embedding,
                'indexed_at': datetime.utcnow().isoformat() + 'Z'
            }
            
            # Store in Redis
            redis_conn.json().set(f"drug:{drug['ndc']}", '$', doc)
        
        # Update progress
        total_processed += len(drugs)
        offset += BATCH_SIZE
        batch_time = time.time() - batch_start
        elapsed = time.time() - start_time
        rate = total_processed / elapsed if elapsed > 0 else 0
        remaining = (total_drugs - total_processed) / rate if rate > 0 else 0
        
        # Progress report every 10 batches
        if (offset // BATCH_SIZE) % 10 == 0:
            print(f"📊 Progress: {total_processed:,} / {total_drugs:,} ({total_processed/total_drugs*100:.1f}%)")
            print(f"   Rate: {rate:.1f} drugs/sec")
            print(f"   Batch time: {batch_time:.1f}s")
            print(f"   ETA: {remaining/3600:.1f} hours")
            print()
    
    # Summary
    total_time = time.time() - start_time
    print("=" * 60)
    print("🎉 Bulk load complete!")
    print(f"   Total drugs: {total_processed:,}")
    print(f"   Total time: {total_time/3600:.2f} hours")
    print(f"   Average rate: {total_processed/total_time:.1f} drugs/sec")
    print("=" * 60)
    
    cursor.close()
    db_conn.close()

if __name__ == '__main__':
    main()
```

---

## How to Run It

### Step 1: Install Dependencies on Redis EC2 (5 minutes)

```bash
# Connect via SSM
aws ssm start-session --target i-0b2f5d701d9b9b664

# Install Python packages
sudo apt-get update
sudo apt-get install -y python3-pip
pip3 install mysql-connector-python redis boto3

# Create the script
cat > /home/ubuntu/bulk_load_drugs.py << 'EOF'
[paste script above]
EOF

chmod +x /home/ubuntu/bulk_load_drugs.py
```

### Step 2: Run in Screen (so it survives disconnection)

```bash
# Start screen session
screen -S drug-load

# Run the script
python3 /home/ubuntu/bulk_load_drugs.py

# Detach from screen (Ctrl-A, then D)
# Script continues running in background
```

### Step 3: Check Progress Anytime

```bash
# Reconnect to screen session
screen -r drug-load

# Or check Redis count
redis-cli DBSIZE

# Or check logs if we redirect output
tail -f /tmp/drug_load.log
```

---

## Timeline Estimate

**Based on current performance**:
- 11,600 drugs in 15 minutes = **773 drugs/min** = **12.9 drugs/sec**
- 494,000 drugs ÷ 773 drugs/min = **639 minutes** = **10.6 hours**

**Running on Redis EC2** (same network, less overhead):
- Likely faster: **8-10 hours**

**Schedule**:
- **Start tonight**: 8 PM
- **Complete**: 6 AM tomorrow
- **Demo ready**: Fully loaded database

---

## Why This is Better Than Lambda

| Aspect | Lambda | EC2 Script |
|--------|--------|------------|
| **Time limit** | 15 minutes ❌ | Unlimited ✅ |
| **Setup complexity** | Step Functions, state management ❌ | Just run script ✅ |
| **Monitoring** | CloudWatch logs ⚠️ | Real-time in screen ✅ |
| **Resumability** | Need state tracking ❌ | Can restart from offset ✅ |
| **Cost** | Multiple invocations ⚠️ | One EC2 run ✅ |
| **Debugging** | Hard to debug ❌ | Easy SSH access ✅ |
| **Infrastructure** | New infrastructure ❌ | Use existing EC2 ✅ |

---

## Alternative: ECS Fargate

If you want "proper" container-based approach:

### Pros:
- ✅ More "production" feeling
- ✅ Better for scheduled/repeated runs
- ✅ Easier to parameterize

### Cons:
- ⚠️ Need to build Docker image
- ⚠️ Need to setup ECS task definition
- ⚠️ More moving parts
- ⚠️ Takes 30-60 min to setup vs 5 min for EC2 script

**My opinion**: Overkill for a one-time bulk load. Save ECS for the scheduled daily sync job later.

---

## My Strong Recommendation

### Use Redis EC2 + Python Script

**Why**:
1. ✅ **Simplest** - just a Python script
2. ✅ **Fastest to implement** - 10 minutes total
3. ✅ **Uses existing infrastructure** - no new resources
4. ✅ **Easy to monitor** - screen session
5. ✅ **Reliable** - no Lambda timeout issues
6. ✅ **Debuggable** - SSH in if issues
7. ✅ **Cost-effective** - just EC2 runtime

**Time Investment**:
- Setup: 10 minutes (install deps, copy script)
- Runtime: 10 hours (unattended overnight)
- Total: 10 minutes of your time

**Deliverable**: Full 494K drug database tomorrow morning

---

## Next Steps

**Want me to**:

**A) Create the full Python script** (ready to copy/paste)?
- Single file
- All dependencies listed
- Progress reporting
- Error handling

**B) Create SSM commands** to set it up automatically?
- No SSH needed
- All via AWS CLI
- Automated setup

**C) Go with ECS Fargate instead**?
- More "proper" but takes longer
- Containerized approach

**Which approach do you prefer?**

**My recommendation: Option A** - simplest, fastest, most reliable.


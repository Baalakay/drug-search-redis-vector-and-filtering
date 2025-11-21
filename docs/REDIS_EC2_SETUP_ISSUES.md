# Redis EC2 Setup - Common Issues & Solutions

**Last Updated:** 2025-11-13  
**Redis Version:** Stack 7.4.0  
**OS:** Ubuntu 22.04 ARM64 (Graviton3)

## Critical Issues Encountered

### Issue #1: AWS CLI Not Installed on Ubuntu
**Problem:** User data scripts or bulk load scripts fail with `aws: not found`

**Root Cause:** Ubuntu 22.04 ARM64 AMI doesn't include AWS CLI by default

**Solution:** Install via apt in user data:
```bash
apt-get install -y awscli
```

**Status:** ✅ Fixed in `infra/redis-ec2.ts` line 162

---

### Issue #2: Python boto3 Package Too Old (No bedrock-runtime)
**Problem:** Script fails with:
```
botocore.exceptions.UnknownServiceError: Unknown service: 'bedrock-runtime'
```

**Root Cause:** Ubuntu's `python3-boto3` package (v1.20.34) predates Bedrock service

**Solution:** Install latest boto3 via pip instead of apt:
```bash
pip3 install boto3 --upgrade
```

**Why Not Use apt:** Ubuntu packages are frozen at release time. Bedrock launched after Ubuntu 22.04 LTS.

**Status:** ✅ Fixed in `infra/redis-ec2.ts` line 165

---

### Issue #3: Missing Secrets Manager Permission for Redis Auth Token
**Problem:** Bulk load script fails with:
```
AccessDeniedException: User: arn:aws:sts::xxx:assumed-role/DAW-Redis-InstanceRole-dev/xxx 
is not authorized to perform: secretsmanager:GetSecretValue on resource: DAW-Redis-AuthToken-dev
```

**Root Cause:** IAM policy only had permission for `DAW-DB-Password-*`, not `DAW-Redis-AuthToken-*`

**Solution:** Add Redis auth token to Secrets Manager permissions:
```typescript
Resource: [
  `arn:aws:secretsmanager:*:*:secret:DAW-DB-Password-${stage}-*`,
  `arn:aws:secretsmanager:*:*:secret:DAW-Redis-AuthToken-${stage}-*`
]
```

**Status:** ✅ Fixed in `infra/redis-ec2.ts` lines 115-118

---

### Issue #4: Aurora Password Desynchronization
**Problem:** After SST deployment, Aurora rejects connections:
```
mysql.connector.errors.ProgrammingError: 1045 (28000): Access denied
```

**Root Cause:** SST regenerates Secrets Manager values on deployment, but doesn't update Aurora

**Solution:** After deployment, manually sync Aurora password:
```bash
DB_PASS=$(aws secretsmanager get-secret-value --secret-id DAW-DB-Password-dev \
  --query SecretString --output text | jq -r '.password')
aws rds modify-db-cluster --db-cluster-identifier daw-aurora-dev \
  --master-user-password "$DB_PASS" --apply-immediately
```

**Prevention:** This is an SST limitation. Always resync after deployment.

**Status:** ⚠️ Manual fix required after each deployment

---

### Issue #5: Redis User Not Created by Package
**Problem:** `chown: invalid user: 'redis:redis'` in user data logs

**Root Cause:** `redis-stack-server` deb package sometimes doesn't create the `redis` user

**Solution:** Explicitly create user before chown:
```bash
id -u redis &>/dev/null || useradd --system --no-create-home --shell /bin/false redis
```

**Status:** ✅ Fixed in `infra/redis-ec2.ts` line 232

---

### Issue #6: Redis Configuration Lost After EC2 Replacement
**Problem:** After `sst deploy`, Redis runs but has no password configured

**Root Cause:** User data only runs on first boot. EC2 replacement creates new instance without config.

**Solution:** Ensure user data script is idempotent and complete:
- Install all dependencies
- Create redis user
- Configure Redis with password
- Enable and start service

**Status:** ✅ Fixed - user data script now complete

---

## Deployment Checklist

### Before Deployment
- [ ] Review `infra/redis-ec2.ts` user data script
- [ ] Verify all dependencies listed in script
- [ ] Check IAM policies include all required resources

### After Deployment
1. **Wait for user data completion** (~3-5 minutes)
   ```bash
   aws ssm send-command --instance-ids <instance-id> \
     --document-name "AWS-RunShellScript" \
     --parameters 'commands=["tail -50 /var/log/user-data.log"]'
   ```

2. **Verify Redis is running**
   ```bash
   aws ssm send-command --instance-ids <instance-id> \
     --document-name "AWS-RunShellScript" \
     --parameters 'commands=["systemctl status redis-stack-server --no-pager"]'
   ```

3. **Sync Aurora password**
   ```bash
   DB_PASS=$(aws secretsmanager get-secret-value --secret-id DAW-DB-Password-dev \
     --query SecretString --output text | jq -r '.password')
   aws rds modify-db-cluster --db-cluster-identifier daw-aurora-dev \
     --master-user-password "$DB_PASS" --apply-immediately
   ```

4. **Wait for Aurora to become available**
   ```bash
   aws rds describe-db-clusters --db-cluster-identifier daw-aurora-dev \
     --query "DBClusters[0].Status" --output text
   ```

5. **Test 10-drug load**
   ```bash
   # Upload test script and run
   aws ssm send-command --instance-ids <instance-id> \
     --document-name "AWS-RunShellScript" \
     --parameters 'commands=["python3 /tmp/test10.py 2>&1"]'
   ```

---

## Testing Script (test10.py)

```python
import json, mysql.connector, redis, boto3

DB_HOST = "daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com"
DB_PORT, DB_NAME, REDIS_HOST, REDIS_PORT = 3306, "fdb", "localhost", 6379

print("🔄 Testing 10 drug load...")

sm = boto3.client("secretsmanager", region_name="us-east-1")
db_creds = json.loads(sm.get_secret_value(SecretId="DAW-DB-Password-dev")["SecretString"])
redis_token = sm.get_secret_value(SecretId="DAW-Redis-AuthToken-dev")["SecretString"]
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

db = mysql.connector.connect(
    host=DB_HOST, port=DB_PORT, database=DB_NAME,
    user=db_creds["username"], password=db_creds["password"]
)
cursor = db.cursor(dictionary=True)

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=redis_token, decode_responses=False)
print(f"✅ Connected - Redis before: {r.dbsize()}")

cursor.execute("SELECT ndc, drug_name, generic_name, manufacturer, dosage_form, route, strength, active_ingredients, dea_schedule FROM drugs WHERE drug_name IS NOT NULL LIMIT 10")

for i, drug in enumerate(cursor.fetchall(), 1):
    text = f"{drug['drug_name']} {drug['generic_name'] or ''}"
    resp = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text})
    )
    emb = json.loads(resp["body"].read())["embedding"]
    data = {k: (v if v else "") for k, v in drug.items()}
    data["embedding"] = emb
    r.json().set(f"drug:{drug['ndc']}", "$", data)
    print(f"  {i}. {drug['ndc']} - {drug['drug_name']}")

print(f"✅ Complete - Redis after: {r.dbsize()}")
cursor.close()
db.close()
```

---

## Architecture Notes

### Why Ubuntu 22.04 ARM64?
- Redis Stack 7.4.0 officially supported
- ARM64 for Graviton3 cost savings
- Active LTS support until 2027

### Why pip3 for boto3 Instead of apt?
- Ubuntu packages frozen at release (boto3 1.20.34 from 2022)
- Bedrock launched in 2023, requires boto3 >= 1.28.0
- pip provides latest version with all AWS services

### Why Manual Aurora Password Sync?
- SST/Pulumi limitation: Secrets Manager updates don't trigger Aurora password change
- Aurora password change requires explicit API call
- Takes 30-60 seconds to propagate

---

## Future Improvements

1. **Automate Aurora Password Sync**
   - Create Lambda to sync on Secrets Manager change
   - Or use Aurora Secrets Manager integration

2. **Health Check Script**
   - Automated post-deployment verification
   - Alert if any service fails

3. **User Data Completion Signal**
   - CloudFormation signal when user data completes
   - Block deployment until ready

---

**Last Validated:** 2025-11-13  
**Validated By:** AI Assistant during Session 4


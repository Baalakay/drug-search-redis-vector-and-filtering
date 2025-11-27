# EC2 Execution Steps - Test Load 100 Drugs

**Date:** 2025-11-19  
**Method:** A (EC2 Redis Instance)  
**Script:** NEW script created today (2025-11-19_test_load_100_drugs.py)

---

## Pre-Execution Checklist

- [ ] Verify EC2 Redis instance is running
- [ ] Verify Aurora is accessible from EC2
- [ ] Have EC2 SSH access or SSM Session Manager access
- [ ] Script is ready to copy

---

## Step 1: Get EC2 Access Info

```bash
# EC2 Instance ID (from your infra)
INSTANCE_ID="i-0aad9fc4ba71454fa"

# Get EC2 IP (if using SSH)
aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].PrivateIpAddress' \
  --output text
```

---

## Step 2: Copy Script to EC2

### Option A: Via SSM (Recommended - No SSH Key Needed)

```bash
# Create script on EC2 via SSM
aws ssm send-command \
  --instance-ids i-0aad9fc4ba71454fa \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cat > /tmp/test_load_100_drugs.py << '\''EOFSCRIPT'\''
<PASTE ENTIRE SCRIPT HERE>
EOFSCRIPT
chmod +x /tmp/test_load_100_drugs.py
"]' \
  --output text --query 'Command.CommandId'
```

### Option B: Via SCP (If SSH Access Available)

```bash
# Copy script
scp scripts/2025-11-19_test_load_100_drugs.py ec2-user@10.0.11.153:/tmp/test_load_100_drugs.py

# Make executable
ssh ec2-user@10.0.11.153 "chmod +x /tmp/test_load_100_drugs.py"
```

---

## Step 3: Install Dependencies (If Needed)

```bash
# Check if dependencies exist
aws ssm start-session --target i-0aad9fc4ba71454fa

# Once in session:
python3 -c "import mysql.connector, redis, numpy, boto3; print('All dependencies OK')"

# If any missing:
pip3 install mysql-connector-python redis numpy boto3
```

---

## Step 4: Run Test Load

```bash
# Start test load
aws ssm send-command \
  --instance-ids i-0aad9fc4ba71454fa \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cd /tmp && python3 test_load_100_drugs.py 2>&1 | tee test_load.log"]' \
  --output text --query 'Command.CommandId'

# Get command ID, then wait 30 seconds and check output
aws ssm get-command-invocation \
  --command-id <COMMAND_ID_FROM_ABOVE> \
  --instance-id i-0aad9fc4ba71454fa \
  --query 'StandardOutputContent' \
  --output text
```

**Expected Output:**
```
====================================================================================================
TEST LOAD: 100 Drugs for Option B Alternatives Testing
====================================================================================================

🔗 Connecting to Aurora...
🔗 Connecting to Redis...

📋 Fetching test dataset...
   Fetching CRESTOR variants...
   ✓ Found 10 CRESTOR variants
   📌 CRESTOR GCN: 57784
   Fetching rosuvastatin generics (same GCN)...
   ✓ Found 15 rosuvastatin generics
   Fetching other statins...
   ✓ Found 20 other statins
   Fetching LIPITOR...
   ✓ Found 5 LIPITOR variants
   Fetching diverse drug classes...
   ✓ Found 30 drugs from diverse classes
   Fetching 20 random drugs to reach 100...
   ✓ Found 20 random drugs

✅ Total drugs fetched: 100

💊 Fetching indications...
   ✓ Found indications for 95 drugs

💾 Loading drugs to Redis...
   [10/100] Loaded 10 drugs...
   [20/100] Loaded 20 drugs...
   ...
   [100/100] Loaded 100 drugs...

✅ Loaded 100 drugs, 0 failed

🔍 Verifying test data...
   Total test keys: 100
   
   Sample verification:
   
   NDC: 00310075139
      drug_name: CRESTOR 10 MG TABLET
      brand_name: CRESTOR
      gcn_seqno: 57784
      drug_class: HMG-COA REDUCTASE INHIBITORS
      is_generic: false
      is_active: true
      embedding: 1024 dimensions ✓
   
   [... 4 more samples ...]

✅ Verification complete

====================================================================================================
✅ TEST LOAD COMPLETE
====================================================================================================

Drugs loaded: 100
Failures: 0
Redis key prefix: drug_test:

Next step: Run field-by-field verification on CRESTOR
```

---

## Step 5: Verify CRESTOR Data

```bash
# Get CRESTOR NDC from test load output (e.g., 00310075139)
CRESTOR_NDC="00310075139"

# Query Redis for CRESTOR
aws ssm send-command \
  --instance-ids i-0aad9fc4ba71454fa \
  --document-name "AWS-RunShellScript" \
  --parameters "commands=[\"redis-cli -a DAW-Redis-SecureAuth-2025 HGETALL drug_test:$CRESTOR_NDC\"]" \
  --output text --query 'Command.CommandId'

# Wait 5 seconds, then:
aws ssm get-command-invocation \
  --command-id <COMMAND_ID> \
  --instance-id i-0aad9fc4ba71454fa \
  --query 'StandardOutputContent' \
  --output text
```

**Expected Output:**
```
ndc
00310075139
drug_name
CRESTOR 10 MG TABLET
brand_name
CRESTOR
generic_name
crestor
gcn_seqno
57784
drug_class
HMG-COA REDUCTASE INHIBITORS
indication
PRIMARY HYPERCHOLESTEROLEMIA|MIXED DYSLIPIDEMIA
is_generic
false
is_brand
true
is_active
true
dosage_form
TABLET
route
ORAL
...
```

**Verify Against Customer System:**
> "Rosuvastatin = HMG-CoA reductase inhibitor - for Primary hypercholesterolemia + Mixed dyslipidemias"

✅ `drug_class` matches "HMG-CoA reductase inhibitor"  
✅ `indication` matches "Primary hypercholesterolemia + Mixed dyslipidemias"

---

## Step 6: Verify Rosuvastatin Generic

```bash
# Get a rosuvastatin generic NDC from test load output
# Should have same GCN (57784) but is_generic=true

aws ssm send-command \
  --instance-ids i-0aad9fc4ba71454fa \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["redis-cli -a DAW-Redis-SecureAuth-2025 --no-auth-warning KEYS '\''drug_test:*'\'' | xargs -I {} redis-cli -a DAW-Redis-SecureAuth-2025 --no-auth-warning HGET {} drug_name | grep -i rosuvastatin | head -1"]' \
  --output text --query 'Command.CommandId'
```

---

## Step 7: Verify Other Statin (Atorvastatin)

Check that atorvastatin has:
- Different GCN (not 57784)
- Same drug_class (HMG-COA REDUCTASE INHIBITORS)

---

## Troubleshooting

### Issue: Script fails with "No module named 'mysql'"

**Solution:**
```bash
aws ssm start-session --target i-0aad9fc4ba71454fa
pip3 install mysql-connector-python
exit
# Re-run script
```

### Issue: "Access denied for user 'dawadmin'"

**Solution:**
```bash
# Verify DB password in Secrets Manager
aws secretsmanager get-secret-value --secret-id DAW-DB-Password-dev

# Script automatically fetches this, so password should be correct
# Check security group allows EC2 → Aurora access
```

### Issue: Redis connection timeout

**Solution:**
```bash
# Verify Redis is running
aws ssm send-command \
  --instance-ids i-0aad9fc4ba71454fa \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["systemctl status redis-stack"]'
```

---

## After Successful Test Load

Once verified:
1. ✅ drug_class is correct
2. ✅ indication is correct
3. ✅ GCN matching works
4. ✅ All 100 drugs loaded

**Then proceed to Phase 6:** Test the 8 search queries via API

---

**Status:** Ready to execute  
**ETA:** ~5-10 minutes for 100 drugs


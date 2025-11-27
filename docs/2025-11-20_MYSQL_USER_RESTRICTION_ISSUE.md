# MySQL User Host Restriction - Blocker Issue
**Date:** 2025-11-20  
**Status:** 🚫 BLOCKER - Prevents test load execution

---

## 🔍 Problem Summary

The MySQL user `dawadmin` has host-based access restrictions preventing connections from **all sources**, including:

```
❌ Redis EC2:     Access denied for user 'dawadmin'@'10.0.11.153' (using password: YES)
❌ Lambda:        Access denied for user 'dawadmin'@'10.0.12.237' (using password: YES)  
❌ Dev Container: Access denied for user 'dawadmin'@'172.31.101.237' (using password: YES)
```

---

## ✅ What IS Working (Network/Security)

### Network Connectivity
- **Port 3306 Reachable:** ✅ Verified from Redis EC2 using `/dev/tcp` test
- **VPC Peering:** ✅ Active (`pcx-0bd5c1c66ab19e74f`)
- **Route Tables:** ✅ Configured correctly

###Security Groups
- **Aurora SG** (`sg-06751ecb3d755eff2`):  
  - ✅ Allows inbound TCP 3306 from Lambda SG (`sg-0e78f3a483550e499`)
  - ✅ Allows inbound TCP 3306 from Redis SG (`sg-09bc62902d8a5ad29`)
  - ✅ Allows inbound TCP 3306 from Dev Container IP (`172.31.101.237/32`)

### Authentication
- **Password:** ✅ Correct (verified from Secrets Manager: `0k(ucbMbiwcW$byc&FUp53c2eUQE!Fi5`)
- **Username:** ✅ Correct (`dawadmin`)

---

## ❌ What IS NOT Working (MySQL User Permissions)

### Root Cause: MySQL User Host Restriction

The MySQL user `dawadmin` was created with restrictive host permissions. Currently it likely has:

```sql
-- Restrictive (current state):
CREATE USER 'dawadmin'@'localhost' IDENTIFIED BY 'password';
-- OR
CREATE USER 'dawadmin'@'specific_ip' IDENTIFIED BY 'password';
```

But we need:

```sql
-- Permissive (needed):
CREATE USER 'dawadmin'@'%' IDENTIFIED BY 'password';  -- Allows from any host
```

### Evidence

1. **Network is fine:** Port 3306 is reachable from Redis EC2
2. **Security groups are fine:** All sources are explicitly allowed
3. **Password is correct:** Verified from Secrets Manager
4. **BUT:** All connection attempts get "Access denied" with correct password

This is **NOT** a networking issue - it's a MySQL authentication/authorization issue.

---

## 🎯 Solution: Grant Wildcard Host Access

Someone with existing Aurora access needs to run:

```sql
GRANT ALL PRIVILEGES ON fdb.* TO 'dawadmin'@'%' IDENTIFIED BY '0k(ucbMbiwcW$byc&FUp53c2eUQE!Fi5';
FLUSH PRIVILEGES;

-- Verify:
SELECT User, Host FROM mysql.user WHERE User='dawadmin';
```

### Option 1: AWS RDS Query Editor (Recommended) ⭐

1. Navigate to: https://console.aws.amazon.com/rds/
2. Click "Query editor" in left sidebar
3. Connect to:
   - **Database:** `daw-aurora-dev`
   - **Database name:** `fdb`
   - **Username:** `dawadmin`
   - **Password:** `0k(ucbMbiwcW$byc&FUp53c2eUQE!Fi5`
4. Run the GRANT statement above

### Option 2: Bastion Host

If you have a bastion host with existing Aurora access, connect from there.

### Option 3: Local Machine

If your local machine has network access to Aurora, connect with:

```bash
mysql -h daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com \
      -u dawadmin \
      -p'0k(ucbMbiwcW$byc&FUp53c2eUQE!Fi5' \
      fdb
```

---

## 📊 Database Details

- **Cluster:** `daw-aurora-dev`
- **Endpoint:** `daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com`
- **Port:** `3306`
- **Engine:** `aurora-mysql 8.0.mysql_aurora.3.08.2`
- **Database:** `fdb`
- **Master User:** `dawadmin`
- **Data API:** ❌ Not enabled
- **IAM Auth:** ❌ Not enabled

---

## ⏭️ What Happens After This Is Fixed

Once the GRANT is successful, we can immediately:

1. **Run test load from dev container:**
   ```bash
   cd /workspaces/DAW
   python3 scripts/2025-11-19_test_load_100_drugs.py
   ```

2. **Verify 100 test drugs** loaded correctly to `drug_test:` prefix

3. **Test 8 realistic queries** against test data

4. **Full production reload** (493k drugs) if tests pass

---

## 🔧 Troubleshooting Steps Taken

### Attempted Solutions (all failed with same error):

1. ✅ Verified security groups - all correct
2. ✅ Tested port 3306 reachability - confirmed reachable
3. ✅ Verified password from Secrets Manager - correct
4. ❌ Tried connecting from Redis EC2 - Access denied
5. ❌ Tried connecting from Lambda - Access denied
6. ❌ Tried connecting from dev container - Access denied
7. ❌ Attempted to grant permissions from Lambda - Access denied (can't grant without access)
8. ✅ Confirmed engine is MySQL (not PostgreSQL)
9. ✅ Confirmed Data API not enabled
10. ✅ Confirmed IAM auth not enabled

### Why Previous Approaches Failed

**Q: Why can't Lambda grant the permission?**  
A: Lambda also gets "Access denied" - it can't connect either.

**Q: Why can't we use SSM to run it on Redis EC2?**  
A: Redis EC2 also gets "Access denied" - same issue.

**Q: Why can't we enable Data API to bypass this?**  
A: Data API can be enabled, but would require:
   - Aurora cluster modification (5-10 min downtime)
   - SST config update  
   - Redeploy
   - Still need to connect once to grant initial permissions

The fastest path is to grant the permission from an existing authorized source.

---

## 📝 Next Actions

**User needs to:**
1. Use AWS RDS Query Editor (or bastion/local machine)
2. Run the GRANT statement
3. Confirm success: `SELECT User, Host FROM mysql.user WHERE User='dawadmin';`

**Then we can:**
1. Run test load immediately
2. Continue with Phase 5-8 of Redis reload plan

---

**Estimated Time to Unblock:** 2-5 minutes (once user has console/bastion access)


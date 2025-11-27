# Phase 4: SST Configuration TODOs

## ⚠️ Manual Changes Made (Need to Sync to SST)

The following manual changes were made and **MUST** be added to SST configuration files to maintain state sync:

### 1. Lambda Function (`DAW-DrugSync-dev`)
**Manual Creation**: Lambda was created via AWS CLI
**Location**: Should be in `infra/sync.ts`
**Status**: ❌ Not in SST - Lambda was manually created as workaround for SST deployment error

### 2. Lambda Layer (`DAW-DrugSync-Dependencies`)
**Manual Creation**: Layer created via AWS CLI
**Location**: Should be in `infra/sync.ts` 
**Status**: ❌ Not in SST - Layer needs to be defined

### 3. Security Group Rules
**Manual Addition**: 
- RDS SG: Allow Lambda SG on port 3306 (MySQL)
**Location**: Already exists in `infra/network.ts` (Lambda → RDS rule exists)
**Status**: ✅ Already in SST

### 4. Lambda Environment Variables
**Manual Update**: Changed REDIS_HOST from `10.0.11.245` to `10.0.11.80`
**Location**: `infra/sync.ts` environment variables
**Status**: ❌ Hardcoded IP in SST, needs to use output from redis-ec2.ts

### 5. Redis Service Start
**Manual Action**: Started redis-stack-server via SSM
**Root Cause**: User data script's `systemctl enable/start` commands didn't execute
**Location**: `infra/redis-ec2.ts` user data script (lines 249-250)
**Status**: ⚠️ User data script exists but failed - needs debugging

## 🔧 Required SST Fixes

### Fix #1: Remove Manual Lambda & Update infra/sync.ts
The Lambda function in `infra/sync.ts` needs to match what was manually created. Currently SST tries to deploy it but hits "RangeError: Invalid string length".

**Issue**: SST deployment error prevents Lambda creation
**Current Workaround**: Manual Lambda creation
**Proper Fix**: Fix SST deployment error OR remove Lambda from SST (not recommended)

### Fix #2: Dynamic Redis IP in Lambda Environment
```typescript
// infra/sync.ts - WRONG (hardcoded)
environment: {
  REDIS_HOST: "10.0.11.245",  // ❌ Hardcoded old IP
  // ...
}

// infra/sync.ts - CORRECT (dynamic)
environment: {
  REDIS_HOST: redisEndpoint,  // ✅ From redis-ec2.ts output
  // ...
}
```

**File to update**: `infra/sync.ts`
**Change**: Use `redisEndpoint` parameter instead of hardcoded IP

### Fix #3: Debug User Data Script
The user data script creates the systemd service file but fails to enable/start it.

**Symptoms**:
- Service file exists: `/etc/systemd/system/redis-stack-server.service`
- Service status: `disabled` and `inactive (dead)`
- No errors in cloud-init logs

**Possible causes**:
1. Script exits before reaching `systemctl` commands
2. `systemctl` commands fail silently
3. User data runs before systemd is ready

**Recommended fix**: Add error handling and logging to user data script:
```bash
# In infra/redis-ec2.ts user data
systemctl enable redis-stack-server || echo "Failed to enable redis" | tee -a /tmp/redis-setup.log
systemctl start redis-stack-server || echo "Failed to start redis" | tee -a /tmp/redis-setup.log
systemctl status redis-stack-server | tee -a /tmp/redis-setup.log
```

## 📋 Next Steps (In Order)

1. **DO NOT** make any more manual AWS changes
2. **Fix #2**: Update `infra/sync.ts` to use dynamic Redis IP
3. **Fix #3**: Add error logging to user data script
4. **Terminate** current Redis instance: `i-0de6100b60edd49dd`
5. **Deploy** via SST: `npx sst deploy --stage dev`
6. **Verify** Redis starts automatically (check logs via SSM)
7. **Fix #1**: Resolve SST Lambda deployment error (future work)

## 🎯 Current Status

- Redis EC2: ✅ Running with Redis installed (manually started)
- Lambda Function: ⚠️ Exists but not in SST state
- Lambda Environment: ⚠️ Has wrong Redis IP (just updated manually)
- Aurora: ✅ Working with correct password

## ⚠️ Critical Note

**ALL** of the above manual changes will cause SST state drift. Future SST deployments may:
- Try to delete/recreate the manual Lambda
- Revert environment variables to old values
- Cause conflicts and deployment failures

**Resolution**: Either:
A) Add all manual resources to SST config (recommended but time-consuming)
B) Continue with manual resources and skip SST for Lambda (not recommended)
C) Fix SST deployment error and let SST manage everything (ideal but blocked)


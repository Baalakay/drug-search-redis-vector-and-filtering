# Phase 4 Blocker: Redis Not Installed on EC2

## Issue
The Redis EC2 instance (`i-0ec914f45110b9b9c`) does not have Redis Stack installed, despite the user data script in `infra/redis-ec2.ts` containing installation commands.

## Root Cause
The EC2 user data script either:
1. Never executed
2. Failed during execution
3. Was not applied when the instance was created/updated

## Impact
- Lambda sync function cannot connect to Redis (Connection refused on port 6379)
- Phase 4 testing is blocked
- All Redis-dependent features are blocked

## Quick Fix (Manual Installation)
Install Redis Stack manually via SSM to unblock Phase 4 testing.

## Proper Fix (For Later)
1. Check if EC2 instance was created before or after user data script was added to SST
2. Re-deploy Redis EC2 with SST to ensure user data runs
3. Or create AMI with Redis pre-installed
4. Add health checks to verify Redis is running after deployment

## Status
- [ ] Manual Redis installation in progress
- [ ] Phase 4 testing blocked
- [ ] Needs proper fix in Phase 1 infrastructure


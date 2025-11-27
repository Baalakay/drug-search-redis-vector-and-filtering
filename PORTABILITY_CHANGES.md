# Portability Changes Summary

This document tracks changes made to make the project portable as a template.

## Changes Made

### 1. Package Name: `daw_functions` → `functions`
- ✅ `packages/functions/pyproject.toml` - Changed package name
- ✅ `infra/search-api.ts` - Updated handler paths
- ✅ `infra/sync.ts` - Updated handler path
- ✅ `packages/functions/src/search_handler.py` - Updated imports

### 2. Project Name Configuration
- ✅ `project.config.ts` - Made `projectName` configurable via `PROJECT_NAME` env var
- ✅ `sst.config.ts` - Uses `$app.name` (from env var or default "DAW")

### 3. Infrastructure Resource Names
**Note**: Many resources use hardcoded "DAW" prefixes because they're imported from existing deployments. For NEW deployments, these will use `$app.name`.

**Files that need updates for full portability:**
- `infra/sync.ts` - Resource names and tags
- `infra/database.ts` - Resource names and tags  
- `infra/network.ts` - Resource names and tags
- `infra/redis-ec2.ts` - Resource names and tags
- `infra/api.ts` - Resource names and tags

**Parameter Store Paths:**
- Currently: `/daw/${stage}/...`
- Should be: `/${$app.name.toLowerCase()}/${stage}/...`

## How to Use This Template

1. **Set Project Name** (optional, defaults to "DAW"):
   ```bash
   export PROJECT_NAME="YourProjectName"
   ```

2. **Deploy**:
   ```bash
   sst deploy --stage dev
   ```

## Backward Compatibility

- Default project name remains "DAW" for backward compatibility
- Existing resource imports will continue to work
- New resources will use `$app.name` from environment or default


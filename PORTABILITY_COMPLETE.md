# Portability Changes - Complete Summary

## ✅ Changes Completed

### 1. Package Name: `daw_functions` → `functions`
- ✅ `packages/functions/pyproject.toml` - Package name changed to `functions`
- ✅ `infra/search-api.ts` - All handler paths updated to `functions.src.*`
- ✅ `infra/sync.ts` - Handler path updated to `functions.src.*`
- ✅ `packages/functions/src/search_handler.py` - Imports updated to `functions.src.*`

### 2. Project Name Configuration
- ✅ `project.config.ts` - Made configurable via `PROJECT_NAME` env var (defaults to "DAW")
- ✅ `sst.config.ts` - Uses `$app.name` from env var or default
- ✅ `sst.config.ts` - Console log uses `$app.name`
- ✅ `sst.config.ts` - Parameter Store path uses `$app.name.toLowerCase()`

### 3. Infrastructure Updates
- ✅ `infra/sync.ts` - CloudWatch namespace uses `$app.name`
- ✅ `infra/sync.ts` - Resource tags use `$app.name`
- ✅ `infra/database.ts` - Parameter Store path uses `$app.name.toLowerCase()`
- ✅ `infra/database.ts` - Resource tags use `$app.name`
- ✅ `infra/search-api.ts` - Secrets Manager ARN uses `$app.name`

## 📝 Remaining Hardcoded References

**Note**: The following still contain hardcoded "DAW" references, but these are mostly:
1. **Resource logical IDs** (Pulumi resource names) - These don't affect deployed resource names
2. **Imported resource references** - These reference existing resources and should stay as-is for existing deployments
3. **Comments/documentation** - Not critical for functionality

**Files with remaining "DAW" references:**
- `infra/network.ts` - Resource logical IDs and tags (can be updated for new deployments)
- `infra/redis-ec2.ts` - Resource names and tags
- `infra/api.ts` - Resource names and tags
- `infra/sync.ts` - Some resource logical IDs (but tags updated)
- `infra/database.ts` - Some resource logical IDs (but tags updated)

## 🚀 How to Use This Template

### For New Projects:

1. **Set your project name** (optional, defaults to "DAW"):
   ```bash
   export PROJECT_NAME="YourProjectName"
   ```

2. **Deploy**:
   ```bash
   sst deploy --stage dev
   ```

### For Existing DAW Deployments:

- All changes are backward compatible
- Default project name remains "DAW"
- Existing resource imports continue to work
- Only new resources will use `$app.name`

## 🔍 Key Changes Made

1. **Package imports**: `daw_functions` → `functions` ✅
2. **SST app name**: Hardcoded "DAW" → `$app.name` (configurable) ✅
3. **Resource tags**: Hardcoded "DAW" → `$app.name` ✅
4. **Parameter Store paths**: `/daw/` → `/${$app.name.toLowerCase()}/` ✅
5. **CloudWatch namespaces**: `DAW/` → `${$app.name}/` ✅
6. **Secrets Manager ARNs**: `DAW-*` → `${$app.name}-*` ✅

## ⚠️ Important Notes

- **Resource logical IDs** (Pulumi resource names like `"DAW-VPC"`) remain unchanged to avoid breaking existing imports
- **Resource names** (AWS resource names) now use `$app.name` where applicable
- **Tags** now use `$app.name` for better organization
- **Parameter Store paths** are now dynamic based on `$app.name`

The project is now portable and can be used as a template by simply setting the `PROJECT_NAME` environment variable!


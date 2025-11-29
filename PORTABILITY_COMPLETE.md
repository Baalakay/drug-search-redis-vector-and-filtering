# Portability Changes - Complete Summary

## ✅ Changes Completed

### 1. Package Name: `daw_functions` → `functions`
- ✅ `packages/functions/pyproject.toml` - Package name changed to `functions`
- ✅ `infra/search-api.ts` - All handler paths updated to `functions.src.*`
- ✅ `infra/sync.ts` - Handler path updated to `functions.src.*`
- ✅ `packages/functions/src/search_handler.py` - Imports updated to `functions.src.*`

### 2. Project Name Configuration
- ✅ `project.config.ts` - Made configurable via `PROJECT_NAME` env var (defaults to "DAW")
- ✅ `project.config.ts` - `PROJECT_PREFIX` now defaults to `PROJECT_NAME` if not set
- ✅ `sst.config.ts` - Uses `$app.name` from env var or default
- ✅ `sst.config.ts` - Console log uses `$app.name`
- ✅ `sst.config.ts` - Parameter Store path uses `$app.name.toLowerCase()`

### 3. Config File Descriptions
- ✅ `package.json` - Description made generic
- ✅ `pyproject.toml` - Description made generic
- ✅ `packages/core/pyproject.toml` - Description made generic
- ✅ `packages/core/package.json` - Description made generic
- ✅ `packages/scripts/pyproject.toml` - Description made generic
- ✅ `packages/scripts/package.json` - Description made generic
- ✅ `packages/jobs/pyproject.toml` - Description made generic

### 3. Infrastructure Updates
- ✅ `infra/sync.ts` - CloudWatch namespace uses `${$app.name}/DrugSync`
- ✅ `infra/sync.ts` - All resource tags use `$app.name`
- ✅ `infra/sync.ts` - EventBridge schedule tags use `$app.name`
- ✅ `infra/sync.ts` - CloudWatch alarm tags use `$app.name`
- ✅ `infra/database.ts` - Parameter Store path uses `$app.name.toLowerCase()`
- ✅ `infra/database.ts` - All resource tags use `$app.name`
- ✅ `infra/search-api.ts` - Secrets Manager ARN uses `$app.name`
- ✅ `infra/search-api.ts` - Default Redis password uses `${$app.name}-Redis-SecureAuth-2025`
- ✅ `infra/network.ts` - All resource tags use `$app.name`
- ✅ `infra/redis-ec2.ts` - All resource tags use `$app.name`
- ✅ `infra/redis-ec2.ts` - CloudWatch namespace uses `${$app.name}/Redis`
- ✅ `infra/redis-ec2.ts` - Parameter Store paths use `/${$app.name.toLowerCase()}/`
- ✅ `infra/redis-ec2.ts` - Log group names use `/${$app.name.toLowerCase()}/`
- ✅ `infra/redis-ec2.ts` - User data script uses dynamic project name
- ✅ `infra/redis-ec2.ts` - S3 bucket references use `${$app.name.toLowerCase()}-temp-data-import-*`
- ✅ `infra/redis-ec2.ts` - Secrets Manager ARNs use `${$app.name}-*`
- ✅ `infra/api.ts` - All resource tags use `$app.name`
- ✅ `infra/api.ts` - Log group names use `${$app.name}-SearchAPI-*`

## 📝 Remaining Hardcoded References

**Note**: The following still contain hardcoded "DAW" references:

1. **Package names** in `package.json` and `pyproject.toml` files - These are part of package identity and require manual changes for new projects. See `PORTABILITY_GUIDE.md` for details.

2. **Default values** in config files - Default to "DAW" for backward compatibility:
   - `project.config.ts`: `process.env.PROJECT_NAME || "DAW"`
   - `sst.config.ts`: `process.env.PROJECT_NAME || "DAW"`

3. **Resource logical IDs** (Pulumi resource names like `"DAW-VPC"`) - These don't affect deployed resource names and are kept for backward compatibility with existing imports

4. **Imported resource references** - These reference existing resources and should stay as-is for existing deployments

5. **Comments/documentation** - Some comments reference "DAW" for clarity but don't affect functionality

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
3. **Resource tags**: All hardcoded "DAW" → `$app.name` ✅
4. **Parameter Store paths**: `/daw/` → `/${$app.name.toLowerCase()}/` ✅
5. **CloudWatch namespaces**: `DAW/` → `${$app.name}/` ✅
6. **CloudWatch log groups**: `/daw/` → `/${$app.name.toLowerCase()}/` ✅
7. **Secrets Manager ARNs**: `DAW-*` → `${$app.name}-*` ✅
8. **S3 bucket references**: `daw-temp-data-import-*` → `${$app.name.toLowerCase()}-temp-data-import-*` ✅
9. **Default Redis password**: `DAW-Redis-SecureAuth-2025` → `${$app.name}-Redis-SecureAuth-2025` ✅
10. **User data scripts**: All hardcoded project names → dynamic `$app.name` ✅

## ⚠️ Important Notes

- **Resource logical IDs** (Pulumi resource names like `"DAW-VPC"`) remain unchanged to avoid breaking existing imports
- **Resource names** (AWS resource names) now use `$app.name` where applicable
- **Tags** now use `$app.name` for better organization
- **Parameter Store paths** are now dynamic based on `$app.name`

The project is now portable and can be used as a template! 

**Quick Start:**
1. Set `PROJECT_NAME` environment variable
2. Update package names in `package.json` and `pyproject.toml` files (see `PORTABILITY_GUIDE.md`)
3. Deploy with `sst deploy --stage dev`

See `PORTABILITY_GUIDE.md` for complete instructions on using this as a template.


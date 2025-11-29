# Portability Guide - Using This Project as a Template

This guide explains how to use this project as a template for new projects and what needs to be customized.

## Automatic Configuration

Most project-specific references are now configurable via environment variables:

### Environment Variables

- `PROJECT_NAME` - Sets the project name (defaults to "DAW")
  - Used for: SST app name, resource tags, CloudWatch namespaces, Parameter Store paths
  - Example: `export PROJECT_NAME="MyProject"`

- `PROJECT_DESCRIPTION` - Sets the project description (optional)
  - Used for: Project metadata
  - Example: `export PROJECT_DESCRIPTION="My Custom Description"`

- `PROJECT_PREFIX` - Sets the prefix for resource naming (defaults to PROJECT_NAME)
  - Used for: Resource naming conventions
  - Example: `export PROJECT_PREFIX="MP"`

## Manual Changes Required

The following files contain package names that are part of the package identity and need to be manually changed for new projects:

### 1. Root Package Files

**`package.json`**
```json
{
  "name": "DAW",  // Change to your project name
  "description": "SST v3 Monorepo"  // Update description
}
```

**`pyproject.toml`**
```toml
[project]
name = "DAW"  # Change to your project name (lowercase recommended)
description = "SST v3 Monorepo"  # Update description
```

### 2. Package-Level Files

**`packages/core/package.json`**
```json
{
  "name": "@daw/core",  // Change to "@yourproject/core"
}
```

**`packages/core/pyproject.toml`**
```toml
[project]
name = "daw_core"  # Change to "yourproject_core"
```

**`packages/scripts/package.json`**
```json
{
  "name": "@daw/scripts",  // Change to "@yourproject/scripts"
}
```

**`packages/scripts/pyproject.toml`**
```toml
[project]
name = "daw_scripts"  # Change to "yourproject_scripts"
dependencies = [
    "daw_core",  # Change to "yourproject_core"
]
```

**`packages/jobs/pyproject.toml`**
```toml
[project]
name = "daw_jobs"  # Change to "yourproject_jobs"
dependencies = [
    "daw_core",  # Change to "yourproject_core"
]
```

### 3. Infrastructure Resource Logical IDs

**Note**: Resource logical IDs (like `"DAW-VPC"`, `"DAW-DrugSync-Role"`) in infrastructure files are kept as-is for backward compatibility with existing deployments. For new projects, you can optionally update these, but they don't affect deployed resource names (which use `$app.name`).

Files with resource logical IDs:
- `infra/network.ts`
- `infra/database.ts`
- `infra/sync.ts`
- `infra/redis-ec2.ts`
- `infra/api.ts`

### 4. Comments and Documentation

Some comments and documentation strings still reference "DAW" for clarity. These can be updated but don't affect functionality.

## Quick Start for New Projects

1. **Set environment variables:**
   ```bash
   export PROJECT_NAME="YourProjectName"
   export PROJECT_DESCRIPTION="Your Project Description"
   ```

2. **Update package names** (see Manual Changes above):
   - Root `package.json` and `pyproject.toml`
   - All `packages/*/package.json` and `packages/*/pyproject.toml` files
   - Update cross-package dependencies

3. **Deploy:**
   ```bash
   sst deploy --stage dev
   ```

## What's Already Portable

✅ **Infrastructure tags** - All use `$app.name`  
✅ **CloudWatch namespaces** - All use `${$app.name}/...`  
✅ **Parameter Store paths** - All use `/${$app.name.toLowerCase()}/...`  
✅ **Secrets Manager ARNs** - All use `${$app.name}-*`  
✅ **Resource names** - All use `$app.name` where applicable  
✅ **User data scripts** - All use dynamic project name  
✅ **S3 bucket references** - All use `${$app.name.toLowerCase()}-*`  

## Backward Compatibility

- Default project name remains "DAW" if `PROJECT_NAME` is not set
- Existing resource imports continue to work
- Only new resources will use the configurable `$app.name`


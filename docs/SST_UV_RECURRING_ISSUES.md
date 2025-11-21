# SST + UV Recurring Issues & Root Causes

## 🚨 CRITICAL TROUBLESHOOTING RULE

**ALWAYS CHECK PULUMI LOGS FIRST** when SST reports success but resources don't exist:
```bash
grep -i "error\|fail\|exception" .sst/pulumi/*/eventlog.json
```
This immediately shows the root cause and saves 20+ minutes of troubleshooting.

## Issue Summary

When using SST v3 with Python Lambda functions and UV as the package manager, several issues keep recurring across different projects. This document identifies the root causes and permanent solutions.

## Recurring Issue #1: UV Sync Errors from .venv Corruption

**Frequency**: After attempting to delete .venv directory
**Error Message**: 
```
Error: failed to run uv sync: exit status 2
error: failed to remove directory `/path/.venv/lib/python3.12/site-packages/package.dist-info`: No such file or directory (os error 2)
```

**Root Cause**: The .venv directory was corrupted by attempting to delete it. UV manages .venv as a virtual drive that cannot be safely deleted.

**❌ NEVER DO THIS**:
```bash
rm -rf .venv  # ❌ CAUSES CORRUPTION - .venv is UV managed!
```

**Permanent Solution**:
- **NEVER attempt to delete .venv** - it's managed by UV
- If UV sync errors occur, clean other artifacts but leave .venv alone:
  ```bash
  # ✅ Safe to clean these
  rm -rf functions/__pycache__ functions/.pytest_cache
  rm -rf .sst
  ```
- UV will self-heal the .venv over time
- Focus on fixing the actual deployment issues, not .venv

**Prevention**: Add to memory bank and session reminders - .venv is off-limits.

## Recurring Issue #2: SST State Out of Sync (Manual AWS Changes)

**Frequency**: After manual AWS CLI updates to resources
**Error Message**: Environment variables, configurations, or resources not updating despite correct SST config.

**Root Cause**: Manual AWS CLI changes cause SST state to go out of sync with actual cloud resources. SST compares config to cached state file, not actual resources.

**❌ WRONG Solution**: `sst remove` (nuclear option - destroys everything)

**✅ CORRECT Solution**: `sst refresh` (syncs state with reality)
```bash
# 1. Sync state with actual cloud resources
sst refresh --stage dev

# 2. Deploy config changes
sst deploy --stage dev
```

**Permanent Solution**: 
- **NEVER manually update AWS resources** outside of SST
- Always use SST configuration files for ALL changes
- Use `sst refresh` when state gets out of sync

**Reference**: [SST State Management Documentation](https://sst.dev/docs/state/#out-of-sync)

## Recurring Issue #3: "Workspace does not contain any buildable packages"

**Frequency**: Every new project setup  
**Error Message**: 
```
Error: failed to run uv build: exit status 2
error: Workspace does not contain any buildable packages
```

**Root Cause**: SST runs `uv build` in the `functions/` directory, but it lacks a `pyproject.toml` with `[build-system]`.

**Permanent Solution**: ALWAYS create `functions/pyproject.toml` during project initialization.

## Recurring Issue #4: "failed to run uv export: exit status 2"

**Frequency**: After pyproject.toml is added  
**Error Message**:
```
Error: failed to run uv export: exit status 2
```

**Root Causes**:
1. UV creates a `.venv` in `functions/` directory that conflicts with SST's packaging
2. UV's `export` command returns non-zero exit codes for stderr output (even on success)
3. Dependency resolution conflicts between `pyproject.toml` and `requirements.txt`
4. Lock file (`uv.lock`) corruption or staleness
5. **MOST COMMON**: `functions/` not added to workspace in root `pyproject.toml`

**Symptoms**:
- Works locally with `uv export` but fails in SST
- Exit code 2 even when UV succeeds
- "RangeError: Invalid string length" (error formatting issue)
- Error immediately after creating `functions/pyproject.toml`

**Why This Keeps Happening**:
- SST invokes UV in a subprocess with different environment/context than manual runs
- UV may use different Python interpreters or resolve dependencies differently
- `.venv` pollution from local development interferes with SST's clean build
- **Missing workspace configuration** causes UV to not recognize functions package

**Critical Fix** - Add functions to workspace:
```toml
# Root pyproject.toml
[tool.uv.workspace]
members = [
    "packages/core",
    "packages/jobs",
    "functions",  # ← ADD THIS! Critical for SST
]
```

**Without this**, UV won't build the functions package, causing:
- `uv export: exit status 2`
- `Workspace does not contain any buildable packages`
- Silent failures during deployment

## Permanent Solutions

### Solution 1: Clean Build Environment

**Before EVERY deployment**, ensure clean state:

```bash
# Clean UV artifacts in functions directory
rm -rf functions/.venv functions/.pytest_cache functions/__pycache__
rm -rf functions/src/**/__pycache__

# Clear SST artifacts cache
rm -rf .sst/artifacts

# Regenerate lock file
cd functions && uv lock --upgrade && cd ..
```

### Solution 2: Project Structure Requirements

```
project/
├── pyproject.toml              # ROOT: dev tools only
├── .python-version             # ROOT: Python version
└── functions/
    ├── pyproject.toml          # LAMBDA: REQUIRED, with [build-system]
    ├── .python-version         # LAMBDA: Match Python runtime
    ├── requirements.txt        # LAMBDA: Pinned versions
    ├── uv.lock                 # LAMBDA: Generated by UV
    └── src/
        └── handlers/
```

### Solution 3: Standard pyproject.toml Template

**`functions/pyproject.toml`** (ALWAYS use this template):

```toml
[project]
name = "lambda-functions"
version = "0.1.0"
description = "Lambda functions package"
requires-python = ">=3.12"
dependencies = [
    "boto3>=1.34.0",
    "botocore>=1.34.0",
    # Add other dependencies with EXACT versions
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]
```

**Key Points**:
- Use `hatchling` (works best with SST)
- Set `packages = ["src"]` - automatically includes ALL subdirectories
- **NEVER** explicitly list subdirectories - causes duplicate files
- Pin major versions but allow patches for security
- Use `functions.src.*` import paths in handler code

### Solution 4: Handler Path vs Import Path Configuration

**Issue**: `"No module named 'core'"` OR `"No module named 'functions'"` OR `"No module named 'src'"` despite correct packaging and directory structure.

**Root Cause**: **CRITICAL MISUNDERSTANDING** - SST does NOT automatically transform the handler path! The handler you specify is used LITERALLY as the Lambda runtime handler.

**The Real Problem**:
SST packages your code using the `name` field from `functions/pyproject.toml`, converting hyphens to underscores. The handler path must match this package name, NOT the directory name or file path.

**✅ CORRECT Solution (Based on Real Project Experience)**:

1. **`functions/pyproject.toml`** - Package name is KEY:
```toml
[project]
name = "my-functions"  # ← Becomes "my_functions" in package (hyphens → underscores)
version = "1.0.0"
dependencies = ["boto3>=1.34.131"]

[tool.hatch.build.targets.wheel]
packages = ["src"]
```

2. **Directory Structure** - All `__init__.py` required:
```
functions/
├── __init__.py           # ← REQUIRED
├── pyproject.toml
└── src/
    ├── __init__.py       # ← REQUIRED  
    └── handlers/
        ├── __init__.py   # ← REQUIRED
        └── my_handler.py
```

3. **SST Configuration** (in `infra/application.ts`) - Use PACKAGE name:
```typescript
// ❌ WRONG - Uses directory name or file path
handler: "functions/src/handlers/my_handler.handler"
handler: "src.handlers.my_handler.handler"

// ✅ CORRECT - Uses package name from pyproject.toml
handler: "my_functions.src.handlers.my_handler.handler"
//        ^^^^^^^^^^^^ (package name with hyphens → underscores)
```

4. **Verify Before Deploying**:
```bash
# Check what SST actually packages
ls -la .sst/artifacts/YourFunctionName-src/

# Find your handler - the path from artifacts root is your handler
find .sst/artifacts/YourFunctionName-src/ -name "my_handler.py"
# Output: .sst/artifacts/Function-src/my_functions/src/handlers/my_handler.py
#                                      ^^^^^^^^^^^^ This is your package root!
```

**Key Points**:
- ✅ Handler path = Python import path (NOT file path)
- ✅ Package name from `pyproject.toml` becomes the root module
- ✅ Hyphens in package names → underscores (`my-pkg` → `my_pkg`)
- ✅ All `__init__.py` files required in package hierarchy
- ✅ Add `functions/` to workspace in root `pyproject.toml`
- ❌ SST does NOT prepend "functions" to the module path
- ❌ Handler is NOT a file path relative to project root

**Common Mistakes That Waste Hours**:
1. Using `"functions/src/..."` (file path, not module path)
2. Using `"src.handlers...."` (missing package root)
3. Forgetting hyphens → underscores conversion
4. Missing any `__init__.py` file
5. Not checking `.sst/artifacts/` to see actual structure

**Result**: Handler works immediately after deploy, no manual Lambda configuration needed.

### Solution 5: .python-version Files

Create in BOTH root and functions/:

```bash
echo "3.12" > .python-version
echo "3.12" > functions/.python-version
```

### Solution 5: Pre-Deployment Script

Create `scripts/pre-deploy.sh`:

```bash
#!/bin/bash
set -e

echo "🧹 Cleaning build artifacts..."
rm -rf functions/.venv functions/.pytest_cache 
find functions -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

echo "🔒 Regenerating lock file..."
cd functions && uv lock --upgrade && cd ..

echo "✅ Ready for deployment"
```

Run before every deploy:
```bash
./scripts/pre-deploy.sh
npx sst deploy --stage staging
```

### Solution 6: Dependency Management

**ALWAYS**:
1. List exact versions in `pyproject.toml` dependencies
2. Keep `requirements.txt` in sync (or remove it)
3. Regenerate `uv.lock` after any dependency change
4. Never manually edit `uv.lock`

**NEVER**:
1. Run `uv venv` or `uv sync` in `functions/` directory
2. Create `.venv` in `functions/`
3. Mix pip and UV in the same project
4. Use loose version specifiers (>= without upper bound)

## Detection & Prevention

### How to Detect These Issues

1. **Test UV locally first**:
```bash
cd functions
uv export > /dev/null 2>&1 && echo "✅ UV export works" || echo "❌ UV export fails"
uv build && echo "✅ UV build works" || echo "❌ UV build fails"
```

2. **Check for pollution**:
```bash
ls -la functions/.venv 2>/dev/null && echo "⚠️  .venv exists in functions/" || echo "✅ No .venv"
```

3. **Verify pyproject.toml**:
```bash
grep -q "\[build-system\]" functions/pyproject.toml && echo "✅ Has build-system" || echo "❌ Missing build-system"
```

### Prevention Checklist

Before every `sst deploy`:

- [ ] `functions/pyproject.toml` exists with `[build-system]`
- [ ] `functions/.python-version` matches Lambda runtime
- [ ] No `.venv` in `functions/` directory
- [ ] `uv.lock` is up-to-date (`cd functions && uv lock --upgrade`)
- [ ] All `__pycache__` directories removed
- [ ] `.sst/artifacts` cleared if changing dependencies

## Why SST + UV is Fragile

**Understanding the Problem**:

1. **SST's Expectations**:
   - Clean, reproducible builds
   - Standard Python packaging structure
   - Zero-state deployments

2. **UV's Behavior**:
   - Creates local `.venv` automatically
   - Uses lock files for reproducibility
   - Returns non-zero exit codes for stderr output

3. **The Conflict**:
   - SST subprocess ≠ local shell environment
   - UV's `.venv` interferes with SST's Lambda packaging
   - Exit code interpretation differs

## Long-Term Fix

**What the SST Migration Guide Should Include**:

1. **Prominent warning section at the top**
2. **Pre-deployment checklist**
3. **Troubleshooting decision tree**
4. **Automated pre-deploy script**
5. **Project structure diagram with annotations**

## Recurring Issue #5: Using Raw Pulumi Lambda Instead of sst.aws.Function

**Frequency**: When copying examples from Pulumi docs instead of SST docs  
**Error**: Lambda deployment "completes" but function doesn't exist. `PromiseRejectionHandledWarning` in logs.

**Root Cause**: Raw Pulumi `aws.lambda.Function` doesn't integrate with SST's Python packaging system.

**Symptoms**:
```bash
✓  Deploy complete
   outputs: {functionArn: "arn:...", functionName: "..."}
# But:
aws lambda list-functions  # ← Shows NO function!

# Related resources exist:
aws iam get-role --role-name Function-Role  # ✅ Exists
aws events list-rules  # ✅ Exists  
aws cloudwatch describe-alarms  # ✅ Exists
# Lambda function: ❌ Missing
```

**❌ WRONG**:
```typescript
const func = new aws.lambda.Function("MyFunc", {
  role: roleArn,
  handler: "handler.lambda_handler",
  runtime: aws.lambda.Runtime.Python3d12,
  code: new pulumi.asset.FileArchive("./functions/"),
});
```

**✅ CORRECT**:
```typescript
const func = new sst.aws.Function("MyFunc", {
  handler: "my_package.src.handlers.handler.lambda_handler",
  runtime: "python3.12",
});
```

**Key Point**: SST's `sst.aws.Function` handles Python packaging, dependencies, IAM, and error reporting automatically. Raw Pulumi requires all of this manually and fails silently with Python packages.

---

## Recurring Issue #6: Node.js Version Incompatibility (RangeError)

**Frequency**: When deploying VPC Lambda functions with SST v3  
**Error**: `RangeError: Invalid string length` during deployment

**Root Cause**: SST v3 VPC Lambda deployments require **Node.js v24.5.0 specifically**. Other versions crash.

**Symptoms**:
```bash
RangeError: Invalid string length
# Even with small (2-4KB) packages
# Even after cleaning .sst directory
```

**❌ Failing**: Node.js v22.x, v23.x  
**✅ Working**: Node.js v24.5.0

**Solution**:
```bash
nvm install 24.5.0
nvm use 24.5.0
nvm alias default 24.5.0
echo "24.5.0" > .nvmrc
```

---

## Recurring Issue #7: SST VPC API Change (vpc.subnets deprecated)

**Frequency**: After SST version updates  
**Error**: `The "vpc.subnets" property has been renamed to "vpc.privateSubnets"`

**Quick Fix**:
```typescript
// ❌ Old
vpc: { subnets: subnetIds }

// ✅ New  
vpc: { privateSubnets: subnetIds }
```

---

## Current Status

### What We've Documented  
- ✅ Handler path must match pyproject.toml package name
- ✅ All `__init__.py` files required
- ✅ Must add functions to workspace in root pyproject.toml
- ✅ Use `sst.aws.Function` not raw Pulumi
- ✅ Node.js v24.5.0 required for VPC Lambda
- ✅ Check `.sst/artifacts/` to verify package structure
- ✅ `vpc.privateSubnets` (not `subnets`)

### Prevention Checklist (Updated)
- [ ] `functions/pyproject.toml` exists with `[build-system]`
- [ ] `functions/__init__.py`, `functions/src/__init__.py`, `functions/src/handlers/__init__.py` exist
- [ ] `functions` added to `[tool.uv.workspace]` in root `pyproject.toml`
- [ ] Using `sst.aws.Function` not `aws.lambda.Function`
- [ ] Node.js v24.5.0 (`node --version`)
- [ ] Handler path matches package name from pyproject.toml (hyphens → underscores)
- [ ] VPC config uses `privateSubnets` not `subnets`
- [ ] No `.venv` in `functions/` directory
- [ ] Verified package structure in `.sst/artifacts/FunctionName-src/`

## Next Steps

1. **Immediate**: Clean all artifacts and try fresh deploy
2. **Short-term**: Create pre-deploy automation script
3. **Long-term**: Consider switching to pip-based workflow if UV issues persist

## Alternative: Use Pip Instead

If UV continues to be problematic, SST works more reliably with pip:

```typescript
// In sst.config.ts or application.ts
const myFunction = new sst.aws.Function("MyFunction", {
  handler: "functions/src/handlers/handler.handler",
  runtime: "python3.12",
  // SST will use pip + requirements.txt automatically
});
```

Remove `pyproject.toml` from functions/ and keep only `requirements.txt` with pinned versions.

## Summary

**The Core Problem**: SST + UV integration is fragile because:
- UV's local artifacts interfere with SST's clean builds
- Exit code handling differences
- Subprocess environment differences

**The Solution**: Rigorous artifact cleaning + standard structure + pre-deploy automation

**When to Switch to Pip**: If these issues persist after following all solutions above.



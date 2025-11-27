# Functions Directory Migration to packages/functions

**Date:** 2025-01-XX  
**Reason:** Align with SST v3 monorepo template specification  
**Reference:** https://github.com/sst/monorepo-template

## Summary

Migrated `functions/` directory to `packages/functions/` per SST monorepo template standards. The `daw_functions` symlink was removed, and any real `daw_functions` directory was archived.

## Changes Made

### ✅ Configuration Files Updated

1. **`pyproject.toml`**
   - Updated workspace member: `"functions"` → `"packages/functions"`

2. **`infra/search-api.ts`**
   - Updated handler paths to use Python import style (not file path style):
     - `"daw_functions/src/search_handler.lambda_handler"` → `"daw_functions.src.search_handler.lambda_handler"`
     - `"daw_functions/src/alternatives_handler.lambda_handler"` → `"daw_functions.src.alternatives_handler.lambda_handler"`
     - `"daw_functions/src/drug_detail_handler.lambda_handler"` → `"daw_functions.src.drug_detail_handler.lambda_handler"`

3. **`infra/sync.ts`**
   - Updated handler path:
     - `"daw_functions/src/handlers/drug_loader.lambda_handler"` → `"daw_functions.src.handlers.drug_loader.lambda_handler"`

4. **`package.json`**
   - Updated scripts to reference `packages/functions/`:
     - `lint`: `functions/` → `packages/functions/`
     - `type-check`: `functions/` → `packages/functions/`

### ✅ Python Imports

- **No changes needed** - Python imports use package name (`daw_functions`) from `pyproject.toml`, not directory name
- Imports remain: `from daw_functions.src.config.llm_config import ...`

## Migration Steps

### Run the Migration Script

```bash
python3 scripts/migrate_functions_to_packages.py
```

This script will:
1. ✅ Move `functions/` → `packages/functions/`
2. ✅ Archive real `daw_functions/` directory (if exists) → `.archive/daw_functions/`
3. ✅ Remove `daw_functions` symlink (if exists)

### Manual Steps (if script fails)

```bash
# 1. Move functions directory
mv functions packages/functions

# 2. Archive daw_functions if it's a real directory (not symlink)
if [ -d daw_functions ] && [ ! -L daw_functions ]; then
    mkdir -p .archive
    mv daw_functions .archive/
fi

# 3. Remove symlink if it exists
if [ -L daw_functions ]; then
    rm daw_functions
fi
```

## Verification

After migration, verify:

1. ✅ `packages/functions/` exists and contains all files
2. ✅ `packages/functions/pyproject.toml` has `name = "daw_functions"`
3. ✅ Handler paths in infra files use Python import style (`daw_functions.src.*`)
4. ✅ Python imports use `daw_functions.src.*` (package name, not directory)
5. ✅ `daw_functions` symlink is removed
6. ✅ Any real `daw_functions` directory is in `.archive/`

## Testing

```bash
# Test SST deployment
sst deploy

# Or test locally
sst dev
```

## Important Notes

### Handler Path Format

**✅ CORRECT** (Python import style):
```typescript
handler: "daw_functions.src.search_handler.lambda_handler"
```

**❌ WRONG** (File path style):
```typescript
handler: "daw_functions/src/search_handler.lambda_handler"
```

The handler path uses the **package name** from `pyproject.toml` (with hyphens converted to underscores), not the directory path.

### Package Name vs Directory Name

- **Directory name**: `packages/functions/` (matches SST monorepo template)
- **Package name**: `daw_functions` (from `pyproject.toml`, used in imports and handlers)
- **Handler path**: Uses package name: `daw_functions.src.*`

## Rollback

If migration causes issues:

```bash
# Restore from archive
mv .archive/daw_functions functions

# Revert pyproject.toml
# Change "packages/functions" back to "functions"

# Revert handler paths in infra files
# Change "daw_functions.src.*" back to "daw_functions/src/*"
```

## Files Modified

- `pyproject.toml` - Workspace member updated
- `infra/search-api.ts` - Handler paths updated (3 functions)
- `infra/sync.ts` - Handler path updated
- `package.json` - Script paths updated
- `scripts/migrate_functions_to_packages.py` - Migration script created

## Files Moved

- `functions/` → `packages/functions/`
- `daw_functions/` (if real directory) → `.archive/daw_functions/`

## Files Removed

- `daw_functions` symlink (if existed)


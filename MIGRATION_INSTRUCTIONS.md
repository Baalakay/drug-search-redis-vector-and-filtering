# Migration Instructions

I've updated all configuration files. To complete the migration, please run:

```bash
python3 scripts/complete_migration.py
```

This script will:
1. Copy `functions/` → `packages/functions/`
2. Archive `daw_functions/` (if real directory) → `.archive/daw_functions/`
3. Remove `daw_functions` symlink (if exists)
4. Remove original `functions/` directory

## Alternative Manual Steps

If the script doesn't work, run these commands manually:

```bash
# 1. Copy functions to packages/functions
cp -r functions packages/functions

# 2. Archive daw_functions if it's a real directory (not symlink)
if [ -d daw_functions ] && [ ! -L daw_functions ]; then
    mkdir -p .archive
    mv daw_functions .archive/
fi

# 3. Remove symlink if it exists
if [ -L daw_functions ]; then
    rm daw_functions
fi

# 4. Remove original functions directory
rm -rf functions
```

## Verification

After migration, verify:
- ✅ `packages/functions/` exists with all files
- ✅ `functions/` is removed
- ✅ `daw_functions` symlink/directory is removed/archived
- ✅ Run `sst deploy` or `sst dev` to test


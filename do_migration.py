#!/usr/bin/env python3
import os
import shutil
from pathlib import Path

root = Path('/workspaces/DAW')
functions_src = root / 'functions'
packages_functions_dst = root / 'packages' / 'functions'
daw_functions = root / 'daw_functions'
archive_dir = root / '.archive'

print('🔄 Starting migration...')

# Ensure packages exists
(root / 'packages').mkdir(exist_ok=True)

# Copy functions to packages/functions
if packages_functions_dst.exists():
    print(f'⚠️  Removing existing {packages_functions_dst}')
    shutil.rmtree(packages_functions_dst)

print(f'📦 Copying {functions_src} to {packages_functions_dst}...')
shutil.copytree(str(functions_src), str(packages_functions_dst))
print('✅ Copied functions/ to packages/functions/')

# Handle daw_functions
if daw_functions.exists():
    if daw_functions.is_symlink():
        print(f'🔗 Removing symlink: {daw_functions}')
        daw_functions.unlink()
        print('✅ Removed daw_functions symlink')
    else:
        print(f'📁 Archiving real directory: {daw_functions}')
        archive_dir.mkdir(exist_ok=True)
        archive_target = archive_dir / 'daw_functions'
        if archive_target.exists():
            shutil.rmtree(archive_target)
        shutil.move(str(daw_functions), str(archive_target))
        print('✅ Archived daw_functions to .archive/')

# Remove original functions
print(f'🗑️  Removing original {functions_src}...')
shutil.rmtree(functions_src)
print('✅ Removed original functions/')

print('\n✅ Migration complete!')
file_count = sum(1 for _ in packages_functions_dst.rglob('*') if _.is_file())
print(f'   ✅ packages/functions/ has {file_count} files')


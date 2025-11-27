#!/usr/bin/env python3
"""
Migration script to move functions/ to packages/functions/ per SST monorepo template.

This script:
1. Moves functions/ directory to packages/functions/
2. Archives daw_functions directory (if it exists as a real directory) to .archive/
3. Removes daw_functions symlink (if it exists)
"""

import os
import shutil
import sys
from pathlib import Path

def main():
    root = Path(__file__).parent.parent
    functions_dir = root / "functions"
    packages_functions_dir = root / "packages" / "functions"
    daw_functions_symlink = root / "daw_functions"
    archive_dir = root / ".archive"
    
    print("🔄 Migrating functions/ to packages/functions/ per SST monorepo template...")
    
    # Step 1: Check if functions/ exists
    if not functions_dir.exists():
        print("❌ Error: functions/ directory does not exist!")
        return 1
    
    # Step 2: Check if packages/functions/ already exists
    if packages_functions_dir.exists():
        print(f"⚠️  Warning: {packages_functions_dir} already exists!")
        response = input("Overwrite? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            return 1
        shutil.rmtree(packages_functions_dir)
    
    # Step 3: Ensure packages/ directory exists
    packages_dir = root / "packages"
    packages_dir.mkdir(exist_ok=True)
    
    # Step 4: Move functions/ to packages/functions/
    print(f"📦 Moving {functions_dir} to {packages_functions_dir}...")
    shutil.move(str(functions_dir), str(packages_functions_dir))
    print("✅ Moved functions/ to packages/functions/")
    
    # Step 5: Handle daw_functions symlink/directory
    if daw_functions_symlink.exists():
        # Check if it's a symlink
        if daw_functions_symlink.is_symlink():
            print(f"🔗 Found symlink: {daw_functions_symlink}")
            target = os.readlink(daw_functions_symlink)
            print(f"   Points to: {target}")
            print(f"🗑️  Removing symlink...")
            daw_functions_symlink.unlink()
            print("✅ Removed daw_functions symlink")
        else:
            # It's a real directory
            print(f"📁 Found real directory: {daw_functions_symlink}")
            archive_dir.mkdir(exist_ok=True)
            archive_target = archive_dir / "daw_functions"
            if archive_target.exists():
                shutil.rmtree(archive_target)
            print(f"📦 Archiving to {archive_target}...")
            shutil.move(str(daw_functions_symlink), str(archive_target))
            print("✅ Archived daw_functions directory to .archive/")
    
    print("\n✅ Migration complete!")
    print("\nNext steps:")
    print("1. Verify packages/functions/ contains all files")
    print("2. Run: sst deploy (or sst dev) to test")
    print("3. If everything works, you can delete .archive/daw_functions if desired")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())


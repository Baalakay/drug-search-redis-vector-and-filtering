#!/usr/bin/env python3
"""
Complete migration script - moves functions/ to packages/functions/
and handles daw_functions symlink/directory
"""
import os
import shutil
import sys
from pathlib import Path

def main():
    root = Path(__file__).parent.parent
    functions_src = root / "functions"
    packages_functions_dst = root / "packages" / "functions"
    daw_functions = root / "daw_functions"
    archive_dir = root / ".archive"
    
    print("🔄 Starting complete migration...")
    print(f"   Source: {functions_src}")
    print(f"   Destination: {packages_functions_dst}")
    
    # Step 1: Verify source exists
    if not functions_src.exists():
        print("❌ Error: functions/ directory does not exist!")
        return 1
    
    # Step 2: Create packages directory if needed
    packages_dir = root / "packages"
    packages_dir.mkdir(exist_ok=True)
    
    # Step 3: Remove destination if exists
    if packages_functions_dst.exists():
        print(f"⚠️  Removing existing {packages_functions_dst}...")
        shutil.rmtree(packages_functions_dst)
    
    # Step 4: Copy functions to packages/functions
    print(f"📦 Copying {functions_src} to {packages_functions_dst}...")
    shutil.copytree(functions_src, packages_functions_dst)
    print("✅ Copied functions/ to packages/functions/")
    
    # Step 5: Handle daw_functions
    if daw_functions.exists():
        if daw_functions.is_symlink():
            print(f"🔗 Found symlink: {daw_functions}")
            target = os.readlink(daw_functions)
            print(f"   Points to: {target}")
            print(f"🗑️  Removing symlink...")
            daw_functions.unlink()
            print("✅ Removed daw_functions symlink")
        else:
            # Real directory
            print(f"📁 Found real directory: {daw_functions}")
            archive_dir.mkdir(exist_ok=True)
            archive_target = archive_dir / "daw_functions"
            if archive_target.exists():
                print(f"⚠️  Removing existing archive target...")
                shutil.rmtree(archive_target)
            print(f"📦 Archiving to {archive_target}...")
            shutil.move(str(daw_functions), str(archive_target))
            print("✅ Archived daw_functions directory to .archive/")
    else:
        print("ℹ️  daw_functions does not exist (already removed or never existed)")
    
    # Step 6: Remove original functions directory
    print(f"🗑️  Removing original {functions_src}...")
    shutil.rmtree(functions_src)
    print("✅ Removed original functions/ directory")
    
    print("\n✅ Migration complete!")
    print("\nVerification:")
    if packages_functions_dst.exists():
        file_count = sum(1 for _ in packages_functions_dst.rglob("*") if _.is_file())
        print(f"   ✅ packages/functions/ exists with {file_count} files")
    else:
        print("   ❌ packages/functions/ does not exist!")
        return 1
    
    if not functions_src.exists():
        print("   ✅ Original functions/ removed")
    else:
        print("   ⚠️  Original functions/ still exists")
    
    if not daw_functions.exists():
        print("   ✅ daw_functions symlink/directory removed/archived")
    else:
        print("   ⚠️  daw_functions still exists")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())


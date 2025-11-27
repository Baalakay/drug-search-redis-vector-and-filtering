#!/usr/bin/env python3
"""
Export Sample Data from All FDB Tables

This script connects to the Aurora FDB database and exports 10 random rows
from each table to CSV files in database/exports/csv/

This helps discover schema and find columns like indication, dosage_form, etc.

Usage:
    python3 scripts/export_fdb_samples.py
"""

import mysql.connector
import csv
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Database connection config
DB_CONFIG = {
    'host': 'daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com',
    'user': 'dawadmin',
    'password': '0k(ucbMbiwcW$byc&FUp53c2eUQE!Fi5',
    'database': 'fdb'
}

# Output directory
OUTPUT_DIR = Path('database/exports/csv')

def get_all_tables(conn) -> List[Dict[str, Any]]:
    """Get all tables in FDB database ordered by row count"""
    print("\n📋 Fetching table list from FDB...")
    
    cursor = conn.cursor()
    query = """
    SELECT 
        table_name,
        table_rows,
        ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb
    FROM information_schema.tables
    WHERE table_schema = 'fdb'
    ORDER BY table_rows DESC
    """
    
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    
    # Convert to list of dicts
    tables = [
        {'table_name': row[0], 'table_rows': row[1], 'size_mb': row[2]}
        for row in rows
    ]
    
    print(f"   ✅ Found {len(tables)} tables")
    return tables

def export_table_sample(conn, table_name: str, output_dir: Path) -> bool:
    """Export 10 random rows from a table to CSV"""
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Get 10 random rows
        # Use ORDER BY RAND() LIMIT 10 for simplicity
        query = f"""
        SELECT * 
        FROM `{table_name}` 
        ORDER BY RAND() 
        LIMIT 10
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print(f"      ⚠️  Table {table_name} is empty")
            cursor.close()
            return False
        
        # Write to CSV
        csv_file = output_dir / f"{table_name}.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        
        print(f"      ✅ {table_name}.csv ({len(rows)} rows, {len(rows[0].keys())} columns)")
        cursor.close()
        return True
        
    except Exception as e:
        print(f"      ❌ {table_name}: {str(e)}")
        return False

def main():
    print("=" * 70)
    print("FDB TABLE SAMPLE EXPORT")
    print("=" * 70)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n📁 Output directory: {OUTPUT_DIR.absolute()}")
    
    # Connect to database
    print("\n🔗 Connecting to Aurora FDB...")
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        print(f"   ✅ Connected to {DB_CONFIG['host']}")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        sys.exit(1)
    
    # Get all tables
    tables = get_all_tables(conn)
    
    # Export samples
    print(f"\n📤 Exporting samples from {len(tables)} tables...")
    print()
    
    success_count = 0
    fail_count = 0
    empty_count = 0
    
    for i, table_info in enumerate(tables, 1):
        table_name = table_info['table_name']
        row_count = table_info['table_rows']
        size_mb = table_info['size_mb']
        
        print(f"   [{i:3d}/{len(tables)}] {table_name} (rows: {row_count:,}, size: {size_mb} MB)")
        
        result = export_table_sample(conn, table_name, OUTPUT_DIR)
        
        if result:
            success_count += 1
        else:
            # Check if it's empty
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
            actual_count = cursor.fetchone()[0]
            cursor.close()
            
            if actual_count == 0:
                empty_count += 1
            else:
                fail_count += 1
    
    # Close connection
    conn.close()
    
    # Summary
    print()
    print("=" * 70)
    print("EXPORT COMPLETE")
    print("=" * 70)
    print(f"   ✅ Successful exports: {success_count}")
    print(f"   ⚠️  Empty tables: {empty_count}")
    print(f"   ❌ Failed exports: {fail_count}")
    print(f"\n📁 CSV files saved to: {OUTPUT_DIR.absolute()}")
    print()
    print("💡 Next steps:")
    print("   1. Search CSV files for columns like 'indication', 'dosage_form', etc.")
    print("   2. Use grep: grep -r 'CREAM\\|GEL\\|INJECTION' database/exports/csv/")
    print("   3. Use grep: grep -r -i 'indication\\|indic' database/exports/csv/")
    print()

if __name__ == '__main__':
    main()


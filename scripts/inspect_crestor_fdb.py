#!/usr/bin/env python3
"""
Inspect Crestor data in FDB to understand drug_class and indication sources
"""
import sys
import os

# Add packages to path
sys.path.insert(0, '/workspaces/DAW/packages/core/src')

import mysql.connector
import boto3
from tabulate import tabulate

def get_db_password():
    """Get database password from Secrets Manager"""
    sm = boto3.client('secretsmanager', region_name='us-east-1')
    return sm.get_secret_value(SecretId='DAW-DB-Password-dev')['SecretString']

def connect_to_aurora():
    """Connect to Aurora MySQL"""
    return mysql.connector.connect(
        host='daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com',
        user='dawadmin',
        password=get_db_password(),
        database='fdb'
    )

def inspect_crestor():
    """Inspect Crestor data from multiple FDB tables"""
    conn = connect_to_aurora()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Get CRESTOR records from rndc14
    print("\n" + "="*80)
    print("1. CRESTOR RECORDS FROM rndc14 (Main Drug Table)")
    print("="*80 + "\n")
    
    cursor.execute("""
        SELECT NDC, LN, BN, INNOV, GCN_SEQNO, DF, DEA, OBSDTEC, LBLRID
        FROM rndc14 
        WHERE UPPER(BN) = 'CRESTOR' 
        LIMIT 5
    """)
    records = cursor.fetchall()
    
    for row in records:
        print(f"NDC: {row['NDC']}")
        print(f"  Drug Name (LN): {row['LN']}")
        print(f"  Brand (BN): {row['BN']}")
        print(f"  INNOV: {row['INNOV']} (1=Brand, 0=Generic)")
        print(f"  GCN_SEQNO: {row['GCN_SEQNO']}")
        print(f"  Dosage Form (DF): {row['DF']}")
        print(f"  DEA: {row['DEA']}")
        print(f"  OBSDTEC: {row['OBSDTEC']} (Obsolete Date - NULL = Active)")
        print(f"  LBLRID: {row['LBLRID']} (Labeler ID)")
        print()
    
    # Get one GCN for further investigation
    gcn = records[0]['GCN_SEQNO']
    
    # 2. Get GCN classification data
    print("\n" + "="*80)
    print(f"2. GCN CLASSIFICATION DATA from rgcnseq4 (GCN={gcn})")
    print("="*80 + "\n")
    
    cursor.execute("""
        SELECT 
            GCN_SEQNO, GNN60, HICL_SEQNO, HIC3, GCRT, STR, STR60
        FROM rgcnseq4 
        WHERE GCN_SEQNO = %s
        LIMIT 1
    """, (gcn,))
    gcn_data = cursor.fetchone()
    
    if gcn_data:
        print(f"GCN_SEQNO: {gcn_data['GCN_SEQNO']}")
        print(f"  GNN60 (Generic Name): {gcn_data['GNN60']}")
        print(f"  HICL_SEQNO: {gcn_data['HICL_SEQNO']} (Hierarchical Ingredient Code List)")
        print(f"  HIC3: {gcn_data['HIC3']} (Therapeutic Class Code)")
        print(f"  GCRT (Route): {gcn_data['GCRT']}")
        print(f"  STR (Strength): {gcn_data['STR']}")
        print(f"  STR60: {gcn_data['STR60']}")
        print()
        
        hicl_seqno = gcn_data['HICL_SEQNO']
        hic3 = gcn_data['HIC3']
    else:
        print(f"No GCN data found for GCN_SEQNO={gcn}")
        return
    
    # 3. Get therapeutic class description
    print("\n" + "="*80)
    print(f"3. THERAPEUTIC CLASS from rhclass (HIC3={hic3})")
    print("="*80 + "\n")
    
    cursor.execute("""
        SELECT HIC3, HIC3DESC
        FROM rhclass 
        WHERE HIC3 = %s
    """, (hic3,))
    class_data = cursor.fetchone()
    
    if class_data:
        print(f"HIC3: {class_data['HIC3']}")
        print(f"  Description: {class_data['HIC3DESC']}")
        print()
    else:
        print(f"No class data found for HIC3={hic3}")
    
    # 4. Get indication data
    print("\n" + "="*80)
    print(f"4. INDICATIONS from rdlim14 (GCN_SEQNO={gcn})")
    print("="*80 + "\n")
    
    cursor.execute("""
        SELECT INDICID, INDICTYPE, RELTYPE
        FROM rdlim14
        WHERE GCN_SEQNO = %s
        LIMIT 10
    """, (gcn,))
    indic_data = cursor.fetchall()
    
    if indic_data:
        print(f"Found {len(indic_data)} indication records:")
        for row in indic_data:
            # Get indication description
            cursor.execute("SELECT INDICDESC FROM rdindc WHERE INDICID = %s", (row['INDICID'],))
            desc = cursor.fetchone()
            desc_text = desc['INDICDESC'] if desc else 'Unknown'
            
            print(f"  INDICID: {row['INDICID']}")
            print(f"    Description: {desc_text}")
            print(f"    Type: {row['INDICTYPE']}")
            print(f"    Relationship: {row['RELTYPE']}")
            print()
    else:
        print(f"No indication data found for GCN_SEQNO={gcn}")
    
    # 5. Check OBSDTEC for active/inactive drugs
    print("\n" + "="*80)
    print("5. ACTIVE vs INACTIVE DRUGS (OBSDTEC field)")
    print("="*80 + "\n")
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_crestor,
            SUM(CASE WHEN OBSDTEC IS NULL THEN 1 ELSE 0 END) as active_count,
            SUM(CASE WHEN OBSDTEC IS NOT NULL THEN 1 ELSE 0 END) as inactive_count
        FROM rndc14 
        WHERE UPPER(BN) = 'CRESTOR'
    """)
    counts = cursor.fetchone()
    
    print(f"Total CRESTOR records: {counts['total_crestor']}")
    print(f"  Active (OBSDTEC IS NULL): {counts['active_count']}")
    print(f"  Inactive (OBSDTEC IS NOT NULL): {counts['inactive_count']}")
    print()
    
    # 6. Get sample rosuvastatin generics
    print("\n" + "="*80)
    print("6. ROSUVASTATIN GENERICS (Same GCN, INNOV=0)")
    print("="*80 + "\n")
    
    cursor.execute("""
        SELECT NDC, LN, BN, INNOV, OBSDTEC
        FROM rndc14 
        WHERE GCN_SEQNO = %s AND INNOV = '0'
        LIMIT 5
    """, (gcn,))
    generics = cursor.fetchall()
    
    for row in generics:
        status = "ACTIVE" if row['OBSDTEC'] is None else f"INACTIVE ({row['OBSDTEC']})"
        print(f"NDC: {row['NDC']} - {status}")
        print(f"  Drug Name: {row['LN']}")
        print(f"  Brand: {row['BN']}")
        print()
    
    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        inspect_crestor()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


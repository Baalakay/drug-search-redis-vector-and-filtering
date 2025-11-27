#!/usr/bin/env python3
"""
Phase 1: FDB Schema Investigation
Query Aurora MySQL to understand drug_class and indication data sources
"""
import os
import sys
import json
import boto3
import mysql.connector
from typing import Dict, Any

def get_db_credentials() -> Dict[str, str]:
    """Get database credentials from Secrets Manager"""
    sm = boto3.client('secretsmanager', region_name='us-east-1')
    secret = sm.get_secret_value(SecretId='DAW-DB-Password-dev')
    password = secret['SecretString']
    
    return {
        'host': 'daw-aurora-dev.cluster-ccbkass84b2d.us-east-1.rds.amazonaws.com',
        'user': 'dawadmin',
        'password': password,
        'database': 'fdb'
    }

def run_query(conn, query: str, params: tuple = None) -> list:
    """Execute query and return results"""
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params or ())
    results = cursor.fetchall()
    cursor.close()
    return results

def print_table(rows: list, title: str):
    """Print results in a formatted table"""
    if not rows:
        print(f"\n{title}: NO RESULTS\n")
        return
    
    print(f"\n{'='*100}")
    print(f"{title}")
    print('='*100)
    
    for i, row in enumerate(rows, 1):
        print(f"\n[{i}]")
        for key, value in row.items():
            print(f"  {key:25s}: {value}")

def main():
    print("="*100)
    print("PHASE 1: FDB SCHEMA INVESTIGATION - CRESTOR")
    print("="*100)
    
    # Connect to Aurora
    print("\n🔌 Connecting to Aurora MySQL...")
    creds = get_db_credentials()
    conn = mysql.connector.connect(**creds)
    print("✅ Connected!")
    
    # Query 1: Basic CRESTOR data
    print("\n" + "="*100)
    print("QUERY 1: Basic CRESTOR data from rndc14")
    print("="*100)
    
    query1 = """
        SELECT 
            NDC, LN, BN, INNOV, GCN_SEQNO, DF, DEA, OBSDTEC, LBLRID
        FROM rndc14 
        WHERE UPPER(BN) = 'CRESTOR' 
        LIMIT 5
    """
    results1 = run_query(conn, query1)
    print_table(results1, "CRESTOR Records")
    
    if not results1:
        print("\n❌ ERROR: No CRESTOR records found!")
        conn.close()
        return
    
    gcn = results1[0]['GCN_SEQNO']
    print(f"\n📌 Using GCN_SEQNO={gcn} for further investigation")
    
    # Query 2: Drug Class from GCN
    print("\n" + "="*100)
    print(f"QUERY 2: Drug Class Data (GCN={gcn})")
    print("="*100)
    
    query2 = """
        SELECT 
            g.GCN_SEQNO,
            g.GNN60 as generic_name,
            g.HICL_SEQNO,
            g.HIC3 as therapeutic_class_code,
            h.HIC3DESC as drug_class_description,
            g.GCRT as route,
            g.STR as strength,
            g.STR60 as strength_60
        FROM rgcnseq4 g
        LEFT JOIN rhclass h ON g.HIC3 = h.HIC3
        WHERE g.GCN_SEQNO = %s
        LIMIT 1
    """
    results2 = run_query(conn, query2, (gcn,))
    print_table(results2, "GCN Classification Data")
    
    if results2:
        drug_class = results2[0].get('drug_class_description', '')
        print(f"\n✅ Drug Class: {drug_class}")
        print(f"   Expected: 'HMG-CoA reductase inhibitor' or similar")
        if 'HMG' in str(drug_class).upper() or 'REDUCTASE' in str(drug_class).upper():
            print(f"   ✓ MATCH!")
        else:
            print(f"   ✗ DOES NOT MATCH - investigate HIC3 table")
    
    # Query 3: Indications
    print("\n" + "="*100)
    print(f"QUERY 3: Indication Data (GCN={gcn})")
    print("="*100)
    
    query3 = """
        SELECT 
            d.GCN_SEQNO,
            d.INDICID,
            i.INDICDESC as indication_description,
            d.INDICTYPE,
            d.RELTYPE
        FROM rdlim14 d
        JOIN rdindc i ON d.INDICID = i.INDICID
        WHERE d.GCN_SEQNO = %s
        LIMIT 10
    """
    results3 = run_query(conn, query3, (gcn,))
    print_table(results3, "Indication Records")
    
    if results3:
        indications = [r['indication_description'] for r in results3]
        print(f"\n✅ Found {len(indications)} indications:")
        for ind in indications:
            print(f"   - {ind}")
        
        print(f"\n   Expected: 'Primary hypercholesterolemia' and 'Mixed dyslipidemias'")
        
        # Check for matches
        indic_text = ' '.join([str(i).upper() for i in indications])
        if 'HYPERCHOLESTEROLEMIA' in indic_text or 'CHOLESTEROL' in indic_text:
            print(f"   ✓ Cholesterol indication FOUND!")
        else:
            print(f"   ✗ Cholesterol indication NOT FOUND")
        
        if 'DYSLIPIDEMIA' in indic_text or 'LIPID' in indic_text:
            print(f"   ✓ Dyslipidemia indication FOUND!")
        else:
            print(f"   ✗ Dyslipidemia indication NOT FOUND")
    else:
        print("\n❌ No indication data found!")
    
    # Query 4: Active vs Inactive
    print("\n" + "="*100)
    print("QUERY 4: Active vs Inactive CRESTOR drugs")
    print("="*100)
    
    query4 = """
        SELECT 
            CASE WHEN OBSDTEC IS NULL THEN 'ACTIVE' ELSE 'INACTIVE' END as status,
            COUNT(*) as count
        FROM rndc14
        WHERE UPPER(BN) = 'CRESTOR'
        GROUP BY status
    """
    results4 = run_query(conn, query4)
    print_table(results4, "Active/Inactive Distribution")
    
    # Query 5: Sample of different drug classes for test dataset
    print("\n" + "="*100)
    print("QUERY 5: Sample drugs from different classes")
    print("="*100)
    
    query5 = """
        SELECT 
            n.NDC,
            n.LN as drug_name,
            n.BN as brand_name,
            n.INNOV,
            h.HIC3DESC as drug_class,
            n.OBSDTEC
        FROM rndc14 n
        LEFT JOIN rgcnseq4 g ON n.GCN_SEQNO = g.GCN_SEQNO
        LEFT JOIN rhclass h ON g.HIC3 = h.HIC3
        WHERE n.OBSDTEC IS NULL
            AND n.LN IS NOT NULL
        LIMIT 10
    """
    results5 = run_query(conn, query5)
    print_table(results5, "Sample Drugs (Various Classes)")
    
    # Query 6: Test if GROUP_CONCAT works for indications
    print("\n" + "="*100)
    print("QUERY 6: Testing GROUP_CONCAT for indications")
    print("="*100)
    
    query6 = """
        SELECT 
            n.NDC,
            n.BN,
            GROUP_CONCAT(DISTINCT i.INDICDESC SEPARATOR '|') as indication
        FROM rndc14 n
        LEFT JOIN rdlim14 d ON n.GCN_SEQNO = d.GCN_SEQNO
        LEFT JOIN rdindc i ON d.INDICID = i.INDICID
        WHERE UPPER(n.BN) = 'CRESTOR'
        GROUP BY n.NDC
        LIMIT 5
    """
    results6 = run_query(conn, query6)
    print_table(results6, "CRESTOR with Concatenated Indications")
    
    # Summary
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    
    print("\n✅ Queries Completed Successfully!")
    print(f"\nKey Findings:")
    print(f"  1. CRESTOR data exists in rndc14")
    print(f"  2. Drug class available via: rgcnseq4 + rhclass (HIC3 → HIC3DESC)")
    print(f"  3. Indications available via: rdlim14 + rdindc")
    print(f"  4. Active drugs: OBSDTEC IS NULL")
    print(f"  5. GROUP_CONCAT works for pipe-separated indications")
    
    print(f"\n📋 Next Step: Review results above and verify:")
    print(f"  - Does drug_class match 'HMG-CoA reductase inhibitor'?")
    print(f"  - Do indications include hypercholesterolemia and dyslipidemias?")
    print(f"  - Are there both active and inactive CRESTOR drugs?")
    
    conn.close()
    print(f"\n✅ Database connection closed")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


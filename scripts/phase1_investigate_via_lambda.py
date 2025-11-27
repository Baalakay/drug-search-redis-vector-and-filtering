#!/usr/bin/env python3
"""
Phase 1: FDB Investigation via Lambda (no local mysql needed)
Invoke DrugSync Lambda to run investigation queries
"""
import boto3
import json
import sys

lambda_client = boto3.client('lambda', region_name='us-east-1')

def invoke_query(query_name: str, sql: str, params: list = None):
    """Invoke Lambda with custom query"""
    payload = {
        'action': 'investigate_fdb',
        'query_name': query_name,
        'sql': sql,
        'params': params or []
    }
    
    print(f"\n{'='*100}")
    print(f"🔍 {query_name}")
    print('='*100)
    
    response = lambda_client.invoke(
        FunctionName='DAW-DrugSync-dev',
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )
    
    result = json.loads(response['Payload'].read())
    
    if result.get('statusCode') == 200:
        body = json.loads(result['body'])
        if body.get('success'):
            rows = body.get('results', [])
            print(f"\n✅ Found {len(rows)} result(s)")
            
            for i, row in enumerate(rows, 1):
                print(f"\n[{i}]")
                for key, value in row.items():
                    print(f"  {key:30s}: {value}")
            
            return rows
        else:
            print(f"❌ Error: {body.get('error')}")
            return []
    else:
        print(f"❌ Lambda error: {result}")
        return []

def main():
    print("="*100)
    print("PHASE 1: FDB SCHEMA INVESTIGATION via Lambda")
    print("="*100)
    
    # Query 1: Basic CRESTOR data
    query1_sql = """
        SELECT NDC, LN, BN, INNOV, GCN_SEQNO, DF, DEA, OBSDTEC, LBLRID
        FROM rndc14 
        WHERE UPPER(BN) = 'CRESTOR' 
        LIMIT 5
    """
    results1 = invoke_query("Query 1: Basic CRESTOR data", query1_sql)
    
    if not results1:
        print("\n❌ Cannot continue without CRESTOR data")
        return
    
    gcn = results1[0]['GCN_SEQNO']
    print(f"\n📌 Using GCN_SEQNO={gcn} for further investigation")
    
    # Query 2: Drug Class
    query2_sql = """
        SELECT 
            g.GCN_SEQNO,
            g.GNN60 as generic_name,
            g.HIC3 as therapeutic_class_code,
            h.HIC3DESC as drug_class_description,
            g.GCRT as route,
            g.STR as strength
        FROM rgcnseq4 g
        LEFT JOIN rhclass h ON g.HIC3 = h.HIC3
        WHERE g.GCN_SEQNO = %s
        LIMIT 1
    """
    results2 = invoke_query(f"Query 2: Drug Class (GCN={gcn})", query2_sql, [gcn])
    
    if results2:
        drug_class = results2[0].get('drug_class_description', '')
        print(f"\n✅ Drug Class: {drug_class}")
        print(f"   Expected: 'HMG-CoA reductase inhibitor'")
        if 'HMG' in str(drug_class).upper() or 'REDUCTASE' in str(drug_class).upper():
            print(f"   ✓ MATCH!")
        else:
            print(f"   ⚠️  DOES NOT MATCH")
    
    # Query 3: Indications
    query3_sql = """
        SELECT 
            d.INDICID,
            i.INDICDESC as indication_description,
            d.INDICTYPE
        FROM rdlim14 d
        JOIN rdindc i ON d.INDICID = i.INDICID
        WHERE d.GCN_SEQNO = %s
        LIMIT 10
    """
    results3 = invoke_query(f"Query 3: Indications (GCN={gcn})", query3_sql, [gcn])
    
    if results3:
        indications = [r['indication_description'] for r in results3]
        print(f"\n✅ Found {len(indications)} indications")
        
        indic_text = ' '.join([str(i).upper() for i in indications])
        if 'HYPERCHOLESTEROLEMIA' in indic_text or 'CHOLESTEROL' in indic_text:
            print(f"   ✓ Cholesterol indication FOUND")
        if 'DYSLIPIDEMIA' in indic_text:
            print(f"   ✓ Dyslipidemia indication FOUND")
    
    # Query 4: Active vs Inactive
    query4_sql = """
        SELECT 
            CASE WHEN OBSDTEC IS NULL THEN 'ACTIVE' ELSE 'INACTIVE' END as status,
            COUNT(*) as count
        FROM rndc14
        WHERE UPPER(BN) = 'CRESTOR'
        GROUP BY status
    """
    invoke_query("Query 4: Active vs Inactive", query4_sql)
    
    # Query 5: GROUP_CONCAT test
    query5_sql = """
        SELECT 
            n.NDC,
            n.BN,
            GROUP_CONCAT(DISTINCT i.INDICDESC SEPARATOR '|') as indication
        FROM rndc14 n
        LEFT JOIN rdlim14 d ON n.GCN_SEQNO = d.GCN_SEQNO
        LEFT JOIN rdindc i ON d.INDICID = i.INDICID
        WHERE UPPER(n.BN) = 'CRESTOR'
        GROUP BY n.NDC
        LIMIT 3
    """
    invoke_query("Query 5: Concatenated Indications", query5_sql)
    
    print("\n" + "="*100)
    print("✅ PHASE 1 COMPLETE")
    print("="*100)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


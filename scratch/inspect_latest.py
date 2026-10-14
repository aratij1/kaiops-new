import pymysql
import json

conn = pymysql.connect(
    host='127.0.0.1',
    port=3307,
    user='kaiops',
    password='kaiops',
    database='kaiops',
    cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cur:
    cur.execute("SELECT id, service, status, root_cause, customer_impact, recommended_action, confidence, created_at FROM incidents ORDER BY created_at DESC LIMIT 5")
    rows = cur.fetchall()
    print(f"Total found in incidents table: {len(rows)}")
    for r in rows:
        print("="*60)
        print(f"ID: {r['id']}")
        print(f"Service: {r['service']}")
        print(f"Status: {r['status']}")
        print(f"Root Cause: {r['root_cause']}")
        print(f"Impact: {r['customer_impact']}")
        print(f"Recommendation: {r['recommended_action']}")
        print(f"Confidence: {r['confidence']}")
        print(f"Created: {r['created_at']}")
        
    cur.execute("SELECT id, incident_id, status, plan_id, risk_tier FROM approvals ORDER BY created_at DESC LIMIT 5")
    approvals = cur.fetchall()
    print("\nApprovals:")
    for a in approvals:
        print(f"  Approval ID: {a['id']} | Incident: {a['incident_id']} | Status: {a['status']} | Plan: {a['plan_id']} | Risk: {a['risk_tier']}")

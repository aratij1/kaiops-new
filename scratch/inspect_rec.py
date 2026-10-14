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
    print("=== LATEST INCIDENT PROJECTIONS ===")
    cur.execute("SELECT * FROM incident_projections ORDER BY updated_at DESC LIMIT 3")
    for r in cur.fetchall():
        print(f"Incident ID: {r.get('incident_id')}, Status: {r.get('status')}, Lifecycle: {r.get('lifecycle_state')}")
        p = json.loads(r.get('projection_payload') or '{}')
        print(f"  Confidence: {p.get('confidence')}")
        print(f"  Causal claim: {p.get('causal_claim')}")
        print(f"  Impact claim: {p.get('impact_claim')}")
        print(f"  Blocked reasons: {p.get('blocked_reasons')}")
        print(f"  Governed plan ready: {p.get('governed_plan_ready')}")
        print(f"  Recommendation ID: {r.get('recommendation_id')}")

    print("\n=== LATEST APPROVALS ===")
    cur.execute("SELECT * FROM approvals ORDER BY created_at DESC LIMIT 3")
    for r in cur.fetchall():
        print(f"Approval ID: {r.get('id')}, Incident: {r.get('incident_id')}, Status: {r.get('status')}, Plan: {r.get('resolution_plan_id')}")

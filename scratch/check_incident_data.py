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
    cur.execute("SELECT id, service, status, title, ticket_id, payload, created_at FROM incidents WHERE service LIKE '%robot%' OR service LIKE '%rabbitmq%' OR title LIKE '%Robot%' ORDER BY created_at DESC")
    rows = cur.fetchall()
    print("Found in incidents table:", len(rows))
    for r in rows:
        payload = r['payload']
        if isinstance(payload, str):
            payload = json.loads(payload)
        print("="*60)
        print("ID:", r['id'])
        print("Service:", r['service'])
        print("Status:", r['status'])
        print("Title:", r['title'])
        print("Ticket:", r['ticket_id'])
        if isinstance(payload, dict):
            print("Root Cause:", payload.get('root_cause') or payload.get('rca'))
            print("Impact:", payload.get('customer_impact') or payload.get('impact'))
            print("Recommendation:", payload.get('recommended_action') or payload.get('recommendation'))
            print("Confidence:", payload.get('confidence'))
            print("Plan:", payload.get('execution_plan'))

    print("\n" + "=" * 60)
    cur.execute("SELECT incident_id, service, status, projection_payload FROM incident_projections WHERE service LIKE '%robot%' OR service LIKE '%rabbitmq%' ORDER BY created_at DESC")
    p_rows = cur.fetchall()
    print("Found in incident_projections table:", len(p_rows))
    for p in p_rows:
        payload = p['projection_payload']
        if isinstance(payload, str):
            payload = json.loads(payload)
        print("-" * 50)
        print("Incident ID:", p['incident_id'], "| Service:", p['service'], "| Status:", p['status'])
        if isinstance(payload, dict):
            print("  Root Cause:", payload.get('root_cause') or payload.get('rca_summary'))
            print("  Impact:", payload.get('customer_impact') or payload.get('impact_summary'))
            print("  Recommendation:", payload.get('recommended_action'))
            print("  Plan ID:", (payload.get('execution_plan') or {}).get('plan_id'))

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
    cur.execute("SELECT id, title, service, status, payload, created_at FROM incidents WHERE title LIKE '%Checkout%' ORDER BY created_at DESC LIMIT 1")
    inc = cur.fetchone()
    if inc:
        print("INCIDENT ID:", inc['id'])
        print("STATUS:", inc['status'])
        print("SERVICE:", inc['service'])
        
        cur.execute("SELECT event_type, created_at, payload FROM incident_events WHERE incident_id=%s AND event_type='incident.recommendation.generated'", (inc['id'],))
        evt = cur.fetchone()
        if evt:
            p = evt['payload']
            if isinstance(p, str):
                p = json.loads(p)
            print("\nRECOMMENDATION EVENT:")
            print("Root cause:", p.get('root_cause'))
            print("Impact:", p.get('impact'))
            print("Recommended action:", p.get('recommended_action'))
            print("Approval readiness:", p.get('approval_readiness'))
            plan = p.get('execution_plan') or {}
            print("Plan execution_ready:", plan.get('execution_ready'))
            print("Plan readiness_blocks:", plan.get('readiness_blocks'))
            print("Plan commands:", plan.get('commands'))

        cur.execute("SELECT projection_payload FROM incident_projections WHERE incident_id=%s", (inc['id'],))
        proj = cur.fetchone()
        if proj:
            pp = proj['projection_payload']
            if isinstance(pp, str):
                pp = json.loads(pp)
            print("\nPROJECTION PAYLOAD:")
            print("Status:", pp.get('status'))
            print("RCA status:", pp.get('rca_status'))
            print("Resolution:", pp.get('resolution'))

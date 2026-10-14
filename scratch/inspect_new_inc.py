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

incident_id = 'a1a9886d836b42eb9a1913045d85f5fa'

with conn.cursor() as cur:
    cur.execute("SELECT event_type, created_at, payload FROM incident_events WHERE incident_id=%s AND event_type='incident.recommendation.generated'", (incident_id,))
    row = cur.fetchone()
    if row:
        payload = row['payload']
        if isinstance(payload, str):
            payload = json.loads(payload)
        print("Root Cause:", payload.get('root_cause'))
        print("Impact:", payload.get('impact'))
        print("Recommended Action:", payload.get('recommended_action'))
        print("Approval Readiness:", payload.get('approval_readiness'))
        print("Execution Plan:", json.dumps(payload.get('execution_plan'), indent=2))

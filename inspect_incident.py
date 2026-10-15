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

import sys

with conn.cursor() as cur:
    if len(sys.argv) > 1:
        incident_id = sys.argv[1]
    else:
        cur.execute("SELECT id FROM incidents WHERE service LIKE '%rabbit%' ORDER BY created_at DESC LIMIT 1")
        row = cur.fetchone()
        incident_id = row['id'] if row else '92a4da4f664e4b1fbff251d92bb4966b'

with conn.cursor() as cur:
    print(f"=== FULL INVESTIGATION FOR INCIDENT {incident_id} ===")
    cur.execute("SELECT * FROM incidents WHERE id=%s", (incident_id,))
    inc = cur.fetchone()
    print("Incident row:")
    for k, v in inc.items():
        if k == 'payload':
            print(f"  payload: {json.dumps(json.loads(v), indent=2)[:1000]}...")
        else:
            print(f"  {k}: {v}")

    print("\n--- APPROVALS ---")
    cur.execute("SELECT * FROM approvals WHERE incident_id=%s", (incident_id,))
    for row in cur.fetchall():
        for k, v in row.items():
            print(f"  {k}: {v}")

    print("\n--- ACTIONS ---")
    cur.execute("SELECT * FROM actions WHERE incident_id=%s", (incident_id,))
    for row in cur.fetchall():
        for k, v in row.items():
            print(f"  {k}: {v}")

    print("\n--- INCIDENT EVENTS ---")
    cur.execute("SELECT event_type, created_at, payload FROM incident_events WHERE incident_id=%s ORDER BY created_at ASC", (incident_id,))
    for row in cur.fetchall():
        print(f"  [{row['created_at']}] {row['event_type']}: {str(row['payload'])[:200]}")

    print("\n--- REMEDIATION OUTCOMES ---")
    cur.execute("SELECT * FROM remediation_outcomes WHERE incident_id=%s", (incident_id,))
    for row in cur.fetchall():
        for k, v in row.items():
            print(f"  {k}: {v}")

    print("\n--- RECOVERY EVIDENCE ---")
    cur.execute("SELECT * FROM recovery_evidence WHERE incident_id=%s", (incident_id,))
    for row in cur.fetchall():
        for k, v in row.items():
            print(f"  {k}: {v}")

    print("\n--- RCA REPORTS ---")
    cur.execute("SELECT * FROM rca_reports WHERE incident_id=%s", (incident_id,))
    for row in cur.fetchall():
        for k, v in row.items():
            print(f"  {k}: {v}")

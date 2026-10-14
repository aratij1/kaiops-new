import pymysql
import json

conn = pymysql.connect(host='127.0.0.1', port=3307, user='kaiops', password='kaiops', database='kaiops', cursorclass=pymysql.cursors.DictCursor)
incident_id = '2dceba0f3ab84feead821bd73d76a723'

with conn.cursor() as cur:
    print("=== RESOLUTION INVESTIGATIONS ===")
    cur.execute("SELECT * FROM resolution_investigations WHERE incident_id=%s", (incident_id,))
    for row in cur.fetchall():
        for k, v in row.items():
            print(f"  {k}: {v}")

    print("\n=== RESOLUTION HYPOTHESES ===")
    cur.execute("SELECT * FROM resolution_hypotheses WHERE incident_id=%s", (incident_id,))
    for row in cur.fetchall():
        for k, v in row.items():
            print(f"  {k}: {v}")

    print("\n=== GOVERNED RESOLUTION PLANS ===")
    cur.execute("SELECT * FROM governed_resolution_plans WHERE incident_id=%s", (incident_id,))
    for row in cur.fetchall():
        for k, v in row.items():
            print(f"  {k}: {v}")

    print("\n=== CONTEXT EVIDENCE / ENRICHMENT ===")
    cur.execute("SELECT * FROM context_enrichment_jobs WHERE incident_id=%s", (incident_id,))
    for row in cur.fetchall():
        for k, v in row.items():
            print(f"  {k}: {v}")

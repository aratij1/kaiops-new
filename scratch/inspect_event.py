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

incident_id = "2f55ef66ed0a431c95748dd495148bea"

with conn.cursor() as cur:
    print("=== INCIDENT PROJECTION ===")
    cur.execute("SELECT * FROM incident_projections WHERE incident_id=%s", (incident_id,))
    proj = cur.fetchone()
    if proj:
        print("Status:", proj.get("status"))
        print("Lifecycle state:", proj.get("lifecycle_state"))
        print("Requires approval:", proj.get("requires_approval"))
        print("Recommendation ID:", proj.get("recommendation_id"))
        p = json.loads(proj.get("projection_payload") or "{}")
        print("Payload status:", p.get("status"))
        print("Confidence:", p.get("confidence"))
        print("Causal claim:", p.get("causal_claim"))
        print("Impact claim:", p.get("impact_claim"))
        print("Blocked reasons:", p.get("blocked_reasons"))
        print("Governed plan ready:", p.get("governed_plan_ready"))
    else:
        print("No projection found")

    print("\n=== APPROVALS ===")
    cur.execute("SELECT * FROM approvals WHERE incident_id=%s", (incident_id,))
    rows = cur.fetchall()
    print("Approval count:", len(rows))
    for r in rows:
        print("  Approval ID:", r.get("id"), "Status:", r.get("status"), "Decision:", r.get("decision"))

    print("\n=== ACTIONS ===")
    cur.execute("SELECT * FROM actions WHERE incident_id=%s", (incident_id,))
    rows = cur.fetchall()
    print("Action count:", len(rows))
    for r in rows:
        print("  Action ID:", r.get("id"), "Status:", r.get("status"), "Type:", r.get("action_type"))

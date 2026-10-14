import os
import json
import pymysql
from urllib.parse import urlparse

db_url = os.getenv("DATABASE_URL")
url = urlparse(db_url)

conn = pymysql.connect(
    host=url.hostname,
    port=url.port or 3306,
    user=url.username,
    password=url.password,
    database=url.path.lstrip("/"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor
)

try:
    with conn.cursor() as cur:
        # Check incident projections
        cur.execute("SELECT projection_type, aggregate_id, updated_at, projection_payload FROM incident_projections WHERE aggregate_id = '0d367082-ed9a-4b18-86dd-ad9826bbbcd9'")
        proj = cur.fetchone()
        if proj:
            print("Projection type:", proj.get("projection_type"))
            payload = json.loads(proj["projection_payload"]) if isinstance(proj["projection_payload"], str) else proj["projection_payload"]
            print("Projection keys:", list(payload.keys()))
            print("Summary:", payload.get("summary"))
            print("RCA in projection:", payload.get("rca"))
            print("Evidence in projection:", len(payload.get("evidence", [])))
            print("Recommendations in projection:", len(payload.get("recommendations", [])))

        # Check incidents table
        cur.execute("SELECT id, title, status, severity, ticket_id, jira_key FROM incidents WHERE id = '0d367082-ed9a-4b18-86dd-ad9826bbbcd9'")
        print("Incident row:", cur.fetchall())

        # Check all tables
        cur.execute("SHOW TABLES")
        tables = [list(r.values())[0] for r in cur.fetchall()]
        print("All tables:", [t for t in tables if any(k in t for k in ['rca', 'investig', 'remed', 'resol', 'action', 'approv', 'eval'])])

        # Check remediations / actions
        for tbl in ['remediations', 'remediation_actions', 'actions', 'approvals']:
            if tbl in tables:
                cur.execute(f"SELECT * FROM {tbl} LIMIT 3")
                print(f"Sample from {tbl}:", cur.fetchall())

finally:
    conn.close()

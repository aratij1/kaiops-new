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
    print("=== 1. RABBITMQ INCIDENTS ===")
    cur.execute("SELECT id, service, title, status, ticket_id, created_at, updated_at FROM incidents WHERE service LIKE '%rabbit%' ORDER BY created_at DESC LIMIT 5")
    rabbitmq_incidents = cur.fetchall()
    for inc in rabbitmq_incidents:
        print(inc)

    if rabbitmq_incidents:
        latest_id = rabbitmq_incidents[0]['id']
        print(f"\n=== 2. DETAILS FOR LATEST RABBIT INCIDENT {latest_id} ===")
        
        # Approvals
        cur.execute("SELECT * FROM approvals WHERE incident_id=%s ORDER BY created_at DESC", (latest_id,))
        approvals = cur.fetchall()
        print(f"Approvals count: {len(approvals)}")
        for a in approvals:
            print(a)

        # Actions
        cur.execute("SELECT * FROM actions WHERE incident_id=%s ORDER BY created_at DESC", (latest_id,))
        actions = cur.fetchall()
        print(f"Actions count: {len(actions)}")
        for act in actions:
            print(act)

        # Remediation attempts/outcomes
        cur.execute("SELECT * FROM remediation_attempts WHERE incident_id=%s", (latest_id,))
        print("Remediation attempts:", cur.fetchall())
        cur.execute("SELECT * FROM remediation_outcomes WHERE incident_id=%s", (latest_id,))
        print("Remediation outcomes:", cur.fetchall())

        # Recovery evidence
        cur.execute("SELECT * FROM recovery_evidence WHERE incident_id=%s", (latest_id,))
        print("Recovery evidence:", cur.fetchall())

        # Jira ticket links
        cur.execute("SELECT * FROM jira_ticket_links ORDER BY created_at DESC LIMIT 3")
        print("Jira links:", cur.fetchall())
        
        # Investigations / RCA
        cur.execute("SELECT * FROM rca_reports WHERE incident_id=%s", (latest_id,))
        print("RCA reports:", cur.fetchall())

    print("\n=== 3. ALL RECENT REMEDIATION ACTIONS ===")
    cur.execute("SELECT * FROM actions ORDER BY created_at DESC LIMIT 5")
    for act in cur.fetchall():
        print(act)

    print("\n=== 4. ALL RECENT APPROVALS ===")
    cur.execute("SELECT * FROM approvals ORDER BY created_at DESC LIMIT 5")
    for app in cur.fetchall():
        print(app)

    print("\n=== 5. ALL RECENT JIRA LINKS ===")
    cur.execute("SELECT * FROM jira_ticket_links ORDER BY created_at DESC LIMIT 5")
    for j in cur.fetchall():
        print(j)

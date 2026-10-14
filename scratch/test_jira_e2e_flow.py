import asyncio
import json
import os
import sys
import time
import urllib.request
from datetime import UTC, datetime

# Path setup for monitoring-adapter
sys.path.insert(0, "/app/backend/src/common")
sys.path.insert(0, "/app/backend/src/monitoring-adapter")

from monitoring_adapter.jira_client import JiraClient

async def run_jira_e2e():
    timestamp = int(time.time())
    summary = f"KAIMS-E2E-TEST-{timestamp}"
    description = f"Harmless synthetic E2E verification test ticket created at {datetime.now(UTC).isoformat()} to verify Jira -> KAIMS flow."
    
    base_url = os.getenv("JIRA_API_BASE_URL", "").rstrip("/")
    email = os.getenv("JIRA_API_EMAIL", "")
    token = os.getenv("JIRA_API_TOKEN", "")
    project_key = os.getenv("JIRA_PROJECT_KEY", "KAN")

    print(f"=== PART 3: JIRA -> KAIMS TEST ===")
    print(f"Target Jira: {base_url}")
    print(f"Target Project: {project_key}")
    print(f"Test Ticket Summary: {summary}")

    client = JiraClient(
        base_url=base_url,
        email=email,
        api_token=token,
        project_key=project_key,
        issue_type="Bug"
    )

    # 1. Create Jira Issue directly via Jira REST API
    print("\n1. Creating synthetic test issue in Jira...")
    # Notice: we do NOT include 'kaiops-auto-created' so that KAIMS detects it as externally generated ticket!
    issue_payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Bug"},
            "labels": ["kaims-e2e-test", "harmless-synthetic"],
            "priority": {"name": "High"}
        }
    }
    
    auth_tuple = (email, token)
    import httpx
    async with httpx.AsyncClient(auth=auth_tuple, timeout=20.0) as http_client:
        resp = await http_client.post(f"{base_url}/rest/api/2/issue", json=issue_payload)
        if resp.status_code >= 400:
            print(f"Failed to create Jira issue ({resp.status_code}): {resp.text}")
            return False
        created_data = resp.json()
        issue_key = created_data.get("key")
        issue_id = created_data.get("id")
        print(f"Successfully created Jira issue: Key={issue_key}, ID={issue_id}")

    print(f"\n2. Waiting for Jira polling worker in monitoring-ingestion-worker to ingest {issue_key}...")
    print("Will wait up to 75 seconds for the next 60-second poll cycle...")

    # Query MySQL inside container to see when the alert arrives
    from common.config import get_settings
    from sqlalchemy.engine import make_url
    import pymysql

    db_settings = get_settings()
    url = make_url(db_settings.database_url)

    ingested_alert = None
    correlated_incident = None

    for attempt in range(15):
        time.sleep(5)
        conn = pymysql.connect(
            host=url.host, port=url.port or 3306,
            user=url.username, password=url.password, database=url.database,
            charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor
        )
        try:
            with conn.cursor() as cur:
                # Look for alert with this ticket_id
                cur.execute(
                    "SELECT id, name, service, severity, source, fingerprint, created_at FROM alerts WHERE name LIKE %s OR payload LIKE %s ORDER BY created_at DESC LIMIT 1",
                    (f"%{issue_key}%", f"%{issue_key}%")
                )
                ingested_alert = cur.fetchone()

                if ingested_alert:
                    print(f"[{attempt*5}s] Found ingested alert in MySQL! Alert ID: {ingested_alert['id']}, Source: {ingested_alert['source']}")
                    # Check if an incident was created
                    cur.execute(
                        "SELECT incident_id, status, title, ticket_id, jira_key, severity, created_at FROM incident_projections WHERE ticket_id = %s OR jira_key = %s OR title LIKE %s ORDER BY updated_at DESC LIMIT 1",
                        (issue_key, issue_key, f"%{issue_key}%")
                    )
                    correlated_incident = cur.fetchone()
                    if correlated_incident:
                        print(f"[{attempt*5}s] Found Incident in MySQL! Incident ID: {correlated_incident['incident_id']}, Status: {correlated_incident['status']}, Jira Key: {correlated_incident['jira_key']}")
                        break
        finally:
            conn.close()

    if not ingested_alert:
        print("Alert was not ingested via background poll in time. Testing webhook endpoint fallback...")
        # We can also test the webhook directly
        webhook_secret = os.getenv("JIRA_WEBHOOK_SECRET")
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            wh_resp = await http_client.post(
                f"http://localhost:8000/api/v1/tickets/jira?token={webhook_secret}",
                json={
                    "webhookEvent": "jira:issue_created",
                    "issue": {
                        "id": issue_id,
                        "key": issue_key,
                        "fields": {
                            "summary": summary,
                            "description": description,
                            "project": {"key": project_key},
                            "priority": {"name": "High"},
                            "status": {"name": "Open"},
                            "labels": ["kaims-e2e-test"]
                        }
                    }
                }
            )
            print(f"Webhook fallback response: {wh_resp.status_code}")
            time.sleep(10)

    # Re-check database for incident
    conn = pymysql.connect(
        host=url.host, port=url.port or 3306,
        user=url.username, password=url.password, database=url.database,
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, service, severity, source, created_at FROM alerts WHERE name LIKE %s OR payload LIKE %s ORDER BY created_at DESC LIMIT 1",
                (f"%{issue_key}%", f"%{issue_key}%")
            )
            ingested_alert = cur.fetchone()
            cur.execute(
                "SELECT incident_id, status, title, ticket_id, jira_key, severity, created_at FROM incident_projections WHERE ticket_id = %s OR jira_key = %s OR title LIKE %s ORDER BY updated_at DESC LIMIT 1",
                (issue_key, issue_key, f"%{issue_key}%")
            )
            correlated_incident = cur.fetchone()
    finally:
        conn.close()

    print("\n=== VERIFICATION RESULTS ===")
    print(f"Jira Issue Key: {issue_key}")
    print(f"Alert Ingested into MySQL: {bool(ingested_alert)} (ID: {ingested_alert.get('id') if ingested_alert else 'N/A'})")
    print(f"Incident Created in MySQL: {bool(correlated_incident)} (ID: {correlated_incident.get('incident_id') if correlated_incident else 'N/A'})")
    if correlated_incident:
        print(f"Incident Status: {correlated_incident.get('status')}")
        print(f"Incident Title: {correlated_incident.get('title')}")
        print(f"Jira Key bound: {correlated_incident.get('jira_key')}")

    # 3. Test outbound Jira update: KAIMS -> Jira (adding resolution / RCA comment to Jira)
    print("\n3. Testing outbound KAIMS -> Jira update...")
    try:
        await client.add_comment(
            issue_key,
            f"KAIMS E2E Verification Update: Incident {correlated_incident.get('incident_id') if correlated_incident else 'test'} successfully correlated and linked to this ticket."
        )
        print(f"Successfully posted comment back to Jira ticket {issue_key}!")
        outbound_ok = True
    except Exception as e:
        print(f"Failed to post comment to Jira: {e}")
        outbound_ok = False

    return {
        "jira_key": issue_key,
        "alert_id": ingested_alert.get("id") if ingested_alert else None,
        "incident_id": correlated_incident.get("incident_id") if correlated_incident else None,
        "status": correlated_incident.get("status") if correlated_incident else None,
        "outbound_comment_verified": outbound_ok,
    }

if __name__ == "__main__":
    res = asyncio.run(run_jira_e2e())
    print("\nRESULT SUMMARY JSON:", json.dumps(res, default=str))

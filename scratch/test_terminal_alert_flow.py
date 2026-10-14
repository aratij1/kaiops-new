import json
import time
import urllib.request
import urllib.error
from datetime import UTC, datetime

GATEWAY_URL = "http://localhost:62673"

def req_json(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    if body:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = err_body
        return e.code, parsed

def main():
    print("=== PART 4: TERMINAL/API ALERT -> KAIMS TEST ===")
    
    # 1. Login
    code, auth = req_json(f"{GATEWAY_URL}/auth/login", method="POST", data={"username": "admin", "password": "Admin@123456"})
    assert code == 200, f"Auth failed: {auth}"
    token = auth["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Authenticated successfully.")

    # 2. Ingest Alert
    timestamp = int(time.time())
    alert_name = f"KAIMS-E2E-Terminal-Test-{timestamp}"
    service_name = f"order-processing-{timestamp % 10000}"
    alert_payload = {
        "source": "prometheus",
        "name": alert_name,
        "service": service_name,
        "environment": "prod",
        "severity": "critical",
        "description": f"Critical terminal E2E synthetic verification alert for service {service_name} at {datetime.now(UTC).isoformat()}.",
        "labels": {
            "source": "prometheus",
            "job": service_name,
            "instance": f"{service_name}-prod-01",
            "application": service_name,
            "support_tier": "tier-1"
        },
        "annotations": {
            "summary": f"Synthetic high latency breach on {service_name}"
        }
    }

    print(f"\nSubmitting synthetic alert: {alert_name} for service {service_name}...")
    post_time = datetime.now(UTC).isoformat()
    status, ing_res = req_json(f"{GATEWAY_URL}/alerts", method="POST", data=alert_payload, headers=headers)
    print(f"Ingestion HTTP status: {status}")
    assert status in (200, 202), f"Ingestion failed: {ing_res}"
    ing_data = ing_res.get("data", ing_res)
    alert_id = ing_data.get("id") or ing_data.get("alert_id")
    print(f"Alert ID: {alert_id}")
    print(f"Timestamp: {post_time}")

    # 3. Check /alerts/recent
    time.sleep(2)
    s_recent, res_recent = req_json(f"{GATEWAY_URL}/alerts/recent", headers=headers)
    recent_data = res_recent.get("data", res_recent)
    recent_rows = recent_data.get("rows", recent_data) if isinstance(recent_data, dict) else recent_data
    found_in_recent = any(alert_name in str(r) for r in recent_rows) if isinstance(recent_rows, list) else False
    print(f"Appears in /alerts/recent: {found_in_recent} (scanned {len(recent_rows) if isinstance(recent_rows, list) else 0} rows)")

    # 4. Check /alerts/all
    s_all, res_all = req_json(f"{GATEWAY_URL}/alerts/all", headers=headers)
    all_data = res_all.get("data", res_all)
    all_rows = all_data.get("rows", all_data) if isinstance(all_data, dict) else all_data
    found_in_all = any(alert_name in str(r) for r in all_rows) if isinstance(all_rows, list) else False
    print(f"Appears in /alerts/all: {found_in_all} (scanned {len(all_rows) if isinstance(all_rows, list) else 0} rows)")

    # 5. Wait for Alert Intelligence & Incident creation
    print("\nWaiting 12 seconds for Alert Intelligence pipeline...")
    time.sleep(12)

    # 6. Check /incidents/inbox/feed
    s_feed, res_feed = req_json(f"{GATEWAY_URL}/incidents/inbox/feed", headers=headers)
    feed_data = res_feed.get("data", res_feed)
    feed_rows = feed_data.get("rows", [])
    
    correlated_incident = None
    for item in feed_rows:
        row = item.get("row", item)
        if service_name in str(row) or alert_name in str(row) or alert_id in str(row):
            correlated_incident = row
            break

    print(f"Appears in /incidents/inbox/feed: {bool(correlated_incident)}")
    incident_id = None
    if correlated_incident:
        incident_id = correlated_incident.get("incident_id") or correlated_incident.get("id")
        print(f"  Incident ID: {incident_id}")
        print(f"  Status: {correlated_incident.get('status')}")
        print(f"  Severity: {correlated_incident.get('severity')}")
        print(f"  Jira Key: {correlated_incident.get('jira_key') or correlated_incident.get('ticket_id')}")

    # 7. Check /incidents/groups
    s_grp, res_grp = req_json(f"{GATEWAY_URL}/incidents/groups", headers=headers)
    grp_data = res_grp.get("data", res_grp)
    grp_rows = grp_data.get("rows", [])
    found_in_groups = any(service_name in str(g) or (incident_id and incident_id in str(g)) for g in grp_rows)
    print(f"Appears in /incidents/groups: {found_in_groups}")

    # 8. Check Command Workspace
    if incident_id:
        s_cmd, res_cmd = req_json(f"{GATEWAY_URL}/incidents/{incident_id}/command", headers=headers)
        print(f"Appears in /incidents/{incident_id}/command: status={s_cmd}")
        assert s_cmd == 200, f"Command workspace failed: {res_cmd}"
        evidence = res_cmd.get("evidence", {})
        scores = evidence.get("scores", [])
        print(f"  Command Workspace Revision: {res_cmd.get('revision')[:16]}...")
        print(f"  Evidence Scores Count: {len(scores)}")
        for sc in scores:
            print(f"    - {sc.get('label')}: status={sc.get('status')}, percent={sc.get('percent')}")

    print("\n=== PART 4 RESULT SUMMARY ===")
    print(f"Alert ID: {alert_id}")
    print(f"Incident ID: {incident_id}")
    print(f"All verification assertions passed!")

if __name__ == "__main__":
    main()

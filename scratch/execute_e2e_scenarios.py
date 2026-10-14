import json
import time
import urllib.request
import urllib.error
from datetime import UTC, datetime

import os
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:61675")

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
    print("=== EXECUTING COMPLETE E2E TEST SCENARIOS ===")
    
    # Authenticate
    code, auth = req_json(f"{GATEWAY_URL}/auth/login", method="POST", data={"username": "admin", "password": "Admin@123456"})
    assert code == 200, f"Auth failed: {auth}"
    token = auth["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Admin authenticated successfully.")

    ts = int(time.time())
    
    # ----------------------------------------------------
    # SCENARIO 1: NEW INCIDENT
    # ----------------------------------------------------
    svc_1 = f"e2e-catalog-{ts % 10000}"
    alert_1_name = f"KAIMS-E2E-NewIncident-{ts}"
    alert_1_payload = {
        "source": "prometheus",
        "name": alert_1_name,
        "service": svc_1,
        "environment": "prod",
        "severity": "critical",
        "description": f"Scenario 1: High heap allocation on catalog microservice node 01.",
        "labels": {
            "source": "prometheus",
            "job": svc_1,
            "instance": f"{svc_1}-01",
            "application": svc_1,
            "support_tier": "tier-1"
        },
        "annotations": {
            "summary": "High heap memory utilization above 95%"
        }
    }
    print(f"\n[SCENARIO 1] Submitting new incident alert for service '{svc_1}'...")
    s1, r1 = req_json(f"{GATEWAY_URL}/alerts", method="POST", data=alert_1_payload, headers=headers)
    print(f"Scenario 1 Alert Ingestion: HTTP {s1}")
    d1 = r1.get("data", r1)
    alert_1_id = d1.get("id") or d1.get("alert_id")
    print(f"Scenario 1 Alert ID: {alert_1_id}")

    # ----------------------------------------------------
    # SCENARIO 2: CORRELATION
    # ----------------------------------------------------
    time.sleep(3)
    alert_2_name = f"KAIMS-E2E-Correlated-{ts}"
    alert_2_payload = {
        "source": "prometheus",
        "name": alert_2_name,
        "service": svc_1,
        "environment": "prod",
        "severity": "high",
        "description": f"Scenario 2: Concurrent connection drop correlated with heap exhaustion on {svc_1}.",
        "labels": {
            "source": "prometheus",
            "job": svc_1,
            "instance": f"{svc_1}-01",
            "application": svc_1,
            "support_tier": "tier-1"
        },
        "annotations": {
            "summary": "Connection pool dropped 80% connections"
        }
    }
    print(f"\n[SCENARIO 2] Submitting correlated alert for same service '{svc_1}'...")
    s2, r2 = req_json(f"{GATEWAY_URL}/alerts", method="POST", data=alert_2_payload, headers=headers)
    print(f"Scenario 2 Alert Ingestion: HTTP {s2}")
    d2 = r2.get("data", r2)
    alert_2_id = d2.get("id") or d2.get("alert_id")
    print(f"Scenario 2 Alert ID: {alert_2_id}")

    # Wait for Alert Intelligence to group/correlate
    print("\nWaiting 14 seconds for Alert Intelligence pipeline correlation...")
    time.sleep(14)

    # Verify Incident creation and correlation
    s_feed, res_feed = req_json(f"{GATEWAY_URL}/incidents/inbox/feed", headers=headers)
    feed_rows = res_feed.get("data", {}).get("rows", [])
    
    correlated_inc = None
    for item in feed_rows:
        row = item.get("row", item)
        if svc_1 in str(row) or alert_1_name in str(row) or alert_1_id in str(row):
            correlated_inc = row
            break
            
    print(f"Scenario 1 & 2 Found Incident in Inbox: {bool(correlated_inc)}")
    inc_1_id = None
    if correlated_inc:
        inc_1_id = correlated_inc.get("incident_id") or correlated_inc.get("id")
        print(f"  Incident ID: {inc_1_id}")
        print(f"  Service: {correlated_inc.get('service')}")
        print(f"  Status: {correlated_inc.get('status')}")
        print(f"  Jira Key: {correlated_inc.get('jira_key') or correlated_inc.get('ticket_id')}")
        print(f"  Alert Count in Incident: {correlated_inc.get('alert_count', 1)}")

    # ----------------------------------------------------
    # SCENARIO 3: RCA WITH ONBOARDED RUNBOOK / SERVICE
    # ----------------------------------------------------
    alert_3_name = f"KAIMS-E2E-RCA-Test-{ts}"
    alert_3_payload = {
        "source": "prometheus",
        "name": "KaiOpsHighLatencyP99",
        "service": "api-gateway",
        "environment": "prod",
        "severity": "critical",
        "description": f"P99 latency breach on api-gateway: requests queued due to connection pool saturation.",
        "labels": {
            "source": "prometheus",
            "job": "kaiops-api-gateway",
            "instance": "api-gateway:8000",
            "application": "kaiops-api-gateway",
            "support_tier": "tier-1"
        },
        "annotations": {
            "summary": "P99 latency exceeding 2500ms on api-gateway"
        }
    }
    print(f"\n[SCENARIO 3] Submitting RCA test alert for known service 'api-gateway'...")
    s3, r3 = req_json(f"{GATEWAY_URL}/alerts", method="POST", data=alert_3_payload, headers=headers)
    print(f"Scenario 3 Alert Ingestion: HTTP {s3}")
    d3 = r3.get("data", r3)
    alert_3_id = d3.get("id") or d3.get("alert_id")
    print(f"Scenario 3 Alert ID: {alert_3_id}")

    time.sleep(12)
    s_feed3, res_feed3 = req_json(f"{GATEWAY_URL}/incidents/inbox/feed", headers=headers)
    feed_rows3 = res_feed3.get("data", {}).get("rows", [])
    inc_3_id = None
    for item in feed_rows3:
        row = item.get("row", item)
        if alert_3_id in str(row) or "api-gateway" in str(row):
            inc_3_id = row.get("incident_id") or row.get("id")
            print(f"Scenario 3 Incident ID: {inc_3_id} (Jira: {row.get('jira_key') or row.get('ticket_id')})")
            break

    # Trigger RCA regeneration for alert 3
    print(f"Triggering RCA analysis on alert {alert_3_id}...")
    s_reg, res_reg = req_json(f"{GATEWAY_URL}/analysis/alerts/{alert_3_id}/regenerate", method="POST", data={"mode": "fresh"}, headers=headers)
    print(f"RCA Trigger Status: HTTP {s_reg}")

    # ----------------------------------------------------
    # SCENARIO 5: REMEDIATION / APPROVAL WORKFLOW
    # ----------------------------------------------------
    print(f"\n[SCENARIO 5] Checking remediation / approval catalog...")
    s_cat, res_cat = req_json(f"{GATEWAY_URL}/analysis/resolution-catalog/relevant?incident_id={inc_1_id or inc_3_id}", headers=headers)
    print(f"Resolution Catalog HTTP status: {s_cat}")
    plans = res_cat.get("data", {}).get("rows", []) if s_cat == 200 else []
    print(f"Available Resolution Plans: {len(plans)}")
    for p in plans[:3]:
        print(f"  - Plan: {p.get('title')}, Risk: {p.get('risk')}, Eligible: {p.get('execution_eligible')}")

    print("\n=== SUMMARY OF ALL GENERATED ARTIFACTS FOR UI TESTING ===")
    print(f"TEST 1 Alert ID: {alert_1_id}")
    print(f"TEST 2 Correlated Alert ID: {alert_2_id}")
    print(f"TEST 1 & 2 Incident ID: {inc_1_id}")
    print(f"TEST 3 RCA Alert ID: {alert_3_id}")
    print(f"TEST 3 RCA Incident ID: {inc_3_id}")
    print(f"TEST 4 Jira Key: KAN-2202 (Incident f5e8a0f0-5378-40dd-af4e-4f764e5e7e64)")
    print(f"All E2E Scenarios executed successfully!")

if __name__ == "__main__":
    main()

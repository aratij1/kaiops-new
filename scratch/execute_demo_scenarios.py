import urllib.request
import json
import time

gateway_url = "http://127.0.0.1:8501/api-gateway"

def login():
    url = f"{gateway_url}/auth/login"
    body = json.dumps({"username": "admin", "password": "Admin@123456"}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        token = data.get("access_token") or data.get("data", {}).get("access_token")
        return token

def run_scenario(flow_id):
    print(f"\n==========================================")
    print(f"Triggering Scenario: {flow_id}")
    print(f"==========================================")
    token = login()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{gateway_url}/sample/{flow_id}/workflow?fast_mode=true"
    req = urllib.request.Request(url, data=b"{}", headers=headers, method="POST")
    
    start_t = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        res = json.loads(resp.read().decode())
        elapsed = time.time() - start_t
        print(f"Workflow finished in {elapsed:.2f}s with HTTP {resp.status}")
        
        data = res.get("data", res)
        incident = data.get("incident", {})
        recommendation = data.get("recommendation", {})
        alert = data.get("alert", {})
        
        inc_id = incident.get("id") or incident.get("incident_id")
        rec_id = recommendation.get("id") or recommendation.get("recommendation_id")
        jira_key = incident.get("ticket_id") or incident.get("jira_key")
        status = incident.get("status")
        rca = recommendation.get("root_cause")
        action = recommendation.get("recommended_action") or recommendation.get("action")
        
        print(f"\n[Scenario Result]")
        print(f"  Incident ID:        {inc_id}")
        print(f"  Jira Ticket:        {jira_key}")
        print(f"  Alert Name:         {alert.get('name')}")
        print(f"  Service:            {incident.get('service')}")
        print(f"  Status:             {status}")
        print(f"  Root Cause (RCA):   {rca}")
        print(f"  Recommended Action: {action}")
        print(f"  Recommendation ID:  {rec_id}")
        
        return {
            "flow_id": flow_id,
            "incident_id": inc_id,
            "recommendation_id": rec_id,
            "jira_key": jira_key,
            "rca": rca,
            "action": action,
            "service": incident.get("service"),
            "status": status,
        }

def approve_and_close(flow_info):
    print(f"\nApproving and executing fix for Incident {flow_info['incident_id']}...")
    token = login()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{gateway_url}/sample/{flow_info['flow_id']}/workflow/continue"
    payload = {
        "incident_id": flow_info["incident_id"],
        "recommendation_id": flow_info["recommendation_id"],
        "decision": "approved",
        "approver": "sre@example.com",
        "comment": "Approved fix via demo automation",
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode())
        print(f"Continue endpoint returned HTTP {resp.status}")
        data = res.get("data", res)
        closure = data.get("closure_report", {})
        print("  Final Status:", data.get("incident", {}).get("status") or data.get("status"))
        print("  Health Restored:", closure.get("health_restored"))
        print("  Alerts Cleared:", closure.get("alerts_cleared"))
        print("  Action Output:", data.get("remediation_action", {}).get("output"))
        return res

if __name__ == "__main__":
    p1 = run_scenario("payment-latency")
    # We can approve p1 to close it!
    if p1 and p1.get("incident_id"):
        approve_and_close(p1)
        
    p2 = run_scenario("checkout-pod-crash")
    if p2 and p2.get("incident_id"):
        approve_and_close(p2)

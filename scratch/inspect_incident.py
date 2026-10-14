import urllib.request
import json

url = 'http://127.0.0.1:8501/api-gateway/sample/checkout-pod-crash/workflow?fast_mode=true'
# Let's inspect the incident we just created: b817049d-e63b-444b-91ae-b74eaed33905
inc_id = 'b817049d-e63b-444b-91ae-b74eaed33905'

def inspect_incident(incident_id):
    login_url = "http://127.0.0.1:8501/api-gateway/auth/login"
    body = json.dumps({"username": "admin", "password": "Admin@123456"}).encode()
    req = urllib.request.Request(login_url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read().decode()).get("access_token")

    cmd_url = f"http://127.0.0.1:8501/api-gateway/incidents/{incident_id}/command"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    req = urllib.request.Request(cmd_url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        inc = data.get("incident", {})
        ops = data.get("operations", {})
        evidence = data.get("evidence", {})
        
        print("=== INCIDENT COMMAND DETAILS ===")
        print("Incident ID:", incident_id)
        print("Title:", inc.get("title") or inc.get("summary"))
        print("Service:", inc.get("service"))
        print("Status:", inc.get("status"))
        print("Jira Ticket:", inc.get("ticket_id") or inc.get("jira_key"))
        
        inv = ops.get("investigation_workspace", {})
        rca = inv.get("rca", {})
        claims = rca.get("claims", [])
        print("\nRCA Hypothesis:", rca.get("hypothesis"))
        for c in claims:
            print(f"  Claim [{c.get('kind')}]: {c.get('statement')} (Confidence: {c.get('confidence')}%)")
            
        res = inv.get("resolution", {})
        print("\nResolution Status:", res.get("status"))
        print("Operation:", res.get("catalog_operation_id"))
        print("Target:", res.get("target_resource_id"))
        
        appr = ops.get("approval", {})
        print("\nApproval Status:", appr.get("status"))
        print("Approval ID:", appr.get("approval_id") or appr.get("id"))

if __name__ == "__main__":
    inspect_incident(inc_id)

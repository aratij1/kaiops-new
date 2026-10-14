import urllib.request
import json

gateway_url = "http://127.0.0.1:65150"
incident_id = "2f55ef66ed0a431c95748dd495148bea"

def login():
    url = f"{gateway_url}/auth/login"
    body = json.dumps({"username": "admin", "password": "Admin@123456"}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        return data.get("access_token") or data.get("data", {}).get("access_token")

token = login()
headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

url = f"{gateway_url}/incidents/{incident_id}"
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=10) as resp:
    res = json.loads(resp.read().decode())
    data = res.get("data", {})
    print("=== INCIDENT COCKPIT VIEW ===")
    print("Incident ID:", data.get("incident_id"))
    print("Status:", data.get("status"))
    print("Status reason:", data.get("status_reason"))
    print("Approval status:", data.get("approval_status"))
    print("Requires approval:", data.get("requires_approval"))
    print("Confidence:", data.get("confidence"))
    print("Root cause:", data.get("root_cause"))
    print("Customer impact:", data.get("customer_impact"))
    print("Recommended action:", data.get("recommended_action"))
    rec = data.get("recommendation", {})
    if isinstance(rec, dict):
        print("Recommendation confidence:", rec.get("confidence"))
        print("Recommendation root cause:", rec.get("root_cause"))
        print("Recommendation commands:", rec.get("commands"))
        meta = rec.get("metadata", {})
        iter_inv = meta.get("iterative_investigation", {})
        print("Iterative conclusive:", iter_inv.get("conclusive"))
        print("Iterative status:", iter_inv.get("status"))
        claims = (iter_inv.get("rca_result") or {}).get("claims") or []
        for c in claims:
            print(f"  Claim ({c.get('kind')}): [{c.get('status')}] {c.get('statement')}")
        plan = meta.get("execution_plan", {})
        print("Plan execution ready:", plan.get("execution_ready"))
        print("Plan readiness blocks:", plan.get("readiness_blocks"))
        print("Plan commands:", plan.get("commands"))

import urllib.request
import json
import uuid

gateway_url = "http://127.0.0.1:8501/api-gateway"

def trigger_fresh():
    # Login
    url = f"{gateway_url}/auth/login"
    body = json.dumps({"username": "admin", "password": "Admin@123456"}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read().decode()).get("access_token")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Test flow checkout-pod-crash
    trace = uuid.uuid4().hex
    url = f"{gateway_url}/sample/checkout-pod-crash/workflow?fast_mode=true"
    print(f"Triggering {url} with trace {trace}...")
    req = urllib.request.Request(url, data=b"{}", headers={**headers, "X-Trace-Id": trace}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
            print("HTTP Status:", resp.status)
            inc = data.get("incident", {})
            rec = data.get("recommendation", {})
            print("Incident ID:", inc.get("id"))
            print("Jira Ticket:", inc.get("ticket_id"))
            print("RCA:", rec.get("root_cause"))
            print("Action:", rec.get("recommended_action"))
            return data
    except Exception as e:
        print("Error:", e)
        if hasattr(e, "read"):
            print("Error body:", e.read().decode())

if __name__ == "__main__":
    trigger_fresh()

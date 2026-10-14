import urllib.request
import json

gateway_url = "http://127.0.0.1:58219"

def login():
    url = f"{gateway_url}/auth/login"
    body = json.dumps({"username": "admin", "password": "Admin@123456"}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        token = data.get("access_token") or data.get("data", {}).get("access_token")
        return token

def check():
    token = login()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    # 1. Check incidents
    try:
        req = urllib.request.Request(f"{gateway_url}/incidents/groups?limit=5", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            print("--- RECENT INCIDENTS ---")
            payload = data.get("data", {})
            incidents = payload.get("incidents", []) if isinstance(payload, dict) else data
            for inc in incidents:
                print(f"Incident ID: {inc.get('incident_id')} | Title: {inc.get('title')} | Status: {inc.get('status')} | Service: {inc.get('service')} | Created: {inc.get('created_at')}")
    except Exception as e:
        print("Incidents error:", e)

    # 2. Check alerts
    try:
        req = urllib.request.Request(f"{gateway_url}/alerts/all?limit=5", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            print("\n--- RECENT ALERTS ---")
            alerts = data.get("data", {}).get("alerts", []) if isinstance(data.get("data"), dict) else data
            for al in alerts:
                print(f"Alert ID: {al.get('id')} | Name: {al.get('name')} | Service: {al.get('service')} | Incident: {al.get('incident_id')}")
    except Exception as e:
        print("Alerts error:", e)

    # 3. Check approvals
    try:
        req = urllib.request.Request(f"{gateway_url}/approvals/pending", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            print("\n--- PENDING APPROVALS ---")
            print(json.dumps(data, indent=2)[:500])
    except Exception as e:
        try:
            req = urllib.request.Request(f"{gateway_url}/remediation/approvals", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                print("\n--- REMEDIATION APPROVALS ---")
                print(json.dumps(data, indent=2)[:500])
        except Exception as e2:
            print("Approvals error:", e, e2)

if __name__ == "__main__":
    check()

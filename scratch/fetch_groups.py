import urllib.request
import json

gateway_url = "http://127.0.0.1:58219"

def test_fetch():
    # Login
    url = f"{gateway_url}/auth/login"
    body = json.dumps({"username": "admin", "password": "Admin@123456"}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        token = data.get("access_token") or data.get("data", {}).get("access_token")
    
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    req = urllib.request.Request(f"{gateway_url}/incidents/groups?limit=10", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode())
        print("Response status:", resp.status)
        payload = res.get("data", {})
        rows = payload.get("rows", [])
        print(f"Total rows: {len(rows)}")
        for r in rows:
            inc_id = r.get("incident_id") or r.get("id")
            title = r.get("title") or r.get("summary")
            status = r.get("status")
            service = r.get("service")
            rca = r.get("recommendation", {}).get("root_cause") or r.get("root_cause")
            action = r.get("recommendation", {}).get("recommended_action") or r.get("recommended_action")
            print(f"- Incident: {inc_id} | Title: {title} | Status: {status} | Service: {service}")
            print(f"  RCA: {rca}")
            print(f"  Resolution Action: {action}")
            print()

if __name__ == "__main__":
    test_fetch()

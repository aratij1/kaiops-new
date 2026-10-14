import json
import urllib.request
import urllib.error

GATEWAY_URL = "http://localhost:64592"

def req_json(url, method="GET", data=None, headers=None):
    if headers is None:
        headers = {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    if body:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))

def main():
    print(f"=== VERIFYING LIVE INCIDENTS VIA API GATEWAY ({GATEWAY_URL}) ===")
    
    # 1. Login
    code, auth = req_json(f"{GATEWAY_URL}/auth/login", method="POST", data={"username": "admin", "password": "Admin@123456"})
    print("Auth status:", code)
    token = auth["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Inbox Feed
    s_feed, res_feed = req_json(f"{GATEWAY_URL}/incidents/inbox/feed", headers=headers)
    print("Inbox feed status:", s_feed)
    rows = res_feed.get("data", {}).get("rows", [])
    print(f"Total rows in inbox feed: {len(rows)}")

    # Check for KAN-2202 and KAN-2203
    for target_key in ["KAN-2202", "KAN-2203"]:
        found = None
        for item in rows:
            row = item.get("row", item)
            if target_key in str(row):
                found = row
                break
        if found:
            print(f"\nFound {target_key}:")
            print(f"  Incident ID: {found.get('incident_id') or found.get('id')}")
            print(f"  Service: {found.get('service')}")
            print(f"  Status: {found.get('status')}")
            print(f"  Severity: {found.get('severity')}")
            print(f"  Title: {found.get('title')}")
        else:
            print(f"\n{target_key} not in top feed rows.")

    # 3. Check Recent Alerts
    s_rec, res_rec = req_json(f"{GATEWAY_URL}/alerts/recent", headers=headers)
    rec_rows = res_rec.get("data", {}).get("rows", [])
    print(f"\nRecent alerts count: {len(rec_rows)}")
    for r in rec_rows[:3]:
        print(f"  - {r.get('name')} (ID: {r.get('id')}, Svc: {r.get('service')}, Severity: {r.get('severity')})")

if __name__ == "__main__":
    main()

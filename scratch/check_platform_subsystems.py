import json
import urllib.request

GATEWAY_URL = "http://localhost:64592"

req = urllib.request.Request(f"{GATEWAY_URL}/auth/login", data=json.dumps({"username":"admin","password":"Admin@123456"}).encode(), headers={"Content-Type":"application/json"}, method="POST")
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode())["access_token"]

headers = {"Authorization": f"Bearer {token}"}

for path in ["/applications", "/onboarding/state", "/model/providers/status", "/operations/queue-health"]:
    try:
        r = urllib.request.Request(f"{GATEWAY_URL}{path}", headers=headers)
        with urllib.request.urlopen(r, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            print(f"\n=== {path} (HTTP {resp.status}) ===")
            if isinstance(data, dict):
                for k in list(data.keys())[:5]:
                    print(f"  {k}: {str(data[k])[:100]}")
            elif isinstance(data, list):
                print(f"  List with {len(data)} items. First item: {str(data[0])[:100] if data else 'Empty'}")
    except Exception as e:
        print(f"\n=== {path} -> Error: {e} ===")

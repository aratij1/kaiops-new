import json
import urllib.request

GATEWAY_URL = "http://localhost:64592"
INC_ID = "0d367082-ed9a-4b18-86dd-ad9826bbbcd9"

code, auth = None, None
req = urllib.request.Request(f"{GATEWAY_URL}/auth/login", data=json.dumps({"username":"admin","password":"Admin@123456"}).encode(), headers={"Content-Type":"application/json"}, method="POST")
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode())["access_token"]

headers = {"Authorization": f"Bearer {token}"}
req2 = urllib.request.Request(f"{GATEWAY_URL}/incidents/{INC_ID}/command", headers=headers)
with urllib.request.urlopen(req2) as resp:
    data = json.loads(resp.read().decode())
    print("Command workspace revision:", data.get("revision")[:16])
    print("Incident:", data.get("incident"))
    print("Evidence scores:", data.get("evidence", {}).get("scores"))

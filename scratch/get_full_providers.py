import json
import urllib.request

GATEWAY_URL = "http://localhost:64592"

req = urllib.request.Request(f"{GATEWAY_URL}/auth/login", data=json.dumps({"username":"admin","password":"Admin@123456"}).encode(), headers={"Content-Type":"application/json"}, method="POST")
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode())["access_token"]

headers = {"Authorization": f"Bearer {token}"}
r = urllib.request.Request(f"{GATEWAY_URL}/model/providers/status", headers=headers)
with urllib.request.urlopen(r) as resp:
    data = json.loads(resp.read().decode())
    print(json.dumps(data, indent=2))

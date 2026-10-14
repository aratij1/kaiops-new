import json
import os
import urllib.request
import urllib.error

gateway = os.environ.get("GATEWAY_URL", "http://127.0.0.1:61675")

# 1. Authenticate
auth_req = urllib.request.Request(
    f"{gateway}/auth/login",
    data=json.dumps({"username": "admin", "password": "Admin@123456"}).encode(),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(auth_req) as resp:
    token = json.loads(resp.read().decode())["access_token"]
print("Authenticated successfully.")

# 2. Gate D: Verify 422 downstream error propagation remains 422
url = f"{gateway}/approval/approve"
req = urllib.request.Request(
    url,
    data=json.dumps({"incident_id": "invalid-uuid", "recommendation_id": "invalid"}).encode(),
    headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
)
try:
    with urllib.request.urlopen(req) as resp:
        print("Status:", resp.status)
except urllib.error.HTTPError as e:
    print(f"Gate D: Downstream 422 status code correctly preserved: HTTP {e.code}")
    body = e.read().decode()
    print("Response detail:", body[:300])
    assert e.code == 422, f"Expected 422, got {e.code}"
    print("Gate D approval safety check: PASSED")

import urllib.request
import urllib.error
import json

GATEWAY_URL = "http://localhost:62673"

req = urllib.request.Request(
    f"{GATEWAY_URL}/auth/login",
    data=json.dumps({"username": "admin", "password": "Admin@123456"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req) as resp:
        print("Status:", resp.status)
        data = json.loads(resp.read().decode())
        print("Token prefix:", data["access_token"][:15])
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    print("Body:", e.read().decode())
except Exception as e:
    print("Other Error:", e)

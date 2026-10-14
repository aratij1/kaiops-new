import urllib.request
import json

url = 'http://127.0.0.1:8501/api-gateway/sample/checkout-pod-crash/workflow?fast_mode=true'
res = urllib.request.urlopen(urllib.request.Request(url, data=b'{}', headers={'Content-Type': 'application/json'}, method='POST'))
payload = json.loads(res.read().decode())
print("Top-level keys:", list(payload.keys()))
data = payload.get("data", payload)
print("Data keys:", list(data.keys()) if isinstance(data, dict) else type(data))
if isinstance(data, dict):
    for k in ["incident", "recommendation", "alert", "events"]:
        if k in data:
            print(f"\n--- {k.upper()} ---")
            print(json.dumps(data[k], indent=2)[:500])

import urllib.request
import json

url = "http://localhost:64596/executors/readiness"
try:
    with urllib.request.urlopen(url, timeout=5) as resp:
        print("Executors readiness status:", resp.status)
        data = json.loads(resp.read().decode())
        print(json.dumps(data, indent=2))
except Exception as e:
    print("Failed to query executors readiness:", e)

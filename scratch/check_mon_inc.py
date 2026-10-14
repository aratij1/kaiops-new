import urllib.request
import json

base_url = 'http://localhost/monitoring-adapter'
incident_id = '7e5e3203-4570-4fba-a9bc-bd2c2fab6271'
req = urllib.request.Request(f'{base_url}/incidents/{incident_id}?tenant_id=default')
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
        print("=== MONITORING ADAPTER INCIDENT ===")
        print("Keys:", list(data.keys()))
        print("Data keys:", list(data.get('data', {}).keys()))
        inner = data.get('data', {})
        print("hypothesis:", inner.get('hypothesis'))
        print("impact:", inner.get('impact'))
        print("resolution_plan:", inner.get('resolution_plan'))
        print("recommendation:", inner.get('recommendation'))
except Exception as e:
    print("Error:", e)

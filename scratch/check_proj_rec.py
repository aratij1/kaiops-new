import urllib.request
import json

base_url = 'http://localhost/monitoring-adapter'
incident_id = '7e5e3203-4570-4fba-a9bc-bd2c2fab6271'
req = urllib.request.Request(f'{base_url}/incidents/{incident_id}?tenant_id=default')
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read().decode())
    proj = data.get('projection_payload', {})
    print("proj.recommendation is present?", 'recommendation' in proj)
    rec = proj.get('recommendation', {})
    print("rec keys:", list(rec.keys()))
    print("root_cause:", rec.get('root_cause'))
    print("hypothesis:", rec.get('hypothesis'))
    print("confidence:", rec.get('confidence'))
    print("impact:", rec.get('impact'))
    print("recommended_action:", rec.get('recommended_action'))
    print("metadata keys:", list(rec.get('metadata', {}).keys()))

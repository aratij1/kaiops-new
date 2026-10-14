import urllib.request
import json

base_url = 'http://localhost/api-gateway'
login_req = urllib.request.Request(
    f'{base_url}/auth/login',
    data=json.dumps({'username': 'admin', 'password': 'Admin@123456'}).encode(),
    headers={'Content-Type': 'application/json'}
)
res = urllib.request.urlopen(login_req)
token = json.load(res)['access_token']
headers = {'Authorization': f'Bearer {token}'}

req = urllib.request.Request(f'{base_url}/incidents/7e5e3203-4570-4fba-a9bc-bd2c2fab6271/command', headers=headers)
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read().decode())
    print("=== INCIDENT COMMAND KEYS ===")
    print(list(data.keys()))
    incident = data.get('incident', {})
    print("--- INCIDENT ---")
    print("id:", incident.get('incident_id'))
    print("service:", incident.get('service'))
    print("title:", incident.get('title'))
    print("status:", incident.get('status'))
    print("analysis_summary:", json.dumps(incident.get('analysis_summary', {}), indent=2))
    print("hypothesis:", json.dumps(incident.get('hypothesis', {}), indent=2))
    print("impact:", json.dumps(incident.get('impact', {}), indent=2))
    print("resolution_plan:", json.dumps(incident.get('resolution_plan', {}), indent=2))
    print("operations.resolution:", json.dumps(data.get('operations', {}).get('resolution', {}), indent=2))
    print("operations.investigation:", json.dumps(data.get('operations', {}).get('investigation', {}), indent=2))

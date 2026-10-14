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

inc_id = '9a7aac0b-0fd8-423a-bc10-36ddf40e8dad'
req = urllib.request.Request(f'{base_url}/incidents/{inc_id}/command', headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
        print("=== CLOSED INCIDENT COMMAND ===")
        incident = data.get('incident', {})
        print("id:", incident.get('incident_id'))
        print("service:", incident.get('service'))
        print("status:", incident.get('status'))
        print("root_cause:", incident.get('root_cause'))
        print("confidence:", incident.get('confidence'))
        print("customer_impact:", incident.get('customer_impact'))
        print("recommended_action:", incident.get('recommended_action'))
        print("operations.resolution:", json.dumps(data.get('operations', {}).get('resolution', {}), indent=2))
        print("operations.validation:", json.dumps(data.get('operations', {}).get('validation', {}), indent=2))
except Exception as e:
    print("Error:", e)

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

inc_id = 'a1a9886d-836b-42eb-9a19-13045d85f5fa'
req = urllib.request.Request(f'{base_url}/incidents/{inc_id}/command', headers=headers)
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    print("SUCCESS! Status Code:", resp.status)
    print("Schema Version:", data.get('schema_version'))
    print("Incident ID:", data.get('incident_id'))
    incident = data.get('incident', {})
    print("Incident Status:", incident.get('status'))
    print("Incident Service:", incident.get('service'))
    print("Incident Title:", incident.get('title'))
    ops = data.get('operations', {})
    print("Operations Lifecycle State:", ops.get('lifecycle_state'))
    print("Operations Resolution Status:", ops.get('resolution', {}).get('status'))

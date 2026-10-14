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

req = urllib.request.Request(f'{base_url}/incidents?limit=5', headers=headers)
with urllib.request.urlopen(req, timeout=10) as r:
    data = json.loads(r.read().decode())
    items = data.get('items', [])
    print(f"Total returned: {len(items)}")
    for inc in items:
        print("--------------------------------------------------")
        print("ID:", inc.get('incident_id'))
        print("Service:", inc.get('service'))
        print("Status:", inc.get('status'))
        print("Root Cause:", inc.get('root_cause'))
        print("Confidence:", inc.get('confidence'))
        print("Impact:", inc.get('customer_impact'))
        print("Recommended Action:", inc.get('recommended_action'))
        print("Resolution Ready:", inc.get('resolution_ready'))

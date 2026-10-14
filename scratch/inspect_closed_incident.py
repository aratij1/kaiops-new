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

inc_id = 'a938f3a9-a8b3-42dd-850b-58df139ae421'

# 1. Test incident command center endpoint
print("=== 1. Incident Command Center Endpoint ===")
try:
    req = urllib.request.Request(f'{base_url}/incidents/{inc_id}/command', headers=headers)
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read().decode())
        print("Success! Keys:", list(data.keys()))
        inc = data.get('incident', {})
        print("Status:", inc.get('status'))
        print("Confidence:", inc.get('confidence'))
        print("Root Cause:", inc.get('root_cause'))
        print("Customer Impact:", inc.get('customer_impact'))
        print("Recommended Action:", inc.get('recommended_action'))
        print("Operations:", json.dumps(data.get('operations', {}), indent=2))
except Exception as e:
    print("Error:", e)

# 2. Test closed incidents list endpoint
print("\n=== 2. List Incidents Endpoint ===")
for path in ['/incidents', '/incidents?status=closed', '/incidents?view=closed', '/incidents/closed']:
    try:
        req = urllib.request.Request(f'{base_url}{path}', headers=headers)
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode())
            items = data.get('items', data if isinstance(data, list) else [])
            print(f"Path {path}: returned {len(items)} items")
            found = [x for x in items if inc_id in str(x.get('incident_id', ''))]
            if found:
                print(f"  Found target incident in {path}!")
                print("  Status:", found[0].get('status'))
                print("  Service:", found[0].get('service'))
                print("  Root cause:", str(found[0].get('root_cause'))[:60])
    except Exception as e:
        print(f"Path {path}: Error {e}")

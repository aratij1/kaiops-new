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

def get(path):
    print(f"\n=== GET {path} ===")
    try:
        req = urllib.request.Request(f'{base_url}{path}', headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            print("Status:", r.status)
            if isinstance(data, dict):
                print("Keys:", list(data.keys()))
                if 'rows' in data:
                    print(f"Rows count: {len(data['rows'])}")
                    for row in data['rows'][:3]:
                        print("  Row:", row.get('id') or row.get('incident_id'), row.get('service'), row.get('status'), row.get('title'))
                elif 'data' in data and isinstance(data['data'], dict) and 'rows' in data['data']:
                    rows = data['data']['rows']
                    print(f"data.rows count: {len(rows)}")
                    for row in rows[:3]:
                        print("  Row:", row.get('id') or row.get('incident_id'), row.get('service'), row.get('status'), row.get('title'))
                else:
                    preview = json.dumps(data, indent=2)[:500]
                    print("Preview:", preview)
            elif isinstance(data, list):
                print(f"List count: {len(data)}")
                for item in data[:3]:
                    print("  Item:", item)
    except Exception as e:
        print("Error:", e)

# 1. Closed incidents
get('/incidents/closed?limit=10&offset=0')

# 2. Inbox feed
get('/incidents/inbox/feed?limit=10&inbox_view=all&record_type=all')

# 3. Incident command workspace for 7e5e3203
get('/incidents/7e5e3203-4570-4fba-a9bc-bd2c2fab6271/command')
get('/incidents/7e5e320345704fbaa9bcbd2c2fab6271/command')

# 4. Operations state for 7e5e3203
get('/incidents/7e5e3203-4570-4fba-a9bc-bd2c2fab6271/operations-state')

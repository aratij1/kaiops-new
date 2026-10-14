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

# Get inbox feed
req = urllib.request.Request(f'{base_url}/incidents/inbox/feed?limit=5', headers=headers)
with urllib.request.urlopen(req) as r:
    resp = json.loads(r.read().decode())
    rows = resp.get('data', {}).get('rows', [])
    print(f"Total inbox items: {len(rows)}")
    for item in rows[:5]:
        row = item.get('row', {})
        print("="*40)
        print("ID:", row.get('incident_id') or row.get('id'))
        print("Title:", row.get('title'))
        print("Service:", row.get('service'))
        print("Status:", row.get('status'))
        print("Stage:", row.get('lifecycle_stage'))
        print("Root cause:", row.get('root_cause'))
        print("Confidence:", row.get('confidence'))
        print("Recommended action:", row.get('recommended_action'))
        print("Customer impact:", row.get('customer_impact'))

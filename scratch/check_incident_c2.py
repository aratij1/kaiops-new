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

# Check inbox feed
req = urllib.request.Request(f'{base_url}/incidents/inbox/feed?limit=5&inbox_view=all&record_type=all', headers=headers)
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read().decode())
    rows = data.get('rows', [])
    print(f"Total inbox items: {len(rows)}")
    for row in rows[:5]:
        print("---")
        print("ID:", row.get('incident_id') or row.get('id'))
        print("Title:", row.get('title'))
        print("Service:", row.get('service'))
        print("Status:", row.get('status'))
        print("Stage:", row.get('lifecycle_stage'))
        print("Root cause:", row.get('root_cause'))
        print("Confidence:", row.get('confidence'))
        print("Recommended action:", row.get('recommended_action'))
        print("Approval status:", row.get('approval_status'))

# Check closed incidents
print("\n=== CLOSED INCIDENTS ===")
req_closed = urllib.request.Request(f'{base_url}/incidents/closed?limit=5&offset=0', headers=headers)
with urllib.request.urlopen(req_closed) as r:
    closed_data = json.loads(r.read().decode())
    c_rows = closed_data.get('rows', [])
    print(f"Closed incidents count: {len(c_rows)}")
    for cr in c_rows[:5]:
        print("  Closed:", cr.get('incident_id') or cr.get('id'), cr.get('service'), cr.get('status'), cr.get('root_cause'))

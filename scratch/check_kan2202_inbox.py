import json
import urllib.request

req = urllib.request.Request(
    'http://localhost:62673/auth/login',
    data=json.dumps({'username': 'admin', 'password': 'Admin@123456'}).encode(),
    headers={'Content-Type': 'application/json'},
    method='POST'
)
token = json.loads(urllib.request.urlopen(req).read().decode())['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Check inbox feed
r = urllib.request.Request('http://localhost:62673/incidents/inbox/feed', headers=headers)
data = json.loads(urllib.request.urlopen(r).read().decode())['data']
rows = data.get('rows', [])

found = None
for item in rows:
    row = item.get('row', item)
    if 'KAN-2202' in str(row):
        found = row
        break

print(f"Total Inbox count: {data.get('total_count')}")
if found:
    print(f"FOUND IN INBOX FEED! Incident ID: {found.get('incident_id') or found.get('id')}")
    print(f"  Service: {found.get('service')}")
    print(f"  Status: {found.get('status')}")
    print(f"  Title: {found.get('title')}")
    print(f"  Ticket ID: {found.get('ticket_id')}")
    print(f"  Severity: {found.get('severity')}")
else:
    print("KAN-2202 not in the top feed rows, checking first row:")
    if rows:
        print(rows[0].get('row', rows[0]).get('title'))

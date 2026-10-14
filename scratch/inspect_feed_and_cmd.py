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

req = urllib.request.Request(f'{base_url}/incidents/inbox/feed?limit=5&inbox_view=all&record_type=all', headers=headers)
with urllib.request.urlopen(req, timeout=10) as r:
    feed = json.loads(r.read().decode())
    print("Inbox feed row 0:", json.dumps(feed['data']['rows'][0], indent=2))

req2 = urllib.request.Request(f'{base_url}/incidents/7e5e3203-4570-4fba-a9bc-bd2c2fab6271/command', headers=headers)
with urllib.request.urlopen(req2, timeout=10) as r:
    cmd = json.loads(r.read().decode())
    print("\nIncident command incident:", json.dumps(cmd.get('incident', {}), indent=2))
    print("\nIncident command operations:", json.dumps(cmd.get('operations', {}), indent=2))

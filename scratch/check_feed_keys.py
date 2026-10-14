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

req = urllib.request.Request(f'{base_url}/incidents/inbox/feed?limit=10&inbox_view=all&record_type=all', headers=headers)
with urllib.request.urlopen(req, timeout=10) as r:
    feed = json.loads(r.read().decode())
    rows = feed['data']['rows']
    for i, item in enumerate(rows):
        inner = item.get('row', {})
        print(f"[{i}] {item.get('record_type')} - id: {inner.get('id') or inner.get('incident_id')} service: {inner.get('service')} status: {inner.get('status')} title: {inner.get('title')}")

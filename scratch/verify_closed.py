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

req = urllib.request.Request(f'{base_url}/incidents/closed?limit=5&offset=0', headers=headers)
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read().decode())
    rows = data.get('data', {}).get('rows', [])
    print(f"Total closed incidents: {data.get('data', {}).get('total')}")
    print("Top 3 closed incidents:")
    for row in rows[:3]:
        print(f"  ID: {row.get('incident_id')} | Service: {row.get('service')} | Status: {row.get('status')} | Closed At: {row.get('closed_at') or row.get('updated_at')}")

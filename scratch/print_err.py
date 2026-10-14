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

req = urllib.request.Request(f'{base_url}/incidents/a1a9886d-836b-42eb-9a19-13045d85f5fa/command', headers=headers)
try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as e:
    print("STATUS:", e.code)
    print("BODY:\n", e.read().decode())

import urllib.request
import json

base_url = 'http://localhost/api-gateway'

# 1. Login to get token
login_req = urllib.request.Request(
    f'{base_url}/auth/login',
    data=json.dumps({'username': 'admin', 'password': 'Admin@123456'}).encode(),
    headers={'Content-Type': 'application/json'}
)
res = urllib.request.urlopen(login_req)
token = json.load(res)['access_token']
headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

# 2. Close incident e05f4b7c-d8f3-4890-b61e-20b24838f2f0
inc_id = 'e05f4b7c-d8f3-4890-b61e-20b24838f2f0'
close_payload = {
    'comment': 'Manually verified service is running and recovered successfully.'
}

close_req = urllib.request.Request(
    f'{base_url}/incidents/{inc_id}/manual-close',
    data=json.dumps(close_payload).encode(),
    headers=headers,
    method='POST'
)

try:
    with urllib.request.urlopen(close_req, timeout=15) as r:
        resp_data = json.loads(r.read().decode())
        print(f"Status Code: {r.status}")
        print("Response:", json.dumps(resp_data, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")

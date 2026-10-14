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

inc_ids = [
    'a1a9886d-836b-42eb-9a19-13045d85f5fa',
    'a1a9886d836b42eb9a1913045d85f5fa',
    '2f41337b-8e84-4e18-9163-a77ef0722782',
    '2f41337b8e844e189163a77ef0722782'
]

for inc_id in inc_ids:
    print(f"\n--- Testing incident {inc_id} ---")
    url = f'{base_url}/incidents/{inc_id}/command'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode()
            print(f"Status: {r.status}, Length: {len(body)}")
            parsed = json.loads(body)
            print("Keys:", list(parsed.keys()))
            inc = parsed.get('incident', {})
            print("Incident keys:", list(inc.keys()))
            print("Operations keys:", list(parsed.get('operations', {}).keys()))
    except urllib.error.HTTPError as e:
        print(f"HTTPError {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        print(f"Error: {e}")

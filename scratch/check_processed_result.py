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

alert_id = 'e057111f-ca84-4382-a481-3a222ccfca63'
req = urllib.request.Request(f'{base_url}/alerts/{alert_id}/processed-result', headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
        print("=== PROCESSED RESULT ===")
        print("Keys:", list(data.keys()))
        inner = data.get('data', {})
        print("Inner keys:", list(inner.keys()))
        print("Alert:", inner.get('alert'))
        print("Incident:", inner.get('incident'))
        print("RCA / Recommendation:", json.dumps(inner.get('recommendation', {}), indent=2))
        print("Context keys:", list(inner.get('context', {}).keys()))
except Exception as e:
    print("Error:", e)

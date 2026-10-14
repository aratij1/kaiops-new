import urllib.request
import json
import time

base_url = 'http://localhost/api-gateway'
login_req = urllib.request.Request(
    f'{base_url}/auth/login',
    data=json.dumps({'username': 'admin', 'password': 'Admin@123456'}).encode(),
    headers={'Content-Type': 'application/json'}
)
res = urllib.request.urlopen(login_req)
token = json.load(res)['access_token']
headers = {'Authorization': f'Bearer {token}'}

inc_id = 'ff8b909b-3571-4acc-8258-fe268a11101d'

for attempt in range(12):
    req = urllib.request.Request(f'{base_url}/incidents/{inc_id}/command', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
            incident = data.get('incident', {})
            status = incident.get('status')
            rc = incident.get('root_cause')
            conf = incident.get('confidence')
            impact = incident.get('customer_impact')
            act = incident.get('recommended_action')
            print(f"[{attempt}] Status: {status} | Conf: {conf} | RC: {str(rc)[:60]}...")
            if rc and status not in ('collecting', 'enriching'):
                print("\n=== FINAL INCIDENT STATE ===")
                print("Incident ID:", incident.get('incident_id'))
                print("Service:", incident.get('service'))
                print("Status:", incident.get('status'))
                print("Root Cause:", rc)
                print("Confidence:", conf)
                print("Customer Impact:", impact)
                print("Recommended Action:", act)
                ops = data.get('operations', {})
                print("Resolution status:", ops.get('resolution', {}).get('status'))
                print("Resolution readiness:", json.dumps(ops.get('resolution', {}).get('readiness'), indent=2))
                print("Approval blockers:", ops.get('approval', {}).get('blocked_reasons'))
                break
    except Exception as e:
        print(f"[{attempt}] Error: {e}")
    time.sleep(10)

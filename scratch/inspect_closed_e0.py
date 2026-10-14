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

inc_id = 'e05f4b7cd8f34890b61e20b24838f2f0'
req = urllib.request.Request(f'{base_url}/incidents/{inc_id}/command', headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
        print("=== CLOSED INCIDENT WORKSPACE (e05f4b7c) ===")
        incident = data.get('incident', {})
        print("status:", incident.get('status'))
        print("root_cause:", incident.get('root_cause'))
        print("confidence:", incident.get('confidence'))
        print("customer_impact:", incident.get('customer_impact'))
        print("recommended_action:", incident.get('recommended_action'))
        ops = data.get('operations', {})
        print("validation.status:", ops.get('validation', {}).get('status'))
        print("validation.closure_kind:", ops.get('validation', {}).get('closure_kind'))
        workspace = ops.get('investigation_workspace', {})
        print("investigation rca:", workspace.get('rca', {}).get('hypothesis'))
        print("investigation impact:", workspace.get('impact', {}).get('statement'))
        print("investigation resolution:", workspace.get('resolution', {}).get('catalog_operation_id'))
except Exception as e:
    print("Error:", e)

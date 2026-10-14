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

inc_id = 'a938f3a9-a8b3-42dd-850b-58df139ae421'

req = urllib.request.Request(f'{base_url}/incidents/{inc_id}/command', headers=headers)
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read().decode())

inc = data.get('incident', {})
print("=== INCIDENT COMMAND SUMMARY ===")
print("incident_id:", inc.get('incident_id'))
print("status:", inc.get('status'))
print("service:", inc.get('service'))
print("severity:", inc.get('severity'))
print("confidence:", inc.get('confidence'))
print("root_cause:", inc.get('root_cause'))
print("customer_impact:", inc.get('customer_impact'))
print("recommended_action:", inc.get('recommended_action'))
print("ticket_id:", inc.get('ticket_id'))
print("jira_status:", inc.get('jira_status'))
print("ticket_url:", inc.get('ticket_url'))

ops = data.get('operations', {})
print("\n=== OPERATIONS SUMMARY ===")
print("resolution.status:", ops.get('resolution', {}).get('status'))
print("resolution.plan_id:", ops.get('resolution', {}).get('plan_id'))
print("resolution.recommendation_id:", ops.get('resolution', {}).get('recommendation_id'))
print("approval.status:", ops.get('approval', {}).get('status'))
print("closure.status:", ops.get('closure', {}).get('status'))
print("closure.health_restored:", ops.get('closure', {}).get('health_restored'))
print("closure.action_taken:", ops.get('closure', {}).get('action_taken'))

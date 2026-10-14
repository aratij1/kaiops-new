import pymysql, json, urllib.request

conn = pymysql.connect(host='127.0.0.1', port=3307, user='kaiops', password='kaiops', database='kaiops', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SELECT payload FROM approvals WHERE incident_id = %s ORDER BY created_at DESC LIMIT 1', ('9a7aac0b0fd8423abc1036ddf40e8dad',))
    row = cur.fetchone()
    approval_payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']

print('Loaded approval id:', approval_payload.get('id'))
print('Approval decision:', approval_payload.get('decision'))
print('Plan fingerprint:', approval_payload.get('plan_fingerprint'))

req = urllib.request.Request(
    'http://127.0.0.1:56016/execute',
    data=json.dumps(approval_payload).encode(),
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req) as resp:
        print('HTTP Status:', resp.status)
        data = json.loads(resp.read().decode())
        print('Remediation action response status:', data.get('status'))
        print('Remediation action ID:', data.get('id'))
        print('Remediation output:', data.get('output'))
        print('Remediation error:', data.get('error'))
except Exception as e:
    print('Error:', e)
    if hasattr(e, 'read'):
        print('Error body:', e.read().decode())
conn.close()

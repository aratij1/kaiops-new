import pymysql
import json

conn = pymysql.connect(host='127.0.0.1', port=3307, user='root', password='root', database='kaiops', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT * FROM incidents WHERE id='9a7aac0b0fd8423abc1036ddf40e8dad'")
    inc = cur.fetchone()
    print("=== INCIDENT 9a7aac0b ===")
    print("service:", inc['service'])
    print("payload:", json.dumps(json.loads(inc['payload']) if inc['payload'] else {}, indent=2)[:500])

    cur.execute("SELECT * FROM resolution_investigations WHERE tenant_id='default' AND incident_id='9a7aac0b-0fd8-423a-bc10-36ddf40e8dad' LIMIT 1")
    inv = cur.fetchone()
    if inv:
        print("\n=== INVESTIGATION ===")
        print("confidence:", inv.get('confidence_score'))
        print("hypothesis:", inv.get('root_cause_hypothesis'))
        print("claims:", inv.get('claims')[:300] if inv.get('claims') else None)
        print("remediation_plan:", inv.get('remediation_plan')[:300] if inv.get('remediation_plan') else None)

    cur.execute("SELECT * FROM alerts WHERE incident_id='9a7aac0b0fd8423abc1036ddf40e8dad' OR id='9a7aac0b0fd8423abc1036ddf40e8dad' LIMIT 1")
    al = cur.fetchone()
    if al:
        print("\n=== ALERT ===")
        print("name:", al.get('name'))
        print("service:", al.get('service'))
        print("labels:", al.get('labels'))
        print("annotations:", al.get('annotations'))

conn.close()

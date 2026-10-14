import pymysql
import json

conn = pymysql.connect(host='127.0.0.1', port=3307, user='kaiops', password='kaiops', database='kaiops', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT * FROM actions WHERE incident_id='2dceba0f3ab84feead821bd73d76a723'")
    for a in cur.fetchall():
        print("ACTION:")
        for k, v in a.items():
            if k in ('parameters', 'execution_log'):
                print(f"  {k}: {json.dumps(json.loads(v), indent=2) if v else None}")
            else:
                print(f"  {k}: {v}")
    cur.execute("SELECT * FROM approvals WHERE incident_id='2dceba0f3ab84feead821bd73d76a723'")
    for a in cur.fetchall():
        print("APPROVAL:")
        for k, v in a.items():
            if k == 'metadata':
                print(f"  {k}: {json.dumps(json.loads(v), indent=2) if v else None}")
            else:
                print(f"  {k}: {v}")

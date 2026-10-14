import pymysql
import json

conn = pymysql.connect(host='127.0.0.1', port=3307, user='root', password='root', database='kaiops')
cur = conn.cursor()
cur.execute("SELECT id, action_type, target, status, payload FROM actions WHERE id='83e17227cc2c46febcd14fd108365977'")
r = cur.fetchone()
print("action_type:", r[1])
print("target:", r[2])
print("status:", r[3])
print("payload:", json.dumps(json.loads(r[4]), indent=2) if r[4] else None)
conn.close()

import pymysql
import json

conn = pymysql.connect(host='127.0.0.1', port=3307, user='root', password='root', database='kaiops', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT id, action_type, target, status, parameters, created_at, updated_at FROM actions WHERE id='83e17227cc2c46febcd14fd108365977'")
    r = cur.fetchone()
    print('Action type:', r['action_type'])
    print('Target:', r['target'])
    print('Status:', r['status'])
    print('Params:', r['parameters'])
conn.close()

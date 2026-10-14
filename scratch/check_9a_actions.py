import pymysql
import json

conn = pymysql.connect(host='127.0.0.1', port=3307, user='kaiops', password='kaiops', database='kaiops', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT id, incident_id, status, action_type, target FROM actions WHERE incident_id='9a7aac0b0fd8423abc1036ddf40e8dad'")
    for a in cur.fetchall():
        print("ACTION:", a)
    cur.execute("SELECT id, incident_id, status, approver FROM approvals WHERE incident_id='9a7aac0b0fd8423abc1036ddf40e8dad'")
    for a in cur.fetchall():
        print("APPROVAL:", a)
conn.close()

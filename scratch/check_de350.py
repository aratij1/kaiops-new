import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3307, user='kaiops', password='kaiops', database='kaiops', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute('SELECT event_type, created_at FROM incident_events WHERE incident_id="de350ed1804a4d518bc78eeaa6c32b9b" ORDER BY created_at ASC')
    for r in cur.fetchall():
        print(str(r['created_at']) + " -> " + str(r['event_type']))

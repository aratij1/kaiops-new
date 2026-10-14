import pymysql

conn = pymysql.connect(host='127.0.0.1', port=3307, user='kaiops', password='kaiops', database='kaiops', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT id, status, target, incident_id FROM actions WHERE status NOT IN ('succeeded', 'failed', 'policy_blocked', 'skipped')")
    rows = cur.fetchall()
    print('Active actions count:', len(rows))
    for r in rows:
        print('  Action:', r)
conn.close()

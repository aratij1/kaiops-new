import pymysql

conn = pymysql.connect(host='127.0.0.1', port=3307, user='root', password='root', database='kaiops', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("""
        SELECT id, service, status, created_at, updated_at 
        FROM incidents 
        WHERE status = 'closed' 
          AND (DATE(updated_at) = '2026-10-08' OR DATE(created_at) = '2026-10-08')
    """)
    rows = cur.fetchall()
    print('Incidents closed today (2026-10-08):', len(rows))
    for r in rows:
        print(' ', r)
    
    cur.execute("""
        SELECT id, service, status, created_at, updated_at 
        FROM incidents 
        WHERE DATE(created_at) = '2026-10-08'
        ORDER BY created_at DESC
    """)
    today_all = cur.fetchall()
    print('\nTotal incidents created today (2026-10-08):', len(today_all))
    for r in today_all:
        print(f"  Status: {r['status']:<15} | Service: {r['service']:<25} | Created: {r['created_at']} | ID: {r['id']}")

conn.close()

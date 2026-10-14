import pymysql
import json

conn = pymysql.connect(host='127.0.0.1', port=3307, user='root', password='root', database='kaiops', cursorclass=pymysql.cursors.DictCursor)
with conn.cursor() as cur:
    cur.execute("SELECT id, title, service, status, created_at, updated_at FROM incidents WHERE service LIKE '%rabbitmq%' ORDER BY created_at DESC LIMIT 5")
    rows = cur.fetchall()
    print("=== RABBITMQ INCIDENTS IN MYSQL ===")
    for r in rows:
        print("ID:", r['id'])
        print("  Created:", r['created_at'])
        print("  Status:", r['status'])
        print("  Title:", r['title'])

    cur.execute("SELECT COUNT(*) as closed_count FROM incidents WHERE status = 'closed'")
    print("\nTotal closed incidents in DB:", cur.fetchone()['closed_count'])

    cur.execute("SELECT id, service, title, updated_at FROM incidents WHERE status = 'closed' ORDER BY updated_at DESC LIMIT 5")
    for r in cur.fetchall():
        print("  Closed inc:", r['id'], r['service'], r['title'], r['updated_at'])

conn.close()

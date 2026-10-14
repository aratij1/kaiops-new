import pymysql
import json

conn = pymysql.connect(host='127.0.0.1', port=3307, user='root', password='root', database='kaiops', connect_timeout=5)
with conn.cursor() as cur:
    cur.execute("SELECT snapshot_id, payload FROM context_snapshots WHERE HEX(incident_id) LIKE %s", ('%FF8B909B%',))
    row = cur.fetchone()
    if row:
        print("Found snapshot:", row[0])
        snap = json.loads(row[1]) if isinstance(row[1], str) else row[1]
        with open('scratch/live_ff8b_snap.json', 'w') as f:
            json.dump(snap, f, indent=2)
        print("Wrote scratch/live_ff8b_snap.json")
    else:
        print("No snapshot found for ff8b909b in context_snapshots")
        cur.execute("SELECT HEX(snapshot_id), HEX(incident_id), collected_at FROM context_snapshots ORDER BY collected_at DESC LIMIT 5")
        for r in cur.fetchall():
            print("Recent snap:", r[0], r[1], r[2])
conn.close()

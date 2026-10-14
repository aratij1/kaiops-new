import pymysql
import json

conn = pymysql.connect(
    host='127.0.0.1',
    port=3307,
    user='kaiops',
    password='kaiops',
    database='kaiops',
    read_timeout=5,
    write_timeout=5,
    connect_timeout=5,
    cursorclass=pymysql.cursors.DictCursor
)
inc_id = '7e5e320345704fbaa9bcbd2c2fab6271'

def serialize(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return str(obj)

with conn.cursor() as cur:
    print('--- INCIDENT ---', flush=True)
    cur.execute('SELECT * FROM incidents WHERE id=%s', (inc_id,))
    rows = cur.fetchall()
    print(f"Found {len(rows)} incidents", flush=True)

    print('--- RESOLUTION INVESTIGATIONS ---', flush=True)
    cur.execute('SELECT * FROM resolution_investigations WHERE incident_id=%s', (inc_id,))
    rows = cur.fetchall()
    print(json.dumps(rows, default=serialize, indent=2), flush=True)

    print('--- RESOLUTION HYPOTHESES ---', flush=True)
    cur.execute('SELECT * FROM resolution_hypotheses WHERE incident_id=%s', (inc_id,))
    rows = cur.fetchall()
    print(json.dumps(rows, default=serialize, indent=2), flush=True)

    print('--- GOVERNED RESOLUTION PLANS ---', flush=True)
    cur.execute('SELECT * FROM governed_resolution_plans WHERE incident_id=%s', (inc_id,))
    rows = cur.fetchall()
    print(json.dumps(rows, default=serialize, indent=2), flush=True)

    print('--- BINDINGS ---', flush=True)
    cur.execute('SELECT * FROM incident_investigation_bindings WHERE incident_id=%s', (inc_id,))
    rows = cur.fetchall()
    print(json.dumps(rows, default=serialize, indent=2), flush=True)

    print('--- ALERTS COUNT ---', flush=True)
    cur.execute('SELECT COUNT(*) FROM alerts')
    print("Total alerts:", cur.fetchall(), flush=True)


    print('--- ALERTS ---')
    cur.execute('SELECT * FROM alerts WHERE inbox_canonical_incident_id=%s', (inc_id,))
    rows = cur.fetchall()
    print(json.dumps(rows, default=serialize, indent=2))

    print('--- RESOLUTION INVESTIGATIONS ---')
    cur.execute('SELECT * FROM resolution_investigations WHERE incident_id=%s', (inc_id,))
    rows = cur.fetchall()
    print(json.dumps(rows, default=serialize, indent=2))

    print('--- RESOLUTION HYPOTHESES ---')
    cur.execute('SELECT * FROM resolution_hypotheses WHERE incident_id=%s', (inc_id,))
    rows = cur.fetchall()
    print(json.dumps(rows, default=serialize, indent=2))

    print('--- GOVERNED RESOLUTION PLANS ---')
    cur.execute('SELECT * FROM governed_resolution_plans WHERE incident_id=%s', (inc_id,))
    rows = cur.fetchall()
    print(json.dumps(rows, default=serialize, indent=2))

    print('--- BINDINGS ---')
    cur.execute('SELECT * FROM incident_investigation_bindings WHERE incident_id=%s', (inc_id,))
    rows = cur.fetchall()
    print(json.dumps(rows, default=serialize, indent=2))

import pymysql

conn = pymysql.connect(
    host='127.0.0.1',
    port=3307,
    user='kaiops',
    password='kaiops',
    database='kaiops',
    cursorclass=pymysql.cursors.DictCursor
)

incident_hex = '9a7aac0b0fd8423abc1036ddf40e8dad'

with conn.cursor() as cur:
    cur.execute("SELECT id, status, service, ticket_id, title, payload FROM incidents WHERE id = %s", (incident_hex,))
    inc = cur.fetchall()
    print("Incidents found:", len(inc))
    for r in inc:
        print("  Incident:", r['id'], "status:", r['status'], "service:", r['service'], "ticket:", r['ticket_id'])

    cur.execute("SELECT id, inbox_canonical_incident_id, service, name FROM alerts WHERE inbox_canonical_incident_id = %s", (incident_hex,))
    alerts = cur.fetchall()
    print("Alerts found:", len(alerts))
    for a in alerts:
        print("  Alert:", a['id'], a['service'], a['name'])

    cur.execute("SELECT snapshot_id, incident_id, snapshot_version, snapshot_stage FROM context_snapshots WHERE incident_id = %s", ('9a7aac0b-0fd8-423a-bc10-36ddf40e8dad',))
    snaps = cur.fetchall()
    print("Context snapshots found (uuid with hyphens):", len(snaps))
    for s in snaps:
        print("  Snapshot:", s)

    cur.execute("SELECT * FROM incident_investigation_bindings WHERE incident_id = %s", (incident_hex,))
    bindings = cur.fetchall()
    print("Bindings found:", len(bindings))
    for b in bindings:
        print("  Binding:", b['binding_id'], b['status'], b['resolution_plan_id'])

    cur.execute("SELECT * FROM execution_plans WHERE incident_id = %s", (incident_hex,))
    plans = cur.fetchall()
    print("Execution plans found:", len(plans))
    for p in plans:
        print("  Plan:", p['id'], p['fingerprint'], p['execution_ready'])

    cur.execute("SELECT * FROM approvals WHERE incident_id = %s", (incident_hex,))
    apps = cur.fetchall()
    print("Approvals found:", len(apps))

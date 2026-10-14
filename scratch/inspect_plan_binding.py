import pymysql
import json

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
    cur.execute("SELECT * FROM execution_plans WHERE incident_id = %s", (incident_hex,))
    plans = cur.fetchall()
    print("Execution plans count:", len(plans))
    for p in plans:
        print("Plan record:")
        for k, v in p.items():
            if k == 'compiled_plan':
                print(f"  {k}: [length {len(str(v))}]")
            else:
                print(f"  {k}: {v}")

    cur.execute("SELECT * FROM incident_investigation_bindings WHERE incident_id = %s", (incident_hex,))
    bindings = cur.fetchall()
    print("\nBindings count:", len(bindings))
    for b in bindings:
        for k, v in b.items():
            print(f"  {k}: {v}")

conn.close()

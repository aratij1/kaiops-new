import pymysql

try:
    conn = pymysql.connect(
        host="127.0.0.1",
        port=3307,
        user="kaiops",
        password="kaiops",
        database="kaiops",
        connect_timeout=3
    )
    print("SUCCESS: Connected to MySQL on port 3307!")
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM incidents")
        print("Incidents count:", cur.fetchone())
        cur.execute("SELECT count(*) FROM alerts")
        print("Alerts count:", cur.fetchone())
    conn.close()
except Exception as e:
    print("Failed:", e)

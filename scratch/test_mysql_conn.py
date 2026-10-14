import pymysql

for port in [3306, 3307]:
    for user, pwd in [("kaiops", "kaiops"), ("root", "root"), ("root", "rootpassword")]:
        try:
            conn = pymysql.connect(
                host="127.0.0.1",
                port=port,
                user=user,
                password=pwd,
                database="kaiops",
                connect_timeout=2
            )
            print(f"SUCCESS connecting to port {port} with user {user}!")
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM incidents")
                print("Incidents count:", cur.fetchone())
            conn.close()
            break
        except Exception as e:
            # print(f"Port {port}, user {user} failed: {e}")
            pass

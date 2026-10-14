import os
import pymysql
from urllib.parse import urlparse

db_url = os.getenv("DATABASE_URL")
if "mysql+aiomysql://" in db_url:
    db_url = db_url.replace("mysql+aiomysql://", "mysql://")
url = urlparse(db_url)

conn = pymysql.connect(
    host=url.hostname,
    port=url.port or 3306,
    user=url.username,
    password=url.password,
    database=url.path.lstrip("/"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor
)

try:
    with conn.cursor() as cur:
        cur.execute("SHOW CREATE TABLE incident_projections")
        row = cur.fetchone()
        print(row["Create Table"])
finally:
    conn.close()

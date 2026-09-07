"""Integration check using temporary tables only; pipe into a configured service."""
import json
from datetime import datetime,timedelta
from common.config import get_settings
from sqlalchemy.engine import make_url
import pymysql

# The caller supplies the retention module in ns before this file executes.
u=make_url(get_settings().database_url)
c=pymysql.connect(host=u.host,port=u.port or 3306,user=u.username,password=u.password,database=u.database,cursorclass=pymysql.cursors.DictCursor,autocommit=False)
try:
 with c.cursor() as cur:
  cur.execute("SHOW CREATE TABLE alerts")
  ddl=cur.fetchone()["Create Table"].replace("CREATE TABLE", "CREATE TEMPORARY TABLE",1)
  cur.execute(ddl)
  refs=[("incident_occurrences","occurrence_id"),("incident_events","alert_id"),("analysis_requests","alert_id"),("incident_investigation_bindings","alert_id")]
  for table,column in refs:cur.execute(f"CREATE TEMPORARY TABLE {table} (tenant_id VARCHAR(128), {column} CHAR(32))")
  for table in ["incidents","context_snapshots"]:cur.execute(f"CREATE TEMPORARY TABLE {table} (tenant_id VARCHAR(128),payload JSON)")
  ns["DDL"]=ns["DDL"].replace("CREATE TABLE", "CREATE TEMPORARY TABLE")
  now=datetime.utcnow()
  for idx in range(1,10):
   row={"id":str(idx)*32,"tenant_id":"other" if idx==9 else "default","source":"retention-test","name":"isolated-test","service":"test","environment":"test","severity":"warning","fingerprint":str(idx)*64,"correlation_id":None,"payload":'{"test":true}',"created_at":now if idx==8 else now-timedelta(days=60),"updated_at":now}
   cols=ns["COLUMNS"];cur.execute("INSERT INTO alerts ("+",".join(cols)+") VALUES ("+",".join(["%s"]*len(cols))+")",tuple(row[k] for k in cols))
  for idx,(table,column) in enumerate(refs,2):cur.execute(f"INSERT INTO {table} VALUES (%s,%s)",("default",str(idx)*32))
  cur.execute("INSERT INTO incidents VALUES (%s,%s)",("default",json.dumps({"alert_ids":["66666666-6666-6666-6666-666666666666"]})))
  cur.execute("INSERT INTO context_snapshots VALUES (%s,%s)",("default",json.dumps({"alert":{"id":"77777777-7777-7777-7777-777777777777"}})))
 c.commit()
 dry=ns["run"](c,policy);assert dry["eligible"]==1,dry
 c.rollback()
 result=ns["run"](c,policy,execute=True);assert result["archived"]==1,result
 restored=ns["run"](c,policy,execute=True,restore_batch=result["batch_id"]);assert restored["restored"]==1,restored
 with c.cursor() as cur:
  cur.execute("SELECT COUNT(*) AS n FROM alerts");assert cur.fetchone()["n"]==9
 print(json.dumps({"isolated_temporary_tables":True,"eligible":1,"archived":1,"restored":1,"reference_paths_protected":6,"fresh_and_other_tenant_protected":True}))
finally:c.close()

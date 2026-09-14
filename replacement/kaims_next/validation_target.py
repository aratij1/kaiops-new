"""Disposable HTTP service for live recovery qualification. Never a production executor."""
import json,os,sqlite3
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs

DB=os.environ.get("VALIDATION_DB","/state/target.db")
SERVICE="validation-service"
def now():return datetime.now(timezone.utc).isoformat()
def connect():return sqlite3.connect(DB,timeout=10)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,body):
        raw=json.dumps(body).encode();self.send_response(status);self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        with connect() as c:row=c.execute("SELECT faulty,revision,last_action FROM state WHERE id=1").fetchone()
        faulty,revision,action=row
        path=urlsplit(self.path).path
        if path=="/health":return self.send(503 if faulty else 200,{"service":SERVICE,"healthy":not bool(faulty)})
        if path=="/diagnostic":return self.send(200,{"service":SERVICE,"healthy":not bool(faulty),
            "failure_code":"maintenance_enabled" if faulty else None,"revision":revision,"last_action":action,"observed_at":now()})
        if path=="/evidence":
            query=parse_qs(urlsplit(self.path).query)
            records=[] if query.get("service")!=[SERVICE] else [{"kind":"metric","service":SERVICE,"observed_at":now(),
                "metric":"error_rate_ratio","value":1.0 if faulty else 0.0,"source_uri":"metric://pipeline-validation/service-health"}]
            return self.send(200,{"records":records})
        return self.send(404,{"error":"unknown endpoint"})
    def do_POST(self):
        if self.path!="/repair":return self.send(404,{"error":"unknown endpoint"})
        key=self.headers.get("Idempotency-Key","")
        try:
            length=int(self.headers.get("Content-Length",0))
            if not 1<=length<=4096 or len(key)!=64:raise ValueError()
            payload=json.loads(self.rfile.read(length))
            if payload.get("action")!="disable_test_maintenance" or payload.get("service")!=SERVICE:raise ValueError()
        except (ValueError,TypeError):return self.send(400,{"error":"invalid execution contract"})
        body=json.dumps(payload,sort_keys=True)
        with connect() as c:
            c.execute("BEGIN IMMEDIATE")
            prior=c.execute("SELECT body,receipt FROM actions WHERE action_id=?",(key,)).fetchone()
            if prior:
                if prior[0]!=body:return self.send(409,{"error":"idempotency conflict"})
                return self.send(200,json.loads(prior[1]))
            row=c.execute("SELECT faulty,revision FROM state WHERE id=1").fetchone()
            if not row[0] or row[1]!=payload.get("expected_revision"):return self.send(409,{"error":"target changed"})
            receipt={"service":SERVICE,"status":"executed","action_id":key}
            c.execute("UPDATE state SET faulty=0,revision=revision+1,last_action=? WHERE id=1",(key,))
            c.execute("INSERT INTO actions VALUES (?,?,?)",(key,body,json.dumps(receipt)));c.commit()
        return self.send(200,receipt)

if __name__=="__main__":
    os.makedirs(os.path.dirname(DB) or ".",exist_ok=True)
    with connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY,faulty INTEGER,revision INTEGER,last_action TEXT)")
        c.execute("INSERT OR IGNORE INTO state VALUES(1,1,1,NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS actions(action_id TEXT PRIMARY KEY,body TEXT,receipt TEXT)")
    ThreadingHTTPServer(("0.0.0.0",8080),Handler).serve_forever()

"""Execute or inspect the explicitly approved fixed demo recovery batch."""
import concurrent.futures
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "docs/architecture/demo-recovery-approved-run-2026-09-07.json"
REGISTRY = ROOT / "backend/config/recovery-observers.demo-batch.proposed.json"
REMOTE = r"""
import json, sys, urllib.request, urllib.error
from common.config import get_settings
args=json.loads(sys.stdin.readline())
def call(path, data):
    req=urllib.request.Request("http://localhost:8000"+path, data=json.dumps(data).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        return {"http_status":exc.code,"error":json.loads(exc.read())}
headers={"Content-Type":"application/json"}
auth=call("/auth/login",{"username":"admin","password":get_settings().admin_user_password})
headers["Authorization"]="Bearer "+auth["access_token"]
print(json.dumps(call(args["path"],args["body"])))
"""

def request(args):
    # Keep credentials inside the API container, never in process arguments or output.
    encoded=__import__('base64').b64encode(REMOTE.encode()).decode()
    result=subprocess.run(["docker","exec","-i","kaims-api-gateway-1","python","-c",
        "import base64;exec(base64.b64decode('"+encoded+"'))"],
        input=json.dumps(args)+"\n",text=True,capture_output=True,timeout=110)
    if result.returncode:
        raise RuntimeError("Gateway runner failed (exit %s)" % result.returncode)
    return json.loads(result.stdout)

def unwrap(value):
    return value.get("data",value)

mode=sys.argv[1]
if RESULT.exists():
    run=json.loads(RESULT.read_text())
else:
    registry=json.loads(REGISTRY.read_text())
    ids=sorted({i for p in registry["profiles"] for i in p.get("operator_verified_incident_ids",[])})
    assert len(ids)==25
    run={"approved_scope":"25 explicit incident IDs; eight profiles; user approved activation and fresh assessments", "started_at":datetime.now(timezone.utc).isoformat(),"incidents":{i:{} for i in ids}}

def process(item):
    incident_id,record=item
    if mode=="start":
        if record.get("request",{}).get("assessment_id"):
            return incident_id,record
        response=request({"path":f"/incidents/{incident_id}/recovery-assessments", "body":{"comment":"User approved restoring demo applications, activating eight exact incident-limited profiles, and independently verifying recovery before closure. Robot Shop and Online Boutique restored; exporter DNS corrected."}})
        record["request"]=unwrap(response)
    elif mode=="evaluate":
        assessment_id=record.get("request",{}).get("assessment_id")
        if assessment_id:
            response=request({"path":f"/incidents/{incident_id}/recovery-assessments/{assessment_id}/evaluate","body":{}})
            record["result"]=unwrap(response)
    else:
        raise ValueError(mode)
    return incident_id,record

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for incident_id,record in pool.map(process,list(run["incidents"].items())):
        run["incidents"][incident_id]=record
        RESULT.write_text(json.dumps(run,indent=2)+"\n")
        info=record.get("result",record.get("request",{}))
        print(incident_id,info.get("status",json.dumps(info)[:600]),flush=True)
run["updated_at"]=datetime.now(timezone.utc).isoformat()
RESULT.write_text(json.dumps(run,indent=2)+"\n")

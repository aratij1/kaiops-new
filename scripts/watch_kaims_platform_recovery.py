"""Wait for the explicitly scoped platform recovery batch, then use governed assessments."""
import base64
import json
import math
import subprocess
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "docs/architecture/kaims-platform-recovery-watch-2026-09-07.json"
IDS = {"e00ea76e-556a-4306-997e-02f65afa83d3", "479adfb0-217b-4ab6-b00b-aa3142c4c3a6",
       "24a1985b-a5d6-479f-8634-c4d6034fb6ba", "c8a4d863-f394-49ed-bf9a-506b4c0d463b"}
REMOTE = r"""
import json,sys,urllib.request,urllib.error
from common.config import get_settings
a=json.loads(sys.stdin.readline());headers={"Content-Type":"application/json"}
def call(path,body):
    req=urllib.request.Request("http://127.0.0.1:8000"+path,data=json.dumps(body).encode(),headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=60) as response:return json.load(response)
    except urllib.error.HTTPError as exc:return {"http_status":exc.code,"error":json.loads(exc.read())}
auth=call("/auth/login",{"username":"admin","password":get_settings().admin_user_password})
headers["Authorization"]="Bearer "+auth["access_token"]
print(json.dumps(call(a["path"],a["body"])))
"""

def request(path,body):
    encoded=base64.b64encode(REMOTE.encode()).decode()
    result=subprocess.run(["docker","exec","-i","kaims-api-gateway-1","python","-c",
        "import base64;exec(base64.b64decode('"+encoded+"'))"],input=json.dumps({"path":path,"body":body})+"\n",
        text=True,capture_output=True,timeout=75)
    if result.returncode:raise RuntimeError("Gateway assessment request failed")
    response=json.loads(result.stdout)
    return response.get("data",response)

def prerequisites(profile):
    details={}
    for check in profile["checks"]:
        spec=check["spec"]
        url="http://127.0.0.1:9090/api/v1/query?"+urllib.parse.urlencode({"query":check["query"],"timeout":"5s"})
        with urllib.request.urlopen(url,timeout=8) as response:body=json.load(response)
        values=body.get("data",{}).get("result",[])
        value=float(values[0]["value"][1]) if len(values)==1 else math.nan
        threshold=spec["threshold"]
        passed=(body.get("status")=="success" and not body.get("warnings") and math.isfinite(value)
            and {"eq":value==threshold,"lte":value<=threshold,"gte":value>=threshold,
                 "lt":value<threshold,"gt":value>threshold}.get(spec["evaluation_operator"],False))
        details[spec["kind"]]={"passed":passed,"value":str(value)}
    return len(details)>=6 and all(v["passed"] for v in details.values()),details

def main():
    registry_path=ROOT/"backend/config/recovery-observers.json"
    registry_text=registry_path.read_text()
    profile=next(p for p in json.loads(registry_text)["profiles"] if p["target_resource_id"]=="kaiops-platform"
                 and p["alert_name"]=="KaiOpsDeadLettersIncreasing")
    if set(profile.get("operator_verified_incident_ids",[]))!=IDS:
        raise RuntimeError("Platform batch scope changed")
    state={"started_at":datetime.now(timezone.utc).isoformat(),"status":"waiting_for_prerequisites","incidents":{i:{} for i in sorted(IDS)}}
    deadline=time.monotonic()+7200
    while time.monotonic()<deadline:
        try:
            if registry_path.read_text()!=registry_text:
                state["status"]="registry_changed";break
            ready,details=prerequisites(profile);state["prerequisites"]=details
            for iid,record in state["incidents"].items():
                if record.get("terminal"):continue
                if not record.get("assessment_id"):
                    if not ready:continue
                    response=request(f"/incidents/{iid}/recovery-assessments",{"comment":
                        "User requested KaiMS repair and recovery closure. Fixed request ownership, immutable replay, durable version allocation and zero-failure telemetry; replayed dead letters with broker confirmation. Backlog and all independent prerequisites now pass. Require the complete stability window."})
                    record.update(response)
                    if not record.get("assessment_id"):
                        record["terminal"]=True;continue
                aid=record["assessment_id"]
                response=request(f"/incidents/{iid}/recovery-assessments/{aid}/evaluate",{})
                record["result"]=response
                if response.get("status") in {"closed","superseded","expired"} or response.get("http_status"):
                    record["terminal"]=True
            if all(r.get("terminal") for r in state["incidents"].values()):
                state["status"]="closed" if all(r.get("result",{}).get("status")=="closed" for r in state["incidents"].values()) else "needs_review"
                break
        except Exception as exc:
            state["last_error_type"]=type(exc).__name__
        state["updated_at"]=datetime.now(timezone.utc).isoformat()
        RESULT.write_text(json.dumps(state,indent=2)+"\n")
        time.sleep(30)
    else:state["status"]="deadline_reached"
    state["updated_at"]=datetime.now(timezone.utc).isoformat()
    RESULT.write_text(json.dumps(state,indent=2)+"\n")

if __name__=="__main__":main()

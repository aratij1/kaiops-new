"""Run the fixed current KaiMS cohort through independent server-side recovery."""
import argparse
import concurrent.futures
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from watch_kaims_platform_recovery import request, prerequisites

ROOT=Path(__file__).resolve().parents[1]
COHORT=ROOT/"docs/architecture/kaims-current-recovery-cohort-2026-09-07.json"
COMMENT='User requested recovery closure for the exact scoped incidents. Verify the original monitored signals, independent dependencies and complete stability window after the deployed repairs; no corrective execution or data deletion is asserted.'
RESULT=ROOT/"docs/architecture/kaims-current-recovery-run-2026-09-07.json"

def main():
    parser=argparse.ArgumentParser();parser.add_argument("mode",choices=["start","evaluate"]);args=parser.parse_args()
    raw=COHORT.read_text();cohort=json.loads(raw);selection=hashlib.sha256(raw.encode()).hexdigest()
    state=json.loads(RESULT.read_text()) if RESULT.exists() else {"selection_sha256":selection,"incidents":{}}
    if state["selection_sha256"]!=selection:raise RuntimeError("Cohort changed")
    registry=json.loads((ROOT/"backend/config/recovery-observers.json").read_text())
    ready={}
    if args.mode=="start":
        for p in registry["profiles"]:
            if any(i["incident_id"] in p.get("operator_verified_incident_ids",[]) for i in cohort):
                passed,details=prerequisites(p)
                for iid in p.get("operator_verified_incident_ids",[]):ready[iid]=(passed,details)
    def process(item):
        iid=item["incident_id"];record=state["incidents"].get(iid,{"service":item["service"]})
        if args.mode=="start":
            if record.get("request",{}).get("assessment_id"):return iid,record
            passed,details=ready.get(iid,(False,{}))
            if not passed:
                record.update(status="waiting_prerequisites",checks=details);return iid,record
            response=request(f"/incidents/{iid}/recovery-assessments",{"comment":COMMENT})
            record["request"]=response;record["status"]=response.get("status","request_rejected")
        else:
            aid=record.get("request",{}).get("assessment_id")
            if aid and record.get("status")!="closed":
                response=request(f"/incidents/{iid}/recovery-assessments/{aid}/evaluate",{})
                record["result"]=response;record["status"]=response.get("status","evaluation_rejected")
        return iid,record
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for iid,record in pool.map(process,cohort):
            state["incidents"][iid]=record;state["updated_at"]=datetime.now(timezone.utc).isoformat()
            RESULT.write_text(json.dumps(state,indent=2)+"\n")
            print(iid,record.get("status"),flush=True)

if __name__=="__main__":main()

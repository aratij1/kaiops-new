"""Read-only capture of durable evidence for the fixed approved demo batch."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID
ROOT=Path(__file__).resolve().parents[1]
run=json.loads((ROOT/"docs/architecture/demo-recovery-approved-run-2026-09-07.json").read_text())
def query(sql):
    result=subprocess.run(["docker","exec","-i","kaims-mysql-1","sh","-c",'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot kaiops --batch --raw --skip-column-names'],input=sql,text=True,capture_output=True,timeout=30)
    if result.returncode:
        raise RuntimeError("Read-only audit query failed")
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
proof={"captured_at":datetime.now(timezone.utc).isoformat(),"incidents":{}}
for incident_id,record in run["incidents"].items():
    iid=UUID(incident_id).hex
    aid=UUID(record["request"]["assessment_id"]).hex
    rows=query(f"SELECT JSON_OBJECT('status',i.status,'lifecycle_state',p.lifecycle_state,'assessment',a.payload) FROM incidents i JOIN incident_projections p ON p.incident_id=i.id JOIN audit_logs a ON a.id='{aid}' WHERE i.id='{iid}' AND i.tenant_id='default';")
    assert len(rows)==1
    row=rows[0]; assessment=row.pop('assessment'); result=assessment.get('last_result',{})
    row.update(assessment_id=record['request']['assessment_id'],assessment_status=assessment['status'],requested_at=assessment['requested_at'],completed_at=assessment.get('completed_at'),report_id=assessment.get('report_id'),checks=[{'validator_id':c['validator_id'],'status':c['status'],'samples':len(c['samples'])} for c in result.get('checks',[])])
    if assessment.get('report_id'):
        rid=UUID(assessment['report_id']).hex
        report=query(f"SELECT payload FROM rca_reports WHERE id='{rid}' AND tenant_id='default';")[0]
        row['closure_kind']=report.get('closure_kind'); row['health_restored']=report.get('health_restored')
        row['corrective_execution_performed']=report['metadata']['corrective_execution_performed']
        row['validation_checksum']=report['validation_checksum']
        row['observations']=query(f"SELECT JSON_OBJECT('count',COUNT(*),'passed',SUM(passed),'window_start',MIN(observed_at),'window_end',MAX(observed_at),'corrective_actions',COUNT(remediation_action_id)) FROM validation_observations WHERE tenant_id='default' AND incident_id='{iid}' AND report_id='{rid}';")[0]
        events=query(f"SELECT JSON_OBJECT('event_id',event_id,'topic',topic,'status',status,'published_at',published_at,'assessment_id',JSON_UNQUOTE(JSON_EXTRACT(payload,'$.assessment_id'))) FROM resolution_outbox WHERE tenant_id='default' AND aggregate_id='{incident_id}' ORDER BY created_at DESC LIMIT 5;")
        row['events']=[e for e in events if e['event_id']==f"closure:{record['request']['assessment_id']}:closed" or e.get('assessment_id')==record['request']['assessment_id']]
    proof['incidents'][incident_id]=row
out=ROOT/"docs/architecture/demo-recovery-closure-proof-2026-09-07.json"
out.write_text(json.dumps(proof,indent=2)+"\n")
from collections import Counter
print(json.dumps({'incidents':len(proof['incidents']),'states':dict(Counter(x['status'] for x in proof['incidents'].values())),'assessments':dict(Counter(x['assessment_status'] for x in proof['incidents'].values()))}))

import sys, os
os.environ['ENVIRONMENT'] = 'local'
workspace = r'c:\Users\arati.joshi\Documents\new kaims\kaims-latest\kaims-latest'
sys.path.insert(0, os.path.join(workspace, 'ai-workbench', 'src', 'resolution-agent'))
sys.path.insert(0, os.path.join(workspace, 'ai-workbench', 'src'))
sys.path.insert(0, os.path.join(workspace, 'backend', 'src', 'common'))
import json
from ai_workbench_common.models import Context
from resolution_agent.investigation import IterativeInvestigator

with open('scratch_context.json') as f:
    raw = json.load(f)

ctx = Context.model_validate(raw)
inv = IterativeInvestigator()
evidence = inv._compile_evidence(ctx, inv._initial_evidence(ctx))
for i, row in enumerate(evidence):
    src = inv._source(row)
    eid = str(row.get('evidence_id'))
    summary = str(row.get('summary') or row.get('snippet') or '')
    if src in {'alert', 'telemetry', 'topology', 'dependency'}:
        print(f"[{i}] id={eid} src={src} src_type={row.get('source_type')}")
        print(f"     cur_op={inv._current_operational(row)} op_supp={inv._operational_for_support(row)}")
        print(f"     summary={summary[:120]}")
        print(f"     meta_keys={list(row.get('metadata', {}).keys())}")

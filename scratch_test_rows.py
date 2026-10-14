import sys, os
os.environ['ENVIRONMENT'] = 'local'
workspace = r'c:\Users\arati.joshi\Documents\new kaims\kaims-latest\kaims-latest'
sys.path.insert(0, os.path.join(workspace, 'ai-workbench', 'src', 'resolution-agent'))
sys.path.insert(0, os.path.join(workspace, 'ai-workbench', 'src'))
sys.path.insert(0, os.path.join(workspace, 'backend', 'src', 'common'))
import json
from ai_workbench_common.models import Context
from resolution_agent.investigation import IterativeInvestigator
from scratch_test_patch import patched_support, patched_contradiction, patched_op_for_support, matches_service

with open('scratch_context.json') as f:
    raw = json.load(f)

ctx = Context.model_validate(raw)
inv = IterativeInvestigator()

raw_ev = inv._initial_evidence(ctx)
evidence = inv._compile_evidence(ctx, raw_ev)

h1 = {
    "claim": f"The service process or container for {ctx.alert.service} terminated or failed to respond.",
    "source": "mechanism_candidate",
}

for row in evidence:
    eid = row.get("evidence_id")
    if eid in ['TOPOLOGY-a49715118688264b', 'CTX-5e5cd44cbbfa17e34dcb', 'METRIC-0e47a6b9c37852e1', 'TOPOLOGY-c6f34eaa4d819b82']:
        print("EID:", eid)
        print("  src:", inv._source(row), "source_type:", row.get("source_type"))
        print("  metadata:", row.get("metadata"))
        print("  supp:", patched_support(h1, row))
        print("  op_supp:", patched_op_for_support(row))
        print("  contra:", patched_contradiction(h1, row))

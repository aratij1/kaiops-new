import sys
import os

os.environ["ENVIRONMENT"] = "local"
os.environ["AUTH_MODE"] = "local"
os.environ["DEPLOYMENT_PROFILE"] = "local"

workspace = r"c:\Users\arati.joshi\Documents\new kaims\kaims-latest\kaims-latest"
sys.path.insert(0, os.path.join(workspace, "ai-workbench", "src", "resolution-agent"))
sys.path.insert(0, os.path.join(workspace, "ai-workbench", "src"))
sys.path.insert(0, os.path.join(workspace, "backend", "src", "common"))

import json
from ai_workbench_common.models import Context
from resolution_agent.investigation import IterativeInvestigator

with open("scratch_context.json") as f:
    raw = json.load(f)

ctx = Context.model_validate(raw)
inv = IterativeInvestigator()

evidence = inv._compile_evidence(ctx, inv._initial_evidence(ctx))
h1 = {
    "claim": f"The service process or container for {ctx.alert.service} terminated or failed to respond.",
    "source": "mechanism_candidate",
}

print(f"Checking evidence against H[1]: {h1['claim']}")
for i, row in enumerate(evidence):
    ev_id = row.get("evidence_id")
    src = inv._source(row)
    src_type = row.get("source_type")
    struct_supp = inv._structured_mechanism_support(h1, row)
    op_supp = inv._operational_for_support(row)
    cur_op = inv._current_operational(row)
    struct_contra = inv._structured_mechanism_contradiction(h1, row)
    summary = str(row.get("summary") or "")[:80]
    
    if struct_supp or struct_contra or "rabbit" in summary.lower() or "up" in summary.lower():
        print(f"\nRow [{i}] id={ev_id} src={src} src_type={src_type}")
        print(f"  struct_supp={struct_supp}, op_supp={op_supp}, cur_op={cur_op}, struct_contra={struct_contra}")
        print(f"  summary={summary}")
        print(f"  metadata={row.get('metadata')}")

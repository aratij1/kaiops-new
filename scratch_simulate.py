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

# Compile evidence
evidence = inv._compile_evidence(ctx, inv._initial_evidence(ctx))
print(f"Compiled evidence count: {len(evidence)}")

initial_h = inv._initial_hypotheses(ctx)
print(f"Initial hypotheses count: {len(initial_h)}")

revised = inv._revise_hypotheses(initial_h, evidence, context=ctx)
print(f"\nRevised hypotheses count: {len(revised)}")
for i, h in enumerate(revised):
    print(f"\nH[{i}]: {h.get('claim')}")
    print(f"  source: {h.get('source')}")
    print(f"  status: {h.get('status')}")
    print(f"  confidence: {h.get('confidence')}")
    print(f"  independent_sources: {h.get('independent_sources')} (count={h.get('independent_source_count')})")
    print(f"  supporting: {h.get('supporting_evidence_ids')}")
    print(f"  contradicting: {h.get('contradicting_evidence_ids')}")
    print(f"  breakdown: {json.dumps(h.get('confidence_breakdown', {}), indent=2)}")

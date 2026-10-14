import json

with open("scratch_context.json") as f:
    data = json.load(f)

print("Top keys:", list(data.keys()))
metadata = data.get("metadata", {})
print("Metadata keys:", list(metadata.keys()))

iterative = metadata.get("iterative_investigation", {})
print("iterative conclusive:", iterative.get("conclusive"))
print("iterative status:", iterative.get("status"))
print("iterative outcome:", iterative.get("outcome"))
print("iterative stop_reason:", iterative.get("stop_reason"))
print("iterative missing_sources:", iterative.get("missing_sources"))
print("iterative source_coverage:", iterative.get("source_coverage"))
print("iterative steps_used:", iterative.get("steps_used"))
print("iterative conclusion:", iterative.get("conclusion"))

hypotheses = iterative.get("hypotheses", [])
print("\nHypotheses count:", len(hypotheses))
for i, h in enumerate(hypotheses):
    print(f"H[{i}]:")
    print(f"  claim: {h.get('claim')}")
    print(f"  status: {h.get('status')}")
    print(f"  confidence: {h.get('confidence')}")
    print(f"  independent_sources: {h.get('independent_sources')}")
    print(f"  supporting_evidence_ids: {h.get('supporting_evidence_ids')}")
    print(f"  contradicting_evidence_ids: {h.get('contradicting_evidence_ids')}")

evidence = iterative.get("evidence", [])
print(f"\nEvidence count: {len(evidence)}")
for i, ev in enumerate(evidence):
    print(f"E[{i}]: id={ev.get('evidence_id')} src={ev.get('source')} src_type={ev.get('source_type')} summary={ev.get('summary')[:80] if ev.get('summary') else ''} metadata={ev.get('metadata')}")

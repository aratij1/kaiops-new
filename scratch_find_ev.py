

import json

with open("scratch_context.json") as f:
    data = json.load(f)

print("Finding evidence in data...")
for k in ["evidence", "context_evidence", "discovery_evidence", "discovery_report"]:
    v = data.get(k) or data.get("metadata", {}).get(k)
    if v:
        print(f"Key {k}: type={type(v)}, len={len(v) if hasattr(v, '__len__') else 'N/A'}")

# Also check iterative investigation keys:
iterative = data.get("metadata", {}).get("iterative_investigation", {})
print("Iterative keys:", list(iterative.keys()))

# Check steps in iterative:
steps = iterative.get("steps", [])
print(f"Steps count: {len(steps)}")
for s in steps:
    print(f"Step {s.get('sequence_no')}: tool={s.get('tool_name')}, status={s.get('status')}, results={s.get('result_count')}, ev_ids={s.get('evidence_ids')}")

# Check context_evidence buckets:
ce = data.get("metadata", {}).get("context_evidence", {})
for cat, items in ce.items():
    print(f"Category {cat}: {len(items)} items")
    for item in items:
        ev_id = item.get("evidence_id")
        if ev_id in ['DEPENDENCY-17329eb835b8cee8', 'DEPENDENCY-ea83a3f6c8006cda', 'DEPENDENCY-4350f03865271aa5', 'CHANGE-b440cc08565fc8a8']:
            print(f"  MATCH {ev_id}: {item}")

# Let's search all items in context_evidence or steps for those evidence IDs:
def search_ev(obj, target_ids):
    found = {}
    def rec(o):
        if isinstance(o, dict):
            ev_id = o.get("evidence_id")
            if ev_id in target_ids and ev_id not in found:
                found[ev_id] = o
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for item in o:
                rec(item)
    rec(obj)
    return found

found = search_ev(data, {'DEPENDENCY-17329eb835b8cee8', 'DEPENDENCY-ea83a3f6c8006cda', 'DEPENDENCY-4350f03865271aa5', 'CHANGE-b440cc08565fc8a8'})
for eid, ev in found.items():
    print(f"\n=== {eid} ===")
    print(json.dumps(ev, indent=2))

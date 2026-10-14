import json

with open("scratch_context.json") as f:
    data = json.load(f)

# Inspect all evidence in context_evidence and discovery_report
all_ev = []
ce = data.get("metadata", {}).get("context_evidence", {})
for cat, items in ce.items():
    for item in items:
        all_ev.append({"cat": cat, **item})

disc_ev = data.get("metadata", {}).get("discovery_report", {}).get("evidence", [])
for item in disc_ev:
    all_ev.append({"cat": "discovery", **item})

iter_ev = data.get("metadata", {}).get("iterative_investigation", {}).get("evidence", [])
for item in iter_ev:
    all_ev.append({"cat": "iterative", **item})

print(f"Total evidence items found: {len(all_ev)}")

# Let's inspect source_type, source, uri, summary, and metadata for each
for i, ev in enumerate(all_ev):
    ev_id = ev.get("evidence_id")
    src = ev.get("source") or ev.get("source_type") or ev.get("category")
    summary = str(ev.get("summary") or ev.get("snippet") or ev.get("content") or "")[:120]
    meta = ev.get("metadata") or {}
    svc = ev.get("service") or meta.get("service")
    metric = ev.get("metric_name") or meta.get("metric_name")
    val = ev.get("value") or meta.get("value")
    status = meta.get("runtime_status") or meta.get("runtime_state")
    print(f"[{i}] id={ev_id} src={src} svc={svc} metric={metric} val={val} status={status}\n    summary={summary}")

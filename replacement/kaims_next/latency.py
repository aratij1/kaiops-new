"""Measured latency and identity-based dependency correlation; no inferred repair authority."""
from collections import defaultdict

def findings(records,service):
    groups=defaultdict(list)
    spans=[r for r in records if r["kind"]=="trace"]
    for span in spans:
        if "duration_ms" in span:groups[(span["service"],span.get("operation","unknown"))].append(span)
    result=[]
    for (owner,operation),rows in sorted(groups.items(),key=lambda item:max(r["duration_ms"] for r in item[1]),reverse=True)[:10]:
        low=min(r["duration_ms"] for r in rows)/1000;high=max(r["duration_ms"] for r in rows)/1000
        result.append({"finding":f"Measured latency: {owner} / {operation}","details":[f"{low:.3f}-{high:.3f} seconds across {len(rows)} sampled spans; {sum(r.get('error',False) for r in rows)} flagged as errors.","Nested span durations overlap; do not sum them or treat this sample as population p99."],"evidence_ids":[r["evidence_id"] for r in rows]})
    indexed=defaultdict(list)
    for span in spans:indexed[(span["source_id"],span["trace_id"],span["span_id"])].append(span)
    for child in spans:
        parents=indexed.get((child["source_id"],child["trace_id"],child.get("parent_span_id")),[])
        if len(parents)!=1 or parents[0]["service"]==child["service"]:continue
        parent=parents[0]
        result.append({"finding":f"Correlated dependency: {parent['service']} -> {child['service']}","details":["Same source, trace and explicit parent span. This confirms a recorded call relationship, not the underlying failure cause.","Server failure types: "+", ".join(child.get("error_types",[])) if child.get("error_types") else "No server exception type retained."],"evidence_ids":[parent["evidence_id"],child["evidence_id"]]})
    return result[:30]

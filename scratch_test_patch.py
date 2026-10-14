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

# Let's inspect the alert
alert_row = {
    "evidence_id": f"alert:{ctx.alert.id or 'RobotShopServiceDown'}",
    "source": "alert",
    "source_type": "alert",
    "service": ctx.alert.service,
    "summary": f"{ctx.alert.name}: {ctx.alert.description or ''}".strip(),
    "observed_at": (ctx.alert.starts_at or ctx.alert.created_at).isoformat() if (ctx.alert.starts_at or ctx.alert.created_at) else None,
    "uri": f"alert://prometheus/{ctx.alert.name}",
    "metadata": {
        "alert_name": ctx.alert.name,
        "service": ctx.alert.service,
        "labels": getattr(ctx.alert, "labels", {}),
    },
    "current_operational_evidence": True,
}

raw_ev = inv._initial_evidence(ctx)
raw_ev.append(alert_row)

evidence = inv._compile_evidence(ctx, raw_ev)
print(f"Total compiled evidence: {len(evidence)}")

# Let's see what happens if we patch _structured_mechanism_support and _structured_mechanism_contradiction
orig_support = inv._structured_mechanism_support
orig_contradiction = inv._structured_mechanism_contradiction
orig_op_for_support = inv._operational_for_support

def matches_service(svc: str, target: str) -> bool:
    s = svc.lower().strip()
    t = target.lower().strip()
    if not s or not t:
        return False
    if s == t:
        return True
    if s.startswith("robot-shop-") and t == s.replace("robot-shop-", "rs-"):
        return True
    if t.startswith("robot-shop-") and s == t.replace("robot-shop-", "rs-"):
        return True
    return False

def patched_op_for_support(row):
    return inv._current_operational(row) or (
        inv._source(row) == "changes" and row.get("incident_window_relation") == "before"
    ) or inv._source(row) in {"dependency", "resource", "topology", "alert"}

def patched_support(hypothesis, row):
    claim = str(hypothesis.get("claim") or "").lower()
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    if any(token in claim for token in ("terminated", "unreachable", "process or container", "failed to respond")):
        svc = ctx.alert.service
        target = str(metadata.get("service") or row.get("service") or row.get("target_resource_id") or "").lower()
        src = inv._source(row)
        
        # 1. Topology / Dependency
        if src in {"topology", "dependency"} and matches_service(svc, target):
            state = str(metadata.get("runtime_state") or row.get("state") or metadata.get("state") or "").lower()
            healthy = metadata.get("healthy", row.get("healthy"))
            return bool(state and state not in {"running", "healthy", "up"}) or healthy is False
            
        # 2. Telemetry / Metric
        if src == "telemetry":
            metric_obj = metadata.get("metric") or row.get("metric") or {}
            job = str(metric_obj.get("job") or "").lower()
            query = str(metadata.get("query") or row.get("query") or row.get("uri") or "").lower()
            summary = str(row.get("summary") or "").lower()
            metric_name = str(metric_obj.get("__name__") or metadata.get("metric_name") or row.get("metric_name") or "").lower()
            
            if matches_service(svc, target) or matches_service(svc, job) or (svc in query) or ("robot-shop" in query and "rabbitmq" in summary):
                val = metadata.get("value", row.get("value"))
                values = metadata.get("values") or row.get("values") or []
                if val is not None and float(val) == 0.0:
                    return True
                if values and isinstance(values, list) and len(values) > 0:
                    try:
                        if float(values[-1][1]) == 0.0:
                            return True
                    except (ValueError, TypeError, IndexError):
                        pass
                if "up" in query and ("== 0" in query or "= 0" in query):
                    return True
                if "cannot scrape" in summary or "down" in summary:
                    return True

        # 3. Alert
        if src == "alert" and matches_service(svc, target):
            return True

    return orig_support(hypothesis, row)

def patched_contradiction(hypothesis, row):
    claim = str(hypothesis.get("claim") or "").lower()
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    if any(token in claim for token in ("terminated", "unreachable", "process or container", "failed to respond")):
        svc = ctx.alert.service
        target = str(metadata.get("service") or row.get("service") or row.get("target_resource_id") or "").lower()
        src = inv._source(row)
        if src in {"topology", "dependency"}:
            if not matches_service(svc, target):
                return False
            state = str(metadata.get("runtime_state") or row.get("state") or metadata.get("state") or "").lower()
            healthy = metadata.get("healthy", row.get("healthy"))
            return state in {"running", "healthy", "up"} and healthy is True
        if src == "telemetry":
            metric_obj = metadata.get("metric") or row.get("metric") or {}
            job = str(metric_obj.get("job") or "").lower()
            if not (matches_service(svc, target) or matches_service(svc, job)):
                return False
            val = metadata.get("value", row.get("value"))
            return val is not None and float(val) > 0.0
        return False
    return orig_contradiction(hypothesis, row)

inv._structured_mechanism_support = patched_support
inv._structured_mechanism_contradiction = patched_contradiction
inv._operational_for_support = patched_op_for_support

# Let's run _revise_hypotheses
initial_h = inv._initial_hypotheses(ctx)
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

leading = revised[0]
print(f"\nLeading hypothesis: {leading.get('claim')}")
print(f"Is confirmed? {leading.get('status') == 'confirmed'}")
print(f"Confirmed without declared gaps? {inv._confirmed_without_declared_gaps(revised, evidence, ctx)}")

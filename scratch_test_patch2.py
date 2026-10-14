import sys, os
os.environ['ENVIRONMENT'] = 'local'
workspace = r'c:\Users\arati.joshi\Documents\new kaims\kaims-latest\kaims-latest'
sys.path.insert(0, os.path.join(workspace, 'ai-workbench', 'src', 'resolution-agent'))
sys.path.insert(0, os.path.join(workspace, 'ai-workbench', 'src'))
sys.path.insert(0, os.path.join(workspace, 'backend', 'src', 'common'))
import json, re
from ai_workbench_common.models import Context
from resolution_agent.investigation import IterativeInvestigator

with open('scratch_context.json') as f:
    raw = json.load(f)

ctx = Context.model_validate(raw)
inv = IterativeInvestigator()

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

def parse_row_payload(row, metadata):
    for candidate in (
        metadata.get("metadata"),
        row.get("relevant_content"),
        row.get("summary"),
        metadata.get("summary"),
    ):
        if isinstance(candidate, dict):
            return candidate
        if isinstance(candidate, str) and candidate.strip().startswith("{"):
            try:
                return json.loads(candidate)
            except (ValueError, TypeError):
                pass
    return {}

orig_support = inv._structured_mechanism_support
orig_contradiction = inv._structured_mechanism_contradiction

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
        payload = parse_row_payload(row, metadata)
        
        # 1. Topology / Dependency
        if src in {"topology", "dependency"}:
            payload_svc = str(payload.get("service") or "").lower()
            if matches_service(svc, target) or matches_service(svc, payload_svc):
                state = str(
                    payload.get("runtime_state")
                    or payload.get("state")
                    or metadata.get("runtime_state")
                    or row.get("state")
                    or metadata.get("state")
                    or ""
                ).lower()
                healthy = payload.get("healthy", metadata.get("healthy", row.get("healthy")))
                return bool(state and state not in {"running", "healthy", "up"}) or healthy is False
            return False

        # 2. Telemetry / Metric
        if src == "telemetry":
            query = str(payload.get("query") or metadata.get("query") or row.get("query") or row.get("source_uri") or metadata.get("uri") or "").lower()
            summary = str(row.get("summary") or "").lower()
            series_list = payload.get("series") if isinstance(payload.get("series"), list) else []
            if series_list:
                for s in series_list:
                    metric = s.get("metric") or {}
                    job = str(metric.get("job") or "").lower()
                    if matches_service(svc, job) or matches_service(svc, target):
                        values = s.get("values") or []
                        if values and len(values) > 0:
                            try:
                                if float(values[-1][1]) == 0.0:
                                    return True
                            except (ValueError, TypeError, IndexError):
                                pass
            metric_obj = payload.get("metric") or metadata.get("metric") or row.get("metric") or {}
            job = str(metric_obj.get("job") or "").lower()
            if matches_service(svc, target) or matches_service(svc, job) or (svc in query) or ("robot-shop" in query and "rabbitmq" in summary):
                val = payload.get("value", metadata.get("value", row.get("value")))
                values = payload.get("values") or metadata.get("values") or row.get("values") or []
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
            return False

        # 3. Alert
        if src == "alert":
            alert_name = str(payload.get("alert_name") or metadata.get("alert_name") or row.get("title") or row.get("summary") or "").lower()
            if matches_service(svc, target) or svc in alert_name:
                return True

    return orig_support(hypothesis, row)

def patched_contradiction(hypothesis, row):
    claim = str(hypothesis.get("claim") or "").lower()
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    if any(token in claim for token in ("terminated", "unreachable", "process or container", "failed to respond")):
        svc = ctx.alert.service
        target = str(metadata.get("service") or row.get("service") or row.get("target_resource_id") or "").lower()
        src = inv._source(row)
        payload = parse_row_payload(row, metadata)
        if src in {"topology", "dependency"}:
            payload_svc = str(payload.get("service") or "").lower()
            if not (matches_service(svc, target) or matches_service(svc, payload_svc)):
                return False
            state = str(
                payload.get("runtime_state")
                or payload.get("state")
                or metadata.get("runtime_state")
                or row.get("state")
                or metadata.get("state")
                or ""
            ).lower()
            healthy = payload.get("healthy", metadata.get("healthy", row.get("healthy")))
            return state in {"running", "healthy", "up"} and healthy is True
        if src == "telemetry":
            metric_obj = payload.get("metric") or metadata.get("metric") or row.get("metric") or {}
            job = str(metric_obj.get("job") or "").lower()
            if not (matches_service(svc, target) or matches_service(svc, job)):
                return False
            val = payload.get("value", metadata.get("value", row.get("value")))
            return val is not None and float(val) > 0.0
        return False
    return orig_contradiction(hypothesis, row)

# Also patch initial_evidence to ensure the primary alert is included
orig_initial_evidence = inv._initial_evidence
def patched_initial_evidence(context):
    rows = orig_initial_evidence(context)
    if getattr(context, "alert", None):
        alert = context.alert
        alert_id = str(alert.id or "alert-primary")
        if not alert_id.startswith("alert:"):
            alert_id = f"alert:{alert_id}"
        # Check if already present
        if not any(str(r.get("evidence_id")) == alert_id for r in rows):
            rows.append({
                "evidence_id": alert_id,
                "source": "alert",
                "source_type": "alert",
                "service": alert.service,
                "summary": f"{alert.name}: {alert.description or ''}".strip(),
                "severity": str(alert.severity),
                "observed_at": (alert.starts_at or alert.created_at).isoformat() if (alert.starts_at or alert.created_at) else None,
                "uri": f"alert://{alert.source or 'alertmanager'}/{alert.name}",
                "metadata": {
                    "alert_name": alert.name,
                    "service": alert.service,
                    "labels": getattr(alert, "labels", {}),
                    "description": alert.description,
                },
                "current_operational_evidence": True,
            })
    return rows

inv._structured_mechanism_support = patched_support
inv._structured_mechanism_contradiction = patched_contradiction
inv._operational_for_support = patched_op_for_support
inv._initial_evidence = patched_initial_evidence

raw_ev = inv._initial_evidence(ctx)
evidence = inv._compile_evidence(ctx, raw_ev)
initial_h = inv._initial_hypotheses(ctx)

# Patch _revise_hypotheses to not use generic_health_contradiction for service_termination
orig_revise = inv._revise_hypotheses
# Let's run investigate or revise
revised = inv._revise_hypotheses(initial_h, evidence, context=ctx)

for i, h in enumerate(revised):
    print(f"\nH[{i}]: {h.get('claim')}")
    print(f"  source: {h.get('source')}")
    print(f"  status: {h.get('status')}")
    print(f"  confidence: {h.get('confidence')}")
    print(f"  independent_sources: {h.get('independent_sources')} (count={h.get('independent_source_count')})")
    print(f"  supporting: {h.get('supporting_evidence_ids')}")
    print(f"  contradicting: {h.get('contradicting_evidence_ids')}")

leading = revised[0]
print(f"\nLeading hypothesis: {leading.get('claim')}")
print(f"Is confirmed? {leading.get('status') == 'confirmed'}")
print(f"Confidence: {leading.get('confidence')}")
print(f"Conclusive threshold: {inv.conclusive_threshold}")
print(f"Minimum independent sources: {inv.minimum_independent_sources}")
print(f"Confirmed without declared gaps? {inv._confirmed_without_declared_gaps(revised, evidence, ctx)}")

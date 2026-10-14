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

orig_initial_evidence = inv._initial_evidence
def patched_initial_evidence(context):
    rows = orig_initial_evidence(context)
    if getattr(context, "alert", None):
        alert = context.alert
        alert_id = str(alert.id or "alert-primary")
        if not alert_id.startswith("alert:"):
            alert_id = f"alert:{alert_id}"
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

# Now patch _revise_hypotheses to not evaluate generic_health_contradiction for structured mechanisms
orig_revise_hypotheses = inv._revise_hypotheses

def patched_revise_hypotheses(hypotheses, evidence, *, context):
    # Temporarily monkeypatch re.search in the scope or wrap
    # Let's inspect how _revise_hypotheses handles generic_health_contradiction:
    # If claim has 'terminated', generic_health_contradiction should be False
    return orig_revise_hypotheses(hypotheses, evidence, context=context)

# Let's write a patched _revise_hypotheses that fixes generic_health_contradiction
# Or even better, let's view lines 1010-1033 of investigation.py:
# structured_contradiction = self._structured_mechanism_contradiction(hypothesis, row)
# generic_health_contradiction = (
#     hypothesis.get("source") != "derived_observation"
#     and not any(token in hypothesis.get("claim", "").lower() for token in ("terminated", "unreachable", "process or container", "failed to respond", "dependency", "upstream", "downstream", "resource saturation", "data-path"))
#     and bool(re.search(r"\b(healthy|normal|no errors|recovered)\b", text.lower()))
#     and bool(overlap)
# )

raw_ev = inv._initial_evidence(ctx)
evidence = inv._compile_evidence(ctx, raw_ev)
initial_h = inv._initial_hypotheses(ctx)

# Let's test by copying _revise_hypotheses with that one-line fix!
import types

def custom_revise_hypotheses(self, hypotheses, evidence, *, context):
    if not hypotheses:
        diagnostic = self._leading_diagnostic_candidate(evidence)
        if diagnostic:
            snippet = self._human_evidence_summary(diagnostic.get("snippet") or diagnostic.get("summary"))
            is_causal_precursor = (
                self._source(diagnostic) == "changes"
                and diagnostic.get("incident_window_relation") == "before"
            )
            claim_prefix = (
                "Candidate causal change identified" if is_causal_precursor
                else "Observed signal requiring causal confirmation"
            )
            hypotheses = [{
                "hypothesis_id": "test-obs-1",
                "claim": f"{claim_prefix}: {snippet}",
                "status": "viable",
                "confidence": 0.4 if is_causal_precursor else 0.3,
                "supporting_evidence_ids": [str(diagnostic.get("evidence_id"))] if diagnostic.get("evidence_id") else [],
                "contradicting_evidence_ids": [],
                "affected_resource_ids": [], "causal_sequence": [], "confidence_components": {},
                "falsification_check": {"objective": "Find an independent source that confirms the causal mechanism."},
                "next_evidence_requests": [],
                "source": "derived_observation",
            }]
    mechanisms = [
        ("service_termination", f"The service process or container for {context.alert.service} terminated or failed to respond.", "Query process state, exit codes, health checks, and termination logs."),
        ("recent_change", f"A recent code or configuration change affected {context.alert.service}.", "Query deployment and code history around the alert onset."),
        ("dependency", f"An unhealthy upstream or downstream dependency is degrading {context.alert.service}.", "Query topology and dependency health for temporal correlation."),
        ("resource_or_data", f"Resource saturation or a data-path constraint is affecting {context.alert.service}.", "Query resource telemetry and data-store health over the incident window."),
        ("traffic", f"A traffic or workload shift exceeded the operating envelope of {context.alert.service}.", "Compare request volume, latency, errors, and capacity before and after onset."),
    ]
    existing_claims = {str(item.get("claim") or "").strip().lower() for item in hypotheses}
    for mechanism, claim, objective in mechanisms:
        if len(hypotheses) >= 6:
            break
        if claim.lower() in existing_claims:
            continue
        from resolution_agent.investigation import hypothesis_digest
        hypotheses.append({
            "hypothesis_id": hypothesis_digest(f"{context.incident_id}:{mechanism}")[:24],
            "claim": claim,
            "status": "candidate",
            "confidence": 0.0,
            "supporting_evidence_ids": [],
            "contradicting_evidence_ids": [],
            "affected_resource_ids": [], "causal_sequence": [], "confidence_components": {},
            "falsification_check": {"objective": objective}, "next_evidence_requests": [],
            "source": "mechanism_candidate",
        })
        existing_claims.add(claim.lower())
    hypotheses = hypotheses[:6]
    coverage = self._coverage(evidence)
    required_sources = self._required_sources(context, hypotheses)
    change_events = self._change_events(context, evidence)
    from common.change_intelligence import rank_correlated_changes, ChangeCorrelationContext
    from resolution_agent.confidence import score_confidence, ConfidenceInputs

    for hypothesis in hypotheses:
        claim_tokens = self._tokens(hypothesis.get("claim"))
        support = []
        sources = set()
        contradiction = []
        is_structured_claim = any(token in hypothesis.get("claim", "").lower() for token in ("terminated", "unreachable", "process or container", "failed to respond", "dependency", "upstream", "downstream", "resource saturation", "data-path"))
        for row in evidence:
            evidence_id = str(row.get("evidence_id") or "")
            text = " ".join(str(row.get(key) or "") for key in ("snippet", "summary", "content", "title"))
            overlap = claim_tokens.intersection(self._tokens(text))
            structured_support = self._structured_mechanism_support(hypothesis, row)
            lexical_support = (
                hypothesis.get("source") != "mechanism_candidate"
                and (len(overlap) >= 2 or (claim_tokens and len(overlap) / len(claim_tokens) >= 0.35))
            )
            current_operational = self._operational_for_support(row)
            if (structured_support or lexical_support) and current_operational:
                if evidence_id:
                    support.append(evidence_id)
                sources.add(self._source(row))
            structured_contradiction = self._structured_mechanism_contradiction(hypothesis, row)
            generic_health_contradiction = (
                hypothesis.get("source") != "derived_observation"
                and not is_structured_claim
                and bool(re.search(r"\b(healthy|normal|no errors|recovered)\b", text.lower()))
                and bool(overlap)
            )
            if evidence_id and current_operational and (
                structured_contradiction
                or generic_health_contradiction
            ):
                contradiction.append(evidence_id)
        supporting_rows = [row for row in evidence if str(row.get("evidence_id") or "") in set(support)]
        fresh_support = [
            row for row in supporting_rows
            if (int(row.get("freshness_seconds") or 0) <= 900 or self._incident_window_aligned(row))
            and self._current_operational(row)
        ]
        temporal_alignment = len(fresh_support) / max(1, len(supporting_rows))
        topology_support = 1.0 if any(row.get("source_type") in {"topology", "dependency"} for row in supporting_rows) else 0.0
        consistency = len(support) / max(1, len(support) + len(contradiction))
        causal_strength = temporal_alignment * 0.5 + topology_support * 0.5
        completeness = sum(1 for source in required_sources if coverage.get(source, 0)) / max(1, len(required_sources))
        scored = score_confidence(ConfidenceInputs(
            evidence_quality=0.85,
            evidence_consistency=consistency,
            causal_strength=causal_strength,
            independent_source_corroboration=min(len(sources) / 3, 1.0),
            temporal_alignment=temporal_alignment,
            topology_alignment=topology_support,
            historical_similarity=0.0,
            successful_test_ratio=0.0,
            contradiction_penalty=min(len(set(contradiction)) * 0.1, 0.35),
            freshness_penalty=0.0,
            missing_data_penalty=(1.0 - completeness) * 0.2,
            sources_unavailable=len(sources) < 2,
            stale_evidence=False,
            model_fallback=False,
            degraded_context=False,
            unresolved_contradictions=bool(contradiction),
            ambiguous_target=False,
            available_components=frozenset({"evidence_quality", "evidence_consistency", "causal_strength", "independent_source_corroboration"}),
        ))
        hypothesis["supporting_evidence_ids"] = [e for e in dict.fromkeys(support) if e not in set(contradiction)]
        hypothesis["contradicting_evidence_ids"] = list(dict.fromkeys(contradiction))
        hypothesis["independent_sources"] = sorted(sources)
        hypothesis["independent_source_count"] = len(sources)
        hypothesis["confidence"] = scored.score
        causally_eligible = hypothesis.get("source") != "derived_observation"
        hypothesis["status"] = (
            "confirmed" if causally_eligible
            and hypothesis["confidence"] >= self.conclusive_threshold
            and len(sources) >= self.minimum_independent_sources
            else "candidate"
        )
    return sorted(hypotheses, key=self._hypothesis_rank, reverse=True)

inv._revise_hypotheses = types.MethodType(custom_revise_hypotheses, inv)
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
print(f"Confirmed without declared gaps? {inv._confirmed_without_declared_gaps(revised, evidence, ctx)}")

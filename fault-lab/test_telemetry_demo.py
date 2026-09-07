from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("fault_lab.py")
SPEC = importlib.util.spec_from_file_location("fault_lab", MODULE_PATH)
assert SPEC and SPEC.loader
fault_lab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fault_lab)


def make_lab() -> fault_lab.FaultLab:
    return fault_lab.FaultLab(
        Path(__file__).parent / "data" / "kaiops_jira_1000_tickets.csv",
        tick_seconds=60,
    )


def stop_lab(lab: fault_lab.FaultLab) -> None:
    lab.stop_event.set()
    lab.worker.join(timeout=1)


def test_telemetry_fault_keeps_workload_available() -> None:
    lab = make_lab()
    try:
        ok, _ = lab.start_fault("kaiops-scenario-43", duration=30)
        assert ok

        status, body, _ = lab.exercise("datadog-agent")

        assert status == 200
        assert body["status"] == "ok"
        assert body["warning"] == "telemetry degraded"
    finally:
        stop_lab(lab)


def test_fault_event_contains_agent_evidence_and_resolution_context() -> None:
    lab = make_lab()
    try:
        ok, _ = lab.start_fault("kaiops-scenario-42", duration=30)
        assert ok

        event = lab.events[-1]

        assert event["scenario_id"] == "kaiops-scenario-42"
        assert event["root_cause"]
        assert event["resolution_steps"]
        assert event["validation"]
        assert event["runbook_id"]
        assert event["trace_id"]
    finally:
        stop_lab(lab)


def test_telemetry_demo_scenarios_are_bounded_nonfatal_profiles() -> None:
    lab = make_lab()
    try:
        assert fault_lab.TELEMETRY_DEMO_SCENARIOS == (
            "kaiops-scenario-42",
            "kaiops-scenario-43",
            "kaiops-scenario-22",
        )
        behaviors = {
            lab.scenarios[scenario_id]["profile"]["behavior"]
            for scenario_id in fault_lab.TELEMETRY_DEMO_SCENARIOS
        }
        assert behaviors == {"telemetry", "backlog"}
    finally:
        stop_lab(lab)


def test_emit_trace_matches_the_alerting_services_own_http_outcome() -> None:
    """Regression for the "traces.search always comes back empty" finding:
    before this, no fault ever produced a real Jaeger trace at all - only
    health-check/metrics-scrape spans existed platform-wide. A latency fault
    must now produce a real span, named for the alerting service, whose
    status/duration matches what `exercise()` already returns for the same
    fault (so a live request and the fault's own trace tell the same story)."""
    lab = make_lab()
    original_send = fault_lab._send_otlp_traces
    try:
        scenario = lab.scenarios["kaiops-scenario-01"]  # checkout-api, latency
        assert scenario["service"] == "checkout-api"
        ok, fault = lab.start_fault("kaiops-scenario-01", duration=30)
        assert ok
        sent = []
        fault_lab._send_otlp_traces = lambda resource_spans: sent.append(resource_spans)
        trace_id = "a" * 32
        span_id = "b" * 16
        lab._emit_trace(scenario, fault, trace_id, span_id)

        assert len(sent) == 1
        resource_spans = sent[0]
        assert len(resource_spans) == 1  # latency is a self-contained fault, no dependency edge
        resource = resource_spans[0]["resource"]
        service_names = {
            attr["value"]["stringValue"] for attr in resource["attributes"] if attr["key"] == "service.name"
        }
        assert service_names == {"checkout-api"}
        span = resource_spans[0]["scopeSpans"][0]["spans"][0]
        assert span["traceId"] == trace_id
        assert span["spanId"] == span_id
        assert "parentSpanId" not in span
        attributes = {attr["key"]: attr["value"] for attr in span["attributes"]}
        assert attributes["http.status_code"] == {"intValue": "504"}
        assert attributes["error"] == {"boolValue": True}
        assert span["status"]["code"] == 2
        duration_ns = int(span["endTimeUnixNano"]) - int(span["startTimeUnixNano"])
        assert duration_ns >= 3_000_000_000  # crosses discovery-mcp's 3s "high_latency" signal threshold
    finally:
        fault_lab._send_otlp_traces = original_send
        stop_lab(lab)


def test_emit_trace_adds_a_genuine_cross_service_dependency_edge() -> None:
    """A "dependency" fault (e.g. connection pool saturation) represents the
    alerting service calling out to a real downstream - the trace must carry
    TWO resource spans (different service.name each) with a real parent/child
    link, which is exactly what discovery-mcp's `_trace_evidence_summary`
    requires to compute a non-empty `dependency_edges` list."""
    lab = make_lab()
    original_send = fault_lab._send_otlp_traces
    try:
        scenario = lab.scenarios["kaiops-scenario-07"]  # payments-api, connection pool saturation
        assert scenario["profile"]["behavior"] == "dependency"
        assert scenario["service"] == "payments-api"
        ok, fault = lab.start_fault("kaiops-scenario-07", duration=30)
        assert ok
        sent = []
        fault_lab._send_otlp_traces = lambda resource_spans: sent.append(resource_spans)
        trace_id = "c" * 32
        parent_span_id = "d" * 16
        lab._emit_trace(scenario, fault, trace_id, parent_span_id)

        resource_spans = sent[0]
        assert len(resource_spans) == 2
        service_names = [
            next(attr["value"]["stringValue"] for attr in rs["resource"]["attributes"] if attr["key"] == "service.name")
            for rs in resource_spans
        ]
        assert service_names == ["payments-api", "database"]
        child_span = resource_spans[1]["scopeSpans"][0]["spans"][0]
        assert child_span["traceId"] == trace_id
        assert child_span["parentSpanId"] == parent_span_id
    finally:
        fault_lab._send_otlp_traces = original_send
        stop_lab(lab)


def test_dependency_downstream_is_empty_when_the_alerting_service_is_already_the_datastore() -> None:
    """orders-db's own replication lag has no further downstream to name -
    must stay a single, self-contained span rather than fabricating a fake
    edge, matching `_discovered_dependency_service`'s "empty when none
    exists" contract in investigation.py."""
    lab = make_lab()
    try:
        scenario = lab.scenarios["kaiops-scenario-09"]  # orders-db, replication lag
        assert scenario["service"] == "orders-db"
        assert scenario["profile"]["behavior"] == "dependency"
        assert lab._dependency_downstream(scenario) == ""
    finally:
        stop_lab(lab)


def test_emit_accepts_explicit_trace_and_span_ids_instead_of_always_fabricating_new_ones() -> None:
    """Before this fix, `emit()` always generated its own random trace_id/
    span_id, unrelated to any real trace - a log line could never be
    cross-referenced to real Jaeger trace evidence for the same event."""
    lab = make_lab()
    try:
        scenario = lab.scenarios["kaiops-scenario-01"]
        ok, fault = lab.start_fault("kaiops-scenario-01", duration=30)
        assert ok
        lab.emit(scenario, "ERROR", "application_fault", "test", fault, trace_id="f" * 32, span_id="e" * 16)
        event = lab.events[-1]
        assert event["trace_id"] == "f" * 32
        assert event["span_id"] == "e" * 16
    finally:
        stop_lab(lab)

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from common.checklist_triage import (
    ChecklistStatus,
    ChecklistTriageEngine,
    ChecklistTriageResult,
)
from common.domain_specialists import (
    DomainSpecialistCouncil,
    SpecialistDomain,
)
from common.hypothesis_trees import (
    BranchStatus,
    HypothesisTreeEngine,
)
from common.metric_analyzer import (
    MetricAnalyzer,
    MetricShape,
)
from common.models import Alert, AlertSeverity
from common.proactive_reliability import (
    BlastRadiusRisk,
    ProactiveReliabilityEngine,
)
from common.published_investigation import (
    PublishedInvestigationBuilder,
    RemediationTier,
    TimelinePhase,
)


@pytest.fixture
def sample_alert() -> Alert:
    return Alert(
        tenant_id="tenant-prod-alpha",
        source="prometheus",
        name="PaymentsDatabaseConnectionExhaustion",
        service="payments-db",
        severity=AlertSeverity.CRITICAL,
        description="Database connection pool utilization exceeded 95% threshold",
        labels={"environment": "production", "cluster": "us-east-1"},
    )


# -----------------------------------------------------------------------------
# 1. Mode 2 Fast Checklist Triage Tests
# -----------------------------------------------------------------------------

def test_checklist_triage_detects_normal_transient_recovery(sample_alert: Alert) -> None:
    engine = ChecklistTriageEngine()
    incident_id = uuid4()

    # Telemetry indicates metric has already dropped below threshold and probes are healthy
    result = engine.evaluate(
        alert=sample_alert,
        incident_id=incident_id,
        telemetry_samples={
            "current_value": 42.0,
            "threshold_value": 85.0,
            "comparator": "gt",
            "disk_usage_percent": 65.0,
            "cert_days_remaining": 120.0,
        },
        runtime_status={
            "probes_healthy": True,
            "restart_count": 0,
        },
    )

    assert result.status == ChecklistStatus.NORMAL
    assert result.should_escalate_to_full_investigation is False
    assert result.suppression_recommended is True
    assert "transient" in result.finding_summary.lower() or "passed" in result.finding_summary.lower()


def test_checklist_triage_pinpoints_specific_finding_pod_crash(sample_alert: Alert) -> None:
    engine = ChecklistTriageEngine()
    incident_id = uuid4()

    # Runtime status shows pod CrashLoopBackOff with 8 restarts
    result = engine.evaluate(
        alert=sample_alert,
        incident_id=incident_id,
        runtime_status={
            "probes_healthy": False,
            "restart_count": 8,
        },
    )

    assert result.status == ChecklistStatus.SPECIFIC_FINDING
    assert result.should_escalate_to_full_investigation is False
    assert result.suppression_recommended is False
    assert "CrashLoopBackOff" in result.finding_summary


def test_checklist_triage_escalates_inconclusive_conditions(sample_alert: Alert) -> None:
    engine = ChecklistTriageEngine()
    incident_id = uuid4()

    # Telemetry remains breached, probes failing, but no single invariant identified
    result = engine.evaluate(
        alert=sample_alert,
        incident_id=incident_id,
        telemetry_samples={
            "current_value": 98.0,
            "threshold_value": 85.0,
            "comparator": "gt",
        },
        runtime_status={
            "probes_healthy": False,
            "restart_count": 1,
        },
    )

    assert result.status == ChecklistStatus.INCONCLUSIVE
    assert result.should_escalate_to_full_investigation is True
    assert result.suppression_recommended is False


# -----------------------------------------------------------------------------
# 2. Parallel Archetype Hypothesis Tree Evaluation Tests
# -----------------------------------------------------------------------------

def test_hypothesis_tree_evaluates_payments_connection_exhaustion() -> None:
    """PDF Case Study 1: Payments datastore connection pool alert.

    Tests parallel evaluation across 6 candidate causes, eliminating slow queries
    and lock contention based on negative evidence, and confirming caller retry storm.
    """
    engine = HypothesisTreeEngine(tenant_id="tenant-prod-alpha")
    incident_id = uuid4()

    evidence_items = [
        {
            "evidence_id": "ev-slow-queries",
            "title": "Slow Query Metrics",
            "summary": "Database slow query count: 0, p99 query duration normal across all tables.",
        },
        {
            "evidence_id": "ev-locks",
            "title": "Lock Contention Stats",
            "summary": "InnoDB lock waits: 0, deadlocks: 0 recorded in interval.",
        },
        {
            "evidence_id": "ev-upstream-deploy",
            "title": "Caller Service Release Log",
            "summary": "Checkout-service deployed v2.5; backoff removed in client retry loop causing amplification.",
        },
    ]

    evaluation = engine.evaluate(
        incident_id=incident_id,
        archetype="connection-pool-saturation",
        evidence_items=evidence_items,
    )

    assert len(evaluation.branches) == 6
    assert evaluation.winning_branch_id == "hyp-caller-retry-storm"

    winning_branch = next(b for b in evaluation.branches if b.branch_id == evaluation.winning_branch_id)
    assert winning_branch.status == BranchStatus.CONFIRMED
    assert winning_branch.confidence >= 0.90
    assert "ev-upstream-deploy" in winning_branch.supporting_evidence_ids

    # Verify eliminated non-causes
    assert "hyp-db-slow-queries" in evaluation.eliminated_branch_ids
    assert "hyp-db-lock-contention" in evaluation.eliminated_branch_ids

    slow_query_branch = next(b for b in evaluation.branches if b.branch_id == "hyp-db-slow-queries")
    assert slow_query_branch.status == BranchStatus.ELIMINATED
    assert "ev-slow-queries" in slow_query_branch.contradicting_evidence_ids


def test_hypothesis_tree_evaluates_storage_throttling_iops_vs_throughput() -> None:
    """PDF Case Study 2: Storage throttling alarm.

    Alarm named for IOPS, but evaluation proves write throughput exceeded ceiling
    while IOPS remained safe.
    """
    engine = HypothesisTreeEngine(tenant_id="tenant-prod-alpha")
    incident_id = uuid4()

    evidence_items = [
        {
            "evidence_id": "ev-iops-stats",
            "title": "Storage Volume IOPS",
            "summary": "Measured IOPS normal at 2,100 / 10,000 quota; iops safe.",
        },
        {
            "evidence_id": "ev-throughput-stats",
            "title": "Storage Volume Bandwidth",
            "summary": "Throughput ceiling breached: write throughput surged to 862.8 MB/s crossing 750 MB/s bandwidth quota.",
        },
    ]

    evaluation = engine.evaluate(
        incident_id=incident_id,
        archetype="storage-throttling",
        evidence_items=evidence_items,
    )

    assert evaluation.winning_branch_id == "hyp-storage-throughput-ceiling"
    assert "hyp-storage-iops-ceiling" in evaluation.eliminated_branch_ids


# -----------------------------------------------------------------------------
# 3. Statistical Metric Shape & Quota Ceiling Analyzer Tests
# -----------------------------------------------------------------------------

def test_metric_analyzer_detects_step_spike_and_ceiling_breach() -> None:
    timestamps = [f"2026-09-24T12:{i:02d}:00Z" for i in range(10)]
    # Baseline ~120 MB/s, then sudden spike to 860 MB/s at index 6
    values = [118.0, 122.0, 119.5, 121.0, 120.2, 123.0, 862.8, 855.0, 860.1, 858.4]

    report = MetricAnalyzer.analyze_series(
        values=values,
        timestamps=timestamps,
        metric_name="EBS_Write_Throughput_MBps",
        ceiling=750.0,
    )

    assert report.shape == MetricShape.STEP_SPIKE
    assert report.ceiling_analysis is not None
    assert report.ceiling_analysis.is_breached is True
    assert report.ceiling_analysis.peak_percent_of_ceiling >= 115.0
    assert len(report.inflection_points) >= 1
    assert report.inflection_points[0].percent_change > 500.0
    assert "CRITICAL: Breached provisioned ceiling" in report.semantic_summary


def test_metric_analyzer_correlates_storage_throttling_iops_vs_throughput() -> None:
    iops = [2050.0, 2100.0, 2080.0, 2150.0, 2120.0]
    throughput = [120.0, 125.0, 862.8, 850.0, 845.0]

    verdict = MetricAnalyzer.correlate_storage_vs_iops(
        iops_values=iops,
        iops_ceiling=10000.0,
        throughput_mb_values=throughput,
        throughput_ceiling_mb=750.0,
    )

    assert "Write throughput breached the 750.0 MB/s ceiling" in verdict
    assert "IOPS remained comfortably low" in verdict
    assert "large block size data transfer" in verdict


# -----------------------------------------------------------------------------
# 4. Domain Specialists & Incident Commander Synthesis Tests
# -----------------------------------------------------------------------------

def test_domain_specialists_synthesize_commander_verdict() -> None:
    council = DomainSpecialistCouncil(tenant_id="tenant-prod-alpha")
    incident_id = uuid4()

    evidence = [
        {
            "evidence_id": "ev-conn-pool",
            "title": "MySQL Connection Stats",
            "content": "MySQL error 1040: too many connections. Connection pool exhausted.",
        },
        {
            "evidence_id": "ev-deploy-git",
            "title": "GitHub Commit Log",
            "content": "Deployment rollout v2.5 by checkout-team: removed backoff in client retry loop.",
        },
    ]

    synthesis = council.evaluate_council(
        incident_id=incident_id,
        service="payments-service",
        evidence_items=evidence,
    )

    assert synthesis.primary_domain in {SpecialistDomain.CODE_RELEASE, SpecialistDomain.DATABASE}
    assert synthesis.consensus_confidence >= 0.90
    assert "Incident Commander Synthesis" in synthesis.synthesized_narrative
    assert len(synthesis.specialist_findings) >= 5
    assert any(f.domain == SpecialistDomain.CODE_RELEASE and f.verdict == "CULPRIT_IDENTIFIED" for f in synthesis.specialist_findings)


# -----------------------------------------------------------------------------
# 5. Published Investigation 3-Phase Timeline & 3-Tier Graded Next Steps
# -----------------------------------------------------------------------------

def test_published_investigation_generates_markdown_artifact() -> None:
    now = datetime.now(UTC)
    incident_id = uuid4()

    investigation = PublishedInvestigationBuilder.build(
        tenant_id="tenant-prod-alpha",
        incident_id=incident_id,
        service="payments-service",
        incident_title="Payments Latency Spike from Unbacked Caller Retries",
        root_cause="Caller deployment v2.5 removed retry backoff, generating a connection pool saturation storm.",
        reported_at=now - timedelta(minutes=15),
        reported_text="504 Gateway Timeout alerts on /api/v1/checkout",
        monitored_at=now - timedelta(minutes=12),
        monitoring_text="MySQL ConnectionPoolExhausted alarm fired on payments-db",
        actual_at=now - timedelta(minutes=20),
        actual_ground_truth="Checkout service v2.5 commit 4a8b9f dropped backoff jitter, amplifying retries 10x",
        immediate_fix="Rollback checkout-service to v2.4 to restore exponential backoff.",
        release_gate="Add automated CI gate rejecting HTTP client PRs without backoff configuration.",
        estate_scan="Scan all 42 microservices to confirm exponential backoff is configured for payments-db callers.",
    )

    assert len(investigation.three_phase_timeline) == 3
    assert {e.phase for e in investigation.three_phase_timeline} == {
        TimelinePhase.REPORTED_SYMPTOM,
        TimelinePhase.MONITORING_OBSERVED,
        TimelinePhase.ACTUAL_EVENTS,
    }

    assert len(investigation.graded_next_steps) == 3
    assert {s.tier for s in investigation.graded_next_steps} == {
        RemediationTier.TIER_1_IMMEDIATE_FIX,
        RemediationTier.TIER_2_RELEASE_GATE,
        RemediationTier.TIER_3_ESTATE_BLAST_RADIUS,
    }

    markdown = investigation.to_markdown_artifact()
    assert "# Published Investigation: Payments Latency Spike" in markdown
    assert "1. What Was Reported" in markdown
    assert "2. What Monitoring Showed" in markdown
    assert "3. What Actually Happened" in markdown
    assert "Tier 1: Immediate Remediation" in markdown
    assert "Tier 2: Architectural Release Gate" in markdown
    assert "Tier 3: Estate-Wide Blast Radius Scan" in markdown


# -----------------------------------------------------------------------------
# 6. Proactive Reliability: Blast Radius & Capacity Headroom Forecasting
# -----------------------------------------------------------------------------

def test_proactive_reliability_analyzes_pr_blast_radius() -> None:
    engine = ProactiveReliabilityEngine(
        tenant_id="tenant-prod-alpha",
        service_topology={"checkout": ["payments", "inventory", "customer-db"]},
    )

    report = engine.analyze_change_impact(
        target_service="checkout",
        changed_files=["src/client/http_client.py", "config/retry_policy.json"],
        diff_text="""
- retry_policy = ExponentialBackoff(base_ms=100, max_attempts=5, jitter=True)
+ retry_policy = ImmediateRetry(max_attempts=10)
        """,
        pr_number=482,
    )

    assert report.target_service == "checkout"
    assert "payments" in report.impacted_downstream_services
    assert report.blast_radius_score >= 0.70
    assert report.risk_tier in {BlastRadiusRisk.HIGH, BlastRadiusRisk.CRITICAL}
    assert any("retry storm" in w.lower() for w in report.architectural_warnings)
    assert any("exponential backoff" in g.lower() for g in report.recommended_gates)


def test_proactive_reliability_forecasts_capacity_exhaustion() -> None:
    engine = ProactiveReliabilityEngine(tenant_id="tenant-prod-alpha")

    # Storage volume growing steadily: 500GB -> 900GB over 8 days with a 1000GB ceiling
    history = [500.0, 550.0, 620.0, 710.0, 780.0, 830.0, 870.0, 910.0]

    report = engine.forecast_capacity_headroom(
        service="payments-db",
        resource_type="Storage_Volume_GB",
        history_values=history,
        provisioned_ceiling=1000.0,
        time_interval_days=8.0,
    )

    assert report.current_utilization == 910.0
    assert report.saturation_percent == 91.0
    assert report.burn_rate_per_day > 0.0
    assert report.estimated_days_to_exhaustion is not None
    # 90GB remaining at ~51GB/day -> under 3 days!
    assert report.estimated_days_to_exhaustion <= 3.0
    assert report.exhaustion_risk == BlastRadiusRisk.CRITICAL
    assert "Immediate action required" in report.recommended_remediation

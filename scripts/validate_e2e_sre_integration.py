"""End-to-End Validation script for newly integrated SRE capabilities in KAIMS.

Verifies:
1. Fast checklist triage (ChecklistTriageEngine)
2. Metric analysis (MetricAnalyzer)
3. Hypothesis trees (HypothesisTreeEngine)
4. Domain specialist council (DomainSpecialistCouncil)
5. Published investigation post-mortem (PublishedInvestigationBuilder)
6. Proactive reliability analysis (ProactiveReliabilityEngine)
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import UUID

# Add backend common to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "src" / "common"))

from common.models import Alert, AlertSeverity
from common.checklist_triage import (
    ChecklistStatus,
    ChecklistTriageEngine,
    ChecklistTriageResult,
)
from common.hypothesis_trees import (
    BranchStatus,
    HypothesisTreeEngine,
)
from common.metric_analyzer import (
    MetricAnalyzer,
    MetricShape,
)
from common.domain_specialists import (
    DomainSpecialistCouncil,
    SpecialistDomain,
)
from common.published_investigation import (
    PublishedInvestigationBuilder,
    RemediationTier,
    TimelinePhase,
)
from common.proactive_reliability import (
    BlastRadiusRisk,
    ProactiveReliabilityEngine,
)


def validate_sre_capabilities():
    print("=" * 70)
    print("VALIDATING KAIMS SRE CAPABILITIES INTEGRATION")
    print("=" * 70)
    results = {}

    incident_id = UUID("24215139-44ea-49f1-9a58-c53d8b006ed7")

    # 1. Fast Checklist Triage
    print("\n[1/6] Testing Fast Checklist Triage Engine on Live Incident Payload...")
    triage_engine = ChecklistTriageEngine()
    alert = Alert(
        tenant_id="tenant-prod-alpha",
        source="prometheus",
        name="TargetDown",
        service="robot-shop-cart",
        severity=AlertSeverity.CRITICAL,
        description="Service robot-shop-cart endpoint unreachable",
    )
    triage_res = triage_engine.evaluate(
        alert=alert,
        incident_id=incident_id,
        runtime_status={"probes_healthy": False, "restart_count": 5},
    )
    print(f" -> Triage Outcome: {triage_res.status}")
    print(f" -> Summary: {triage_res.finding_summary}")
    print(f" -> Suppression recommended: {triage_res.suppression_recommended}")
    assert triage_res.status == ChecklistStatus.SPECIFIC_FINDING
    assert "CrashLoopBackOff" in triage_res.finding_summary
    results["1. Fast Checklist Triage"] = "PASSED"

    # 2. Metric Analysis & Ceiling Breaches
    print("\n[2/6] Testing Metric Analysis Engine (Time-series shapes & Ceiling Breach)...")
    timestamps = [f"2026-09-24T12:{i:02d}:00Z" for i in range(10)]
    values = [118.0, 122.0, 119.5, 121.0, 120.2, 123.0, 862.8, 855.0, 860.1, 858.4]
    report = MetricAnalyzer.analyze_series(
        values=values,
        timestamps=timestamps,
        metric_name="robot-shop-cart-write-mbps",
        ceiling=750.0,
    )
    print(f" -> Detected Shape: {report.shape}")
    print(f" -> Ceiling Breached: {report.ceiling_analysis.is_breached}")
    print(f" -> Peak Utilization: {report.ceiling_analysis.peak_percent_of_ceiling:.1f}%")
    assert report.shape == MetricShape.STEP_SPIKE
    assert report.ceiling_analysis.is_breached is True

    storage_verdict = MetricAnalyzer.correlate_storage_vs_iops(
        iops_values=[2050.0, 2100.0, 2080.0, 2150.0, 2120.0],
        iops_ceiling=10000.0,
        throughput_mb_values=[120.0, 125.0, 862.8, 850.0, 845.0],
        throughput_ceiling_mb=750.0,
    )
    print(f" -> Correlation Analysis: {storage_verdict[:100]}...")
    assert "Write throughput breached the 750.0 MB/s ceiling" in storage_verdict
    results["2. Metric Analysis"] = "PASSED"

    # 3. Hypothesis Trees
    print("\n[3/6] Testing Archetype Hypothesis Trees Engine...")
    tree_engine = HypothesisTreeEngine(tenant_id="tenant-prod-alpha")
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
    evaluation = tree_engine.evaluate(
        incident_id=incident_id,
        archetype="connection-pool-saturation",
        evidence_items=evidence_items,
    )
    print(f" -> Winning Hypothesis Branch: {evaluation.winning_branch_id}")
    print(f" -> Eliminated Non-Causes: {evaluation.eliminated_branch_ids}")
    assert evaluation.winning_branch_id == "hyp-caller-retry-storm"
    assert "hyp-db-slow-queries" in evaluation.eliminated_branch_ids
    results["3. Hypothesis Trees"] = "PASSED"

    # 4. Domain Specialist Council
    print("\n[4/6] Testing Domain Specialist Council & Synthesis...")
    council = DomainSpecialistCouncil(tenant_id="tenant-prod-alpha")
    synthesis = council.evaluate_council(
        incident_id=incident_id,
        service="robot-shop-cart",
        evidence_items=[
            {
                "evidence_id": "ev-conn-pool",
                "title": "Container Status",
                "content": "Container terminated with signal 137 (OOMKilled); cgroup memory ceiling exhausted.",
            },
            {
                "evidence_id": "ev-deploy-git",
                "title": "Git Commit Log",
                "content": "Release v1.8 increased buffer queue size to 50,000 without heap ceiling adjustment.",
            },
        ],
    )
    print(f" -> Primary Domain: {synthesis.primary_domain}")
    print(f" -> Consensus Confidence: {synthesis.consensus_confidence}")
    print(f" -> Contributing Specialists: {len(synthesis.specialist_findings)}")
    assert synthesis.primary_domain in {SpecialistDomain.CODE_RELEASE, SpecialistDomain.INFRASTRUCTURE}
    assert synthesis.consensus_confidence >= 0.85
    results["4. Domain Specialist Council"] = "PASSED"

    # 5. Published Investigation / Post-Mortem
    print("\n[5/6] Testing Published Investigation & 3-Tier Graded Post-Mortem...")
    now = datetime.now(timezone.utc)
    investigation = PublishedInvestigationBuilder.build(
        tenant_id="tenant-prod-alpha",
        incident_id=incident_id,
        service="robot-shop-cart",
        incident_title="Robot-Shop-Cart Out of Memory Crash During Ingestion",
        root_cause="Release v1.8 increased buffer queue size without cgroup memory limit adjustment.",
        reported_at=now - timedelta(minutes=15),
        reported_text="504 Gateway Timeout alerts on /cart/items",
        monitored_at=now - timedelta(minutes=12),
        monitoring_text="TargetDown and OOMKilled alerts fired in Kubernetes namespace",
        actual_at=now - timedelta(minutes=20),
        actual_ground_truth="Worker process exceeded 2048MB container cgroup limit",
        immediate_fix="Rollback deployment to v1.7 and increase container memory limit to 4096MB.",
        release_gate="Add automated CI check for buffer allocations against memory limits.",
        estate_scan="Audit all microservice Helm charts for missing resource request/limit definitions.",
    )
    markdown_doc = investigation.to_markdown_artifact()
    print(" -> Post-Mortem Markdown Size:", len(markdown_doc), "bytes")
    assert "# Published Investigation: Robot-Shop-Cart" in markdown_doc
    assert "1. What Was Reported" in markdown_doc
    assert "2. What Monitoring Showed" in markdown_doc
    assert "3. What Actually Happened" in markdown_doc
    assert "Tier 1: Immediate Remediation" in markdown_doc
    assert "Tier 2: Architectural Release Gate" in markdown_doc
    assert "Tier 3: Estate-Wide Blast Radius Scan" in markdown_doc
    results["5. Published Investigation"] = "PASSED"

    # 6. Proactive Reliability Analysis
    print("\n[6/6] Testing Proactive Reliability Engine (PR Changes & Headroom Forecasting)...")
    proactive = ProactiveReliabilityEngine(
        tenant_id="tenant-prod-alpha",
        service_topology={"robot-shop-cart": ["redis", "shipping", "catalogue"]},
    )
    blast = proactive.analyze_change_impact(
        target_service="robot-shop-cart",
        changed_files=["server.js", "config.json"],
        diff_text="- retry_policy = ExponentialBackoff()\n+ retry_policy = ImmediateRetry(max_attempts=10)",
        pr_number=102,
    )
    print(f" -> Blast Radius Score: {blast.blast_radius_score}")
    print(f" -> Impacted Downstream Services: {blast.impacted_downstream_services}")
    assert "redis" in blast.impacted_downstream_services

    headroom = proactive.forecast_capacity_headroom(
        service="robot-shop-cart",
        resource_type="Memory_MB",
        history_values=[1200.0, 1350.0, 1500.0, 1680.0, 1820.0, 1940.0],
        provisioned_ceiling=2048.0,
        time_interval_days=6.0,
    )
    print(f" -> Current Utilization: {headroom.current_utilization} MB")
    print(f" -> Saturation: {headroom.saturation_percent:.1f}%")
    print(f" -> Days to Exhaustion: {headroom.estimated_days_to_exhaustion:.1f} days")
    print(f" -> Risk Tier: {headroom.exhaustion_risk}")
    assert headroom.saturation_percent > 90.0
    assert headroom.estimated_days_to_exhaustion <= 2.0
    assert headroom.exhaustion_risk == BlastRadiusRisk.CRITICAL
    results["6. Proactive Reliability"] = "PASSED"

    print("\n" + "=" * 70)
    print("ALL 6 SRE CAPABILITIES INTEGRATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)
    for cap, status in results.items():
        print(f"  [+] {cap:<35}: {status}")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = validate_sre_capabilities()
    sys.exit(0 if success else 1)

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from common.payload_reducer import PayloadReducer
from common.signal_validator import (
    FailureLayer,
    SignalValidationStatus,
    SignalValidator,
)
from common.timeline_reconstructor import (
    EventSignificance,
    TimelineEventType,
    TimelineReconstructor,
)


@pytest.fixture
def tenant_id() -> str:
    return "tenant-prod-alpha"


@pytest.fixture
def incident_id() -> str:
    return uuid4()


# =============================================================================
# Benchmark Scenario A: DB Connection Alert where DB is Healthy but Caller Retries -> WRONG_LAYER
# =============================================================================
def test_benchmark_a_db_alert_wrong_layer_caller_retry(tenant_id, incident_id):
    """PDF Case Study 1: Payments datastore connection pool alert.
    DB internal metrics are healthy (query latency 4.2ms, CPU 22%, 0 lock waits, 0.1s lag),
    but caller retry rate is 450 retries/sec due to an upstream deployment.
    """
    res = SignalValidator.validate(
        tenant_id=tenant_id,
        incident_id=incident_id,
        alert_name="MySQLConnectionPoolExhausted",
        service="payments-db",
        telemetry={
            "query_latency_ms": 4.2,
            "db_cpu_pct": 22.0,
            "db_iops": 650.0,
            "innodb_lock_waits": 0,
            "replication_lag_s": 0.1,
            "caller_retry_rate_per_sec": 450.0,
        },
    )

    assert res.status == SignalValidationStatus.WRONG_LAYER
    assert res.target_layer == FailureLayer.DATABASE
    assert res.indicated_layer == FailureLayer.APPLICATION
    assert res.is_target_healthy is True
    assert "caller retry storm" in res.reasoning.lower()
    assert "checkout-service" in res.upstream_candidates
    assert any(c.check_name == "QueryLatencyCheck" and c.is_healthy for c in res.checks)
    assert any(c.check_name == "LockContentionCheck" and c.is_healthy for c in res.checks)


# =============================================================================
# Benchmark Scenario B: Storage IOPS Alert where Bottleneck is Throughput -> MISLEADING
# =============================================================================
def test_benchmark_b_storage_iops_misleading_throughput_ceiling(tenant_id, incident_id):
    """PDF Case Study 2: Storage throttling alarm named for IOPS.
    IOPS is only at 2,100 / 30,000 (7%), but write throughput is 862.8 MB/s crossing 750 MB/s limit.
    """
    res = SignalValidator.validate(
        tenant_id=tenant_id,
        incident_id=incident_id,
        alert_name="EBSVolumeIOPSThrottling",
        service="payments-db-replica",
        telemetry={
            "volume_iops": 2100.0,
            "iops_ceiling": 30000.0,
            "write_mbps": 862.8,
            "throughput_ceiling_mbps": 750.0,
        },
    )

    assert res.status == SignalValidationStatus.MISLEADING
    assert res.target_layer == FailureLayer.STORAGE
    assert res.is_target_healthy is False
    assert "throughput breached the 750.0 mb/s ceiling" in res.reasoning.lower()
    assert any(c.check_name == "IopsSaturationCheck" and c.is_healthy for c in res.checks)
    assert any(c.check_name == "ThroughputCeilingCheck" and not c.is_healthy for c in res.checks)


# =============================================================================
# Benchmark Scenario C: Self-Clearing Scheduled Batch Spike -> TRANSIENT
# =============================================================================
def test_benchmark_c_scheduled_batch_spike_transient(tenant_id, incident_id):
    """PDF Page 13: Database write alarm with no impact (daily batch peak)."""
    res = SignalValidator.validate(
        tenant_id=tenant_id,
        incident_id=incident_id,
        alert_name="DatabaseWriteLatencySpike",
        service="analytics-db",
        telemetry={
            "current_value": 45.0,
            "threshold_value": 80.0,
            "is_scheduled_batch_window": True,
        },
    )

    assert res.status == SignalValidationStatus.TRANSIENT
    assert res.is_target_healthy is True
    assert "batch" in res.reasoning.lower() or "recovered" in res.reasoning.lower()


# =============================================================================
# Benchmark Scenario D: Large Kubernetes Environment Reduction
# =============================================================================
def test_benchmark_d_large_k8s_payload_reduction():
    """Context engineering: 500 pods in cluster -> summarizes 497 healthy, isolates 3 abnormal."""
    raw_pods = []
    # 497 healthy pods
    for i in range(497):
        raw_pods.append({
            "name": f"worker-pod-{i}",
            "namespace": "production",
            "phase": "Running",
            "status": {"phase": "Running", "containerStatuses": [{"ready": True, "restartCount": 0}]},
        })

    # 3 abnormal pods
    raw_pods.append({
        "name": "cart-api-7b8f9-x1",
        "namespace": "production",
        "phase": "Running",
        "status": {
            "phase": "Running",
            "containerStatuses": [{
                "ready": False,
                "restartCount": 12,
                "state": {"waiting": {"reason": "CrashLoopBackOff", "message": "Back-off 5m restarting failed container"}},
            }],
        },
    })
    raw_pods.append({
        "name": "checkout-svc-5c6d-z2",
        "namespace": "production",
        "phase": "Failed",
        "status": {
            "phase": "Failed",
            "containerStatuses": [{
                "ready": False,
                "restartCount": 1,
                "state": {"terminated": {"exitCode": 137, "reason": "OOMKilled", "message": "Container exceeded 2048MB cgroup limit"}},
            }],
        },
    })
    raw_pods.append({
        "name": "ingress-gw-9f8e-a3",
        "namespace": "production",
        "phase": "Pending",
        "status": {"phase": "Pending", "reason": "NodeAdmissionError"},
    })

    reduced = PayloadReducer.reduce_k8s_pods(raw_pods, target_namespace="production")

    assert reduced.total_pods_inspected == 500
    assert reduced.healthy_pods_count == 497
    assert reduced.abnormal_pods_count == 3
    assert len(reduced.abnormal_pods) == 3

    pod_names = {p.name for p in reduced.abnormal_pods}
    assert "cart-api-7b8f9-x1" in pod_names
    assert "checkout-svc-5c6d-z2" in pod_names
    assert "ingress-gw-9f8e-a3" in pod_names

    oom_pod = next(p for p in reduced.abnormal_pods if p.name == "checkout-svc-5c6d-z2")
    assert oom_pod.exit_code == 137
    assert oom_pod.reason == "OOMKilled"


# =============================================================================
# Benchmark Scenario E: Large Log Stream Signature Clustering & Burst Rate
# =============================================================================
def test_benchmark_e_large_log_stream_reduction():
    """Context engineering: 1,000 log lines with varying UUIDs/IPs clustered into signatures."""
    raw_logs = []
    # 700 connection pool timeout logs with varying UUIDs and IPs
    for i in range(700):
        raw_logs.append({
            "message": f"2026-09-24T14:{i % 60:02d}:00Z [ERROR] Connection pool timeout for user {uuid4()} from 10.0.{i % 255}.{i % 255}:5432 - max pool 50 reached",
            "level": "ERROR",
            "timestamp": f"2026-09-24T14:{i % 60:02d}:00Z",
            "uri": "opensearch://payments/logs",
        })

    # 300 slow query warnings
    for i in range(300):
        raw_logs.append({
            "message": f"2026-09-24T14:{i % 60:02d}:00Z [WARN] Slow query detected on orders table taking 4200ms query_id={i * 1000}",
            "level": "WARN",
            "timestamp": f"2026-09-24T14:{i % 60:02d}:00Z",
            "uri": "opensearch://orders/logs",
        })

    reduction = PayloadReducer.reduce_logs(raw_logs, max_clusters=5)

    assert reduction.total_lines_inspected == 1000
    assert reduction.unique_clusters_count <= 4
    assert len(reduction.top_clusters) >= 2

    top_sig = reduction.top_clusters[0]
    assert top_sig.count == 700
    assert "<UUID>" in top_sig.signature_pattern
    assert "<IP_PORT>" in top_sig.signature_pattern
    assert top_sig.burst_rate_per_min > 0.0
    assert top_sig.provenance_uri == "opensearch://payments/logs"


# =============================================================================
# Benchmark Scenario F: Timeline Cascade Sequence Reconstruction
# =============================================================================
def test_benchmark_f_timeline_cascade_reconstruction(tenant_id, incident_id):
    """PDF Deep Dive 3:
    13:50: Deployment removes backoff
    13:58: Retry rate surges by 650%
    14:02: Connection pool hits 100% saturation
    14:05: Alert fires on connection pool
    """
    t_deploy = datetime(2026, 9, 24, 13, 50, 0, tzinfo=UTC)
    t_retry = datetime(2026, 9, 24, 13, 58, 0, tzinfo=UTC)
    t_sat = datetime(2026, 9, 24, 14, 2, 0, tzinfo=UTC)
    t_alert = datetime(2026, 9, 24, 14, 5, 0, tzinfo=UTC)

    timeline = TimelineReconstructor.reconstruct(
        tenant_id=tenant_id,
        incident_id=incident_id,
        deployments=[{
            "timestamp": t_deploy,
            "service": "checkout-service",
            "title": "Release v2.5 Deployment",
            "description": "Removed retry backoff in client loop",
            "source": "jenkins://checkout-pipeline",
        }],
        metric_inflections=[
            {
                "timestamp": t_retry,
                "service": "checkout-service",
                "metric_name": "client_retry_rate",
                "percent_change": 650.0,
                "summary": "Surge from 15 retries/sec to 450 retries/sec",
            },
            {
                "timestamp": t_sat,
                "service": "payments-db",
                "metric_name": "connection_pool_saturation",
                "percent_change": 100.0,
                "summary": "Pool reached 50/50 connections",
            },
        ],
        alerts=[{
            "timestamp": t_alert,
            "service": "payments-db",
            "name": "MySQLConnectionPoolExhausted",
            "description": "Connection pool at 100%",
        }],
    )

    assert len(timeline.events) == 4
    # Chronological verification
    assert timeline.events[0].event_type == TimelineEventType.DEPLOYMENT
    assert timeline.events[1].event_type == TimelineEventType.RETRY_STORM_START
    assert timeline.events[2].event_type == TimelineEventType.METRIC_INFLECTION
    assert timeline.events[3].event_type == TimelineEventType.ALERT_TRIGGERED

    assert timeline.triggering_change_event_id == timeline.events[0].event_id
    assert timeline.primary_symptom_event_id == timeline.events[3].event_id

    # Verify deltas relative to triggering deployment
    assert timeline.events[0].delta_seconds_from_trigger == 0.0
    assert timeline.events[1].delta_seconds_from_trigger == 8 * 60.0  # +8 min
    assert timeline.events[3].delta_seconds_from_trigger == 15 * 60.0  # +15 min

    assert len(timeline.sequence_narrative) == 4
    assert "13:50:00" in timeline.sequence_narrative[0]
    assert "14:05:00" in timeline.sequence_narrative[3]


# =============================================================================
# Benchmark Scenario G: Conflicting/Noisy Evidence -> INCONCLUSIVE
# =============================================================================
def test_benchmark_g_conflicting_noisy_evidence_inconclusive(tenant_id, incident_id):
    """When telemetry is conflicting or incomplete, the validator must explicitly
    emit INCONCLUSIVE without hallucinating a false root cause.
    """
    res = SignalValidator.validate(
        tenant_id=tenant_id,
        incident_id=incident_id,
        alert_name="UncorrelatedNetworkJitter",
        service="gateway-mesh",
        telemetry={
            "has_conflicting_sources": True,
            "source_a": "latency_high",
            "source_b": "latency_normal",
        },
    )

    assert res.status == SignalValidationStatus.INCONCLUSIVE
    assert res.target_layer == FailureLayer.UNKNOWN
    assert res.is_target_healthy is False
    assert "insufficient or contradictory" in res.reasoning.lower()
    assert "escalate" in res.recommended_pivot.lower()

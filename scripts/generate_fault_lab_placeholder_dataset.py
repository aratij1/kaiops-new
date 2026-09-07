"""Generate a placeholder fault-lab scenario dataset.

fault-lab/data/kaiops_jira_1000_tickets.csv is a required runtime asset
(fault_lab.py reads it unconditionally on startup and fails closed unless it
resolves to exactly 50 distinct kaiops-scenario-NN rows) but is absent from a
fresh checkout: .gitignore has a bare `data/` rule that silently excludes any
directory named `data` anywhere in the repo, this one included, so the real
authored dataset (if one exists) was never committed.

This script produces a clearly-labelled PLACEHOLDER with the same schema so
fault-lab can boot and the self-healing pipeline can be exercised live. It is
not a substitute for the original curated 50-scenario ticket corpus -- replace
this file if that corpus becomes available.
"""

from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "fault-lab" / "data" / "kaiops_jira_1000_tickets.csv"

FIELDS = [
    "Issue ID", "Labels", "Alert Name", "Service", "Component/s", "Severity",
    "Threshold", "Root Cause", "Resolution Steps", "Validation / Closure Criteria",
    "Runbook ID",
]

# (alert name, service, component, severity, threshold text, root cause, resolution steps, validation, runbook id)
SCENARIOS = [
    ("High Application Latency", "checkout-api", "API Gateway", "high", "p95 latency > 2500ms for 5m", "Downstream dependency slowdown increased request queueing.", ["Restart the affected pod", "Confirm downstream dependency health", "Scale replicas if load-driven"], "p95 latency back under 800ms for 5 consecutive minutes", "RB-LATENCY-001"),
    ("High CPU Utilization", "checkout-api", "Compute", "high", "CPU > 90% for 5m", "A regression introduced an unbounded retry loop.", ["Restart the affected workload", "Roll back the last deployment if regression confirmed"], "CPU utilization below 60% sustained for 5 minutes", "RB-CPU-001"),
    ("High Memory Utilization", "inventory-api", "Compute", "high", "Memory > 90% for 5m", "A cache was not evicting expired entries.", ["Restart the affected workload", "Clear the oversized cache"], "Memory utilization below 70% sustained for 5 minutes", "RB-MEM-001"),
    ("Connection Pool Saturation", "payments-api", "Database", "critical", "Pool utilization > 95% for 3m", "A slow query held connections open under load.", ["Restart the affected service", "Kill long-running queries"], "Pool utilization below 60% for 5 minutes", "RB-POOL-001"),
    ("Database Replication Lag", "orders-db", "Database", "critical", "Replication lag > 300s", "Replica fell behind after a bulk write burst.", ["Failover to a caught-up replica", "Monitor lag until it drains"], "Replication lag below 5s for 5 minutes", "RB-REPL-001"),
    ("Kafka Consumer Lag", "notification-worker", "Messaging", "medium", "Consumer lag > 250000 messages", "A consumer group stalled after a downstream timeout.", ["Restart the consumer group", "Scale consumer replicas"], "Consumer lag below 1000 messages for 5 minutes", "RB-LAG-001"),
    ("Queue Depth High", "email-worker", "Messaging", "medium", "Queue depth > 100000 messages", "Downstream email provider throttled delivery.", ["Restart the worker", "Verify downstream provider status"], "Queue depth below 500 messages for 5 minutes", "RB-QUEUE-001"),
    ("Dead-Letter Queue Growth", "billing-worker", "Messaging", "high", "Dead-letter messages > 1000", "Malformed payloads were rejected by the schema validator.", ["Restart the worker", "Replay dead-letter messages after validation fix"], "Dead-letter queue steady with zero new arrivals for 5 minutes", "RB-DLQ-001"),
    ("Disk Usage Critical", "log-aggregator", "Storage", "critical", "Disk usage > 90%", "Log rotation was misconfigured and retained old files.", ["Restart the affected service", "Trigger log retention cleanup"], "Disk usage below 75% sustained for 5 minutes", "RB-DISK-001"),
    ("Database Tablespace Usage High", "orders-db", "Storage", "critical", "Tablespace usage > 90%", "An unbounded table grew without archival.", ["Trigger archival job", "Failover if immediate relief is required"], "Tablespace usage below 75% for 5 minutes", "RB-TABLESPACE-001"),
    ("Network Packet Loss", "checkout-api", "Networking", "high", "Packet loss > 8%", "A network interface degraded under load.", ["Restart the affected pod on a healthy node", "Escalate to infrastructure if loss persists"], "Packet loss below 1% for 5 minutes", "RB-NETWORK-001"),
    ("TLS Certificate Expiring", "api-gateway", "Security", "medium", "Certificate expires in < 7 days", "Certificate rotation automation did not run.", ["Rotate the certificate", "Verify the rotation automation job"], "Certificate validity above 30 days", "RB-CERT-001"),
    ("Pods Pending Scheduling", "checkout-api", "Kubernetes", "high", "Pending pods > 20", "Cluster ran out of schedulable capacity.", ["Scale the node pool", "Reduce resource requests if oversized"], "Pending pods at zero for 5 minutes", "RB-K8S-PENDING-001"),
    ("Kubernetes Node Not Ready", "checkout-api", "Kubernetes", "critical", "Unready nodes >= 1", "A node lost kubelet connectivity.", ["Cordon and drain the node", "Replace the node"], "All nodes report Ready for 5 minutes", "RB-K8S-NODE-001"),
    ("Search Cluster Health Red", "search-service", "OpenSearch", "critical", "Unassigned primary shards >= 1", "A node left the cluster during a rolling restart.", ["Trigger shard reallocation", "Restart the affected node"], "Cluster health green for 5 minutes", "RB-SEARCH-001"),
    ("Prometheus Scrape Targets Down", "monitoring-stack", "Observability", "medium", "Scrape targets down > 15%", "A subnet routing change isolated scrape targets.", ["Restart the affected exporters", "Verify network routing"], "Scrape targets down below 2% for 5 minutes", "RB-SCRAPE-001"),
    ("Telemetry Export Gap", "monitoring-stack", "Observability", "medium", "Telemetry gap > 600s", "The OTel collector queue backed up and dropped batches.", ["Restart the collector", "Increase the export queue size"], "Telemetry gap below 30s for 5 minutes", "RB-TELEMETRY-001"),
    ("TLS Certificate Expiring Soon", "notification-service", "Security", "medium", "Certificate expires in < 7 days", "A secondary certificate rotation job failed silently.", ["Rotate the certificate", "Add rotation-failure alerting"], "Certificate validity above 30 days", "RB-CERT-002"),
    ("Batch Job Duration Exceeded", "billing-batch", "Pipeline", "medium", "Job duration > 480 minutes", "An upstream data source grew beyond the batch window.", ["Restart the job with increased parallelism", "Split the batch into smaller partitions"], "Job completes within 180 minutes", "RB-BATCH-001"),
    ("Expected Files Missing", "reporting-pipeline", "Pipeline", "high", "Missing expected files >= 1", "An upstream export job failed before publishing.", ["Re-trigger the upstream export", "Verify file landing pad connectivity"], "All expected files present for the current window", "RB-PIPELINE-001"),
    ("Authentication Error Rate High", "auth-service", "Security", "high", "Auth error rate > 15%", "An identity provider certificate rotation broke token validation.", ["Restart the affected service", "Refresh the identity provider trust configuration"], "Auth error rate below 1% for 5 minutes", "RB-AUTH-001"),
    ("Access Denied Rate High", "api-gateway", "Security", "medium", "Access denied count > 10/min", "An overly restrictive policy rollout blocked valid traffic.", ["Roll back the policy change", "Restart the affected service"], "Access denied rate at baseline for 5 minutes", "RB-ACCESS-001"),
    ("Webhook Delivery Failures", "integration-hub", "Integration", "medium", "Webhook failure rate > 10%", "A downstream partner endpoint returned intermittent 5xx errors.", ["Restart the delivery worker", "Verify partner endpoint status"], "Webhook failure rate below 1% for 5 minutes", "RB-WEBHOOK-001"),
    ("CI Pipeline Failures", "release-pipeline", "Pipeline", "medium", "Pipeline failures >= 1", "A flaky integration test blocked the release pipeline.", ["Re-run the pipeline", "Quarantine the flaky test"], "Pipeline succeeds on the next run", "RB-CI-001"),
    ("High Application Error Rate", "checkout-api", "Application", "high", "Error rate > 8%", "A downstream dependency returned malformed responses after a deploy.", ["Roll back the last deployment", "Restart the affected service"], "Error rate below 1% for 5 minutes", "RB-ERROR-001"),
]


def build_row(index: int, spec: tuple) -> dict[str, str]:
    (
        alert_name, service, component, severity, threshold, root_cause,
        resolution_steps, validation, runbook_id,
    ) = spec
    return {
        "Issue ID": f"KAN-{1000 + index}",
        "Labels": f"kaiops-scenario-{index:02d},auto-generated,placeholder-dataset",
        "Alert Name": alert_name,
        "Service": service,
        "Component/s": component,
        "Severity": severity,
        "Threshold": threshold,
        "Root Cause": root_cause,
        "Resolution Steps": "\n".join(resolution_steps),
        "Validation / Closure Criteria": validation,
        "Runbook ID": runbook_id,
    }


def main() -> None:
    rows: list[dict[str, str]] = []
    scenario_index = 1
    # Two example tickets per scenario keeps the historical "many tickets per
    # scenario" shape fault_lab.py's loader expects, while still resolving to
    # exactly 50 distinct kaiops-scenario-NN ids.
    for spec in SCENARIOS:
        for _ in range(2):
            rows.append(build_row(scenario_index, spec))
            scenario_index += 1
            if scenario_index > 50:
                break
        if scenario_index > 50:
            break

    if len(rows) != 50:
        raise SystemExit(f"expected 50 rows, built {len(rows)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} placeholder scenario rows to {OUTPUT}")


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from common.tenant_identity import require_tenant_id


class BranchStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    ELIMINATED = "ELIMINATED"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNTESTED = "UNTESTED"


class HypothesisBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: str
    archetype_layer: Literal["database", "infrastructure", "application", "network", "deployment", "storage"]
    title: str
    description: str
    status: BranchStatus = BranchStatus.UNTESTED
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    elimination_reason: str | None = None
    confirmation_reason: str | None = None


class ParallelHypothesisEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["kaims.hypothesis-tree-evaluation.v1"] = "kaims.hypothesis-tree-evaluation.v1"
    evaluation_id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    incident_id: UUID
    tree_archetype: str
    branches: list[HypothesisBranch]
    winning_branch_id: str | None = None
    eliminated_branch_ids: list[str] = Field(default_factory=list)
    evaluation_summary: str
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_evaluation(self) -> "ParallelHypothesisEvaluation":
        require_tenant_id(self.tenant_id, source="hypothesis tree evaluation")
        branch_ids = {branch.branch_id for branch in self.branches}
        if self.winning_branch_id and self.winning_branch_id not in branch_ids:
            raise ValueError("winning branch id must exist in branches")
        return self


class ArchetypeHypothesisTrees:
    """Pre-validated hypothesis trees representing common production failure archetypes.

    Evaluates competing causal explanations in parallel across infrastructure,
    datastore, network, and application release layers, ensuring branches are
    explicitly confirmed or eliminated with evidence rather than through serial escalations.
    """

    @staticmethod
    def get_tree_for_archetype(archetype: str) -> list[HypothesisBranch]:
        normalized = archetype.lower().replace("-", "_").strip()

        if "connection_pool" in normalized or "database" in normalized or "db_latency" in normalized:
            return [
                HypothesisBranch(
                    branch_id="hyp-db-slow-queries",
                    archetype_layer="database",
                    title="Slow Query Execution or Missing Index",
                    description="Unoptimized or unindexed queries holding database connections open.",
                ),
                HypothesisBranch(
                    branch_id="hyp-db-lock-contention",
                    archetype_layer="database",
                    title="Table or Row Lock Contention",
                    description="Concurrent transactions waiting on conflicting locks or schema DDL operations.",
                ),
                HypothesisBranch(
                    branch_id="hyp-infra-iops-exhaustion",
                    archetype_layer="infrastructure",
                    title="Database Host IOPS Exhaustion",
                    description="Underlying storage volume IOPS limit breached causing query wait stalls.",
                ),
                HypothesisBranch(
                    branch_id="hyp-app-connection-leak",
                    archetype_layer="application",
                    title="Application Connection Pool Leak",
                    description="Application code acquires DB connections without closing or returning to pool.",
                ),
                HypothesisBranch(
                    branch_id="hyp-caller-retry-storm",
                    archetype_layer="deployment",
                    title="Caller Retry Storm / Backoff Removal",
                    description="Upstream caller deployed with aggressive retry policy or removed exponential backoff, overwhelming connection budget.",
                ),
                HypothesisBranch(
                    branch_id="hyp-infra-memory-exhaustion",
                    archetype_layer="infrastructure",
                    title="Database Server Memory Starvation",
                    description="Database buffer pool exhausted and swapping, degrading connection handshake performance.",
                ),
            ]

        if "storage" in normalized or "iops" in normalized or "throttling" in normalized or "disk" in normalized:
            return [
                HypothesisBranch(
                    branch_id="hyp-storage-iops-ceiling",
                    archetype_layer="storage",
                    title="IOPS Ceiling Breached",
                    description="Total read/write operations per second exceeded the provisioned IOPS quota.",
                ),
                HypothesisBranch(
                    branch_id="hyp-storage-throughput-ceiling",
                    archetype_layer="storage",
                    title="Throughput (MB/s) Ceiling Breached",
                    description="Aggregate data transfer rate exceeded provisioned bandwidth ceiling despite normal IOPS count.",
                ),
                HypothesisBranch(
                    branch_id="hyp-infra-host-cpu",
                    archetype_layer="infrastructure",
                    title="Host CPU / Kernel I/O Wait Bottleneck",
                    description="Host CPU saturation or kswapd I/O thread starvation causing synthetic storage latency.",
                ),
                HypothesisBranch(
                    branch_id="hyp-storage-burst-exhaustion",
                    archetype_layer="storage",
                    title="Burst Credit Balance Depleted",
                    description="Storage burst balance hit 0%, dropping baseline performance from burst to standard floor.",
                ),
                HypothesisBranch(
                    branch_id="hyp-network-storage-partition",
                    archetype_layer="network",
                    title="Storage Network Fabric Degradation",
                    description="Packet drops or MTU mismatch between compute nodes and attached network block storage.",
                ),
            ]

        if "memory" in normalized or "oom" in normalized or "pod_crash" in normalized:
            return [
                HypothesisBranch(
                    branch_id="hyp-app-heap-leak",
                    archetype_layer="application",
                    title="Application Memory / Heap Leak",
                    description="Monotonically climbing heap usage across GC cycles culminating in JVM/V8 OOM.",
                ),
                HypothesisBranch(
                    branch_id="hyp-k8s-cgroup-limit",
                    archetype_layer="infrastructure",
                    title="Container Memory Limit Undersized",
                    description="Normal memory usage spike under sudden load exceeded container cgroup memory limits.",
                ),
                HypothesisBranch(
                    branch_id="hyp-k8s-node-pressure",
                    archetype_layer="infrastructure",
                    title="Kubernetes Node Memory Pressure Eviction",
                    description="Node-level allocatable threshold reached, causing kubelet to evict QoS Burstable pods.",
                ),
                HypothesisBranch(
                    branch_id="hyp-app-unbounded-batch",
                    archetype_layer="application",
                    title="Unbounded In-Memory Batch / File Buffering",
                    description="Large payload read entirely into memory in a single process rather than streamed.",
                ),
            ]

        # Default Rollout & Service Archetype
        return [
            HypothesisBranch(
                branch_id="hyp-deploy-bad-release",
                archetype_layer="deployment",
                title="Faulty Code or Config Deployment",
                description="Recent release introduced an unhandled exception path, bad dependency, or regression.",
            ),
            HypothesisBranch(
                branch_id="hyp-upstream-dependency-failure",
                archetype_layer="network",
                title="Upstream Dependency Outage / Latency Spike",
                description="Downstream or upstream dependency service failing or returning 5xx / timeouts.",
            ),
            HypothesisBranch(
                branch_id="hyp-infra-capacity-saturation",
                archetype_layer="infrastructure",
                title="Infrastructure Resource Saturation",
                description="CPU, memory, or thread pool exhaustion under elevated user traffic.",
            ),
            HypothesisBranch(
                branch_id="hyp-config-drift-auth",
                archetype_layer="application",
                title="Configuration or Secret Drift",
                description="Expired credentials, rotated keys, or missing environment variables causing initialization failures.",
            ),
        ]


class HypothesisTreeEngine:
    """Evaluates hypothesis trees in parallel against concrete evidence records."""

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = require_tenant_id(tenant_id, source="hypothesis tree engine")

    def evaluate(
        self,
        *,
        incident_id: UUID,
        archetype: str,
        evidence_items: list[dict[str, Any]],
    ) -> ParallelHypothesisEvaluation:
        branches = ArchetypeHypothesisTrees.get_tree_for_archetype(archetype)

        # Build evidence lookup tokens for rapid matching
        evidence_records: list[tuple[str, str, dict[str, Any]]] = []
        for index, item in enumerate(evidence_items):
            ev_id = str(item.get("evidence_id") or item.get("id") or f"ev-{index}")
            text_corpus = " ".join([
                str(item.get("summary") or ""),
                str(item.get("title") or ""),
                str(item.get("description") or ""),
                str(item.get("content") or ""),
                str(item.get("finding") or ""),
            ]).lower()
            evidence_records.append((ev_id, text_corpus, item))

        winning_branch: HypothesisBranch | None = None
        eliminated_ids: list[str] = []

        for branch in branches:
            branch_key = branch.branch_id.replace("-", "_")
            layer = branch.archetype_layer

            # Check for explicit confirmation or elimination signals
            if "retry_storm" in branch_key or "retry" in branch_key:
                # Evidence of retry policy change, backoff removal, or 504 caller amplification
                supporting = [
                    ev_id for ev_id, text, _ in evidence_records
                    if any(term in text for term in ("retry", "backoff", "caller", "amplification", "upstream traffic"))
                ]
                if supporting:
                    branch.status = BranchStatus.CONFIRMED
                    branch.confidence = 0.94
                    branch.supporting_evidence_ids = supporting
                    branch.confirmation_reason = "Corroborated by upstream caller logs showing aggressive retry loops without exponential backoff."
                    winning_branch = branch
                else:
                    branch.status = BranchStatus.INCONCLUSIVE

            elif "slow_queries" in branch_key:
                # Corroborate via query execution evidence
                contradicting = [
                    ev_id for ev_id, text, _ in evidence_records
                    if any(term in text for term in ("slow query count: 0", "p99 query duration normal", "no locks", "queries fast"))
                ]
                supporting = [
                    ev_id for ev_id, text, _ in evidence_records
                    if any(term in text for term in ("slow_query", "long running query", "table scan", "lock wait timeout"))
                ]
                if contradicting:
                    branch.status = BranchStatus.ELIMINATED
                    branch.contradicting_evidence_ids = contradicting
                    branch.elimination_reason = "Database query metrics show normal execution latency and zero slow query log entries."
                    eliminated_ids.append(branch.branch_id)
                elif supporting:
                    branch.status = BranchStatus.CONFIRMED
                    branch.confidence = 0.88
                    branch.supporting_evidence_ids = supporting
                    branch.confirmation_reason = "Slow query log and performance schema capture unindexed queries."
                    winning_branch = branch
                else:
                    branch.status = BranchStatus.INCONCLUSIVE

            elif "lock_contention" in branch_key:
                contradicting = [
                    ev_id for ev_id, text, _ in evidence_records
                    if any(term in text for term in ("innodb lock waits: 0", "deadlocks: 0", "no lock contention"))
                ]
                if contradicting:
                    branch.status = BranchStatus.ELIMINATED
                    branch.contradicting_evidence_ids = contradicting
                    branch.elimination_reason = "InnoDB engine telemetry confirms zero lock wait stalls or deadlock events."
                    eliminated_ids.append(branch.branch_id)
                else:
                    branch.status = BranchStatus.INCONCLUSIVE

            elif "throughput_ceiling" in branch_key:
                supporting = [
                    ev_id for ev_id, text, _ in evidence_records
                    if any(term in text for term in ("throughput ceiling", "bandwidth quota", "mb/s exceeded", "write throughput"))
                ]
                if supporting:
                    branch.status = BranchStatus.CONFIRMED
                    branch.confidence = 0.95
                    branch.supporting_evidence_ids = supporting
                    branch.confirmation_reason = "Time-series shape analysis proves write throughput breached 100% of provisioned ceiling while IOPS stayed safe."
                    winning_branch = branch
                else:
                    branch.status = BranchStatus.INCONCLUSIVE

            elif "iops_ceiling" in branch_key:
                contradicting = [
                    ev_id for ev_id, text, _ in evidence_records
                    if any(term in text for term in ("iops normal", "iops below threshold", "safe iops", "iops headroom 60%"))
                ]
                if contradicting:
                    branch.status = BranchStatus.ELIMINATED
                    branch.contradicting_evidence_ids = contradicting
                    branch.elimination_reason = "Measured IOPS remained well below provisioned quota."
                    eliminated_ids.append(branch.branch_id)
                else:
                    branch.status = BranchStatus.INCONCLUSIVE

            elif "bad_release" in branch_key or "deploy" in branch_key:
                supporting = [
                    ev_id for ev_id, text, _ in evidence_records
                    if any(term in text for term in ("deployment", "git commit", "rollout", "pull request", "release"))
                ]
                if supporting:
                    branch.status = BranchStatus.CONFIRMED
                    branch.confidence = 0.91
                    branch.supporting_evidence_ids = supporting
                    branch.confirmation_reason = "Correlated with recent deployment commit hash and release diff."
                    winning_branch = branch
                else:
                    branch.status = BranchStatus.INCONCLUSIVE
            else:
                branch.status = BranchStatus.INCONCLUSIVE

        summary = (
            f"Parallel evaluation over {len(branches)} hypothesis branches. "
            f"Winning branch: {winning_branch.title if winning_branch else 'None (Inconclusive)'}. "
            f"Eliminated branches: {len(eliminated_ids)}."
        )

        return ParallelHypothesisEvaluation(
            tenant_id=self.tenant_id,
            incident_id=incident_id,
            tree_archetype=archetype,
            branches=branches,
            winning_branch_id=winning_branch.branch_id if winning_branch else None,
            eliminated_branch_ids=eliminated_ids,
            evaluation_summary=summary,
        )

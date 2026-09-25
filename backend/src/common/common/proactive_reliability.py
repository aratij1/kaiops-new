from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from common.tenant_identity import require_tenant_id


class BlastRadiusRisk(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChangeImpactReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["kaims.change-impact.v1"] = "kaims.change-impact.v1"
    analysis_id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    repository: str
    target_service: str
    pr_number: int | None = None
    commit_sha: str | None = None
    changed_components: list[str]
    impacted_downstream_services: list[str]
    blast_radius_score: float = Field(ge=0.0, le=1.0)
    risk_tier: BlastRadiusRisk
    architectural_warnings: list[str] = Field(default_factory=list)
    recommended_gates: list[str] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_report(self) -> "ChangeImpactReport":
        require_tenant_id(self.tenant_id, source="change impact report")
        return self


class CapacityHeadroomReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["kaims.capacity-headroom.v1"] = "kaims.capacity-headroom.v1"
    report_id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    service: str
    resource_type: str
    current_utilization: float
    provisioned_ceiling: float
    saturation_percent: float
    burn_rate_per_day: float
    estimated_days_to_exhaustion: float | None = None
    exhaustion_risk: BlastRadiusRisk
    recommended_remediation: str
    forecasted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_headroom(self) -> "CapacityHeadroomReport":
        require_tenant_id(self.tenant_id, source="capacity headroom report")
        return self


class ProactiveReliabilityEngine:
    """Proactive Reliability Pillar (Sherlocks.ai Pillar 4 & Mode 3).

    Performs change impact analysis against service topology before release,
    and forecasts capacity / headroom exhaustion before outages occur.
    """

    def __init__(self, tenant_id: str, service_topology: dict[str, list[str]] | None = None) -> None:
        self.tenant_id = require_tenant_id(tenant_id, source="proactive reliability engine")
        # Topology mapping: service -> list of downstream dependencies
        self.topology = service_topology or {
            "checkout": ["payments", "inventory", "customer-db"],
            "payments": ["payments-db", "fraud-detection", "banking-gateway"],
            "orders": ["payments", "inventory", "shipping"],
            "inventory": ["inventory-db"],
        }

    def analyze_change_impact(
        self,
        *,
        target_service: str,
        changed_files: list[str],
        diff_text: str = "",
        repository: str = "main-repo",
        pr_number: int | None = None,
    ) -> ChangeImpactReport:
        downstream = self.topology.get(target_service, [])
        warnings: list[str] = []
        gates: list[str] = []

        norm_diff = diff_text.lower()
        is_retry_change = any(k in norm_diff for k in ("retry", "backoff", "attempts", "reconnect"))
        is_schema_change = any(f.endswith((".sql", "schema.py", "migration.py")) for f in changed_files)
        is_timeout_change = any(k in norm_diff for k in ("timeout", "deadline", "keepalive"))

        # Calculate blast radius
        base_score = 0.2
        if downstream:
            base_score += min(0.4, 0.1 * len(downstream))
        if is_retry_change:
            base_score += 0.3
            warnings.append(
                "Change modifies client retry logic. Risk of caller retry storm under backend latency degradation."
            )
            gates.append("Enforce exponential backoff and randomized jitter on all client HTTP retry loops.")
        if is_schema_change:
            base_score += 0.2
            warnings.append("Change includes database schema migration; potential lock contention.")
            gates.append("Run online DDL checker (gh-ost / pt-online-schema-change) before deploy.")
        if is_timeout_change:
            base_score += 0.15
            warnings.append("Change alters connection timeouts; check for cascading timeout mismatch.")

        blast_radius = min(1.0, round(base_score, 2))
        if blast_radius >= 0.75:
            risk = BlastRadiusRisk.CRITICAL
        elif blast_radius >= 0.50:
            risk = BlastRadiusRisk.HIGH
        elif blast_radius >= 0.30:
            risk = BlastRadiusRisk.MEDIUM
        else:
            risk = BlastRadiusRisk.LOW

        return ChangeImpactReport(
            tenant_id=self.tenant_id,
            repository=repository,
            target_service=target_service,
            pr_number=pr_number,
            changed_components=changed_files,
            impacted_downstream_services=downstream,
            blast_radius_score=blast_radius,
            risk_tier=risk,
            architectural_warnings=warnings,
            recommended_gates=gates,
        )

    def forecast_capacity_headroom(
        self,
        *,
        service: str,
        resource_type: str,
        history_values: list[float],
        provisioned_ceiling: float,
        time_interval_days: float = 7.0,
    ) -> CapacityHeadroomReport:
        if not history_values or provisioned_ceiling <= 0:
            return CapacityHeadroomReport(
                tenant_id=self.tenant_id,
                service=service,
                resource_type=resource_type,
                current_utilization=0.0,
                provisioned_ceiling=provisioned_ceiling,
                saturation_percent=0.0,
                burn_rate_per_day=0.0,
                estimated_days_to_exhaustion=None,
                exhaustion_risk=BlastRadiusRisk.LOW,
                recommended_remediation="No metrics available for headroom forecasting.",
            )

        current = history_values[-1]
        saturation = (current / provisioned_ceiling) * 100.0

        # Calculate linear burn rate
        n = len(history_values)
        if n >= 2:
            change = history_values[-1] - history_values[0]
            burn_rate = change / max(0.1, time_interval_days)
        else:
            burn_rate = 0.0

        days_remaining = None
        if burn_rate > 0:
            headroom = provisioned_ceiling - current
            if headroom <= 0:
                days_remaining = 0.0
            else:
                days_remaining = round(headroom / burn_rate, 1)

        # Classify risk
        if days_remaining is not None and days_remaining <= 3.0:
            risk = BlastRadiusRisk.CRITICAL
            remediation = f"Immediate action required: Provision capacity increase within {days_remaining} days to avoid outage."
        elif days_remaining is not None and days_remaining <= 14.0:
            risk = BlastRadiusRisk.HIGH
            remediation = f"Plan capacity expansion: Current growth rate will deplete ceiling in {days_remaining} days."
        elif saturation >= 85.0:
            risk = BlastRadiusRisk.MEDIUM
            remediation = f"Utilization high at {saturation:.1f}%. Monitor closely."
        else:
            risk = BlastRadiusRisk.LOW
            remediation = "Capacity headroom within healthy operating envelope."

        return CapacityHeadroomReport(
            tenant_id=self.tenant_id,
            service=service,
            resource_type=resource_type,
            current_utilization=round(current, 2),
            provisioned_ceiling=round(provisioned_ceiling, 2),
            saturation_percent=round(saturation, 1),
            burn_rate_per_day=round(burn_rate, 2),
            estimated_days_to_exhaustion=days_remaining,
            exhaustion_risk=risk,
            recommended_remediation=remediation,
        )

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from common.models import Alert
from common.tenant_identity import require_tenant_id


class ChecklistStatus(StrEnum):
    NORMAL = "NORMAL"
    INCONCLUSIVE = "INCONCLUSIVE"
    SPECIFIC_FINDING = "SPECIFIC_FINDING"


class ChecklistItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    check_id: str
    name: str
    target: str
    passed: bool
    conclusive: bool
    details: str
    observed_value: Any | None = None
    threshold: Any | None = None


class ChecklistTriageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["kaims.checklist-triage.v1"] = "kaims.checklist-triage.v1"
    triage_id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    incident_id: UUID
    service: str
    status: ChecklistStatus
    items: list[ChecklistItem]
    finding_summary: str
    should_escalate_to_full_investigation: bool
    suppression_recommended: bool = False
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_triage_result(self) -> "ChecklistTriageResult":
        require_tenant_id(self.tenant_id, source="checklist triage result")
        if self.status == ChecklistStatus.NORMAL:
            self.should_escalate_to_full_investigation = False
            self.suppression_recommended = True
        elif self.status == ChecklistStatus.INCONCLUSIVE:
            self.should_escalate_to_full_investigation = True
            self.suppression_recommended = False
        elif self.status == ChecklistStatus.SPECIFIC_FINDING:
            # When a specific finding is verified, we can immediately route to action/approval
            self.should_escalate_to_full_investigation = False
            self.suppression_recommended = False
        return self


class ChecklistTriageEngine:
    """Mode 2 Fast Checklist Triage.

    Runs fast, deterministic diagnostic checklists on incoming alerts
    before initiating an expensive multi-agent or LLM investigation loop.
    Returns:
      - NORMAL: All health checks passed; transient burst or self-clearing condition.
      - INCONCLUSIVE: Checks ran, but could not settle the issue; escalates to Mode 1.
      - SPECIFIC_FINDING: A deterministic failure invariant was identified and pinpointed.
    """

    def __init__(self, custom_rules: list[dict[str, Any]] | None = None) -> None:
        self.custom_rules = custom_rules or []

    def evaluate(
        self,
        *,
        alert: Alert,
        incident_id: UUID,
        telemetry_samples: dict[str, Any] | None = None,
        runtime_status: dict[str, Any] | None = None,
    ) -> ChecklistTriageResult:
        tenant_id = require_tenant_id(getattr(alert, "tenant_id", "default"), source="checklist evaluation")
        service = str(alert.service or "unknown").strip()
        samples = telemetry_samples or {}
        runtime = runtime_status or {}

        items: list[ChecklistItem] = []

        # Check 1: Current Service Health Ping / Probes
        probes_healthy = runtime.get("probes_healthy")
        endpoint_available = runtime.get("endpoint_available")
        if probes_healthy is not None or endpoint_available is not None:
            is_healthy = bool(probes_healthy if probes_healthy is not None else endpoint_available)
            items.append(
                ChecklistItem(
                    check_id="probe_health",
                    name="Readiness and Liveness Probes",
                    target=service,
                    passed=is_healthy,
                    conclusive=False,
                    details="Probes healthy and service accepting traffic" if is_healthy else "Service failing readiness/liveness probes",
                    observed_value="healthy" if is_healthy else "unhealthy",
                    threshold="healthy",
                )
            )

        # Check 2: Transient Burst / Self-clearing check
        # If the metric that triggered the alert has already dropped back below alert threshold
        current_rate = samples.get("current_value")
        threshold_val = samples.get("threshold_value")
        if current_rate is not None and threshold_val is not None:
            try:
                curr = float(current_rate)
                thresh = float(threshold_val)
                comparator = str(samples.get("comparator") or "gt").lower()
                is_breached = curr > thresh if comparator in {"gt", ">", "above"} else curr < thresh
                passed = not is_breached
                items.append(
                    ChecklistItem(
                        check_id="threshold_recovery",
                        name="Threshold Current Status",
                        target=service,
                        passed=passed,
                        conclusive=False,
                        details="Metric has dropped back to normal operating bounds" if passed else f"Metric remains breached: {curr} vs threshold {thresh}",
                        observed_value=curr,
                        threshold=thresh,
                    )
                )
            except (ValueError, TypeError):
                pass

        # Check 3: Deterministic Pod Crashloop / Eviction
        restart_count = runtime.get("restart_count")
        if restart_count is not None:
            try:
                restarts = int(restart_count)
                has_excessive_restarts = restarts >= 5
                items.append(
                    ChecklistItem(
                        check_id="crashloop_backoff",
                        name="Pod CrashLoopBackOff Check",
                        target=service,
                        passed=not has_excessive_restarts,
                        conclusive=has_excessive_restarts,
                        details=f"Pod in CrashLoopBackOff with {restarts} restarts in window" if has_excessive_restarts else f"Normal restart count: {restarts}",
                        observed_value=restarts,
                        threshold=5,
                    )
                )
            except (ValueError, TypeError):
                pass

        # Check 4: Disk / Capacity Hard Ceiling
        disk_pct = samples.get("disk_usage_percent")
        if disk_pct is not None:
            try:
                dp = float(disk_pct)
                full = dp >= 98.0
                items.append(
                    ChecklistItem(
                        check_id="disk_exhaustion",
                        name="Storage Volume Exhaustion",
                        target=service,
                        passed=not full,
                        conclusive=full,
                        details=f"Volume disk space exhausted at {dp:.1f}%" if full else f"Disk headroom normal at {dp:.1f}%",
                        observed_value=dp,
                        threshold=98.0,
                    )
                )
            except (ValueError, TypeError):
                pass

        # Check 5: Certificate Expiration
        cert_days = samples.get("cert_days_remaining")
        if cert_days is not None:
            try:
                days = float(cert_days)
                expired = days <= 0
                items.append(
                    ChecklistItem(
                        check_id="cert_expiry",
                        name="TLS Certificate Expiration",
                        target=service,
                        passed=not expired,
                        conclusive=expired,
                        details="TLS certificate is expired" if expired else f"TLS certificate valid ({days:.0f} days remaining)",
                        observed_value=days,
                        threshold=0,
                    )
                )
            except (ValueError, TypeError):
                pass

        # Determine Tri-state status
        if not items:
            # If no fast-path checklist items were available, result is inconclusive -> escalate
            return ChecklistTriageResult(
                tenant_id=tenant_id,
                incident_id=incident_id,
                service=service,
                status=ChecklistStatus.INCONCLUSIVE,
                items=[],
                finding_summary="No pre-flight diagnostic checklists matched; escalating to full investigation.",
                should_escalate_to_full_investigation=True,
            )

        failed_items = [item for item in items if not item.passed]
        conclusive_failures = [item for item in failed_items if item.conclusive]

        if not failed_items:
            # Every check passed! Transient burst or self-cleared
            return ChecklistTriageResult(
                tenant_id=tenant_id,
                incident_id=incident_id,
                service=service,
                status=ChecklistStatus.NORMAL,
                items=items,
                finding_summary="All pre-flight checks passed. Metric within baseline and probes healthy; alert is transient.",
                should_escalate_to_full_investigation=False,
                suppression_recommended=True,
            )

        if conclusive_failures:
            primary = conclusive_failures[0]
            return ChecklistTriageResult(
                tenant_id=tenant_id,
                incident_id=incident_id,
                service=service,
                status=ChecklistStatus.SPECIFIC_FINDING,
                items=items,
                finding_summary=f"Deterministic failure identified by checklist [{primary.name}]: {primary.details}",
                should_escalate_to_full_investigation=False,
                suppression_recommended=False,
            )

        # Failed checks exist but they are inconclusive
        return ChecklistTriageResult(
            tenant_id=tenant_id,
            incident_id=incident_id,
            service=service,
            status=ChecklistStatus.INCONCLUSIVE,
            items=items,
            finding_summary=f"Checklist inconclusive: {len(failed_items)} checks failed without conclusive single-cause invariant. Escalating to Mode 1.",
            should_escalate_to_full_investigation=True,
            suppression_recommended=False,
        )

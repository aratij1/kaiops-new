from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from common.tenant_identity import require_tenant_id


class TimelinePhase(StrEnum):
    REPORTED_SYMPTOM = "REPORTED_SYMPTOM"
    MONITORING_OBSERVED = "MONITORING_OBSERVED"
    ACTUAL_EVENTS = "ACTUAL_EVENTS"


class TimelineEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: TimelinePhase
    timestamp: datetime
    title: str
    description: str
    source: str
    evidence_ids: list[str] = Field(default_factory=list)


class RemediationTier(StrEnum):
    TIER_1_IMMEDIATE_FIX = "TIER_1_IMMEDIATE_FIX"
    TIER_2_RELEASE_GATE = "TIER_2_RELEASE_GATE"
    TIER_3_ESTATE_BLAST_RADIUS = "TIER_3_ESTATE_BLAST_RADIUS"


class GradedNextStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tier: RemediationTier
    priority: Literal["P0", "P1", "P2"]
    title: str
    action_item: str
    owner_team: str
    automated_executable: bool = False
    verification_method: str


class PublishedInvestigation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["kaims.published-investigation.v1"] = "kaims.published-investigation.v1"
    investigation_id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    incident_id: UUID
    service: str
    incident_title: str
    root_cause_summary: str
    three_phase_timeline: list[TimelineEntry]
    graded_next_steps: list[GradedNextStep]
    eliminated_hypotheses_count: int = 0
    confirmed_hypotheses_count: int = 1
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_investigation(self) -> "PublishedInvestigation":
        require_tenant_id(self.tenant_id, source="published investigation")
        if not self.three_phase_timeline:
            raise ValueError("published investigation requires at least one timeline entry")
        if not self.graded_next_steps:
            raise ValueError("published investigation requires graded next steps")
        return self

    def to_markdown_artifact(self) -> str:
        """Formats the published investigation into the standard post-mortem format."""
        lines = [
            f"# Published Investigation: {self.incident_title}",
            "",
            f"**Incident ID:** `{self.incident_id}` | **Service:** `{self.service}` | **Published:** {self.published_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "## Executive Summary",
            self.root_cause_summary,
            "",
            f"- **Hypotheses Evaluated:** {self.eliminated_hypotheses_count + self.confirmed_hypotheses_count}",
            f"- **Confirmed Causes:** {self.confirmed_hypotheses_count}",
            f"- **Eliminated Non-Causes:** {self.eliminated_hypotheses_count}",
            "",
            "## 3-Phase Incident Timeline",
            "",
            "| Phase | Timestamp (UTC) | Description | Source |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for item in sorted(self.three_phase_timeline, key=lambda t: t.timestamp):
            phase_label = {
                TimelinePhase.REPORTED_SYMPTOM: "1. What Was Reported",
                TimelinePhase.MONITORING_OBSERVED: "2. What Monitoring Showed",
                TimelinePhase.ACTUAL_EVENTS: "3. What Actually Happened",
            }.get(item.phase, item.phase.value)
            ts_str = item.timestamp.strftime("%H:%M:%S")
            lines.append(f"| **{phase_label}** | {ts_str} | {item.title}: {item.description} | `{item.source}` |")

        lines.extend([
            "",
            "## 3-Tier Graded Next Steps",
            "",
        ])

        for step in sorted(self.graded_next_steps, key=lambda s: s.tier.value):
            tier_badge = {
                RemediationTier.TIER_1_IMMEDIATE_FIX: "Tier 1: Immediate Remediation",
                RemediationTier.TIER_2_RELEASE_GATE: "Tier 2: Architectural Release Gate",
                RemediationTier.TIER_3_ESTATE_BLAST_RADIUS: "Tier 3: Estate-Wide Blast Radius Scan",
            }.get(step.tier, step.tier.value)

            lines.extend([
                f"### [{step.priority}] {tier_badge}: {step.title}",
                f"- **Action:** {step.action_item}",
                f"- **Owner:** `{step.owner_team}`",
                f"- **Automated Verification:** {'Yes' if step.automated_executable else 'Manual'}",
                f"- **Verification Check:** {step.verification_method}",
                "",
            ])

        return "\n".join(lines)


class PublishedInvestigationBuilder:
    """Helper to assemble a PublishedInvestigation from KAIMS incident artifacts."""

    @staticmethod
    def build(
        *,
        tenant_id: str,
        incident_id: UUID,
        service: str,
        incident_title: str,
        root_cause: str,
        reported_at: datetime,
        reported_text: str,
        monitored_at: datetime,
        monitoring_text: str,
        actual_at: datetime,
        actual_ground_truth: str,
        immediate_fix: str,
        release_gate: str,
        estate_scan: str,
        owner_team: str = "sre-core",
        eliminated_count: int = 5,
    ) -> PublishedInvestigation:
        timeline = [
            TimelineEntry(
                phase=TimelinePhase.REPORTED_SYMPTOM,
                timestamp=reported_at,
                title="Symptom Reported",
                description=reported_text,
                source="pagerduty/slack",
            ),
            TimelineEntry(
                phase=TimelinePhase.MONITORING_OBSERVED,
                timestamp=monitored_at,
                title="Alarm Fired",
                description=monitoring_text,
                source="cloudwatch/prometheus",
            ),
            TimelineEntry(
                phase=TimelinePhase.ACTUAL_EVENTS,
                timestamp=actual_at,
                title="Underlying Root Cause",
                description=actual_ground_truth,
                source="kaiops-discovery-mcp",
            ),
        ]

        steps = [
            GradedNextStep(
                tier=RemediationTier.TIER_1_IMMEDIATE_FIX,
                priority="P0",
                title="Restore Service Operation",
                action_item=immediate_fix,
                owner_team=owner_team,
                automated_executable=True,
                verification_method="Verify HTTP 200 latency drops back below p99 200ms threshold.",
            ),
            GradedNextStep(
                tier=RemediationTier.TIER_2_RELEASE_GATE,
                priority="P1",
                title="Prevent Reintroduction via CI/CD Policy Gate",
                action_item=release_gate,
                owner_team="devops-platform",
                automated_executable=True,
                verification_method="Run automated linter checking HTTP retry backoff parameters before deployment.",
            ),
            GradedNextStep(
                tier=RemediationTier.TIER_3_ESTATE_BLAST_RADIUS,
                priority="P2",
                title="Estate-Wide Proactive Scan",
                action_item=estate_scan,
                owner_team="reliability-architecture",
                automated_executable=False,
                verification_method="Crawl all active microservice dependency repos against knowledge graph.",
            ),
        ]

        return PublishedInvestigation(
            tenant_id=tenant_id,
            incident_id=incident_id,
            service=service,
            incident_title=incident_title,
            root_cause_summary=root_cause,
            three_phase_timeline=timeline,
            graded_next_steps=steps,
            eliminated_hypotheses_count=eliminated_count,
            confirmed_hypotheses_count=1,
        )

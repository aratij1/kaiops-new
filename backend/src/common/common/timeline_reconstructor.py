from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from common.tenant_identity import require_tenant_id


class TimelineEventType(StrEnum):
    DEPLOYMENT = "DEPLOYMENT"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    DATABASE_MIGRATION = "DATABASE_MIGRATION"
    SECURITY_GROUP_CHANGE = "SECURITY_GROUP_CHANGE"
    RETRY_STORM_START = "RETRY_STORM_START"
    METRIC_INFLECTION = "METRIC_INFLECTION"
    LOG_ANOMALY_BURST = "LOG_ANOMALY_BURST"
    PROBE_FAILURE = "PROBE_FAILURE"
    ALERT_TRIGGERED = "ALERT_TRIGGERED"
    ALERT_CLEARED = "ALERT_CLEARED"
    HUMAN_ACTION = "HUMAN_ACTION"


class EventSignificance(StrEnum):
    TRIGGERING_CHANGE = "TRIGGERING_CHANGE"
    INTERMEDIATE_AMPLIFIER = "INTERMEDIATE_AMPLIFIER"
    PRIMARY_SYMPTOM = "PRIMARY_SYMPTOM"
    CORRELATED_METRIC = "CORRELATED_METRIC"
    MITIGATION_ATTEMPT = "MITIGATION_ATTEMPT"
    INFORMATIONAL = "INFORMATIONAL"


class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: f"evt-{uuid4().hex[:8]}")
    timestamp: datetime
    event_type: TimelineEventType
    source: str
    service: str
    title: str
    description: str
    significance: EventSignificance = EventSignificance.INFORMATIONAL
    delta_seconds_from_trigger: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class IncidentTimeline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["kaims.incident-timeline.v1"] = "kaims.incident-timeline.v1"
    timeline_id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    incident_id: UUID
    events: list[TimelineEvent] = Field(default_factory=list)
    sequence_narrative: list[str] = Field(default_factory=list)
    triggering_change_event_id: str | None = None
    primary_symptom_event_id: str | None = None
    root_cause_window_start: datetime | None = None
    root_cause_window_end: datetime | None = None
    reconstructed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_identity(self) -> "IncidentTimeline":
        require_tenant_id(self.tenant_id, source="incident timeline")
        return self


class TimelineReconstructor:
    """Reconstructs high-fidelity chronological incident timelines correlating changes,
    metric inflections, log bursts, and alerts across multiple estate domains.
    """

    @staticmethod
    def _parse_ts(ts_raw: Any) -> datetime:
        if isinstance(ts_raw, datetime):
            return ts_raw.astimezone(UTC) if ts_raw.tzinfo else ts_raw.replace(tzinfo=UTC)
        if isinstance(ts_raw, (int, float)):
            return datetime.fromtimestamp(ts_raw, tz=UTC)
        if isinstance(ts_raw, str):
            try:
                return datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).astimezone(UTC)
            except Exception:
                pass
        return datetime.now(UTC)

    @classmethod
    def reconstruct(
        cls,
        *,
        tenant_id: str,
        incident_id: UUID,
        alerts: list[dict[str, Any]] | None = None,
        deployments: list[dict[str, Any]] | None = None,
        config_changes: list[dict[str, Any]] | None = None,
        metric_inflections: list[dict[str, Any]] | None = None,
        log_bursts: list[dict[str, Any]] | None = None,
        human_actions: list[dict[str, Any]] | None = None,
    ) -> IncidentTimeline:
        require_tenant_id(tenant_id, source="timeline reconstructor")
        raw_events: list[TimelineEvent] = []

        # 1. Ingest Deployments & Migrations
        for dep in deployments or []:
            ts = cls._parse_ts(dep.get("timestamp") or dep.get("created_at") or dep.get("deployed_at"))
            svc = str(dep.get("service") or dep.get("target_service") or "unknown-service")
            title = str(dep.get("title") or f"Deployment {dep.get('version', '')} on {svc}")
            desc = str(dep.get("description") or dep.get("commit_message") or json.dumps(dep, default=str))
            raw_events.append(
                TimelineEvent(
                    timestamp=ts,
                    event_type=TimelineEventType.DEPLOYMENT,
                    source=str(dep.get("source") or "jenkins://pipeline"),
                    service=svc,
                    title=title,
                    description=desc,
                    significance=EventSignificance.TRIGGERING_CHANGE,
                    evidence_ids=[str(dep.get("evidence_id") or dep.get("id") or "ev-deploy")],
                    metadata=dict(dep),
                )
            )

        # 2. Ingest Config Changes & Migrations
        for cfg in config_changes or []:
            ts = cls._parse_ts(cfg.get("timestamp") or cfg.get("applied_at"))
            svc = str(cfg.get("service") or "unknown-service")
            is_mig = any(k in str(cfg).lower() for k in ("migration", "ddl", "schema"))
            raw_events.append(
                TimelineEvent(
                    timestamp=ts,
                    event_type=TimelineEventType.DATABASE_MIGRATION if is_mig else TimelineEventType.CONFIG_CHANGE,
                    source=str(cfg.get("source") or "git://config"),
                    service=svc,
                    title=str(cfg.get("title") or ("Database Migration" if is_mig else "Config Change")),
                    description=str(cfg.get("description") or json.dumps(cfg, default=str)),
                    significance=EventSignificance.TRIGGERING_CHANGE,
                    evidence_ids=[str(cfg.get("evidence_id") or cfg.get("id") or "ev-cfg")],
                    metadata=dict(cfg),
                )
            )

        # 3. Ingest Metric Inflections & Amplifiers (e.g. Retry surges, IOPS/Throughput saturation)
        for inf in metric_inflections or []:
            ts = cls._parse_ts(inf.get("timestamp") or inf.get("inflection_time"))
            svc = str(inf.get("service") or "unknown-service")
            name = str(inf.get("metric_name") or "metric_inflection")
            pct = float(inf.get("percent_change", 0.0))
            is_retry = "retry" in name.lower()
            raw_events.append(
                TimelineEvent(
                    timestamp=ts,
                    event_type=TimelineEventType.RETRY_STORM_START if is_retry else TimelineEventType.METRIC_INFLECTION,
                    source=str(inf.get("source") or "prometheus://metrics"),
                    service=svc,
                    title=f"Metric Surge: {name}",
                    description=f"{name} shifted by {pct:+.1f}%: {inf.get('summary', '')}",
                    significance=EventSignificance.INTERMEDIATE_AMPLIFIER,
                    evidence_ids=[str(inf.get("evidence_id") or "ev-metric")],
                    metadata=dict(inf),
                )
            )

        # 4. Ingest Log Bursts & Probe Failures
        for log in log_bursts or []:
            ts = cls._parse_ts(log.get("timestamp") or log.get("first_seen"))
            svc = str(log.get("service") or "unknown-service")
            raw_events.append(
                TimelineEvent(
                    timestamp=ts,
                    event_type=TimelineEventType.LOG_ANOMALY_BURST,
                    source=str(log.get("source") or "opensearch://logs"),
                    service=svc,
                    title=f"Log Error Burst: {log.get('signature_pattern', 'Exception')[:60]}",
                    description=f"Observed {log.get('count', 1)} errors at rate {log.get('burst_rate_per_min', 0)}/min",
                    significance=EventSignificance.CORRELATED_METRIC,
                    evidence_ids=[str(log.get("evidence_id") or "ev-log")],
                    metadata=dict(log),
                )
            )

        # 5. Ingest Alerts (Primary Symptoms)
        for alt in alerts or []:
            ts = cls._parse_ts(alt.get("created_at") or alt.get("starts_at") or alt.get("timestamp"))
            svc = str(alt.get("service") or "unknown-service")
            raw_events.append(
                TimelineEvent(
                    timestamp=ts,
                    event_type=TimelineEventType.ALERT_TRIGGERED,
                    source=str(alt.get("source") or "alertmanager"),
                    service=svc,
                    title=f"Alert: {alt.get('name', 'IncidentAlert')}",
                    description=str(alt.get("description") or "Threshold breached"),
                    significance=EventSignificance.PRIMARY_SYMPTOM,
                    evidence_ids=[str(alt.get("evidence_id") or alt.get("id") or "ev-alert")],
                    metadata=dict(alt),
                )
            )

        # 6. Ingest Human / Operator Actions
        for act in human_actions or []:
            ts = cls._parse_ts(act.get("timestamp") or act.get("performed_at"))
            svc = str(act.get("service") or "operator")
            raw_events.append(
                TimelineEvent(
                    timestamp=ts,
                    event_type=TimelineEventType.HUMAN_ACTION,
                    source="audit://human_operator",
                    service=svc,
                    title=str(act.get("title") or "Operator Action"),
                    description=str(act.get("description") or json.dumps(act, default=str)),
                    significance=EventSignificance.MITIGATION_ATTEMPT,
                    evidence_ids=[str(act.get("evidence_id") or "ev-human")],
                    metadata=dict(act),
                )
            )

        # Sort strictly chronologically
        raw_events.sort(key=lambda e: e.timestamp)

        # Determine Primary Symptom & Triggering Change
        primary_symptom = next((e for e in raw_events if e.significance == EventSignificance.PRIMARY_SYMPTOM), None)
        triggering_change = next((e for e in raw_events if e.significance == EventSignificance.TRIGGERING_CHANGE), None)

        ref_time = (triggering_change or primary_symptom or raw_events[0]).timestamp if raw_events else datetime.now(UTC)

        narrative: list[str] = []
        for e in raw_events:
            delta_s = (e.timestamp - ref_time).total_seconds()
            e.delta_seconds_from_trigger = round(delta_s, 1)
            time_str = e.timestamp.strftime("%H:%M:%S")
            narrative.append(f"[{time_str}] ({e.event_type.value}) {e.service}: {e.title} -> {e.description}")

        win_start = raw_events[0].timestamp if raw_events else None
        win_end = raw_events[-1].timestamp if raw_events else None

        return IncidentTimeline(
            tenant_id=tenant_id,
            incident_id=incident_id,
            events=raw_events,
            sequence_narrative=narrative,
            triggering_change_event_id=triggering_change.event_id if triggering_change else None,
            primary_symptom_event_id=primary_symptom.event_id if primary_symptom else None,
            root_cause_window_start=win_start,
            root_cause_window_end=win_end,
        )

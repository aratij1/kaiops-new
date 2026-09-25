from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from common.metric_analyzer import MetricAnalyzer, MetricShape
from common.tenant_identity import require_tenant_id


class AbnormalPodDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    namespace: str
    phase: str
    restart_count: int = 0
    reason: str | None = None
    message: str | None = None
    exit_code: int | None = None
    node_name: str | None = None
    container_statuses: list[dict[str, Any]] = Field(default_factory=list)
    last_transition_time: str | None = None


class PodReductionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_pods_inspected: int
    healthy_pods_count: int
    abnormal_pods_count: int
    abnormal_pods: list[AbnormalPodDetail] = Field(default_factory=list)
    summarized_status: str
    provenance_source: str = "kubernetes://cluster"


class LogCluster(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signature_id: str
    signature_pattern: str
    sample_message: str
    count: int
    first_seen: str | None = None
    last_seen: str | None = None
    burst_rate_per_min: float = 0.0
    log_level: str = "ERROR"
    provenance_uri: str | None = None


class LogReductionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_lines_inspected: int
    unique_clusters_count: int
    top_clusters: list[LogCluster] = Field(default_factory=list)
    noise_filtered_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    anomaly_window_start: str | None = None
    anomaly_window_end: str | None = None
    provenance_source: str = "opensearch://logs"


class MetricSeriesReduction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_name: str
    data_points_count: int
    shape: MetricShape
    baseline_mean: float
    peak_value: float
    provisioned_ceiling: float | None = None
    peak_saturation_percent: float | None = None
    is_ceiling_breached: bool = False
    inflection_points_count: int = 0
    semantic_summary: str
    provenance_source: str = "prometheus://metrics"


class ReducedEvidencePackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["kaims.reduced-evidence.v1"] = "kaims.reduced-evidence.v1"
    package_id: UUID = Field(default_factory=uuid4)
    tenant_id: str
    target_service: str
    k8s_reduction: PodReductionResult | None = None
    log_reduction: LogReductionResult | None = None
    metric_reductions: list[MetricSeriesReduction] = Field(default_factory=list)
    original_payload_bytes: int
    reduced_payload_bytes: int
    reduction_ratio_percent: float
    reduced_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_identity(self) -> "ReducedEvidencePackage":
        require_tenant_id(self.tenant_id, source="reduced evidence package")
        return self


class PayloadReducer:
    """Context Engineering & Token Guard Layer (Solving the MCP Token Exhaustion Problem).

    Reduces massive diagnostic payloads (thousands of pods, multi-megabyte log streams,
    raw point-by-point time-series) into compact, structured findings while preserving
    abnormal evidence, correlations, and complete source provenance.
    """

    @staticmethod
    def reduce_k8s_pods(
        pods: list[dict[str, Any]],
        *,
        target_namespace: str | None = None,
        provenance_source: str = "kubernetes://cluster",
    ) -> PodReductionResult:
        total = len(pods)
        abnormal: list[AbnormalPodDetail] = []
        healthy_count = 0

        for pod in pods:
            ns = str(pod.get("namespace") or pod.get("metadata", {}).get("namespace") or "default")
            if target_namespace and ns != target_namespace:
                continue

            name = str(pod.get("name") or pod.get("metadata", {}).get("name") or "unknown-pod")
            status = pod.get("status") if isinstance(pod.get("status"), dict) else {}
            phase = str(status.get("phase") or pod.get("phase") or "Unknown")

            container_statuses = status.get("containerStatuses") or pod.get("container_statuses") or []
            restart_count = sum(int(cs.get("restartCount", cs.get("restart_count", 0))) for cs in container_statuses if isinstance(cs, dict))

            # Detect abnormal conditions
            is_abnormal = False
            reason = None
            message = None
            exit_code = None

            if phase not in {"Running", "Succeeded"}:
                is_abnormal = True
                reason = str(status.get("reason") or phase)

            for cs in container_statuses:
                if not isinstance(cs, dict):
                    continue
                state = cs.get("state", {})
                waiting = state.get("waiting", {})
                terminated = state.get("terminated", {})

                if waiting:
                    wait_reason = str(waiting.get("reason") or "Waiting")
                    if wait_reason in {"CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "CreateContainerConfigError"}:
                        is_abnormal = True
                        reason = wait_reason
                        message = waiting.get("message")
                if terminated:
                    term_exit = terminated.get("exitCode", terminated.get("exit_code"))
                    if term_exit and term_exit != 0:
                        is_abnormal = True
                        exit_code = int(term_exit)
                        reason = str(terminated.get("reason") or f"ExitCode:{term_exit}")
                        message = terminated.get("message")
                if not cs.get("ready", True) and phase == "Running":
                    is_abnormal = True
                    reason = reason or "UnreadyContainers"

            if restart_count > 3:
                is_abnormal = True
                reason = reason or f"HighRestarts({restart_count})"

            if is_abnormal:
                abnormal.append(
                    AbnormalPodDetail(
                        name=name,
                        namespace=ns,
                        phase=phase,
                        restart_count=restart_count,
                        reason=reason,
                        message=message,
                        exit_code=exit_code,
                        node_name=pod.get("spec", {}).get("nodeName") or pod.get("node_name"),
                        container_statuses=[dict(cs) for cs in container_statuses if isinstance(cs, dict)],
                        last_transition_time=str(status.get("startTime") or pod.get("created_at") or ""),
                    )
                )
            else:
                healthy_count += 1

        summary = f"Analyzed {total} pods: {healthy_count} healthy, {len(abnormal)} abnormal."
        return PodReductionResult(
            total_pods_inspected=total,
            healthy_pods_count=healthy_count,
            abnormal_pods_count=len(abnormal),
            abnormal_pods=abnormal,
            summarized_status=summary,
            provenance_source=provenance_source,
        )

    @staticmethod
    def reduce_logs(
        logs: list[dict[str, Any] | str],
        *,
        max_clusters: int = 10,
        provenance_source: str = "opensearch://logs",
    ) -> LogReductionResult:
        total = len(logs)
        if total == 0:
            return LogReductionResult(
                total_lines_inspected=0,
                unique_clusters_count=0,
                top_clusters=[],
                noise_filtered_ratio=1.0,
                provenance_source=provenance_source,
            )

        # Cluster storage: pattern -> {count, sample, first, last, level, uri}
        clusters: dict[str, dict[str, Any]] = {}
        all_timestamps: list[str] = []

        for entry in logs:
            if isinstance(entry, dict):
                raw_msg = str(entry.get("message") or entry.get("summary") or entry.get("content") or json.dumps(entry))
                level = str(entry.get("level") or entry.get("severity") or "ERROR").upper()
                ts = str(entry.get("timestamp") or entry.get("observed_at") or entry.get("@timestamp") or "")
                uri = str(entry.get("uri") or provenance_source)
            else:
                raw_msg = str(entry)
                level = "ERROR" if any(k in raw_msg.lower() for k in ("error", "exception", "fatal", "panic", "critical")) else "INFO"
                ts = ""
                uri = provenance_source

            if ts:
                all_timestamps.append(ts)

            # Normalization regex for signature clustering
            pattern = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<UUID>", raw_msg, flags=re.IGNORECASE)
            pattern = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?\b", "<IP_PORT>", pattern)
            pattern = re.sub(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?\b", "<TIMESTAMP>", pattern)
            pattern = re.sub(r"\b0x[0-9a-fA-F]+\b", "<HEX>", pattern)
            pattern = re.sub(r"\b[0-9a-f]{20,64}\b", "<HASH>", pattern)
            pattern = re.sub(r"\b\d+\b", "<NUM>", pattern)
            pattern = re.sub(r"\s+", " ", pattern).strip()

            if pattern not in clusters:
                sig_id = f"sig-{abs(hash(pattern)) % 1000000:06d}"
                clusters[pattern] = {
                    "signature_id": sig_id,
                    "signature_pattern": pattern,
                    "sample_message": raw_msg[:300],
                    "count": 1,
                    "first_seen": ts or None,
                    "last_seen": ts or None,
                    "log_level": level,
                    "provenance_uri": uri,
                }
            else:
                clusters[pattern]["count"] += 1
                if ts:
                    clusters[pattern]["last_seen"] = ts
                    if not clusters[pattern]["first_seen"]:
                        clusters[pattern]["first_seen"] = ts

        sorted_clusters = sorted(clusters.values(), key=lambda c: c["count"], reverse=True)
        top = [
            LogCluster(
                signature_id=c["signature_id"],
                signature_pattern=c["signature_pattern"],
                sample_message=c["sample_message"],
                count=c["count"],
                first_seen=c["first_seen"],
                last_seen=c["last_seen"],
                burst_rate_per_min=round(float(c["count"]) / 5.0, 2),  # approx 5 min window
                log_level=c["log_level"],
                provenance_uri=c["provenance_uri"],
            )
            for c in sorted_clusters[:max_clusters]
        ]

        noise_ratio = max(0.0, 1.0 - (len(top) / max(total, 1)))
        all_timestamps.sort()

        return LogReductionResult(
            total_lines_inspected=total,
            unique_clusters_count=len(clusters),
            top_clusters=top,
            noise_filtered_ratio=round(noise_ratio, 4),
            anomaly_window_start=all_timestamps[0] if all_timestamps else None,
            anomaly_window_end=all_timestamps[-1] if all_timestamps else None,
            provenance_source=provenance_source,
        )

    @staticmethod
    def reduce_metrics(
        values: list[float],
        *,
        metric_name: str,
        timestamps: list[str] | None = None,
        ceiling: float | None = None,
        provenance_source: str = "prometheus://metrics",
    ) -> MetricSeriesReduction:
        report = MetricAnalyzer.analyze_series(
            values=values,
            timestamps=timestamps,
            metric_name=metric_name,
            ceiling=ceiling,
        )

        peak_saturation = report.ceiling_analysis.peak_percent_of_ceiling if report.ceiling_analysis else None
        is_breached = report.ceiling_analysis.is_breached if report.ceiling_analysis else False

        return MetricSeriesReduction(
            metric_name=metric_name,
            data_points_count=report.data_points,
            shape=report.shape,
            baseline_mean=report.baseline_mean,
            peak_value=report.peak_value,
            provisioned_ceiling=ceiling,
            peak_saturation_percent=peak_saturation,
            is_ceiling_breached=is_breached,
            inflection_points_count=len(report.inflection_points),
            semantic_summary=report.semantic_summary,
            provenance_source=provenance_source,
        )

    @classmethod
    def build_reduced_context_package(
        cls,
        *,
        tenant_id: str,
        target_service: str,
        raw_k8s_pods: list[dict[str, Any]] | None = None,
        raw_logs: list[dict[str, Any] | str] | None = None,
        raw_metrics: dict[str, list[float]] | None = None,
        metric_ceilings: dict[str, float] | None = None,
    ) -> ReducedEvidencePackage:
        require_tenant_id(tenant_id, source="build reduced context package")
        metric_ceilings = metric_ceilings or {}

        # 1. K8s Pods
        k8s_res = cls.reduce_k8s_pods(raw_k8s_pods) if raw_k8s_pods is not None else None

        # 2. Logs
        log_res = cls.reduce_logs(raw_logs) if raw_logs is not None else None

        # 3. Metrics
        metric_res: list[MetricSeriesReduction] = []
        if raw_metrics:
            for m_name, vals in raw_metrics.items():
                ceil = metric_ceilings.get(m_name)
                metric_res.append(cls.reduce_metrics(vals, metric_name=m_name, ceiling=ceil))

        # Calculate payload byte sizes
        raw_obj = {
            "pods": raw_k8s_pods or [],
            "logs": raw_logs or [],
            "metrics": raw_metrics or {},
        }
        orig_bytes = len(json.dumps(raw_obj, default=str).encode("utf-8"))

        reduced_dict = {
            "k8s": k8s_res.model_dump(mode="json") if k8s_res else None,
            "logs": log_res.model_dump(mode="json") if log_res else None,
            "metrics": [m.model_dump(mode="json") for m in metric_res],
        }
        red_bytes = len(json.dumps(reduced_dict, default=str).encode("utf-8"))
        reduction_ratio = max(0.0, (1.0 - (red_bytes / max(orig_bytes, 1))) * 100.0)

        return ReducedEvidencePackage(
            tenant_id=tenant_id,
            target_service=target_service,
            k8s_reduction=k8s_res,
            log_reduction=log_res,
            metric_reductions=metric_res,
            original_payload_bytes=orig_bytes,
            reduced_payload_bytes=red_bytes,
            reduction_ratio_percent=round(reduction_ratio, 2),
        )

from __future__ import annotations

import math
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class MetricShape(StrEnum):
    STABLE = "STABLE"
    MONOTONIC_INCREASE = "MONOTONIC_INCREASE"
    STEP_SPIKE = "STEP_SPIKE"
    DECAY = "DECAY"
    OSCILLATING = "OSCILLATING"
    BURST = "BURST"


class InflectionPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    timestamp: str | None = None
    value_before: float
    value_after: float
    magnitude_change: float
    percent_change: float


class CeilingAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric_name: str
    provisioned_ceiling: float
    peak_value: float
    peak_percent_of_ceiling: float
    is_breached: bool
    breach_duration_samples: int = 0


class MetricSeriesReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["kaims.metric-analysis.v1"] = "kaims.metric-analysis.v1"
    analysis_id: UUID = Field(default_factory=uuid4)
    metric_name: str
    shape: MetricShape
    sample_count: int
    baseline_mean: float
    baseline_std: float
    min_value: float
    max_value: float
    latest_value: float
    inflection_points: list[InflectionPoint] = Field(default_factory=list)
    ceiling_analysis: CeilingAnalysis | None = None
    semantic_summary: str
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MetricAnalyzer:
    """Pre-computes mathematical time-series shapes, step-changes, and quota breaches.

    Avoids dumping raw float arrays into LLM context windows (the MCP Problem),
    converting noisy numerical metrics into concise, mathematically verified causal summaries.
    """

    @staticmethod
    def analyze_series(
        values: list[float],
        timestamps: list[str] | None = None,
        *,
        metric_name: str = "metric",
        ceiling: float | None = None,
    ) -> MetricSeriesReport:
        if not values:
            return MetricSeriesReport(
                metric_name=metric_name,
                shape=MetricShape.STABLE,
                sample_count=0,
                baseline_mean=0.0,
                baseline_std=0.0,
                min_value=0.0,
                max_value=0.0,
                latest_value=0.0,
                semantic_summary=f"{metric_name}: No samples available.",
            )

        n = len(values)
        mean_val = sum(values) / n
        variance = sum((x - mean_val) ** 2 for x in values) / n if n > 1 else 0.0
        std_val = math.sqrt(variance)
        min_val = min(values)
        max_val = max(values)
        latest_val = values[-1]

        # Detect Inflection Points (consecutive jump >= 50% or exceeding std_val)
        inflections: list[InflectionPoint] = []
        for i in range(1, n):
            before = values[i - 1]
            after = values[i]
            diff = after - before
            denom = abs(before) if abs(before) > 1e-6 else 1e-6
            pct = (diff / denom) * 100.0
            if abs(pct) >= 50.0 or (std_val > 0 and abs(diff) >= std_val):
                ts = timestamps[i] if timestamps and i < len(timestamps) else f"sample-{i}"
                inflections.append(
                    InflectionPoint(
                        index=i,
                        timestamp=ts,
                        value_before=round(before, 2),
                        value_after=round(after, 2),
                        magnitude_change=round(diff, 2),
                        percent_change=round(pct, 1),
                    )
                )

        # Classify Shape
        if n < 3:
            shape = MetricShape.STABLE
        else:
            diffs = [values[i] - values[i - 1] for i in range(1, n)]
            increasing = sum(1 for d in diffs if d > 0)
            decreasing = sum(1 for d in diffs if d < 0)

            if inflections and any(abs(inf.percent_change) >= 100 for inf in inflections):
                shape = MetricShape.STEP_SPIKE
            elif increasing >= (n - 1) * 0.75:
                shape = MetricShape.MONOTONIC_INCREASE
            elif decreasing >= (n - 1) * 0.75:
                shape = MetricShape.DECAY
            elif std_val < (mean_val * 0.10 if mean_val > 0 else 0.1):
                shape = MetricShape.STABLE
            else:
                shape = MetricShape.OSCILLATING

        # Ceiling & Saturation Analysis
        ceiling_data: CeilingAnalysis | None = None
        if ceiling is not None and ceiling > 0:
            peak_pct = (max_val / ceiling) * 100.0
            breached_count = sum(1 for v in values if v >= ceiling)
            ceiling_data = CeilingAnalysis(
                metric_name=metric_name,
                provisioned_ceiling=round(ceiling, 2),
                peak_value=round(max_val, 2),
                peak_percent_of_ceiling=round(peak_pct, 1),
                is_breached=breached_count > 0,
                breach_duration_samples=breached_count,
            )

        # Generate semantic summary
        summary_parts = [
            f"{metric_name} exhibited {shape.value} behavior across {n} data points.",
            f"Baseline: {mean_val:.1f} (std={std_val:.1f}), ranging from {min_val:.1f} to {max_val:.1f}.",
        ]

        if ceiling_data:
            if ceiling_data.is_breached:
                summary_parts.append(
                    f"CRITICAL: Breached provisioned ceiling of {ceiling:.1f} at peak {max_val:.1f} "
                    f"({ceiling_data.peak_percent_of_ceiling:.1f}% saturation across {ceiling_data.breach_duration_samples} samples)."
                )
            else:
                summary_parts.append(
                    f"Headroom safe: Peak reached {max_val:.1f} vs ceiling {ceiling:.1f} "
                    f"({ceiling_data.peak_percent_of_ceiling:.1f}% of ceiling, {100 - ceiling_data.peak_percent_of_ceiling:.1f}% headroom remaining)."
                )

        if inflections:
            first_inf = inflections[0]
            summary_parts.append(
                f"Significant step inflection at {first_inf.timestamp or f'index {first_inf.index}'}: "
                f"{first_inf.value_before} -> {first_inf.value_after} ({first_inf.percent_change:+.1f}%)."
            )

        return MetricSeriesReport(
            metric_name=metric_name,
            shape=shape,
            sample_count=n,
            baseline_mean=round(mean_val, 3),
            baseline_std=round(std_val, 3),
            min_value=round(min_val, 3),
            max_value=round(max_val, 3),
            latest_value=round(latest_val, 3),
            inflection_points=inflections,
            ceiling_analysis=ceiling_data,
            semantic_summary=" ".join(summary_parts),
        )

    @staticmethod
    def correlate_storage_vs_iops(
        *,
        iops_values: list[float],
        iops_ceiling: float,
        throughput_mb_values: list[float],
        throughput_ceiling_mb: float,
        timestamps: list[str] | None = None,
    ) -> str:
        """Deep-dive case study from Sherlocks.ai Page 11:

        Determines whether a storage throttling alert was caused by IOPS starvation
        or raw throughput (MB/s) ceiling exhaustion.
        """
        iops_rep = MetricAnalyzer.analyze_series(
            iops_values, timestamps, metric_name="Storage IOPS", ceiling=iops_ceiling
        )
        tp_rep = MetricAnalyzer.analyze_series(
            throughput_mb_values, timestamps, metric_name="Storage Throughput (MB/s)", ceiling=throughput_ceiling_mb
        )

        iops_pct = iops_rep.ceiling_analysis.peak_percent_of_ceiling if iops_rep.ceiling_analysis else 0.0
        tp_pct = tp_rep.ceiling_analysis.peak_percent_of_ceiling if tp_rep.ceiling_analysis else 0.0

        if tp_pct >= 100.0 and iops_pct < 80.0:
            return (
                f"Storage Throttling Root Cause Identified: "
                f"Write throughput breached the {throughput_ceiling_mb} MB/s ceiling at {tp_rep.max_value} MB/s ({tp_pct:.1f}% saturation), "
                f"while IOPS remained comfortably low at {iops_rep.max_value} / {iops_ceiling} ({iops_pct:.1f}% saturation). "
                f"Culprit is large block size data transfer (e.g. unbuffered backup/dump or bulk writes), not high IOPS query rates."
            )

        if iops_pct >= 100.0 and tp_pct < 80.0:
            return (
                f"Storage Throttling Root Cause Identified: "
                f"IOPS limit breached at {iops_rep.max_value} ops/sec ({iops_pct:.1f}% saturation), "
                f"while bandwidth remained low at {tp_rep.max_value} MB/s ({tp_pct:.1f}% saturation). "
                f"Culprit is small random I/O operations (e.g. unindexed table scans or lock lookups)."
            )

        return (
            f"Storage Throttling Analysis: IOPS peak {iops_pct:.1f}% saturation, "
            f"Throughput peak {tp_pct:.1f}% saturation. Both metrics contributed to storage pressure."
        )

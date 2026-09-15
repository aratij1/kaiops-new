from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence


def unattempted_requirement_connector(
    requirement: Any,
    authorized: Iterable[str] | set[str] | Sequence[str],
    jobs: list[dict[str, Any]] | None = None,
) -> str | None:
    """Return the next authorized connector candidate for a requirement that has not been attempted yet."""
    auth_set = {str(c).strip().lower() for c in (authorized or []) if c}
    candidates = getattr(requirement, "candidate_connectors", None) or []
    if isinstance(candidates, str):
        candidates = [candidates]

    attempted: set[str] = set()
    req_id = str(getattr(requirement, "requirement_id", "") or getattr(requirement, "id", "")).strip()

    if jobs:
        for job in jobs:
            job_req_id = str(job.get("requirement_id") or "").strip()
            if not req_id or job_req_id == req_id:
                cid = str(job.get("connector_id") or "").strip().lower()
                if cid:
                    attempted.add(cid)

    for cand in candidates:
        cand_norm = str(cand).strip().lower()
        if cand_norm in auth_set and cand_norm not in attempted:
            return cand_norm
    return None


def collection_attempt_limit(connector: str | Any = None) -> int:
    """Return the maximum number of enrichment collection attempts allowed per connector."""
    return 3


def investigation_gaps(
    rca_analysis: dict[str, Any] | None,
    investigation_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Extract or synthesize missing evidence gaps for an RCA investigation."""
    gaps: list[dict[str, Any]] = []
    if isinstance(rca_analysis, dict):
        raw_gaps = rca_analysis.get("missing_evidence") or rca_analysis.get("investigation_gaps")
        if isinstance(raw_gaps, list):
            for item in raw_gaps:
                if isinstance(item, dict):
                    gaps.append(item)
                elif isinstance(item, str) and item.strip():
                    gaps.append({"question": item.strip(), "category": "context"})
    if not gaps and isinstance(investigation_report, dict):
        raw_report_gaps = investigation_report.get("missing_evidence") or investigation_report.get("gaps")
        if isinstance(raw_report_gaps, list):
            for item in raw_report_gaps:
                if isinstance(item, dict):
                    gaps.append(item)
                elif isinstance(item, str) and item.strip():
                    gaps.append({"question": item.strip(), "category": "context"})
    return gaps


def blocking_investigation_gaps(
    rca_analysis: dict[str, Any] | None,
    investigation_report: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return missing evidence items that block conclusive RCA resolution."""
    gaps = investigation_gaps(rca_analysis, investigation_report)
    return gaps


def requirement_blocks_recollection(requirement_row: dict[str, Any], rca_version: int = 1) -> bool:
    """Determine whether an existing context evidence requirement row should block fresh recollection."""
    if not isinstance(requirement_row, dict):
        return True
    status = str(requirement_row.get("status") or "").strip().lower()
    if status in {"completed", "satisfied", "in_progress", "collecting"}:
        row_version = requirement_row.get("rca_version")
        if row_version is not None:
            try:
                if int(row_version) >= int(rca_version):
                    return True
            except (ValueError, TypeError):
                pass
        return True
    return False


def incident_collection_window(
    alert: Any,
    reference_time: datetime | None = None,
    lookback_minutes: int = 60,
    lookahead_minutes: int = 15,
) -> tuple[datetime, datetime]:
    """Calculate the [start, end] context collection timestamp window for an alert/incident."""
    base_time = None
    if alert is not None:
        base_time = getattr(alert, "created_at", None) or getattr(alert, "timestamp", None)
        if isinstance(base_time, str):
            try:
                base_time = datetime.fromisoformat(base_time.replace("Z", "+00:00"))
            except Exception:
                base_time = None
    if base_time is None:
        base_time = reference_time or datetime.now(timezone.utc)
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)

    window_start = base_time - timedelta(minutes=lookback_minutes)
    window_end = base_time + timedelta(minutes=lookahead_minutes)
    return window_start, window_end

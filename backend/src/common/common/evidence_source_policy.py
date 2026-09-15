from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_TIMESTAMP_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\b"
)

_ALERT_FILE_PATTERNS = (
    "alert_",
    "alerts_",
    "alert-",
    "alerts-",
    "alert.json",
    "alerts.json",
    "email_ingestion_state.json",
    "jira_admission_state.json",
)

_ALERT_DIR_PATTERNS = (
    "ingested_alerts",
    "alert_fixtures",
    "fixtures/alerts",
    "fixtures\\alerts",
)


def is_alert_artifact_reference(path: str | Path) -> bool:
    """Return True if path references an alert payload or alert state file rather than an operational log."""
    path_str = str(path).lower()
    name = Path(path).name.lower()
    if any(dir_pat in path_str for dir_pat in _ALERT_DIR_PATTERNS):
        return True
    if any(name.startswith(pat) or name == pat for pat in _ALERT_FILE_PATTERNS):
        return True
    return False


def is_alert_artifact(raw: Any) -> bool:
    """Return True if the evidence record / dict represents an alert artifact instead of an operational log."""
    if not isinstance(raw, dict):
        return False
    if raw.get("is_alert_artifact") is True:
        return True
    source_ref = str(
        raw.get("source_reference")
        or raw.get("source_uri")
        or raw.get("citation")
        or raw.get("uri")
        or raw.get("path")
        or ""
    ).strip()
    if source_ref and is_alert_artifact_reference(source_ref):
        return True
    # If dict has explicit alert payload markers
    if "fingerprint" in raw and ("severity" in raw or "alert_name" in raw or "status" in raw):
        if not raw.get("log_message") and not raw.get("message") and "labels" in raw and isinstance(raw["labels"], dict):
            return True
    return False


def log_observed_at(text: str | Any) -> str | None:
    """Extract an observed timestamp string from a log line or snippet if present."""
    if not isinstance(text, str):
        return None
    match = _TIMESTAMP_RE.search(text)
    if match:
        return match.group(1).replace(" ", "T")
    return None

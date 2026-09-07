"""Regression coverage for a real, live-reproduced production failure.

`_require_catalog_readiness` (the gate in front of both
/resolution-catalog/relevant and /resolution-catalog/select) computed
"is this investigation conclusive?" by reading `metadata["investigation_report"]`
-- a coverage/crawl-steps summary that has never carried `conclusive` or
`status` fields. The actual investigator verdict (IterativeInvestigator's
conclusive/status/outcome) lives under `metadata["iterative_investigation"]`.
This meant `investigation.get("conclusive")` was permanently `None` for
every incident in the system's history, so every single recommendation --
no matter how well-grounded -- was rejected as "investigation is not
conclusive", and /resolution-catalog/select could never succeed for any
incident, ever. Confirmed live: incident 417fc764acf342b1bdc8e815d18e8f1f's
rca_version 10 had `iterative_investigation.conclusive == True` and
`.status == "conclusive"` (IterativeInvestigator genuinely corroborated its
leading hypothesis and stopped), yet `investigation_report` has no such keys
at all -- so the pre-fix code always rejected it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Every service in this repo names its FastAPI entrypoint module `app.py`, so
# a plain `import app` would silently bind to whichever service's `app.py`
# another test module already cached under `sys.modules["app"]` in the same
# pytest session. Load resolution-agent's module explicitly, under its own
# name, to avoid that collision.
RESOLUTION_AGENT_SRC = Path(__file__).resolve().parents[2] / "ai-workbench" / "src" / "resolution-agent"
if str(RESOLUTION_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(RESOLUTION_AGENT_SRC))

if "resolution_agent_app" in sys.modules:
    _resolution_agent_app = sys.modules["resolution_agent_app"]
else:
    _spec = importlib.util.spec_from_file_location("resolution_agent_app", RESOLUTION_AGENT_SRC / "app.py")
    _resolution_agent_app = importlib.util.module_from_spec(_spec)
    sys.modules["resolution_agent_app"] = _resolution_agent_app
    _spec.loader.exec_module(_resolution_agent_app)

_investigation_readiness_blocks = _resolution_agent_app._investigation_readiness_blocks


def _grounded_metadata(*, iterative_investigation: dict | None, investigation_report: dict | None) -> dict:
    metadata = {
        "rca_status": "grounded",
        "evidence_ids": ["TRACE-1"],
        "rca_analysis": {"evidence_used": ["TRACE-1"], "missing_evidence": [], "conflicting_evidence": []},
    }
    if iterative_investigation is not None:
        metadata["iterative_investigation"] = iterative_investigation
    if investigation_report is not None:
        metadata["investigation_report"] = investigation_report
    return metadata


def test_conclusive_iterative_investigation_is_not_blocked_even_without_a_matching_investigation_report() -> None:
    """The exact shape real recommendations actually carry: `investigation_report`
    exists (coverage/crawl-steps) but has no conclusive/status keys, while
    `iterative_investigation` (the real verdict) says conclusive.
    """
    metadata = _grounded_metadata(
        iterative_investigation={"conclusive": True, "status": "conclusive", "outcome": "EVIDENCE_SUPPORTED"},
        investigation_report={
            "schema_version": "kaims.resolution-investigation.v1",
            "coverage": {"logs": 9, "code": 14},
            "missing_sources": ["history", "changes"],
        },
    )
    assert _investigation_readiness_blocks(metadata) == []


def test_inconclusive_iterative_investigation_is_still_blocked() -> None:
    metadata = _grounded_metadata(
        iterative_investigation={"conclusive": False, "status": "insufficient_evidence"},
        investigation_report={"coverage": {}},
    )
    assert "investigation is not conclusive" in _investigation_readiness_blocks(metadata)


def test_missing_iterative_investigation_falls_back_to_investigation_report() -> None:
    """Legacy/historical recommendations that predate `iterative_investigation`
    must keep working off `investigation_report` exactly as before.
    """
    metadata = _grounded_metadata(
        iterative_investigation=None,
        investigation_report={"conclusive": True, "status": "conclusive"},
    )
    assert _investigation_readiness_blocks(metadata) == []


def test_neither_field_present_is_blocked() -> None:
    metadata = _grounded_metadata(iterative_investigation=None, investigation_report=None)
    assert "investigation is not conclusive" in _investigation_readiness_blocks(metadata)


def test_declared_evidence_gaps_still_block_a_conclusive_investigation() -> None:
    """The conclusiveness fix must not paper over a genuine, separate gap:
    an investigation can be conclusive (the investigator stopped, confident
    in its leading hypothesis) while still self-declaring evidence it could
    not corroborate -- that must keep blocking catalog selection.
    """
    metadata = _grounded_metadata(
        iterative_investigation={"conclusive": True, "status": "conclusive"},
        investigation_report=None,
    )
    metadata["rca_analysis"]["missing_evidence"] = ["Dependency health metrics confirming the failure."]
    blocks = _investigation_readiness_blocks(metadata)
    assert "declared evidence gaps remain" in blocks
    assert "investigation is not conclusive" not in blocks

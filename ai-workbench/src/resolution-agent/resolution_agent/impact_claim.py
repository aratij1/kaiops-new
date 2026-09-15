from __future__ import annotations

import hashlib
from typing import Any

from resolution_agent.contracts import ClaimKind, ClaimStatus, EvidenceBoundClaim


def _claim_id(kind: ClaimKind, statement: str) -> str:
    digest = hashlib.sha256(f"{kind.value}:{statement.strip().casefold()}".encode()).hexdigest()[:20]
    return f"claim-{kind.value.lower()}-{digest}"


def evaluated_impact_claim(
    impact_analysis: dict[str, Any] | None,
    impact_text: str | None,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build an auditable EvidenceBoundClaim for the evaluated impact of an incident."""
    analysis = impact_analysis if isinstance(impact_analysis, dict) else {}
    evidence_list = evidence or []
    statement = str(
        impact_text
        or analysis.get("statement")
        or analysis.get("impact_statement")
        or "Observed alert symptom requires customer/business impact confirmation."
    ).strip()

    available_evidence_ids = {
        str(item.get("evidence_id"))
        for item in evidence_list
        if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
    }
    raw_support = analysis.get("supporting_evidence_ids") or analysis.get("evidence_ids") or []
    supporting_ids = [str(eid) for eid in raw_support if str(eid) in available_evidence_ids]

    if supporting_ids:
        status = ClaimStatus.GROUNDED
        limitations = []
    elif analysis.get("observed") is True or analysis.get("status") == "OBSERVED":
        status = ClaimStatus.OBSERVED
        limitations = ["Impact observed in telemetry but not fully corroborated across independent business indicators."]
    else:
        status = ClaimStatus.NOT_ESTABLISHED
        limitations = ["An alert signal is not proof of customer or business impact."]

    claim = EvidenceBoundClaim(
        claim_id=_claim_id(ClaimKind.IMPACT, statement),
        kind=ClaimKind.IMPACT,
        status=status,
        statement=statement,
        supporting_evidence_ids=supporting_ids,
        falsification_test=(
            "Collect direct SLO, availability, transaction, support-ticket, or customer-impact evidence "
            "for the incident window."
        ),
        limitations=limitations,
    )
    return claim.model_dump(mode="json")

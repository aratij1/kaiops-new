import pytest
from common.incident_command_contract import build_incident_command_workspace
from pydantic import ValidationError


def test_command_workspace_composes_matching_read_models() -> None:
    workspace = build_incident_command_workspace(
        incident_id="incident-1",
        incident={"incident_id": "incident-1", "updated_at": "2026-09-01T10:00:00Z"},
        operations={"incident_id": "incident-1", "lifecycle_version": 7},
    )

    assert workspace.schema_version == "kaiops.incident-command.v2"
    assert workspace.incident["incident_id"] == "incident-1"
    assert workspace.operations["lifecycle_version"] == 7
    assert len(workspace.revision) == 64


def test_command_workspace_owns_evidence_scores_and_binding_blockers() -> None:
    workspace = build_incident_command_workspace(
        incident_id="incident-1",
        incident={"incident_id": "incident-1"},
        operations={
            "incident_id": "incident-1",
            "context": {"snapshot_id": "snapshot-new", "quality": {"quality_score": 0.82}},
            "investigation_workspace": {
                "binding": {"context_snapshot_id": "snapshot-bound"},
                "evidence_summary": {
                    "latest_context_records": 12,
                    "bound_snapshot_records": 10,
                    "rca_bound_records": 5,
                    "traceable_citations": 4,
                    "unresolved_bindings": 1,
                },
                "rca": {"status": "investigating", "conflicting_evidence": ["conflict"]},
                "requirements": [{"status": "collecting"}, {"status": "resolved"}],
                "resolution": {"status": "blocked"},
            },
        },
    )

    assert workspace.evidence.counts.latest_context_records == 12
    assert workspace.evidence.counts.open_requirements == 1
    assert workspace.evidence.counts.open_conflicts == 1
    assert workspace.evidence.binding_consistent is False
    assert workspace.evidence.scores[0].percent == 82
    assert workspace.evidence.scores[1].ratio is not None
    assert workspace.evidence.scores[1].ratio.percent == 80
    assert "RCA_SNAPSHOT_STALE" in workspace.evidence.blockers
    assert "RCA_EVIDENCE_BINDING_UNRESOLVED" in workspace.evidence.blockers
    assert "RCA_NOT_GROUNDED" in workspace.evidence.blockers
    assert "RESOLUTION_NOT_READY" in workspace.evidence.blockers
    assert workspace.evidence.scores[2].status == "blocked"


def test_command_workspace_flags_exhausted_evidence_collection() -> None:
    workspace = build_incident_command_workspace(
        incident_id="incident-1",
        incident={"incident_id": "incident-1"},
        operations={
            "incident_id": "incident-1",
            "investigation_workspace": {
                "requirements": [
                    {"status": "blocked"},
                    {"status": "assignment_blocked"},
                    {"status": "collected"},
                ],
            },
        },
    )

    # Both open requirements have dead-ended (retry budget exhausted, no
    # authorized human responder) - nothing is still in flight, so the
    # operator can be offered a partial-evidence recommendation instead of
    # an indefinite "not ready" with no path forward.
    assert workspace.evidence.counts.open_requirements == 2
    assert workspace.evidence.counts.exhausted_requirements == 2
    assert workspace.evidence.counts.pending_requirements == 0
    assert workspace.evidence.evidence_collection_exhausted is True


def test_command_workspace_evidence_collection_not_exhausted_while_pending() -> None:
    workspace = build_incident_command_workspace(
        incident_id="incident-1",
        incident={"incident_id": "incident-1"},
        operations={
            "incident_id": "incident-1",
            "investigation_workspace": {
                "requirements": [
                    {"status": "blocked"},
                    {"status": "human_requested"},
                ],
            },
        },
    )

    # One requirement is still waiting on a human response - collection is
    # not exhausted yet, so this must not be offered as operator-reviewable.
    assert workspace.evidence.counts.exhausted_requirements == 1
    assert workspace.evidence.counts.pending_requirements == 1
    assert workspace.evidence.evidence_collection_exhausted is False


def test_command_workspace_no_open_requirements_is_not_exhausted() -> None:
    workspace = build_incident_command_workspace(
        incident_id="incident-1",
        incident={"incident_id": "incident-1"},
        operations={
            "incident_id": "incident-1",
            "investigation_workspace": {"requirements": [{"status": "collected"}]},
        },
    )

    # No declared gaps at all is a different, better state than "gaps exist
    # but we gave up" - it must not be reported as evidence_collection_exhausted.
    assert workspace.evidence.counts.open_requirements == 0
    assert workspace.evidence.evidence_collection_exhausted is False


def test_command_workspace_rejects_mixed_incident_identity() -> None:
    with pytest.raises(ValidationError, match="operations identity does not match"):
        build_incident_command_workspace(
            incident_id="incident-1",
            incident={"incident_id": "incident-1"},
            operations={"incident_id": "incident-2"},
        )


def test_command_workspace_revision_changes_with_lifecycle_version() -> None:
    first = build_incident_command_workspace(
        incident_id="incident-1",
        incident={"incident_id": "incident-1", "updated_at": "2026-09-01T10:00:00Z"},
        operations={"incident_id": "incident-1", "lifecycle_version": 7},
    )
    second = build_incident_command_workspace(
        incident_id="incident-1",
        incident={"incident_id": "incident-1", "updated_at": "2026-09-01T10:00:00Z"},
        operations={"incident_id": "incident-1", "lifecycle_version": 8},
    )

    assert first.revision != second.revision


def test_command_deduplicates_projection_without_changing_source_evidence():
    import copy
    context = {"metadata": {"evidence": [{"id": "e1", "value": "x" * 10000}]}}
    recommendation = {"root_cause": "Recorded hypothesis"}
    incident = {
        "incident_id": "incident-1", "context": context,
        "recommendation": recommendation,
        "projection_payload": {
            "context": copy.deepcopy(context), "context_metadata": copy.deepcopy(context["metadata"]),
            "recommendation": copy.deepcopy(recommendation), "status": "closed",
            "incident_lifecycle": {"assessment_id": "assessment-1"},
        },
    }
    original = copy.deepcopy(incident)
    command = build_incident_command_workspace(
        incident_id="incident-1", incident=incident, operations={"incident_id": "incident-1"},
    )
    assert incident == original
    assert command.incident["context"] == context
    assert command.incident["recommendation"] == recommendation
    assert command.incident["projection_payload"] == {
        "status": "closed", "incident_lifecycle": {"assessment_id": "assessment-1"},
    }


def test_command_preserves_distinct_and_projection_only_evidence():
    incident = {
        "incident_id": "incident-1", "context": {"metadata": {"version": 2}},
        "projection_payload": {
            "context": {"metadata": {"version": 1}}, "context_metadata": {"version": 1},
            "recommendation": {"root_cause": "Historical hypothesis"},
        },
    }
    command = build_incident_command_workspace(
        incident_id="incident-1", incident=incident, operations={"incident_id": "incident-1"},
    )
    assert command.incident == incident


def test_command_workspace_accepts_hyphenated_uuid() -> None:
    incident_uuid_hyphenated = "f874ad68-4265-4904-a3d5-23ab41b4d4c7"
    workspace = build_incident_command_workspace(
        incident_id=incident_uuid_hyphenated,
        incident={"id": incident_uuid_hyphenated, "status": "investigating"},
        operations={"incident_id": incident_uuid_hyphenated, "lifecycle_state": "RCA_READY"},
    )
    assert workspace.incident_id == incident_uuid_hyphenated
    assert workspace.incident["id"] == incident_uuid_hyphenated
    assert workspace.operations["incident_id"] == incident_uuid_hyphenated


def test_command_workspace_normalizes_32_char_hex_uuid_to_same_incident() -> None:
    incident_uuid_hyphenated = "f874ad68-4265-4904-a3d5-23ab41b4d4c7"
    incident_uuid_hex = "f874ad6842654904a3d523ab41b4d4c7"

    workspace_hyphenated = build_incident_command_workspace(
        incident_id=incident_uuid_hyphenated,
        incident={"id": incident_uuid_hyphenated, "status": "investigating"},
        operations={"incident_id": incident_uuid_hyphenated, "lifecycle_state": "RCA_READY"},
    )
    workspace_hex = build_incident_command_workspace(
        incident_id=incident_uuid_hex,
        incident={"id": incident_uuid_hyphenated, "status": "investigating"},
        operations={"incident_id": incident_uuid_hyphenated, "lifecycle_state": "RCA_READY"},
    )

    assert workspace_hex.incident_id == incident_uuid_hyphenated
    assert workspace_hex.revision == workspace_hyphenated.revision
    assert workspace_hex.model_dump(mode="json") == workspace_hyphenated.model_dump(mode="json")


def test_command_workspace_rejects_invalid_or_mismatched_uuid() -> None:
    incident_uuid_1 = "f874ad68-4265-4904-a3d5-23ab41b4d4c7"
    incident_uuid_2 = "e763ac57-3154-4803-92c4-12ba30a3c3b6"

    with pytest.raises(ValidationError, match="operations identity does not match"):
        build_incident_command_workspace(
            incident_id=incident_uuid_1,
            incident={"id": incident_uuid_1},
            operations={"incident_id": incident_uuid_2},
        )

    with pytest.raises(ValidationError, match="incident projection identity does not match"):
        build_incident_command_workspace(
            incident_id=incident_uuid_1,
            incident={"id": incident_uuid_2},
            operations={"incident_id": incident_uuid_1},
        )

    with pytest.raises(ValidationError, match="incident projection identity does not match"):
        build_incident_command_workspace(
            incident_id="invalid-uuid-token",
            incident={"id": "different-token"},
            operations={"incident_id": "invalid-uuid-token"},
        )

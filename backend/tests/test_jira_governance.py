from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from common.context_enrichment_contract import (
    EvidenceRequirement,
    HitlJiraRequest,
    HitlRoutingConfiguration,
    HumanEvidenceJiraRequest,
    TicketClosurePolicy,
)
from common.database import (
    ApplicationRecord,
    ExecutionPlanRecord,
    IncidentInvestigationBindingRecord,
    IncidentProjectionRecord,
    OnboardingControlPlaneRecord,
)
from common.hitl_routing import resolve_hitl_assignee
from common.jira_governance import (
    governed_jira_action,
    jira_webhook_event_id,
    kaims_may_close_ticket,
    validate_jira_approval,
)
from common.repository import ContextEnrichmentRepository
import importlib.util
from pathlib import Path

_APP_PATH = Path(__file__).resolve().parents[1] / "src" / "monitoring-adapter" / "app.py"
_spec = importlib.util.spec_from_file_location("monitoring_adapter_app", _APP_PATH)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

app = _mod.app
create_hitl_jira_assignment = _mod.create_hitl_jira_assignment
create_human_evidence_jira_request = _mod.create_human_evidence_jira_request


def routing() -> HitlRoutingConfiguration:
    return HitlRoutingConfiguration(
        default_approver_group="platform-approvers", l2_group="payments-l2",
        l3_group="payments-l3", service_owner="payments-owner-account-id",
        timezone="Asia/Calcutta", business_hours={}, severity_sla_minutes={"critical": 15},
        jira_project_key="KAN", jira_issue_type="Bug",
        jira_transition_mapping={"approved": "31", "rejected": "41"},
        fallback_assignment_group="platform-l2",
    )


@pytest.mark.asyncio
async def test_hitl_request_resolves_exact_service_owner_and_sla():
    incident_id = uuid4()
    assignment = await resolve_hitl_assignee(
        "tenant-a", SimpleNamespace(id=incident_id), "remediation", "critical", routing=routing(),
    )
    assert assignment.incident_id == incident_id
    assert assignment.assignee == "payments-owner-account-id"
    assert assignment.source == "service_owner"
    assert assignment.due_at <= datetime.now(UTC) + timedelta(minutes=16)


@pytest.mark.asyncio
async def test_incident_assignment_precedes_service_owner_and_placeholder_is_rejected():
    incident_id = uuid4()
    assignment = await resolve_hitl_assignee(
        "tenant-a", SimpleNamespace(id=incident_id), "evidence", "critical",
        routing=routing(), incident_assignee="incident-user-account-id",
    )
    assert assignment.assignee == "incident-user-account-id"
    assert assignment.source == "incident_assignment"
    with pytest.raises(ValueError, match="No governed HITL assignee"):
        await resolve_hitl_assignee(
            "tenant-a", SimpleNamespace(id=incident_id), "evidence", "critical",
            routing=routing().model_copy(update={
                "service_owner": "incident-owner", "l2_group": "unknown",
                "l3_group": "operator", "fallback_assignment_group": "unassigned",
            }),
        )


async def seed_identity(session):
    now = datetime.now(UTC)
    incident_id, alert_id, analysis_id = uuid4(), uuid4(), uuid4()
    snapshot_id, recommendation_id, selection_id, plan_id = uuid4(), uuid4(), uuid4(), uuid4()
    context_fingerprint, plan_fingerprint = "c" * 64, "sha256:" + "p" * 64
    session.add(IncidentInvestigationBindingRecord(
        tenant_id="tenant-a", project_id="project-a", incident_id=incident_id,
        alert_id=alert_id, analysis_request_id=analysis_id, context_snapshot_id=snapshot_id,
        context_fingerprint=context_fingerprint, recommendation_id=recommendation_id,
        rca_version=3, resolution_plan_id=selection_id, plan_fingerprint=plan_fingerprint,
        status="grounded", created_at=now, expires_at=now + timedelta(hours=1),
    ))
    session.add(ExecutionPlanRecord(
        id=plan_id, tenant_id="tenant-a", incident_id=incident_id,
        recommendation_id=recommendation_id, rca_version=3,
        context_snapshot_id=snapshot_id, context_fingerprint=context_fingerprint,
        resolution_selection_id=selection_id, policy_version="policy-v1",
        playbook_id="restart-service", schema_version="kaims.execution-plan.v2",
        fingerprint=plan_fingerprint, target_service="payments", target_environment="prod",
        risk_tier="MEDIUM", execution_mode="HITL", approval_required=True,
        execution_ready=True, readiness_blocks=[], plan_payload={"plan_id": str(plan_id)},
    ))
    await session.flush()
    return {
        "incident_id": incident_id, "recommendation_id": recommendation_id,
        "rca_version": 3, "context_snapshot_id": snapshot_id,
        "context_fingerprint": context_fingerprint, "resolution_selection_id": selection_id,
        "execution_plan_id": plan_id, "plan_fingerprint": plan_fingerprint,
    }


@pytest.mark.asyncio
async def test_jira_binding_preserves_full_identity_and_cross_tenant_lookup_fails(
    sqlite_session_factory,
):
    async with sqlite_session_factory() as session:
        identity = await seed_identity(session)
        repo = ContextEnrichmentRepository(session)
        binding = await repo.bind_jira_incident(
            tenant_id="tenant-a", jira_issue_key="KAN-42", jira_project_key="KAN",
            assignee_id="payments-owner-account-id", assignee_group=None,
            approval_expires_at=datetime.now(UTC) + timedelta(minutes=15),
            ownership="human", closure_policy={"ownership": "human", "kaims_may_close": False},
            **identity,
        )
        assert binding["execution_plan_id"] == str(identity["execution_plan_id"])
        assert await repo.get_jira_incident_binding(
            tenant_id="tenant-b", jira_issue_key="KAN-42", jira_project_key="KAN",
        ) is None


@pytest.mark.asyncio
async def test_duplicate_webhook_is_idempotent_and_unauthorized_actor_cannot_approve(
    sqlite_session_factory,
):
    payload = {
        "timestamp": 1, "webhookEvent": "jira:issue_updated",
        "issue": {"id": "42", "key": "KAN-42"}, "changelog": {"id": "99"},
    }
    async with sqlite_session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        first, _ = await repo.record_jira_webhook_outcome(
            tenant_id="tenant-a", event_id=jira_webhook_event_id(payload),
            jira_issue_key="KAN-42", action="approved", actor_id="intruder",
            outcome="rejected", payload=payload,
        )
        duplicate, _ = await repo.record_jira_webhook_outcome(
            tenant_id="tenant-a", event_id=jira_webhook_event_id(payload),
            jira_issue_key="KAN-42", action="approved", actor_id="intruder",
            outcome="rejected", payload=payload,
        )
        assert first is True and duplicate is False
    valid, reason = validate_jira_approval(
        binding={"assignee_id": "authorized"}, actor_id="intruder", action="approved",
        current_identity={},
    )
    assert valid is False
    assert "not the assigned" in reason


def test_stale_plan_cannot_be_approved_and_arbitrary_comment_is_not_approval():
    binding = {
        "assignee_id": "authorized", "recommendation_id": "r1", "rca_version": 2,
        "context_snapshot_id": "s1", "context_fingerprint": "c1",
        "execution_plan_id": "p1", "plan_fingerprint": "f1",
        "approval_expires_at": datetime.now(UTC) + timedelta(minutes=5),
    }
    current = {**binding, "execution_plan_id": "p2"}
    valid, reason = validate_jira_approval(
        binding=binding, actor_id="authorized", action="approved", current_identity=current,
    )
    assert valid is False and "execution_plan_id changed" in reason
    assert governed_jira_action("In Progress", {"approved": "Approved"}) == "updated"


def test_ticket_closure_authority_is_fail_closed():
    ready_state = {
        "remediation_status": "succeeded", "validation_status": "passed",
        "required_validators_complete": True, "alerts_cleared": True,
        "stability_window_passed": True, "rollback_not_active": True,
        "critical_contradictions": [], "current_plan_matches_approved_plan": True,
    }
    human_policy = TicketClosurePolicy(ownership="human", kaims_may_close=False)
    assert kaims_may_close_ticket(human_policy, ready_state)[0] is False
    kaims_policy = TicketClosurePolicy(ownership="kaims", kaims_may_close=True)
    assert kaims_may_close_ticket(kaims_policy, ready_state) == (True, [])
    assert kaims_may_close_ticket(kaims_policy, {**ready_state, "alerts_cleared": False})[0] is False


@pytest.mark.asyncio
async def test_resolve_human_evidence_responder_returns_typed_user_and_group(sqlite_session_factory):
    incident_id = uuid4()
    async with sqlite_session_factory() as session:
        # 1. User from projection owner
        session.add(IncidentProjectionRecord(
            tenant_id="tenant-a", incident_id=incident_id,
            owner="alice@example.com", service="payments", environment="prod", status="open",
        ))
        await session.flush()
        repo = ContextEnrichmentRepository(session)
        res = await repo.resolve_human_evidence_responder(tenant_id="tenant-a", incident_id=incident_id)
        assert res == {"identity": "alice@example.com", "source": "incident_assignment", "kind": "user"}

    # 2. Group from application owner_team when owner_email is absent
    incident_id_2 = uuid4()
    async with sqlite_session_factory() as session:
        session.add(IncidentProjectionRecord(
            tenant_id="tenant-a", incident_id=incident_id_2,
            owner=None, service="checkout", environment="prod", status="open",
        ))
        session.add(ApplicationRecord(
            tenant_id="tenant-a", name="checkout", owner_email=None,
            owner_team="core-payments", status="active", environment="prod",
            namespace="default", region="us-east-1", technology="python", metrics_endpoint="http://prometheus:9090",
        ))
        await session.flush()
        repo = ContextEnrichmentRepository(session)
        res = await repo.resolve_human_evidence_responder(tenant_id="tenant-a", incident_id=incident_id_2)
        assert res == {"identity": "core-payments", "source": "service_ownership", "kind": "group"}

    # 3. Group from control plane default_approver_group
    incident_id_3 = uuid4()
    async with sqlite_session_factory() as session:
        session.add(IncidentProjectionRecord(
            tenant_id="tenant-a", incident_id=incident_id_3,
            owner=None, service="", environment="prod", status="open",
        ))
        session.add(OnboardingControlPlaneRecord(
            tenant_id="tenant-a", project_name="platform", status="ACTIVE",
            payload={"default_approver_group": "platform-approvers"},
        ))
        await session.flush()
        repo = ContextEnrichmentRepository(session)
        res = await repo.resolve_human_evidence_responder(tenant_id="tenant-a", incident_id=incident_id_3)
        assert res == {"identity": "platform-approvers", "source": "tenant_default", "kind": "group"}


@pytest.mark.asyncio
async def test_create_human_evidence_jira_request_group_never_calls_assignee(sqlite_session_factory):
    incident_id = uuid4()
    requirement_id = uuid4()
    request_id = uuid4()

    mock_client = MagicMock()
    mock_client.create_or_update_incident = AsyncMock(return_value=("KAN-2004", "created"))
    mock_client.assign_issue = AsyncMock()
    mock_client.add_comment = AsyncMock()
    mock_client.add_labels = AsyncMock()
    mock_client.get_issue = AsyncMock(return_value={"fields": {"updated": "2026-09-07T12:00:00Z"}})

    app.state.session_factory = sqlite_session_factory

    async with sqlite_session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        await repo.upsert_context_evidence_requirements([
            EvidenceRequirement(
                requirement_id=requirement_id, tenant_id="tenant-a", incident_id=incident_id,
                rca_version=1, category="business_impact", question="Team question",
                reason="Team reason", priority="high", collection_mode="human_required",
                created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
            )
        ])
        created_req = await repo.create_human_evidence_request(
            tenant_id="tenant-a", incident_id=incident_id,
            requirement_id=requirement_id, expected_responder="core-payments",
            assignment_type="group", assignment_source="service_ownership",
            due_at=datetime.now(UTC) + timedelta(hours=1), acceptable_format="format",
            evidence_already_checked=[], hypothesis_impact="impact",
        )
        await session.commit()

    req = HumanEvidenceJiraRequest(
        tenant_id="tenant-a", incident_id=incident_id, request_id=created_req.request_id,
        requirement_id=requirement_id, assignee_id="core-payments", assignment_type="group",
        due_at=datetime.now(UTC) + timedelta(hours=1), requested_evidence="Metrics snapshot",
        reason="Verify core payments status", kaims_deep_link="http://localhost:8080/incidents/1",
    )

    with patch.object(_mod, "_jira_api_client", return_value=mock_client), \
         patch.object(_mod, "JIRA_PROJECT_KEY", "KAN"):
        result = await create_human_evidence_jira_request(req)

    # Asserts that assign_issue is NEVER called for group assignments
    mock_client.assign_issue.assert_not_called()
    # Asserts that team comment and label are attached
    mock_client.add_comment.assert_called_once()
    assert "core-payments" in mock_client.add_comment.call_args[0][1]
    mock_client.add_labels.assert_called_once_with("KAN-2004", ["kaiops-team-core-payments"])
    # Asserts binding is synchronized
    assert result["jira_sync_status"] == "synchronized"
    assert result["jira_assignee_id"] == "core-payments"


@pytest.mark.asyncio
async def test_create_hitl_jira_assignment_group_never_calls_assignee(sqlite_session_factory):
    mock_client = MagicMock()
    mock_client.create_or_update_incident = AsyncMock(return_value=("KAN-2005", "created"))
    mock_client.assign_issue = AsyncMock()
    mock_client.add_comment = AsyncMock()
    mock_client.add_labels = AsyncMock()
    mock_client.add_remote_link = AsyncMock()
    mock_client.transition_issue = AsyncMock()

    app.state.session_factory = sqlite_session_factory

    async with sqlite_session_factory() as session:
        identity = await seed_identity(session)
        await session.commit()

    req = HitlJiraRequest(
        tenant_id="tenant-a",
        incident_id=identity["incident_id"],
        recommendation_id=identity["recommendation_id"],
        rca_version=identity["rca_version"],
        context_snapshot_id=identity["context_snapshot_id"],
        context_fingerprint=identity["context_fingerprint"],
        resolution_selection_id=identity["resolution_selection_id"],
        execution_plan_id=identity["execution_plan_id"],
        plan_fingerprint=identity["plan_fingerprint"],
        risk="low",
        rollback_plan="revert",
        approval_expires_at=datetime.now(UTC) + timedelta(hours=1),
        summary="Restart service",
        service="payments",
        environment="prod",
        severity="critical",
        approval_type="remediation",
        evidence_summary_url="http://localhost:8080/evidence",
        closure_policy=TicketClosurePolicy(ownership="human", kaims_may_close=False),
        routing=HitlRoutingConfiguration(
            default_approver_group="payments-l2",
            l2_group="payments-l2",
            l3_group="payments-l3",
            service_owner=None,
            timezone="UTC",
            business_hours={},
            severity_sla_minutes={"critical": 15},
            jira_project_key="KAN",
            jira_issue_type="Bug",
            jira_transition_mapping={"approval_pending": "11"},
            fallback_assignment_group="payments-l2",
        ),
    )

    with patch.object(_mod, "_jira_api_client", return_value=mock_client), \
         patch.object(_mod, "JIRA_PROJECT_KEY", "KAN"):
        result = await create_hitl_jira_assignment(req)

    # Asserts assign_issue is NEVER called for group assignments
    mock_client.assign_issue.assert_not_called()
    assert mock_client.add_comment.call_count >= 1
    mock_client.add_labels.assert_called_once_with("KAN-2005", ["kaiops-team-payments-l2"])
    assert result["binding"]["assignee_group"] == "payments-l2"


@pytest.mark.asyncio
async def test_group_evidence_response_authorization_enforces_strict_boundary(sqlite_session_factory):
    incident_id = uuid4()
    requirement_id = uuid4()

    async with sqlite_session_factory() as session:
        repo = ContextEnrichmentRepository(session)
        await repo.upsert_context_evidence_requirements([
            EvidenceRequirement(
                requirement_id=requirement_id, tenant_id="tenant-a", incident_id=incident_id,
                rca_version=1, category="business_impact", question="Group question",
                reason="Group reason", priority="high", collection_mode="human_required",
                created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
            )
        ])
        request = await repo.create_human_evidence_request(
            tenant_id="tenant-a", incident_id=incident_id,
            requirement_id=requirement_id, expected_responder="core-payments",
            assignment_type="group", assignment_source="service_ownership",
            due_at=datetime.now(UTC) + timedelta(hours=1), acceptable_format="format",
            evidence_already_checked=[], hypothesis_impact="impact",
        )
        await repo.bind_human_evidence_jira(
            tenant_id="tenant-a", incident_id=incident_id, request_id=request.request_id,
            requirement_id=requirement_id, jira_issue_key="KAN-2004", jira_issue_url="http://jira/KAN-2004",
            jira_version="1", jira_assignee_id="core-payments", sync_status="synchronized",
        )

        # 1. Unassigned group direct submission by user-456 fails (strict authorization preserved)
        with pytest.raises(PermissionError, match="authenticated responder is not assigned to this evidence request"):
            await repo.record_human_evidence_response(
                tenant_id="tenant-a", incident_id=incident_id, requirement_id=requirement_id,
                response={"response": "Metrics looking good", "responder_id": "user-456", "responded_at": datetime.now(UTC), "source_reference": "jira://KAN-2004"},
            )

        # 2. Jira user claims ticket in Jira UI -> Jira webhook synchronizes user-456
        await repo.synchronize_human_evidence_jira_assignee(
            tenant_id="tenant-a", jira_issue_key="KAN-2004", jira_assignee_id="user-456",
            jira_version="2", sync_status="synchronized",
        )

        # 3. user-456 is now authorized and can submit response
        recorded = await repo.record_human_evidence_response(
            tenant_id="tenant-a", incident_id=incident_id, requirement_id=requirement_id,
            response={"response": "Metrics looking good", "responder_id": "user-456", "responded_at": datetime.now(UTC), "source_reference": "jira://KAN-2004"},
        )
        assert recorded["status"] == "answered"

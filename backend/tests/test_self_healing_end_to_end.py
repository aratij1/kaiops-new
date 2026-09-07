"""Chained, non-mocked proof that the self-healing loop actually heals.

Every other remediation/closure test in this suite exercises one stage of the
control loop in isolation (build the action, run one plugin, run the
validator) and several of them deliberately assert the *negative* path: no
live connector is configured in this environment, so execution is correctly
skipped rather than faking success (see test_remediation_closure.py).

This file exercises the positive path with the same unmodified production
classes, chained together in one incident story:

  1. A governed remediation action is dispatched through the real connector
     adapter interface (`BasePlugin`/`FakeCapabilityAdapter` from
     remediation_engine.plugins -- the same interface every live connector
     plugin implements; "fake" here means "no external system", not "test
     double for our own code").
  2. Its genuine execution result and independent pre/post recovery evidence
     are handed to the real `ClosureValidationAgent.validate()` from
     closure-service -- the same function production traffic calls.

If the pipeline is wired correctly, an incident with a successful execution
and confirming independent evidence reaches `health_restored=True` and
`closure_status="closed"`. If it does not, self-healing does not work end to
end regardless of how many isolated unit tests pass.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from closure_service import ClosureValidationAgent
from common.models import RemediationAction, RemediationStatus
from common.orchestration.execution_plan_contract import canonical_plan_fingerprint
from remediation_engine.plugins import FakeCapabilityAdapter

REQUIRED_KINDS = [
    "availability", "alert_clearance", "error_rate", "latency", "dependency_health", "critical_alerts",
]


def _validators(kinds: list[str]) -> list[dict]:
    return [
        {
            "validator_id": f"validator-{kind}",
            "tenant_id": "tenant-a",
            "connector_id": "fake-observer",
            "target_resource_id": "payments-api",
            "kind": kind,
            "check_reference": f"fake-check:{kind}",
            "expected_condition": f"{kind} passes",
            "evaluation_operator": "eq",
            "threshold": True,
            "observation_window_seconds": 60,
            "minimum_sample_count": 2,
            "timeout_seconds": 10,
            "authoritative_source": "fake-observer",
            "onboarding_registry_reference": f"validator-registry:validator-{kind}",
        }
        for kind in kinds
    ]


def _governed_plan() -> dict:
    validators = _validators(REQUIRED_KINDS)
    plan = {
        "schema_version": "kaims.execution-plan.v2",
        "plan_id": str(uuid4()),
        "tenant_id": "tenant-a",
        "rca_version": "rca-v1",
        "evidence_snapshot_id": "snapshot-v1",
        "recommendation_version": "recommendation-v1",
        "validation_endpoints": [],
        "validators": validators,
        "required_validation_kinds": REQUIRED_KINDS,
        "stability_window_seconds": 60,
    }
    plan["plan_fingerprint"] = canonical_plan_fingerprint(plan)
    return plan


@pytest.mark.asyncio
async def test_self_healing_end_to_end_recovers_and_closes_incident() -> None:
    plan = _governed_plan()
    incident_id = uuid4()
    action = RemediationAction(
        tenant_id="tenant-a",
        incident_id=incident_id,
        action_type="fake_test",
        target="payments-api",
        status=RemediationStatus.DISPATCHING,
        parameters={
            "execution_plan": plan,
            "approved_plan_fingerprint": plan["plan_fingerprint"],
            "target_resource_id": "dt://payments-api",
            "credential_ref": "vault://test/payments",
        },
    )

    # --- Stage 1: real dispatch through the connector adapter interface ---
    # This is the exact interface every live connector plugin (Kubernetes,
    # Jenkins, Ansible, ...) implements; nothing here is stubbed on our side.
    executed = await FakeCapabilityAdapter("fake_test").execute(action)
    assert executed.status == RemediationStatus.SUCCEEDED, (
        "connector adapter dispatch did not report success; the self-healing "
        "loop cannot proceed to closure"
    )
    executed.completed_at = datetime.now(UTC) - timedelta(seconds=90)

    contract = {
        "schema_version": "kaims.remediation.v3",
        "execution_id": str(executed.id),
        "plan_id": str(plan["plan_id"]),
        "plan_fingerprint": plan["plan_fingerprint"],
        "target": {"name": executed.target},
        "plan": plan,
    }
    contract["binding_fingerprint"] = canonical_plan_fingerprint(contract)
    executed.parameters["execution_contract"] = contract
    executed.parameters["validator_registry_snapshot"] = plan["validators"]

    now = datetime.now(UTC)
    executed.parameters["pre_state_validation_observations"] = [
        {
            "validator_id": f"validator-{kind}",
            "execution_id": str(executed.id),
            "plan_fingerprint": plan["plan_fingerprint"],
            "connector_id": "fake-observer",
            "target_resource_id": "payments-api",
            "observed_at": (now - timedelta(seconds=120)).isoformat(),
            "passed": False,
            "measured_value": 0,
            "expected_value": 1,
            "observation_window_start": (now - timedelta(seconds=180)).isoformat(),
            "observation_window_end": (now - timedelta(seconds=120)).isoformat(),
            "result_checksum": f"sha256:{'0' * 64}",
        }
        for kind in REQUIRED_KINDS
    ]
    executed.parameters["validation_observations"] = [
        {
            "validator_id": f"validator-{kind}",
            "execution_id": str(executed.id),
            "plan_fingerprint": plan["plan_fingerprint"],
            "connector_id": "fake-observer",
            "target_resource_id": "payments-api",
            "observed_at": (now - timedelta(seconds=offset)).isoformat(),
            "passed": True,
            "result_checksum": f"sha256:{'a' * 64}",
        }
        for kind in REQUIRED_KINDS
        for offset in (65, 0)
    ]

    # --- Stage 2: real independent closure validation ---
    report = await ClosureValidationAgent().validate(executed)

    assert report.validation["remediation_succeeded"] is True
    assert report.validation["approved_plan_fingerprint_preserved"] is True
    assert report.validation["independent_checks_passed"] is True
    assert report.validation["stability_window_completed"] is True
    assert report.validation["all_recovery_checks_passed"] is True
    assert report.health_restored is True
    assert report.alerts_cleared is True
    assert report.closure_status == "closed"
    assert report.metadata["outcome_validation"]["outcome"] == "RECOVERED"
    assert report.metadata["outcome_validation"]["closure_authorized"] is True
    assert report.metadata["closed_loop_validation"]["closure_authorized"] is True


@pytest.mark.asyncio
async def test_self_healing_end_to_end_refuses_to_close_without_independent_evidence() -> None:
    """The mirror image of the test above: the connector reports success, but
    no independent validator confirmed recovery. Closure must refuse -- a
    green executor exit code is not, by itself, proof of healing.
    """
    plan = _governed_plan()
    action = RemediationAction(
        tenant_id="tenant-a",
        incident_id=uuid4(),
        action_type="fake_test",
        target="payments-api",
        status=RemediationStatus.DISPATCHING,
        parameters={
            "execution_plan": plan,
            "approved_plan_fingerprint": plan["plan_fingerprint"],
            "target_resource_id": "dt://payments-api",
            "credential_ref": "vault://test/payments",
        },
    )

    executed = await FakeCapabilityAdapter("fake_test").execute(action)
    assert executed.status == RemediationStatus.SUCCEEDED
    executed.completed_at = datetime.now(UTC) - timedelta(seconds=90)
    # No execution_contract, no validator observations attached: the connector
    # said "done" but nothing independent confirmed it.

    report = await ClosureValidationAgent().validate(executed)

    assert report.health_restored is False
    assert report.closure_status == "validation_failed"
    assert report.validation["independent_checks_passed"] is False
    assert report.metadata["outcome_validation"]["closure_authorized"] is False


if __name__ == "__main__":
    asyncio.run(test_self_healing_end_to_end_recovers_and_closes_incident())
    asyncio.run(test_self_healing_end_to_end_refuses_to_close_without_independent_evidence())
    print("self-healing end-to-end: recovered+closed and refuse-without-evidence both verified")

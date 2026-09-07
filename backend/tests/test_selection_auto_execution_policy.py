from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError


def load_resolution_module():
    path = Path("ai-workbench/src/resolution-agent/app.py")
    spec = importlib.util.spec_from_file_location("selection_policy_resolution_app", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_approval_module():
    path = Path("backend/src/approval-service/app.py")
    spec = importlib.util.spec_from_file_location("selection_policy_approval_app", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ApprovalRequest.model_rebuild(_types_namespace={"UUID": UUID})
    module.ModifyRequest.model_rebuild(_types_namespace={"UUID": UUID})
    return module


def learned_option(**overrides) -> dict:
    option = {
        "id": "learned-runbook-1", "source": "tenant-learned-resolution-catalog",
        "service": "checkout", "risk": "low", "self_heal_eligible": True,
        "success_count": 3, "failure_count": 0,
        "steps": ["restart checkout-api"], "validation": ["health check passes"],
        "rollback": ["restore previous revision"],
    }
    option.update(overrides)
    return option


def static_option(**overrides) -> dict:
    option = {
        "id": "kaims-restart-service", "source": "kaims-governed-catalog-v1",
        "service": "checkout", "risk": "low",
        "steps": ["restart checkout-api"], "validation": ["health check passes"],
        "rollback": ["restore previous revision"],
    }
    option.update(overrides)
    return option


def recommendation(**overrides) -> dict:
    payload = {"confidence": 0.95}
    payload.update(overrides)
    return payload


class TestSelectionPolicyDecision:
    def test_certified_learned_runbook_is_auto_eligible_once_enabled(self):
        module = load_resolution_module()
        module.settings.resolution_auto_execution_enabled = True
        decision = module._selection_policy_decision(
            option=learned_option(), recommendation=recommendation(), environment="prod",
        )
        assert decision.decision == "hotl"
        assert decision.required_approver_role == "policy-engine"

    def test_certified_learned_runbook_stays_human_gated_when_disabled(self):
        module = load_resolution_module()
        module.settings.resolution_auto_execution_enabled = False
        decision = module._selection_policy_decision(
            option=learned_option(), recommendation=recommendation(), environment="prod",
        )
        assert decision.decision == "hitl"

    def test_unproven_static_catalog_option_never_auto_executes(self):
        # Even with the deployment override on, an option that was never
        # reviewed and never proven via a real successful execution (no
        # self_heal_eligible flag) must never skip a human - "canary_supported"
        # stands in for a proven track record here, and a static catalog entry
        # has none.
        module = load_resolution_module()
        module.settings.resolution_auto_execution_enabled = True
        decision = module._selection_policy_decision(
            option=static_option(), recommendation=recommendation(), environment="prod",
        )
        assert decision.decision == "hitl"
        assert "canary_not_supported" in decision.reason_codes

    def test_low_confidence_learned_runbook_still_requires_a_human(self):
        module = load_resolution_module()
        module.settings.resolution_auto_execution_enabled = True
        decision = module._selection_policy_decision(
            option=learned_option(), recommendation=recommendation(confidence=0.7), environment="prod",
        )
        assert decision.decision == "hitl"

    def test_missing_rollback_blocks_regardless_of_certification(self):
        module = load_resolution_module()
        module.settings.resolution_auto_execution_enabled = True
        decision = module._selection_policy_decision(
            option=learned_option(rollback=[]), recommendation=recommendation(), environment="prod",
        )
        assert decision.decision == "block"


class TestPolicyEngineApprovalRequest:
    AUTO_APPROVER = "kaims-auto-policy"

    def test_policy_engine_approval_accepted_when_deployment_opted_in(self):
        module = load_approval_module()
        module.settings.resolution_auto_execution_enabled = True
        request = module.ApprovalRequest(
            incident_id=uuid4(), recommendation_id=uuid4(), tenant_id="tenant-a",
            approver=self.AUTO_APPROVER, approver_role="policy-engine", channel="policy-engine",
        )
        assert request.approver_role == "policy-engine"

    def test_policy_engine_approval_rejected_when_deployment_has_not_opted_in(self):
        module = load_approval_module()
        module.settings.resolution_auto_execution_enabled = False
        with pytest.raises(ValidationError, match="automatic execution is not enabled"):
            module.ApprovalRequest(
                incident_id=uuid4(), recommendation_id=uuid4(), tenant_id="tenant-a",
                approver=self.AUTO_APPROVER, approver_role="policy-engine", channel="policy-engine",
            )

    def test_policy_engine_role_cannot_be_claimed_under_a_human_name(self):
        module = load_approval_module()
        module.settings.resolution_auto_execution_enabled = True
        with pytest.raises(ValidationError, match="kaims-auto-policy"):
            module.ApprovalRequest(
                incident_id=uuid4(), recommendation_id=uuid4(), tenant_id="tenant-a",
                approver="someone@example.com", approver_role="policy-engine", channel="policy-engine",
            )

    def test_policy_engine_channel_cannot_be_paired_with_a_human_role(self):
        module = load_approval_module()
        module.settings.resolution_auto_execution_enabled = True
        with pytest.raises(ValidationError, match="both be 'policy-engine'"):
            module.ApprovalRequest(
                incident_id=uuid4(), recommendation_id=uuid4(), tenant_id="tenant-a",
                approver=self.AUTO_APPROVER, approver_role="hitl-reviewer", channel="policy-engine",
            )

    def test_ordinary_human_approval_is_unaffected(self):
        module = load_approval_module()
        module.settings.resolution_auto_execution_enabled = False
        request = module.ApprovalRequest(
            incident_id=uuid4(), recommendation_id=uuid4(), tenant_id="tenant-a",
            approver="operator-a", approver_role="hitl-reviewer",
        )
        assert request.approver_role == "hitl-reviewer"

    def test_policy_engine_cannot_modify_the_proposed_action(self):
        module = load_approval_module()
        module.settings.resolution_auto_execution_enabled = True
        with pytest.raises(ValidationError, match="cannot modify"):
            module.ModifyRequest(
                incident_id=uuid4(), recommendation_id=uuid4(), tenant_id="tenant-a",
                approver=self.AUTO_APPROVER, approver_role="policy-engine", channel="policy-engine",
                modified_action="do something else",
            )

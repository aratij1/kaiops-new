"""Reproduces a live UI report: an ambiguous, platform-wide alert target
("kaiops-platform") correctly blocked execution, but still displayed a
Kubernetes validation command left over from the un-overridden catalog
template - misleading in a deployment that has no Kubernetes cluster at all
and can never run it, even though the gate itself was safe.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from common.models import Alert, AlertSeverity
from common.orchestration.execution_plan import resolve_execution_plan


def _alert(service: str) -> Alert:
    return Alert(
        id=uuid4(), tenant_id="tenant-a", source="prometheus", name="KaiOpsServiceDown",
        service=service, environment="prod", severity=AlertSeverity.CRITICAL,
        description=f"Service {service} is not reachable by Prometheus for more than 1 minute.",
    )


def _plan(service: str) -> dict:
    return resolve_execution_plan(
        alert=_alert(service), workflow_name="test", requires_approval=True, risk_tier="high",
        execution_mode="human-approval", resolution_hints="restart the unreachable service",
        evidence_basis=[], incident_id=uuid4(), root_cause="service unreachable", confidence=0.9,
    )


def test_ambiguous_platform_target_shows_no_commands_of_any_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REMEDIATION_EXECUTION_PLATFORM", "docker-compose")
    monkeypatch.setenv("REMEDIATION_COMPOSE_PROJECT", "kaims")
    plan = _plan("kaiops-platform")

    assert plan["execution_ready"] is False
    assert any("does not implement catalog operations" in reason for reason in plan["readiness_blocks"])
    assert plan["commands"] == []
    # Previously left over from the un-overridden kubectl template - a
    # command that reads as ready-to-run but can never execute here.
    assert plan["validation_commands"] == []
    assert plan["rollback_commands"] == []
    assert not any("kubectl" in str(command) for command in [*plan["commands"], *plan["validation_commands"]])


def test_recognized_internal_service_still_gets_real_docker_compose_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REMEDIATION_EXECUTION_PLATFORM", "docker-compose")
    monkeypatch.setenv("REMEDIATION_COMPOSE_PROJECT", "kaims")
    plan = _plan("kaiops-model-router")

    assert plan["readiness_blocks"] == []
    assert plan["commands"]
    assert all("docker-socket-proxy" in command for command in plan["commands"])
    assert plan["validation_commands"] == [
        "curl --fail --silent --show-error --retry 15 --retry-all-errors "
        "--retry-connrefused --retry-delay 2 http://model-router:8000/healthz"
    ]

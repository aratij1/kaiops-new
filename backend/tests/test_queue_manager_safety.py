from common.message_processing import extract_processing_identities
from api_gateway.auth_policy import ADMIN_ROLE, route_auth_rule
from app import _queue_job_id


def test_queue_manager_routes_require_administrator() -> None:
    assert route_auth_rule("GET", "/operations/queues") == {ADMIN_ROLE}
    assert route_auth_rule("POST", "/operations/queues/cancel-alert") == {ADMIN_ROLE}
    assert route_auth_rule("POST", "/operations/queues/kaiops.worker.raw-alerts/jobs/job-123/rerun") == {ADMIN_ROLE}
    assert route_auth_rule("DELETE", "/operations/queues/kaiops.worker.raw-alerts/jobs/job-123") == {ADMIN_ROLE}
    assert route_auth_rule("DELETE", "/operations/queues/kaiops.worker.raw-alerts/messages") == {ADMIN_ROLE}


def test_queue_job_identity_is_stable_and_scoped_to_queue() -> None:
    payload = b'{"alert_id":"alert-123"}'
    assert _queue_job_id("kaiops.worker.raw-alerts", payload) == _queue_job_id("kaiops.worker.raw-alerts", payload)
    assert _queue_job_id("kaiops.worker.raw-alerts", payload) != _queue_job_id("kaiops.worker.context", payload)
    assert _queue_job_id("kaiops.worker.raw-alerts", payload).startswith("job-")


def test_processing_identities_follow_alert_across_pipeline_envelopes() -> None:
    identities = extract_processing_identities(
        {
            "alert_id": "alert-123",
            "incident_id": "incident-456",
            "event_envelope": {"event_id": "event-789", "alert_id": "alert-123"},
        }
    )
    assert identities[0:2] == ["alert-123", "incident-456"]
    assert "event-789" in identities


def test_processing_identities_are_unique_and_ignore_empty_values() -> None:
    assert extract_processing_identities({"alert_id": "same", "id": "same", "incident_id": ""}) == ["same"]


def test_cancellation_follows_nested_canonical_workflow_subjects():
    identities = extract_processing_identities({
        "event_envelope": {"identity": {"incident_id": "incident-a", "alert_id": "alert-a"}},
        "context": {"incident_id": "incident-a", "alert": {"id": "alert-a"}},
        "incident": {"id": "incident-a"},
    })
    assert set(identities) == {"incident-a", "alert-a"}


def test_sample_identity_uses_complete_large_body():
    from common.queue_management import describe_message
    import json
    body = json.dumps({"context": {"alert_id": "a", "incident_id": "i"}, "data": "x" * 60000}).encode()
    row = describe_message("kaiops.worker.context", body)
    assert row["job_id"] == _queue_job_id("kaiops.worker.context", body)
    assert row["job_id"] != _queue_job_id("kaiops.worker.context", body[:50000])
    assert row["alert_id"] == "a"
    assert row["incident_id"] == "i"
    assert row["payload_bytes"] == len(body)


def test_sample_handles_invalid_json_and_non_object_payloads():
    from common.queue_management import describe_message
    for body in (b"[]", b"null", b"123", b"bad json", b"\xff"):
        row = describe_message("kaiops.worker.context", body)
        assert row["payload_valid"] is False
        assert row["name"] == "Queued event"


def test_virtual_host_is_decoded_once():
    from common.queue_management import broker_vhost
    assert broker_vhost("amqp://localhost/") == "/"
    assert broker_vhost("amqp://localhost/%2F") == "/"
    assert broker_vhost("amqp://localhost/team%2Fprod") == "team/prod"


async def test_failed_republish_does_not_ack_original(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from common import queue_management as qm
    import pytest
    message = MagicMock(body=b"{}", headers={})
    for key in ("content_type", "content_encoding", "correlation_id", "message_id", "timestamp", "type", "app_id"):
        setattr(message, key, None)
    message.ack = AsyncMock()
    queue = MagicMock(get=AsyncMock(return_value=message))
    channel = MagicMock(set_qos=AsyncMock(), declare_queue=AsyncMock(return_value=queue))
    channel.default_exchange.publish = AsyncMock(side_effect=RuntimeError("publish failed"))
    connection = MagicMock(channel=AsyncMock(return_value=channel), close=AsyncMock())
    monkeypatch.setattr(qm.aio_pika, "connect_robust", AsyncMock(return_value=connection))
    with pytest.raises(RuntimeError, match="publish failed"):
        await qm.mutate_ready_queue_job(broker_url="amqp://localhost", queue_name="kaiops.q", job_id=qm.queue_job_id("kaiops.q", b"{}"), rerun=True)
    message.ack.assert_not_awaited()
    connection.close.assert_awaited_once()


async def test_sampling_requeues_all_messages(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from common import queue_management as qm
    message = MagicMock(body=b"[]", redelivered=False, reject=AsyncMock())
    queue = MagicMock(get=AsyncMock(side_effect=[message, None]))
    channel = MagicMock(set_qos=AsyncMock(), declare_queue=AsyncMock(return_value=queue))
    connection = MagicMock(channel=AsyncMock(return_value=channel), close=AsyncMock())
    monkeypatch.setattr(qm.aio_pika, "connect_robust", AsyncMock(return_value=connection))
    rows = await qm.sample_ready_messages("amqp://localhost", "kaiops.q")
    assert len(rows) == 1
    message.reject.assert_awaited_once_with(requeue=True)
    connection.close.assert_awaited_once()

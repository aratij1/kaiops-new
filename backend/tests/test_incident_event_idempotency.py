"""Regression coverage for a real, live-reproduced production failure.

A redelivered or concurrently retried incident event (RabbitMQ redelivery, a
retried HTTP call, two near-simultaneous requests for the same incident) is
built fresh each time via `build_event_envelope`, which assigns a new random
`event_id` per call. The deterministic `(transport_provider, idempotency_key)`
pair is what actually identifies "the same logical event" -- and the live
MySQL table has always enforced that pair as unique (uq_incident_events_idempotency,
added by 20260708_incident_metadata_layer.sql). `IncidentEventRecord` never
declared that constraint, so a SQLite dev/test database silently allowed
duplicates while production correctly rejected the second insert and (before
this fix) let the IntegrityError escape as an unhandled request failure
instead of the "safely coalesced" no-op the UI already promises.
"""

from __future__ import annotations

import pytest
from common.event_publishers import build_event_envelope
from common.repository import IncidentRepository
from sqlalchemy import func, select


def _context_collected_envelope(incident_id: str) -> dict:
    return build_event_envelope(
        event_type="incident.context.collected",
        identity={"incident_id": incident_id, "trace_id": "trace-1"},
        scope={"tenant_id": "tenant-a", "service": "api-gateway", "environment": "prod"},
        state={"status": "investigating"},
        policy={},
        transport={"provider": "rabbitmq", "channel": "orchestration-events"},
        payload={"quality": {"grounding_coverage": 0.53}},
    )


@pytest.mark.asyncio
async def test_redelivered_incident_event_is_coalesced_not_rejected(sqlite_session_factory) -> None:
    incident_id = "11111111-1111-4111-8111-111111111111"

    async with sqlite_session_factory() as session:
        repo = IncidentRepository(session)
        first = _context_collected_envelope(incident_id)
        second = _context_collected_envelope(incident_id)
        assert first["event_id"] != second["event_id"], "envelopes must reproduce a real redelivery"
        assert first["idempotency"]["idempotency_key"] == second["idempotency"]["idempotency_key"]

        await repo.save_incident_event(first)
        # Must not raise IntegrityError: this is the exact scenario that
        # previously surfaced to the operator as "Analysis failed: (raised as
        # a result of Query-invoked autoflush ...) Duplicate entry ...".
        await repo.save_incident_event(second)
        await session.commit()

    from common.database import IncidentEventRecord

    async with sqlite_session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(IncidentEventRecord).where(
                IncidentEventRecord.idempotency_key == first["idempotency"]["idempotency_key"],
            )
        )
        assert count == 1, "the redelivered copy must not create a second row"


@pytest.mark.asyncio
async def test_distinct_incidents_are_not_coalesced_together(sqlite_session_factory) -> None:
    """The fix must only swallow a genuine duplicate, never a different event
    that happens to share nothing but a coincidental collision path.
    """
    async with sqlite_session_factory() as session:
        repo = IncidentRepository(session)
        await repo.save_incident_event(_context_collected_envelope("22222222-2222-4222-8222-222222222222"))
        await repo.save_incident_event(_context_collected_envelope("33333333-3333-4333-8333-333333333333"))
        await session.commit()

    from common.database import IncidentEventRecord

    async with sqlite_session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(IncidentEventRecord))
        assert count == 2


def _recommendation_generated_envelope(
    *, incident_id: str, recommendation_id: str, transport_provider: str = "unknown",
    explicit_idempotency_key: bool = True,
) -> dict:
    """Mirrors resolution-agent's real `_persist_resolution_event` envelope.

    `explicit_idempotency_key=False` reproduces the pre-fix call, which never
    passed an `idempotency` block at all and therefore fell through to
    `build_event_envelope`'s static `f"{event_type}:{incident_id}"` default --
    identical for every RCA regeneration of the same incident.
    """
    kwargs = dict(
        event_type="incident.recommendation.generated",
        identity={"incident_id": incident_id, "trace_id": "trace-1"},
        scope={"tenant_id": "tenant-a", "service": "api-gateway", "environment": "prod"},
        state={"status": "awaiting_approval"},
        policy={"risk_tier": "low", "requires_approval": True},
        transport={"provider": transport_provider, "channel": "resolution-events"},
        payload={"recommendation_id": recommendation_id, "rca_version": None},
    )
    if explicit_idempotency_key:
        kwargs["idempotency"] = {
            "idempotency_key": f"incident.recommendation.generated:{recommendation_id}",
        }
    return build_event_envelope(**kwargs)


@pytest.mark.asyncio
async def test_repeat_rca_regenerations_each_advance_the_projection(sqlite_session_factory) -> None:
    """Real, live-reproduced bug: every RCA regeneration for the same incident
    publishes an `incident.recommendation.generated` event with the same
    `transport_provider` (almost always "unknown" -- decision_payload rarely
    carries message_bus_provider for a manual/programmatic regeneration).
    Before the fix, resolution-agent's `_persist_resolution_event` never
    passed an explicit `idempotency` block, so every regeneration after the
    first collided on `(transport_provider, idempotency_key)` and was
    silently swallowed by `save_incident_event`'s IntegrityError handling --
    which also skips `_upsert_projection_from_record`, permanently freezing
    `IncidentProjectionRecord.recommendation_id` at the first RCA version
    forever, even though later, more current, grounded RCAs kept landing in
    `incident_investigation_bindings`. This is what made
    `/resolution-catalog/select` reject the genuinely-current recommendation
    as "stale_recommendation" on every incident checked. The fix keys
    idempotency on the recommendation's own id, which is unique per RCA
    version, instead of the incident-wide static default.
    """
    incident_id = "44444444-4444-4444-8444-444444444444"
    recommendation_v1 = "55555555-5555-4555-8555-555555555555"
    recommendation_v2 = "66666666-6666-4666-8666-666666666666"

    async with sqlite_session_factory() as session:
        repo = IncidentRepository(session)
        await repo.save_incident_event(
            _recommendation_generated_envelope(incident_id=incident_id, recommendation_id=recommendation_v1)
        )
        await repo.save_incident_event(
            _recommendation_generated_envelope(incident_id=incident_id, recommendation_id=recommendation_v2)
        )
        await session.commit()

    from common.database import IncidentEventRecord, IncidentProjectionRecord
    from uuid import UUID

    async with sqlite_session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(IncidentEventRecord).where(
                IncidentEventRecord.event_type == "incident.recommendation.generated",
            )
        )
        assert count == 2, "each RCA regeneration is a distinct event, not a duplicate"

        projection = await session.get(IncidentProjectionRecord, UUID(incident_id))
        assert projection is not None
        assert projection.recommendation_id == UUID(recommendation_v2), (
            "the projection must advance to the latest RCA, not freeze at the first one"
        )


@pytest.mark.asyncio
async def test_regeneration_without_explicit_idempotency_key_reproduces_the_freeze(
    sqlite_session_factory,
) -> None:
    """Anchors the pre-fix failure mode directly: without an explicit,
    per-recommendation idempotency key, a second RCA regeneration for the
    same incident (same transport_provider) collides with the first and is
    silently dropped, leaving the projection stuck on the stale recommendation.
    """
    incident_id = "77777777-7777-4777-8777-777777777777"
    recommendation_v1 = "88888888-8888-4888-8888-888888888888"
    recommendation_v2 = "99999999-9999-4999-8999-999999999999"

    async with sqlite_session_factory() as session:
        repo = IncidentRepository(session)
        await repo.save_incident_event(
            _recommendation_generated_envelope(
                incident_id=incident_id, recommendation_id=recommendation_v1,
                explicit_idempotency_key=False,
            )
        )
        await repo.save_incident_event(
            _recommendation_generated_envelope(
                incident_id=incident_id, recommendation_id=recommendation_v2,
                explicit_idempotency_key=False,
            )
        )
        await session.commit()

    from common.database import IncidentEventRecord, IncidentProjectionRecord
    from uuid import UUID

    async with sqlite_session_factory() as session:
        count = await session.scalar(
            select(func.count()).select_from(IncidentEventRecord).where(
                IncidentEventRecord.event_type == "incident.recommendation.generated",
            )
        )
        assert count == 1, "demonstrates the pre-fix collision: the second regeneration is swallowed"

        projection = await session.get(IncidentProjectionRecord, UUID(incident_id))
        assert projection is not None
        assert projection.recommendation_id == UUID(recommendation_v1), (
            "demonstrates the pre-fix freeze: the projection never advances past the first RCA"
        )

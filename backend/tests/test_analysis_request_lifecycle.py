from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from common.repository import IncidentRepository


@pytest.mark.asyncio
async def test_active_analysis_requests_coalesce_per_incident(sqlite_session_factory) -> None:
    tenant_id = "tenant-a"
    incident_id = uuid4()
    first_request_id = uuid4()
    async with sqlite_session_factory() as session:
        repository = IncidentRepository(session)
        first, first_created = await repository.create_or_reuse_analysis_request(
            request_id=first_request_id,
            tenant_id=tenant_id,
            incident_id=incident_id,
            alert_id=uuid4(),
            expected_recommendation_id=uuid4(),
            mode="fresh",
        )
        second, second_created = await repository.create_or_reuse_analysis_request(
            request_id=uuid4(),
            tenant_id=tenant_id,
            incident_id=incident_id,
            alert_id=uuid4(),
            expected_recommendation_id=uuid4(),
            mode="fresh",
        )
        await session.commit()

    assert first_created is True
    assert second_created is False
    assert second.request_id == first_request_id


@pytest.mark.asyncio
async def test_terminal_request_allows_a_new_analysis(sqlite_session_factory) -> None:
    tenant_id = "tenant-a"
    incident_id = uuid4()
    async with sqlite_session_factory() as session:
        repository = IncidentRepository(session)
        first, _ = await repository.create_or_reuse_analysis_request(
            request_id=uuid4(), tenant_id=tenant_id, incident_id=incident_id,
            alert_id=uuid4(), expected_recommendation_id=uuid4(), mode="fresh",
        )
        first.status = "complete"
        second, created = await repository.create_or_reuse_analysis_request(
            request_id=uuid4(), tenant_id=tenant_id, incident_id=incident_id,
            alert_id=uuid4(), expected_recommendation_id=uuid4(), mode="fresh",
        )
        await session.commit()

    assert created is True
    assert second.request_id != first.request_id


@pytest.mark.asyncio
async def test_analysis_failure_is_terminal_and_retryable(sqlite_session_factory) -> None:
    request_id = uuid4()
    async with sqlite_session_factory() as session:
        repository = IncidentRepository(session)
        row, _ = await repository.create_or_reuse_analysis_request(
            request_id=request_id, tenant_id="tenant-a", incident_id=uuid4(),
            alert_id=uuid4(), expected_recommendation_id=uuid4(), mode="fresh",
        )
        changed = await repository.fail_analysis_request(
            request_id, tenant_id="tenant-a", reason="context connector contract failed",
        )
        await session.commit()

    assert changed is True
    assert row.status == "failed"
    assert row.terminal_reason == "context connector contract failed"
    assert row.completed_at is not None


@pytest.mark.asyncio
async def test_an_expired_published_request_never_blocks_a_fresh_one(sqlite_session_factory) -> None:
    """A request stuck at "published" past its own `expires_at` is not truly
    active - nothing transitions it out of "published" on its own once its
    underlying event is lost (a crashed consumer, a message-bus outage, or a
    resolution-agent supersede path that never ran to completion). Before
    this fix, `create_or_reuse_analysis_request` treated any row with
    status in (accepted, queued, published, running) as active forever,
    regardless of expiry - permanently blocking every future regeneration
    attempt for the same incident. `_publish_analysis_regeneration_command`
    would then return that dead row's own stale `delivery` value without
    ever publishing anything new, which reads as a normal success
    ("delivery=published") while doing nothing at all. Reproduced live:
    reprocessing the same 8 real incidents a second time, well past their
    15-minute expiry, still returned "OK ... delivery=published" for all 8
    with zero new resolution-agent log activity for any of them.
    """
    tenant_id = "tenant-a"
    incident_id = uuid4()
    now = datetime.now(UTC)
    async with sqlite_session_factory() as session:
        repository = IncidentRepository(session)
        first, first_created = await repository.create_or_reuse_analysis_request(
            request_id=uuid4(), tenant_id=tenant_id, incident_id=incident_id,
            alert_id=uuid4(), expected_recommendation_id=uuid4(), mode="fresh",
        )
        first.status = "published"
        first.expires_at = now - timedelta(minutes=1)
        second, second_created = await repository.create_or_reuse_analysis_request(
            request_id=uuid4(), tenant_id=tenant_id, incident_id=incident_id,
            alert_id=uuid4(), expected_recommendation_id=uuid4(), mode="fresh",
        )
        await session.commit()

    assert first_created is True
    assert second_created is True
    assert second.request_id != first.request_id
    assert first.status == "timed_out"
    assert first.terminal_reason == "analysis_deadline_exceeded"


@pytest.mark.asyncio
async def test_expired_analysis_stops_polling(sqlite_session_factory) -> None:
    now = datetime.now(UTC)
    async with sqlite_session_factory() as session:
        repository = IncidentRepository(session)
        row, _ = await repository.create_or_reuse_analysis_request(
            request_id=uuid4(), tenant_id="tenant-a", incident_id=uuid4(),
            alert_id=uuid4(), expected_recommendation_id=uuid4(), mode="fresh",
        )
        row.status = "published"
        row.expires_at = now - timedelta(seconds=1)
        changed = await repository.expire_analysis_request(row, now=now)
        await session.commit()

    assert changed is True
    assert row.status == "timed_out"
    assert row.terminal_reason == "analysis_deadline_exceeded"

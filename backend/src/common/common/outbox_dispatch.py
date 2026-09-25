from __future__ import annotations

import asyncio
import logging
from typing import Any
from fastapi import FastAPI
from sqlalchemy import text

logger = logging.getLogger("common.outbox_dispatch")


async def flush_resolution_outbox(app: FastAPI, settings: Any) -> int:
    if not getattr(settings, "database_enabled", False) or getattr(app.state, "session_factory", None) is None:
        return 0
    published = 0
    async with app.state.session_factory() as session:
        bind = getattr(session, "bind", None)
        dialect_name = str(getattr(getattr(bind, "dialect", None), "name", "")).lower()
        is_sqlite = "sqlite" in dialect_name
        if is_sqlite:
            acquired = 1
        else:
            try:
                acquired = await session.scalar(text("SELECT GET_LOCK('kaiops_resolution_outbox_dispatch', 0)"))
            except Exception:
                acquired = 1

        if int(acquired or 0) != 1:
            return 0
        try:
            from common.repository import IncidentRepository
            repo = IncidentRepository(session)
            rows = await repo.list_pending_resolution_events(
                limit=int(getattr(settings, "resolution_outbox_batch_size", 100) or 100)
            )
            publishers = getattr(app.state, "message_bus_publishers", {})
            for row in rows:
                provider = str(row.payload.get("transport") or "").strip().lower()
                publisher = publishers.get(provider) or publishers.get("rabbitmq") or getattr(app.state, "producer", None)
                if publisher:
                    try:
                        await publisher.publish(row.topic, row.payload, key=row.partition_key)
                        await repo.mark_resolution_event_published(row.event_id)
                        published += 1
                    except Exception as exc:
                        await repo.mark_resolution_event_retry(row.event_id, str(exc))
                    await session.commit()
        finally:
            if not is_sqlite:
                try:
                    await session.execute(text("SELECT RELEASE_LOCK('kaiops_resolution_outbox_dispatch')"))
                    await session.commit()
                except Exception:
                    pass
    return published

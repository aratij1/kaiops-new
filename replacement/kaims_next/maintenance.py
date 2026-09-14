"""Offline maintenance: stop API/consumers before refreshing reference context."""
import json
from sqlalchemy import select, update, delete
from .handoff import write_transaction, applications, outbox, enqueue, event
from .incidents import baselines, incidents


def refresh_documents(store, tenant, application):
    """Retain historical artifacts/incidents and queue discovery of the existing roots.

    Caller must stop consumers and intake for this database first. This is deliberately
    not exposed as an online API until discovery generations are implemented.
    """
    with write_transaction(store.engine) as c:
        scope = (applications.c.tenant_id == tenant, applications.c.application_id == application)
        app = c.execute(select(applications).where(*scope).with_for_update()).mappings().one()
        if app["state"] not in {"context_ready", "context_blocked"}:
            raise ValueError("Discovery is already in progress")
        active = c.execute(select(incidents.c.incident_id).where(
            incidents.c.tenant_id == tenant, incidents.c.application_id == application,
            incidents.c.state.in_(["collection_queued", "analysis_queued", "resolution_queued", "awaiting_approval", "execution_queued", "verification_queued"]))).first()
        if active:
            raise ValueError("Wait for active incident collection and analysis before refresh")
        for raw in c.execute(select(outbox.c.envelope).where(outbox.c.published == 0)).scalars():
            envelope = json.loads(raw)
            if envelope["tenant_id"] == tenant and envelope["application_id"] == application:
                raise ValueError("Wait for pending application events before refresh")
        c.execute(delete(baselines).where(baselines.c.tenant_id == tenant,
            baselines.c.application_id == application))
        c.execute(update(applications).where(*scope).values(state="discovery_queued", version=app["version"]+1))
        enqueue(c, event("application.discovery.requested", tenant, application))

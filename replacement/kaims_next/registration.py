"""Version-checked registration changes with durable snapshots and rediscovery."""
import json
from datetime import datetime, timezone
from sqlalchemy import Table, Column, String, Integer, Text, select, insert, update, delete
from .handoff import write_transaction, metadata, applications, outbox, inbox, encode, enqueue, event
from .incidents import incidents, baselines

revisions = Table("next_registration_revisions", metadata,
    Column("tenant_id", String(128), primary_key=True),
    Column("application_id", String(128), primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("config", Text, nullable=False),
    Column("recorded_at", String(64), nullable=False))


def revise(store, tenant, application, expected_version, config):
    encoded = encode(config)
    with write_transaction(store.engine) as c:
        scope = (applications.c.tenant_id == tenant, applications.c.application_id == application)
        current = c.execute(select(applications).where(*scope).with_for_update()).mappings().one()
        if current["version"] != expected_version:
            raise ValueError("Registration changed. Refresh the application before saving again.")
        if current["config"] == encoded:
            return False
        if current["state"] not in {"context_ready", "context_blocked"}:
            raise ValueError("Wait for document discovery to finish before editing registration.")
        active = c.execute(select(incidents.c.request).where(incidents.c.tenant_id == tenant,
            incidents.c.application_id == application,
            incidents.c.state.in_(["collection_queued", "analysis_queued", "waiting_for_context", "resolution_queued", "awaiting_approval", "execution_queued", "verification_queued"]))).scalars().all()
        if active:
            raise ValueError("Wait for active investigations to finish before editing registration.")
        # A published ready event can still be awaiting admission. Check durable consumption.
        consumers = {"application.discovery.requested":"discovery", "application.context.requested":"context",
            "application.context.ready":"incident-admission", "application.context.blocked":"incident-admission"}
        for raw in c.execute(select(outbox.c.envelope).where(outbox.c.topic.in_(consumers))).scalars():
            envelope = json.loads(raw)
            if envelope["tenant_id"] != tenant or envelope["application_id"] != application:
                continue
            if not c.execute(select(inbox.c.event_id).where(inbox.c.consumer == consumers[envelope["topic"]],
                inbox.c.event_id == envelope["event_id"])).first():
                raise ValueError("Wait for pending discovery events to finish before editing registration.")
        changed = c.execute(update(applications).where(*scope, applications.c.version == expected_version).values(
            config=encoded, state="discovery_queued", version=expected_version+1))
        if changed.rowcount != 1:
            raise ValueError("Registration changed. Refresh the application before saving again.")
        for version, snapshot in [(expected_version,current["config"]),(expected_version+1,encoded)]:
            if not c.execute(select(revisions.c.version).where(revisions.c.tenant_id == tenant,
                revisions.c.application_id == application, revisions.c.version == version)).first():
                c.execute(insert(revisions).values(tenant_id=tenant, application_id=application,
                    version=version, config=snapshot, recorded_at=datetime.now(timezone.utc).isoformat()))
        c.execute(delete(baselines).where(baselines.c.tenant_id == tenant, baselines.c.application_id == application))
        envelope = event("application.discovery.requested", tenant, application)
        envelope["application_version"] = expected_version+1
        enqueue(c, envelope)
    return True

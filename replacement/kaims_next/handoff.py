"""Independent transactional handoff core. SQLAlchemy supports isolated MySQL deployment.

This is the durable state boundary, not a discovery or RCA implementation.
"""
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy import Column, Integer, MetaData, String, Table, Text, insert, select, update

metadata = MetaData()
applications = Table("next_applications", metadata,
    Column("tenant_id", String(128), primary_key=True),
    Column("application_id", String(128), primary_key=True),
    Column("config", Text, nullable=False), Column("state", String(64), nullable=False),
    Column("version", Integer, nullable=False))
outbox = Table("next_outbox", metadata,
    Column("event_id", String(36), primary_key=True), Column("topic", String(128), nullable=False),
    Column("envelope", Text, nullable=False), Column("created_at", String(64), nullable=False), Column("published", Integer, nullable=False, default=0))
inbox = Table("next_inbox", metadata,
    Column("consumer", String(128), primary_key=True), Column("event_id", String(36), primary_key=True))
artifacts = Table("next_artifacts", metadata,
    Column("tenant_id", String(128), primary_key=True), Column("application_id", String(128), primary_key=True),
    Column("artifact_id", String(64), primary_key=True), Column("content", Text().with_variant(LONGTEXT(), "mysql"), nullable=False))


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def event(topic, tenant, application, refs=(), *, correlation_id=None, causation_id=None):
    return {"schema_version": 1, "event_id": str(uuid4()), "topic": topic,
            "tenant_id": tenant, "application_id": application, "artifact_refs": list(refs),
            "correlation_id": correlation_id or str(uuid4()), "causation_id": causation_id,
            "created_at": datetime.now(timezone.utc).isoformat()}


def enqueue(connection, envelope):
    if len(encode(envelope).encode()) > 16384:
        raise ValueError("Event exceeds 16 KiB reference-envelope limit")
    connection.execute(insert(outbox).values(event_id=envelope["event_id"], topic=envelope["topic"],
                                            envelope=encode(envelope), created_at=envelope["created_at"], published=0))


@contextmanager
def write_transaction(engine):
    with engine.begin() as connection:
        # SQLite ignores SELECT FOR UPDATE; reserve the writer before reading state.
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        yield connection


class Handoff:
    def __init__(self, engine):
        self.engine = engine

    def onboard(self, tenant, application, config):
        if not tenant or not application:
            raise ValueError("Tenant and application are required")
        encoded = encode(config)
        with write_transaction(self.engine) as c:
            existing = c.execute(select(applications).where(
                applications.c.tenant_id == tenant, applications.c.application_id == application).with_for_update()).mappings().first()
            if existing:
                if existing["config"] != encoded:
                    raise ValueError("Existing registration differs; explicit versioned update required")
                return False
            c.execute(insert(applications).values(tenant_id=tenant,application_id=application,
                      config=encoded,state="discovery_queued",version=1))
            enqueue(c,event("application.discovery.requested",tenant,application))
        return True

    def application(self, tenant, application):
        with self.engine.connect() as c:
            row=c.execute(select(applications).where(applications.c.tenant_id==tenant,
                          applications.c.application_id==application)).mappings().one()
            return {**dict(row),"config":json.loads(row["config"])}

    def consumed(self, consumer, event_id):
        with self.engine.connect() as c:
            return c.execute(select(inbox.c.event_id).where(inbox.c.consumer==consumer,
                             inbox.c.event_id==event_id)).first() is not None

    def artifact(self, tenant, application, artifact_id):
        with self.engine.connect() as c:
            content = c.execute(select(artifacts.c.content).where(artifacts.c.tenant_id == tenant,
                      artifacts.c.application_id == application,artifacts.c.artifact_id == artifact_id)).scalar_one()
            return json.loads(content)

    def complete(self, consumer, envelope, *, expected_state, next_state, next_topic, result):
        # Transport-specific workers validate the event and execute collectors outside
        # this transaction. A duplicate may repeat a read, but cannot advance state twice.
        tenant, application = envelope["tenant_id"], envelope["application_id"]
        content = encode(result)
        digest = hashlib.sha256(content.encode()).hexdigest()
        with write_transaction(self.engine) as c:
            row = c.execute(select(applications).where(applications.c.tenant_id == tenant,
                            applications.c.application_id == application).with_for_update()).mappings().one()
            done = c.execute(select(inbox.c.event_id).where(inbox.c.consumer == consumer,
                             inbox.c.event_id == envelope["event_id"])).first()
            if done:
                return False
            if envelope.get("application_version", row["version"]) != row["version"]:
                raise ValueError("Stale application version")
            if row["state"] != expected_state:
                raise ValueError("Unexpected stage; stale or misrouted delivery")
            for ref in envelope.get("artifact_refs", []):
                if c.execute(select(artifacts.c.artifact_id).where(artifacts.c.tenant_id == tenant,
                             artifacts.c.application_id == application,artifacts.c.artifact_id == ref)).first() is None:
                    raise ValueError("Artifact missing from application scope")
            if c.execute(select(artifacts.c.artifact_id).where(artifacts.c.tenant_id == tenant,
                         artifacts.c.application_id == application,artifacts.c.artifact_id == digest)).first() is None:
                c.execute(insert(artifacts).values(tenant_id=tenant,application_id=application,
                                                  artifact_id=digest,content=content))
            c.execute(update(applications).where(applications.c.tenant_id == tenant,
                      applications.c.application_id == application).values(state=next_state,version=row["version"]+1))
            c.execute(insert(inbox).values(consumer=consumer,event_id=envelope["event_id"]))
            if next_topic:
                following=event(next_topic,tenant,application,[digest],correlation_id=envelope["correlation_id"],
                                causation_id=envelope["event_id"])
                following["application_version"]=row["version"]+1
                enqueue(c,following)
        return True

    async def dispatch(self, publish_confirmed, limit=20):
        # Concurrent dispatchers can duplicate a delivery; consumer inbox makes it safe.
        with self.engine.connect() as c:
            pending = c.execute(select(outbox).where(outbox.c.published == 0).order_by(outbox.c.created_at,outbox.c.event_id).limit(limit)).mappings().all()
        for row in pending:
            await publish_confirmed(row["topic"],json.loads(row["envelope"]))
            with write_transaction(self.engine) as c:
                c.execute(update(outbox).where(outbox.c.event_id == row["event_id"]).values(published=1))
        return len(pending)

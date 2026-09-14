"""Durable incident admission and evidence stages, isolated from application lifecycle."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from sqlalchemy import Column, String, Text, Table, insert, select, update
from .handoff import write_transaction, metadata, applications, artifacts, inbox, encode, enqueue, event

incidents = Table("next_incidents", metadata,
    Column("tenant_id", String(128), primary_key=True),
    Column("application_id", String(128), primary_key=True),
    Column("incident_id", String(128), primary_key=True),
    Column("request", Text, nullable=False), Column("state", String(64), nullable=False),
    Column("result_ref", String(64)))
baselines = Table("next_baselines", metadata,
    Column("tenant_id", String(128), primary_key=True),
    Column("application_id", String(128), primary_key=True),
    Column("state", String(64), nullable=False), Column("artifact_ref", String(64), nullable=False))


incident_runs = Table("next_incident_runs", metadata,
    Column("run_id", String(36), primary_key=True),
    Column("tenant_id", String(128), nullable=False),
    Column("application_id", String(128), nullable=False),
    Column("incident_id", String(128), nullable=False),
    Column("previous_result_ref", String(64)),
    Column("previous_state", String(64), nullable=False),
    Column("requested_at", String(64), nullable=False))


def instant(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None: raise ValueError("Timezone required")
    return parsed.astimezone(timezone.utc)


class IncidentStore:
    def __init__(self, store): self.store, self.engine = store, store.engine

    def scope(self, tenant, application, incident):
        return (incidents.c.tenant_id == tenant, incidents.c.application_id == application,
                incidents.c.incident_id == incident)

    def lock_app(self, c, tenant, application):
        return c.execute(select(applications).where(applications.c.tenant_id == tenant,
            applications.c.application_id == application).with_for_update()).mappings().one()

    def emit(self, c, row, topic, refs=(), parent=None):
        envelope = event(topic, row["tenant_id"], row["application_id"], refs,
            correlation_id=parent["correlation_id"] if parent else None,
            causation_id=parent["event_id"] if parent else None)
        envelope["incident_id"] = row["incident_id"]
        # A recollection may run after source retention has expired. Keep the last
        # usable assessment available so an empty refresh cannot erase evidence.
        if topic == "incident.collection.requested" and row.get("result_ref"):
            envelope["previous_result_ref"] = row["result_ref"]
        enqueue(c, envelope)

    def admit(self, tenant, application, incident, request):
        start, end = instant(request["window_start"]), instant(request["window_end"])
        if not incident or not request["service"] or end <= start or end-start > timedelta(hours=24):
            raise ValueError("Require service and a positive incident window of at most 24 hours")
        if end > datetime.now(timezone.utc)+timedelta(minutes=5):
            raise ValueError("Incident window cannot be in the future")
        request = {**request, "window_start": start.isoformat(), "window_end": end.isoformat()}
        with write_transaction(self.engine) as c:
            app = self.lock_app(c, tenant, application)
            if request["service"] not in json.loads(app["config"]).get("services", []):
                raise ValueError("Service is not registered for this application")
            existing = c.execute(select(incidents).where(*self.scope(tenant, application, incident))).mappings().first()
            if existing:
                if existing["request"] != encode(request): raise ValueError("Incident ID already has a different request")
                return False
            baseline = c.execute(select(baselines).where(baselines.c.tenant_id == tenant,
                baselines.c.application_id == application)).mappings().first()
            state = "waiting_for_context" if baseline is None else (
                "collection_queued" if baseline["state"] == "context_ready" else "context_blocked")
            row = dict(tenant_id=tenant, application_id=application, incident_id=incident,
                       request=encode(request), state=state, result_ref=None)
            c.execute(insert(incidents).values(**row))
            if state == "collection_queued": self.emit(c, row, "incident.collection.requested", [baseline["artifact_ref"]])
        return True

    def reinvestigate(self, tenant, application, incident, expected_result_ref, mode="recollect"):
        with write_transaction(self.engine) as c:
            app = self.lock_app(c,tenant,application)
            row = c.execute(select(incidents).where(*self.scope(tenant,application,incident))).mappings().one()
            if row["result_ref"] != expected_result_ref or row["state"] not in {"assessed","failed","context_blocked"}:
                raise ValueError("Investigation changed or is already running. Refresh before retrying.")
            if json.loads(row["request"])["service"] not in json.loads(app["config"]).get("services",[]):
                raise ValueError("Service is no longer registered")
            baseline = c.execute(select(baselines).where(baselines.c.tenant_id==tenant,
                baselines.c.application_id==application)).mappings().first()
            if app["state"] != "context_ready" or not baseline or baseline["state"] != "context_ready":
                raise ValueError("Wait for document context to become ready")
            evidence_ref=None
            if mode == "reanalyze":
                if not row["result_ref"]:raise ValueError("No stored assessment evidence to reanalyze")
                content=c.execute(select(artifacts.c.content).where(artifacts.c.tenant_id==tenant,
                    artifacts.c.application_id==application,artifacts.c.artifact_id==row["result_ref"])).scalar_one()
                evidence_ref=json.loads(content).get("evidence_ref")
                if evidence_ref:
                    candidate=self.store.artifact(tenant,application,evidence_ref)
                    if (not any(item.get("kind") == "trace" for item in candidate.get("records", []))
                            and any(item.get("status") == "no_matches" for item in candidate.get("source_outcomes", []))):
                        # Prefer the latest prior run with usable records when a
                        # retention-limited recollection produced no matches.
                        prior_runs=c.execute(select(incident_runs.c.previous_result_ref).where(
                            incident_runs.c.tenant_id==tenant,incident_runs.c.application_id==application,
                            incident_runs.c.incident_id==incident).order_by(incident_runs.c.requested_at.desc())).scalars()
                        for prior_result_ref in prior_runs:
                            if not prior_result_ref: continue
                            prior_result=self.store.artifact(tenant,application,prior_result_ref)
                            prior_evidence_ref=prior_result.get("evidence_ref")
                            if prior_evidence_ref:
                                prior_evidence=self.store.artifact(tenant,application,prior_evidence_ref)
                                if prior_evidence.get("records"):
                                    evidence_ref=prior_evidence_ref; break
                if not evidence_ref:raise ValueError("No stored assessment evidence to reanalyze")
            elif mode != "recollect":raise ValueError("Unsupported investigation mode")
            c.execute(insert(incident_runs).values(run_id=str(uuid4()),tenant_id=tenant,application_id=application,
                incident_id=incident,previous_result_ref=row["result_ref"],previous_state=row["state"],
                requested_at=datetime.now(timezone.utc).isoformat()))
            c.execute(update(incidents).where(*self.scope(tenant,application,incident)).values(state="analysis_queued" if evidence_ref else "collection_queued",result_ref=evidence_ref))
            self.emit(c,row,"incident.analysis.requested" if evidence_ref else "incident.collection.requested",[evidence_ref or baseline["artifact_ref"]])

    def get(self, tenant, application, incident):
        with self.engine.connect() as c:
            row = dict(c.execute(select(incidents).where(*self.scope(tenant, application, incident))).mappings().one())
            baseline = c.execute(select(baselines).where(baselines.c.tenant_id == tenant,
                baselines.c.application_id == application)).mappings().first()
        with self.engine.connect() as c:
            row["previous_runs"] = [dict(r) for r in c.execute(select(incident_runs).where(
                incident_runs.c.tenant_id==tenant,incident_runs.c.application_id==application,
                incident_runs.c.incident_id==incident).order_by(incident_runs.c.requested_at.desc()).limit(10)).mappings()]
        row["baseline"] = dict(baseline) if baseline else None
        row["request"] = json.loads(row["request"])
        row["result"] = self.store.artifact(tenant, application, row["result_ref"]) if row["result_ref"] else None
        evidence = row["result"] or {}
        if evidence.get("evidence_ref"):
            evidence = self.store.artifact(tenant, application, evidence["evidence_ref"])
        if evidence.get("baseline_ref"):
            ref = evidence["baseline_ref"]
            historical = self.store.artifact(tenant, application, ref)
            row["baseline"] = {"tenant_id":tenant, "application_id":application, "artifact_ref":ref,
                "state":"context_ready" if historical.get("baseline_ready") else "context_blocked"}
        return row

    def release(self, envelope):
        tenant, application = envelope["tenant_id"], envelope["application_id"]
        ref, = envelope["artifact_refs"]
        baseline = self.store.artifact(tenant, application, ref)
        ready = envelope["topic"] == "application.context.ready"
        if bool(baseline.get("baseline_ready")) != ready: raise ValueError("Baseline outcome mismatch")
        with write_transaction(self.engine) as c:
            app = self.lock_app(c, tenant, application)
            if c.execute(select(inbox).where(inbox.c.consumer == "incident-admission",
                inbox.c.event_id == envelope["event_id"])).first(): return False
            state = "context_ready" if ready else "context_blocked"
            if app["state"] != state or envelope.get("application_version", app["version"]) != app["version"]:
                raise ValueError("Stale context notification")
            old = c.execute(select(baselines).where(baselines.c.tenant_id == tenant,
                baselines.c.application_id == application)).first()
            if old is None:
                c.execute(insert(baselines).values(tenant_id=tenant, application_id=application,
                    state=state, artifact_ref=ref))
            waiting = c.execute(select(incidents).where(incidents.c.tenant_id == tenant,
                incidents.c.application_id == application, incidents.c.state == "waiting_for_context")).mappings().all()
            for row in waiting:
                c.execute(update(incidents).where(*self.scope(tenant, application, row["incident_id"])).values(
                    state="collection_queued" if ready else "context_blocked"))
                if ready: self.emit(c, row, "incident.collection.requested", [ref], envelope)
            c.execute(insert(inbox).values(consumer="incident-admission", event_id=envelope["event_id"]))
        return True

    def complete(self, envelope, consumer, expected, state, result, topic=None):
        tenant, application, incident = envelope["tenant_id"], envelope["application_id"], envelope["incident_id"]
        content = encode(result); digest = hashlib.sha256(content.encode()).hexdigest()
        with write_transaction(self.engine) as c:
            self.lock_app(c, tenant, application)
            if c.execute(select(inbox).where(inbox.c.consumer == consumer,
                inbox.c.event_id == envelope["event_id"])).first(): return False
            row = c.execute(select(incidents).where(*self.scope(tenant, application, incident))).mappings().one()
            if row["state"] != expected: raise ValueError("Stale incident stage")
            for ref in envelope.get("artifact_refs", []):
                if not c.execute(select(artifacts).where(artifacts.c.tenant_id == tenant,
                    artifacts.c.application_id == application, artifacts.c.artifact_id == ref)).first():
                    raise ValueError("Artifact outside application scope")
            if not c.execute(select(artifacts).where(artifacts.c.tenant_id == tenant,
                artifacts.c.application_id == application, artifacts.c.artifact_id == digest)).first():
                c.execute(insert(artifacts).values(tenant_id=tenant, application_id=application,
                    artifact_id=digest, content=content))
            c.execute(update(incidents).where(*self.scope(tenant, application, incident)).values(state=state, result_ref=digest))
            c.execute(insert(inbox).values(consumer=consumer, event_id=envelope["event_id"]))
            if topic: self.emit(c, row, topic, [digest], envelope)
        return True


class IncidentWorker:
    topics = {"application.context.ready": "incident-admission", "application.context.blocked": "incident-admission",
              "incident.collection.requested": "incident-collection", "incident.analysis.requested": "incident-analysis"}

    def __init__(self, store, collector, resolution_policies=None):
        self.store,self.collector=store,collector
        self.resolution_policies=resolution_policies or {}

    async def handle(self, envelope):
        from .telemetry import assess
        if envelope["schema_version"] != 1: raise ValueError("Unsupported schema")
        UUID(envelope["event_id"]); instant(envelope["created_at"])
        consumer = self.topics[envelope["topic"]]
        if self.store.store.consumed(consumer, envelope["event_id"]): return False
        if consumer == "incident-admission": return self.store.release(envelope)
        row = self.store.get(envelope["tenant_id"], envelope["application_id"], envelope["incident_id"])
        ref, = envelope["artifact_refs"]
        source = self.store.store.artifact(row["tenant_id"], row["application_id"], ref)
        if consumer == "incident-collection":
            if (row["state"] != "collection_queued" or not source.get("baseline_ready")
                    or not row["baseline"] or row["baseline"]["artifact_ref"] != ref):
                raise ValueError("Baseline or incident stage mismatch")
            config = self.store.store.application(row["tenant_id"], row["application_id"])["config"]
            result = await self.collector.collect(config, {key:row["request"][key] for key in ("service","window_start","window_end")})
            # Jaeger/Prometheus retention can expire between the original run and
            # a rerun. Preserve the prior evidence when every source has no match;
            # otherwise a refresh would turn a known assessment into an empty one.
            if not result.get("records") and envelope.get("previous_result_ref"):
                prior=self.store.store.artifact(row["tenant_id"],row["application_id"],envelope["previous_result_ref"])
                prior_ref=prior.get("evidence_ref")
                if prior_ref:
                    prior_evidence=self.store.store.artifact(row["tenant_id"],row["application_id"],prior_ref)
                    prior_evidence["refresh_status"]="no_matches_retained_prior_evidence"
                    prior_evidence["refresh_warning"]="The requested window is outside current source retention; prior evidence remains the active assessment."
                    result=prior_evidence
            result.update(incident_id=row["incident_id"], baseline_ref=ref)
            return self.store.complete(envelope, consumer, "collection_queued", "analysis_queued", result, "incident.analysis.requested")
        if source.get("incident_id") != row["incident_id"] or row["result_ref"] != ref:
            raise ValueError("Evidence does not belong to current incident stage")
        baseline = self.store.store.artifact(row["tenant_id"],row["application_id"],source["baseline_ref"])
        manifest = self.store.store.artifact(row["tenant_id"],row["application_id"],baseline["manifest_ref"]) if baseline.get("manifest_ref") else {}
        result = assess(source,request=row["request"],documents=manifest.get("documents",[]))
        result["evidence_ref"] = ref
        key="/".join((row["tenant_id"],row["application_id"],row["request"]["service"]))
        topic="incident.resolution.requested" if key in self.resolution_policies else None
        return self.store.complete(envelope, consumer, "analysis_queued", "resolution_queued" if topic else "assessed", result,topic)

    async def fail(self, envelope, reason):
        consumer = self.topics[envelope["topic"]]
        if consumer == "incident-admission":
            # Database failure must keep retrying delivery; it cannot be safely recorded as a business failure.
            raise RuntimeError("Context admission unavailable")
        return self.store.complete(envelope, consumer,
            "collection_queued" if consumer == "incident-collection" else "analysis_queued", "failed",
            {"reason": reason, "failed_stage": consumer, "resolution": {"status": "blocked"}})

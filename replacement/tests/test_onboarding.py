import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine,select

sys.path.insert(0,str(Path(__file__).parents[1]))
from kaims_next.handoff import Handoff,metadata,outbox
from kaims_next.discovery import DocumentDiscovery
from kaims_next.workers import OnboardingWorker


@pytest.fixture
def system(tmp_path):
    engine=create_engine("sqlite:///"+str(tmp_path/"state.db"))
    metadata.create_all(engine)
    root=tmp_path/"documents";root.mkdir()
    yield Handoff(engine),DocumentDiscovery({"docs":root}),root
    engine.dispose()


def event_for(store,topic):
    with store.engine.connect() as c:
        return json.loads(c.execute(select(outbox.c.envelope).where(outbox.c.topic==topic)).scalar_one())


@pytest.mark.asyncio
async def test_onboarding_discovers_real_file_then_commits_reference_only_baseline(system):
    store,discovery,root=system
    (root/"runbook.md").write_text("Check the connection pool before restarting the service.")
    store.onboard("tenant","app",{"document_sources":[{"id":"runbooks","root":"docs"}]})
    worker=OnboardingWorker(store,discovery)
    request=event_for(store,"application.discovery.requested")
    await worker.handle(request)
    assert store.application("tenant","app")["state"]=="context_queued"
    context=event_for(store,"application.context.requested")
    manifest=store.artifact("tenant","app",context["artifact_refs"][0])
    assert manifest["documents"][0]["content"].startswith("Check the connection pool")
    assert manifest["documents"][0]["observed_at"] is None
    assert "content" not in context
    await worker.handle(context)
    assert store.application("tenant","app")["state"]=="context_ready"
    assert not await worker.handle(request)
    ready=event_for(store,"application.context.ready")
    baseline=store.artifact("tenant","app",ready["artifact_refs"][0])
    assert baseline["incident_evidence_required"] is True
    assert "content" not in json.dumps(baseline)


@pytest.mark.asyncio
@pytest.mark.parametrize("sources,reason", [([],None),([{"id":"missing","root":"absent"}],"not_configured"),([{"id":"empty","root":"docs"}],"no_matches")])
async def test_missing_documents_reach_explicit_blocked_state(system,sources,reason):
    store,discovery,_=system
    store.onboard("t","a",{"document_sources":sources})
    worker=OnboardingWorker(store,discovery)
    await worker.handle(event_for(store,"application.discovery.requested"))
    await worker.handle(event_for(store,"application.context.requested"))
    assert store.application("t","a")["state"]=="context_blocked"
    blocked=event_for(store,"application.context.blocked")
    baseline=store.artifact("t","a",blocked["artifact_refs"][0])
    if reason: assert baseline["source_outcomes"][0]["status"]==reason


def test_discovery_rejects_traversal_and_ingestion_artifacts(system):
    _,discovery,root=system
    (root/"landing").mkdir();(root/"landing"/"alert.json").write_text('{"alert":"not evidence"}')
    result=discovery.collect({"document_sources":[{"id":"escape","root":"docs","path":".."},{"id":"scope","root":"docs"}]})
    assert result["sources"][0]["reason"]=="path_outside_configured_root"
    assert result["documents"]==[]


def test_size_limit_is_reported_instead_of_silently_declaring_complete(system):
    _,_,root=system
    (root/"large.txt").write_text("x"*100)
    discovery=DocumentDiscovery({"docs":root},max_file_bytes=10)
    result=discovery.collect({"document_sources":[{"id":"scope","root":"docs"}]})
    assert result["sources"][0]["status"]=="partial"
    assert result["sources"][0]["rejected"]==1


@pytest.mark.asyncio
async def test_uncommitted_stage_is_not_acknowledged(system):
    store,discovery,_=system
    class Message:
        body=b'{"schema_version":99}'
        routing_key="application.discovery.requested"
        acknowledged=False
        async def ack(self): self.acknowledged=True
    message=Message()
    with pytest.raises(ValueError): await OnboardingWorker(store,discovery).delivery(message)
    assert not message.acknowledged

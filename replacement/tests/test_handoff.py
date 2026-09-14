import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine,select,event

spec=importlib.util.spec_from_file_location("next_handoff",Path(__file__).parents[1]/"kaims_next/handoff.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@pytest.fixture
def store(tmp_path):
    engine=create_engine("sqlite:///"+str(tmp_path/"next.db"))
    m.metadata.create_all(engine)
    yield m.Handoff(engine)
    engine.dispose()


def pending(store):
    with store.engine.connect() as c:
        return [json.loads(r) for r in c.execute(select(m.outbox.c.envelope).where(m.outbox.c.published==0)).scalars()]


def test_onboarding_saves_one_discovery_request_and_rejects_changed_duplicate(store):
    assert store.onboard("t","a",{"document_roots":["configured-repository"]})
    assert not store.onboard("t","a",{"document_roots":["configured-repository"]})
    assert len(pending(store))==1
    assert pending(store)[0]["topic"]=="application.discovery.requested"
    with pytest.raises(ValueError): store.onboard("t","a",{"document_roots":[]})


def test_database_failure_rolls_back_registration_and_event(store):
    def fail(conn,cursor,statement,parameters,context,executemany):
        if statement.startswith("INSERT INTO next_outbox"):
            raise RuntimeError("simulated disk failure")
    event.listen(store.engine,"before_cursor_execute",fail)
    try:
        with pytest.raises(RuntimeError): store.onboard("t","a",{})
    finally:
        event.remove(store.engine,"before_cursor_execute",fail)
    with store.engine.connect() as c:
        assert c.execute(select(m.applications)).first() is None
    assert pending(store)==[]


@pytest.mark.asyncio
async def test_broker_outage_preserves_pending_request_across_restart(store):
    store.onboard("t","a",{})
    async def unavailable(*args): raise ConnectionError("broker offline")
    with pytest.raises(ConnectionError): await store.dispatch(unavailable)
    restarted=m.Handoff(store.engine)
    delivered=[]
    async def publish(topic,envelope): delivered.append(envelope)
    assert await restarted.dispatch(publish)==1
    assert delivered[0]["event_id"]
    assert pending(restarted)==[]


def test_duplicate_after_commit_does_not_repeat_transition_or_copy_context(store):
    store.onboard("t","a",{})
    request=pending(store)[0]
    args=dict(expected_state="discovery_queued",next_state="context_queued",
              next_topic="application.context.requested",result={"source":"runbooks","status":"no_matches"})
    assert store.complete("discovery",request,**args)
    assert not m.Handoff(store.engine).complete("discovery",request,**args)
    successor=[e for e in pending(store) if e["topic"]=="application.context.requested"][0]
    assert successor["causation_id"]==request["event_id"]
    assert "result" not in successor
    assert store.artifact("t","a",successor["artifact_refs"][0])["status"]=="no_matches"
    with store.engine.connect() as c:
        assert len(c.execute(select(m.artifacts)).all())==1


def test_cross_application_reference_cannot_be_used(store):
    store.onboard("t","a",{})
    request=pending(store)[0]
    store.complete("discovery",request,expected_state="discovery_queued",next_state="context_queued",
                   next_topic="application.context.requested",result={"document":"owned by a"})
    ref=[e for e in pending(store) if e["topic"]=="application.context.requested"][0]["artifact_refs"][0]
    store.onboard("other","b",{})
    forged=[e for e in pending(store) if e["application_id"]=="b"][0]
    forged["artifact_refs"]=[ref]
    with pytest.raises(ValueError,match="scope"):
        store.complete("discovery",forged,expected_state="discovery_queued",next_state="context_queued",
                       next_topic="application.context.requested",result={})


def test_stale_stage_cannot_overwrite_context_readiness(store):
    store.onboard("t","a",{})
    request=pending(store)[0]
    with pytest.raises(ValueError,match="Unexpected stage"):
        store.complete("context",request,expected_state="context_queued",next_state="ready",next_topic=None,result={})

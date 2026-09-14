import asyncio
import json
import sys
from pathlib import Path
import httpx
import pytest
from sqlalchemy import create_engine, select
sys.path.insert(0,str(Path(__file__).parents[1]))
from kaims_next.handoff import Handoff, metadata, outbox
from kaims_next.incidents import IncidentStore, IncidentWorker
from kaims_next.discovery import DocumentDiscovery
from kaims_next.workers import OnboardingWorker
from kaims_next.telemetry import TelemetryCollector, assess

REQUEST = {"service":"gateway", "window_start":"2026-09-01T10:00:00Z", "window_end":"2026-09-01T10:10:00Z"}
RECORD = {"service":"gateway", "observed_at":"2026-09-01T10:05:00Z", "kind":"metric",
          "metric":"error_rate_ratio", "value":0.2, "source_uri":"metric://fixture/errors"}


def setup(tmp_path, docs=True):
    engine=create_engine("sqlite:///"+str(tmp_path/"state.db"))
    metadata.create_all(engine)
    store=Handoff(engine)
    root=tmp_path/"docs";root.mkdir()
    if docs: (root/"runbook.md").write_text("Reference only")
    store.onboard("t","a",{"document_sources":[{"id":"docs","root":"docs"}],
                           "services":["gateway"],"telemetry_sources":["metrics"]})
    return store,IncidentStore(store),OnboardingWorker(store,DocumentDiscovery({"docs":root}))


def pending(store, topic):
    with store.engine.connect() as c:
        return json.loads(c.execute(select(outbox.c.envelope).where(outbox.c.topic==topic)).scalar_one())


async def baseline(store, onboarding):
    await onboarding.handle(pending(store,"application.discovery.requested"))
    await onboarding.handle(pending(store,"application.context.requested"))


def test_waiting_incident_released_and_assessed_once(tmp_path):
    async def run():
        store,inc,onboarding=setup(tmp_path)
        inc.admit("t","a","i",REQUEST)
        assert inc.get("t","a","i")["state"]=="waiting_for_context"
        assert inc.admit("t","a","i",REQUEST) is False
        with pytest.raises(ValueError): inc.admit("t","a","i",{**REQUEST,"window_end":"2026-09-01T10:11:00Z"})
        await baseline(store,onboarding)
        # Admission before ready notification processing is still released correctly.
        inc.admit("t","a","j",REQUEST)
        transport=httpx.MockTransport(lambda request:httpx.Response(200,json={"records":[RECORD]}))
        worker=IncidentWorker(inc,TelemetryCollector({"metrics":{"url":"https://fixture.test/records"}},transport=transport))
        ready=pending(store,"application.context.ready")
        assert await worker.handle(ready)
        assert not await worker.handle(ready)
        inc.admit("t","a","k",REQUEST)
        assert inc.get("t","a","k")["state"]=="collection_queued"
        with store.engine.connect() as c:
            envelopes=[json.loads(row[0]) for row in c.execute(select(outbox.c.envelope).where(outbox.c.topic=="incident.collection.requested"))]
        for envelope in envelopes:
            assert await worker.handle(envelope)
            assert not await worker.handle(envelope)
        with store.engine.connect() as c:
            envelopes=[json.loads(row[0]) for row in c.execute(select(outbox.c.envelope).where(outbox.c.topic=="incident.analysis.requested"))]
        for envelope in envelopes:
            assert await worker.handle(envelope)
            assert not await worker.handle(envelope)
        result=inc.get("t","a","i")
        assert result["state"]=="assessed"
        assert result["result"]["impact"]["status"]=="observed_service_errors"
        assert result["result"]["impact"]["business_impact"]=="not_established"
        assert result["result"]["rca"]["confirmed_cause"] is None
        assert result["result"]["resolution"]["status"]=="blocked"
    asyncio.run(run())


def test_blocked_baseline_releases_waiters_to_explicit_block(tmp_path):
    async def run():
        store,inc,onboarding=setup(tmp_path,False)
        inc.admit("t","a","i",REQUEST)
        await baseline(store,onboarding)
        worker=IncidentWorker(inc,TelemetryCollector({}))
        await worker.handle(pending(store,"application.context.blocked"))
        inc.admit("t","a","j",REQUEST)
        assert all(inc.get("t","a",i)["state"]=="context_blocked" for i in ("i","j"))
    asyncio.run(run())


@pytest.mark.parametrize("changed",[
    {"observed_at":"2026-08-01T10:05:00Z"}, {"observed_at":"2026-09-01T10:05:00"},
    {"service":"other"}, {"source_uri":"log:///data/landing/alert.json"},
    {"source_uri":"document://docs/runbook"}, {"value":True}, {"value":2}, {"observed_at":None}])
def test_invalid_operational_evidence_is_rejected(changed):
    with pytest.raises((ValueError,TypeError,AttributeError)):
        TelemetryCollector({}).validate({**RECORD,**changed},"metrics",REQUEST)


def test_timeout_empty_and_bad_source_are_explicit():
    async def run():
        async def respond(request):
            if request.url.host=="timeout.test": raise httpx.ReadTimeout("timeout")
            if request.url.host=="bad.test": return httpx.Response(503)
            return httpx.Response(200,json={"records":[]})
        collector=TelemetryCollector({s:{"url":"https://"+s+".test/records"} for s in ("timeout","bad","empty")},transport=httpx.MockTransport(respond))
        evidence=await collector.collect({"telemetry_sources":["timeout","bad","empty","missing"]},REQUEST)
        assert [s["status"] for s in evidence["source_outcomes"]]==["timed_out","failed","no_matches","not_configured"]
        assert assess(evidence)["impact"]["status"]=="not_established"
    asyncio.run(run())


def test_failed_dependency_is_hypothesis_not_confirmed_cause():
    trace=TelemetryCollector({}).validate({"kind":"trace","service":"gateway","observed_at":RECORD["observed_at"],
        "source_uri":"trace://fixture/123","trace_id":"t","span_id":"s","peer_service":"database","error":True},"traces",REQUEST)
    result=assess({"records":[trace],"source_outcomes":[]})
    assert result["rca"]["status"]=="hypotheses_only"
    assert result["rca"]["confirmed_cause"] is None
    assert result["impact"]["status"]=="observed_failed_spans"
    assert result["impact"]["customer_impact"]=="not_established"
    assert result["impact"]["business_impact"]=="not_established"


def test_incident_window_and_service_membership_enforced(tmp_path):
    _,inc,_=setup(tmp_path)
    for request in ({**REQUEST,"service":"foreign"},{**REQUEST,"window_end":"2026-09-01T09:00:00Z"},
                    {**REQUEST,"window_end":"2026-09-03T10:00:00Z"}):
        with pytest.raises(ValueError): inc.admit("t","a","i",request)


def test_cross_incident_evidence_cannot_drive_analysis(tmp_path):
    async def run():
        store,inc,onboarding=setup(tmp_path)
        await baseline(store,onboarding)
        worker=IncidentWorker(inc,TelemetryCollector({}))
        await worker.handle(pending(store,"application.context.ready"))
        inc.admit("t","a","i",REQUEST)
        await worker.handle(pending(store,"incident.collection.requested"))
        envelope=pending(store,"incident.analysis.requested")
        inc.admit("t","a","other",REQUEST)
        from uuid import uuid4
        bad={**envelope,"event_id":str(uuid4()),"incident_id":"other"}
        with pytest.raises(ValueError): await worker.handle(bad)
        assert inc.get("t","a","other")["state"]=="collection_queued"
        assert await worker.handle(envelope)
        assert inc.get("t","a","i")["result"]["impact"]["status"]=="not_established"
    asyncio.run(run())


def test_exhausted_collection_persists_terminal_failure(tmp_path):
    async def run():
        store,inc,onboarding=setup(tmp_path)
        await baseline(store,onboarding)
        worker=IncidentWorker(inc,TelemetryCollector({}))
        await worker.handle(pending(store,"application.context.ready"))
        inc.admit("t","a","i",REQUEST)
        envelope=pending(store,"incident.collection.requested")
        assert await worker.fail(envelope,"TimeoutError")
        assert not await worker.fail(envelope,"TimeoutError")
        assert inc.get("t","a","i")["state"]=="failed"
    asyncio.run(run())


def test_oversized_response_rejected_before_assessment():
    async def run():
        transport=httpx.MockTransport(lambda request:httpx.Response(200,json={"records":[RECORD]}))
        collector=TelemetryCollector({"m":{"url":"https://fixture.test/records"}},transport=transport,max_bytes=10)
        result=await collector.collect({"telemetry_sources":["m"]},REQUEST)
        assert result["source_outcomes"][0]["status"]=="failed"
        assert result["records"]==[]
    asyncio.run(run())


def test_incident_admission_rolls_back_if_outbox_fails(tmp_path):
    async def run():
        from sqlalchemy import event
        store,inc,onboarding=setup(tmp_path)
        await baseline(store,onboarding)
        worker=IncidentWorker(inc,TelemetryCollector({}))
        await worker.handle(pending(store,"application.context.ready"))
        def reject_insert(connection,cursor,statement,parameters,context,executemany):
            if statement.startswith("INSERT INTO next_outbox"):
                raise RuntimeError("Synthetic persistence failure")
        event.listen(store.engine,"before_cursor_execute",reject_insert)
        try:
            with pytest.raises(RuntimeError): inc.admit("t","a","i",REQUEST)
        finally: event.remove(store.engine,"before_cursor_execute",reject_insert)
        from sqlalchemy.exc import NoResultFound
        with pytest.raises(NoResultFound): inc.get("t","a","i")
        assert inc.admit("t","a","i",REQUEST)
    asyncio.run(run())

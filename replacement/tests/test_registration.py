import asyncio
import json
import pytest
from sqlalchemy import select, event as sql_event
from test_incidents import setup, baseline, pending, REQUEST
from kaims_next.registration import revise, revisions
from kaims_next.handoff import outbox


def test_revision_rediscovers_with_version_checks_and_preserves_snapshots(tmp_path):
    async def run():
        store, incidents, worker = setup(tmp_path)
        await baseline(store, worker)
        old = store.application("t", "a")
        config = {**old["config"], "services":["gateway","worker"]}
        with pytest.raises(ValueError, match="pending discovery"):
            revise(store, "t", "a", old["version"], config)
        incidents.release(pending(store, "application.context.ready"))
        def fail(conn,cursor,statement,parameters,context,executemany):
            if statement.startswith("INSERT INTO next_outbox"): raise RuntimeError("disk failure")
        sql_event.listen(store.engine,"before_cursor_execute",fail)
        try:
            with pytest.raises(RuntimeError): revise(store,"t","a",old["version"],config)
        finally: sql_event.remove(store.engine,"before_cursor_execute",fail)
        assert store.application("t","a")==old
        assert revise(store,"t","a",old["version"],config)
        with pytest.raises(ValueError,match="changed"):
            revise(store,"t","a",old["version"],config)
        with store.engine.connect() as c:
            snapshots=c.execute(select(revisions).where(revisions.c.tenant_id=="t")).mappings().all()
        assert [json.loads(s["config"])["services"] for s in snapshots]==[["gateway"],["gateway","worker"]]
        incidents.admit("t","a","new",REQUEST)
        assert incidents.get("t","a","new")["state"]=="waiting_for_context"
        for topic in ["application.discovery.requested","application.context.requested","application.context.ready"]:
            with store.engine.connect() as c:
                envelopes=[json.loads(raw) for raw in c.execute(select(outbox.c.envelope).where(outbox.c.topic==topic)).scalars()]
            for envelope in envelopes:
                if topic.endswith("ready"): incidents.release(envelope)
                else: await worker.handle(envelope)
        assert incidents.get("t","a","new")["state"]=="collection_queued"
        now=store.application("t","a")
        assert not revise(store,"t","a",now["version"],config)
        with pytest.raises(ValueError,match="active investigations"):
            revise(store,"t","a",now["version"],old["config"])
    asyncio.run(run())


def test_registration_api_requires_auth_and_checks_catalog(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock
    from kaims_next import runtime
    store,incidents,worker=setup(tmp_path)
    asyncio.run(baseline(store,worker))
    incidents.release(pending(store,"application.context.ready"))
    roots=tmp_path/"roots.json"; roots.write_text(json.dumps({"docs":str(tmp_path/"docs")}))
    sources=tmp_path/"sources.json";sources.write_text(json.dumps({"metrics":{"url":"http://unused"}}))
    monkeypatch.setenv("NEXT_API_TOKEN","x"*32);monkeypatch.setenv("NEXT_TENANT_ID","t")
    monkeypatch.setenv("NEXT_DATABASE_URL","sqlite:///"+str(tmp_path/"state.db"))
    monkeypatch.setenv("NEXT_DOCUMENT_ROOTS_FILE",str(roots));monkeypatch.setenv("NEXT_TELEMETRY_SOURCES_FILE",str(sources))
    monkeypatch.setenv("NEXT_RABBITMQ_URL","amqp://unused");monkeypatch.delenv("NEXT_AUTO_INCIDENT_APPLICATIONS",raising=False)
    monkeypatch.setattr(runtime.aio_pika,"connect_robust",AsyncMock(side_effect=ConnectionError()))
    old=store.application("t","a")
    payload={"application_id":"a","expected_version":old["version"],**old["config"],"services":["gateway","worker"]}
    headers={"Authorization":"Bearer "+"x"*32}
    with TestClient(runtime.create_app()) as client:
        assert client.put("/applications/a",json=payload).status_code==401
        assert client.put("/applications/a",json={**payload,"expected_version":1},headers=headers).status_code==409
        assert client.put("/applications/a",json={**payload,"telemetry_sources":["unknown"]},headers=headers).status_code==409
        assert client.put("/applications/a",json={**payload,"document_sources":[{"id":"d","root":"docs","path":".."}]},headers=headers).status_code==409
        assert client.put("/applications/foreign",json={**payload,"application_id":"foreign"},headers=headers).status_code==404
        result=client.put("/applications/a",json=payload,headers=headers)
        assert result.status_code==202
        assert result.json()["state"]=="discovery_queued"
        assert result.json()["config"]["services"]==["gateway","worker"]

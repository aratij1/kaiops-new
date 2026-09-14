import asyncio
import json
import pytest
from sqlalchemy import select, update
from test_incidents import setup, baseline, pending, REQUEST
from kaims_next.handoff import outbox, artifacts
from kaims_next.maintenance import refresh_documents


def test_offline_refresh_rebuilds_baseline_and_preserves_history(tmp_path):
    async def run():
        store, incidents, worker = setup(tmp_path)
        await baseline(store, worker)
        incidents.release(pending(store, "application.context.ready"))
        old = store.application("t", "a")
        with pytest.raises(ValueError, match="pending"):
            refresh_documents(store, "t", "a")
        with store.engine.begin() as c:
            c.execute(update(outbox).values(published=1))
            old_artifacts = set(c.execute(select(artifacts.c.artifact_id)).scalars())
        (tmp_path/"docs"/"new.md").write_text("New historical reference")
        refresh_documents(store, "t", "a")
        assert store.application("t", "a")["config"] == old["config"]
        incidents.admit("t", "a", "new", REQUEST)
        assert incidents.get("t", "a", "new")["state"] == "waiting_for_context"
        with pytest.raises(ValueError, match="already"):
            refresh_documents(store, "t", "a")
        for topic in ["application.discovery.requested", "application.context.requested", "application.context.ready"]:
            with store.engine.connect() as c:
                envelopes = [json.loads(raw) for raw in c.execute(select(outbox.c.envelope).where(outbox.c.topic == topic)).scalars()]
            for envelope in envelopes:
                if topic.endswith("ready"): incidents.release(envelope)
                else: await worker.handle(envelope)
        current = incidents.get("t", "a", "new")
        assert current["state"] == "collection_queued"
        context = store.artifact("t", "a", current["baseline"]["artifact_ref"])
        assert len(context["document_refs"]) == 2
        with store.engine.connect() as c:
            assert old_artifacts <= set(c.execute(select(artifacts.c.artifact_id)).scalars())
        with pytest.raises(ValueError, match="active incident"):
            refresh_documents(store, "t", "a")
    asyncio.run(run())

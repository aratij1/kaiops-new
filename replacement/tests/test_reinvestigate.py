import asyncio,json
import pytest,httpx
from sqlalchemy import select
from test_incidents import setup,baseline,pending,REQUEST,RECORD
from kaims_next.handoff import outbox
from kaims_next.incidents import IncidentWorker
from kaims_next.telemetry import TelemetryCollector


def test_rerun_retains_results_and_uses_documents(tmp_path):
    async def run():
        store,inc,onboarding=setup(tmp_path)
        (tmp_path/"docs"/"runbook.md").write_text("Gateway reference: confirm failed calls before remediation.")
        await baseline(store,onboarding);inc.release(pending(store,"application.context.ready"))
        worker=IncidentWorker(inc,TelemetryCollector({"metrics":{"url":"https://fixture.test"}},transport=httpx.MockTransport(lambda r:httpx.Response(200,json={"records":[RECORD]}))))
        inc.admit("t","a","i",REQUEST)
        async def drain():
            for topic in ["incident.collection.requested","incident.analysis.requested"]:
                with store.engine.connect() as c:
                    envelopes=[json.loads(raw) for raw in c.execute(select(outbox.c.envelope).where(outbox.c.topic==topic)).scalars()]
                for envelope in envelopes:await worker.handle(envelope)
        await drain();old=inc.get("t","a","i")
        assert old["result"]["rca"]["reference_context"][0]["authority"]=="reference_only"
        assert old["result"]["impact"]["summary"]
        assert old["result"]["rca"]["confirmed_cause"] is None
        with pytest.raises(ValueError):inc.reinvestigate("t","a","i","f"*64)
        inc.reinvestigate("t","a","i",old["result_ref"])
        with pytest.raises(ValueError):inc.reinvestigate("t","a","i",old["result_ref"])
        await drain();new=inc.get("t","a","i")
        assert new["state"]=="assessed"
        assert new["previous_runs"][0]["previous_result_ref"]==old["result_ref"]
        assert store.artifact("t","a",old["result_ref"])==old["result"]
        assert new["request"]==old["request"]
        evidence_ref=new["result"]["evidence_ref"]
        inc.reinvestigate("t","a","i",new["result_ref"],mode="reanalyze")
        assert inc.get("t","a","i")["state"]=="analysis_queued"
        await drain()
        assert inc.get("t","a","i")["result"]["evidence_ref"]==evidence_ref
    asyncio.run(run())

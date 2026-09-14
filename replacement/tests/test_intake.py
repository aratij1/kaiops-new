import asyncio
from datetime import datetime,timezone,timedelta
from test_incidents import setup,baseline,pending
from kaims_next.intake import AlertIntake
from kaims_next.incidents import IncidentWorker
from kaims_next.telemetry import TelemetryCollector


def test_intake_is_durable_and_deduplicated_across_restart(tmp_path):
    async def run():
        store,inc,onboarding=setup(tmp_path)
        now=datetime.now(timezone.utc)
        alert={"state":"firing","fingerprint":"a"*64,"active_at":(now-timedelta(minutes=1)).isoformat(),"service":"gateway","name":"GatewayErrors","severity":"critical","source_id":"metrics"}
        async def collect(config,endpoints):return {"checked_at":now.isoformat(),"status":"collected","source_outcomes":[],"alerts":[alert]}
        first=await AlertIntake(inc,{},collect).scan("t","a")
        assert first["created"]==1
        incident_id=first["incident_ids"][0]
        assert inc.get("t","a",incident_id)["state"]=="waiting_for_context"
        assert (await AlertIntake(inc,{},collect).scan("t","a"))["existing"]==1
        await baseline(store,onboarding)
        worker=IncidentWorker(inc,TelemetryCollector({}))
        await worker.handle(pending(store,"application.context.ready"))
        await worker.handle(pending(store,"incident.collection.requested"))
        await worker.handle(pending(store,"incident.analysis.requested"))
        result=inc.get("t","a",incident_id)
        assert result["state"]=="assessed"
        assert result["request"]["origin"]["name"]=="GatewayErrors"
        assert result["result"]["rca"]["confirmed_cause"] is None
        alert["active_at"]=(now-timedelta(seconds=20)).isoformat()
        assert (await AlertIntake(inc,{},collect).scan("t","a"))["created"]==1
    asyncio.run(run())


def test_pending_and_invalid_activation_do_not_create_incidents(tmp_path):
    async def run():
        _,inc,_=setup(tmp_path)
        async def collect(config,endpoints):return {"checked_at":"now","status":"partial_or_unavailable","source_outcomes":[],"alerts":[{"state":"pending"},{"state":"firing","active_at":None}]}
        result=await AlertIntake(inc,{},collect).scan("t","a")
        assert result["created"]==0 and result["skipped"]==2
    asyncio.run(run())

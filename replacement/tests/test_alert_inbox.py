import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
import asyncio,hashlib
from sqlalchemy import create_engine
from kaims_next.handoff import Handoff,metadata,encode
from kaims_next.incidents import IncidentStore,instant
from kaims_next.alert_inbox import snapshot


def test_alert_links_scoped_and_application_pages(tmp_path):
    async def run():
        store=Handoff(create_engine("sqlite:///"+str(tmp_path/"db")));metadata.create_all(store.engine)
        for name in ["a","b","c","d","e"]:store.onboard("t",name,{"services":["gateway"]})
        store.onboard("foreign","hidden",{"services":["gateway"]})
        alert={"fingerprint":"a"*64,"active_at":"2026-09-01T10:00:00Z","name":"Latency","service":"gateway","state":"firing","severity":"critical","source_id":"metrics"}
        identifier="alert-"+hashlib.sha256(encode([alert["fingerprint"],instant(alert["active_at"]).isoformat()]).encode()).hexdigest()[:32]
        IncidentStore(store).admit("t","a",identifier,{"service":"gateway","window_start":"2026-09-01T10:00:00Z","window_end":"2026-09-01T10:02:00Z"})
        async def collect(config,endpoints):return {"status":"collected","source_outcomes":[],"alerts":[alert]}
        data=await snapshot(store,"t",{},collect=collect)
        assert data["next"]=="d"
        assert len(data["items"])==4
        assert data["items"][0]["incident_id"]==identifier
        assert all(r["incident_id"] is None for r in data["items"][1:])
        last=await snapshot(store,"t",{},after="d",collect=collect)
        assert [a["application_id"] for a in last["applications"]]==["e"]
        assert last["next"] is None
        assert not (await snapshot(store,"t",{},application_id="hidden",collect=collect))["items"]
    asyncio.run(run())

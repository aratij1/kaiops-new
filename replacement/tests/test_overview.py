import asyncio
import httpx
from sqlalchemy.exc import NoResultFound
import pytest
from test_incidents import setup,baseline,REQUEST,pending
from kaims_next.overview import overview
from kaims_next.live_alerts import live_alerts
from kaims_next.incidents import IncidentWorker
from kaims_next.telemetry import TelemetryCollector


def test_overview_documents_counts_and_tenant_scope(tmp_path):
    async def run():
        store,inc,worker=setup(tmp_path)
        await baseline(store,worker)
        await IncidentWorker(inc,TelemetryCollector({})).handle(pending(store,"application.context.ready"))
        inc.admit("t","a","i",REQUEST)
        data=overview(store,"t","a",{"metrics":{"url":"https://private","headers":{"secret":"hidden"}}})
        assert data["incidents"]["in_progress"]==1
        assert len(data["documents"])==1
        assert "content" not in data["documents"][0]
        assert data["health"]["status"]=="unknown"
        assert "https://private" not in str(data) and "hidden" not in str(data)
        with pytest.raises(NoResultFound):overview(store,"foreign","a",{})
    asyncio.run(run())


def test_alerts_require_service_and_scope_labels():
    async def run():
        rows=[{"labels":{"service":"gateway","environment":"prod","alertname":"Errors"},"state":"firing"},
              {"labels":{"service":"gateway","environment":"dev"},"state":"firing"},
              {"labels":{"service":"other","environment":"prod"},"state":"firing"},
              {"labels":{"service":"gateway"},"state":"firing"}]
        transport=httpx.MockTransport(lambda r:httpx.Response(200,json={"status":"success","data":{"alerts":rows}}))
        data=await live_alerts({"services":["gateway"],"telemetry_sources":["p"]},{"p":{"type":"prometheus","url":"https://fixture.test","service_label":"service","labels":{"environment":"prod"}}},transport)
        assert len(data["alerts"])==1
        assert data["source_outcomes"][0]["excluded_outside_scope"]==3
    asyncio.run(run())


def test_alert_failure_not_empty_success():
    async def run():
        data=await live_alerts({"services":["a"],"telemetry_sources":["p"]},{"p":{"type":"prometheus","url":"https://fixture.test"}},httpx.MockTransport(lambda r:httpx.Response(503)))
        assert data["status"]=="partial_or_unavailable"
        assert data["source_outcomes"][0]["status"]=="failed"
        assert (await live_alerts({"telemetry_sources":[]},{}))["status"]=="not_configured"
    asyncio.run(run())


def test_alert_scope_can_differ_from_metric_only_labels():
    async def run():
        rows=[{"labels":{"service":"gateway","application":"KaiMS","environment":"prod","alertname":"Disconnected"},"state":"firing"},
              {"labels":{"service":"gateway","application":"Other","environment":"prod"},"state":"firing"}]
        transport=httpx.MockTransport(lambda r:httpx.Response(200,json={"status":"success","data":{"alerts":rows}}))
        endpoint={"type":"prometheus","url":"https://fixture.test","service_label":"service", "labels":{"application":"KaiMS","environment":"prod","job":"kaims","tenant":"default"},"alert_labels":{"application":"KaiMS","environment":"prod"}}
        data=await live_alerts({"services":["gateway"],"telemetry_sources":["p"]},{"p":endpoint},transport)
        assert len(data["alerts"])==1
        assert data["alerts"][0]["name"]=="Disconnected"
        assert endpoint["labels"]["tenant"]=="default"
    asyncio.run(run())

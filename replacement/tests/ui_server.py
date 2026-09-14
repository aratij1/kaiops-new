"""Disposable real API/SQLite fixture for browser verification; no live mutations."""
import asyncio,json,os,socket,sys,tempfile
from pathlib import Path
from unittest.mock import AsyncMock
import httpx,uvicorn
from sqlalchemy import create_engine,select
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kaims_next import runtime
from kaims_next.handoff import Handoff,metadata,outbox
from kaims_next.incidents import IncidentStore,IncidentWorker
from kaims_next.workers import OnboardingWorker
from kaims_next.discovery import DocumentDiscovery
from kaims_next.telemetry import TelemetryCollector

async def seed(directory,database):
    engine=create_engine(database);metadata.create_all(engine);store=Handoff(engine)
    docs=Path(directory)/"documents";docs.mkdir();(docs/"runbook.md").write_text("Synthetic runbook")
    store.onboard("ui-test","fixture-app",{"document_sources":[{"id":"docs","root":"docs"}],"services":["gateway"],"telemetry_sources":["fixture-source"]})
    worker=OnboardingWorker(store,DocumentDiscovery({"docs":docs}))
    def pending(topic):
        with engine.connect() as c: return json.loads(c.execute(select(outbox.c.envelope).where(outbox.c.topic==topic)).scalar_one())
    await worker.handle(pending("application.discovery.requested"));await worker.handle(pending("application.context.requested"))
    inc=IncidentStore(store)
    stamp="2026-09-01T10:05:00Z"
    records=[{"service":"gateway","observed_at":stamp,"kind":"metric","metric":"error_rate_ratio","value":0.2,"source_uri":"metric://fixture/errors"},
        {"service":"gateway","observed_at":stamp,"kind":"log","source_uri":"log://fixture/1","message":"</pre><script>window.injected=true</script>"}]
    collector=TelemetryCollector({"fixture-source":{"url":"https://fixture.test"}},transport=httpx.MockTransport(lambda r:httpx.Response(200,json={"records":records})))
    incident_worker=IncidentWorker(inc,collector)
    await incident_worker.handle(pending("application.context.ready"))
    inc.admit("ui-test","fixture-app","assessed-example",{"service":"gateway","window_start":"2026-09-01T10:00:00Z","window_end":"2026-09-01T10:10:00Z"})
    await incident_worker.handle(pending("incident.collection.requested"));await incident_worker.handle(pending("incident.analysis.requested"))
    store.onboard("another-tenant","hidden-application",{"services":[]})
    engine.dispose()
    return docs

with tempfile.TemporaryDirectory() as directory:
    database="sqlite:///"+str(Path(directory)/"state.db")
    docs=asyncio.run(seed(directory,database))
    roots=Path(directory)/"roots.json";roots.write_text(json.dumps({"docs":str(docs)}))
    sources=Path(directory)/"sources.json";sources.write_text(json.dumps({"fixture-source":{"url":"https://fixture.test","headers":{"Authorization":"do-not-display"}}}))
    os.environ.update(NEXT_TENANT_ID="ui-test",NEXT_API_TOKEN="ui-fixture-token-"+"x"*32,NEXT_DATABASE_URL=database,
        NEXT_DOCUMENT_ROOTS_FILE=str(roots),NEXT_TELEMETRY_SOURCES_FILE=str(sources),NEXT_RABBITMQ_URL="amqp://unused")
    runtime.aio_pika.connect_robust=AsyncMock(side_effect=ConnectionError())
    sock=socket.socket();sock.bind(("127.0.0.1",0));sock.listen(128)
    print(json.dumps({"port":sock.getsockname()[1]}),flush=True)
    server=uvicorn.Server(uvicorn.Config(runtime.create_app(),log_level="error"))
    server.run(sockets=[sock])

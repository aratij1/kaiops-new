"""Real broker contract check in unique queues; no application messages consumed."""
import json
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sources={name:(root/"kaims_next"/(name+".py")).read_text() for name in ("handoff","rabbitmq","discovery","workers","consumer","incidents","native_telemetry","jaeger","telemetry","live_alerts","intake")}
runner = r"""
import asyncio,json,sys,tempfile,types
from pathlib import Path
from uuid import uuid4
import aio_pika
from sqlalchemy import create_engine,select
from common.config import get_settings
sources=json.load(sys.stdin)
core=types.ModuleType('handoff');exec(sources['handoff'],core.__dict__)
broker=types.ModuleType('next_broker');exec(sources['rabbitmq'],broker.__dict__)
package=types.ModuleType('kaims_next');package.__path__=[];sys.modules['kaims_next']=package
sys.modules['kaims_next.handoff']=core
incidents=types.ModuleType('kaims_next.incidents');sys.modules['kaims_next.incidents']=incidents;exec(sources['incidents'],incidents.__dict__)
native=types.ModuleType('kaims_next.native_telemetry');sys.modules['kaims_next.native_telemetry']=native;exec(sources['native_telemetry'],native.__dict__)
jaeger=types.ModuleType('kaims_next.jaeger');sys.modules['kaims_next.jaeger']=jaeger;exec(sources['jaeger'],jaeger.__dict__)
telemetry=types.ModuleType('kaims_next.telemetry');sys.modules['kaims_next.telemetry']=telemetry;exec(sources['telemetry'],telemetry.__dict__)
discovery=types.ModuleType('kaims_next.discovery');sys.modules['kaims_next.discovery']=discovery;exec(sources['discovery'],discovery.__dict__)
workers=types.ModuleType('kaims_next.workers');exec(sources['workers'],workers.__dict__)
consumers=types.ModuleType('next_consumer');exec(sources['consumer'],consumers.__dict__)
live=types.ModuleType('kaims_next.live_alerts');sys.modules['kaims_next.live_alerts']=live;exec(sources['live_alerts'],live.__dict__)
intake=types.ModuleType('kaims_next.intake');sys.modules['kaims_next.intake']=intake;exec(sources['intake'],intake.__dict__)
from datetime import datetime,timezone
class FixtureClock(datetime):
 @classmethod
 def now(cls,tz=None): return datetime(2026,9,1,10,6,tzinfo=timezone.utc)
intake.datetime=FixtureClock
async def main():
 namespace='kaims-next-contract-'+uuid4().hex
 connection=await aio_pika.connect_robust(get_settings().rabbitmq_url,timeout=10)
 queues={}
 recovery=[]
 try:
  with tempfile.TemporaryDirectory() as directory:
   engine=create_engine('sqlite:///'+str(Path(directory)/'state.db'))
   core.metadata.create_all(engine)
   store=core.Handoff(engine)
   docs=Path(directory)/'docs';docs.mkdir();(docs/'runbook.md').write_text('Synthetic contract-test document')
   collector=discovery.DocumentDiscovery({'fixture':docs})
   worker=workers.OnboardingWorker(store,collector)
   store.onboard('contract-test','fixture-app',{'document_sources':[{'id':'runbooks','root':'fixture'}],'services':['fixture-service'],'telemetry_sources':['fixture-telemetry','fixture-prometheus','fixture-loki','fixture-jaeger']})
   incident_store=incidents.IncidentStore(store)
   async def fixture_alerts(config,endpoints):
    return {'checked_at':'2026-09-01T10:06:00Z','status':'collected','source_outcomes':[],
     'alerts':[{'state':'firing','fingerprint':'a'*64,'active_at':'2026-09-01T10:01:00Z','service':'fixture-service','name':'FixtureError','severity':'critical','source_id':'fixture-prometheus'}]}
   intake_worker=intake.AlertIntake(incident_store,{},fixture_alerts)
   admitted=await intake_worker.scan('contract-test','fixture-app')
   fixture_incident_id=admitted['incident_ids'][0]
   assert (await intake_worker.scan('contract-test','fixture-app'))['existing']==1
   assert incident_store.get('contract-test','fixture-app',fixture_incident_id)['state']=='waiting_for_context'
   channel,publisher,_=await broker.topology(connection,namespace,{})
   unroutable=False
   try: await store.dispatch(publisher)
   except Exception: unroutable=True
   assert unroutable, 'Unroutable publish must fail confirmation'
   with engine.connect() as c:
    assert c.execute(select(core.outbox.c.published)).scalar_one()==0
   await channel.close()
   channel,publisher,queues=await broker.topology(connection,namespace,{
    'discovery':'application.discovery.requested',
    'context':'application.context.requested',
    'discovery-observer':'application.discovery.requested',
    'incident-admission':'application.context.ready','incident-collection':'incident.collection.requested','incident-analysis':'incident.analysis.requested'})
   retry,quarantine,recovery=await broker.recovery_routes(channel,namespace,'discovery','application.discovery.requested',delay_ms=10)
   assert await store.dispatch(publisher)==1
   observer=await queues['discovery-observer'].get(timeout=10);await observer.ack()
   message=await queues['discovery'].get(timeout=10)
   class TemporaryFailure:
    async def handle(self,envelope): raise OSError('synthetic transient failure')
   await consumers.StageConsumer(TemporaryFailure(),retry,quarantine).handle(message)
   async def next_retry():
    for _ in range(100):
     item=await queues['discovery'].get(fail=False)
     if item is not None: return item
     await asyncio.sleep(0.05)
    raise AssertionError('Retry did not reach original consumer')
   message=await next_retry()
   assert message.headers['kaims-attempt']==2
   assert await queues['discovery-observer'].get(fail=False) is None
   envelope=json.loads(message.body)
   assert await worker.handle(envelope)
   # Simulate commit-before-ACK redelivery with a new durable store instance.
   restarted=core.Handoff(engine)
   worker=workers.OnboardingWorker(restarted,collector)
   assert not await worker.handle(envelope)
   await message.ack()
   assert await restarted.dispatch(publisher)==1
   message=await queues['context'].get(timeout=10)
   envelope=json.loads(message.body)
   assert 'sources' not in envelope and len(message.body)<16384
   document=restarted.artifact('contract-test','fixture-app',envelope['artifact_refs'][0])
   assert document['sources'][0]['status']=='collected'
   assert document['documents'][0]['content']=='Synthetic contract-test document'
   assert await worker.handle(envelope)
   await message.ack()
   assert await restarted.dispatch(publisher)==1
   ready=await queues['incident-admission'].get(timeout=10)
   assert json.loads(ready.body)['topic']=='application.context.ready'
   await quarantine(ready,'synthetic quarantine check')
   quarantined=await recovery[1].get(timeout=10)
   assert quarantined.body==ready.body
   await quarantined.ack()
   async def serve_fixture(reader,writer):
    try:
     request=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),5)
     from urllib.parse import urlsplit,parse_qs
     target=request.split(b' ')[1].decode();parsed=urlsplit(target);params=parse_qs(parsed.query)
     if parsed.path=='/api/v1/query':
      assert params['query']==['service_error_ratio{service_name="fixture-service"}[121s]']
      body=json.dumps({'status':'success','data':{'resultType':'matrix','result':[{'metric':{'service_name':'fixture-service'},'values':[[1788257100,'0.15']]}]}}).encode()
     elif parsed.path=='/api/traces':
      assert params['service']==['fixture-service']
      trace_id='a'*32
      parent={'traceID':trace_id,'spanID':'1'*16,'processID':'p','startTime':1788257100000000,'duration':20000,'operationName':'fixture request','tags':[{'key':'error','value':True}],'references':[]}
      child={**parent,'spanID':'2'*16,'startTime':1788257100001000,'duration':10000,'tags':[{'key':'peer.service','value':'database'},{'key':'error','value':True}],
       'references':[{'refType':'CHILD_OF','traceID':trace_id,'spanID':'1'*16}]}
      body=json.dumps({'data':[{'traceID':trace_id,'processes':{'p':{'serviceName':'fixture-service','tags':[]}},'spans':[parent,child]}]}).encode()
     elif parsed.path=='/loki/api/v1/query_range':
      assert params['query']==['{service_name="fixture-service"}']
      body=json.dumps({'status':'success','data':{'resultType':'streams','result':[{'stream':{'service_name':'fixture-service'},'values':[['1788257100000000000','Synthetic operational timeout']]}]}}).encode()
     else:
      assert b'service=fixture-service' in request and b'window_start=' in request and b'window_end=' in request
      body=json.dumps({'records':[{'kind':'metric','service':'fixture-service','observed_at':'2026-09-01T10:05:00Z','metric':'error_rate_ratio','value':0.15,'source_uri':'metric://fixture/errors'}]}).encode()
     writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body)
     await writer.drain()
    finally:
     writer.close();await writer.wait_closed()
   server=await asyncio.start_server(serve_fixture,'127.0.0.1',0)
   async with server:
    port=server.sockets[0].getsockname()[1]
    incident_worker=incidents.IncidentWorker(incident_store,telemetry.TelemetryCollector({'fixture-telemetry':{'url':'http://127.0.0.1:'+str(port)+'/records'},
     'fixture-prometheus':{'type':'prometheus','url':'http://127.0.0.1:'+str(port),'metric_name':'service_error_ratio','metric':'error_rate_ratio'},
     'fixture-loki':{'type':'loki','url':'http://127.0.0.1:'+str(port)},
     'fixture-jaeger':{'type':'jaeger','url':'http://127.0.0.1:'+str(port)}}))
    await incident_worker.handle(json.loads(ready.body));await ready.ack()
    for queue in ('incident-collection','incident-analysis'):
     assert await store.dispatch(publisher)==1
     message=await queues[queue].get(timeout=10)
     envelope=json.loads(message.body)
     assert await incident_worker.handle(envelope)
     assert not await incident_worker.handle(envelope)
     await message.ack()
    result=incident_store.get('contract-test','fixture-app',fixture_incident_id)
    assert result['state']=='assessed'
    assert all(outcome['status']=='collected' and outcome['accepted']==(2 if outcome['source_id']=='fixture-jaeger' else 1) for outcome in result['result']['source_outcomes'])
    assert result['result']['impact']['status']=='observed_service_errors'
    assert result['result']['rca']['confirmed_cause'] is None
    assert len(result['result']['rca']['trace_relationships'])==1
    assert result['result']['rca']['status']=='hypotheses_only'
    assert result['result']['resolution']['status']=='blocked'
   server.close();await server.wait_closed()
   with engine.connect() as c:
    assert c.execute(select(core.applications.c.state)).scalar_one()=='context_ready'
   engine.dispose()
   print(json.dumps({'real_broker':True,'unroutable_publish_retained':True,'onboarding_to_discovery':True,
     'discovery_to_context':True,'context_ready_delivered':True,'duplicate_after_commit_ignored':True,
     'reference_messages_only':True,'confirmed_retry_relay':True,'retry_isolated_from_siblings':True,'confirmed_quarantine':True,'actual_file_discovery':True,'fixtures_only':True,'live_rca_qualified':False,'waiting_incident_released':True,'http_telemetry_collected':True,'incident_assessed':True,'impact_separate_from_rca':True,'unverified_resolution_blocked':True,'native_prometheus_fixture':True,'native_loki_fixture':True,'native_jaeger_fixture':True,'trace_relationships_preserved':True,'automatic_alert_admission':True,'repeated_alert_deduplicated':True}))
 finally:
  for queue in [*queues.values(),*recovery]: await queue.delete(if_unused=False,if_empty=False)
  channel=await connection.channel()
  for name in (namespace,namespace+".retry",namespace+".dead",namespace+".discovery.replay"):
   await channel.exchange_delete(name)
  await connection.close()
async def bounded():
 async with asyncio.timeout(60):
  await main()
asyncio.run(bounded())
"""
result=subprocess.run(['docker','exec','-i','kaims-api-gateway-1','python','-c',runner],
                      input=json.dumps(sources),text=True,capture_output=True,timeout=120)
if result.returncode:
    raise SystemExit(result.stderr)
report=json.loads(result.stdout)
(root/'rabbitmq-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))

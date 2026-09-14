"""Read-only live Jaeger check; stores counts, not trace contents."""
import asyncio,json,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from kaims_next.telemetry import TelemetryCollector,assess
async def main():
    end=datetime.now(timezone.utc)
    request={"service":"api-gateway","window_start":(end-timedelta(minutes=15)).isoformat(),"window_end":end.isoformat()}
    collector=TelemetryCollector({"local-jaeger":{"type":"jaeger","url":"http://127.0.0.1:16686"}})
    evidence=await collector.collect({"telemetry_sources":["local-jaeger"]},request)
    report={"real_jaeger":True,"read_only":True,"source_outcomes":evidence["source_outcomes"],
        "records":len(evidence["records"]),"relationships":len(assess(evidence)["rca"]["trace_relationships"]),"live_rca_qualified":False}
    (root/"jaeger-verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))
    assert evidence["records"], "No accepted live Jaeger spans; adapter not qualified"
if __name__=="__main__":asyncio.run(main())

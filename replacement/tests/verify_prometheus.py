"""Read-only native adapter check against the local monitoring Prometheus."""
import asyncio
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from kaims_next.telemetry import TelemetryCollector


async def main():
    end=datetime.now(timezone.utc)
    request={"service":"telemetry-monitoring","window_start":(end-timedelta(minutes=2)).isoformat(),"window_end":end.isoformat()}
    collector=TelemetryCollector({"local-prometheus":{"type":"prometheus","url":"http://127.0.0.1:9090",
        "service_label":"job","metric_name":"prometheus_http_requests_total","metric":"request_count"}})
    result=await collector.collect({"telemetry_sources":["local-prometheus"]},request)
    report={"real_prometheus":True,"read_only":True,"scope_label":"job","scope_value":"telemetry-monitoring",
        "source_outcomes":result["source_outcomes"],"records":len(result["records"]),"live_rca_qualified":False}
    (root/"prometheus-verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))
    assert result["records"], "Live adapter sample qualification failed"
    assert result["source_outcomes"][0]["status"]=="collected"


if __name__=="__main__": asyncio.run(main())

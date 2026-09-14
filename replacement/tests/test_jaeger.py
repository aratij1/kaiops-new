import asyncio
import copy
import sys
from pathlib import Path
import httpx
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))
from kaims_next.telemetry import TelemetryCollector,assess
from kaims_next.native_telemetry import nanoseconds,native_request

REQUEST={"service":"gateway","window_start":"2026-09-01T10:00:00Z","window_end":"2026-09-01T10:10:00Z"}
TRACE="a"*32
PARENT="1"*16
CHILD="2"*16
ENDPOINT={"type":"jaeger","url":"https://fixture.test"}


def fixture():
    parent={"traceID":TRACE,"spanID":PARENT,"processID":"p","startTime":nanoseconds(REQUEST["window_start"])//1000+1000,
        "duration":20000,"operationName":"GET /health","tags":[{"key":"error","value":True}],"references":[]}
    child={**parent,"spanID":CHILD,"startTime":parent["startTime"]+1000,"duration":10000,
        "tags":[{"key":"error","value":True},{"key":"peer.service","value":"database"}],
        "references":[{"refType":"CHILD_OF","traceID":TRACE,"spanID":PARENT}]}
    return {"data":[{"traceID":TRACE,"processes":{"p":{"serviceName":"gateway","tags":[]}},"spans":[parent,child]}]}


def collect(payload,endpoint=ENDPOINT):
    async def run():
        transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload))
        return await TelemetryCollector({"j":endpoint},transport=transport).collect({"telemetry_sources":["j"]},REQUEST)
    return asyncio.run(run())


def test_native_trace_parent_child_and_hypothesis():
    result=collect(fixture())
    assert len(result["records"])==2
    assert result["records"][1]["duration_ms"]==10
    assessment=assess(result)
    assert assessment["rca"]["status"]=="hypotheses_only"
    assert assessment["rca"]["confirmed_cause"] is None
    assert assessment["rca"]["trace_relationships"][0]["both_spans_failed"] is True
    assert assessment["impact"]["status"]=="observed_failed_spans"
    assert assessment["impact"]["customer_impact"]=="not_established"


@pytest.mark.parametrize("change",[
    {"traceID":"b"*32},{"startTime":0},{"duration":-1},{"spanID":"invalid"},
    {"references":[{"refType":"CHILD_OF","traceID":"b"*32,"spanID":PARENT}]},
    {"references":[{"refType":"CHILD_OF","traceID":TRACE,"spanID":CHILD}]},
])
def test_malformed_or_stale_child_is_rejected(change):
    payload=fixture();payload["data"][0]["spans"][1].update(change)
    result=collect(payload)
    assert len(result["records"])==1
    assert result["source_outcomes"][0]["rejected"]==1
    assert assess(result)["rca"]["trace_relationships"]==[]


def test_returned_process_scope_checked_without_relabelling():
    payload=fixture();payload["data"][0]["processes"]["p"]["serviceName"]="foreign"
    assert collect(payload)["records"]==[]
    assert collect(fixture(),{**ENDPOINT,"tags":{"environment":"prod"}})["records"]==[]


def test_string_error_is_not_boolean_error():
    payload=fixture()
    for span in payload["data"][0]["spans"]: span["tags"]=[{"key":"error","value":"true"}]
    assert all(not r["error"] for r in collect(payload)["records"])


def test_conflicting_duplicate_spans_cannot_create_relationship():
    payload=fixture();other=copy.deepcopy(payload["data"][0]["spans"][0]);other["duration"]+=1
    payload["data"][0]["spans"].append(other)
    assert assess(collect(payload))["rca"]["trace_relationships"]==[]


def test_query_uses_microsecond_window_and_service():
    url,params=native_request(ENDPOINT,REQUEST,2000)
    assert url.endswith("/api/traces")
    assert params["service"]=="gateway"
    assert params["start"]==nanoseconds(REQUEST["window_start"])//1000
    assert params["limit"]==20


def test_query_errors_do_not_look_like_complete_results():
    payload=fixture();payload["errors"]=[{"msg":"source unavailable"}]
    result=collect(payload)
    assert result["source_outcomes"][0]["status"]=="partial"


def test_cyclic_parent_references_are_not_relationship_evidence():
    payload=fixture()
    parent=payload["data"][0]["spans"][0]
    parent["references"]=[{"refType":"CHILD_OF","traceID":TRACE,"spanID":CHILD}]
    assert assess(collect(payload))["rca"]["trace_relationships"]==[]


def test_failure_details_survive_and_nested_spans_not_counted_as_requests():
    payload=fixture()
    for span in payload["data"][0]["spans"]:
        span["tags"].extend([{"key":"http.response.status_code","type":"int64","value":503},{"key":"exception.type","type":"string","value":"ConnectionError"}])
    result=collect(payload)
    assert all(r["http_status_code"]==503 for r in result["records"])
    assessment=assess(result)
    assert assessment["impact"]["sampled_error_traces"]==1
    assert assessment["rca"]["failure_findings"]
    assert "HTTP 503" in assessment["rca"]["failure_findings"][0]["details"]
    assert "ConnectionError" in assessment["rca"]["failure_findings"][0]["details"]
    assert assessment["rca"]["confirmed_cause"] is None


def test_latency_findings_include_measured_ranges_and_dependency_correlations():
    payload=fixture()
    payload["data"][0]["processes"]["p"]["serviceName"]="frontend"
    payload["data"][0]["processes"]["d"]={"serviceName":"product-catalog","tags":[]}
    child=payload["data"][0]["spans"][1]
    child["processID"]="d"
    async def _collect_with_dependencies():
        transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload))
        return await TelemetryCollector({"j":{**ENDPOINT,"dependency_services":{"frontend":["product-catalog"]}}},transport=transport).collect({"telemetry_sources":["j"],"services":["frontend","product-catalog"]},{**REQUEST,"service":"frontend"})
    result=asyncio.run(_collect_with_dependencies())
    assessment=assess(result,request={"service":"frontend"})
    findings=assessment["rca"]["failure_findings"]
    assert any("Measured latency" in f["finding"] and "0.010-0.010" in f["details"][0] for f in findings)
    assert any("Correlated dependency: frontend -> product-catalog" in f["finding"] for f in findings)

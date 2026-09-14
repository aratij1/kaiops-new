import asyncio
import sys
from pathlib import Path
import httpx
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))
from kaims_next.telemetry import TelemetryCollector, assess
from kaims_next.native_telemetry import native_request, nanoseconds

REQUEST={"service":"gateway","window_start":"2026-09-01T10:00:00Z","window_end":"2026-09-01T10:10:00Z"}
STAMP=nanoseconds("2026-09-01T10:05:00Z")
PROM={"type":"prometheus","url":"https://fixture.test","metric_name":"service_error_ratio","metric":"error_rate_ratio"}
LOKI={"type":"loki","url":"https://fixture.test"}


def collect(endpoint,payload,**kwargs):
    async def run():
        transport=httpx.MockTransport(lambda request:httpx.Response(200,json=payload))
        return await TelemetryCollector({"native":endpoint},transport=transport,**kwargs).collect({"telemetry_sources":["native"]},REQUEST)
    return asyncio.run(run())


def matrix(values,labels=None):
    return {"status":"success","data":{"resultType":"matrix","result":[{"metric":labels or {"service_name":"gateway"},"values":values}]}}


def streams(values,labels=None):
    return {"status":"success","data":{"resultType":"streams","result":[{"stream":labels or {"service_name":"gateway"},"values":values}]}}


def test_prometheus_reads_raw_samples_not_evaluation_timestamps():
    url,params=native_request(PROM,REQUEST,2000)
    assert url.endswith("/api/v1/query")
    assert params["query"]=='service_error_ratio{service_name="gateway"}[601s]'
    assert params["time"]==REQUEST["window_end"]
    result=collect(PROM,matrix([[STAMP/1e9,"0.2"],[(STAMP-900000000000)/1e9,"0.9"]]))
    assert result["source_outcomes"][0]["status"]=="partial"
    assert len(result["records"])==1
    assert result["records"][0]["observed_at"]=="2026-09-01T10:05:00+00:00"
    assert assess(result)["impact"]["status"]=="observed_service_errors"


def test_metric_unit_conversion_is_explicit():
    endpoint={**PROM,"metric":"latency_p99_ms","multiplier":1000}
    result=collect(endpoint,matrix([[STAMP/1e9,"0.25"]]))
    assert result["records"][0]["value"]==250
    assert assess(result)["impact"]["status"]=="not_established"


@pytest.mark.parametrize("value",["NaN","+Inf","-1","1.5",True])
def test_invalid_raw_error_ratios_are_not_evidence(value):
    result=collect(PROM,matrix([[STAMP/1e9,value]]))
    assert result["records"]==[]
    assert result["source_outcomes"][0]["rejected"]==1


@pytest.mark.parametrize("labels",[{"service_name":"other"},{"job":"gateway"},{"service_name":"gateway","environment":"dev"}])
def test_native_series_must_match_returned_service_and_environment(labels):
    result=collect({**PROM,"labels":{"environment":"prod"}},matrix([[STAMP/1e9,"0.2"]],labels))
    assert result["records"]==[]
    assert result["source_outcomes"][0]["status"]=="partial"


def test_loki_preserves_nanosecond_identity_and_reports_limit():
    url,params=native_request(LOKI,REQUEST,2)
    assert url.endswith("/loki/api/v1/query_range")
    assert params["start"]==str(nanoseconds(REQUEST["window_start"]))
    assert params["end"]==str(nanoseconds(REQUEST["window_end"])+1)
    result=collect(LOKI,streams([[str(STAMP),"timeout"],[str(STAMP+1),"timeout"]]),max_records=2)
    assert len(result["records"])==2
    assert result["records"][0]["evidence_id"]!=result["records"][1]["evidence_id"]
    assert result["source_outcomes"][0]["warnings"]==["log_limit_reached"]
    assert result["source_outcomes"][0]["status"]=="partial"


@pytest.mark.parametrize("path",["/data/landing/a.json","C:\\data\\ingested_alerts\\a.json","/data/%6canding/a.json"])
def test_loki_ingestion_artifacts_are_rejected(path):
    result=collect(LOKI,streams([[str(STAMP),"alert received"]],{"service_name":"gateway","filename":path}))
    assert result["records"]==[]
    assert result["source_outcomes"][0]["rejected"]==1


def test_loki_rejects_sample_one_nanosecond_after_window_end():
    result=collect(LOKI,streams([[str(nanoseconds(REQUEST["window_end"])+1),"too late"]]))
    assert result["records"]==[]


def test_source_query_failure_is_distinct_from_no_matches():
    failed=collect(PROM,{"status":"error","error":"private source detail"})
    empty=collect(PROM,{"status":"success","data":{"resultType":"matrix","result":[]}})
    assert failed["source_outcomes"][0]["status"]=="failed"
    assert "private source detail" not in str(failed)
    assert empty["source_outcomes"][0]["status"]=="no_matches"


def test_label_values_are_quoted_and_metric_expressions_rejected():
    import json
    service='gateway"} or up{job="'
    _,params=native_request(PROM,{**REQUEST,"service":service},2000)
    assert params["query"]=='service_error_ratio{service_name='+json.dumps(service)+'}[601s]'
    with pytest.raises(ValueError): native_request({**PROM,"metric_name":"rate(errors[5m])"},REQUEST,2000)


def test_source_warnings_do_not_look_complete():
    payload=matrix([[STAMP/1e9,"0.2"]]);payload["warnings"]=["partial response"]
    result=collect(PROM,payload)
    assert result["source_outcomes"][0]["status"]=="partial"


def test_fixed_service_sse_observations_do_not_claim_outage_or_cause():
    endpoint={**PROM,"fixed_service":"gateway","labels":{"job":"gateway-only","instance":"gateway:8000"},"metric_name":"kaiops_sse_connections","metric":"sse_connections"}
    url,params=native_request(endpoint,REQUEST,2000)
    assert 'service_name=' not in params["query"]
    data=collect(endpoint,matrix([[STAMP/1e9,"0"]],{"job":"gateway-only","instance":"gateway:8000"}))
    assert data["source_outcomes"][0]["accepted"]==1
    result=assess(data)
    assert result["rca"]["confirmed_cause"] is None
    assert result["impact"]["status"]=="not_established"
    assert result["rca"]["observations"][0]["finding"]=="All collected SSE connection samples are zero."
    assert len(result["rca"]["next_checks"])==2
    wrong=collect(endpoint,matrix([[STAMP/1e9,"0"]],{"job":"unrelated","instance":"gateway:8000"}))
    assert wrong["records"]==[]
    with pytest.raises(ValueError): native_request(endpoint,{**REQUEST,"service":"other"},2000)
    with pytest.raises(ValueError): native_request({**endpoint,"labels":{}},REQUEST,2000)


def test_cumulative_counters_are_not_impact_measurements():
    data=collect({**PROM,"metric":"request_count"},matrix([[STAMP/1e9,"5250"],[STAMP/1e9+15,"5250"]]))
    result=assess(data)
    assert result["impact"]["measurements"]==[]
    assert result["impact"]["counter_sample_count"]==2
    assert result["impact"]["status"]=="not_established"
